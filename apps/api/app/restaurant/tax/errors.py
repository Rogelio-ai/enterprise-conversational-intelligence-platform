class RestaurantTaxError(RuntimeError):
    """Base error for authoritative Restaurant tax resolution."""


class TaxClassificationUnavailableError(RestaurantTaxError):
    pass


class TaxRuleUnavailableError(RestaurantTaxError):
    pass


class TaxRuleAmbiguousError(RestaurantTaxError):
    pass


class TaxPolicyUnsupportedError(RestaurantTaxError):
    pass


class TaxTreatmentUnsupportedError(RestaurantTaxError):
    pass


class TaxCalculationError(RestaurantTaxError):
    pass


class TaxScopeViolationError(RestaurantTaxError):
    pass
