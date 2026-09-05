class FiscalIssuanceError(RuntimeError):
    code = 'FISCAL_ISSUANCE_ERROR'

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class FiscalIssuanceRequestInvalidError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_REQUEST_INVALID'


class FiscalBillingDocumentNotFoundError(FiscalIssuanceError):
    code = 'FISCAL_BILLING_DOCUMENT_NOT_FOUND'


class FiscalIssuanceNotFoundError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_NOT_FOUND'


class FiscalCanonicalEvidenceInvalidError(FiscalIssuanceError):
    code = 'FISCAL_CANONICAL_EVIDENCE_INVALID'


class FiscalIssuanceIdempotencyConflictError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_IDEMPOTENCY_CONFLICT'


class FiscalIssuanceStateConflictError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_STATE_CONFLICT'


class FiscalIssuanceConcurrencyConflictError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_CONCURRENCY_CONFLICT'


class FiscalProviderUnavailableError(FiscalIssuanceError):
    code = 'FISCAL_PROVIDER_UNAVAILABLE'


class FiscalCredentialResolutionError(FiscalIssuanceError):
    code = 'FISCAL_CREDENTIAL_RESOLUTION_FAILED'


class FiscalIssuanceRecoveryNotAllowedError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_RECOVERY_NOT_ALLOWED'


class FiscalIssuanceRetryNotAllowedError(FiscalIssuanceError):
    code = 'FISCAL_ISSUANCE_RETRY_NOT_ALLOWED'


class FiscalIssuanceStaleFenceError(FiscalIssuanceConcurrencyConflictError):
    code = 'FISCAL_ISSUANCE_STALE_FENCE'


class FiscalProviderBindingMismatchError(FiscalIssuanceError):
    code = 'FISCAL_PROVIDER_BINDING_MISMATCH'


class FiscalRecoveryInconclusiveError(FiscalIssuanceError):
    code = 'FISCAL_RECOVERY_INCONCLUSIVE'
