from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import Field

from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalContractValue,
)


class FiscalProviderCredentialBinding(FiscalContractValue):
    """Durable, non-secret locator for the original provider account binding."""

    tenant_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    provider_key: str = Field(min_length=1, max_length=128)
    credential_binding: str = Field(min_length=1, max_length=200)
    operation_reference: str = Field(min_length=1, max_length=200)


@runtime_checkable
class FiscalProviderCredentialResolver(Protocol):
    async def resolve(
        self, *, binding: FiscalProviderCredentialBinding
    ) -> EphemeralFiscalProviderCredential: ...
