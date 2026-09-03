from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from app.main import create_app
from app.restaurant.integrations.payments.contracts import (
    PaymentExecutionOutcome,
    PaymentRecoveryOutcome,
)
from app.restaurant.integrations.payments.credentials import (
    DeterministicMerchantCredentialResolver,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from app.restaurant.integrations.payments.observability import (
    PAYMENT_EXECUTION_DURATION_SECONDS,
    PAYMENT_EXECUTION_TOTAL,
    PAYMENT_RECOVERY_TOTAL,
)
from test_canonical_order_commercial_acceptance import (
    _open_and_join,
    _scope,
    _staff_headers,
)
from test_restaurant_payment_settlement_foundation import (
    _check,
    _electronic_payload,
    _grant,
    _order,
)


CUSTOMER_SENTINEL = 'b4-customer-source-must-never-escape'
MERCHANT_SENTINEL = 'b4-merchant-secret-must-never-escape'


def _log_payload(caplog) -> str:
    return repr([vars(record) for record in caplog.records])


def _log_events(caplog) -> set[str]:
    return {
        record.event for record in caplog.records
        if hasattr(record, 'event')
    }


def _location(connection, scope, name: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO locations (
                tenant_id,organization_id,code,name,timezone,status
            ) VALUES (%s,%s,UUID(),%s,'America/Mexico_City','ACTIVE')
            ''',
            (scope.tenant_id, scope.organization_id, name),
        )
        return int(cursor.lastrowid)


def _organization_location(connection, scope) -> tuple[int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO organizations (tenant_id,code,name,status) "
            "VALUES (%s,UUID(),'Other','ACTIVE')",
            (scope.tenant_id,),
        )
        organization_id = int(cursor.lastrowid)
        cursor.execute(
            '''
            INSERT INTO locations (
                tenant_id,organization_id,code,name,timezone,status
            ) VALUES (%s,%s,UUID(),'Other','America/Mexico_City','ACTIVE')
            ''',
            (scope.tenant_id, organization_id),
        )
        return organization_id, int(cursor.lastrowid)


def _configuration(
    connection,
    scope,
    *,
    key: str,
    adapter_kind: str,
    priority: int,
    status: str = 'ACTIVE',
    method: str = 'CARD',
    currency: str = 'MXN',
    credential_binding: str | None = None,
    organization_id: int | None = None,
    location_id: int | None = None,
) -> int:
    owner_organization_id = organization_id or scope.organization_id
    owner_location_id = location_id or scope.location_id
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO location_payment_executor_configurations (
                tenant_id,organization_id,location_id,executor_key,display_name,
                adapter_kind,topology,status,credential_binding,selection_priority
            ) VALUES (%s,%s,%s,%s,%s,%s,'EXTERNAL',%s,%s,%s)
            ''',
            (
                scope.tenant_id,
                owner_organization_id,
                owner_location_id,
                key,
                f'Display {key}',
                adapter_kind,
                status,
                credential_binding,
                priority,
            ),
        )
        configuration_id = int(cursor.lastrowid)
        cursor.execute(
            '''
            INSERT INTO location_payment_executor_capabilities (
                executor_configuration_id,tenant_id,organization_id,location_id,
                method_category,currency
            ) VALUES (%s,%s,%s,%s,%s,%s)
            ''',
            (
                configuration_id,
                scope.tenant_id,
                owner_organization_id,
                owner_location_id,
                method,
                currency,
            ),
        )
    return configuration_id


def _client(settings, executors, credential_resolver=None) -> TestClient:
    return TestClient(create_app(
        settings=settings,
        payment_executors=executors,
        merchant_credential_resolver=credential_resolver,
    ))


def test_available_executors_are_safe_scoped_runtime_backed_and_ordered(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, f'{prefix}-local')
    foreign = _scope(connection, f'{prefix}-foreign')
    _grant(connection, local.tenant_id, configure_executor=False)
    other_location_id = _location(connection, local, 'Other location')
    other_organization_id, other_organization_location_id = _organization_location(
        connection, local
    )
    first_id = _configuration(
        connection,
        local,
        key='first',
        adapter_kind='AVAILABLE',
        priority=10,
        credential_binding='private-binding-first',
    )
    second_id = _configuration(
        connection,
        local,
        key='second',
        adapter_kind='AVAILABLE',
        priority=10,
    )
    _configuration(
        connection, local, key='inactive', adapter_kind='AVAILABLE',
        priority=0, status='INACTIVE',
    )
    _configuration(
        connection, local, key='wrong-method', adapter_kind='AVAILABLE',
        priority=0, method='TRANSFER',
    )
    _configuration(
        connection, local, key='wrong-currency', adapter_kind='AVAILABLE',
        priority=0, currency='USD',
    )
    _configuration(
        connection, local, key='missing-runtime', adapter_kind='MISSING', priority=0
    )
    _configuration(
        connection, local, key='wrong-location', adapter_kind='AVAILABLE',
        priority=0, location_id=other_location_id,
    )
    _configuration(
        connection,
        local,
        key='wrong-organization',
        adapter_kind='AVAILABLE',
        priority=0,
        organization_id=other_organization_id,
        location_id=other_organization_location_id,
    )
    _configuration(
        connection, foreign, key='foreign', adapter_kind='AVAILABLE', priority=0
    )

    with _client(
        integration_settings, {'AVAILABLE': DeterministicPaymentExecutor()}
    ) as client:
        _, diner_headers = _open_and_join(client, local)
        diner_response = client.get(
            '/diner/payment-executors?method_category=CARD&currency=mxn',
            headers=diner_headers,
        )
        assert diner_response.status_code == 200, diner_response.text
        assert [item['executor_key'] for item in diner_response.json()] == [
            'first', 'second'
        ]
        assert first_id < second_id
        assert all(set(item) == {
            'executor_key', 'display_name', 'topology', 'method_category', 'currency'
        } for item in diner_response.json())
        assert 'private-binding-first' not in diner_response.text
        assert 'AVAILABLE' not in diner_response.text
        assert 'executor_configuration_id' not in diner_response.text

        staff_headers = _staff_headers(client, local)
        staff_response = client.get(
            '/payment-executors',
            headers=staff_headers,
            params={
                'organization_id': local.organization_id,
                'location_id': local.location_id,
                'method_category': 'CARD',
                'currency': 'MXN',
            },
        )
        assert staff_response.status_code == 200
        assert staff_response.json() == diner_response.json()
        foreign_response = client.get(
            '/payment-executors',
            headers=staff_headers,
            params={
                'organization_id': foreign.organization_id,
                'location_id': foreign.location_id,
                'method_category': 'CARD',
                'currency': 'MXN',
            },
        )
        assert foreign_response.status_code == 200
        assert foreign_response.json() == []


def test_public_selection_and_payment_source_contract_is_unambiguous_and_safe(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _configuration(
        connection, scope, key='public', adapter_kind='AVAILABLE', priority=10
    )
    executor = DeterministicPaymentExecutor()

    with _client(integration_settings, {'AVAILABLE': executor}) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b4-public-contract')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        base = _electronic_payload(check, '10', diner_id)
        base.pop('execution_credential')
        base.pop('executor_key')

        explicit = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b4-explicit'},
            json={
                **base,
                'selection_mode': 'EXPLICIT',
                'executor_key': 'public',
                'customer_payment_source': CUSTOMER_SENTINEL,
            },
        )
        assert explicit.status_code == 201, explicit.text
        assert explicit.json()['state'] == 'SUCCEEDED'

        legacy = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b4-legacy'},
            json={
                **base,
                'amount': '11',
                'executor_key': 'public',
                'execution_credential': CUSTOMER_SENTINEL,
            },
        )
        assert legacy.status_code == 201, legacy.text

        auto = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b4-auto'},
            json={
                **base,
                'amount': '12',
                'selection_mode': 'AUTO',
                'customer_payment_source': CUSTOMER_SENTINEL,
            },
        )
        assert auto.status_code == 201, auto.text

        invalid_payloads = (
            {
                **base,
                'selection_mode': 'EXPLICIT',
                'customer_payment_source': CUSTOMER_SENTINEL,
            },
            {
                **base,
                'selection_mode': 'AUTO',
                'executor_key': 'public',
                'customer_payment_source': CUSTOMER_SENTINEL,
            },
            {
                **base,
                'executor_key': 'public',
                'customer_payment_source': CUSTOMER_SENTINEL,
                'execution_credential': 'second-secret-source',
            },
            {
                **base,
                'selection_mode': 'EXPLICIT',
                'executor_key': 'public',
                'customer_payment_source': CUSTOMER_SENTINEL,
                'executor_configuration_id': 123,
            },
        )
        for index, payload in enumerate(invalid_payloads):
            response = client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': f'b4-invalid-{index}'},
                json=payload,
            )
            assert response.status_code == 422, response.text
            assert CUSTOMER_SENTINEL not in response.text
            assert 'second-secret-source' not in response.text

    assert executor.execution_calls == 3
    assert CUSTOMER_SENTINEL not in explicit.text
    assert CUSTOMER_SENTINEL not in legacy.text
    assert CUSTOMER_SENTINEL not in auto.text
    assert CUSTOMER_SENTINEL not in _log_payload(caplog)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT request_fingerprint FROM restaurant_payments WHERE check_id=%s',
            (check['id'],),
        )
        fingerprints = tuple(row['request_fingerprint'] for row in cursor.fetchall())
    assert len(fingerprints) == 3
    assert all(CUSTOMER_SENTINEL not in value for value in fingerprints)


def test_controlled_selection_errors_are_safe_and_create_no_payment(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, f'{prefix}-local')
    foreign = _scope(connection, f'{prefix}-foreign')
    _grant(connection, local.tenant_id, configure_executor=False)
    _configuration(
        connection, foreign, key='foreign', adapter_kind='AVAILABLE', priority=0
    )
    _configuration(
        connection, local, key='inactive', adapter_kind='AVAILABLE',
        priority=0, status='INACTIVE',
    )
    _configuration(
        connection, local, key='transfer-only', adapter_kind='AVAILABLE',
        priority=0, method='TRANSFER',
    )
    _configuration(
        connection, local, key='usd-only', adapter_kind='AVAILABLE',
        priority=0, currency='USD',
    )
    _configuration(
        connection, local, key='unavailable', adapter_kind='MISSING', priority=0
    )
    executor = DeterministicPaymentExecutor()

    with _client(integration_settings, {'AVAILABLE': executor}) as client:
        _, diner_headers = _open_and_join(client, local)
        _order(client, connection, local, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b4-safe-errors')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        base = _electronic_payload(check, '10', diner_id, CUSTOMER_SENTINEL)
        for index, key in enumerate((
            'unknown', 'foreign', 'inactive', 'transfer-only', 'usd-only', 'unavailable'
        )):
            response = client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': f'b4-error-{index}'},
                json={
                    **base,
                    'selection_mode': 'EXPLICIT',
                    'executor_key': key,
                },
            )
            assert response.status_code == 409, response.text
            assert response.json()['error'] == {
                'code': 'PAYMENT_EXECUTOR_UNAVAILABLE',
                'message': 'Payment executor is unavailable',
            }
            assert CUSTOMER_SENTINEL not in response.text
            assert 'credential_binding' not in response.text
            assert 'MISSING' not in response.text

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 0
    assert executor.execution_calls == 0
    assert CUSTOMER_SENTINEL not in _log_payload(caplog)
    assert 'payment_executor_unavailable' in _log_events(caplog)


def test_payment_observability_is_safe_and_metrics_have_only_bounded_labels(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _configuration(
        connection,
        scope,
        key='observed',
        adapter_kind='OBSERVED',
        priority=10,
        credential_binding='observed-binding',
    )
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(
            PaymentExecutionOutcome.SUCCEEDED,
            PaymentExecutionOutcome.DEFINITE_FAILURE,
            PaymentExecutionOutcome.REJECTED,
            PaymentExecutionOutcome.UNCERTAIN,
        ),
        recovery_outcomes=(PaymentRecoveryOutcome.STILL_UNCERTAIN,),
    )
    credential_resolver = DeterministicMerchantCredentialResolver(
        {'observed-binding': MERCHANT_SENTINEL}
    )
    label_values = {
        'method': 'CARD',
        'adapter_kind': 'OBSERVED',
        'topology': 'EXTERNAL',
    }
    before = {
        outcome: PAYMENT_EXECUTION_TOTAL.labels(
            **label_values, outcome=outcome
        )._value.get()
        for outcome in (
            'SUCCEEDED', 'DEFINITE_FAILURE', 'REJECTED', 'UNCERTAIN'
        )
    }
    recovery_before = PAYMENT_RECOVERY_TOTAL.labels(
        **label_values, outcome='STILL_UNCERTAIN'
    )._value.get()

    with _client(
        integration_settings,
        {'OBSERVED': executor},
        credential_resolver,
    ) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b4-observability')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        states = []
        payment_ids = []
        for index in range(4):
            response = client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': f'b4-observed-{index}'},
                json={
                    **_electronic_payload(check, str(10 + index), diner_id),
                    'selection_mode': 'EXPLICIT',
                    'executor_key': 'observed',
                    'execution_credential': None,
                    'customer_payment_source': CUSTOMER_SENTINEL,
                },
            )
            assert response.status_code == 201, response.text
            assert CUSTOMER_SENTINEL not in response.text
            assert MERCHANT_SENTINEL not in response.text
            states.append(response.json()['state'])
            payment_ids.append(response.json()['id'])
        assert states == ['SUCCEEDED', 'FAILED', 'REJECTED', 'UNCERTAIN']

        recovered = client.post(
            f'/restaurant-payments/{payment_ids[-1]}/recover',
            headers=_staff_headers(client, scope),
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['state'] == 'UNCERTAIN'

    assert PAYMENT_EXECUTION_TOTAL._labelnames == (
        'method', 'outcome', 'adapter_kind', 'topology'
    )
    assert PAYMENT_EXECUTION_DURATION_SECONDS._labelnames == (
        'method', 'outcome', 'adapter_kind', 'topology'
    )
    assert PAYMENT_RECOVERY_TOTAL._labelnames == (
        'method', 'outcome', 'adapter_kind', 'topology'
    )
    for outcome, previous in before.items():
        assert PAYMENT_EXECUTION_TOTAL.labels(
            **label_values, outcome=outcome
        )._value.get() == previous + 1
    assert PAYMENT_RECOVERY_TOTAL.labels(
        **label_values, outcome='STILL_UNCERTAIN'
    )._value.get() == recovery_before + 1
    assert {
        'payment_executor_selected',
        'payment_execution_started',
        'payment_execution_completed',
        'payment_execution_uncertain',
        'payment_recovery_started',
        'payment_recovery_completed',
        'payment_recovery_uncertain',
    }.issubset(_log_events(caplog))
    assert CUSTOMER_SENTINEL not in _log_payload(caplog)
    assert MERCHANT_SENTINEL not in _log_payload(caplog)
    metrics = generate_latest().decode()
    assert CUSTOMER_SENTINEL not in metrics
    assert MERCHANT_SENTINEL not in metrics

    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT COALESCE(SUM(amount),0) AS amount
            FROM restaurant_check_settlements WHERE check_id=%s
            ''',
            (check['id'],),
        )
        assert Decimal(cursor.fetchone()['amount']) == Decimal('10')
