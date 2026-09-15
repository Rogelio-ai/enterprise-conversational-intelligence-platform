"""Canonical scoped Preparation Area provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, PreparationArea, Resource
from app.restaurant import resource_provisioning


AREA_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_CODE_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')


class PreparationAreaProvisioningError(ValueError):
    pass


class PreparationAreaScopeNotFoundError(PreparationAreaProvisioningError):
    pass


class PreparationAreaConflictError(PreparationAreaProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class PreparationAreaProvisioningPlan:
    operation: str
    area_code: str
    area_id: int | None
    resource_id: int | None


@dataclass(frozen=True, slots=True)
class PreparationAreaProvisioningResult:
    area: PreparationArea
    operation: str


def normalize_code(value: str) -> str:
    if not isinstance(value, str):
        raise PreparationAreaProvisioningError('Invalid Preparation Area code')
    normalized = value.strip().upper()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise PreparationAreaProvisioningError(
            'Code must contain only letters, numbers, underscores, or hyphens'
        )
    return normalized


def _name(value: str) -> str:
    if not isinstance(value, str):
        raise PreparationAreaProvisioningError('Invalid Preparation Area name')
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise PreparationAreaProvisioningError(
            'Preparation Area name must contain between 1 and 200 characters'
        )
    return normalized


def _status(value: str) -> str:
    if not isinstance(value, str):
        raise PreparationAreaProvisioningError('Invalid Preparation Area status')
    normalized = value.strip().upper()
    if normalized not in AREA_STATUSES:
        raise PreparationAreaProvisioningError('Unsupported Preparation Area status')
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
        raise PreparationAreaScopeNotFoundError('Location not found')
    return location


async def _resource_by_id(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    resource_id: int | None,
) -> None:
    if resource_id is None:
        return
    value = await db.scalar(select(Resource.id).where(
        Resource.id == resource_id,
        Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
    ))
    if value is None:
        raise PreparationAreaScopeNotFoundError(
            'Resource not found in this Location'
        )


async def resolve_area(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, area_code: str, for_update: bool = False,
) -> PreparationArea:
    code = normalize_code(area_code)
    statement = select(PreparationArea).where(
        PreparationArea.tenant_id == tenant_id,
        PreparationArea.organization_id == organization_id,
        PreparationArea.location_id == location_id,
        PreparationArea.code == code,
    )
    if for_update:
        statement = statement.with_for_update()
    area = await db.scalar(statement)
    if area is None:
        raise PreparationAreaScopeNotFoundError('Preparation Area not found')
    return area


async def create_area(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, resource_id: int | None, code: str, name: str,
    status: str = 'ACTIVE', commit: bool = True,
) -> PreparationArea:
    normalized_status = _status(status)
    if normalized_status != 'ACTIVE':
        raise PreparationAreaConflictError('New Preparation Areas must be ACTIVE')
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, for_update=True,
    )
    await _resource_by_id(
        db, tenant_id=tenant_id, location_id=location_id,
        resource_id=resource_id,
    )
    area = PreparationArea(
        tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, resource_id=resource_id,
        code=normalize_code(code), name=_name(name), status=normalized_status,
    )
    db.add(area)
    try:
        if commit:
            await db.commit()
            await db.refresh(area)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise PreparationAreaConflictError(
            'Preparation Area code already exists in this Location'
        ) from exc
    return area


async def update_area(
    db: AsyncSession, *, tenant_id: int, area_id: int,
    changes: dict[str, object], commit: bool = True,
) -> PreparationArea:
    allowed = {'name', 'resource_id', 'status'}
    if not changes or not set(changes) <= allowed:
        raise PreparationAreaProvisioningError(
            'Invalid Preparation Area update fields'
        )
    area = await db.scalar(select(PreparationArea).where(
        PreparationArea.id == area_id,
        PreparationArea.tenant_id == tenant_id,
    ).with_for_update())
    if area is None:
        raise PreparationAreaScopeNotFoundError('Preparation Area not found')
    updates = dict(changes)
    if 'name' in updates:
        if not isinstance(updates['name'], str):
            raise PreparationAreaProvisioningError('Invalid Preparation Area name')
        updates['name'] = _name(updates['name'])
    if 'resource_id' in updates:
        resource_id = updates['resource_id']
        if resource_id is not None and not isinstance(resource_id, int):
            raise PreparationAreaProvisioningError('Invalid Resource identifier')
        await _resource_by_id(
            db, tenant_id=tenant_id, location_id=area.location_id,
            resource_id=resource_id,
        )
    if 'status' in updates:
        if not isinstance(updates['status'], str):
            raise PreparationAreaProvisioningError('Invalid Preparation Area status')
        updates['status'] = _status(updates['status'])
    for field, value in updates.items():
        setattr(area, field, value)
    if commit:
        await db.commit()
        await db.refresh(area)
    else:
        await db.flush()
    return area


def _operation(
    area: PreparationArea, *, resource_id: int | None, name: str, status: str,
) -> str:
    current = (area.resource_id, area.name, area.status)
    requested = (resource_id, name, status)
    return 'UNCHANGED' if current == requested else 'UPDATE'


async def _resource_id_for_code(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    resource_code: str | None,
) -> int | None:
    if resource_code is None:
        return None
    try:
        resource = await resource_provisioning.resolve_resource(
            db, tenant_id=tenant_id, location_id=location_id,
            resource_code=resource_code,
        )
    except resource_provisioning.ResourceScopeNotFoundError as exc:
        raise PreparationAreaScopeNotFoundError(
            'Resource not found in this Location'
        ) from exc
    except resource_provisioning.ResourceProvisioningError as exc:
        raise PreparationAreaProvisioningError(str(exc)) from exc
    return resource.id


async def plan_area(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, area_code: str, resource_code: str | None,
    name: str, status: str, allow_unresolved_resource: bool = False,
) -> PreparationAreaProvisioningPlan:
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    code = normalize_code(area_code)
    normalized_name = _name(name)
    normalized_status = _status(status)
    resource_resolved = True
    try:
        resource_id = await _resource_id_for_code(
            db, tenant_id=tenant_id, location_id=location_id,
            resource_code=resource_code,
        )
    except PreparationAreaScopeNotFoundError:
        if not allow_unresolved_resource:
            raise
        resource_id = None
        resource_resolved = False
    area = await db.scalar(select(PreparationArea).where(
        PreparationArea.tenant_id == tenant_id,
        PreparationArea.organization_id == organization_id,
        PreparationArea.location_id == location_id,
        PreparationArea.code == code,
    ))
    if area is None:
        if normalized_status != 'ACTIVE':
            raise PreparationAreaConflictError(
                'New Preparation Areas must be ACTIVE'
            )
        return PreparationAreaProvisioningPlan(
            'CREATE', code, None, resource_id,
        )
    operation = 'UPDATE' if not resource_resolved else _operation(
        area, resource_id=resource_id, name=normalized_name,
        status=normalized_status,
    )
    return PreparationAreaProvisioningPlan(
        operation, code, area.id, resource_id,
    )


async def provision_area(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, area_code: str, resource_code: str | None,
    name: str, status: str,
) -> PreparationAreaProvisioningResult:
    code = normalize_code(area_code)
    normalized_name = _name(name)
    normalized_status = _status(status)
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, for_update=True,
    )
    resource_id = await _resource_id_for_code(
        db, tenant_id=tenant_id, location_id=location_id,
        resource_code=resource_code,
    )
    area = await db.scalar(select(PreparationArea).where(
        PreparationArea.tenant_id == tenant_id,
        PreparationArea.organization_id == organization_id,
        PreparationArea.location_id == location_id,
        PreparationArea.code == code,
    ).with_for_update())
    if area is None:
        if normalized_status != 'ACTIVE':
            raise PreparationAreaConflictError(
                'New Preparation Areas must be ACTIVE'
            )
        area = PreparationArea(
            tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, resource_id=resource_id,
            code=code, name=normalized_name, status=normalized_status,
        )
        db.add(area)
        operation = 'CREATE'
    else:
        operation = _operation(
            area, resource_id=resource_id, name=normalized_name,
            status=normalized_status,
        )
        if operation == 'UPDATE':
            area.resource_id = resource_id
            area.name = normalized_name
            area.status = normalized_status
    try:
        await db.commit()
        await db.refresh(area)
    except IntegrityError as exc:
        await db.rollback()
        raise PreparationAreaConflictError(
            'Preparation Area code already exists in this Location'
        ) from exc
    return PreparationAreaProvisioningResult(area, operation)
