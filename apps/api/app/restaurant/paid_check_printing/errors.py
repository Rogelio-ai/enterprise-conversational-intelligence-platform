class PaidCheckPrintingError(Exception):
    code = 'PAID_CHECK_PRINT_ERROR'


class PaidCheckDispatchNotFoundError(PaidCheckPrintingError, LookupError):
    code = 'PAID_CHECK_DISPATCH_NOT_FOUND'


class PaidCheckNotSettledError(PaidCheckPrintingError):
    code = 'PAID_CHECK_NOT_SETTLED'


class PaidCheckTargetError(PaidCheckPrintingError):
    code = 'PAID_CHECK_TARGET_INVALID'


class PaidCheckIdempotencyConflictError(PaidCheckPrintingError):
    code = 'PAID_CHECK_PRINT_IDEMPOTENCY_CONFLICT'


class PaidCheckDeliveryConflictError(PaidCheckPrintingError):
    code = 'PAID_CHECK_DELIVERY_CONFLICT'
