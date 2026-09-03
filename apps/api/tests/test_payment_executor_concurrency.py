from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event, Lock

import pymysql
from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
    PaymentExecutionResult,
    PaymentRecoveryOutcome,
    PaymentRecoveryRequest,
    PaymentRecoveryResult,
)
from app.restaurant.integrations.payments.credentials import (
    DeterministicMerchantCredentialResolver,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from app.restaurant.integrations.payments.registry import PaymentExecutorRegistry
from app.restaurant.payments import errors
from test_canonical_order_commercial_acceptance import (
    _open_and_join,
    _scope,
    _staff_headers,
)
from test_payment_executor_api import _configuration
from test_restaurant_payment_settlement_foundation import (
    _check,
    _electronic_payload,
    _grant,
    _order,
)


CUSTOMER_SECRET = 'b5-concurrent-customer-source-never-escape'
MERCHANT_SECRET = 'b5-concurrent-merchant-secret-never-escape'


class BlockingExecutionExecutor(DeterministicPaymentExecutor):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.execution_entered = Event()
        self.execution_release = Event()

    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult:
        self.execution_entered.set()
        if not self.execution_release.wait(15):
            raise AssertionError('Timed out waiting to release payment execution')
        return await super().execute(
            request=request,
            merchant_credential=merchant_credential,
            customer_payment_source=customer_payment_source,
        )


class BlockingRecoveryExecutor(DeterministicPaymentExecutor):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.recovery_entered = Event()
        self.recovery_release = Event()

    async def recover(
        self,
        *,
        request: PaymentRecoveryRequest,
        merchant_credential: EphemeralMerchantCredential | None = None,
    ) -> PaymentRecoveryResult:
        self.recovery_entered.set()
        if not self.recovery_release.wait(15):
            raise AssertionError('Timed out waiting to release payment recovery')
        return await super().recover(
            request=request,
            merchant_credential=merchant_credential,
        )


class PossibleEffectFailureExecutor(DeterministicPaymentExecutor):
    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult:
        del request, merchant_credential, customer_payment_source
        self.execution_calls += 1
        raise TimeoutError('synthetic timeout after possible provider effect')


class DuplicateReferenceExecutor(DeterministicPaymentExecutor):
    def __init__(self, external_reference: str) -> None:
        super().__init__()
        self._external_reference = external_reference
        self._barrier = Barrier(2)
        self._count_lock = Lock()

    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult:
        del request, merchant_credential, customer_payment_source
        with self._count_lock:
            self.execution_calls += 1
        self._barrier.wait(timeout=15)
        return PaymentExecutionResult(
            outcome=PaymentExecutionOutcome.SUCCEEDED,
            external_reference=self._external_reference,
            external_status='SUCCEEDED',
        )


class VanishingPaymentExecutorRegistry(PaymentExecutorRegistry):
    """Makes the selected runtime disappear before execution revalidation."""

    def __init__(self, executors) -> None:
        super().__init__(executors)
        self.resolve_calls = 0

    def resolve(self, adapter_kind: str) -> object:
        self.resolve_calls += 1
        if self.resolve_calls > 1:
            raise errors.PaymentExecutorAdapterNotRegisteredError(
                'Synthetic runtime disappearance'
            )
        return super().resolve(adapter_kind)


class DisablingPaymentExecutorRegistry(PaymentExecutorRegistry):
    """Disables the binding after selection but before execution revalidation."""

    def __init__(self, connection, configuration_id: int, executors) -> None:
        super().__init__(executors)
        self._connection = connection
        self._configuration_id = configuration_id
        self.resolve_calls = 0

    def resolve(self, adapter_kind: str) -> object:
        executor = super().resolve(adapter_kind)
        self.resolve_calls += 1
        if self.resolve_calls == 1:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE location_payment_executor_configurations "
                    "SET status='INACTIVE' WHERE id=%s",
                    (self._configuration_id,),
                )
        return executor


def _payment_rows(connection, check_id: int) -> tuple[dict, ...]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT * FROM restaurant_payments WHERE check_id=%s ORDER BY id',
            (check_id,),
        )
        return tuple(cursor.fetchall())


def _settlement_count(connection, check_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements WHERE check_id=%s',
            (check_id,),
        )
        return int(cursor.fetchone()['count'])


def _new_check(client, connection, scope, label: str, amount: str = '100'):
    _, diner_headers = _open_and_join(client, scope)
    _order(client, connection, scope, diner_headers, amount=amount)
    check = _check(client, diner_headers, label)
    diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
    return diner_headers, check, diner_id


def test_concurrent_liability_reservation_never_exceeds_available(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _configuration(connection, scope, key='race', adapter_kind='RACE', priority=10)
    executor = DeterministicPaymentExecutor()

    with TestClient(create_app(
        settings=integration_settings, payment_executors={'RACE': executor}
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-liability-race'
        )
        staff_headers = _staff_headers(client, scope)

        def pay(key: str):
            return client.post(
                f"/restaurant-checks/{check['id']}/payments",
                headers={**staff_headers, 'Idempotency-Key': key},
                json={
                    **_electronic_payload(check, '70', diner_id, CUSTOMER_SECRET),
                    'selection_mode': 'EXPLICIT',
                    'executor_key': 'race',
                    'payer_type': 'OTHER',
                    'payer_diner_session_id': None,
                    'payer_reference': key,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = tuple(
                future.result() for future in (
                    pool.submit(pay, 'b5-liability-a'),
                    pool.submit(pay, 'b5-liability-b'),
                )
            )

    assert sorted(response.status_code for response in responses) == [201, 409]
    rows = _payment_rows(connection, check['id'])
    assert len(rows) == 1
    assert Decimal(rows[0]['amount']) == Decimal('70')
    assert _settlement_count(connection, check['id']) == 1
    assert executor.execution_calls == 1


def test_concurrent_auto_idempotency_binds_once_across_disable_and_priority_change(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    original_id = _configuration(
        connection, scope, key='original', adapter_kind='BLOCK', priority=10
    )
    replacement_id = _configuration(
        connection, scope, key='replacement', adapter_kind='BLOCK', priority=20
    )
    executor = BlockingExecutionExecutor()

    with (
        TestClient(create_app(
            settings=integration_settings, payment_executors={'BLOCK': executor}
        )) as client,
        TestClient(create_app(
            settings=integration_settings, payment_executors={'BLOCK': executor}
        )) as concurrent_client,
    ):
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-auto-idempotency'
        )
        payload = _electronic_payload(check, '60', diner_id, CUSTOMER_SECRET)
        payload.pop('executor_key')
        payload['selection_mode'] = 'AUTO'

        def pay(request_client=client):
            return request_client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': 'b5-auto-same'},
                json=payload,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(pay)
            assert executor.execution_entered.wait(10)
            second_future = pool.submit(pay, concurrent_client)
            second = second_future.result(timeout=10)
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE location_payment_executor_configurations "
                    "SET status='INACTIVE' WHERE id=%s",
                    (original_id,),
                )
                cursor.execute(
                    'UPDATE location_payment_executor_configurations '
                    'SET selection_priority=0 WHERE id=%s',
                    (replacement_id,),
                )
            executor.execution_release.set()
            first = first_future.result(timeout=10)

        replay = pay()

    assert sorted((first.status_code, second.status_code)) == [200, 201]
    assert replay.status_code == 200
    assert first.json()['id'] == second.json()['id'] == replay.json()['id']
    rows = _payment_rows(connection, check['id'])
    assert len(rows) == 1
    assert rows[0]['executor_configuration_id'] == original_id
    assert rows[0]['executor_configuration_id'] != replacement_id
    assert rows[0]['state'] == 'SUCCEEDED'
    assert executor.execution_calls == 1
    assert _settlement_count(connection, check['id']) == 1


def test_discovery_is_staleable_and_runtime_loss_never_substitutes_executor(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    disabled_id = _configuration(
        connection, scope, key='disable-me', adapter_kind='DISABLE', priority=10
    )
    _configuration(
        connection, scope, key='runtime-loss', adapter_kind='RUNTIME', priority=20
    )
    disabled_executor = DeterministicPaymentExecutor()
    runtime_executor = DeterministicPaymentExecutor()
    registry = PaymentExecutorRegistry({
        'DISABLE': disabled_executor,
        'RUNTIME': runtime_executor,
    })

    with TestClient(create_app(
        settings=integration_settings, payment_executor_registry=registry
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-stale-discovery'
        )
        discovered = client.get(
            '/diner/payment-executors?method_category=CARD&currency=MXN',
            headers=diner_headers,
        )
        assert discovered.status_code == 200
        assert [item['executor_key'] for item in discovered.json()] == [
            'disable-me', 'runtime-loss'
        ]

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE location_payment_executor_configurations "
                "SET status='INACTIVE' WHERE id=%s",
                (disabled_id,),
            )
        registry._executors.pop('RUNTIME')

        responses = []
        for index, key in enumerate(('disable-me', 'runtime-loss')):
            responses.append(client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={
                    **diner_headers,
                    'Idempotency-Key': f'b5-stale-discovery-{index}',
                },
                json={
                    **_electronic_payload(check, '20', diner_id, CUSTOMER_SECRET),
                    'selection_mode': 'EXPLICIT',
                    'executor_key': key,
                },
            ))

    assert [response.status_code for response in responses] == [409, 409]
    assert all(response.json()['error'] == {
        'code': 'PAYMENT_EXECUTOR_UNAVAILABLE',
        'message': 'Payment executor is unavailable',
    } for response in responses)
    assert _payment_rows(connection, check['id']) == ()
    assert disabled_executor.execution_calls == 0
    assert runtime_executor.execution_calls == 0


def test_runtime_loss_after_selection_preserves_binding_without_fallback(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    selected_id = _configuration(
        connection, scope, key='selected', adapter_kind='VANISH', priority=10
    )
    fallback_id = _configuration(
        connection, scope, key='fallback', adapter_kind='FALLBACK', priority=20
    )
    selected_executor = DeterministicPaymentExecutor()
    fallback_executor = DeterministicPaymentExecutor()
    registry = VanishingPaymentExecutorRegistry({
        'VANISH': selected_executor,
        'FALLBACK': fallback_executor,
    })

    with TestClient(create_app(
        settings=integration_settings, payment_executor_registry=registry
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-runtime-after-selection'
        )
        response = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b5-runtime-vanished'},
            json={
                **_electronic_payload(check, '30', diner_id, CUSTOMER_SECRET),
                'selection_mode': 'EXPLICIT',
                'executor_key': 'selected',
            },
        )

    assert response.status_code == 201
    assert response.json()['state'] == 'FAILED'
    payment = _payment_rows(connection, check['id'])[0]
    assert payment['executor_configuration_id'] == selected_id
    assert payment['executor_configuration_id'] != fallback_id
    assert payment['last_error_code'] == 'PAYMENT_EXECUTOR_ADAPTER_NOT_REGISTERED'
    assert selected_executor.execution_calls == 0
    assert fallback_executor.execution_calls == 0
    assert _settlement_count(connection, check['id']) == 0


def test_configuration_disabled_after_reservation_prevents_first_external_call(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    selected_id = _configuration(
        connection, scope, key='selected', adapter_kind='SELECTED', priority=10
    )
    replacement_id = _configuration(
        connection, scope, key='replacement', adapter_kind='REPLACEMENT', priority=20
    )
    selected_executor = DeterministicPaymentExecutor()
    replacement_executor = DeterministicPaymentExecutor()
    registry = DisablingPaymentExecutorRegistry(
        connection,
        selected_id,
        {
            'SELECTED': selected_executor,
            'REPLACEMENT': replacement_executor,
        },
    )

    with TestClient(create_app(
        settings=integration_settings, payment_executor_registry=registry
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b7r-disabled-after-reservation'
        )
        payload = _electronic_payload(check, '30', diner_id, CUSTOMER_SECRET)
        payload.pop('executor_key')
        payload['selection_mode'] = 'AUTO'
        response = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b7r-disabled-binding'},
            json=payload,
        )

    assert response.status_code == 201, response.text
    assert response.json()['state'] == 'FAILED'
    rows = _payment_rows(connection, check['id'])
    assert len(rows) == 1
    assert rows[0]['executor_configuration_id'] == selected_id
    assert rows[0]['executor_configuration_id'] != replacement_id
    assert rows[0]['last_error_code'] == 'PAYMENT_EXECUTOR_CONFIGURATION_INACTIVE'
    assert selected_executor.execution_calls == 0
    assert replacement_executor.execution_calls == 0
    assert registry.resolve_calls == 1
    assert _settlement_count(connection, check['id']) == 0


def test_concurrent_retry_has_one_execution_claim_and_one_financial_effect(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _configuration(
        connection,
        scope,
        key='claim',
        adapter_kind='CLAIM',
        priority=10,
        credential_binding='claim-binding',
    )
    executor = BlockingExecutionExecutor()
    credential_resolver = DeterministicMerchantCredentialResolver({})

    with (
        TestClient(create_app(
            settings=integration_settings,
            payment_executors={'CLAIM': executor},
            merchant_credential_resolver=credential_resolver,
        )) as client,
        TestClient(create_app(
            settings=integration_settings,
            payment_executors={'CLAIM': executor},
            merchant_credential_resolver=credential_resolver,
        )) as concurrent_client,
    ):
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-execution-claim'
        )
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b5-claim-initial'},
            json={
                **_electronic_payload(check, '50', diner_id, CUSTOMER_SECRET),
                'selection_mode': 'EXPLICIT',
                'executor_key': 'claim',
            },
        )
        assert created.status_code == 201
        assert created.json()['state'] == 'FAILED'
        credential_resolver._credentials['claim-binding'] = MERCHANT_SECRET
        staff_headers = _staff_headers(client, scope)

        def retry(request_client=client):
            return request_client.post(
                f"/restaurant-payments/{created.json()['id']}/retry",
                headers=staff_headers,
                json={'customer_payment_source': CUSTOMER_SECRET},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            winner_future = pool.submit(retry)
            assert executor.execution_entered.wait(10)
            loser_future = pool.submit(retry, concurrent_client)
            loser = loser_future.result(timeout=10)
            executor.execution_release.set()
            winner = winner_future.result(timeout=10)

    assert winner.status_code == 200
    assert winner.json()['state'] == 'SUCCEEDED'
    assert loser.status_code == 409
    assert executor.execution_calls == 1
    assert _settlement_count(connection, check['id']) == 1
    rows = _payment_rows(connection, check['id'])
    assert len(rows) == 1 and rows[0]['attempt_count'] == 2


def test_expired_original_claim_is_fenced_by_recovery_winner(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    configuration_id = _configuration(
        connection, scope, key='fenced', adapter_kind='FENCED', priority=10
    )
    executor = BlockingExecutionExecutor(
        recovery_outcomes=(PaymentRecoveryOutcome.CONFIRMED_SUCCESS,)
    )

    with (
        TestClient(create_app(
            settings=integration_settings, payment_executors={'FENCED': executor}
        )) as client,
        TestClient(create_app(
            settings=integration_settings, payment_executors={'FENCED': executor}
        )) as recovery_client,
    ):
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-stale-fencing'
        )
        staff_headers = _staff_headers(client, scope)

        def initiate():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': 'b5-fenced'},
                json={
                    **_electronic_payload(check, '100', diner_id, CUSTOMER_SECRET),
                    'selection_mode': 'EXPLICIT',
                    'executor_key': 'fenced',
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            stale_future = pool.submit(initiate)
            assert executor.execution_entered.wait(10)
            payment = _payment_rows(connection, check['id'])[0]
            assert payment['state'] == 'IN_PROGRESS'
            assert payment['executor_configuration_id'] == configuration_id
            stale_token = payment['claim_token']
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE restaurant_payments '
                    'SET claim_expires_at=DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE) '
                    'WHERE id=%s',
                    (payment['id'],),
                )
            recovered = recovery_client.post(
                f"/restaurant-payments/{payment['id']}/recover",
                headers=staff_headers,
            )
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()['state'] == 'SUCCEEDED'
            executor.execution_release.set()
            stale = stale_future.result(timeout=10)

    assert stale.status_code == 201
    assert stale.json()['state'] == 'SUCCEEDED'
    assert _settlement_count(connection, check['id']) == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT attempt_type,result,claim_token FROM restaurant_payment_attempts '
            'WHERE payment_id=%s ORDER BY attempt_sequence',
            (payment['id'],),
        )
        attempts = tuple(cursor.fetchall())
    assert attempts[0]['result'] == 'FENCED'
    assert attempts[0]['claim_token'] == stale_token
    assert attempts[1]['attempt_type'] == 'STALE_RECOVERY'
    assert attempts[1]['result'] == 'SUCCEEDED'
    assert executor.execution_calls == 1
    assert executor.recovery_calls == 1


def test_concurrent_recovery_stays_uncertain_and_preserves_historical_executor(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    original_id = _configuration(
        connection, scope, key='uncertain-original', adapter_kind='RECOVER', priority=10
    )
    replacement_id = _configuration(
        connection, scope, key='uncertain-replacement', adapter_kind='RECOVER', priority=20
    )
    executor = BlockingRecoveryExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(
            PaymentRecoveryOutcome.STILL_UNCERTAIN,
            PaymentRecoveryOutcome.STILL_UNCERTAIN,
        ),
    )

    with (
        TestClient(create_app(
            settings=integration_settings, payment_executors={'RECOVER': executor}
        )) as client,
        TestClient(create_app(
            settings=integration_settings, payment_executors={'RECOVER': executor}
        )) as concurrent_client,
    ):
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-recovery-race'
        )
        payload = _electronic_payload(check, '40', diner_id, CUSTOMER_SECRET)
        payload.pop('executor_key')
        payload['selection_mode'] = 'AUTO'
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b5-uncertain'},
            json=payload,
        )
        assert created.status_code == 201
        assert created.json()['state'] == 'UNCERTAIN'
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE location_payment_executor_configurations "
                "SET status='INACTIVE' WHERE id=%s",
                (original_id,),
            )
            cursor.execute(
                'UPDATE location_payment_executor_configurations '
                'SET selection_priority=0 WHERE id=%s',
                (replacement_id,),
            )
        staff_headers = _staff_headers(client, scope)

        def recover(request_client=client):
            return request_client.post(
                f"/restaurant-payments/{created.json()['id']}/recover",
                headers=staff_headers,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            winner_future = pool.submit(recover)
            assert executor.recovery_entered.wait(10)
            loser_future = pool.submit(recover, concurrent_client)
            loser = loser_future.result(timeout=10)
            executor.recovery_release.set()
            winner = winner_future.result(timeout=10)
        repeated = recover()
        projection = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=staff_headers,
        )

    assert winner.status_code == 200
    assert winner.json()['state'] == 'UNCERTAIN'
    assert loser.status_code == 409
    assert repeated.status_code == 200
    assert repeated.json()['state'] == 'UNCERTAIN'
    payment = _payment_rows(connection, check['id'])[0]
    assert payment['executor_configuration_id'] == original_id
    assert payment['executor_configuration_id'] != replacement_id
    assert payment['state'] == 'UNCERTAIN'
    assert _settlement_count(connection, check['id']) == 0
    assert Decimal(projection.json()['uncertain_exposure']) == Decimal('40')
    assert executor.execution_calls == 1
    assert executor.recovery_calls == 2


def test_definite_absence_retry_revalidates_original_configuration_without_fallback(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    original_id = _configuration(
        connection, scope, key='absence-original', adapter_kind='ABSENCE', priority=10
    )
    replacement_id = _configuration(
        connection, scope, key='absence-replacement', adapter_kind='ABSENCE', priority=20
    )
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(
            PaymentExecutionOutcome.UNCERTAIN,
            PaymentExecutionOutcome.SUCCEEDED,
        ),
        recovery_outcomes=(PaymentRecoveryOutcome.DEFINITE_ABSENCE,),
    )

    with TestClient(create_app(
        settings=integration_settings, payment_executors={'ABSENCE': executor}
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-definite-absence'
        )
        payload = _electronic_payload(check, '40', diner_id, CUSTOMER_SECRET)
        payload.pop('executor_key')
        payload['selection_mode'] = 'AUTO'
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b5-absence'},
            json=payload,
        )
        assert created.status_code == 201
        assert created.json()['state'] == 'UNCERTAIN'
        original_provider_idempotency_key = _payment_rows(
            connection, check['id']
        )[0]['provider_idempotency_key']
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE location_payment_executor_configurations "
                "SET status='INACTIVE' WHERE id=%s",
                (original_id,),
            )
            cursor.execute(
                'UPDATE location_payment_executor_configurations '
                'SET selection_priority=0 WHERE id=%s',
                (replacement_id,),
            )
        staff_headers = _staff_headers(client, scope)
        absent = client.post(
            f"/restaurant-payments/{created.json()['id']}/recover",
            headers=staff_headers,
        )
        retried = client.post(
            f"/restaurant-payments/{created.json()['id']}/retry",
            headers=staff_headers,
            json={'customer_payment_source': CUSTOMER_SECRET},
        )

    assert absent.status_code == 200 and absent.json()['state'] == 'FAILED'
    assert retried.status_code == 200 and retried.json()['state'] == 'FAILED'
    assert retried.json()['attempts'][-1]['error_code'] == (
        'PAYMENT_EXECUTOR_CONFIGURATION_INACTIVE'
    )
    payment = _payment_rows(connection, check['id'])[0]
    assert payment['executor_configuration_id'] == original_id
    assert payment['executor_configuration_id'] != replacement_id
    assert payment['provider_idempotency_key'] == original_provider_idempotency_key
    assert executor.execution_calls == 1
    assert executor.recovery_calls == 1
    assert _settlement_count(connection, check['id']) == 0


def test_external_reference_identity_is_unique_per_configuration_under_race(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    first_configuration_id = _configuration(
        connection, scope, key='identity-a', adapter_kind='IDENTITY', priority=10
    )
    second_configuration_id = _configuration(
        connection, scope, key='identity-b', adapter_kind='IDENTITY', priority=20
    )
    executor = DeterministicPaymentExecutor(execution_outcomes=(
        PaymentExecutionOutcome.DEFINITE_FAILURE,
        PaymentExecutionOutcome.DEFINITE_FAILURE,
        PaymentExecutionOutcome.DEFINITE_FAILURE,
    ))

    with TestClient(create_app(
        settings=integration_settings, payment_executors={'IDENTITY': executor}
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-external-identity'
        )
        payments = []
        for index, (key, amount) in enumerate((
            ('identity-a', '10'), ('identity-a', '11'), ('identity-b', '12')
        )):
            response = client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': f'b5-identity-{index}'},
                json={
                    **_electronic_payload(check, amount, diner_id, CUSTOMER_SECRET),
                    'selection_mode': 'EXPLICIT',
                    'executor_key': key,
                },
            )
            assert response.status_code == 201
            assert response.json()['state'] == 'FAILED'
            payments.append(response.json()['id'])

    shared_reference = f'b5-shared-reference-{prefix}'
    barrier = Barrier(2)
    result_lock = Lock()
    results: list[str] = []

    def assign_reference(payment_id: int) -> None:
        worker = pymysql.connect(
            host=integration_settings.mysql_host,
            port=integration_settings.mysql_port,
            user=integration_settings.mysql_user,
            password=integration_settings.mysql_password.get_secret_value(),
            database=integration_settings.mysql_database,
            autocommit=True,
        )
        try:
            barrier.wait(timeout=10)
            try:
                with worker.cursor() as cursor:
                    cursor.execute(
                        'UPDATE restaurant_payments SET external_reference=%s WHERE id=%s',
                        (shared_reference, payment_id),
                    )
                result = 'updated'
            except pymysql.err.IntegrityError:
                result = 'duplicate'
            with result_lock:
                results.append(result)
        finally:
            worker.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = tuple(pool.submit(assign_reference, payment_id) for payment_id in payments[:2])
        for future in futures:
            future.result(timeout=10)

    assert sorted(results) == ['duplicate', 'updated']
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE restaurant_payments SET external_reference=%s WHERE id=%s',
            (shared_reference, payments[2]),
        )
        cursor.execute(
            'SELECT executor_configuration_id,COUNT(*) AS count '
            'FROM restaurant_payments WHERE external_reference=%s '
            'GROUP BY executor_configuration_id ORDER BY executor_configuration_id',
            (shared_reference,),
        )
        identities = tuple(cursor.fetchall())
    assert identities == (
        {'executor_configuration_id': first_configuration_id, 'count': 1},
        {'executor_configuration_id': second_configuration_id, 'count': 1},
    )
    assert _settlement_count(connection, check['id']) == 0


def test_duplicate_provider_success_has_one_settlement_and_uncertain_loser(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    configuration_id = _configuration(
        connection, scope, key='duplicate-success', adapter_kind='DUPLICATE', priority=10
    )
    shared_reference = f'b5-provider-duplicate-{prefix}'
    executor = DuplicateReferenceExecutor(shared_reference)

    with (
        TestClient(create_app(
            settings=integration_settings, payment_executors={'DUPLICATE': executor}
        )) as first_client,
        TestClient(create_app(
            settings=integration_settings, payment_executors={'DUPLICATE': executor}
        )) as second_client,
    ):
        diner_headers, check, diner_id = _new_check(
            first_client, connection, scope, 'b5-duplicate-success'
        )

        def pay(request_client, idempotency_key: str):
            return request_client.post(
                f"/diner/restaurant-checks/{check['id']}/payments",
                headers={**diner_headers, 'Idempotency-Key': idempotency_key},
                json={
                    **_electronic_payload(check, '30', diner_id, CUSTOMER_SECRET),
                    'selection_mode': 'EXPLICIT',
                    'executor_key': 'duplicate-success',
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = tuple(future.result(timeout=20) for future in (
                pool.submit(pay, first_client, 'b5-duplicate-success-a'),
                pool.submit(pay, second_client, 'b5-duplicate-success-b'),
            ))

    assert [response.status_code for response in responses] == [201, 201], [
        response.text for response in responses
    ]
    assert sorted(response.json()['state'] for response in responses) == [
        'SUCCEEDED', 'UNCERTAIN'
    ]
    payments = _payment_rows(connection, check['id'])
    assert len(payments) == 2
    assert all(
        payment['executor_configuration_id'] == configuration_id
        for payment in payments
    )
    assert sorted(payment['state'] for payment in payments) == [
        'SUCCEEDED', 'UNCERTAIN'
    ]
    assert sum(
        payment['external_reference'] == shared_reference for payment in payments
    ) == 1
    assert _settlement_count(connection, check['id']) == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COALESCE(SUM(amount),0) AS amount '
            'FROM restaurant_check_settlements WHERE check_id=%s',
            (check['id'],),
        )
        assert Decimal(cursor.fetchone()['amount']) == Decimal('30')


def test_concurrent_scopes_bind_only_their_own_executor_configuration(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    first_scope = _scope(connection, f'{prefix}-first')
    second_scope = _scope(connection, f'{prefix}-second')
    _grant(connection, first_scope.tenant_id, configure_executor=False)
    _grant(connection, second_scope.tenant_id, configure_executor=False)
    first_id = _configuration(
        connection, first_scope, key='shared', adapter_kind='SCOPED', priority=10
    )
    second_id = _configuration(
        connection, second_scope, key='shared', adapter_kind='SCOPED', priority=10
    )
    _configuration(
        connection, second_scope, key='foreign-only', adapter_kind='SCOPED', priority=0
    )
    executor = DeterministicPaymentExecutor()

    with TestClient(create_app(
        settings=integration_settings, payment_executors={'SCOPED': executor}
    )) as client:
        first_headers, first_check, first_diner = _new_check(
            client, connection, first_scope, 'b5-first-scope'
        )
        second_headers, second_check, second_diner = _new_check(
            client, connection, second_scope, 'b5-second-scope'
        )
        first_payload = _electronic_payload(
            first_check, '30', first_diner, CUSTOMER_SECRET
        )
        first_payload.pop('executor_key')
        first_payload['selection_mode'] = 'AUTO'
        second_payload = {
            **_electronic_payload(second_check, '30', second_diner, CUSTOMER_SECRET),
            'selection_mode': 'EXPLICIT',
            'executor_key': 'shared',
        }

        request_arguments = (
            (
                f"/diner/restaurant-checks/{first_check['id']}/payments",
                {**first_headers, 'Idempotency-Key': 'b5-first-scope'},
                first_payload,
            ),
            (
                f"/diner/restaurant-checks/{second_check['id']}/payments",
                {**second_headers, 'Idempotency-Key': 'b5-second-scope'},
                second_payload,
            ),
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [future.result() for future in (
                pool.submit(
                    client.post,
                    request_arguments[0][0],
                    headers=request_arguments[0][1],
                    json=request_arguments[0][2],
                ),
                pool.submit(
                    client.post,
                    request_arguments[1][0],
                    headers=request_arguments[1][1],
                    json=request_arguments[1][2],
                ),
            )]
        for index, response in enumerate(responses):
            if response.status_code == 409:
                assert response.json()['error']['code'] == 'PAYMENT_CONCURRENCY_CONFLICT'
                path, headers, payload = request_arguments[index]
                responses[index] = client.post(path, headers=headers, json=payload)
        foreign = client.post(
            f"/diner/restaurant-checks/{first_check['id']}/payments",
            headers={**first_headers, 'Idempotency-Key': 'b5-foreign-scope'},
            json={
                **_electronic_payload(first_check, '10', first_diner, CUSTOMER_SECRET),
                'selection_mode': 'EXPLICIT',
                'executor_key': 'foreign-only',
            },
        )

    assert [response.status_code for response in responses] == [201, 201], [
        response.text for response in responses
    ]
    assert foreign.status_code == 409
    assert foreign.json()['error']['code'] == 'PAYMENT_EXECUTOR_UNAVAILABLE'
    assert _payment_rows(connection, first_check['id'])[0]['executor_configuration_id'] == first_id
    assert _payment_rows(connection, second_check['id'])[0]['executor_configuration_id'] == second_id
    assert _settlement_count(connection, first_check['id']) == 1
    assert _settlement_count(connection, second_check['id']) == 1


def test_credential_failure_possible_provider_effect_and_cash_keep_safe_boundaries(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    missing_credential_id = _configuration(
        connection,
        scope,
        key='credential-failure',
        adapter_kind='BEFORE_CALL',
        priority=10,
        credential_binding='missing-binding',
    )
    possible_effect_id = _configuration(
        connection,
        scope,
        key='possible-effect',
        adapter_kind='POSSIBLE_EFFECT',
        priority=20,
        credential_binding='available-binding',
    )
    before_call = DeterministicPaymentExecutor()
    possible_effect = PossibleEffectFailureExecutor()
    credential_resolver = DeterministicMerchantCredentialResolver({
        'available-binding': MERCHANT_SECRET
    })

    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={
            'BEFORE_CALL': before_call,
            'POSSIBLE_EFFECT': possible_effect,
        },
        merchant_credential_resolver=credential_resolver,
    )) as client:
        diner_headers, check, diner_id = _new_check(
            client, connection, scope, 'b5-provider-boundaries'
        )
        credential_failure = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b5-before-call'},
            json={
                **_electronic_payload(check, '20', diner_id, CUSTOMER_SECRET),
                'selection_mode': 'EXPLICIT',
                'executor_key': 'credential-failure',
            },
        )
        possible = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'b5-possible-effect'},
            json={
                **_electronic_payload(check, '20', diner_id, CUSTOMER_SECRET),
                'selection_mode': 'EXPLICIT',
                'executor_key': 'possible-effect',
            },
        )
        resolver_calls_before_cash = len(credential_resolver.calls)
        cash = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={
                **_staff_headers(client, scope),
                'Idempotency-Key': 'b5-cash-regression',
            },
            json={
                'expected_check_version': check['version'],
                'expected_check_fingerprint': check['fingerprint'],
                'amount': '30',
                'currency': 'MXN',
                'method_category': 'CASH',
                'payer_type': 'DINER',
                'payer_diner_session_id': diner_id,
                'cash_tendered_amount': '30',
            },
        )
        projection = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=_staff_headers(client, scope),
        )

    assert credential_failure.status_code == 201
    assert credential_failure.json()['state'] == 'FAILED'
    assert possible.status_code == 201
    assert possible.json()['state'] == 'UNCERTAIN'
    assert cash.status_code == 201 and cash.json()['state'] == 'SUCCEEDED'
    assert before_call.execution_calls == 0
    assert possible_effect.execution_calls == 1
    assert len(credential_resolver.calls) == resolver_calls_before_cash
    rows = _payment_rows(connection, check['id'])
    assert rows[0]['executor_configuration_id'] == missing_credential_id
    assert rows[0]['state'] == 'FAILED'
    assert rows[1]['executor_configuration_id'] == possible_effect_id
    assert rows[1]['state'] == 'UNCERTAIN'
    assert rows[2]['executor_configuration_id'] is None
    assert rows[2]['state'] == 'SUCCEEDED'
    assert _settlement_count(connection, check['id']) == 1
    assert Decimal(projection.json()['confirmed_settlement']) == Decimal('30')
    assert Decimal(projection.json()['uncertain_exposure']) == Decimal('20')
    assert Decimal(projection.json()['reserved_financial_exposure']) == Decimal('20')
    log_payload = repr([vars(record) for record in caplog.records])
    durable_payload = repr(rows)
    for secret in (CUSTOMER_SECRET, MERCHANT_SECRET, 'missing-binding'):
        assert secret not in log_payload
        assert secret not in durable_payload
