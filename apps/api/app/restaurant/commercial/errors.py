class CommercialResolutionError(RuntimeError):
    pass


class DraftNotCommerciallyReadyError(CommercialResolutionError):
    pass


class PriceUnavailableError(CommercialResolutionError):
    pass


class CurrencyConflictError(CommercialResolutionError):
    pass


class UnsupportedPromotionSemanticsError(CommercialResolutionError):
    pass
