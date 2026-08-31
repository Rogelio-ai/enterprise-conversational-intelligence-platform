class PreparationDeliveryError(Exception):
    """Base preparation delivery error."""


class PreparationDeliveryNotFoundError(PreparationDeliveryError, LookupError):
    pass


class PreparationDeliveryConflictError(PreparationDeliveryError):
    pass


class PreparationDeliveryConfigurationError(PreparationDeliveryError):
    pass
