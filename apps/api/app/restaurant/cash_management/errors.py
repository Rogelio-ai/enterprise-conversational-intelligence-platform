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
