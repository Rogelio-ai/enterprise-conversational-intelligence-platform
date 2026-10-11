"""Organization/Location lifecycle operations with caller-owned transactions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Organization, OrganizationHeadquartersChange


class OrganizationLocationConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HeadquartersChangeResult:
    organization: Organization
    previous_location_id: int | None
    new_location_id: int


async def assign_headquarters_in_transaction(
    db: AsyncSession,
    *,
    organization: Organization,
    location_id: int,
    actor_membership_id: int,
    operation_id: str,
    deactivate_previous: bool = False,
) -> HeadquartersChangeResult:
    """Assign headquarters after the caller locks the owning Organization."""
    previous_location_id = organization.headquarters_location_id
    location_ids = tuple(sorted({
        value for value in (previous_location_id, location_id) if value is not None
    }))
    locations = tuple((await db.scalars(
        select(Location)
        .where(
            Location.id.in_(location_ids),
            Location.tenant_id == organization.tenant_id,
            Location.organization_id == organization.id,
        )
        .order_by(Location.id)
        .with_for_update()
    )).all())
    by_id = {value.id: value for value in locations}
    target = by_id.get(location_id)
    if target is None:
        raise OrganizationLocationConflictError(
            'Headquarters Location is outside the Organization scope'
        )
    if target.status != 'ACTIVE':
        raise OrganizationLocationConflictError('Headquarters Location must be active')
    if previous_location_id == location_id:
        if deactivate_previous:
            raise OrganizationLocationConflictError(
                'Current headquarters cannot be deactivated without a replacement'
            )
        return HeadquartersChangeResult(
            organization=organization,
            previous_location_id=previous_location_id,
            new_location_id=location_id,
        )
    if previous_location_id is not None and previous_location_id not in by_id:
        raise OrganizationLocationConflictError(
            'Current headquarters is outside the Organization scope'
        )

    organization.headquarters_location_id = location_id
    if deactivate_previous and previous_location_id is not None:
        by_id[previous_location_id].status = 'INACTIVE'
    db.add(OrganizationHeadquartersChange(
        tenant_id=organization.tenant_id,
        organization_id=organization.id,
        previous_location_id=previous_location_id,
        new_location_id=location_id,
        actor_membership_id=actor_membership_id,
        operation_id=operation_id,
    ))
    await db.flush()
    return HeadquartersChangeResult(
        organization=organization,
        previous_location_id=previous_location_id,
        new_location_id=location_id,
    )


async def validate_organization_activation(
    db: AsyncSession, *, organization: Organization,
) -> None:
    """Reject activation unless the owned headquarters reference is valid and active."""
    if organization.headquarters_location_id is None:
        raise OrganizationLocationConflictError(
            'Organization requires an active headquarters before activation'
        )
    headquarters = await db.scalar(
        select(Location)
        .where(
            Location.id == organization.headquarters_location_id,
            Location.tenant_id == organization.tenant_id,
            Location.organization_id == organization.id,
        )
        .with_for_update()
    )
    if headquarters is None or headquarters.status != 'ACTIVE':
        raise OrganizationLocationConflictError(
            'Organization requires an active headquarters before activation'
        )
