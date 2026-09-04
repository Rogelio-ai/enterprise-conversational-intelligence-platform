from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalIssuanceResult,
    FiscalRecoveryResult,
)


@runtime_checkable
class FiscalIssuancePort(Protocol):
    async def issue(
        self,
        *,
        request: FiscalIssuanceRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalIssuanceResult: ...

    async def recover(
        self,
        *,
        request: FiscalIssuanceRecoveryRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalRecoveryResult: ...
