class RestaurantCheckError(RuntimeError):
    code = 'RESTAURANT_CHECK_ERROR'

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class CheckNotFoundError(RestaurantCheckError):
    code = 'CHECK_NOT_FOUND'


class NoEligibleConsumptionError(RestaurantCheckError):
    code = 'NO_ELIGIBLE_CONSUMPTION'


class DinerActiveCheckError(RestaurantCheckError):
    code = 'DINER_HAS_ACTIVE_CHECK'


class DinerAlreadyAssignedError(RestaurantCheckError):
    code = 'DINER_ALREADY_ASSIGNED_TO_ACTIVE_CHECK'


class DinerActiveDraftError(RestaurantCheckError):
    code = 'DINER_HAS_ACTIVE_ORDER_DRAFT'


class OrderingBlockedError(RestaurantCheckError):
    code = 'ORDERING_BLOCKED_BY_ACTIVE_CHECK'


class ConsumptionReservedError(RestaurantCheckError):
    code = 'CONSUMPTION_ALREADY_RESERVED'


class CrossLocationCheckError(RestaurantCheckError):
    code = 'CROSS_LOCATION_CHECK_NOT_ALLOWED'


class CheckNotModifiableError(RestaurantCheckError):
    code = 'CHECK_NOT_MODIFIABLE'


class CheckVersionConflictError(RestaurantCheckError):
    code = 'CHECK_VERSION_CONFLICT'


class CheckAllocationIncompleteError(RestaurantCheckError):
    code = 'CHECK_ALLOCATION_INCOMPLETE'


class CheckControllerTransferRequiredError(RestaurantCheckError):
    code = 'CHECK_CONTROLLER_TRANSFER_REQUIRED'


class CheckPermissionError(RestaurantCheckError):
    code = 'CHECK_PERMISSION_DENIED'


class CheckIdempotencyConflictError(RestaurantCheckError):
    code = 'CHECK_IDEMPOTENCY_CONFLICT'


class TableOutstandingBalanceError(RestaurantCheckError):
    code = 'TABLE_OUTSTANDING_BALANCE_NOT_ZERO'


class TableNotEligibleError(RestaurantCheckError):
    code = 'TABLE_NOT_ELIGIBLE_FOR_CLOSURE'
