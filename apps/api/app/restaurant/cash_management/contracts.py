from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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
    expected_cash: Decimal
    opened_at: datetime
    opened_by_actor_type: str
    opened_by_actor_id: int | None
    opened_by_actor_reference: str | None
    selected_cash_count_id: int | None
    final_movement_version: int | None
    frozen_expected_cash: Decimal | None
    frozen_variance: Decimal | None
    variance_reason: str | None
    closed_at: datetime | None
    closed_by_actor_type: str | None
    closed_by_actor_id: int | None
    closed_by_actor_reference: str | None


@dataclass(frozen=True)
class CashMovementProjection:
    id: int
    cash_session_id: int
    movement_type: str
    amount: Decimal
    currency: str
    reason: str | None
    reference: str | None
    recorded_at: datetime
    actor_type: str
    actor_id: int | None
    actor_reference: str | None
    authorized_by_actor_type: str
    authorized_by_actor_id: int | None
    authorized_by_actor_reference: str | None


@dataclass(frozen=True)
class CashCountProjection:
    id: int
    cash_session_id: int
    counted_amount: Decimal
    currency: str
    captured_movement_version: int
    counted_at: datetime
    actor_type: str
    actor_id: int | None
    actor_reference: str | None
