from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class InitiateFiscalIssuanceCommand:
    organization_id: int
    location_id: int
    billing_document_id: int
    provider_key: str
    credential_binding: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RecoverFiscalIssuanceCommand:
    organization_id: int
    location_id: int
    billing_issuance_id: int


@dataclass(frozen=True, slots=True)
class RetryFiscalIssuanceCommand:
    organization_id: int
    location_id: int
    billing_issuance_id: int


@dataclass(frozen=True, slots=True)
class BillingIssuanceAttemptProjection:
    sequence: int
    attempt_type: str
    started_at: datetime
    completed_at: datetime | None
    result: str | None
    external_reference: str | None
    external_status: str | None
    error_kind: str | None
    error_message: str | None
    result_fingerprint: str | None
    actor_type: str | None
    actor_id: int | None
    actor_reference: str | None
    correlation_id: str | None


@dataclass(frozen=True, slots=True)
class BillingIssuanceProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    billing_document_id: int
    provider_key: str
    state: str
    idempotency_key: str
    request_schema_version: int
    request_fingerprint: str
    provider_idempotency_key: str
    external_reference: str | None
    external_status: str | None
    attempt_count: int
    last_error_kind: str | None
    last_error_message: str | None
    requested_at: datetime
    completed_at: datetime | None
    attempts: tuple[BillingIssuanceAttemptProjection, ...]
