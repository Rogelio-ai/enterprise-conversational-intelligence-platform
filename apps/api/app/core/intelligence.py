from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrustedIntelligenceContext:
    """Trusted scalar scope constructed from authenticated canonical state."""

    tenant_id: int
    organization_id: int
    location_id: int | None
    resource_id: int | None
    conversation_id: int
    source_message_id: int
    participant_id: int
    correlation_id: str

    def __post_init__(self) -> None:
        required_ids = (
            self.tenant_id,
            self.organization_id,
            self.conversation_id,
            self.source_message_id,
            self.participant_id,
        )
        if any(value <= 0 for value in required_ids):
            raise ValueError('Trusted intelligence identifiers must be positive')
        if self.location_id is not None and self.location_id <= 0:
            raise ValueError('Trusted Location identifier must be positive')
        if self.resource_id is not None and self.resource_id <= 0:
            raise ValueError('Trusted Resource identifier must be positive')
        if self.resource_id is not None and self.location_id is None:
            raise ValueError('Trusted Resource context requires Location context')
        correlation_id = self.correlation_id.strip()
        if not correlation_id or len(correlation_id) > 128:
            raise ValueError('A valid correlation identifier is required')
        object.__setattr__(self, 'correlation_id', correlation_id)
