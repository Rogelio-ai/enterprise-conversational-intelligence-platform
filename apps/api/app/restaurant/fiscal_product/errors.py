class FiscalProductEvidenceError(RuntimeError):
    pass


class FiscalProductScopeError(FiscalProductEvidenceError):
    pass


class FiscalProductEvidenceUnavailableError(FiscalProductEvidenceError):
    pass


class FiscalProductEvidenceAmbiguousError(FiscalProductEvidenceError):
    pass
