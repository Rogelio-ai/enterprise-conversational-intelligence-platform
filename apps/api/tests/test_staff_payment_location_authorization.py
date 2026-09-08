from __future__ import annotations

from app.restaurant.integrations.payments.contracts import (
    PaymentExecutionOutcome,
    PaymentRecoveryOutcome,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from test_canonical_order_commercial_acceptance import _scope, _staff_headers
from test_cash_payment_integration import (
    _grant_cash_permissions,
    _location,
    _payment_payload,
    _prepared_check,
    _register_and_session,
)
from test_restaurant_payment_settlement_foundation import (
    _client,
    _electronic_payload,
    _grant,
)
from test_staff_check_query import (
    _grant_location,
    _login,
    _membership,
    _membership_id,
    _new_check,
    _other_location,
    _table_scope,
)


def _financial_counts(connection, check_id: int) -> tuple[int, int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
            (check_id,),
        )
        payments = int(cursor.fetchone()['count'])
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE check_id=%s',
            (check_id,),
        )
        settlements = int(cursor.fetchone()['count'])
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_movements cm '
            'JOIN restaurant_payments rp ON rp.id=cm.restaurant_payment_id '
            'WHERE rp.check_id=%s',
            (check_id,),
        )
        movements = int(cursor.fetchone()['count'])
    return payments, settlements, movements


def test_staff_payment_requires_authoritative_location_before_execution_and_replay(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    owner_membership_id = _membership_id(connection, scope.email)
    _grant_location(connection, scope.tenant_id, owner_membership_id, scope.location_id)
    other_location = _other_location(connection, scope, 'PAYMENT-MISMATCH')
    _grant_location(
        connection, scope.tenant_id, owner_membership_id, other_location.location_id
    )
    permission_email, _ = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-payment-permission-no-grant',
        permissions=('restaurant_payment.manage',),
    )
    no_permission_email, no_permission_membership_id = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-payment-grant-no-permission',
        permissions=(),
    )
    _grant_location(
        connection, scope.tenant_id, no_permission_membership_id, scope.location_id
    )
    foreign = _scope(connection, f'{prefix}-payment-foreign')
    _grant(connection, foreign.tenant_id, configure_executor=False)
    foreign_membership_id = _membership_id(connection, foreign.email)
    _grant_location(
        connection, foreign.tenant_id, foreign_membership_id, foreign.location_id
    )
    executor = DeterministicPaymentExecutor()

    with _client(integration_settings, executor) as client:
        check, diner_headers = _new_check(client, connection, scope, 'staff-payment')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payload = _electronic_payload(check, '40', diner_id)
        staff_headers = _staff_headers(client, scope)
        url = f"/restaurant-checks/{check['id']}/payments"
        headers = {**staff_headers, 'Idempotency-Key': 'staff-location-card'}

        missing_location = client.post(url, headers=headers, json=payload)
        assert missing_location.status_code == 422, missing_location.text
        assert _financial_counts(connection, check['id']) == (0, 0, 0)
        assert executor.execution_calls == 0

        created = client.post(
            url,
            headers=headers,
            params={'location_id': scope.location_id},
            json=payload,
        )
        assert created.status_code == 201, created.text
        assert created.json()['state'] == 'SUCCEEDED'
        assert executor.execution_calls == 1

        replay = client.post(
            url,
            headers=headers,
            params={'location_id': scope.location_id},
            json=payload,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()['id'] == created.json()['id']
        assert replay.json()['state'] == created.json()['state']
        assert executor.execution_calls == 1

        mismatch_replay = client.post(
            url,
            headers=headers,
            params={'location_id': other_location.location_id},
            json=payload,
        )
        assert mismatch_replay.status_code == 404, mismatch_replay.text
        assert str(created.json()['id']) not in mismatch_replay.text
        assert 'instrument_last_four' not in mismatch_replay.text

        changed = client.post(
            url,
            headers=headers,
            params={'location_id': scope.location_id},
            json={**payload, 'amount': '41'},
        )
        assert changed.status_code == 409, changed.text
        assert changed.json()['error']['code'] == 'PAYMENT_IDEMPOTENCY_CONFLICT'

        foreign_check, _ = _new_check(
            client, connection, foreign, 'foreign-staff-payment'
        )
        denied_cases = (
            (
                _login(client, permission_email),
                scope.location_id,
                check['id'],
                404,
                'permission-no-grant',
            ),
            (
                _login(client, no_permission_email),
                scope.location_id,
                check['id'],
                403,
                'grant-no-permission',
            ),
            (
                staff_headers,
                other_location.location_id,
                check['id'],
                404,
                'requested-location-mismatch',
            ),
            (
                staff_headers,
                scope.location_id,
                foreign_check['id'],
                404,
                'foreign-check',
            ),
            (
                staff_headers,
                scope.location_id,
                check['id'] + 999999,
                404,
                'unknown-check',
            ),
        )
        counts_before = _financial_counts(connection, check['id'])
        for denied_headers, location_id, check_id, status, key in denied_cases:
            denied = client.post(
                f'/restaurant-checks/{check_id}/payments',
                headers={**denied_headers, 'Idempotency-Key': key},
                params={'location_id': location_id},
                json=payload,
            )
            assert denied.status_code == status, denied.text
            assert 'instrument_last_four' not in denied.text
        assert _financial_counts(connection, check['id']) == counts_before
        assert executor.execution_calls == 1

        diner_check, diner_payment_headers = _new_check(
            client,
            connection,
            _table_scope(connection, scope, 'DINER-PAYMENT'),
            'diner-payment-regression',
        )
        diner_payment_id = client.get(
            '/diner-session', headers=diner_payment_headers
        ).json()['id']
        diner_payment = client.post(
            f"/diner/restaurant-checks/{diner_check['id']}/payments",
            headers={
                **diner_payment_headers,
                'Idempotency-Key': 'diner-location-regression',
            },
            json=_electronic_payload(diner_check, '40', diner_payment_id),
        )
        assert diner_payment.status_code == 201, diner_payment.text


def test_cash_payment_requires_check_cash_session_and_grant_location_consistency(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    owner_membership_id = _membership_id(connection, scope.email)
    _grant_location(connection, scope.tenant_id, owner_membership_id, scope.location_id)
    wrong_location_id = _location(connection, scope)
    _grant_location(connection, scope.tenant_id, owner_membership_id, wrong_location_id)

    foreign = _scope(connection, f'{prefix}-cash-foreign')
    _grant(connection, foreign.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, foreign.tenant_id)
    foreign_membership_id = _membership_id(connection, foreign.email)
    _grant_location(
        connection, foreign.tenant_id, foreign_membership_id, foreign.location_id
    )

    with _client(integration_settings) as client:
        headers = _staff_headers(client, scope)
        register, session = _register_and_session(
            client, scope, headers, code='AUTHORIZED-CASH'
        )
        _, wrong_session = _register_and_session(
            client,
            scope,
            headers,
            code='WRONG-LOCATION-CASH',
            location_id=wrong_location_id,
        )
        foreign_headers = _staff_headers(client, foreign)
        _, foreign_session = _register_and_session(
            client, foreign, foreign_headers, code='FOREIGN-CASH'
        )

        check = _prepared_check(client, connection, scope)
        inbox = client.get(
            '/restaurant-checks',
            headers=headers,
            params={'location_id': scope.location_id},
        )
        assert inbox.status_code == 200, inbox.text
        assert check['id'] in [item['id'] for item in inbox.json()['items']]
        active = client.get(
            '/cash-sessions/active',
            headers=headers,
            params={
                'location_id': scope.location_id,
                'resource_id': register['id'],
            },
        )
        assert active.status_code == 200, active.text
        assert active.json()['id'] == session['id']

        accepted = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**headers, 'Idempotency-Key': 'authorized-cash-payment'},
            params={'location_id': scope.location_id},
            json=_payment_payload(
                check, amount='40', tendered='50', cash_session_id=session['id']
            ),
        )
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()['state'] == 'SUCCEEDED'
        assert _financial_counts(connection, check['id']) == (1, 1, 2)

        denied_check = _prepared_check(
            client, connection, _table_scope(connection, scope, 'DENIED-CASH')
        )
        assert _financial_counts(connection, denied_check['id']) == (0, 0, 0)
        for key, cash_session_id in (
            ('wrong-location-cash', wrong_session['id']),
            ('foreign-cash', foreign_session['id']),
        ):
            denied = client.post(
                f"/restaurant-checks/{denied_check['id']}/payments",
                headers={**headers, 'Idempotency-Key': key},
                params={'location_id': scope.location_id},
                json=_payment_payload(
                    denied_check,
                    amount='40',
                    tendered='50',
                    cash_session_id=cash_session_id,
                ),
            )
            assert denied.status_code == 404, denied.text
            assert denied.json()['error']['code'] == 'CASH_SESSION_NOT_FOUND'
        assert _financial_counts(connection, denied_check['id']) == (0, 0, 0)


def test_staff_recovery_authorizes_payment_location_before_provider_and_state_replay(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    owner_membership_id = _membership_id(connection, scope.email)
    _grant_location(connection, scope.tenant_id, owner_membership_id, scope.location_id)
    other_location = _other_location(connection, scope, 'RECOVERY-MISMATCH')
    _grant_location(
        connection, scope.tenant_id, owner_membership_id, other_location.location_id
    )
    recover_no_grant_email, _ = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-recover-permission-no-grant',
        permissions=('restaurant_payment.recover',),
    )
    no_permission_email, no_permission_membership_id = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-recover-grant-no-permission',
        permissions=(),
    )
    _grant_location(
        connection, scope.tenant_id, no_permission_membership_id, scope.location_id
    )
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(PaymentRecoveryOutcome.CONFIRMED_SUCCESS,),
    )

    with _client(integration_settings, executor) as client:
        check, diner_headers = _new_check(client, connection, scope, 'staff-recovery')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'uncertain-for-recovery'},
            json=_electronic_payload(check, '40', diner_id),
        )
        assert created.status_code == 201, created.text
        assert created.json()['state'] == 'UNCERTAIN'
        payment_id = created.json()['id']
        recovery_url = f'/restaurant-payments/{payment_id}/recover'

        denied_cases = (
            (_staff_headers(client, scope), other_location.location_id, 404),
            (_login(client, recover_no_grant_email), scope.location_id, 404),
            (_login(client, no_permission_email), scope.location_id, 403),
        )
        for headers, location_id, expected_status in denied_cases:
            denied = client.post(
                recovery_url, headers=headers, params={'location_id': location_id}
            )
            assert denied.status_code == expected_status, denied.text
        assert executor.recovery_calls == 0

        owner_headers = _staff_headers(client, scope)
        recovered = client.post(
            recovery_url,
            headers=owner_headers,
            params={'location_id': scope.location_id},
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['state'] == 'SUCCEEDED'
        assert executor.recovery_calls == 1

        wrong_location_replay = client.post(
            recovery_url,
            headers=owner_headers,
            params={'location_id': other_location.location_id},
        )
        assert wrong_location_replay.status_code == 404, wrong_location_replay.text
        compatible_authorized_replay = client.post(recovery_url, headers=owner_headers)
        assert compatible_authorized_replay.status_code == 409
        assert compatible_authorized_replay.json()['error']['code'] == 'PAYMENT_STATE_CONFLICT'
        assert executor.recovery_calls == 1
