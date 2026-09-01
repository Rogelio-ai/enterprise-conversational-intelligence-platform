from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class CheckOrderLine:
    order_id: int
    diner_session_id: int
    service_session_id: int
    resource_id: int
    accepted_at: datetime
    accepted_payable_amount: Decimal
    accepted_commercial_fingerprint: str
    items: tuple[dict, ...]


@dataclass(frozen=True)
class CheckDinerGroup:
    diner_session_id: int
    display_name: str
    orders: tuple[CheckOrderLine, ...]


@dataclass(frozen=True)
class CheckResourceGroup:
    resource_id: int
    service_session_id: int
    diners: tuple[CheckDinerGroup, ...]


@dataclass(frozen=True)
class CheckProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    status: str
    version: int
    fingerprint: str
    currency: str
    controller_diner_session_id: int | None
    member_ids: tuple[int, ...]
    consumption_total: Decimal
    gratuity_total: Decimal
    liability_total: Decimal
    confirmed_settlement: Decimal
    outstanding: Decimal
    uncertain_exposure: Decimal
    frozen_at: datetime | None
    cancelled_at: datetime | None
    details: tuple[CheckResourceGroup, ...] | None
    signal: str | None = None


@dataclass(frozen=True)
class EligibleDinerConsumption:
    diner_session_id: int
    service_session_id: int
    resource_id: int
    display_name: str
    eligible_order_ids: tuple[int, ...]
    eligible_total: Decimal
    currency: str | None
    active_check_id: int | None
    has_active_nonempty_draft: bool


@dataclass(frozen=True)
class TableBalanceProjection:
    service_session_id: int
    resource_id: int
    currency: str | None
    accepted_consumption: Decimal
    reserved_in_active_checks: Decimal
    unreserved_unsettled_consumption: Decimal
    settled_consumption: Decimal
    pending_exposure: Decimal
    uncertain_exposure: Decimal
    outstanding_confirmed_balance: Decimal
    unresolved_active_checks: int
    closure_eligible: bool
    service_continuation_decision_required: bool
