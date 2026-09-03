from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PaymentAttemptProjection:
    sequence: int
    attempt_type: str
    executor_key: str
    actor_type: str
    actor_id: int | None
    correlation_id: str | None
    started_at: datetime
    external_call_started_at: datetime | None
    completed_at: datetime | None
    result: str
    external_reference: str | None
    external_status: str | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class PaymentProjection:
    id: int
    check_id: int
    check_version: int
    check_fingerprint: str
    amount: Decimal
    currency: str
    method_category: str
    payer_type: str
    payer_diner_session_id: int | None
    payer_reference: str | None
    state: str
    executor_key: str | None
    external_reference: str | None
    external_status: str | None
    instrument_brand: str | None
    instrument_last_four: str | None
    instrument_display: str | None
    cash_tendered_amount: Decimal | None
    cash_change_due: Decimal | None
    terminal_at: datetime | None
    attempts: tuple[PaymentAttemptProjection, ...]


@dataclass(frozen=True)
class CheckSettlementProjection:
    check_id: int
    check_status: str
    check_version: int
    check_fingerprint: str
    liability_total: Decimal
    currency: str
    confirmed_settlement: Decimal
    reserved_financial_exposure: Decimal
    uncertain_exposure: Decimal
    available_to_initiate: Decimal
    payments: tuple[PaymentProjection, ...]
