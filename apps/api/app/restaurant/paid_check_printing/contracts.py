from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PaidCheckAttemptProjection:
    id: int
    attempt_sequence: int
    attempt_type: str
    connector_id: int
    claim_request_id: str | None
    actor_principal_reference: str
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    result: str
    result_fingerprint: str | None
    local_job_reference: str | None
    error_kind: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class PaidCheckDispatchProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    restaurant_check_id: int
    check_version: int
    check_fingerprint: str
    cashier_resource_id: int
    cashier_resource_code: str
    cashier_resource_name: str
    connector_id: int
    connector_code: str
    connector_name: str
    local_target_key: str
    operation_id: str
    state: str
    payload_schema: str
    payload_text: str
    payload_fingerprint: str
    claim_expires_at: datetime | None
    attempt_count: int
    available_at: datetime
    last_error_kind: str | None
    last_error_message: str | None
    created_by_membership_id: int
    correlation_id: str | None
    terminal_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: tuple[PaidCheckAttemptProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class PaidCheckClaimResult:
    dispatch: PaidCheckDispatchProjection
    attempt: PaidCheckAttemptProjection
    claim_token: str


@dataclass(frozen=True, slots=True)
class PaidCheckRecordResult:
    dispatch: PaidCheckDispatchProjection
    attempt: PaidCheckAttemptProjection
    replayed: bool
