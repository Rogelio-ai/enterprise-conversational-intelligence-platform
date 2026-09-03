from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
    PaymentExecutionResult,
    PaymentRecoveryOutcome,
)
from app.restaurant.integrations.payments.credentials import (
    DeterministicMerchantCredentialResolver,
    MerchantCredentialContext,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
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


CUSTOMER_SOURCE = 'synthetic-customer-source-never-persist'
MERCHANT_CREDENTIAL = 'synthetic-merchant-credential-never-persist'


def _configuration(
    connection,
    scope,
    *,
    key: str,
    adapter_kind: str,
    credential_binding: str | None,
    priority: int = 100,
    status: str = 'ACTIVE',
    location_id: int | None = None,
) -> int:
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
                scope.organization_id,
                owner_location_id,
                key,
                f'Executor {key}',
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
            ) VALUES (%s,%s,%s,%s,'CARD','MXN')
            ''',
            (
                configuration_id,
                scope.tenant_id,
                scope.organization_id,
                owner_location_id,
            ),
        )
    return configuration_id


class CommitInspectingCredentialResolver(DeterministicMerchantCredentialResolver):
    def __init__(self, connection, credentials: dict[str, str]) -> None:
        super().__init__(credentials)
        self._connection = connection
        self.durable_before_resolution: list[bool] = []

    async def resolve(
        self, *, context: MerchantCredentialContext
    ) -> EphemeralMerchantCredential:
        with self._connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT state,executor_configuration_id
                FROM restaurant_payments WHERE id=%s
                ''',
                (int(context.operation_reference),),
            )
            payment = cursor.fetchone()
        self.durable_before_resolution.append(
            payment is not None
            and payment['state'] == 'IN_PROGRESS'
            and payment['executor_configuration_id'] == context.executor_configuration_id
        )
        return await super().resolve(context=context)


class CommitInspectingExecutor(DeterministicPaymentExecutor):
    def __init__(self, connection, **kwargs) -> None:
        super().__init__(**kwargs)
        self._connection = connection
        self.durable_before_execution: list[bool] = []
        self.customer_source_matches: list[bool] = []
        self.merchant_credential_matches: list[bool] = []

    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult:
        with self._connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT state,executor_configuration_id
                FROM restaurant_payments WHERE id=%s
                ''',
                (int(request.operation_reference),),
            )
            payment = cursor.fetchone()
        self.durable_before_execution.append(
            payment is not None
            and payment['state'] == 'IN_PROGRESS'
            and payment['executor_configuration_id'] is not None
        )
        self.customer_source_matches.append(
            customer_payment_source is not None
            and customer_payment_source.value.get_secret_value() == CUSTOMER_SOURCE
        )
        self.merchant_credential_matches.append(
            merchant_credential is not None
            and merchant_credential.value.get_secret_value() == MERCHANT_CREDENTIAL
        )
        return await super().execute(
            request=request,
            merchant_credential=merchant_credential,
            customer_payment_source=customer_payment_source,
        )


def _client(settings, executors, credential_resolver=None) -> TestClient:
    return TestClient(create_app(
        settings=settings,
        payment_executors=executors,
        merchant_credential_resolver=credential_resolver,
    ))


def _rows(connection, table: str, payment_id: int) -> tuple[dict, ...]:
    column = 'id' if table == 'restaurant_payments' else 'payment_id'
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM {table} WHERE {column}=%s', (payment_id,))
        return tuple(cursor.fetchall())


def test_explicit_selection_is_durable_before_ephemeral_inputs_and_leaves_safe_evidence(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    configuration_id = _configuration(
        connection,
        scope,
        key='primary',
        adapter_kind='ADAPTER_A',
        credential_binding='binding-A',
    )
    executor = CommitInspectingExecutor(connection)
    credential_resolver = CommitInspectingCredentialResolver(
        connection, {'binding-A': MERCHANT_CREDENTIAL}
    )

    with _client(
        integration_settings,
        {'ADAPTER_A': executor},
        credential_resolver,
    ) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b3-explicit-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payload = {
            **_electronic_payload(check, '40', diner_id, CUSTOMER_SOURCE),
            'executor_key': 'primary',
        }
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b3-explicit'},
            json=payload,
        )
        assert created.status_code == 201, created.text
        payment_id = created.json()['id']
        assert created.json()['state'] == 'SUCCEEDED'

        replay = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b3-explicit'},
            json={**payload, 'execution_credential': 'different-ephemeral-source'},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()['id'] == payment_id

    payment_rows = _rows(connection, 'restaurant_payments', payment_id)
    attempt_rows = _rows(connection, 'restaurant_payment_attempts', payment_id)
    settlement_rows = _rows(connection, 'restaurant_check_settlements', payment_id)
    assert payment_rows[0]['executor_configuration_id'] == configuration_id
    assert payment_rows[0]['executor_key'] == 'primary'
    assert len(attempt_rows) == 1
    assert len(settlement_rows) == 1
    assert executor.execution_calls == 1
    assert executor.durable_before_execution == [True]
    assert executor.customer_source_matches == [True]
    assert executor.merchant_credential_matches == [True]
    assert credential_resolver.durable_before_resolution == [True]
    assert [call.executor_configuration_id for call in credential_resolver.calls] == [
        configuration_id
    ]
    durable_text = repr((payment_rows, attempt_rows, settlement_rows))
    assert CUSTOMER_SOURCE not in durable_text
    assert MERCHANT_CREDENTIAL not in durable_text
    assert CUSTOMER_SOURCE not in caplog.text
    assert MERCHANT_CREDENTIAL not in caplog.text
    assert MERCHANT_CREDENTIAL not in repr(credential_resolver)


def test_auto_selects_once_and_inactive_original_controls_recovery(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    original_id = _configuration(
        connection,
        scope,
        key='original-auto',
        adapter_kind='ADAPTER_A',
        credential_binding='binding-A',
        priority=10,
    )
    replacement_id = _configuration(
        connection,
        scope,
        key='replacement-auto',
        adapter_kind='ADAPTER_B',
        credential_binding='binding-B',
        priority=20,
    )
    original = CommitInspectingExecutor(
        connection,
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
    )
    replacement = CommitInspectingExecutor(connection)
    credential_resolver = CommitInspectingCredentialResolver(
        connection,
        {
            'binding-A': MERCHANT_CREDENTIAL,
            'binding-B': MERCHANT_CREDENTIAL,
        },
    )

    with _client(
        integration_settings,
        {'ADAPTER_A': original, 'ADAPTER_B': replacement},
        credential_resolver,
    ) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b3-auto-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        auto_payload = _electronic_payload(check, '40', diner_id, CUSTOMER_SOURCE)
        auto_payload.pop('executor_key')
        first = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b3-auto'},
            json=auto_payload,
        )
        assert first.status_code == 201, first.text
        assert first.json()['state'] == 'UNCERTAIN'
        payment_id = first.json()['id']

        with connection.cursor() as cursor:
            cursor.execute(
                '''
                UPDATE location_payment_executor_configurations
                SET status='INACTIVE',selection_priority=999 WHERE id=%s
                ''',
                (original_id,),
            )
            cursor.execute(
                '''
                UPDATE location_payment_executor_configurations
                SET selection_priority=0 WHERE id=%s
                ''',
                (replacement_id,),
            )

        replay = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b3-auto'},
            json={**auto_payload, 'execution_credential': 'changed-source'},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()['id'] == payment_id
        assert original.execution_calls == 1

        replacement_payment = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b3-auto-replacement'},
            json={**auto_payload, 'amount': '10'},
        )
        assert replacement_payment.status_code == 201, replacement_payment.text
        assert replacement_payment.json()['state'] == 'SUCCEEDED'
        assert replacement.execution_calls == 1

        before_recovery = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=_staff_headers(client, scope),
        ).json()
        assert Decimal(before_recovery['uncertain_exposure']) == Decimal('40')
        assert Decimal(before_recovery['confirmed_settlement']) == Decimal('10')

        recovered = client.post(
            f'/restaurant-payments/{payment_id}/recover',
            headers=_staff_headers(client, scope),
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['state'] == 'SUCCEEDED'

    payment = _rows(connection, 'restaurant_payments', payment_id)[0]
    assert payment['executor_configuration_id'] == original_id
    assert original.recovery_calls == 1
    assert replacement.recovery_calls == 0
    assert original.recovery_received_merchant_credential is True
    assert original.last_recovery_external_reference == payment['external_reference']
    assert [call.credential_binding for call in credential_resolver.calls] == [
        'binding-A',
        'binding-B',
        'binding-A',
    ]
    assert [call.executor_configuration_id for call in credential_resolver.calls] == [
        original_id,
        replacement_id,
        original_id,
    ]
    assert len(_rows(connection, 'restaurant_check_settlements', payment_id)) == 1


def test_retry_rejects_inactive_original_without_rebinding_or_external_call(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    original_id = _configuration(
        connection,
        scope,
        key='retry-original',
        adapter_kind='ADAPTER_A',
        credential_binding='binding-A',
        priority=10,
    )
    replacement_id = _configuration(
        connection,
        scope,
        key='retry-replacement',
        adapter_kind='ADAPTER_B',
        credential_binding='binding-B',
        priority=20,
    )
    original = CommitInspectingExecutor(
        connection,
        execution_outcomes=(
            PaymentExecutionOutcome.UNCERTAIN,
            PaymentExecutionOutcome.SUCCEEDED,
        ),
        recovery_outcomes=(PaymentRecoveryOutcome.DEFINITE_ABSENCE,),
    )
    replacement = CommitInspectingExecutor(connection)
    credential_resolver = CommitInspectingCredentialResolver(
        connection,
        {
            'binding-A': MERCHANT_CREDENTIAL,
            'binding-B': MERCHANT_CREDENTIAL,
        },
    )

    with _client(
        integration_settings,
        {'ADAPTER_A': original, 'ADAPTER_B': replacement},
        credential_resolver,
    ) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b3-retry-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payload = _electronic_payload(check, '40', diner_id, CUSTOMER_SOURCE)
        payload.pop('executor_key')
        first = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b3-retry'},
            json=payload,
        )
        assert first.status_code == 201, first.text
        assert first.json()['state'] == 'UNCERTAIN'

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE location_payment_executor_configurations SET status='INACTIVE' "
                'WHERE id=%s',
                (original_id,),
            )
            cursor.execute(
                'UPDATE location_payment_executor_configurations SET selection_priority=0 '
                'WHERE id=%s',
                (replacement_id,),
            )

        absent = client.post(
            f"/restaurant-payments/{first.json()['id']}/recover",
            headers=_staff_headers(client, scope),
        )
        assert absent.status_code == 200, absent.text
        assert absent.json()['state'] == 'FAILED'

        retried = client.post(
            f"/restaurant-payments/{first.json()['id']}/retry",
            headers=_staff_headers(client, scope),
            json={'execution_credential': CUSTOMER_SOURCE},
        )
        assert retried.status_code == 200, retried.text
        assert retried.json()['state'] == 'FAILED'
        assert retried.json()['executor_key'] == 'retry-original'
        assert retried.json()['attempts'][-1]['error_code'] == (
            'PAYMENT_EXECUTOR_CONFIGURATION_INACTIVE'
        )

    payment = _rows(connection, 'restaurant_payments', first.json()['id'])[0]
    assert payment['executor_configuration_id'] == original_id
    assert original.execution_calls == 1
    assert original.recovery_calls == 1
    assert replacement.execution_calls == 0
    assert [call.executor_configuration_id for call in credential_resolver.calls] == [
        original_id,
        original_id,
    ]
    assert len(_rows(connection, 'restaurant_check_settlements', first.json()['id'])) == 0


@pytest.mark.parametrize('selection', ['foreign', 'auto', 'missing-runtime'])
def test_invalid_selection_creates_no_payment_or_provider_call(
    integration_settings, sql_connection, selection,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, f'{prefix}-local')
    foreign = _scope(connection, f'{prefix}-foreign')
    _grant(connection, local.tenant_id, configure_executor=False)
    _configuration(
        connection,
        foreign,
        key='foreign-only',
        adapter_kind='AVAILABLE',
        credential_binding='foreign-binding',
    )
    if selection == 'missing-runtime':
        _configuration(
            connection,
            local,
            key='missing-runtime',
            adapter_kind='MISSING',
            credential_binding=None,
        )
    executor = DeterministicPaymentExecutor()
    credential_resolver = DeterministicMerchantCredentialResolver(
        {'foreign-binding': MERCHANT_CREDENTIAL}
    )

    with _client(
        integration_settings,
        {'AVAILABLE': executor},
        credential_resolver,
    ) as client:
        _, diner_headers = _open_and_join(client, local)
        _order(client, connection, local, diner_headers, amount='100')
        check = _check(client, diner_headers, f'b3-invalid-{selection}')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payload = _electronic_payload(check, '40', diner_id, CUSTOMER_SOURCE)
        if selection == 'foreign':
            payload['executor_key'] = 'foreign-only'
        elif selection == 'auto':
            payload.pop('executor_key')
        else:
            payload['executor_key'] = 'missing-runtime'
        response = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': f'b3-invalid-{selection}'},
            json=payload,
        )
        assert response.status_code == 409, response.text

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 0
    assert executor.execution_calls == 0
    assert credential_resolver.calls == []


class ExplodingCredentialResolver:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, *, context: MerchantCredentialContext):
        del context
        self.calls += 1
        raise AssertionError('Cash must not resolve merchant credentials')


def test_cash_needs_no_configuration_registry_credential_or_customer_source(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    credential_resolver = ExplodingCredentialResolver()

    with _client(integration_settings, {}, credential_resolver) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'b3-cash-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        paid = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**_staff_headers(client, scope), 'Idempotency-Key': 'b3-cash'},
            json={
                'expected_check_version': check['version'],
                'expected_check_fingerprint': check['fingerprint'],
                'amount': '100',
                'currency': 'MXN',
                'method_category': 'CASH',
                'payer_type': 'DINER',
                'payer_diner_session_id': diner_id,
                'cash_tendered_amount': '100',
            },
        )
        assert paid.status_code == 201, paid.text
        assert paid.json()['state'] == 'SUCCEEDED'

    payment = _rows(connection, 'restaurant_payments', paid.json()['id'])[0]
    assert payment['executor_configuration_id'] is None
    assert payment['executor_key'] is None
    assert credential_resolver.calls == 0
