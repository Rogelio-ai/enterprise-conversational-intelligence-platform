from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.restaurant.preparation_delivery.contracts import DeliveryResult


@dataclass(frozen=True, slots=True)
class PreparationDeliveryRequest:
    dispatch_id: int
    operation_id: str
    destination_code: str
    local_target_key: str
    payload_schema: str
    payload_text: str
    payload_fingerprint: str
    correlation_id: str | None


@runtime_checkable
class PreparationDeliveryPort(Protocol):
    async def deliver(self, request: PreparationDeliveryRequest) -> DeliveryResult: ...
