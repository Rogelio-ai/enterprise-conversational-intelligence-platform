from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.payments.contracts import (
    PaymentExecutionOutcome,
    PaymentRecoveryOutcome,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _open_and_join,
    _preview,
    _product,
    _scope,
    _staff_headers,
)


def _client(settings, executor=None):
    executors = {} if executor is None else {'deterministic': executor}
    return TestClient(create_app(settings=settings, payment_executors=executors))


def _grant(connection, tenant_id: int, *, configure_executor: bool = True) -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1', (tenant_id,))
        role_id = cursor.fetchone()['id']
        for code in (
            'restaurant_check.read', 'restaurant_check.manage',
            'restaurant_payment.read', 'restaurant_payment.manage', 'restaurant_payment.recover',
        ):
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = cursor.fetchone()['id']
            cursor.execute(
                'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
                (role_id, permission_id),
            )
        if configure_executor:
            cursor.execute(
                '''
                SELECT organization_id,id AS location_id
                FROM locations WHERE tenant_id=%s ORDER BY id LIMIT 1
                ''',
                (tenant_id,),
            )
            owner = cursor.fetchone()
            cursor.execute(
                '''
                INSERT INTO location_payment_executor_configurations (
                    tenant_id,organization_id,location_id,executor_key,display_name,
                    adapter_kind,topology,status,selection_priority
                ) VALUES (%s,%s,%s,'deterministic','Deterministic','deterministic',
                    'EXTERNAL','ACTIVE',100)
                ''',
                (tenant_id, owner['organization_id'], owner['location_id']),
            )
            configuration_id = cursor.lastrowid
            cursor.execute(
                '''
                INSERT INTO location_payment_executor_capabilities (
                    executor_configuration_id,tenant_id,organization_id,location_id,
                    method_category,currency
                ) VALUES (%s,%s,%s,%s,'CARD','MXN')
                ''',
                (
                    configuration_id,
                    tenant_id,
                    owner['organization_id'],
                    owner['location_id'],
                ),
            )


def _order(client, connection, scope, diner_headers, amount='100'):
    product_id = _product(connection, scope, amount=amount)
    preview = _preview(client, diner_headers, product_id)
    response = _confirm(client, diner_headers, preview, f'payment-order-{product_id}')
    assert response.status_code == 201, response.text
    return response.json()


def _check(client, diner_headers, key='payment-check'):
    response = client.post(
        '/diner/restaurant-checks',
        headers={**diner_headers, 'Idempotency-Key': key},
        json={'mode': 'INDIVIDUAL'},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join_opened(client, opened, name):
    joined = client.post('/diner-sessions/join', json={
        'join_context_key': opened['join_context_key'],
        'access_code': opened['access_code'],
        'display_name': name,
    })
    assert joined.status_code == 201, joined.text
    return {'Authorization': f"Bearer {joined.json()['access_token']}"}


def _electronic_payload(check, amount, diner_id, credential='test-ephemeral-token'):
    return {
        'expected_check_version': check['version'],
        'expected_check_fingerprint': check['fingerprint'],
        'amount': str(amount), 'currency': check['currency'],
        'method_category': 'CARD', 'payer_type': 'DINER',
        'payer_diner_session_id': diner_id,
        'executor_key': 'deterministic',
        'execution_credential': credential,
    }


def test_cash_auto_freeze_exact_settlement_keeps_lock_until_continuation_yes(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers)
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payment = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**_staff_headers(client, scope), 'Idempotency-Key': 'cash-full'},
            json={
                'expected_check_version': check['version'],
                'expected_check_fingerprint': check['fingerprint'],
                'amount': '100', 'currency': 'MXN', 'method_category': 'CASH',
                'payer_type': 'DINER', 'payer_diner_session_id': diner_id,
                'cash_tendered_amount': '150',
            },
        )
        assert payment.status_code == 201, payment.text
        body = payment.json()
        assert body['state'] == 'SUCCEEDED'
        assert Decimal(body['amount']) == Decimal('100')
        assert Decimal(body['cash_change_due']) == Decimal('50')
        settled = client.get(
            f"/diner/restaurant-checks/{check['id']}/settlement", headers=diner_headers
        )
        assert settled.status_code == 200, settled.text
        assert settled.json()['check_status'] == 'SETTLED'
        assert Decimal(settled.json()['confirmed_settlement']) == Decimal('100')
        assert settled.json()['available_to_initiate'] == '0.0000'
        blocked = client.post('/diner/order-draft', headers=diner_headers)
        assert blocked.status_code == 409
        check_projection = client.get(
            f"/diner/restaurant-checks/{check['id']}", headers=diner_headers,
        ).json()
        assert check_projection['signal'] == 'SERVICE_CONTINUATION_DECISION_REQUIRED'
        assert check_projection['continuation_decision'] == 'PENDING'
        continued = client.post(
            f"/diner/restaurant-checks/{check['id']}/continuation-decision",
            headers={**diner_headers, 'Idempotency-Key': 'continue-after-cash'},
            json={'expected_version': check['version'], 'decision': 'YES'},
        )
        assert continued.status_code == 200, continued.text
        assert continued.json()['continuation_decision'] == 'YES'
        assert client.post('/diner/order-draft', headers=diner_headers).status_code == 201
        balance = client.get(
            f"/restaurant-service-sessions/{opened['id']}/outstanding-balance",
            headers=_staff_headers(client, scope),
        ).json()
        assert balance['closure_eligible'] is True
        assert balance['service_continuation_decision_required'] is False
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,settled_at FROM restaurant_checks WHERE id=%s', (check['id'],))
        assert cursor.fetchone()['status'] == 'SETTLED'
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_check_settlements WHERE payment_id=%s', (body['id'],))
        assert cursor.fetchone()['count'] == 1
        cursor.execute('SELECT state,ownership_slot FROM restaurant_check_allocations WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone() == {'state': 'SETTLED', 'ownership_slot': 1}
        cursor.execute('SELECT active_slot FROM restaurant_check_members WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone()['active_slot'] is None


def test_uncertain_reserves_capacity_multiple_payers_and_recovery_finalizes(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN, PaymentExecutionOutcome.SUCCEEDED),
        recovery_outcomes=(PaymentRecoveryOutcome.CONFIRMED_SUCCESS,),
    )
    with _client(integration_settings, executor) as client:
        opened, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'uncertain-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        first = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'uncertain-40'},
            json=_electronic_payload(check, '40', diner_id),
        )
        assert first.status_code == 201, first.text
        assert first.json()['state'] == 'UNCERTAIN'
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE restaurant_payments SET state='RESERVED' WHERE id=%s",
                (first.json()['id'],),
            )
        balance = client.get(
            f"/restaurant-service-sessions/{opened['id']}/outstanding-balance",
            headers=_staff_headers(client, scope),
        ).json()
        assert Decimal(balance['pending_exposure']) == Decimal('0')
        assert Decimal(balance['reserved_payment_exposure']) == Decimal('40')
        assert Decimal(balance['uncertain_exposure']) == Decimal('0')
        assert balance['closure_eligible'] is False
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE restaurant_payments SET state='UNCERTAIN' WHERE id=%s",
                (first.json()['id'],),
            )
        over = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**_staff_headers(client, scope), 'Idempotency-Key': 'over-after-uncertain'},
            json={
                **_electronic_payload(check, '70', diner_id),
                'payer_type': 'OTHER', 'payer_diner_session_id': None,
                'payer_reference': 'second-payer',
            },
        )
        assert over.status_code == 409
        assert over.json()['error']['code'] == 'PAYMENT_AMOUNT_EXCEEDS_AVAILABLE_LIABILITY'
        second = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**_staff_headers(client, scope), 'Idempotency-Key': 'other-payer-60'},
            json={
                **_electronic_payload(check, '60', diner_id),
                'payer_type': 'OTHER', 'payer_diner_session_id': None,
                'payer_reference': 'second-payer',
            },
        )
        assert second.status_code == 201, second.text
        assert second.json()['state'] == 'SUCCEEDED'
        projection = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=_staff_headers(client, scope),
        ).json()
        assert projection['check_status'] == 'FROZEN'
        assert Decimal(projection['confirmed_settlement']) == Decimal('60')
        assert Decimal(projection['uncertain_exposure']) == Decimal('40')
        assert Decimal(projection['available_to_initiate']) == Decimal('0')
        recovered = client.post(
            f"/restaurant-payments/{first.json()['id']}/recover",
            headers=_staff_headers(client, scope),
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['state'] == 'SUCCEEDED'
        duplicate_recovery = client.post(
            f"/restaurant-payments/{first.json()['id']}/recover",
            headers=_staff_headers(client, scope),
        )
        assert duplicate_recovery.status_code == 409
        assert duplicate_recovery.json()['error']['code'] == 'PAYMENT_STATE_CONFLICT'
        final = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=_staff_headers(client, scope),
        ).json()
        assert final['check_status'] == 'SETTLED'
        assert Decimal(final['confirmed_settlement']) == Decimal('100')
        assert executor.execution_calls == 2
        assert executor.recovery_calls == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_check_settlements WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone()['count'] == 2


def test_duplicate_initiation_one_execution_and_conflicting_reuse(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'duplicate-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payload = _electronic_payload(check, '40', diner_id)
        first = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'same-payment'}, json=payload,
        )
        replay = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'same-payment'}, json=payload,
        )
        assert first.status_code == 201 and replay.status_code == 200
        assert first.json()['id'] == replay.json()['id']
        assert executor.execution_calls == 1
        conflict = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'same-payment'},
            json=_electronic_payload(check, '30', diner_id),
        )
        assert conflict.status_code == 409
        assert conflict.json()['error']['code'] == 'PAYMENT_IDEMPOTENCY_CONFLICT'


def test_diner_cannot_confirm_cash_and_failed_rejected_have_no_settlement(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor(execution_outcomes=(
        PaymentExecutionOutcome.DEFINITE_FAILURE, PaymentExecutionOutcome.REJECTED,
    ))
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'failure-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        denied = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'diner-cash'},
            json={
                'expected_check_version': check['version'],
                'expected_check_fingerprint': check['fingerprint'],
                'amount': '10', 'currency': 'MXN', 'method_category': 'CASH',
                'payer_type': 'DINER', 'payer_diner_session_id': diner_id,
                'cash_tendered_amount': '10',
            },
        )
        assert denied.status_code == 403
        states = []
        for key in ('failure', 'rejection'):
            response = client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': key},
                json=_electronic_payload(check, '20', diner_id),
            )
            assert response.status_code == 201, response.text
            states.append(response.json()['state'])
        assert states == ['FAILED', 'REJECTED']
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_check_settlements WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone()['count'] == 0


def test_two_simultaneous_full_balance_payments_have_one_winner(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'race-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        staff = _staff_headers(client, scope)

        def pay(key):
            return client.post(
                f"/restaurant-checks/{check['id']}/payments",
                headers={**staff, 'Idempotency-Key': key},
                json={
                    **_electronic_payload(check, '100', diner_id),
                    'payer_type': 'OTHER', 'payer_diner_session_id': None,
                    'payer_reference': key,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = (pool.submit(pay, 'race-a'), pool.submit(pay, 'race-b'))
            results = tuple(value.result() for value in responses)
        assert sorted(value.status_code for value in results) == [201, 409], [value.text for value in results]
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s AND state='SUCCEEDED'", (check['id'],))
        assert cursor.fetchone()['count'] == 1
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_check_settlements WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone()['count'] == 1


def test_recovery_absence_releases_capacity_retry_reacquires_and_uncertainty_remains_reserved(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(
            PaymentExecutionOutcome.UNCERTAIN,
            PaymentExecutionOutcome.SUCCEEDED,
            PaymentExecutionOutcome.UNCERTAIN,
        ),
        recovery_outcomes=(
            PaymentRecoveryOutcome.DEFINITE_ABSENCE,
            PaymentRecoveryOutcome.STILL_UNCERTAIN,
        ),
    )
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'recovery-outcomes-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        first = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'absence-40'},
            json=_electronic_payload(check, '40', diner_id),
        ).json()
        absent = client.post(
            f"/restaurant-payments/{first['id']}/recover",
            headers=_staff_headers(client, scope),
        )
        assert absent.status_code == 200, absent.text
        assert absent.json()['state'] == 'FAILED'
        retried = client.post(
            f"/restaurant-payments/{first['id']}/retry",
            headers=_staff_headers(client, scope),
            json={'execution_credential': 'new-ephemeral-token'},
        )
        assert retried.status_code == 200, retried.text
        assert retried.json()['state'] == 'SUCCEEDED'
        second = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'still-uncertain-20'},
            json=_electronic_payload(check, '20', diner_id),
        ).json()
        uncertain = client.post(
            f"/restaurant-payments/{second['id']}/recover",
            headers=_staff_headers(client, scope),
        )
        assert uncertain.status_code == 200, uncertain.text
        assert uncertain.json()['state'] == 'UNCERTAIN'
        projection = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=_staff_headers(client, scope),
        ).json()
        assert Decimal(projection['confirmed_settlement']) == Decimal('40')
        assert Decimal(projection['uncertain_exposure']) == Decimal('20')
        assert Decimal(projection['available_to_initiate']) == Decimal('40')


def test_expired_in_progress_attempt_is_fenced_before_recovery(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(PaymentRecoveryOutcome.CONFIRMED_SUCCESS,),
    )
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'stale-recovery-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payment = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'stale-full'},
            json=_electronic_payload(check, '100', diner_id),
        ).json()
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE restaurant_payments SET state='IN_PROGRESS',claim_token='expired-claim',"
                "claim_expires_at=DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE) WHERE id=%s",
                (payment['id'],),
            )
            cursor.execute(
                "UPDATE restaurant_payment_attempts SET result='IN_PROGRESS',claim_token='expired-claim',"
                "completed_at=NULL,error_code=NULL,error_message=NULL WHERE payment_id=%s "
                "ORDER BY attempt_sequence DESC LIMIT 1",
                (payment['id'],),
            )
        recovered = client.post(
            f"/restaurant-payments/{payment['id']}/recover",
            headers=_staff_headers(client, scope),
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['state'] == 'SUCCEEDED'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT attempt_type,result,error_code FROM restaurant_payment_attempts '
            'WHERE payment_id=%s ORDER BY attempt_sequence',
            (payment['id'],),
        )
        attempts = cursor.fetchall()
        assert attempts[0]['result'] == 'FENCED'
        assert attempts[0]['error_code'] == 'PAYMENT_STALE_ATTEMPT_FENCED'
        assert attempts[1]['attempt_type'] == 'STALE_RECOVERY'
        assert attempts[1]['result'] == 'SUCCEEDED'


def test_first_payment_vs_gratuity_mutation_has_one_authoritative_winner(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'payment-tip-race-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']

        def pay():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': 'payment-tip-race-pay'},
                json=_electronic_payload(check, '100', diner_id),
            )

        def tip():
            return client.put(
                f"/diner/restaurant-checks/{check['id']}/gratuity",
                headers={**diner_headers, 'Idempotency-Key': 'payment-tip-race-tip'},
                json={'expected_version': check['version'], 'input_type': 'FIXED_AMOUNT', 'input_value': '10'},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = (pool.submit(pay), pool.submit(tip))
            results = tuple(value.result() for value in responses)
        assert sum(value.status_code in (200, 201) for value in results) == 1
        assert sum(value.status_code == 409 for value in results) == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,gratuity_total FROM restaurant_checks WHERE id=%s', (check['id'],))
        persisted = cursor.fetchone()
        if persisted['status'] == 'SETTLED':
            assert Decimal(persisted['gratuity_total']) == Decimal('0')
        else:
            assert persisted['status'] == 'OPEN'
            assert Decimal(persisted['gratuity_total']) == Decimal('10')


def test_concurrent_partial_payments_serialize_to_exact_liability(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'partial-race-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']

        def pay(key, amount):
            return client.post(
                f"/restaurant-checks/{check['id']}/payments",
                headers={**_staff_headers(client, scope), 'Idempotency-Key': key},
                json={
                    **_electronic_payload(check, amount, diner_id),
                    'payer_type': 'OTHER', 'payer_diner_session_id': None,
                    'payer_reference': key,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = (pool.submit(pay, 'partial-race-a', '40'), pool.submit(pay, 'partial-race-b', '60'))
            results = tuple(value.result() for value in responses)
        assert [value.status_code for value in results] == [201, 201], [value.text for value in results]
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM restaurant_checks WHERE id=%s', (check['id'],))
        assert cursor.fetchone()['status'] == 'SETTLED'
        cursor.execute('SELECT SUM(amount) AS total FROM restaurant_check_settlements WHERE check_id=%s', (check['id'],))
        assert Decimal(cursor.fetchone()['total']) == Decimal('100')


def test_payment_vs_check_cancellation_has_one_winner(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with _client(integration_settings, executor) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'payment-cancel-race-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']

        def pay():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': 'payment-cancel-race-pay'},
                json=_electronic_payload(check, '100', diner_id),
            )

        def cancel():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/cancellation",
                headers={**diner_headers, 'Idempotency-Key': 'payment-cancel-race-cancel'},
                json={'expected_version': check['version'], 'reason': 'race certification'},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(value.result() for value in (pool.submit(pay), pool.submit(cancel)))
        assert sum(value.status_code in (200, 201) for value in results) == 1
        assert sum(value.status_code == 409 for value in results) == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM restaurant_checks WHERE id=%s', (check['id'],))
        assert cursor.fetchone()['status'] in ('SETTLED', 'CANCELLED')


def test_final_settlement_vs_ordering_reenable_is_atomic(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'settlement-order-race-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        staff = _staff_headers(client, scope)

        def settle():
            return client.post(
                f"/restaurant-checks/{check['id']}/payments",
                headers={**staff, 'Idempotency-Key': 'settlement-order-race-cash'},
                json={
                    'expected_check_version': check['version'],
                    'expected_check_fingerprint': check['fingerprint'],
                    'amount': '100', 'currency': 'MXN', 'method_category': 'CASH',
                    'payer_type': 'DINER', 'payer_diner_session_id': diner_id,
                    'cash_tendered_amount': '100',
                },
            )

        def order():
            return client.post('/diner/order-draft', headers=diner_headers)

        with ThreadPoolExecutor(max_workers=2) as pool:
            settlement, ordering = tuple(
                value.result() for value in (pool.submit(settle), pool.submit(order))
            )
        assert settlement.status_code == 201, settlement.text
        assert ordering.status_code in (201, 409), ordering.text
        assert client.post('/diner/order-draft', headers=diner_headers).status_code == 409
        continued = client.post(
            f"/restaurant-checks/{check['id']}/continuation-decision",
            headers={**staff, 'Idempotency-Key': 'race-continuation-yes'},
            json={'expected_version': check['version'], 'decision': 'YES'},
        )
        assert continued.status_code == 200, continued.text
        assert client.post('/diner/order-draft', headers=diner_headers).status_code == 201
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM restaurant_checks WHERE id=%s', (check['id'],))
        assert cursor.fetchone()['status'] == 'SETTLED'
        cursor.execute('SELECT active_slot FROM restaurant_check_members WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone()['active_slot'] is None


def test_diner_scope_does_not_lock_unrelated_diner_and_no_closes_only_target(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, first = _open_and_join(client, scope, name='Included')
        second = _join_opened(client, opened, 'Unrelated')
        _order(client, connection, scope, first, amount='100')
        check = _check(client, first, 'diner-scope-check')
        check = client.put(
            f"/diner/restaurant-checks/{check['id']}/gratuity",
            headers={**first, 'Idempotency-Key': 'diner-scope-tip'},
            json={'expected_version': check['version'], 'input_type': 'FIXED_AMOUNT', 'input_value': '10'},
        ).json()
        assert check['diner_scope_ids'] == [client.get('/diner-session', headers=first).json()['id']]
        assert check['table_scope_session_ids'] == []
        assert client.post('/diner/order-draft', headers=first).status_code == 409
        assert client.post('/diner/order-draft', headers=second).status_code == 201
        diner_id = client.get('/diner-session', headers=first).json()['id']
        paid = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**_staff_headers(client, scope), 'Idempotency-Key': 'diner-scope-cash'},
            json={
                'expected_check_version': check['version'],
                'expected_check_fingerprint': check['fingerprint'],
                'amount': '110', 'currency': 'MXN', 'method_category': 'CASH',
                'payer_type': 'DINER', 'payer_diner_session_id': diner_id,
                'cash_tendered_amount': '110',
            },
        )
        assert paid.status_code == 201, paid.text
        no = client.post(
            f"/diner/restaurant-checks/{check['id']}/continuation-decision",
            headers={**first, 'Idempotency-Key': 'diner-scope-no'},
            json={'expected_version': check['version'], 'decision': 'NO'},
        )
        assert no.status_code == 200, no.text
        assert client.post('/diner/order-draft', headers=first).status_code == 409
        ended = client.post('/diner-session/end', headers=first)
        assert ended.status_code == 200, ended.text
        assert ended.json()['status'] == 'ENDED'
        assert client.get('/diner-session', headers=second).status_code == 200
        current = client.get(
            f"/resources/{scope.resource_id}/service-sessions/current",
            headers=_staff_headers(client, scope),
        )
        assert current.status_code == 200
        assert current.json()['status'] == 'OPEN'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT acquired_version,released_version FROM restaurant_check_members '
            'WHERE check_id=%s AND diner_session_id=%s',
            (check['id'], diner_id),
        )
        assert cursor.fetchone() == {'acquired_version': 1, 'released_version': 2}


def test_table_scope_blocks_existing_and_new_diners_until_yes(
    integration_settings, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, controller = _open_and_join(client, scope, name='Controller')
        existing = _join_opened(client, opened, 'Existing')
        _order(client, connection, scope, controller, amount='100')
        created = client.post(
            '/diner/restaurant-checks',
            headers={**controller, 'Idempotency-Key': 'whole-table-check'},
            json={'mode': 'GLOBAL_TABLE'},
        )
        assert created.status_code == 201, created.text
        check = created.json()
        assert check['table_scope_session_ids'] == [opened['id']]
        assert check['diner_scope_ids'] == []
        assert client.post('/diner/order-draft', headers=existing).status_code == 409
        newcomer = _join_opened(client, opened, 'Newcomer')
        assert client.post('/diner/order-draft', headers=newcomer).status_code == 409
        controller_id = client.get('/diner-session', headers=controller).json()['id']
        staff = _staff_headers(client, scope)
        paid = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**staff, 'Idempotency-Key': 'whole-table-cash'},
            json={
                'expected_check_version': check['version'],
                'expected_check_fingerprint': check['fingerprint'],
                'amount': '100', 'currency': 'MXN', 'method_category': 'CASH',
                'payer_type': 'DINER', 'payer_diner_session_id': controller_id,
                'cash_tendered_amount': '100',
            },
        )
        assert paid.status_code == 201, paid.text
        assert client.post('/diner/order-draft', headers=newcomer).status_code == 409
        balance = client.get(
            f"/restaurant-service-sessions/{opened['id']}/outstanding-balance",
            headers=staff,
        ).json()
        assert balance['service_continuation_decision_required'] is True
        yes = client.post(
            f"/restaurant-checks/{check['id']}/continuation-decision",
            headers={**staff, 'Idempotency-Key': 'whole-table-yes'},
            json={'expected_version': check['version'], 'decision': 'YES'},
        )
        assert yes.status_code == 200, yes.text
        assert client.post('/diner/order-draft', headers=existing).status_code == 201
        assert client.post('/diner/order-draft', headers=newcomer).status_code == 201
        _order(client, connection, scope, controller, amount='25')
        second_cycle = client.post(
            '/diner/restaurant-checks',
            headers={**controller, 'Idempotency-Key': 'whole-table-check-cycle-2'},
            json={'mode': 'GLOBAL_TABLE'},
        )
        assert second_cycle.status_code == 201, second_cycle.text
        second_check = second_cycle.json()
        paid_again = client.post(
            f"/restaurant-checks/{second_check['id']}/payments",
            headers={**staff, 'Idempotency-Key': 'whole-table-cash-cycle-2'},
            json={
                'expected_check_version': second_check['version'],
                'expected_check_fingerprint': second_check['fingerprint'],
                'amount': '25', 'currency': 'MXN', 'method_category': 'CASH',
                'payer_type': 'DINER', 'payer_diner_session_id': controller_id,
                'cash_tendered_amount': '25',
            },
        )
        assert paid_again.status_code == 201, paid_again.text
        no = client.post(
            f"/restaurant-checks/{second_check['id']}/continuation-decision",
            headers={**staff, 'Idempotency-Key': 'whole-table-no-cycle-2'},
            json={'expected_version': second_check['version'], 'decision': 'NO'},
        )
        assert no.status_code == 200, no.text
        closed = client.post(
            f"/restaurant-service-sessions/{opened['id']}/close", headers=staff,
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()['status'] == 'CLOSED'
        reopened = client.post(
            f'/resources/{scope.resource_id}/service-sessions',
            headers=staff, json={'party_size': 2},
        )
        assert reopened.status_code == 201, reopened.text
        assert reopened.json()['id'] != opened['id']
        assert reopened.json()['access_code'] != opened['access_code']
