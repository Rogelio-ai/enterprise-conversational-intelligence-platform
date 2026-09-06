class RestaurantPaymentError(RuntimeError):
    code = 'RESTAURANT_PAYMENT_ERROR'

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class PaymentNotFoundError(RestaurantPaymentError):
    code = 'PAYMENT_NOT_FOUND'


class PaymentPermissionError(RestaurantPaymentError):
    code = 'PAYMENT_PERMISSION_DENIED'


class PaymentIdempotencyConflictError(RestaurantPaymentError):
    code = 'PAYMENT_IDEMPOTENCY_CONFLICT'


class CheckNotPayableError(RestaurantPaymentError):
    code = 'CHECK_NOT_PAYABLE'


class CheckFinancialIdentityConflictError(RestaurantPaymentError):
    code = 'CHECK_FINANCIAL_IDENTITY_CONFLICT'


class PaymentAmountExceedsAvailableError(RestaurantPaymentError):
    code = 'PAYMENT_AMOUNT_EXCEEDS_AVAILABLE_LIABILITY'


class InvalidPaymentAmountError(RestaurantPaymentError):
    code = 'INVALID_PAYMENT_AMOUNT'


class InvalidCashTenderError(RestaurantPaymentError):
    code = 'INVALID_CASH_TENDER'


class CashSessionRequiredError(RestaurantPaymentError):
    code = 'CASH_SESSION_REQUIRED'


class CashSessionNotFoundError(RestaurantPaymentError):
    code = 'CASH_SESSION_NOT_FOUND'


class InvalidCashSessionError(RestaurantPaymentError):
    code = 'INVALID_CASH_SESSION'


class PaymentStateConflictError(RestaurantPaymentError):
    code = 'PAYMENT_STATE_CONFLICT'


class PaymentRecoveryRequiredError(RestaurantPaymentError):
    code = 'PAYMENT_RECOVERY_REQUIRED'


class PaymentStaleResultError(RestaurantPaymentError):
    code = 'PAYMENT_STALE_RESULT'


class PaymentConcurrencyConflictError(RestaurantPaymentError):
    code = 'PAYMENT_CONCURRENCY_CONFLICT'


class DuplicateSettlementError(RestaurantPaymentError):
    code = 'DUPLICATE_PAYMENT_SETTLEMENT'


class UnsupportedExecutionCapabilityError(RestaurantPaymentError):
    code = 'PAYMENT_EXECUTION_UNSUPPORTED'


class RecoveryUnavailableError(RestaurantPaymentError):
    code = 'PAYMENT_RECOVERY_UNAVAILABLE'


class SensitiveCredentialMisuseError(RestaurantPaymentError):
    code = 'SENSITIVE_PAYMENT_CREDENTIAL_MISUSE'


class PaymentExecutorRegistryError(RestaurantPaymentError):
    code = 'PAYMENT_EXECUTOR_REGISTRY_ERROR'


class DuplicatePaymentExecutorRegistrationError(PaymentExecutorRegistryError):
    code = 'PAYMENT_EXECUTOR_DUPLICATE_REGISTRATION'


class PaymentExecutorAdapterNotRegisteredError(PaymentExecutorRegistryError):
    code = 'PAYMENT_EXECUTOR_ADAPTER_NOT_REGISTERED'


class PaymentExecutorResolutionError(RestaurantPaymentError):
    code = 'PAYMENT_EXECUTOR_RESOLUTION_ERROR'


class InvalidPaymentExecutorSelectionError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_SELECTION_INVALID'


class PaymentExecutorConfigurationNotFoundError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_CONFIGURATION_NOT_FOUND'


class PaymentExecutorConfigurationInactiveError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_CONFIGURATION_INACTIVE'


class UnsupportedPaymentExecutorMethodError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_METHOD_UNSUPPORTED'


class UnsupportedPaymentExecutorCurrencyError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_CURRENCY_UNSUPPORTED'


class UnsupportedPaymentExecutorCapabilityError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_CAPABILITY_UNSUPPORTED'


class NoEligiblePaymentExecutorError(PaymentExecutorResolutionError):
    code = 'PAYMENT_EXECUTOR_NOT_ELIGIBLE'


class MerchantCredentialResolutionError(RestaurantPaymentError):
    code = 'MERCHANT_CREDENTIAL_RESOLUTION_ERROR'
