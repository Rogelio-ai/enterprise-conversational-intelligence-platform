from __future__ import annotations

from collections import deque

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


class DeterministicPaymentExecutor:
    """Bounded WS-23 certification executor; never a production provider."""

    def __init__(
        self,
        *,
        execution_outcomes: tuple[PaymentExecutionOutcome, ...] = (PaymentExecutionOutcome.SUCCEEDED,),
        recovery_outcomes: tuple[PaymentRecoveryOutcome, ...] = (PaymentRecoveryOutcome.CONFIRMED_SUCCESS,),
    ) -> None:
        self._execution_outcomes = deque(execution_outcomes)
        self._recovery_outcomes = deque(recovery_outcomes)
        self._operations: dict[str, PaymentExecutionResult] = {}
        self.execution_calls = 0
        self.recovery_calls = 0
        self.execution_received_customer_source = False
        self.execution_received_merchant_credential = False
        self.recovery_received_merchant_credential = False
        self.last_recovery_external_reference: str | None = None

    @staticmethod
    def _reference(request_fingerprint: str) -> str:
        return f'mock-payment-{request_fingerprint[:24]}'

    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult:
        self.execution_received_merchant_credential = merchant_credential is not None
        self.execution_received_customer_source = customer_payment_source is not None
        existing = self._operations.get(request.idempotency_key)
        if existing is not None:
            return existing
        self.execution_calls += 1
        outcome = self._execution_outcomes.popleft() if self._execution_outcomes else PaymentExecutionOutcome.SUCCEEDED
        evidence = {
            'external_reference': self._reference(request.request_fingerprint),
            'external_status': outcome.value,
            'instrument_brand': 'TEST',
            'instrument_last_four': '0000',
            'instrument_display': 'TEST •••• 0000',
        }
        if outcome is PaymentExecutionOutcome.SUCCEEDED:
            result = PaymentExecutionResult(outcome=outcome, **evidence)
        elif outcome is PaymentExecutionOutcome.UNCERTAIN:
            result = PaymentExecutionResult(outcome=outcome, **evidence, error_code='MOCK_UNCERTAIN', error_message='Deterministic uncertain result')
        else:
            result = PaymentExecutionResult(
                outcome=outcome,
                external_status=outcome.value,
                error_code=f'MOCK_{outcome.value}',
                error_message=f'Deterministic {outcome.value.lower()}',
            )
        self._operations[request.idempotency_key] = result
        return result

    async def recover(
        self,
        *,
        request: PaymentRecoveryRequest,
        merchant_credential: EphemeralMerchantCredential | None = None,
    ) -> PaymentRecoveryResult:
        self.recovery_calls += 1
        self.recovery_received_merchant_credential = merchant_credential is not None
        self.last_recovery_external_reference = request.external_reference
        outcome = self._recovery_outcomes.popleft() if self._recovery_outcomes else PaymentRecoveryOutcome.STILL_UNCERTAIN
        if outcome is PaymentRecoveryOutcome.DEFINITE_ABSENCE:
            # The executor has certified that no provider-side operation exists;
            # a later retry may therefore reuse the durable idempotency key.
            self._operations.pop(request.idempotency_key, None)
        if outcome is PaymentRecoveryOutcome.CONFIRMED_SUCCESS:
            return PaymentRecoveryResult(
                outcome=outcome,
                external_reference=self._reference(request.request_fingerprint),
                external_status='SUCCEEDED',
                instrument_brand='TEST', instrument_last_four='0000', instrument_display='TEST •••• 0000',
            )
        return PaymentRecoveryResult(
            outcome=outcome,
            external_status=outcome.value,
            error_code=f'MOCK_{outcome.value}',
            error_message=f'Deterministic {outcome.value.lower()}',
        )
