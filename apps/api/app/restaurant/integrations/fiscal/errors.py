class FiscalProviderRegistryError(RuntimeError):
    """Safe process-local registry failure."""


class DuplicateFiscalProviderRegistrationError(FiscalProviderRegistryError):
    pass


class FiscalProviderNotRegisteredError(FiscalProviderRegistryError):
    pass


class FiscalProviderCredentialResolutionError(RuntimeError):
    """Safe credential-boundary failure that never includes secret material."""

    def __init__(self) -> None:
        super().__init__('Fiscal provider credential is unavailable')
