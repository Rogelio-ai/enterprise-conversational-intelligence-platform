class DraftNotFoundError(LookupError):
    pass


class DraftContextError(ValueError):
    pass


class DraftNotMutableError(RuntimeError):
    pass


class DraftItemNotFoundError(LookupError):
    pass


class InvalidDraftQuantityError(ValueError):
    pass


class ProductNotOrderableError(RuntimeError):
    pass


class InvalidDraftCompositionError(RuntimeError):
    pass


class InvalidDraftSelectionError(ValueError):
    pass


class DraftConcurrencyConflictError(RuntimeError):
    pass
