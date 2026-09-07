from __future__ import annotations

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
from test_canonical_order_commercial_acceptance import _open_and_join, _scope
from test_payment_executor_api import _configuration
from test_restaurant_payment_settlement_foundation import (
    _check,
    _electronic_payload,
    _grant,
    _order,
)


PRIVATE_KEY = 'conekta-private-integration-secret'
TOKEN = 'tok_integration_opaque_secret'


class CommitInspectingConektaTransport:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.durable_before_http: list[bool] = []

    async def create_order(
        self, *, private_key: str, payload: Mapping[str, Any]
    ) -> ConektaHttpResponse:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT state FROM restaurant_payments ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
        self.durable_before_http.append(row is not None and row['state'] == 'IN_PROGRESS')
        self.calls.append((private_key, payload))
        return ConektaHttpResponse(200, {
            'id': 'ord_committed_payment', 'payment_status': 'paid',
            'charges': {'data': [{'payment_method': {'brand': 'visa', 'last4': '4242'}}]},
        })


def test_real_conekta_path_commits_before_http_and_replay_never_duplicates(
    integration_settings, sql_connection, caplog,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _configuration(
        connection, scope, key='conekta-card', adapter_kind='CONEKTA', priority=10,
        credential_binding='conekta-private-binding', client_public_key='key_public_only',
    )
    transport = CommitInspectingConektaTransport(connection)
    executor = ConektaPaymentExecutor(transport)
    credentials = DeterministicMerchantCredentialResolver({
        'conekta-private-binding': PRIVATE_KEY,
    })

    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={'CONEKTA': executor},
        merchant_credential_resolver=credentials,
    )) as client:
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'real-conekta-payment')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payload = {
            **_electronic_payload(check, '100', diner_id, TOKEN),
            'selection_mode': 'EXPLICIT', 'executor_key': 'conekta-card',
        }
        headers = {**diner_headers, 'Idempotency-Key': 'real-conekta-one-logical-payment'}
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments", headers=headers, json=payload,
        )
        replay = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments", headers=headers, json=payload,
        )
        changed = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers=headers,
            json={**payload, 'amount': '99'},
        )

    assert created.status_code == 201, created.text
    assert created.json()['state'] == 'SUCCEEDED'
    assert created.json()['external_reference'] == 'ord_committed_payment'
    assert replay.status_code == 200 and replay.json()['id'] == created.json()['id']
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'PAYMENT_IDEMPOTENCY_CONFLICT'
    assert transport.durable_before_http == [True]
    assert len(transport.calls) == 1
    assert transport.calls[0][0] == PRIVATE_KEY
    assert transport.calls[0][1]['line_items'][0]['unit_price'] == 10000
    assert transport.calls[0][1]['charges'][0]['payment_method']['token_id'] == TOKEN
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT external_reference,state FROM restaurant_payments WHERE id=%s',
            (created.json()['id'],),
        )
        assert cursor.fetchone() == {
            'external_reference': 'ord_committed_payment', 'state': 'SUCCEEDED',
        }
    persisted_and_logged = repr(transport.durable_before_http) + caplog.text
    assert PRIVATE_KEY not in persisted_and_logged
    assert TOKEN not in persisted_and_logged
