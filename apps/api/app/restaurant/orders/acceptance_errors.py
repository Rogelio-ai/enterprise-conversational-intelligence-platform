class DraftNotConfirmableError(RuntimeError):
    pass


class ConfirmationStaleError(RuntimeError):
    pass


class OrderAlreadyConfirmedError(RuntimeError):
    pass


class ConfirmationConflictError(RuntimeError):
    pass


class RestaurantOrderNotFoundError(LookupError):
    pass
