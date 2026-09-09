from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.payments.conekta import (
    ConektaHttpResponse,
    ConektaPaymentExecutor,
)
from app.restaurant.integrations.payments.credentials import (
    DeterministicMerchantCredentialResolver,
)
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


PRIVATE_KEY = 'conekta-recovery-private-secret'
TOKEN = 'tok_recovery_execution_only'


class RecoverableConektaTransport:
    def __init__(self) -> None:
        self.create_calls: list[tuple[str, Mapping[str, Any]]] = []
        self.retrieve_calls: list[tuple[str, str]] = []

    async def create_order(
        self, *, private_key: str, payload: Mapping[str, Any]
    ) -> ConektaHttpResponse:
        self.create_calls.append((private_key, payload))
        return ConektaHttpResponse(200, {
            'id': 'ord_recoverable_payment',
            'payment_status': 'pending_payment',
            'charges': {
                'data': [{
                    'payment_method': {'brand': 'visa', 'last4': '4242'},
                }],
            },
        })

    async def retrieve_order(
        self, *, private_key: str, order_id: str
    ) -> ConektaHttpResponse:
        self.retrieve_calls.append((private_key, order_id))
        return ConektaHttpResponse(200, {
            'id': order_id,
            'payment_status': 'paid',
            'charges': {
                'data': [{
                    'payment_method': {'brand': 'visa', 'last4': '4242'},
                }],
            },
        })


def test_real_conekta_recovery_uses_order_lookup_and_generic_settlement_once(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _configuration(
        connection,
        scope,
        key='conekta-recovery',
        adapter_kind='CONEKTA',
        priority=10,
        credential_binding='conekta-recovery-binding',
        client_public_key='key_public_only',
    )
    transport = RecoverableConektaTransport()
    credentials = DeterministicMerchantCredentialResolver({
        'conekta-recovery-binding': PRIVATE_KEY,
    })

    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={'CONEKTA': ConektaPaymentExecutor(transport)},
        merchant_credential_resolver=credentials,
    )) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'conekta-recovery-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={
                **diner_headers,
                'Idempotency-Key': 'conekta-recovery-payment',
            },
            json={
                **_electronic_payload(check, '100', diner_id, TOKEN),
                'selection_mode': 'EXPLICIT',
                'executor_key': 'conekta-recovery',
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()['state'] == 'UNCERTAIN'
        assert created.json()['external_reference'] == 'ord_recoverable_payment'

        staff_headers = _staff_headers(client, scope)
        recovered = client.post(
            f"/restaurant-payments/{created.json()['id']}/recover",
            headers=staff_headers,
        )
        repeated = client.post(
            f"/restaurant-payments/{created.json()['id']}/recover",
            headers=staff_headers,
        )
        settlement = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )

    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['state'] == 'SUCCEEDED'
    assert recovered.json()['external_reference'] == 'ord_recoverable_payment'
    assert repeated.status_code == 409
    assert repeated.json()['error']['code'] == 'PAYMENT_STATE_CONFLICT'
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()['check_status'] == 'SETTLED'
    assert Decimal(settlement.json()['confirmed_settlement']) == Decimal('100')
    assert Decimal(settlement.json()['uncertain_exposure']) == Decimal('0')
    assert transport.retrieve_calls == [
        (PRIVATE_KEY, 'ord_recoverable_payment'),
    ]
    assert len(transport.create_calls) == 1

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE payment_id=%s',
            (created.json()['id'],),
        )
        assert cursor.fetchone()['count'] == 1

    persisted_and_logged = repr(settlement.json()) + caplog.text
    assert PRIVATE_KEY not in persisted_and_logged
    assert TOKEN not in persisted_and_logged
