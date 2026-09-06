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
    InventoryItem,
    Location,
    Product,
    ProductConsumptionComponent,
    ProductConsumptionDefinition,
    StockMovement,
)
from app.restaurant.inventory import errors
from app.restaurant.inventory.contracts import (
    ConsumptionComponentInput,
    ConsumptionComponentProjection,
    ConsumptionDefinitionProjection,
    CostComponentProjection,
    ProductCostProjection,
    StockMovementProjection,
    StockProjection,
)
from app.restaurant.inventory.units import (
    QUANTITY_UNIT,
    UnitConversionError,
    convert_quantity,
    exact_quantity,
    unit_code,
)


REQUEST_SCHEMA_VERSION = 1
MANUAL_MOVEMENT_TYPES = frozenset(
    {'OPENING_BALANCE', 'MANUAL_IN', 'MANUAL_OUT', 'ADJUSTMENT', 'REVERSAL'}
)
_CURRENCY = re.compile(r'^[A-Z]{3}$')
_ZERO = Decimal('0')


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
    db: AsyncSession, *, tenant_id: int, location_id: int
) -> Location:
    value = await db.scalar(
        select(Location).where(
            Location.id == location_id, Location.tenant_id == tenant_id
        )
    )
    if value is None:
        raise errors.InventoryScopeNotFoundError('Location not found')
    return value


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


async def create_inventory_item(
    db: AsyncSession, *, tenant_id: int, location_id: int, code: str, name: str,
    base_uom: str, standard_unit_cost: Decimal, currency: str,
) -> InventoryItem:
    location = await _location(db, tenant_id=tenant_id, location_id=location_id)
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
    status: str | None = None,
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
    if standard_unit_cost is not None:
        value.standard_unit_cost = _cost(standard_unit_cost)
    if currency is not None:
        value.currency = _currency(currency)
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
    db: AsyncSession, definition: ProductConsumptionDefinition
) -> ConsumptionDefinitionProjection:
    rows = (
        await db.execute(
            select(ProductConsumptionComponent, InventoryItem)
            .join(
                InventoryItem,
                (InventoryItem.id == ProductConsumptionComponent.inventory_item_id)
                & (InventoryItem.tenant_id == ProductConsumptionComponent.tenant_id)
                & (InventoryItem.organization_id == ProductConsumptionComponent.organization_id)
                & (InventoryItem.location_id == ProductConsumptionComponent.location_id),
            )
            .where(
                ProductConsumptionComponent.tenant_id == definition.tenant_id,
                ProductConsumptionComponent.definition_id == definition.id,
            )
            .order_by(ProductConsumptionComponent.inventory_item_id)
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
            )
            for component, item in rows
        ),
    )


async def get_consumption_definition(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
) -> ConsumptionDefinitionProjection:
    value = await db.scalar(
        select(ProductConsumptionDefinition).where(
            ProductConsumptionDefinition.tenant_id == tenant_id,
            ProductConsumptionDefinition.location_id == location_id,
            ProductConsumptionDefinition.product_id == product_id,
        )
    )
    if value is None:
        raise errors.ConsumptionDefinitionNotFoundError()
    return await _definition_projection(db, value)


async def put_consumption_definition(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
    expected_version: int, status: str, tracking_mode: str,
    components: tuple[ConsumptionComponentInput, ...],
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
                quantity = convert_quantity(
                    component.quantity,
                    from_uom=component.uom,
                    to_uom=items[component.inventory_item_id].base_uom,
                )
                exact_quantity(quantity, positive=True)
            except UnitConversionError as exc:
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
        await db.commit()
        await db.refresh(definition)
        return await _definition_projection(db, definition)
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
    )


async def create_stock_movement(
    db: AsyncSession, *, context: ExecutionContext, inventory_item_id: int,
    movement_type: str, quantity: Decimal | None, reversal_of_movement_id: int | None,
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
        if reversal_of_movement_id is None or quantity is not None:
            raise errors.InvalidStockMovementError(
                'REVERSAL requires reversal_of_movement_id and derives its quantity'
            )
    elif reversal_of_movement_id is not None or quantity is None:
        raise errors.InvalidStockMovementError(
            'Only REVERSAL may reference another movement'
        )
    requested_quantity = str(quantity) if quantity is not None else None
    fingerprint = _fingerprint(
        {
            'schema_version': REQUEST_SCHEMA_VERSION,
            'inventory_item_id': inventory_item_id,
            'movement_type': movement_type,
            'quantity': requested_quantity,
            'reversal_of_movement_id': reversal_of_movement_id,
            'reason': reason,
            'reference': reference,
        }
    )
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
        item = await _item(
            db, tenant_id=context.tenant_id,
            inventory_item_id=inventory_item_id,
            for_update=movement_type in ('OPENING_BALANCE', 'REVERSAL'),
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

        if movement_type == 'REVERSAL':
            original = await db.scalar(
                select(StockMovement).where(
                    StockMovement.id == reversal_of_movement_id,
                    StockMovement.tenant_id == context.tenant_id,
                    StockMovement.inventory_item_id == item.id,
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
        else:
            try:
                normalized_quantity = exact_quantity(quantity)  # type: ignore[arg-type]
            except UnitConversionError as exc:
                raise errors.InvalidStockMovementError(str(exc)) from exc
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

        movement = StockMovement(
            tenant_id=item.tenant_id,
            organization_id=item.organization_id,
            location_id=item.location_id,
            inventory_item_id=item.id,
            movement_type=movement_type,
            quantity=normalized_quantity,
            reversal_of_movement_id=reversal_of_movement_id,
            reason=reason,
            reference=reference,
            recorded_at=_now(),
            actor_type=context.actor_type.value,
            actor_id=context.principal_id,
            actor_reference=context.principal_reference,
            opening_balance_slot=1 if movement_type == 'OPENING_BALANCE' else None,
            idempotency_actor_scope=actor_scope,
            idempotency_key=idempotency_key,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=fingerprint,
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
    inventory_item_id: int | None = None,
) -> tuple[StockProjection, ...]:
    await _location(db, tenant_id=tenant_id, location_id=location_id)
    balance = (
        select(func.coalesce(func.sum(StockMovement.quantity), 0))
        .where(
            StockMovement.tenant_id == InventoryItem.tenant_id,
            StockMovement.location_id == InventoryItem.location_id,
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
            base_uom=item.base_uom,
            quantity=quantity.quantize(QUANTITY_UNIT),
        )
        for item, quantity in rows
    )


async def list_stock_movements(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    inventory_item_id: int | None = None, limit: int = 50, offset: int = 0,
) -> tuple[StockMovementProjection, ...]:
    await _location(db, tenant_id=tenant_id, location_id=location_id)
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
    definition = await db.scalar(
        select(ProductConsumptionDefinition).where(
            ProductConsumptionDefinition.tenant_id == tenant_id,
            ProductConsumptionDefinition.location_id == location_id,
            ProductConsumptionDefinition.product_id == product_id,
            ProductConsumptionDefinition.status == 'ACTIVE',
        )
    )
    if definition is None:
        raise errors.ConsumptionDefinitionNotFoundError()
    if definition.tracking_mode == 'NON_DERIVABLE':
        return ProductCostProjection(
            product_id=product_id,
            location_id=location_id,
            definition_version=definition.version,
            tracking_mode=definition.tracking_mode,
            cost_status='NON_DERIVABLE',
            currency=None,
            components=(),
            total_theoretical_cost=None,
        )
    rows = (
        await db.execute(
            select(ProductConsumptionComponent, InventoryItem)
            .join(
                InventoryItem,
                (InventoryItem.id == ProductConsumptionComponent.inventory_item_id)
                & (InventoryItem.tenant_id == ProductConsumptionComponent.tenant_id),
            )
            .where(
                ProductConsumptionComponent.tenant_id == tenant_id,
                ProductConsumptionComponent.definition_id == definition.id,
            )
            .order_by(ProductConsumptionComponent.inventory_item_id)
        )
    ).all()
    components = tuple(
        CostComponentProjection(
            inventory_item_id=item.id,
            inventory_item_code=item.code,
            inventory_item_name=item.name,
            quantity=component.quantity,
            base_uom=item.base_uom,
            standard_unit_cost=item.standard_unit_cost,
            currency=item.currency,
            theoretical_cost=component.quantity * item.standard_unit_cost,
        )
        for component, item in rows
    )
    currencies = {component.currency for component in components}
    if len(currencies) > 1:
        return ProductCostProjection(
            product_id=product_id,
            location_id=location_id,
            definition_version=definition.version,
            tracking_mode=definition.tracking_mode,
            cost_status='CURRENCY_MISMATCH',
            currency=None,
            components=components,
            total_theoretical_cost=None,
        )
    currency = next(iter(currencies), None)
    return ProductCostProjection(
        product_id=product_id,
        location_id=location_id,
        definition_version=definition.version,
        tracking_mode=definition.tracking_mode,
        cost_status='RESOLVED',
        currency=currency,
        components=components,
        total_theoretical_cost=sum(
            (component.theoretical_cost for component in components), _ZERO
        ),
    )
