from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActorType(StrEnum):
    EMPLOYEE = 'EMPLOYEE'
    DINER = 'DINER'
    SYSTEM = 'SYSTEM'
    AGENT = 'AGENT'
    EXTERNAL_SYSTEM = 'EXTERNAL_SYSTEM'


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Trusted actor context resolved by an authenticated application boundary."""

    actor_type: ActorType
    tenant_id: int
    principal_id: int | None
    principal_reference: str | None
    correlation_id: str | None
    causation_id: str | None = None

    def __post_init__(self) -> None:
        if self.tenant_id <= 0:
            raise ValueError('ExecutionContext tenant_id must be positive')
        if self.actor_type in (ActorType.EMPLOYEE, ActorType.DINER):
            if self.principal_id is None or self.principal_id <= 0:
                raise ValueError('Human ExecutionContext requires a positive principal_id')
            if self.principal_reference is not None:
                raise ValueError('Human ExecutionContext cannot use principal_reference')
        elif not self.principal_reference or not self.principal_reference.strip():
            raise ValueError('Non-human ExecutionContext requires principal_reference')
