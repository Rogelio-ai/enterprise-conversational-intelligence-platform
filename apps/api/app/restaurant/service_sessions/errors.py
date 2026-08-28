class RestaurantServiceError(RuntimeError):
    pass


class ServiceContextError(RestaurantServiceError):
    pass


class ResourceAlreadyOccupiedError(RestaurantServiceError):
    pass


class ServiceSessionNotFoundError(RestaurantServiceError):
    pass


class ServiceSessionClosedError(RestaurantServiceError):
    pass


class PartySizeConflictError(RestaurantServiceError):
    pass


class InvalidJoinError(RestaurantServiceError):
    pass


class JoinLockedError(InvalidJoinError):
    def __init__(self, retry_after: int):
        super().__init__('Diner join is temporarily unavailable')
        self.retry_after = retry_after


class CapacityConflictError(RestaurantServiceError):
    pass


class DuplicateDinerIdentityError(RestaurantServiceError):
    pass


class DinerAuthorizationError(RestaurantServiceError):
    pass
