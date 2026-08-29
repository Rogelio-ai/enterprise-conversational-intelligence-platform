from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PosSubmissionAttemptProjection:
    sequence: int
    attempt_type: str
    actor_type: str
    actor_membership_id: int | None
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    result: str
    error_kind: str | None
    error_message: str | None
    external_order_id: str | None


@dataclass(frozen=True, slots=True)
class PosSubmissionProjection:
    id: int
    restaurant_order_id: int
    connector_key: str
    external_location_id: str
    state: str
    idempotency_key: str
    request_fingerprint: str
    external_order_id: str | None
    external_status: str | None
    claim_expires_at: datetime | None
    last_error_kind: str | None
    last_error_message: str | None
    attempts: tuple[PosSubmissionAttemptProjection, ...]
