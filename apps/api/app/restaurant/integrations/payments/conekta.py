from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Protocol

import httpx

from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
    PaymentExecutionResult,
)


CONEKTA_ORDERS_ENDPOINT = 'https://api.conekta.io/orders'
CONEKTA_ACCEPT = 'application/vnd.conekta-v2.3.0+json'
_MINOR_UNIT_FACTOR = Decimal('100')


class ConektaAmbiguousTransportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConektaHttpResponse:
    status_code: int
    body: Mapping[str, Any] | None


class ConektaOrderTransport(Protocol):
    async def create_order(
        self, *, private_key: str, payload: Mapping[str, Any]
    ) -> ConektaHttpResponse: ...


class HttpxConektaOrderTransport:
    """Single-attempt Conekta Direct API transport with bounded timeouts."""

    def __init__(
        self,
        *,
        endpoint: str = CONEKTA_ORDERS_ENDPOINT,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._transport = transport
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )

    async def create_order(
        self, *, private_key: str, payload: Mapping[str, Any]
    ) -> ConektaHttpResponse:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self._endpoint,
                    json=payload,
                    headers={
                        'Authorization': f'Bearer {private_key}',
                        'Accept': CONEKTA_ACCEPT,
                        'Content-Type': 'application/json',
                        'Accept-Language': 'es',
                    },
                )
        except httpx.HTTPError as exc:
            raise ConektaAmbiguousTransportError(
                'Conekta outcome is unknown after transport interruption'
            ) from exc
        try:
            body = response.json()
        except ValueError:
            body = None
        return ConektaHttpResponse(
            status_code=response.status_code,
            body=body if isinstance(body, Mapping) else None,
        )


def _minor_units(amount: Decimal, currency: str) -> int:
    if currency != 'MXN':
        raise ValueError('Conekta CARD execution supports MXN only')
    scaled = amount * _MINOR_UNIT_FACTOR
    exact = scaled.to_integral_value()
    if scaled != exact:
        raise ValueError('Conekta amount has unsupported precision')
    return int(exact)


def _string(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:maximum] if normalized else None


def _charge(body: Mapping[str, Any]) -> Mapping[str, Any] | None:
    charges = body.get('charges')
    if not isinstance(charges, Mapping):
        return None
    data = charges.get('data')
    if not isinstance(data, list) or not data or not isinstance(data[0], Mapping):
        return None
    return data[0]


def _safe_evidence(body: Mapping[str, Any]) -> dict[str, str | None]:
    charge = _charge(body)
    payment_method = None if charge is None else charge.get('payment_method')
    payment_method = payment_method if isinstance(payment_method, Mapping) else {}
    brand = _string(payment_method.get('brand'), maximum=64)
    last_four = _string(payment_method.get('last4'), maximum=4)
    if last_four is not None and (len(last_four) != 4 or not last_four.isdigit()):
        last_four = None
    display = None
    if last_four is not None:
        display = f'{(brand or "CARD").upper()} •••• {last_four}'[:100]
    return {
        'external_reference': _string(body.get('id'), maximum=200),
        'external_status': _string(body.get('payment_status'), maximum=64),
        'instrument_brand': None if brand is None else brand.upper(),
        'instrument_last_four': last_four,
        'instrument_display': display,
    }


class ConektaPaymentExecutor:
    """Initial Conekta CARD Order executor; recovery and 3DS continuation are separate."""

    def __init__(self, transport: ConektaOrderTransport | None = None) -> None:
        self._transport = transport or HttpxConektaOrderTransport()

    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult:
        if request.method_category != 'CARD':
            return self._failure('CONEKTA_METHOD_UNSUPPORTED')
        if merchant_credential is None:
            return self._failure('CONEKTA_CREDENTIAL_UNAVAILABLE')
        if customer_payment_source is None:
            return self._failure('CONEKTA_PAYMENT_SOURCE_REQUIRED')
        try:
            unit_price = _minor_units(request.amount, request.currency)
        except ValueError:
            return self._failure('CONEKTA_AMOUNT_UNSUPPORTED')

        identity = request.customer_identity
        payload = {
            'currency': request.currency,
            'customer_info': {
                'name': identity.display_name,
                'email': identity.email,
                'phone': identity.phone,
            },
            'line_items': [{
                'name': f'Restaurant check {request.operation_reference}',
                'unit_price': unit_price,
                'quantity': 1,
            }],
            'charges': [{
                'payment_method': {
                    'type': 'card',
                    'token_id': customer_payment_source.value.get_secret_value(),
                },
            }],
        }
        try:
            response = await self._transport.create_order(
                private_key=merchant_credential.value.get_secret_value(),
                payload=payload,
            )
        except ConektaAmbiguousTransportError:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.UNCERTAIN,
                error_code='CONEKTA_TRANSPORT_UNCERTAIN',
                error_message='Conekta did not establish a definitive payment result',
            )
        return self._result(response)

    @staticmethod
    def _failure(code: str) -> PaymentExecutionResult:
        return PaymentExecutionResult(
            outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
            error_code=code,
            error_message='Conekta payment could not be executed',
        )

    @classmethod
    def _result(cls, response: ConektaHttpResponse) -> PaymentExecutionResult:
        body = response.body
        if response.status_code == 401:
            return cls._failure('CONEKTA_AUTHENTICATION_ERROR')
        if response.status_code == 402:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.REJECTED,
                external_status='HTTP_402',
                error_code='CONEKTA_PAYMENT_REJECTED',
                error_message='Conekta did not approve the card payment',
            )
        if response.status_code == 422:
            return cls._failure('CONEKTA_REQUEST_REJECTED')
        if response.status_code >= 500:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.UNCERTAIN,
                external_status=f'HTTP_{response.status_code}',
                error_code='CONEKTA_PROVIDER_UNCERTAIN',
                error_message='Conekta did not establish a definitive payment result',
            )
        if not 200 <= response.status_code < 300 or body is None:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.UNCERTAIN,
                external_status=f'HTTP_{response.status_code}',
                error_code='CONEKTA_RESPONSE_UNCERTAIN',
                error_message='Conekta returned an unexpected payment result',
            )

        evidence = _safe_evidence(body)
        payment_status = evidence['external_status']
        if payment_status == 'paid' and evidence['external_reference']:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.SUCCEEDED, **evidence
            )
        if payment_status in {'declined', 'rejected'}:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.REJECTED,
                error_code='CONEKTA_PAYMENT_REJECTED',
                error_message='Conekta did not approve the card payment',
                **evidence,
            )
        if payment_status in {'failed', 'error', 'expired', 'cancelled'}:
            return PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
                error_code='CONEKTA_PAYMENT_FAILED',
                error_message='Conekta established that the payment failed',
                **evidence,
            )
        return PaymentExecutionResult(
            outcome=PaymentExecutionOutcome.UNCERTAIN,
            error_code='CONEKTA_RESULT_PENDING',
            error_message='Conekta payment result requires later confirmation',
            **evidence,
        )
