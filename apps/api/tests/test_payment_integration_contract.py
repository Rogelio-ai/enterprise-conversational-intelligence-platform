from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
    PaymentCustomerIdentity,
    PaymentRecoveryOutcome,
    PaymentRecoveryRequest,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor


def test_payment_port_contract_is_restaurant_independent_and_exact() -> None:
    field_names = set(PaymentExecutionRequest.model_fields)
    assert field_names == {
        'operation_reference', 'amount', 'currency', 'method_category',
        'idempotency_key', 'request_fingerprint', 'customer_identity',
    }
    assert not any(
        token in name
        for name in field_names
        for token in ('restaurant', 'check', 'order', 'diner', 'service_session')
    )
    with pytest.raises(ValidationError):
        PaymentExecutionRequest(
            operation_reference='operation-1', amount=1.2, currency='MXN',
            method_category='CARD', idempotency_key='stable-key',
            request_fingerprint='a' * 64,
            customer_identity={
                'display_name': 'Ana', 'email': 'ana@example.com', 'phone': '+525500000001',
            },
        )


def test_payment_customer_identity_normalizes_and_rejects_invalid_contact_data() -> None:
    identity = PaymentCustomerIdentity(
        display_name='  Ana  ', email='  ANA@Example.COM ', phone='+52 (55) 0000-0001',
    )
    assert identity.model_dump() == {
        'display_name': 'Ana', 'email': 'ana@example.com', 'phone': '+525500000001',
    }
    for invalid in (
        {'display_name': '', 'email': 'ana@example.com', 'phone': '+525500000001'},
        {'display_name': 'Ana', 'email': 'invalid', 'phone': '+525500000001'},
        {'display_name': 'Ana', 'email': 'ana@example.com', 'phone': '5500000001'},
        {'display_name': 'Ana', 'email': 'ana@example.com'},
        {'display_name': 'Ana', 'phone': '+525500000001'},
    ):
        with pytest.raises(ValidationError):
            PaymentCustomerIdentity.model_validate(invalid)


def test_deterministic_executor_stable_idempotency_and_recovery_outcomes() -> None:
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(
            PaymentRecoveryOutcome.DEFINITE_ABSENCE,
            PaymentRecoveryOutcome.STILL_UNCERTAIN,
        ),
    )
    request = PaymentExecutionRequest(
        operation_reference='operation-1', amount=Decimal('10.0000'),
        currency='MXN', method_category='CARD', idempotency_key='stable-key',
        request_fingerprint='a' * 64,
        customer_identity={
            'display_name': 'Ana', 'email': 'ana@example.com', 'phone': '+525500000001',
        },
    )
    customer_source = EphemeralCustomerPaymentSource(value='test-only-customer-source')
    merchant_credential = EphemeralMerchantCredential(value='test-only-merchant-credential')
    first = asyncio.run(executor.execute(
        request=request,
        merchant_credential=merchant_credential,
        customer_payment_source=customer_source,
    ))
    replay = asyncio.run(executor.execute(
        request=request,
        merchant_credential=merchant_credential,
        customer_payment_source=customer_source,
    ))
    assert first == replay
    assert executor.execution_calls == 1
    assert executor.last_customer_identity == request.customer_identity
    recovery_request = PaymentRecoveryRequest(
        operation_reference='operation-1', idempotency_key='stable-key',
        request_fingerprint='a' * 64,
    )
    absent = asyncio.run(executor.recover(
        request=recovery_request, merchant_credential=merchant_credential
    ))
    uncertain = asyncio.run(executor.recover(
        request=recovery_request, merchant_credential=merchant_credential
    ))
    assert absent.outcome is PaymentRecoveryOutcome.DEFINITE_ABSENCE
    assert uncertain.outcome is PaymentRecoveryOutcome.STILL_UNCERTAIN
    for secret in (customer_source, merchant_credential):
        assert 'test-only' not in repr(secret)
        assert 'test-only' not in str(secret)
