class CashManagementError(RuntimeError):
    code = 'CASH_MANAGEMENT_ERROR'

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class CashSessionNotFoundError(CashManagementError):
    code = 'CASH_SESSION_NOT_FOUND'


class CashRegisterNotFoundError(CashManagementError):
    code = 'CASH_REGISTER_NOT_FOUND'


class InvalidCashRegisterError(CashManagementError):
    code = 'INVALID_CASH_REGISTER'


class CashRegisterInactiveError(CashManagementError):
    code = 'CASH_REGISTER_INACTIVE'


class CashManagementNotActivatedError(CashManagementError):
    code = 'CASH_MANAGEMENT_NOT_ACTIVATED'


class ActiveCashSessionExistsError(CashManagementError):
    code = 'ACTIVE_CASH_SESSION_EXISTS'


class CashSessionIdempotencyConflictError(CashManagementError):
    code = 'CASH_SESSION_IDEMPOTENCY_CONFLICT'


class CashSessionConcurrencyConflictError(CashManagementError):
    code = 'CASH_SESSION_CONCURRENCY_CONFLICT'


class InvalidCashSessionRequestError(CashManagementError):
    code = 'INVALID_CASH_SESSION_REQUEST'


class CashSessionPermissionError(CashManagementError):
    code = 'CASH_SESSION_PERMISSION_DENIED'


class CashSessionClosedError(CashManagementError):
    code = 'CASH_SESSION_CLOSED'


class InvalidCashMovementError(CashManagementError):
    code = 'INVALID_CASH_MOVEMENT'


class DuplicateOpeningFloatError(CashManagementError):
    code = 'DUPLICATE_OPENING_FLOAT'


class CashMovementIdempotencyConflictError(CashManagementError):
    code = 'CASH_MOVEMENT_IDEMPOTENCY_CONFLICT'


class InvalidCashCountError(CashManagementError):
    code = 'INVALID_CASH_COUNT'


class CashCountNotFoundError(CashManagementError):
    code = 'CASH_COUNT_NOT_FOUND'


class CashCountSessionConflictError(CashManagementError):
    code = 'CASH_COUNT_SESSION_CONFLICT'


class CashCountIdempotencyConflictError(CashManagementError):
    code = 'CASH_COUNT_IDEMPOTENCY_CONFLICT'


class StaleCashCountError(CashManagementError):
    code = 'STALE_CASH_COUNT'


class CashSessionCloseConflictError(CashManagementError):
    code = 'CASH_SESSION_CLOSE_CONFLICT'


class CashSessionCloseIdempotencyConflictError(CashManagementError):
    code = 'CASH_SESSION_CLOSE_IDEMPOTENCY_CONFLICT'


class CashSessionVarianceReasonRequiredError(CashManagementError):
    code = 'CASH_SESSION_VARIANCE_REASON_REQUIRED'
