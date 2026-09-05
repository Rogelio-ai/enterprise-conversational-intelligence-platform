from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import Field

from app.restaurant.integrations.fiscal.contracts import FiscalContractValue


class FiscalArtifactStorageRequest(FiscalContractValue):
    tenant_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    billing_issuance_id: int = Field(gt=0)
    external_fiscal_identifier: str = Field(min_length=1, max_length=200)
    artifact_kind: str = Field(min_length=1, max_length=64)
    media_type: str = Field(min_length=1, max_length=128)
    content: bytes = Field(min_length=1)
    content_hash: str = Field(
        min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    byte_size: int = Field(gt=0)


class FiscalArtifactStorageReceipt(FiscalContractValue):
    storage_strategy: str = Field(min_length=1, max_length=64)
    storage_reference: str = Field(min_length=1, max_length=500)
    content_hash: str = Field(
        min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    byte_size: int = Field(gt=0)


@runtime_checkable
class FiscalArtifactStoragePort(Protocol):
    async def store(
        self, *, request: FiscalArtifactStorageRequest
    ) -> FiscalArtifactStorageReceipt: ...
