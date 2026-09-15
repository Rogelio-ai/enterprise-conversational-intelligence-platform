"""Canonical scoped Resource provisioning by the certified Location code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Resource


RESOURCE_TYPES = frozenset({
    'AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', 'VEHICLE', 'DEVICE',
    'CASH_REGISTER',
})
RESOURCE_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_CODE_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_CODE_CONSTRAINT = 'uq_resources_location_code'


class ResourceProvisioningError(ValueError):
    pass


class ResourceScopeNotFoundError(ResourceProvisioningError):
    pass


class ResourceConflictError(ResourceProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class ResourceProvisioningPlan:
    operation: str
    resource_code: str
    resource_id: int | None


@dataclass(frozen=True, slots=True)
class ResourceProvisioningResult:
    resource: Resource
    operation: str


def normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise ResourceProvisioningError(
            'Code must contain only letters, numbers, underscores, or hyphens'
        )
    return normalized


def _name(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise ResourceProvisioningError(
            'Resource name must contain between 1 and 200 characters'
        )
    return normalized


def _type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in RESOURCE_TYPES:
        raise ResourceProvisioningError('Unsupported Resource type')
    return normalized


def _status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in RESOURCE_STATUSES:
        raise ResourceProvisioningError('Unsupported Resource status')
    return normalized


def is_duplicate_code_error(exc: IntegrityError) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == _CODE_CONSTRAINT


async def _location(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    for_update: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id, Location.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    location = await db.scalar(statement)
    if location is None:
        raise ResourceScopeNotFoundError('Location not found')
    return location


def _activate_cash_management(location: Location) -> None:
    if location.cash_management_activated_at is None:
        location.cash_management_activated_at = datetime.now(UTC).replace(tzinfo=None)


async def resolve_resource(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    resource_code: str, for_update: bool = False,
) -> Resource:
    code = normalize_code(resource_code)
    statement = select(Resource).where(
        Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
        Resource.code == code,
    )
    if for_update:
        statement = statement.with_for_update()
    resource = await db.scalar(statement)
    if resource is None:
        raise ResourceScopeNotFoundError('Resource not found')
    return resource


async def create_resource(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    code: str, name: str, resource_type: str, status: str = 'ACTIVE',
    commit: bool = True,
) -> Resource:
    normalized_status = _status(status)
    if normalized_status != 'ACTIVE':
        raise ResourceConflictError('New Resources must be ACTIVE')
    location = await _location(
        db, tenant_id=tenant_id, location_id=location_id, for_update=True,
    )
    if location.status != 'ACTIVE':
        raise ResourceConflictError('Location must be active')
    normalized_type = _type(resource_type)
    if normalized_type == 'CASH_REGISTER':
        _activate_cash_management(location)
    resource = Resource(
        tenant_id=tenant_id, location_id=location_id,
        code=normalize_code(code), name=_name(name),
        resource_type=normalized_type, status=normalized_status,
    )
    db.add(resource)
    try:
        if commit:
            await db.commit()
            await db.refresh(resource)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if commit and is_duplicate_code_error(exc):
            raise ResourceConflictError(
                'Resource code already exists in this Location'
            ) from exc
        raise
    return resource


async def update_resource(
    db: AsyncSession, *, tenant_id: int, resource_id: int,
    changes: dict[str, object], commit: bool = True,
) -> Resource:
    allowed = {'code', 'name', 'resource_type', 'status'}
    if not changes or not set(changes) <= allowed:
        raise ResourceProvisioningError('Invalid Resource update fields')
    resource = await db.scalar(select(Resource).where(
        Resource.id == resource_id, Resource.tenant_id == tenant_id,
    ).with_for_update())
    if resource is None:
        raise ResourceScopeNotFoundError('Resource not found')
    updates = dict(changes)
    normalized_type = None
    normalized_status = None
    if 'code' in updates:
        if not isinstance(updates['code'], str):
            raise ResourceProvisioningError('Invalid Resource code')
        updates['code'] = normalize_code(updates['code'])
    if 'name' in updates:
        if not isinstance(updates['name'], str):
            raise ResourceProvisioningError('Invalid Resource name')
        updates['name'] = _name(updates['name'])
    if 'resource_type' in updates:
        if not isinstance(updates['resource_type'], str):
            raise ResourceProvisioningError('Invalid Resource type')
        normalized_type = _type(updates['resource_type'])
        updates['resource_type'] = normalized_type
    if 'status' in updates:
        if not isinstance(updates['status'], str):
            raise ResourceProvisioningError('Invalid Resource status')
        normalized_status = _status(updates['status'])
        updates['status'] = normalized_status
    if normalized_status == 'ACTIVE' or normalized_type == 'CASH_REGISTER':
        location = await _location(
            db, tenant_id=tenant_id, location_id=resource.location_id,
            for_update=True,
        )
        if location.status != 'ACTIVE':
            raise ResourceConflictError('Location must be active')
        if normalized_type == 'CASH_REGISTER':
            _activate_cash_management(location)
    for field, value in updates.items():
        setattr(resource, field, value)
    try:
        if commit:
            await db.commit()
            await db.refresh(resource)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if is_duplicate_code_error(exc):
            raise ResourceConflictError(
                'Resource code already exists in this Location'
            ) from exc
        raise
    return resource


def _operation(
    resource: Resource, *, name: str, resource_type: str, status: str,
) -> str:
    current = (resource.name, resource.resource_type, resource.status)
    requested = (name, resource_type, status)
    return 'UNCHANGED' if current == requested else 'UPDATE'


async def plan_resource(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    resource_code: str, name: str, resource_type: str, status: str,
) -> ResourceProvisioningPlan:
    location = await _location(db, tenant_id=tenant_id, location_id=location_id)
    code = normalize_code(resource_code)
    normalized_name = _name(name)
    normalized_type = _type(resource_type)
    normalized_status = _status(status)
    resource = await db.scalar(select(Resource).where(
        Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
        Resource.code == code,
    ))
    if resource is None:
        if normalized_status != 'ACTIVE':
            raise ResourceConflictError('New Resources must be ACTIVE')
        if location.status != 'ACTIVE':
            raise ResourceConflictError('Location must be active')
        return ResourceProvisioningPlan('CREATE', code, None)
    operation = _operation(
        resource, name=normalized_name,
        resource_type=normalized_type, status=normalized_status,
    )
    if operation == 'UPDATE' and (
        normalized_status == 'ACTIVE' or normalized_type == 'CASH_REGISTER'
    ) and location.status != 'ACTIVE':
        raise ResourceConflictError('Location must be active')
    return ResourceProvisioningPlan(operation, code, resource.id)


async def provision_resource(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    resource_code: str, name: str, resource_type: str, status: str,
) -> ResourceProvisioningResult:
    plan = await plan_resource(
        db, tenant_id=tenant_id, location_id=location_id,
        resource_code=resource_code, name=name,
        resource_type=resource_type, status=status,
    )
    changes = {'name': name, 'resource_type': resource_type, 'status': status}
    if plan.resource_id is not None:
        resource = await resolve_resource(
            db, tenant_id=tenant_id, location_id=location_id,
            resource_code=plan.resource_code, for_update=True,
        )
        operation = _operation(
            resource, name=name.strip(), resource_type=resource_type.strip().upper(),
            status=status.strip().upper(),
        )
        if operation == 'UPDATE':
            resource = await update_resource(
                db, tenant_id=tenant_id, resource_id=resource.id, changes=changes,
            )
        return ResourceProvisioningResult(resource, operation)
    try:
        resource = await create_resource(
            db, tenant_id=tenant_id, location_id=location_id,
            code=plan.resource_code, name=name, resource_type=resource_type,
            status=status, commit=False,
        )
        await db.commit()
        await db.refresh(resource)
        return ResourceProvisioningResult(resource, 'CREATE')
    except IntegrityError as exc:
        await db.rollback()
        if not is_duplicate_code_error(exc):
            raise
        winner = await resolve_resource(
            db, tenant_id=tenant_id, location_id=location_id,
            resource_code=plan.resource_code, for_update=True,
        )
        operation = _operation(
            winner, name=name.strip(), resource_type=resource_type.strip().upper(),
            status=status.strip().upper(),
        )
        if operation == 'UPDATE':
            await db.rollback()
            raise ResourceConflictError(
                'Concurrent Resource definition conflicts with the canonical winner'
            )
        return ResourceProvisioningResult(winner, operation)
