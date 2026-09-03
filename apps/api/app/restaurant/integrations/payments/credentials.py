from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.restaurant.integrations.payments.contracts import EphemeralMerchantCredential
from app.restaurant.payments import errors


@dataclass(frozen=True)
class MerchantCredentialContext:
    tenant_id: int
    organization_id: int
    location_id: int
    executor_configuration_id: int
    adapter_kind: str
    credential_binding: str
    operation_reference: str


@runtime_checkable
class MerchantCredentialResolver(Protocol):
    async def resolve(
        self, *, context: MerchantCredentialContext
    ) -> EphemeralMerchantCredential: ...


class DeterministicMerchantCredentialResolver:
    """Explicit in-memory test boundary; not a production secret backend."""

    def __init__(self, credentials: dict[str, str]) -> None:
        self._credentials = dict(credentials)
        self.calls: list[MerchantCredentialContext] = []

    async def resolve(
        self, *, context: MerchantCredentialContext
    ) -> EphemeralMerchantCredential:
        self.calls.append(context)
        value = self._credentials.get(context.credential_binding)
        if value is None:
            raise errors.MerchantCredentialResolutionError(
                'Merchant credential is unavailable for the selected executor configuration'
            )
        return EphemeralMerchantCredential(value=value)
