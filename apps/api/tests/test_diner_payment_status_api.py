from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.payments.contracts import (
    PaymentExecutionOutcome,
    PaymentRecoveryOutcome,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from test_canonical_order_commercial_acceptance import _open_and_join, _scope
from test_restaurant_payment_settlement_foundation import (
    _check,
    _electronic_payload,
    _grant,
    _join_opened,
    _order,
)


SAFE_DINER_PAYMENT_FIELDS = {
    'id', 'check_id', 'amount', 'currency', 'method_category', 'state',
    'instrument_display', 'terminal_at',
}


def _payment_count(connection, check_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
            (check_id,),
        )
        return int(cursor.fetchone()['count'])


def test_diner_payment_read_and_recovery_are_check_authorized_and_settle_once(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, f'{prefix}-owner')
    foreign_scope = _scope(connection, f'{prefix}-foreign')
    _grant(connection, scope.tenant_id)
    _grant(connection, foreign_scope.tenant_id)
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(PaymentRecoveryOutcome.CONFIRMED_SUCCESS,),
    )

    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={'deterministic': executor},
    )) as client:
        opened, owner_headers = _open_and_join(client, scope)
        _, foreign_headers = _open_and_join(client, foreign_scope)
        unrelated_headers = _join_opened(client, opened, 'Unrelated diner')
        _order(client, connection, scope, owner_headers, amount='100')
        check = _check(client, owner_headers, 'diner-payment-status-check')
        diner_id = client.get('/diner-session', headers=owner_headers).json()['id']
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={
                **owner_headers,
                'Idempotency-Key': 'diner-payment-status-uncertain',
            },
            json=_electronic_payload(check, '100', diner_id),
        )
        assert created.status_code == 201, created.text
        payment_id = created.json()['id']
        payment_url = (
            f"/diner/restaurant-checks/{check['id']}/payments/{payment_id}"
        )

        read = client.get(payment_url, headers=owner_headers)
        unrelated = client.get(payment_url, headers=unrelated_headers)
        foreign = client.get(payment_url, headers=foreign_headers)
        wrong_check = client.get(
            f'/diner/restaurant-checks/{check["id"]}/payments/{payment_id + 999}',
            headers=owner_headers,
        )
        before_count = _payment_count(connection, check['id'])
        recovered = client.post(f'{payment_url}/recover', headers=owner_headers)
        repeated = client.post(f'{payment_url}/recover', headers=owner_headers)
        settlement = client.get(
            f"/diner/restaurant-checks/{check['id']}/settlement",
            headers=owner_headers,
        )

    assert read.status_code == 200, read.text
    assert set(read.json()) == SAFE_DINER_PAYMENT_FIELDS
    assert read.json()['state'] == 'UNCERTAIN'
    assert 'fingerprint' not in read.text
    assert 'attempt' not in read.text
    assert unrelated.status_code == 404
    assert foreign.status_code == 404
    assert wrong_check.status_code == 404
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['state'] == 'SUCCEEDED'
    assert repeated.status_code == 409
    assert repeated.json()['error']['code'] == 'PAYMENT_STATE_CONFLICT'
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()['check_status'] == 'SETTLED'
    assert Decimal(settlement.json()['confirmed_settlement']) == Decimal('100')
    assert _payment_count(connection, check['id']) == before_count == 1
    assert executor.execution_calls == 1
    assert executor.recovery_calls == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE payment_id=%s',
            (payment_id,),
        )
        assert cursor.fetchone()['count'] == 1


def test_diner_recovery_still_uncertain_preserves_blocking_financial_truth(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(PaymentRecoveryOutcome.STILL_UNCERTAIN,),
    )

    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={'deterministic': executor},
    )) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'diner-still-uncertain-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'diner-still-uncertain'},
            json=_electronic_payload(check, '40', diner_id),
        ).json()
        recovered = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments/{created['id']}/recover",
            headers=diner_headers,
        )
        settlement = client.get(
            f"/diner/restaurant-checks/{check['id']}/settlement",
            headers=diner_headers,
        )

    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['state'] == 'UNCERTAIN'
    assert Decimal(settlement.json()['uncertain_exposure']) == Decimal('40')
    assert Decimal(settlement.json()['available_to_initiate']) == Decimal('60')
    assert executor.execution_calls == 1
    assert executor.recovery_calls == 1
    assert _payment_count(connection, check['id']) == 1
