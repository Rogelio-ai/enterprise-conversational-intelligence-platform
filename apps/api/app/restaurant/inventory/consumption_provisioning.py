"""Onboarding boundary for the canonical Product consumption aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InventoryItem,
    Location,
    ProductConsumptionDefinition,
    ProductConsumptionVersion,
    ProductConsumptionVersionComponent,
)
from app.restaurant.catalog import provisioning as product_provisioning
from app.restaurant.inventory import errors
from app.restaurant.inventory import service as inventory_service
from app.restaurant.inventory.contracts import (
    ConsumptionComponentInput,
    ConsumptionDefinitionProjection,
)
from app.restaurant.inventory.units import UnitConversionError, exact_quantity


_UOM_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]{0,31}$')
_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_TRACKING_MODES = frozenset({'DERIVABLE', 'NON_DERIVABLE'})


class ConsumptionProvisioningError(ValueError):
    pass


class ConsumptionScopeNotFoundError(ConsumptionProvisioningError):
    pass


class ConsumptionConflictError(ConsumptionProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class ConsumptionComponentDefinition:
    inventory_item_code: str
    quantity: Decimal
    uom: str


@dataclass(frozen=True, slots=True)
class ConsumptionProvisioningPlan:
    operation: str
    product_id: int | None
    definition_id: int | None
    expected_version: int


@dataclass(frozen=True, slots=True)
class ConsumptionProvisioningResult:
    definition: ConsumptionDefinitionProjection
    operation: str


def _status(value: object) -> str:
    if not isinstance(value, str):
        raise ConsumptionProvisioningError('Invalid Consumption status')
    normalized = value.strip().upper()
    if normalized not in _STATUSES:
        raise ConsumptionProvisioningError('Unsupported Consumption status')
    return normalized


def _tracking_mode(value: object) -> str:
    if not isinstance(value, str):
        raise ConsumptionProvisioningError('Invalid Consumption tracking mode')
    normalized = value.strip().upper()
    if normalized not in _TRACKING_MODES:
        raise ConsumptionProvisioningError('Unsupported Consumption tracking mode')
    return normalized


def _component(
    value: ConsumptionComponentDefinition,
) -> ConsumptionComponentDefinition:
    code = value.inventory_item_code.strip().upper()
    if not code or len(code) > 64:
        raise ConsumptionProvisioningError('Invalid Inventory Item code')
    try:
        quantity = exact_quantity(value.quantity, positive=True)
    except UnitConversionError as exc:
        raise ConsumptionProvisioningError(str(exc)) from exc
    uom = value.uom.strip().upper()
    if _UOM_PATTERN.fullmatch(uom) is None:
        raise ConsumptionProvisioningError('Unsupported component UOM code')
    return ConsumptionComponentDefinition(code, quantity, uom)


def _components(
    values: tuple[ConsumptionComponentDefinition, ...], tracking_mode: str,
) -> tuple[ConsumptionComponentDefinition, ...]:
    normalized = tuple(_component(value) for value in values)
    codes = [value.inventory_item_code for value in normalized]
    if len(codes) != len(set(codes)):
        raise ConsumptionProvisioningError(
            'A Consumption Definition cannot contain the same Inventory Item twice'
        )
    if tracking_mode == 'DERIVABLE' and not normalized:
        raise ConsumptionProvisioningError(
            'DERIVABLE Consumption requires at least one component'
        )
    if tracking_mode == 'NON_DERIVABLE' and normalized:
        raise ConsumptionProvisioningError(
            'NON_DERIVABLE Consumption cannot contain components'
        )
    return normalized


async def _location(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
) -> Location:
    location = await db.scalar(select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    ))
    if location is None:
        raise ConsumptionScopeNotFoundError('Location not found')
    return location


async def _item(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
    inventory_item_code: str,
) -> InventoryItem | None:
    return await db.scalar(select(InventoryItem).where(
        InventoryItem.tenant_id == tenant_id,
        InventoryItem.organization_id == organization_id,
        InventoryItem.location_id == location_id,
        InventoryItem.code == inventory_item_code,
    ))


async def _definition(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
    product_id: int,
) -> ProductConsumptionDefinition | None:
    return await db.scalar(select(ProductConsumptionDefinition).where(
        ProductConsumptionDefinition.tenant_id == tenant_id,
        ProductConsumptionDefinition.organization_id == organization_id,
        ProductConsumptionDefinition.location_id == location_id,
        ProductConsumptionDefinition.product_id == product_id,
    ))


async def _latest_version(
    db: AsyncSession, *, definition_id: int,
) -> ProductConsumptionVersion | None:
    return await db.scalar(select(ProductConsumptionVersion).where(
        ProductConsumptionVersion.definition_id == definition_id,
    ).order_by(ProductConsumptionVersion.revision.desc()).limit(1))


async def _same_state(
    db: AsyncSession, *, definition: ProductConsumptionDefinition,
    latest: ProductConsumptionVersion, status: str, tracking_mode: str,
    effective_from: datetime | None,
    requested: tuple[tuple[int, Decimal, str], ...],
) -> bool:
    if (
        definition.status != status
        or definition.tracking_mode != tracking_mode
        or (effective_from is not None and latest.effective_from != effective_from)
    ):
        return False
    rows = tuple((await db.scalars(
        select(ProductConsumptionVersionComponent).where(
            ProductConsumptionVersionComponent.version_id == latest.id,
        ).order_by(ProductConsumptionVersionComponent.inventory_item_id)
    )).all())
    current = tuple(
        (row.inventory_item_id, row.source_quantity, row.source_uom)
        for row in rows
    )
    return current == requested


async def plan_consumption_definition(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    tracking_mode: str, effective_from: datetime | None, status: str,
    components: tuple[ConsumptionComponentDefinition, ...],
    allow_unresolved_product: bool = False,
    allow_unresolved_items: frozenset[str] = frozenset(),
    allow_unresolved_evidence: frozenset[tuple[str, str]] = frozenset(),
) -> ConsumptionProvisioningPlan:
    normalized_status = _status(status)
    normalized_mode = _tracking_mode(tracking_mode)
    normalized_components = _components(components, normalized_mode)
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    try:
        product = await product_provisioning.resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except product_provisioning.ProductProvisioningError as exc:
        if allow_unresolved_product:
            return ConsumptionProvisioningPlan('CREATE', None, None, 0)
        raise ConsumptionScopeNotFoundError(str(exc)) from exc

    definition = await _definition(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, product_id=product.id,
    )
    evaluation_time = effective_from or await db.scalar(
        select(func.current_timestamp(6))
    )
    requested: list[tuple[int, Decimal, str]] = []
    unresolved = False
    for component in normalized_components:
        item = await _item(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id,
            inventory_item_code=component.inventory_item_code,
        )
        if item is None:
            if component.inventory_item_code in allow_unresolved_items:
                unresolved = True
                continue
            raise ConsumptionScopeNotFoundError(
                f'Inventory Item {component.inventory_item_code} not found'
            )
        if item.status != 'ACTIVE':
            raise ConsumptionConflictError(
                f'Inventory Item {component.inventory_item_code} must be active'
            )
        try:
            await inventory_service.resolve_quantity_evidence(
                db, item=item, quantity=component.quantity,
                source_uom=component.uom, as_of=evaluation_time,
            )
        except errors.InventoryError as exc:
            if (
                component.inventory_item_code, component.uom
            ) in allow_unresolved_evidence:
                unresolved = True
                continue
            raise ConsumptionProvisioningError(str(exc)) from exc
        requested.append((item.id, component.quantity, component.uom))

    if definition is None:
        return ConsumptionProvisioningPlan('CREATE', product.id, None, 0)
    latest = await _latest_version(db, definition_id=definition.id)
    if latest is None:
        raise ConsumptionConflictError(
            'Existing Consumption Definition has no published version'
        )
    if unresolved:
        operation = 'UPDATE'
    else:
        operation = (
            'UNCHANGED'
            if await _same_state(
                db, definition=definition, latest=latest,
                status=normalized_status, tracking_mode=normalized_mode,
                effective_from=effective_from,
                requested=tuple(sorted(requested)),
            )
            else 'UPDATE'
        )
    return ConsumptionProvisioningPlan(
        operation, product.id, definition.id, definition.version,
    )


async def _latest_projection(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
) -> ConsumptionDefinitionProjection:
    values = await inventory_service.list_consumption_definition_versions(
        db, tenant_id=tenant_id, product_id=product_id,
        location_id=location_id,
    )
    if not values:
        raise ConsumptionConflictError(
            'Consumption Definition has no published version'
        )
    return values[-1]


async def provision_consumption_definition(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    tracking_mode: str, effective_from: datetime | None, status: str,
    components: tuple[ConsumptionComponentDefinition, ...], actor_id: int,
) -> ConsumptionProvisioningResult:
    plan = await plan_consumption_definition(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, binding_namespace=binding_namespace,
        product_key=product_key, tracking_mode=tracking_mode,
        effective_from=effective_from, status=status, components=components,
    )
    product = await product_provisioning.resolve_product_binding(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, product_key=product_key,
    )
    if plan.operation == 'UNCHANGED':
        return ConsumptionProvisioningResult(
            await _latest_projection(
                db, tenant_id=tenant_id, product_id=product.id,
                location_id=location_id,
            ),
            'UNCHANGED',
        )
    normalized_mode = _tracking_mode(tracking_mode)
    normalized_components = _components(components, normalized_mode)
    inputs: list[ConsumptionComponentInput] = []
    for component in normalized_components:
        item = await _item(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id,
            inventory_item_code=component.inventory_item_code,
        )
        if item is None:
            raise ConsumptionScopeNotFoundError(
                f'Inventory Item {component.inventory_item_code} not found'
            )
        inputs.append(ConsumptionComponentInput(
            inventory_item_id=item.id, quantity=component.quantity,
            uom=component.uom,
        ))
    try:
        result = await inventory_service.put_consumption_definition(
            db, tenant_id=tenant_id, product_id=product.id,
            location_id=location_id, expected_version=plan.expected_version,
            status=_status(status), tracking_mode=normalized_mode,
            components=tuple(inputs), effective_from=effective_from,
            actor_id=actor_id,
        )
        return ConsumptionProvisioningResult(result, plan.operation)
    except errors.ConsumptionDefinitionVersionConflictError as exc:
        winner = await plan_consumption_definition(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, binding_namespace=binding_namespace,
            product_key=product_key, tracking_mode=tracking_mode,
            effective_from=effective_from, status=status,
            components=components,
        )
        if winner.operation == 'UNCHANGED':
            return ConsumptionProvisioningResult(
                await _latest_projection(
                    db, tenant_id=tenant_id, product_id=product.id,
                    location_id=location_id,
                ),
                'UNCHANGED',
            )
        raise ConsumptionConflictError(
            'Consumption Definition changed concurrently'
        ) from exc
    except errors.InventoryScopeNotFoundError as exc:
        raise ConsumptionScopeNotFoundError(str(exc)) from exc
    except errors.InventoryError as exc:
        raise ConsumptionProvisioningError(str(exc)) from exc
