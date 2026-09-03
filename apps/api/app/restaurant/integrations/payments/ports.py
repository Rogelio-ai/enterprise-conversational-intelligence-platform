from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
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
        merchant_credential: EphemeralMerchantCredential | None,
        customer_payment_source: EphemeralCustomerPaymentSource | None,
    ) -> PaymentExecutionResult: ...


@runtime_checkable
class PaymentRecoveryPort(Protocol):
    async def recover(
        self,
        *,
        request: PaymentRecoveryRequest,
        merchant_credential: EphemeralMerchantCredential | None,
    ) -> PaymentRecoveryResult: ...
