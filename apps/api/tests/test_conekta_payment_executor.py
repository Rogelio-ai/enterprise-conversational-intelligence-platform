from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Mapping

import httpx
import pytest

from app.main import create_app
from app.restaurant.integrations.payments.conekta import (
    CONEKTA_ACCEPT,
    CONEKTA_ORDERS_ENDPOINT,
    ConektaAmbiguousTransportError,
    ConektaHttpResponse,
    ConektaPaymentExecutor,
    HttpxConektaOrderTransport,
)
from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
)


PRIVATE_KEY = 'private-key-must-remain-server-side'
TOKEN = 'tok_test_opaque_never_log'


class RecordingTransport:
    def __init__(self, response: ConektaHttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def create_order(
        self, *, private_key: str, payload: Mapping[str, Any]
    ) -> ConektaHttpResponse:
        self.calls.append((private_key, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _request(amount: str = '123.45', currency: str = 'MXN') -> PaymentExecutionRequest:
    return PaymentExecutionRequest(
        operation_reference='42', amount=Decimal(amount), currency=currency,
        method_category='CARD', idempotency_key='provider-key',
        request_fingerprint='a' * 64,
        customer_identity={
            'display_name': 'Ana', 'email': 'ana@example.com', 'phone': '+525500000001',
        },
    )


def _execute(executor: ConektaPaymentExecutor, request: PaymentExecutionRequest | None = None):
    return asyncio.run(executor.execute(
        request=request or _request(),
        merchant_credential=EphemeralMerchantCredential(value=PRIVATE_KEY),
        customer_payment_source=EphemeralCustomerPaymentSource(value=TOKEN),
    ))


def test_conekta_executor_maps_exact_truthful_order_and_safe_success_evidence() -> None:
    transport = RecordingTransport(ConektaHttpResponse(200, {
        'id': 'ord_safe_reference', 'payment_status': 'paid',
        'charges': {'data': [{'payment_method': {'brand': 'visa', 'last4': '4242'}}]},
    }))
    result = _execute(ConektaPaymentExecutor(transport))

    assert result.outcome is PaymentExecutionOutcome.SUCCEEDED
    assert result.external_reference == 'ord_safe_reference'
    assert result.instrument_display == 'VISA •••• 4242'
    assert len(transport.calls) == 1
    private_key, payload = transport.calls[0]
    assert private_key == PRIVATE_KEY
    assert payload == {
        'currency': 'MXN',
        'customer_info': {
            'name': 'Ana', 'email': 'ana@example.com', 'phone': '+525500000001',
        },
        'line_items': [{
            'name': 'Restaurant check 42', 'unit_price': 12345, 'quantity': 1,
        }],
        'charges': [{
            'payment_method': {'type': 'card', 'token_id': TOKEN},
        }],
    }
    assert not any(isinstance(value, float) for value in _walk(payload))
    assert not {'pan', 'cvv', 'cvc', 'card_number'} & set(_keys(payload))


def _walk(value: object):
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)
    else:
        yield value


def _keys(value: object):
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield key
            yield from _keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _keys(nested)


@pytest.mark.parametrize(
    ('response', 'outcome', 'code'),
    (
        (ConektaHttpResponse(402, {}), PaymentExecutionOutcome.REJECTED, 'CONEKTA_PAYMENT_REJECTED'),
        (ConektaHttpResponse(401, {}), PaymentExecutionOutcome.DEFINITE_FAILURE, 'CONEKTA_AUTHENTICATION_ERROR'),
        (ConektaHttpResponse(422, {}), PaymentExecutionOutcome.DEFINITE_FAILURE, 'CONEKTA_REQUEST_REJECTED'),
        (ConektaHttpResponse(500, {}), PaymentExecutionOutcome.UNCERTAIN, 'CONEKTA_PROVIDER_UNCERTAIN'),
        (ConektaHttpResponse(200, {'id': 'ord_pending', 'payment_status': 'pending_payment'}), PaymentExecutionOutcome.UNCERTAIN, 'CONEKTA_RESULT_PENDING'),
        (ConektaHttpResponse(200, {'id': 'ord_failed', 'payment_status': 'failed'}), PaymentExecutionOutcome.DEFINITE_FAILURE, 'CONEKTA_PAYMENT_FAILED'),
        (ConektaHttpResponse(200, None), PaymentExecutionOutcome.UNCERTAIN, 'CONEKTA_RESPONSE_UNCERTAIN'),
        (ConektaAmbiguousTransportError(), PaymentExecutionOutcome.UNCERTAIN, 'CONEKTA_TRANSPORT_UNCERTAIN'),
    ),
)
def test_conekta_executor_maps_controlled_outcomes_without_retry(
    response, outcome, code,
) -> None:
    transport = RecordingTransport(response)
    result = _execute(ConektaPaymentExecutor(transport))
    assert result.outcome is outcome
    assert result.error_code == code
    assert len(transport.calls) == 1
    assert PRIVATE_KEY not in repr(result)
    assert TOKEN not in repr(result)


@pytest.mark.parametrize(('amount', 'currency'), (('10.001', 'MXN'), ('10.00', 'USD')))
def test_conekta_executor_rejects_inexact_or_unsupported_money_before_http(
    amount: str, currency: str,
) -> None:
    transport = RecordingTransport(ConektaHttpResponse(200, {}))
    result = _execute(ConektaPaymentExecutor(transport), _request(amount, currency))
    assert result.outcome is PaymentExecutionOutcome.DEFINITE_FAILURE
    assert result.error_code == 'CONEKTA_AMOUNT_UNSUPPORTED'
    assert transport.calls == []


def test_http_transport_posts_once_with_private_bearer_and_v23_headers() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'id': 'ord_1', 'payment_status': 'paid'})

    transport = HttpxConektaOrderTransport(transport=httpx.MockTransport(handler))
    response = asyncio.run(transport.create_order(
        private_key=PRIVATE_KEY, payload={'currency': 'MXN'},
    ))
    assert response.status_code == 200
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == CONEKTA_ORDERS_ENDPOINT
    assert request.headers['Authorization'] == f'Bearer {PRIVATE_KEY}'
    assert request.headers['Accept'] == CONEKTA_ACCEPT
    assert request.headers['Accept-Language'] == 'es'


def test_default_runtime_registry_contains_real_conekta_executor(integration_settings) -> None:
    app = create_app(settings=integration_settings)
    assert isinstance(
        app.state.payment_executor_registry.resolve('CONEKTA'), ConektaPaymentExecutor
    )
