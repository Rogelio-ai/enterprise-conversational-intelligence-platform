class DraftNotConfirmableError(RuntimeError):
    pass


class TaxEvidenceUnavailableError(DraftNotConfirmableError):
    pass


class FiscalProductEvidenceUnavailableError(DraftNotConfirmableError):
    pass


class ConfirmationStaleError(RuntimeError):
    pass


class OrderAlreadyConfirmedError(RuntimeError):
    pass


class ConfirmationConflictError(RuntimeError):
    pass


class RestaurantOrderNotFoundError(LookupError):
    pass
