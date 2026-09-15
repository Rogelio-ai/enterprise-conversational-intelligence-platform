"""Canonical Location Preparation Configuration provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, LocationPreparationConfiguration


PREPARATION_OWNERS = frozenset({'PLATFORM', 'EXTERNAL_POS'})


class PreparationConfigurationProvisioningError(ValueError):
    pass


class PreparationConfigurationScopeNotFoundError(
    PreparationConfigurationProvisioningError
):
    pass


class PreparationConfigurationConflictError(
    PreparationConfigurationProvisioningError
):
    pass


@dataclass(frozen=True, slots=True)
class PreparationConfigurationProvisioningPlan:
    operation: str
    configuration_id: int | None


@dataclass(frozen=True, slots=True)
class PreparationConfigurationProvisioningResult:
    configuration: LocationPreparationConfiguration
    operation: str


def _owner(value: str) -> str:
    if not isinstance(value, str):
        raise PreparationConfigurationProvisioningError(
            'Invalid Preparation Configuration owner'
        )
    normalized = value.strip().upper()
    if normalized not in PREPARATION_OWNERS:
        raise PreparationConfigurationProvisioningError(
            'Unsupported Preparation Configuration owner'
        )
    return normalized


async def _location(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, for_update: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    location = await db.scalar(statement)
    if location is None:
        raise PreparationConfigurationScopeNotFoundError('Location not found')
    return location


async def resolve_configuration(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, for_update: bool = False,
) -> LocationPreparationConfiguration:
    statement = select(LocationPreparationConfiguration).where(
        LocationPreparationConfiguration.tenant_id == tenant_id,
        LocationPreparationConfiguration.organization_id == organization_id,
        LocationPreparationConfiguration.location_id == location_id,
    )
    if for_update:
        statement = statement.with_for_update()
    configuration = await db.scalar(statement)
    if configuration is None:
        raise PreparationConfigurationScopeNotFoundError(
            'Location Preparation Configuration not found'
        )
    return configuration


async def plan_configuration(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, preparation_owner: str,
) -> PreparationConfigurationProvisioningPlan:
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    owner = _owner(preparation_owner)
    configuration = await db.scalar(select(LocationPreparationConfiguration).where(
        LocationPreparationConfiguration.tenant_id == tenant_id,
        LocationPreparationConfiguration.organization_id == organization_id,
        LocationPreparationConfiguration.location_id == location_id,
    ))
    if configuration is None:
        return PreparationConfigurationProvisioningPlan('CREATE', None)
    operation = (
        'UNCHANGED' if configuration.preparation_owner == owner else 'UPDATE'
    )
    return PreparationConfigurationProvisioningPlan(operation, configuration.id)


async def provision_configuration(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, preparation_owner: str,
) -> PreparationConfigurationProvisioningResult:
    owner = _owner(preparation_owner)
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, for_update=True,
    )
    configuration = await db.scalar(select(LocationPreparationConfiguration).where(
        LocationPreparationConfiguration.tenant_id == tenant_id,
        LocationPreparationConfiguration.organization_id == organization_id,
        LocationPreparationConfiguration.location_id == location_id,
    ).with_for_update())
    if configuration is None:
        operation = 'CREATE'
        configuration = LocationPreparationConfiguration(
            tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, preparation_owner=owner,
        )
        db.add(configuration)
    elif configuration.preparation_owner == owner:
        operation = 'UNCHANGED'
    else:
        operation = 'UPDATE'
        configuration.preparation_owner = owner
    try:
        await db.commit()
        await db.refresh(configuration)
    except IntegrityError as exc:
        await db.rollback()
        raise PreparationConfigurationConflictError(
            'Location Preparation Configuration update conflicted'
        ) from exc
    return PreparationConfigurationProvisioningResult(configuration, operation)
