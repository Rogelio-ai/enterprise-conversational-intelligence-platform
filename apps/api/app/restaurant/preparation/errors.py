class PreparationNotFoundError(LookupError):
    pass


class PreparationConflictError(RuntimeError):
    pass


class PreparationOwnershipError(PreparationConflictError):
    pass


class PreparationTransitionError(PreparationConflictError):
    pass


class PreparationStaleError(PreparationConflictError):
    pass


class PreparationIdempotencyError(PreparationConflictError):
    pass
