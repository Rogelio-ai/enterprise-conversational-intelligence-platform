from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DispatchAttemptProjection:
    id: int
    attempt_sequence: int
    attempt_type: str
    connector_id: int
    actor_type: str
    actor_membership_id: int | None
    actor_principal_reference: str | None
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    result: str
    result_fingerprint: str | None
    local_job_reference: str | None
    error_kind: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class DispatchProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    restaurant_order_id: int
    preparation_work_id: int
    preparation_area_id: int
    destination_id: int
    operation_kind: str
    generation: int
    operation_id: str
    reprint_of_dispatch_id: int | None
    state: str
    payload_schema: str
    payload_text: str
    payload_fingerprint: str
    destination_code: str
    destination_name: str
    destination_channel: str
    connector_id: int
    connector_code: str
    connector_name: str
    local_target_key: str
    claim_expires_at: datetime | None
    attempt_count: int
    available_at: datetime
    last_error_kind: str | None
    last_error_message: str | None
    initiating_actor_type: str
    initiating_membership_id: int | None
    initiating_principal_reference: str | None
    correlation_id: str | None
    causation_id: str | None
    terminal_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: tuple[DispatchAttemptProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaimResult:
    dispatch: DispatchProjection
    attempt: DispatchAttemptProjection
    claim_token: str


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    result: str
    result_fingerprint: str
    local_job_reference: str | None = None
    error_kind: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RecordResultOutcome:
    dispatch: DispatchProjection
    attempt: DispatchAttemptProjection
    replayed: bool
