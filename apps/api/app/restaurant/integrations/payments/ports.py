from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.restaurant.integrations.payments.contracts import (
    EphemeralExecutionCredential,
    PaymentExecutionRequest,
    PaymentExecutionResult,
    PaymentRecoveryRequest,
    PaymentRecoveryResult,
)


@runtime_checkable
class PaymentExecutionPort(Protocol):
    async def execute(
        self,
        *,
        request: PaymentExecutionRequest,
        credential: EphemeralExecutionCredential,
    ) -> PaymentExecutionResult: ...


@runtime_checkable
class PaymentRecoveryPort(Protocol):
    async def recover(self, *, request: PaymentRecoveryRequest) -> PaymentRecoveryResult: ...
