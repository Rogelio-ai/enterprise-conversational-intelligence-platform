from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.restaurant.integrations.payments.contracts import (
    EphemeralExecutionCredential,
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
    credential = EphemeralExecutionCredential(value='test-only-ephemeral')
    first = asyncio.run(executor.execute(request=request, credential=credential))
    replay = asyncio.run(executor.execute(request=request, credential=credential))
    assert first == replay
    assert executor.execution_calls == 1
    recovery_request = PaymentRecoveryRequest(
        operation_reference='operation-1', idempotency_key='stable-key',
        request_fingerprint='a' * 64,
    )
    absent = asyncio.run(executor.recover(request=recovery_request))
    uncertain = asyncio.run(executor.recover(request=recovery_request))
    assert absent.outcome is PaymentRecoveryOutcome.DEFINITE_ABSENCE
    assert uncertain.outcome is PaymentRecoveryOutcome.STILL_UNCERTAIN
    assert 'test-only-ephemeral' not in repr(credential)
