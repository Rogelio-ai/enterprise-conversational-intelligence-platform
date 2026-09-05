class RestaurantBillingError(RuntimeError):
    code = 'RESTAURANT_BILLING_ERROR'

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class BillingRequestInvalidError(RestaurantBillingError):
    code = 'BILLING_REQUEST_INVALID'


class BillingDocumentNotFoundError(RestaurantBillingError):
    code = 'BILLING_DOCUMENT_NOT_FOUND'


class BillingCheckNotSettledError(RestaurantBillingError):
    code = 'BILLING_CHECK_NOT_SETTLED'


class BillingSourceNotEligibleError(RestaurantBillingError):
    code = 'BILLING_SOURCE_NOT_ELIGIBLE'


class BillingIssuerProfileMissingError(RestaurantBillingError):
    code = 'BILLING_ISSUER_PROFILE_MISSING'


class BillingRecipientInvalidError(RestaurantBillingError):
    code = 'BILLING_RECIPIENT_INVALID'


class BillingTaxEvidenceUnavailableError(RestaurantBillingError):
    code = 'BILLING_TAX_EVIDENCE_UNAVAILABLE'


class BillingFiscalEvidenceUnavailableError(RestaurantBillingError):
    code = 'BILLING_FISCAL_EVIDENCE_UNAVAILABLE'


class BillingFiscalArithmeticError(RestaurantBillingError):
    code = 'BILLING_FISCAL_ARITHMETIC_INCONSISTENT'


class BillingUnsupportedFiscalComponentError(RestaurantBillingError):
    code = 'BILLING_UNSUPPORTED_FISCAL_COMPONENT'


class BillingIdempotencyConflictError(RestaurantBillingError):
    code = 'BILLING_IDEMPOTENCY_CONFLICT'


class BillingConcurrencyConflictError(RestaurantBillingError):
    code = 'BILLING_CONCURRENCY_CONFLICT'
