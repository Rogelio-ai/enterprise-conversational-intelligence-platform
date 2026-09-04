from __future__ import annotations

from collections import deque

from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceOutcome,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalIssuanceResult,
    FiscalProviderErrorKind,
    FiscalRecoveryOutcome,
    FiscalRecoveryResult,
)


class DeterministicFiscalProvider:
    """Bounded in-memory contract fake; never a production provider."""

    def __init__(
        self,
        *,
        issuance_outcomes: tuple[FiscalIssuanceOutcome, ...] = (
            FiscalIssuanceOutcome.SUCCEEDED,
        ),
        recovery_outcomes: tuple[FiscalRecoveryOutcome, ...] = (
            FiscalRecoveryOutcome.RECOVERED_SUCCESS,
        ),
    ) -> None:
        self._issuance_outcomes = deque(issuance_outcomes)
        self._recovery_outcomes = deque(recovery_outcomes)
        self._operations: dict[str, FiscalIssuanceResult] = {}
        self.issue_calls = 0
        self.recovery_calls = 0
        self.issue_received_credential = False
        self.recovery_received_credential = False

    @staticmethod
    def _reference(request_fingerprint: str) -> str:
        return f'fake-fiscal-{request_fingerprint[:24]}'

    async def issue(
        self,
        *,
        request: FiscalIssuanceRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalIssuanceResult:
        self.issue_received_credential = credential is not None
        existing = self._operations.get(request.provider_idempotency_key)
        if existing is not None:
            return existing

        self.issue_calls += 1
        outcome = (
            self._issuance_outcomes.popleft()
            if self._issuance_outcomes
            else FiscalIssuanceOutcome.SUCCEEDED
        )
        if outcome is FiscalIssuanceOutcome.SUCCEEDED:
            result = FiscalIssuanceResult(
                outcome=outcome,
                external_reference=self._reference(request.request_fingerprint),
                external_status=outcome.value,
            )
        else:
            error_kind = {
                FiscalIssuanceOutcome.DEFINITE_FAILURE:
                    FiscalProviderErrorKind.TECHNICAL_FAILURE,
                FiscalIssuanceOutcome.REJECTED:
                    FiscalProviderErrorKind.BUSINESS_REJECTION,
                FiscalIssuanceOutcome.UNCERTAIN:
                    FiscalProviderErrorKind.AMBIGUOUS_RESULT,
            }[outcome]
            result = FiscalIssuanceResult(
                outcome=outcome,
                external_status=outcome.value,
                error_kind=error_kind,
                error_message=f'Deterministic {outcome.value.lower()}',
            )
        self._operations[request.provider_idempotency_key] = result
        return result

    async def recover(
        self,
        *,
        request: FiscalIssuanceRecoveryRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalRecoveryResult:
        self.recovery_received_credential = credential is not None
        self.recovery_calls += 1
        outcome = (
            self._recovery_outcomes.popleft()
            if self._recovery_outcomes
            else FiscalRecoveryOutcome.STILL_UNCERTAIN
        )
        if outcome is FiscalRecoveryOutcome.RECOVERED_SUCCESS:
            return FiscalRecoveryResult(
                outcome=outcome,
                external_reference=(
                    request.external_reference
                    or self._reference(request.request_fingerprint)
                ),
                external_status=outcome.value,
            )
        if outcome is FiscalRecoveryOutcome.DEFINITE_ABSENCE:
            self._operations.pop(request.provider_idempotency_key, None)
            return FiscalRecoveryResult(
                outcome=outcome,
                external_status=outcome.value,
            )
        error_kind = {
            FiscalRecoveryOutcome.DEFINITE_FAILURE:
                FiscalProviderErrorKind.TECHNICAL_FAILURE,
            FiscalRecoveryOutcome.REJECTED:
                FiscalProviderErrorKind.BUSINESS_REJECTION,
            FiscalRecoveryOutcome.STILL_UNCERTAIN:
                FiscalProviderErrorKind.AMBIGUOUS_RESULT,
        }[outcome]
        return FiscalRecoveryResult(
            outcome=outcome,
            external_status=outcome.value,
            error_kind=error_kind,
            error_message=f'Deterministic {outcome.value.lower()}',
        )
