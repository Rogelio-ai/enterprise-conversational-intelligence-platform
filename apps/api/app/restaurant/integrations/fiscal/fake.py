from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import hashlib

from app.restaurant.integrations.fiscal.contracts import (
    AuthoritativeFiscalResult,
    EphemeralFiscalProviderCredential,
    FiscalIssuanceOutcome,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalIssuanceResult,
    FiscalArtifactEvidence,
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

    @staticmethod
    def _fiscal_result(request_fingerprint: str) -> AuthoritativeFiscalResult:
        content = f'<fake-fiscal>{request_fingerprint}</fake-fiscal>'.encode()
        reference = DeterministicFiscalProvider._reference(request_fingerprint)
        return AuthoritativeFiscalResult(
            external_fiscal_identifier=f'fake-id-{request_fingerprint[:24]}',
            fiscal_document_type='INVOICE',
            fiscal_document_version='TEST-1',
            issued_at=datetime(2026, 1, 1, tzinfo=UTC),
            artifacts=(FiscalArtifactEvidence(
                artifact_kind='STAMPED_FISCAL_DOCUMENT',
                media_type='application/xml',
                storage_strategy='FAKE_PROVIDER_REFERENCE',
                storage_reference=f'fake://fiscal/{reference}',
                content_hash=hashlib.sha256(content).hexdigest(),
                byte_size=len(content),
                provider_artifact_reference=reference,
            ),),
        )

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
                fiscal_result=self._fiscal_result(request.request_fingerprint),
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
        if outcome in (
            FiscalIssuanceOutcome.SUCCEEDED,
            FiscalIssuanceOutcome.UNCERTAIN,
        ):
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
                fiscal_result=self._fiscal_result(request.request_fingerprint),
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
