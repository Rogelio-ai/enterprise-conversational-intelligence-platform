from __future__ import annotations

from collections.abc import Mapping

from app.restaurant.integrations.fiscal import errors
from app.restaurant.integrations.fiscal.ports import FiscalIssuancePort


class FiscalProviderRegistry:
    """Process-local provider lookup with no persistence or fallback selection."""

    def __init__(
        self, providers: Mapping[str, FiscalIssuancePort] | None = None
    ) -> None:
        self._providers: dict[str, FiscalIssuancePort] = {}
        for provider_key, provider in (providers or {}).items():
            self.register(provider_key, provider)

    def register(self, provider_key: str, provider: FiscalIssuancePort) -> None:
        key = self._key(provider_key)
        if key in self._providers:
            raise errors.DuplicateFiscalProviderRegistrationError(
                f'Fiscal provider {key!r} is already registered'
            )
        self._providers[key] = provider

    def resolve(self, provider_key: str) -> FiscalIssuancePort:
        key = self._key(provider_key)
        provider = self._providers.get(key)
        if provider is None:
            raise errors.FiscalProviderNotRegisteredError(
                f'Fiscal provider {key!r} is not registered'
            )
        return provider

    @staticmethod
    def _key(provider_key: str) -> str:
        if not isinstance(provider_key, str) or not provider_key.strip():
            raise errors.FiscalProviderNotRegisteredError(
                'Fiscal provider key is required'
            )
        return provider_key.strip()
