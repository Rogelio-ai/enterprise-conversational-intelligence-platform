from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    InventoryCostRevision,
    InventoryItem,
    ItemUomConversion,
    Location,
    Product,
    ProductConsumptionComponent,
    ProductConsumptionDefinition,
    ProductConsumptionVersion,
    ProductConsumptionVersionComponent,
    StockMovement,
    Warehouse,
)
from app.restaurant.inventory import errors
from app.restaurant.inventory.contracts import (
    ConsumptionComponentInput,
    ConsumptionComponentProjection,
    ConsumptionDefinitionProjection,
    CostComponentProjection,
    InventoryCostRevisionProjection,
    ItemUomConversionProjection,
    ProductCostProjection,
    StockMovementProjection,
    StockProjection,
    WarehouseProjection,
)
from app.restaurant.inventory.units import (
    QUANTITY_UNIT,
    UnitConversionError,
    conversion_factor,
    convert_item_quantity,
    convert_quantity,
    exact_quantity,
    unit_code,
)


REQUEST_SCHEMA_VERSION = 1
MANUAL_MOVEMENT_TYPES = frozenset(
    {'OPENING_BALANCE', 'MANUAL_IN', 'MANUAL_OUT', 'ADJUSTMENT', 'REVERSAL'}
)
_CURRENCY = re.compile(r'^[A-Z]{3}$')
_OPERATIONAL_UOM = re.compile(r'^[A-Z][A-Z0-9_]{0,31}$')
_ZERO = Decimal('0')


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _database_now(db: AsyncSession) -> datetime:
    value = await db.scalar(select(func.current_timestamp(6)))
    # The existing ledger uses MySQL/MariaDB DATETIME without fractional
    # precision. Persist and resolve "now" at that same precision so the
    # database cannot round an effective instant into the next second.
    return (value if value is not None else _now()).replace(microsecond=0)


def _currency(value: str) -> str:
    normalized = value.strip().upper()
    if _CURRENCY.fullmatch(normalized) is None:
        raise errors.InvalidInventoryItemError('Currency must be three uppercase letters')
    return normalized


def _cost(value: Decimal) -> Decimal:
    try:
        value = exact_quantity(value)
    except UnitConversionError as exc:
        raise errors.InvalidInventoryItemError(str(exc)) from exc
    if value < _ZERO:
        raise errors.InvalidInventoryItemError('Standard unit cost cannot be negative')
    return value


def _text(value: str, *, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise errors.InvalidInventoryItemError(
            f'{field} must contain between 1 and {maximum} characters'
        )
    return normalized


async def _location(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    for_update: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id, Location.tenant_id == tenant_id
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.InventoryScopeNotFoundError('Location not found')
    return value


def _warehouse_projection(value: Warehouse) -> WarehouseProjection:
    return WarehouseProjection(
        id=value.id,
        tenant_id=value.tenant_id,
        organization_id=value.organization_id,
        location_id=value.location_id,
        code=value.code,
        name=value.name,
        status=value.status,
        is_default=value.default_slot == 1,
        negative_stock_policy=value.negative_stock_policy,
        version=value.version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


async def resolve_default_warehouse(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    for_update: bool = False,
) -> Warehouse:
    location = await _location(
        db, tenant_id=tenant_id, location_id=location_id, for_update=True,
    )
    statement = select(Warehouse).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.organization_id == location.organization_id,
        Warehouse.location_id == location.id,
        Warehouse.default_slot == 1,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        value = Warehouse(
            tenant_id=tenant_id,
            organization_id=location.organization_id,
            location_id=location.id,
            code='DEFAULT',
            name='Default Warehouse',
            status='ACTIVE',
            default_slot=1,
            negative_stock_policy='ALLOW',
            version=1,
        )
        db.add(value)
        await db.flush()
    return value


async def _warehouse_for_scope(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
    warehouse_id: int | None,
    for_update: bool = False,
) -> Warehouse:
    if warehouse_id is None:
        return await resolve_default_warehouse(
            db, tenant_id=tenant_id, location_id=location_id,
            for_update=for_update,
        )
    statement = select(Warehouse).where(
        Warehouse.id == warehouse_id,
        Warehouse.tenant_id == tenant_id,
        Warehouse.organization_id == organization_id,
        Warehouse.location_id == location_id,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.WarehouseNotFoundError()
    return value


async def stock_quantity(
    db: AsyncSession, *, tenant_id: int, warehouse_id: int, inventory_item_id: int,
) -> Decimal:
    quantities = (
        await db.scalars(
            select(StockMovement.quantity).where(
                StockMovement.tenant_id == tenant_id,
                StockMovement.warehouse_id == warehouse_id,
                StockMovement.inventory_item_id == inventory_item_id,
            ).order_by(StockMovement.id).with_for_update()
        )
    ).all()
    return sum(
        (Decimal(value) for value in quantities), start=Decimal(0)
    ).quantize(QUANTITY_UNIT)


async def list_warehouses(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> tuple[WarehouseProjection, ...]:
    await resolve_default_warehouse(
        db, tenant_id=tenant_id, location_id=location_id,
    )
    await db.commit()
    rows = tuple((await db.execute(
        select(Warehouse).where(
            Warehouse.tenant_id == tenant_id,
            Warehouse.location_id == location_id,
        ).order_by(Warehouse.id)
    )).scalars().all())
    return tuple(_warehouse_projection(value) for value in rows)


async def update_warehouse_policy(
    db: AsyncSession, *, tenant_id: int, warehouse_id: int,
    expected_version: int, negative_stock_policy: str,
) -> WarehouseProjection:
    policy = negative_stock_policy.strip().upper()
    if policy not in ('ALLOW', 'WARN', 'BLOCK'):
        raise errors.InvalidStockMovementError('Unsupported negative-stock policy')
    try:
        value = await db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id,
                Warehouse.tenant_id == tenant_id,
            ).with_for_update()
        )
        if value is None:
            raise errors.WarehouseNotFoundError()
        if value.version != expected_version:
            raise errors.WarehouseVersionConflictError(
                f'Expected version {expected_version}, current version is {value.version}'
            )
        value.negative_stock_policy = policy
        value.version += 1
        await db.commit()
        await db.refresh(value)
        return _warehouse_projection(value)
    except Exception:
        await db.rollback()
        raise


async def _item(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    for_update: bool = False,
) -> InventoryItem:
    statement = select(InventoryItem).where(
        InventoryItem.id == inventory_item_id,
        InventoryItem.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.InventoryItemNotFoundError()
    return value


async def inventory_item_location(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
) -> int:
    return (await _item(
        db, tenant_id=tenant_id, inventory_item_id=inventory_item_id,
    )).location_id


async def warehouse_location(
    db: AsyncSession, *, tenant_id: int, warehouse_id: int,
) -> int:
    location_id = await db.scalar(
        select(Warehouse.location_id).where(
            Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id,
        )
    )
    if location_id is None:
        raise errors.WarehouseNotFoundError()
    return location_id


def _conversion_projection(
    value: ItemUomConversion, base_uom: str,
) -> ItemUomConversionProjection:
    return ItemUomConversionProjection(
        id=value.id, inventory_item_id=value.inventory_item_id,
        operational_uom=value.operational_uom, base_uom=base_uom,
        factor_to_base=value.factor_to_base, revision=value.revision,
        effective_at=value.effective_at, actor_id=value.actor_id,
        reference=value.reference, created_at=value.created_at,
    )


def _cost_projection(value: InventoryCostRevision) -> InventoryCostRevisionProjection:
    return InventoryCostRevisionProjection(
        id=value.id, inventory_item_id=value.inventory_item_id,
        revision=value.revision, standard_unit_cost=value.standard_unit_cost,
        currency=value.currency, effective_at=value.effective_at,
        source=value.source, actor_id=value.actor_id, reference=value.reference,
        created_at=value.created_at,
    )


def _operational_uom(value: str) -> str:
    normalized = value.strip().upper()
    if _OPERATIONAL_UOM.fullmatch(normalized) is None:
        raise errors.InvalidItemUomConversionError('Unsupported operational UOM code')
    return normalized


async def append_item_uom_conversion(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    operational_uom: str, factor_to_base: Decimal, effective_at: datetime | None,
    actor_id: int, reference: str | None,
) -> ItemUomConversionProjection:
    item = await _item(
        db, tenant_id=tenant_id, inventory_item_id=inventory_item_id,
        for_update=True,
    )
    operational_uom = _operational_uom(operational_uom)
    try:
        built_in = unit_code(operational_uom)
    except UnitConversionError:
        built_in = None
    if built_in is not None:
        try:
            convert_quantity(Decimal('1'), from_uom=built_in, to_uom=item.base_uom)
        except UnitConversionError as exc:
            raise errors.InvalidItemUomConversionError(str(exc)) from exc
        raise errors.InvalidItemUomConversionError(
            'Built-in UOM conversions cannot be overridden per item'
        )
    try:
        factor_to_base = conversion_factor(factor_to_base)
    except UnitConversionError as exc:
        raise errors.InvalidItemUomConversionError(str(exc)) from exc
    if effective_at is None:
        effective_at = await _database_now(db)
    latest = await db.scalar(
        select(ItemUomConversion).where(
            ItemUomConversion.tenant_id == tenant_id,
            ItemUomConversion.inventory_item_id == item.id,
            ItemUomConversion.operational_uom == operational_uom,
        ).order_by(
            ItemUomConversion.revision.desc()
        ).limit(1).with_for_update()
    )
    if latest is not None and effective_at < latest.effective_at:
        raise errors.InvalidItemUomConversionError(
            'Conversion revisions cannot be backdated before the latest revision'
        )
    value = ItemUomConversion(
        tenant_id=item.tenant_id, organization_id=item.organization_id,
        location_id=item.location_id, inventory_item_id=item.id,
        operational_uom=operational_uom, factor_to_base=factor_to_base,
        revision=1 if latest is None else latest.revision + 1,
        effective_at=effective_at, actor_id=actor_id,
        reference=reference.strip() if reference and reference.strip() else None,
    )
    db.add(value)
    try:
        await db.commit()
        await db.refresh(value)
        return _conversion_projection(value, item.base_uom)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.DuplicateItemUomConversionError(
            'Conversion revision was appended concurrently'
        ) from exc


async def list_item_uom_conversions(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
) -> tuple[ItemUomConversionProjection, ...]:
    item = await _item(db, tenant_id=tenant_id, inventory_item_id=inventory_item_id)
    values = (await db.scalars(
        select(ItemUomConversion).where(
            ItemUomConversion.tenant_id == tenant_id,
            ItemUomConversion.inventory_item_id == item.id,
        ).order_by(ItemUomConversion.operational_uom, ItemUomConversion.revision)
    )).all()
    return tuple(_conversion_projection(value, item.base_uom) for value in values)


async def resolve_cost_as_of(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    as_of: datetime,
) -> InventoryCostRevision | None:
    return await db.scalar(
        select(InventoryCostRevision).where(
            InventoryCostRevision.tenant_id == tenant_id,
            InventoryCostRevision.inventory_item_id == inventory_item_id,
            InventoryCostRevision.effective_at <= as_of,
        ).order_by(
            InventoryCostRevision.effective_at.desc(),
            InventoryCostRevision.revision.desc(),
        ).limit(1)
    )


async def get_cost_as_of(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    as_of: datetime,
) -> InventoryCostRevisionProjection:
    await _item(db, tenant_id=tenant_id, inventory_item_id=inventory_item_id)
    value = await resolve_cost_as_of(
        db, tenant_id=tenant_id, inventory_item_id=inventory_item_id, as_of=as_of,
    )
    if value is None:
        raise errors.InventoryCostNotDerivableError(
            'No standard-cost revision applies at the requested time'
        )
    return _cost_projection(value)


async def list_cost_revisions(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
) -> tuple[InventoryCostRevisionProjection, ...]:
    await _item(db, tenant_id=tenant_id, inventory_item_id=inventory_item_id)
    values = (await db.scalars(
        select(InventoryCostRevision).where(
            InventoryCostRevision.tenant_id == tenant_id,
            InventoryCostRevision.inventory_item_id == inventory_item_id,
        ).order_by(InventoryCostRevision.revision)
    )).all()
    return tuple(_cost_projection(value) for value in values)


async def append_cost_revision(
    db: AsyncSession, *, item: InventoryItem, standard_unit_cost: Decimal,
    currency: str, effective_at: datetime, actor_id: int | None,
    source: str, reference: str | None,
) -> InventoryCostRevision:
    latest = await db.scalar(
        select(InventoryCostRevision).where(
            InventoryCostRevision.tenant_id == item.tenant_id,
            InventoryCostRevision.inventory_item_id == item.id,
        ).order_by(InventoryCostRevision.revision.desc()).limit(1).with_for_update()
    )
    if latest is not None and effective_at < latest.effective_at:
        if source == 'INVENTORY_ITEM_UPDATE':
            # A normal item PATCH means "effective now". Clamp database /
            # application clock skew to the latest instant; revision breaks
            # ties deterministically when effective timestamps are equal.
            effective_at = latest.effective_at
        else:
            raise errors.InvalidInventoryCostRevisionError(
                'Cost revisions cannot be backdated before the latest revision'
            )
    value = InventoryCostRevision(
        tenant_id=item.tenant_id, organization_id=item.organization_id,
        location_id=item.location_id, inventory_item_id=item.id,
        revision=1 if latest is None else latest.revision + 1,
        standard_unit_cost=standard_unit_cost, currency=currency,
        effective_at=effective_at, source=source, actor_id=actor_id,
        reference=reference.strip() if reference and reference.strip() else None,
    )
    db.add(value)
    return value


async def create_cost_revision(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    expected_version: int, standard_unit_cost: Decimal, currency: str,
    effective_at: datetime | None, actor_id: int, reference: str | None,
) -> InventoryCostRevisionProjection:
    item = await _item(
        db, tenant_id=tenant_id, inventory_item_id=inventory_item_id,
        for_update=True,
    )
    if item.version != expected_version:
        raise errors.InventoryItemVersionConflictError()
    standard_unit_cost = _cost(standard_unit_cost)
    currency = _currency(currency)
    if effective_at is None:
        effective_at = await _database_now(db)
    value = await append_cost_revision(
        db, item=item, standard_unit_cost=standard_unit_cost, currency=currency,
        effective_at=effective_at, actor_id=actor_id,
        source='STANDARD_COST_UPDATE', reference=reference,
    )
    item.standard_unit_cost = standard_unit_cost
    item.currency = currency
    item.version += 1
    try:
        await db.commit()
        await db.refresh(value)
        return _cost_projection(value)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.InventoryCostRevisionConflictError() from exc


async def resolve_quantity_evidence(
    db: AsyncSession, *, item: InventoryItem, quantity: Decimal,
    source_uom: str | None, as_of: datetime,
) -> tuple[Decimal, str, ItemUomConversion | None, Decimal]:
    try:
        quantity = exact_quantity(quantity)
    except UnitConversionError as exc:
        raise errors.InvalidStockMovementError(str(exc)) from exc
    normalized_uom = item.base_uom if source_uom is None else _operational_uom(source_uom)
    try:
        built_in = unit_code(normalized_uom)
    except UnitConversionError:
        built_in = None
    if built_in is not None:
        try:
            normalized = convert_quantity(
                quantity, from_uom=built_in, to_uom=item.base_uom,
            )
            factor = convert_quantity(
                Decimal('1'), from_uom=built_in, to_uom=item.base_uom,
            )
        except UnitConversionError as exc:
            raise errors.InvalidStockMovementError(str(exc)) from exc
        return normalized, normalized_uom, None, factor
    conversion = await db.scalar(
        select(ItemUomConversion).where(
            ItemUomConversion.tenant_id == item.tenant_id,
            ItemUomConversion.inventory_item_id == item.id,
            ItemUomConversion.operational_uom == normalized_uom,
            ItemUomConversion.effective_at <= as_of,
        ).order_by(
            ItemUomConversion.effective_at.desc(),
            ItemUomConversion.revision.desc(),
        ).limit(1)
    )
    if conversion is None:
        raise errors.ItemUomConversionNotFoundError(
            'No item conversion applies for the requested operational UOM'
        )
    try:
        normalized = convert_item_quantity(
            quantity, factor_to_base=conversion.factor_to_base,
        )
    except UnitConversionError as exc:
        raise errors.InvalidStockMovementError(str(exc)) from exc
    return normalized, normalized_uom, conversion, conversion.factor_to_base


async def create_inventory_item(
    db: AsyncSession, *, tenant_id: int, location_id: int, code: str, name: str,
    base_uom: str, standard_unit_cost: Decimal, currency: str, actor_id: int,
) -> InventoryItem:
    location = await _location(
        db, tenant_id=tenant_id, location_id=location_id, for_update=True,
    )
    await resolve_default_warehouse(
        db, tenant_id=tenant_id, location_id=location_id,
    )
    code = _text(code, field='Code', maximum=64).upper()
    name = _text(name, field='Name', maximum=200)
    try:
        base_uom = unit_code(base_uom).value
    except UnitConversionError as exc:
        raise errors.InvalidInventoryItemError(str(exc)) from exc
    standard_unit_cost = _cost(standard_unit_cost)
    currency = _currency(currency)
    value = InventoryItem(
        tenant_id=tenant_id,
        organization_id=location.organization_id,
        location_id=location.id,
        code=code,
        name=name,
        base_uom=base_uom,
        standard_unit_cost=standard_unit_cost,
        currency=currency,
        status='ACTIVE',
        version=1,
    )
    db.add(value)
    try:
        await db.flush()
        await append_cost_revision(
            db, item=value, standard_unit_cost=standard_unit_cost,
            currency=currency, effective_at=await _database_now(db), actor_id=actor_id,
            source='ITEM_CREATION', reference=None,
        )
        await db.commit()
        await db.refresh(value)
        return value
    except IntegrityError as exc:
        await db.rollback()
        duplicate = await db.scalar(
            select(InventoryItem.id).where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.location_id == location_id,
                InventoryItem.code == code,
            )
        )
        if duplicate is not None:
            raise errors.DuplicateInventoryItemCodeError() from exc
        raise


async def update_inventory_item(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    expected_version: int, name: str | None = None,
    standard_unit_cost: Decimal | None = None, currency: str | None = None,
    status: str | None = None, actor_id: int,
) -> InventoryItem:
    value = await _item(
        db, tenant_id=tenant_id, inventory_item_id=inventory_item_id,
        for_update=True,
    )
    if value.version != expected_version:
        current_version = value.version
        await db.rollback()
        raise errors.InventoryItemVersionConflictError(
            f'Expected version {expected_version}, current version is {current_version}'
        )
    if name is not None:
        value.name = _text(name, field='Name', maximum=200)
    resolved_cost = (
        _cost(standard_unit_cost)
        if standard_unit_cost is not None else value.standard_unit_cost
    )
    resolved_currency = _currency(currency) if currency is not None else value.currency
    cost_changed = (
        resolved_cost != value.standard_unit_cost
        or resolved_currency != value.currency
    )
    if cost_changed:
        await append_cost_revision(
            db, item=value, standard_unit_cost=resolved_cost,
            currency=resolved_currency, effective_at=await _database_now(db),
            actor_id=actor_id,
            source='INVENTORY_ITEM_UPDATE', reference=None,
        )
        value.standard_unit_cost = resolved_cost
        value.currency = resolved_currency
    if status is not None:
        status = status.strip().upper()
        if status not in ('ACTIVE', 'INACTIVE'):
            raise errors.InvalidInventoryItemError('Unsupported Inventory Item status')
        value.status = status
    value.version += 1
    try:
        await db.commit()
        await db.refresh(value)
        return value
    except Exception:
        await db.rollback()
        raise


async def list_inventory_items(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    status: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[InventoryItem, ...]:
    await _location(db, tenant_id=tenant_id, location_id=location_id)
    statement = select(InventoryItem).where(
        InventoryItem.tenant_id == tenant_id,
        InventoryItem.location_id == location_id,
    )
    if status is not None:
        statement = statement.where(InventoryItem.status == status)
    return tuple(
        (
            await db.execute(
                statement.order_by(InventoryItem.name, InventoryItem.id)
                .limit(limit).offset(offset)
            )
        ).scalars().all()
    )


async def _definition_projection(
    db: AsyncSession, definition: ProductConsumptionDefinition,
    version: ProductConsumptionVersion,
) -> ConsumptionDefinitionProjection:
    rows = (
        await db.execute(
            select(ProductConsumptionVersionComponent, InventoryItem)
            .join(
                InventoryItem,
                (InventoryItem.id == ProductConsumptionVersionComponent.inventory_item_id)
                & (InventoryItem.tenant_id == ProductConsumptionVersionComponent.tenant_id)
                & (InventoryItem.organization_id == ProductConsumptionVersionComponent.organization_id)
                & (InventoryItem.location_id == ProductConsumptionVersionComponent.location_id),
            )
            .where(
                ProductConsumptionVersionComponent.tenant_id == definition.tenant_id,
                ProductConsumptionVersionComponent.version_id == version.id,
            )
            .order_by(ProductConsumptionVersionComponent.inventory_item_id)
        )
    ).all()
    return ConsumptionDefinitionProjection(
        id=definition.id,
        product_id=definition.product_id,
        location_id=definition.location_id,
        version=definition.version,
        status=definition.status,
        tracking_mode=definition.tracking_mode,
        components=tuple(
            ConsumptionComponentProjection(
                inventory_item_id=item.id,
                inventory_item_code=item.code,
                inventory_item_name=item.name,
                quantity=component.quantity,
                base_uom=item.base_uom,
                source_quantity=component.source_quantity,
                source_uom=component.source_uom,
                conversion_revision_id=component.conversion_revision_id,
                conversion_factor=component.conversion_factor,
            )
            for component, item in rows
        ),
        recipe_version_id=version.id,
        recipe_revision=version.revision,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        published_at=version.published_at,
    )


async def resolve_consumption_version(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
    as_of: datetime, for_update: bool = False,
) -> tuple[ProductConsumptionDefinition, ProductConsumptionVersion] | None:
    statement = (
        select(ProductConsumptionDefinition, ProductConsumptionVersion)
        .join(
            ProductConsumptionVersion,
            (ProductConsumptionVersion.definition_id == ProductConsumptionDefinition.id)
            & (ProductConsumptionVersion.tenant_id == ProductConsumptionDefinition.tenant_id)
            & (ProductConsumptionVersion.location_id == ProductConsumptionDefinition.location_id),
        )
        .where(
            ProductConsumptionDefinition.tenant_id == tenant_id,
            ProductConsumptionDefinition.location_id == location_id,
            ProductConsumptionDefinition.product_id == product_id,
            ProductConsumptionVersion.publication_status == 'PUBLISHED',
            ProductConsumptionVersion.effective_from <= as_of,
            (
                ProductConsumptionVersion.effective_to.is_(None)
                | (ProductConsumptionVersion.effective_to > as_of)
            ),
        )
        .order_by(
            ProductConsumptionVersion.effective_from.desc(),
            ProductConsumptionVersion.revision.desc(),
        )
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    return (await db.execute(statement)).first()


async def get_consumption_definition(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
    as_of: datetime | None = None,
) -> ConsumptionDefinitionProjection:
    value = await resolve_consumption_version(
        db, tenant_id=tenant_id, product_id=product_id, location_id=location_id,
        as_of=as_of or await _database_now(db),
    )
    if value is None:
        raise errors.ConsumptionDefinitionNotFoundError()
    return await _definition_projection(db, value[0], value[1])


async def list_consumption_definition_versions(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
) -> tuple[ConsumptionDefinitionProjection, ...]:
    definition = await db.scalar(select(ProductConsumptionDefinition).where(
        ProductConsumptionDefinition.tenant_id == tenant_id,
        ProductConsumptionDefinition.location_id == location_id,
        ProductConsumptionDefinition.product_id == product_id,
    ))
    if definition is None:
        raise errors.ConsumptionDefinitionNotFoundError()
    versions = tuple((await db.scalars(select(ProductConsumptionVersion).where(
        ProductConsumptionVersion.tenant_id == tenant_id,
        ProductConsumptionVersion.definition_id == definition.id,
    ).order_by(ProductConsumptionVersion.revision))).all())
    return tuple(
        [await _definition_projection(db, definition, version) for version in versions]
    )


async def put_consumption_definition(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
    expected_version: int, status: str, tracking_mode: str,
    components: tuple[ConsumptionComponentInput, ...], effective_from: datetime | None,
    actor_id: int,
) -> ConsumptionDefinitionProjection:
    status = status.strip().upper()
    tracking_mode = tracking_mode.strip().upper()
    if status not in ('ACTIVE', 'INACTIVE'):
        raise errors.InvalidConsumptionDefinitionError('Unsupported definition status')
    if tracking_mode not in ('DERIVABLE', 'NON_DERIVABLE'):
        raise errors.InvalidConsumptionDefinitionError('Unsupported tracking mode')
    if tracking_mode == 'NON_DERIVABLE' and components:
        raise errors.InvalidConsumptionDefinitionError(
            'NON_DERIVABLE definitions cannot contain components'
        )
    ids = [component.inventory_item_id for component in components]
    if len(ids) != len(set(ids)):
        raise errors.InvalidConsumptionDefinitionError(
            'A definition cannot contain the same Inventory Item twice'
        )
    try:
        location = await _location(db, tenant_id=tenant_id, location_id=location_id)
        product = await db.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
                Product.organization_id == location.organization_id,
            ).with_for_update()
        )
        if product is None:
            raise errors.InventoryScopeNotFoundError('Product not found')
        definition = await db.scalar(
            select(ProductConsumptionDefinition).where(
                ProductConsumptionDefinition.tenant_id == tenant_id,
                ProductConsumptionDefinition.location_id == location_id,
                ProductConsumptionDefinition.product_id == product_id,
            ).with_for_update()
        )
        if definition is None:
            if expected_version != 0:
                raise errors.ConsumptionDefinitionVersionConflictError(
                    'Expected version must be 0 when creating a definition'
                )
            definition = ProductConsumptionDefinition(
                tenant_id=tenant_id,
                organization_id=location.organization_id,
                location_id=location_id,
                product_id=product_id,
                version=1,
                status=status,
                tracking_mode=tracking_mode,
            )
            db.add(definition)
            await db.flush()
        else:
            if definition.version != expected_version:
                raise errors.ConsumptionDefinitionVersionConflictError(
                    f'Expected version {expected_version}, current version is {definition.version}'
                )
            definition.version += 1
            definition.status = status
            definition.tracking_mode = tracking_mode
            await db.execute(
                delete(ProductConsumptionComponent).where(
                    ProductConsumptionComponent.definition_id == definition.id
                )
            )

        published_at = await _database_now(db)
        effective_from = effective_from or published_at
        latest = await db.scalar(
            select(ProductConsumptionVersion).where(
                ProductConsumptionVersion.tenant_id == tenant_id,
                ProductConsumptionVersion.definition_id == definition.id,
            ).order_by(ProductConsumptionVersion.revision.desc()).limit(1).with_for_update()
        )
        if latest is not None and effective_from < latest.effective_from:
            raise errors.InvalidConsumptionDefinitionError(
                'Recipe versions cannot be backdated before the latest version'
            )
        if latest is not None and latest.effective_to is None:
            latest.effective_to = effective_from
        recipe_version = ProductConsumptionVersion(
            tenant_id=tenant_id, organization_id=location.organization_id,
            location_id=location_id, definition_id=definition.id,
            revision=1 if latest is None else latest.revision + 1,
            status=status, tracking_mode=tracking_mode,
            publication_status='PUBLISHED', effective_from=effective_from,
            effective_to=None, actor_id=actor_id, source='CURRENT_DEFINITION_PUT',
            published_at=published_at,
        )
        db.add(recipe_version)
        await db.flush()

        items: dict[int, InventoryItem] = {}
        if ids:
            item_rows = tuple(
                (
                    await db.execute(
                        select(InventoryItem).where(
                            InventoryItem.tenant_id == tenant_id,
                            InventoryItem.organization_id == location.organization_id,
                            InventoryItem.location_id == location_id,
                            InventoryItem.id.in_(sorted(ids)),
                        ).order_by(InventoryItem.id).with_for_update()
                    )
                ).scalars().all()
            )
            items = {item.id: item for item in item_rows}
            if set(items) != set(ids):
                raise errors.InventoryItemNotFoundError(
                    'A recipe Inventory Item was not found in the Product location'
                )
            if any(item.status != 'ACTIVE' for item in item_rows):
                raise errors.InvalidConsumptionDefinitionError(
                    'A recipe cannot reference an inactive Inventory Item'
                )
        for component in components:
            try:
                quantity, source_uom, conversion, factor = await resolve_quantity_evidence(
                    db, item=items[component.inventory_item_id],
                    quantity=component.quantity, source_uom=component.uom,
                    as_of=effective_from,
                )
                exact_quantity(quantity, positive=True)
            except (UnitConversionError, errors.InventoryError) as exc:
                raise errors.InvalidConsumptionDefinitionError(str(exc)) from exc
            db.add(
                ProductConsumptionComponent(
                    tenant_id=tenant_id,
                    organization_id=location.organization_id,
                    location_id=location_id,
                    definition_id=definition.id,
                    inventory_item_id=component.inventory_item_id,
                    quantity=quantity,
                )
            )
            db.add(ProductConsumptionVersionComponent(
                tenant_id=tenant_id, organization_id=location.organization_id,
                location_id=location_id, definition_id=definition.id,
                version_id=recipe_version.id,
                inventory_item_id=component.inventory_item_id, quantity=quantity,
                source_quantity=component.quantity, source_uom=source_uom,
                conversion_revision_id=conversion.id if conversion is not None else None,
                conversion_factor=factor,
                base_uom_evidence=items[component.inventory_item_id].base_uom,
            ))
        await db.commit()
        await db.refresh(definition)
        return await _definition_projection(db, definition, recipe_version)
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(
            select(ProductConsumptionDefinition).where(
                ProductConsumptionDefinition.tenant_id == tenant_id,
                ProductConsumptionDefinition.location_id == location_id,
                ProductConsumptionDefinition.product_id == product_id,
            )
        )
        if winner is not None:
            raise errors.ConsumptionDefinitionVersionConflictError(
                'Consumption Definition was changed concurrently'
            ) from exc
        raise
    except Exception:
        await db.rollback()
        raise


def _actor_scope(context: ExecutionContext) -> str:
    if context.actor_type is ActorType.EMPLOYEE:
        return f'EMPLOYEE:{context.principal_id}'
    return f'{context.actor_type.value}:{context.principal_reference}'


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _movement_projection(value: StockMovement, base_uom: str) -> StockMovementProjection:
    return StockMovementProjection(
        id=value.id,
        inventory_item_id=value.inventory_item_id,
        location_id=value.location_id,
        warehouse_id=value.warehouse_id,
        movement_type=value.movement_type,
        quantity=value.quantity,
        base_uom=base_uom,
        reversal_of_movement_id=value.reversal_of_movement_id,
        reason=value.reason,
        reference=value.reference,
        recorded_at=value.recorded_at,
        actor_type=value.actor_type,
        actor_id=value.actor_id,
        actor_reference=value.actor_reference,
        negative_stock_policy=value.negative_stock_policy,
        negative_stock_warning=value.negative_stock_warning,
        resulting_stock_quantity=value.resulting_stock_quantity,
        source_quantity=value.source_quantity,
        source_uom=value.source_uom,
        conversion_revision_id=value.conversion_revision_id,
        conversion_factor=value.conversion_factor,
        base_uom_evidence=value.base_uom_evidence,
        standard_cost_revision_id=value.standard_cost_revision_id,
        standard_unit_cost_evidence=value.standard_unit_cost_evidence,
        cost_currency_evidence=value.cost_currency_evidence,
        extended_standard_cost=value.extended_standard_cost,
        evidence_status=value.evidence_status,
    )


async def create_stock_movement(
    db: AsyncSession, *, context: ExecutionContext, inventory_item_id: int,
    warehouse_id: int | None,
    movement_type: str, quantity: Decimal | None, uom: str | None,
    reversal_of_movement_id: int | None,
    reason: str | None, reference: str | None, idempotency_key: str,
) -> tuple[StockMovementProjection, bool]:
    if context.actor_type is not ActorType.EMPLOYEE:
        raise errors.InvalidStockMovementError('Manual movement requires an employee actor')
    movement_type = movement_type.strip().upper()
    if movement_type not in MANUAL_MOVEMENT_TYPES:
        raise errors.InvalidStockMovementError('Movement type is not manually creatable')
    reason = reason.strip() if reason is not None and reason.strip() else None
    reference = reference.strip() if reference is not None and reference.strip() else None
    if reason is not None and len(reason) > 500:
        raise errors.InvalidStockMovementError('Reason exceeds 500 characters')
    if reference is not None and len(reference) > 200:
        raise errors.InvalidStockMovementError('Reference exceeds 200 characters')
    if movement_type != 'OPENING_BALANCE' and reason is None:
        raise errors.InvalidStockMovementError('Reason is required for this movement type')
    if movement_type == 'REVERSAL':
        if reversal_of_movement_id is None or quantity is not None or uom is not None:
            raise errors.InvalidStockMovementError(
                'REVERSAL requires only reversal_of_movement_id and derives its evidence'
            )
    elif reversal_of_movement_id is not None or quantity is None:
        raise errors.InvalidStockMovementError(
            'Only REVERSAL may reference another movement'
        )
    requested_quantity = str(quantity) if quantity is not None else None
    fingerprint_payload = {
        'schema_version': REQUEST_SCHEMA_VERSION,
        'inventory_item_id': inventory_item_id,
        'movement_type': movement_type,
        'quantity': requested_quantity,
        'reversal_of_movement_id': reversal_of_movement_id,
        'reason': reason,
        'reference': reference,
    }
    if warehouse_id is not None:
        fingerprint_payload['warehouse_id'] = warehouse_id
    if uom is not None:
        fingerprint_payload['uom'] = _operational_uom(uom)
    fingerprint = _fingerprint(fingerprint_payload)
    actor_scope = _actor_scope(context)
    replay = await db.scalar(
        select(StockMovement).where(
            StockMovement.tenant_id == context.tenant_id,
            StockMovement.idempotency_actor_scope == actor_scope,
            StockMovement.idempotency_key == idempotency_key,
        )
    )
    if replay is not None:
        if replay.request_fingerprint != fingerprint:
            raise errors.StockMovementIdempotencyConflictError()
        item = await _item(
            db, tenant_id=context.tenant_id,
            inventory_item_id=replay.inventory_item_id,
        )
        return _movement_projection(replay, item.base_uom), True

    try:
        uncommitted_item = await _item(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
        )
        warehouse = await _warehouse_for_scope(
            db, tenant_id=uncommitted_item.tenant_id,
            organization_id=uncommitted_item.organization_id,
            location_id=uncommitted_item.location_id,
            warehouse_id=warehouse_id, for_update=True,
        )
        item = await _item(
            db, tenant_id=context.tenant_id,
            inventory_item_id=inventory_item_id, for_update=True,
        )
        if movement_type != 'REVERSAL' and warehouse.status != 'ACTIVE':
            raise errors.InvalidStockMovementError(
                'Cannot create a new movement in an inactive Warehouse'
            )
        if movement_type != 'REVERSAL' and item.status != 'ACTIVE':
            raise errors.InvalidStockMovementError(
                'Cannot create a new movement for an inactive Inventory Item'
            )
        replay = await db.scalar(
            select(StockMovement).where(
                StockMovement.tenant_id == context.tenant_id,
                StockMovement.idempotency_actor_scope == actor_scope,
                StockMovement.idempotency_key == idempotency_key,
            ).with_for_update()
        )
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise errors.StockMovementIdempotencyConflictError()
            await db.commit()
            return _movement_projection(replay, item.base_uom), True

        recorded_at = await _database_now(db)
        if movement_type == 'REVERSAL':
            original = await db.scalar(
                select(StockMovement).where(
                    StockMovement.id == reversal_of_movement_id,
                    StockMovement.tenant_id == context.tenant_id,
                    StockMovement.inventory_item_id == item.id,
                    StockMovement.warehouse_id == warehouse.id,
                ).with_for_update()
            )
            if original is None:
                raise errors.StockMovementNotFoundError('Original movement not found')
            if original.movement_type == 'REVERSAL':
                raise errors.InvalidStockMovementError('A reversal cannot be reversed')
            prior = await db.scalar(
                select(StockMovement.id).where(
                    StockMovement.reversal_of_movement_id == original.id
                ).with_for_update()
            )
            if prior is not None:
                raise errors.StockMovementAlreadyReversedError()
            normalized_quantity = -original.quantity
            source_quantity = (
                -original.source_quantity
                if original.source_quantity is not None else None
            )
            source_uom = original.source_uom
            conversion = None
            conversion_revision_id = original.conversion_revision_id
            resolved_factor = original.conversion_factor
            cost_revision = None
            cost_revision_id = original.standard_cost_revision_id
            unit_cost_evidence = original.standard_unit_cost_evidence
            cost_currency = original.cost_currency_evidence
            extended_cost = (
                -original.extended_standard_cost
                if original.extended_standard_cost is not None else None
            )
            evidence_status = original.evidence_status
        else:
            try:
                source_quantity = exact_quantity(quantity)  # type: ignore[arg-type]
            except UnitConversionError as exc:
                raise errors.InvalidStockMovementError(str(exc)) from exc
            (
                normalized_quantity, source_uom, conversion, resolved_factor,
            ) = await resolve_quantity_evidence(
                db, item=item, quantity=source_quantity,
                source_uom=uom, as_of=recorded_at,
            )
            conversion_revision_id = conversion.id if conversion is not None else None
            cost_revision = await resolve_cost_as_of(
                db, tenant_id=item.tenant_id, inventory_item_id=item.id,
                as_of=recorded_at,
            )
            cost_revision_id = cost_revision.id if cost_revision is not None else None
            unit_cost_evidence = (
                cost_revision.standard_unit_cost if cost_revision is not None else None
            )
            cost_currency = cost_revision.currency if cost_revision is not None else None
            extended_cost = (
                (normalized_quantity * unit_cost_evidence).quantize(
                    Decimal('0.000000000001')
                )
                if unit_cost_evidence is not None else None
            )
            evidence_status = 'RESOLVED' if cost_revision is not None else 'COST_NON_DERIVABLE'
            valid_sign = (
                movement_type in ('OPENING_BALANCE', 'MANUAL_IN')
                and normalized_quantity > _ZERO
            ) or (
                movement_type == 'MANUAL_OUT' and normalized_quantity < _ZERO
            ) or (
                movement_type == 'ADJUSTMENT' and normalized_quantity != _ZERO
            )
            if not valid_sign:
                raise errors.InvalidStockMovementError('Movement quantity has the wrong sign')

        current_quantity = await stock_quantity(
            db, tenant_id=item.tenant_id, warehouse_id=warehouse.id,
            inventory_item_id=item.id,
        )
        resulting_quantity = (current_quantity + normalized_quantity).quantize(
            QUANTITY_UNIT
        )
        warning = (
            resulting_quantity < _ZERO
            and warehouse.negative_stock_policy in ('WARN', 'BLOCK')
        )
        if (
            warehouse.negative_stock_policy == 'BLOCK'
            and normalized_quantity < _ZERO
            and movement_type != 'REVERSAL'
            and resulting_quantity < _ZERO
        ):
            raise errors.NegativeStockBlockedError(
                'Movement would make warehouse stock negative'
            )

        movement = StockMovement(
            tenant_id=item.tenant_id,
            organization_id=item.organization_id,
            location_id=item.location_id,
            warehouse_id=warehouse.id,
            inventory_item_id=item.id,
            movement_type=movement_type,
            quantity=normalized_quantity,
            reversal_of_movement_id=reversal_of_movement_id,
            reason=reason,
            reference=reference,
            recorded_at=recorded_at,
            actor_type=context.actor_type.value,
            actor_id=context.principal_id,
            actor_reference=context.principal_reference,
            opening_balance_slot=1 if movement_type == 'OPENING_BALANCE' else None,
            idempotency_actor_scope=actor_scope,
            idempotency_key=idempotency_key,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=fingerprint,
            negative_stock_policy=warehouse.negative_stock_policy,
            negative_stock_warning=warning,
            resulting_stock_quantity=resulting_quantity,
            source_quantity=source_quantity,
            source_uom=source_uom,
            conversion_revision_id=conversion_revision_id,
            conversion_factor=resolved_factor,
            base_uom_evidence=(
                original.base_uom_evidence
                if movement_type == 'REVERSAL' else item.base_uom
            ),
            standard_cost_revision_id=cost_revision_id,
            standard_unit_cost_evidence=unit_cost_evidence,
            cost_currency_evidence=cost_currency,
            extended_standard_cost=extended_cost,
            evidence_status=evidence_status,
        )
        db.add(movement)
        await db.commit()
        await db.refresh(movement)
        return _movement_projection(movement, item.base_uom), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(
            select(StockMovement).where(
                StockMovement.tenant_id == context.tenant_id,
                StockMovement.idempotency_actor_scope == actor_scope,
                StockMovement.idempotency_key == idempotency_key,
            )
        )
        if winner is not None:
            if winner.request_fingerprint != fingerprint:
                raise errors.StockMovementIdempotencyConflictError() from exc
            item = await _item(
                db, tenant_id=context.tenant_id,
                inventory_item_id=winner.inventory_item_id,
            )
            return _movement_projection(winner, item.base_uom), True
        if movement_type == 'OPENING_BALANCE':
            raise errors.DuplicateOpeningBalanceError() from exc
        if movement_type == 'REVERSAL':
            raise errors.StockMovementAlreadyReversedError() from exc
        raise
    except Exception:
        await db.rollback()
        raise


async def list_stock(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    inventory_item_id: int | None = None, warehouse_id: int | None = None,
) -> tuple[StockProjection, ...]:
    location = await _location(db, tenant_id=tenant_id, location_id=location_id)
    warehouse = await _warehouse_for_scope(
        db, tenant_id=tenant_id, organization_id=location.organization_id,
        location_id=location_id, warehouse_id=warehouse_id,
    )
    await db.commit()
    balance = (
        select(func.coalesce(func.sum(StockMovement.quantity), 0))
        .where(
            StockMovement.tenant_id == InventoryItem.tenant_id,
            StockMovement.location_id == InventoryItem.location_id,
            StockMovement.warehouse_id == warehouse.id,
            StockMovement.inventory_item_id == InventoryItem.id,
        )
        .correlate(InventoryItem)
        .scalar_subquery()
    )
    statement = select(InventoryItem, balance).where(
        InventoryItem.tenant_id == tenant_id,
        InventoryItem.location_id == location_id,
    )
    if inventory_item_id is not None:
        statement = statement.where(InventoryItem.id == inventory_item_id)
    rows = (await db.execute(statement.order_by(InventoryItem.id))).all()
    return tuple(
        StockProjection(
            inventory_item_id=item.id,
            code=item.code,
            name=item.name,
            location_id=item.location_id,
            warehouse_id=warehouse.id,
            base_uom=item.base_uom,
            quantity=quantity.quantize(QUANTITY_UNIT),
        )
        for item, quantity in rows
    )


async def list_stock_movements(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    inventory_item_id: int | None = None, warehouse_id: int | None = None,
    limit: int = 50, offset: int = 0,
) -> tuple[StockMovementProjection, ...]:
    location = await _location(db, tenant_id=tenant_id, location_id=location_id)
    warehouse = await _warehouse_for_scope(
        db, tenant_id=tenant_id, organization_id=location.organization_id,
        location_id=location_id, warehouse_id=warehouse_id,
    )
    await db.commit()
    statement = (
        select(StockMovement, InventoryItem.base_uom)
        .join(
            InventoryItem,
            (InventoryItem.id == StockMovement.inventory_item_id)
            & (InventoryItem.tenant_id == StockMovement.tenant_id),
        )
        .where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.location_id == location_id,
            StockMovement.warehouse_id == warehouse.id,
        )
    )
    if inventory_item_id is not None:
        statement = statement.where(StockMovement.inventory_item_id == inventory_item_id)
    rows = (
        await db.execute(
            statement.order_by(StockMovement.recorded_at, StockMovement.id)
            .limit(limit).offset(offset)
        )
    ).all()
    return tuple(_movement_projection(movement, base_uom) for movement, base_uom in rows)


async def resolve_current_product_cost(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
) -> ProductCostProjection:
    as_of = await _database_now(db)
    resolved = await resolve_consumption_version(
        db, tenant_id=tenant_id, product_id=product_id,
        location_id=location_id, as_of=as_of,
    )
    if resolved is None or resolved[1].status != 'ACTIVE':
        raise errors.ConsumptionDefinitionNotFoundError()
    definition, recipe_version = resolved
    if recipe_version.tracking_mode == 'NON_DERIVABLE':
        return ProductCostProjection(
            product_id=product_id,
            location_id=location_id,
            definition_version=recipe_version.revision,
            tracking_mode=recipe_version.tracking_mode,
            cost_status='NON_DERIVABLE',
            currency=None,
            components=(),
            total_theoretical_cost=None,
        )
    rows = (
        await db.execute(
            select(ProductConsumptionVersionComponent, InventoryItem)
            .join(
                InventoryItem,
                (InventoryItem.id == ProductConsumptionVersionComponent.inventory_item_id)
                & (InventoryItem.tenant_id == ProductConsumptionVersionComponent.tenant_id),
            )
            .where(
                ProductConsumptionVersionComponent.tenant_id == tenant_id,
                ProductConsumptionVersionComponent.version_id == recipe_version.id,
            )
            .order_by(ProductConsumptionVersionComponent.inventory_item_id)
        )
    ).all()
    resolved_rows = []
    for component, item in rows:
        revision = await resolve_cost_as_of(
            db, tenant_id=tenant_id, inventory_item_id=item.id, as_of=as_of,
        )
        if revision is None:
            return ProductCostProjection(
                product_id=product_id, location_id=location_id,
                definition_version=recipe_version.revision,
                tracking_mode=recipe_version.tracking_mode,
                cost_status='NON_DERIVABLE', currency=None, components=(),
                total_theoretical_cost=None,
            )
        resolved_rows.append((component, item, revision))
    components = tuple(
        CostComponentProjection(
            inventory_item_id=item.id, inventory_item_code=item.code,
            inventory_item_name=item.name, quantity=component.quantity,
            base_uom=item.base_uom,
            standard_unit_cost=revision.standard_unit_cost,
            currency=revision.currency,
            theoretical_cost=component.quantity * revision.standard_unit_cost,
        )
        for component, item, revision in resolved_rows
    )
    currencies = {component.currency for component in components}
    if len(currencies) > 1:
        return ProductCostProjection(
            product_id=product_id,
            location_id=location_id,
            definition_version=recipe_version.revision,
            tracking_mode=recipe_version.tracking_mode,
            cost_status='CURRENCY_MISMATCH',
            currency=None,
            components=components,
            total_theoretical_cost=None,
        )
    currency = next(iter(currencies), None)
    return ProductCostProjection(
        product_id=product_id,
        location_id=location_id,
        definition_version=recipe_version.revision,
        tracking_mode=recipe_version.tracking_mode,
        cost_status='RESOLVED',
        currency=currency,
        components=components,
        total_theoretical_cost=sum(
            (component.theoretical_cost for component in components), _ZERO
        ),
    )
