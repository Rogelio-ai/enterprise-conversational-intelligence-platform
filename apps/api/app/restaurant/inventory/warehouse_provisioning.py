"""Canonical operator-defined Warehouse provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Warehouse


WAREHOUSE_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
NEGATIVE_STOCK_POLICIES = frozenset({'ALLOW', 'WARN', 'BLOCK'})
_CODE_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')
_DUPLICATE_KEY_PATTERN = re.compile(
    r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE,
)
_WAREHOUSE_CONSTRAINTS = frozenset({
    'uq_warehouses_location_code', 'uq_warehouses_location_default',
})


class WarehouseProvisioningError(ValueError):
    pass


class WarehouseScopeNotFoundError(WarehouseProvisioningError):
    pass


class WarehouseConflictError(WarehouseProvisioningError):
    pass


WarehouseState = tuple[str, str, int | None, str, int]
RequestedWarehouseState = tuple[str, str, int | None, str]


@dataclass(frozen=True, slots=True)
class WarehouseProvisioningPlan:
    operation: str
    warehouse_code: str
    warehouse_id: int | None
    observed_state: WarehouseState | None


@dataclass(frozen=True, slots=True)
class WarehouseProvisioningResult:
    location: Location
    warehouse: Warehouse
    operation: str


def normalize_code(value: object) -> str:
    if not isinstance(value, str):
        raise WarehouseProvisioningError('Invalid Warehouse code')
    normalized = value.strip().upper()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise WarehouseProvisioningError(
            'Warehouse code must contain only letters, numbers, underscores, or hyphens'
        )
    return normalized


def _name(value: object) -> str:
    if not isinstance(value, str):
        raise WarehouseProvisioningError('Invalid Warehouse name')
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise WarehouseProvisioningError(
            'Warehouse name must contain between 1 and 200 characters'
        )
    return normalized


def _status(value: object) -> str:
    if not isinstance(value, str):
        raise WarehouseProvisioningError('Invalid Warehouse status')
    normalized = value.strip().upper()
    if normalized not in WAREHOUSE_STATUSES:
        raise WarehouseProvisioningError('Unsupported Warehouse status')
    return normalized


def _policy(value: object) -> str:
    if not isinstance(value, str):
        raise WarehouseProvisioningError('Invalid negative-stock policy')
    normalized = value.strip().upper()
    if normalized not in NEGATIVE_STOCK_POLICIES:
        raise WarehouseProvisioningError('Unsupported negative-stock policy')
    return normalized


def _default_slot(value: object) -> int | None:
    if not isinstance(value, bool):
        raise WarehouseProvisioningError('Warehouse default flag must be boolean')
    return 1 if value else None


def _state(warehouse: Warehouse) -> WarehouseState:
    return (
        warehouse.name, warehouse.status, warehouse.default_slot,
        warehouse.negative_stock_policy, warehouse.version,
    )


def _requested_state(
    *, name: str, status: str, default_slot: int | None,
    negative_stock_policy: str,
) -> RequestedWarehouseState:
    return name, status, default_slot, negative_stock_policy


def _matches(
    state: WarehouseState, requested: RequestedWarehouseState,
) -> bool:
    return state[:4] == requested


def _is_warehouse_constraint(exc: IntegrityError) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return (
        match is not None
        and match.group(1).rsplit('.', 1)[-1] in _WAREHOUSE_CONSTRAINTS
    )


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
        raise WarehouseScopeNotFoundError('Location not found')
    return location


async def _warehouse(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, warehouse_code: str, for_update: bool = False,
) -> Warehouse | None:
    statement = select(Warehouse).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.organization_id == organization_id,
        Warehouse.location_id == location_id,
        Warehouse.code == warehouse_code,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def _verify_default_available(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, warehouse_code: str, for_update: bool = False,
) -> None:
    statement = select(Warehouse).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.organization_id == organization_id,
        Warehouse.location_id == location_id,
        Warehouse.default_slot == 1,
        Warehouse.code != warehouse_code,
    )
    if for_update:
        statement = statement.with_for_update()
    if await db.scalar(statement) is not None:
        raise WarehouseConflictError(
            'A different default Warehouse already exists in this Location'
        )


def _verify_update(
    warehouse: Warehouse, *, requested: RequestedWarehouseState,
) -> None:
    if warehouse.default_slot != requested[2]:
        raise WarehouseConflictError(
            'Existing Warehouse default identity cannot be changed by onboarding'
        )


async def plan_warehouse(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, warehouse_code: str, name: str, is_default: bool,
    negative_stock_policy: str, status: str,
) -> WarehouseProvisioningPlan:
    code = normalize_code(warehouse_code)
    normalized_name = _name(name)
    normalized_status = _status(status)
    normalized_policy = _policy(negative_stock_policy)
    default_slot = _default_slot(is_default)
    location = await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    requested = _requested_state(
        name=normalized_name, status=normalized_status,
        default_slot=default_slot, negative_stock_policy=normalized_policy,
    )
    warehouse = await _warehouse(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location.id, warehouse_code=code,
    )
    if warehouse is None:
        if normalized_status != 'ACTIVE':
            raise WarehouseConflictError('New Warehouses must be ACTIVE')
        if location.status != 'ACTIVE':
            raise WarehouseConflictError('Location must be active')
        if default_slot == 1:
            await _verify_default_available(
                db, tenant_id=tenant_id, organization_id=organization_id,
                location_id=location.id, warehouse_code=code,
            )
        return WarehouseProvisioningPlan('CREATE', code, None, None)
    observed = _state(warehouse)
    _verify_update(warehouse, requested=requested)
    if normalized_status == 'ACTIVE' and location.status != 'ACTIVE':
        raise WarehouseConflictError('Location must be active')
    return WarehouseProvisioningPlan(
        'UNCHANGED' if _matches(observed, requested) else 'UPDATE',
        code, warehouse.id, observed,
    )


async def provision_warehouse(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, warehouse_code: str, name: str, is_default: bool,
    negative_stock_policy: str, status: str,
) -> WarehouseProvisioningResult:
    code = normalize_code(warehouse_code)
    normalized_name = _name(name)
    normalized_status = _status(status)
    normalized_policy = _policy(negative_stock_policy)
    default_slot = _default_slot(is_default)
    plan = await plan_warehouse(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, warehouse_code=code, name=normalized_name,
        is_default=is_default, negative_stock_policy=normalized_policy,
        status=normalized_status,
    )
    location = await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, for_update=True,
    )
    current = await _warehouse(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location.id, warehouse_code=code, for_update=True,
    )
    requested = _requested_state(
        name=normalized_name, status=normalized_status,
        default_slot=default_slot, negative_stock_policy=normalized_policy,
    )
    if plan.operation == 'CREATE':
        if current is not None:
            if _matches(_state(current), requested):
                await db.commit()
                return WarehouseProvisioningResult(location, current, 'UNCHANGED')
            raise WarehouseConflictError(
                'A conflicting Warehouse was created concurrently'
            )
        if normalized_status != 'ACTIVE' or location.status != 'ACTIVE':
            raise WarehouseConflictError(
                'A new Warehouse and its Location must be active'
            )
        if default_slot == 1:
            await _verify_default_available(
                db, tenant_id=tenant_id, organization_id=organization_id,
                location_id=location.id, warehouse_code=code, for_update=True,
            )
        warehouse = Warehouse(
            tenant_id=tenant_id, organization_id=organization_id,
            location_id=location.id, code=code, name=normalized_name,
            status='ACTIVE', default_slot=default_slot,
            negative_stock_policy=normalized_policy, version=1,
        )
        db.add(warehouse)
        operation = 'CREATE'
    else:
        if current is None:
            raise WarehouseConflictError('Planned Warehouse no longer exists')
        _verify_update(current, requested=requested)
        current_state = _state(current)
        if current_state != plan.observed_state:
            if _matches(current_state, requested):
                await db.commit()
                return WarehouseProvisioningResult(location, current, 'UNCHANGED')
            raise WarehouseConflictError('Warehouse changed concurrently')
        operation = 'UNCHANGED' if _matches(current_state, requested) else 'UPDATE'
        if operation == 'UPDATE':
            current.name = normalized_name
            current.status = normalized_status
            current.negative_stock_policy = normalized_policy
            current.version += 1
        warehouse = current
    try:
        if operation != 'UNCHANGED':
            await db.commit()
            await db.refresh(warehouse)
        else:
            await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_warehouse_constraint(exc):
            raise WarehouseConflictError(
                'Warehouse code or default identity conflicts in this Location'
            ) from exc
        raise
    return WarehouseProvisioningResult(location, warehouse, operation)
