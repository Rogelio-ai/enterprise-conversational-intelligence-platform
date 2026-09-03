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
    PaymentRecoveryOutcome,
    PaymentRecoveryRequest,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor


def test_payment_port_contract_is_restaurant_independent_and_exact() -> None:
    field_names = set(PaymentExecutionRequest.model_fields)
    assert field_names == {
        'operation_reference', 'amount', 'currency', 'method_category',
        'idempotency_key', 'request_fingerprint',
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
        )


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
