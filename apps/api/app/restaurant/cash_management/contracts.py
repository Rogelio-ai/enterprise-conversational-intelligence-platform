from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CashSessionProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    cashier_membership_id: int
    currency: str
    status: str
    movement_version: int
    opened_at: datetime
    opened_by_actor_type: str
    opened_by_actor_id: int | None
    opened_by_actor_reference: str | None
