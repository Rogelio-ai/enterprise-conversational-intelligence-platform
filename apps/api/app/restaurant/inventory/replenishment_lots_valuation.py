from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models.inventory import (
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryCostRevision,
    InventoryItem,
    InventoryLot,
    InventoryValuationSnapshot,
    InventoryValuationSnapshotLine,
    PurchaseOrder,
    PurchaseOrderLine,
    ReplenishmentPolicy,
    StockMovement,
    Warehouse,
)
from app.restaurant.inventory import errors, service
from app.restaurant.inventory.units import QUANTITY_UNIT, UnitConversionError, exact_quantity


ZERO = Decimal('0')
VALUE_UNIT = Decimal('0.000000000001')


class B10Error(errors.InventoryError):
    code = 'INVENTORY_B10_CONFLICT'


class B10NotFound(B10Error):
    code = 'INVENTORY_B10_NOT_FOUND'


def _actor(context: ExecutionContext) -> int:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise B10Error('B10 staff operation requires an employee actor')
    return context.principal_id


def _actor_scope(context: ExecutionContext) -> str:
    return f'EMPLOYEE:{_actor(context)}'


async def _now(db: AsyncSession) -> datetime:
    value = await db.scalar(select(func.current_timestamp()))
    assert value is not None
    return value.replace(microsecond=0)


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


async def _scope(
    db: AsyncSession, tenant_id: int, warehouse_id: int, inventory_item_id: int | None = None,
    *, for_update: bool = False,
) -> tuple[Warehouse, InventoryItem | None]:
    warehouse_query = select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id)
    if for_update:
        warehouse_query = warehouse_query.with_for_update()
    warehouse = await db.scalar(warehouse_query)
    if warehouse is None:
        raise B10NotFound('Warehouse not found')
    item = None
    if inventory_item_id is not None:
        item_query = select(InventoryItem).where(
            InventoryItem.id == inventory_item_id,
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.organization_id == warehouse.organization_id,
            InventoryItem.location_id == warehouse.location_id,
        )
        if for_update:
            item_query = item_query.with_for_update()
        item = await db.scalar(item_query)
        if item is None:
            raise B10NotFound('Inventory Item not found')
    return warehouse, item


async def _on_order(db: AsyncSession, policy: ReplenishmentPolicy) -> Decimal:
    rows = (await db.scalars(
        select(PurchaseOrderLine).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id).where(
            PurchaseOrder.tenant_id == policy.tenant_id,
            PurchaseOrder.warehouse_id == policy.warehouse_id,
            PurchaseOrderLine.inventory_item_id == policy.inventory_item_id,
            PurchaseOrder.status.in_(('APPROVED', 'PARTIALLY_RECEIVED')),
        )
    )).all()
    total = ZERO
    for row in rows:
        received = Decimal(await db.scalar(
            select(func.coalesce(func.sum(GoodsReceiptLine.normalized_quantity), ZERO))
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id)
            .where(GoodsReceipt.status == 'ACCEPTED', GoodsReceiptLine.purchase_order_line_id == row.id)
        ) or ZERO)
        total += max(Decimal(row.normalized_ordered_quantity) - received, ZERO)
    return total.quantize(QUANTITY_UNIT)


async def project_policy(db: AsyncSession, value: ReplenishmentPolicy) -> dict:
    on_hand = Decimal(await db.scalar(select(func.coalesce(func.sum(StockMovement.quantity), ZERO)).where(
        StockMovement.tenant_id == value.tenant_id,
        StockMovement.warehouse_id == value.warehouse_id,
        StockMovement.inventory_item_id == value.inventory_item_id,
    )) or ZERO).quantize(QUANTITY_UNIT)
    on_order = await _on_order(db, value)
    suggested = (
        max(Decimal(value.normalized_target_quantity) - on_hand, ZERO).quantize(QUANTITY_UNIT)
        if value.status == 'ACTIVE' and value.normalized_target_quantity is not None else ZERO.quantize(QUANTITY_UNIT)
    )
    return {
        'id': value.id, 'location_id': value.location_id, 'warehouse_id': value.warehouse_id,
        'inventory_item_id': value.inventory_item_id, 'status': value.status,
        'minimum_quantity': _decimal(value.minimum_quantity), 'target_quantity': _decimal(value.target_quantity),
        'source_uom': value.source_uom, 'conversion_factor': _decimal(value.conversion_factor),
        'base_uom_evidence': value.base_uom_evidence,
        'normalized_minimum_quantity': _decimal(value.normalized_minimum_quantity),
        'normalized_target_quantity': _decimal(value.normalized_target_quantity),
        'on_hand': _decimal(on_hand), 'on_order': _decimal(on_order), 'suggested_quantity': _decimal(suggested),
        'version': value.version, 'actor_id': value.actor_id,
        'created_at': value.created_at, 'updated_at': value.updated_at,
    }


async def put_policy(
    db: AsyncSession, *, context: ExecutionContext, warehouse_id: int, inventory_item_id: int,
    expected_version: int, status: str, minimum_quantity: Decimal | None,
    target_quantity: Decimal | None, source_uom: str,
) -> dict:
    actor = _actor(context)
    warehouse, item = await _scope(db, context.tenant_id, warehouse_id, inventory_item_id, for_update=True)
    assert item is not None
    status = status.strip().upper()
    if status not in ('ACTIVE', 'INACTIVE'):
        raise B10Error('Unsupported replenishment policy status')
    if minimum_quantity is None and target_quantity is None:
        raise B10Error('Minimum or target quantity is required')
    now = await _now(db)
    try:
        minimum = exact_quantity(minimum_quantity) if minimum_quantity is not None else None
        target = exact_quantity(target_quantity) if target_quantity is not None else None
        if minimum is not None and minimum < ZERO or target is not None and target < ZERO:
            raise B10Error('Replenishment quantities cannot be negative')
        if minimum is not None and target is not None and target < minimum:
            raise B10Error('Target quantity cannot be below minimum quantity')
        normalized_minimum = conversion = None
        normalized_target = None
        factor = Decimal('1')
        normalized_uom = source_uom
        if minimum is not None:
            normalized_minimum, normalized_uom, conversion, factor = await service.resolve_quantity_evidence(db, item=item, quantity=minimum, source_uom=source_uom, as_of=now)
        if target is not None:
            normalized_target, normalized_uom, target_conversion, factor = await service.resolve_quantity_evidence(db, item=item, quantity=target, source_uom=source_uom, as_of=now)
            conversion = target_conversion or conversion
    except UnitConversionError as exc:
        raise B10Error(str(exc)) from exc
    value = await db.scalar(select(ReplenishmentPolicy).where(
        ReplenishmentPolicy.warehouse_id == warehouse.id,
        ReplenishmentPolicy.inventory_item_id == item.id,
    ).with_for_update())
    if value is None:
        if expected_version != 0:
            raise B10Error('Replenishment policy does not exist')
        value = ReplenishmentPolicy(
            tenant_id=context.tenant_id, organization_id=warehouse.organization_id,
            location_id=warehouse.location_id, warehouse_id=warehouse.id,
            inventory_item_id=item.id, version=1, actor_id=actor,
        )
        db.add(value)
    else:
        if value.version != expected_version:
            raise B10Error(f'Expected version {expected_version}, current version is {value.version}')
        value.version += 1
        value.actor_id = actor
    value.status = status
    value.minimum_quantity = minimum
    value.target_quantity = target
    value.source_uom = normalized_uom
    value.conversion_revision_id = conversion.id if conversion else None
    value.conversion_factor = factor
    value.base_uom_evidence = item.base_uom
    value.normalized_minimum_quantity = normalized_minimum
    value.normalized_target_quantity = normalized_target
    try:
        await db.commit(); await db.refresh(value)
        return await project_policy(db, value)
    except IntegrityError as exc:
        await db.rollback(); raise B10Error('Replenishment policy conflict') from exc
    except Exception:
        await db.rollback(); raise


async def list_policies(db: AsyncSession, tenant_id: int, location_id: int) -> list[dict]:
    values = (await db.scalars(select(ReplenishmentPolicy).where(
        ReplenishmentPolicy.tenant_id == tenant_id,
        ReplenishmentPolicy.location_id == location_id,
    ).order_by(ReplenishmentPolicy.inventory_item_id))).all()
    return [await project_policy(db, value) for value in values]


def validate_lot_dates(item: InventoryItem, manufacture_date: date | None, expiry_date: date | None, best_before_date: date | None) -> None:
    policy = item.date_tracking_policy
    if policy in ('EXPIRY', 'BOTH') and expiry_date is None:
        raise B10Error('Expiry date is required by Inventory Item policy')
    if policy in ('BEST_BEFORE', 'BOTH') and best_before_date is None:
        raise B10Error('Best-before date is required by Inventory Item policy')
    for value in (expiry_date, best_before_date):
        if manufacture_date is not None and value is not None and value < manufacture_date:
            raise B10Error('Tracked date cannot precede manufacture date')


async def create_origin_lot(
    db: AsyncSession, *, item: InventoryItem, warehouse: Warehouse, origin_type: str,
    origin_id: int, lot_code: str | None, origin_at: datetime,
    manufacture_date: date | None, expiry_date: date | None, best_before_date: date | None,
    original_quantity: Decimal, source_quantity: Decimal, source_uom: str,
    conversion_revision_id: int | None, conversion_factor: Decimal, base_uom_evidence: str,
    unit_cost_evidence: Decimal | None, cost_currency_evidence: str | None,
) -> InventoryLot | None:
    validate_lot_dates(item, manufacture_date, expiry_date, best_before_date)
    if not lot_code:
        if item.lot_tracking_policy == 'REQUIRED':
            raise B10Error('Lot code is required by Inventory Item policy')
        return None
    code = lot_code.strip()
    if not code or len(code) > 100:
        raise B10Error('Lot code must contain between 1 and 100 characters')
    resolved = unit_cost_evidence is not None and cost_currency_evidence is not None
    lot = InventoryLot(
        tenant_id=item.tenant_id, organization_id=item.organization_id, location_id=item.location_id,
        warehouse_id=warehouse.id, inventory_item_id=item.id, origin_type=origin_type,
        goods_receipt_line_id=origin_id if origin_type == 'GOODS_RECEIPT' else None,
        preparation_batch_output_id=origin_id if origin_type == 'PREPARATION_BATCH' else None,
        lot_code=code, origin_at=origin_at, manufacture_date=manufacture_date,
        expiry_date=expiry_date, best_before_date=best_before_date,
        original_quantity=original_quantity, source_quantity=source_quantity,
        source_uom=source_uom, conversion_revision_id=conversion_revision_id,
        conversion_factor=conversion_factor, base_uom_evidence=base_uom_evidence,
        cost_evidence_status='RESOLVED' if resolved else 'COST_NON_DERIVABLE',
        unit_cost_evidence=unit_cost_evidence if resolved else None,
        cost_currency_evidence=cost_currency_evidence if resolved else None,
        status='ACTIVE',
    )
    db.add(lot); await db.flush(); return lot


def lot_date_state(value: InventoryLot, today: date) -> str | None:
    dates = [entry for entry in (value.expiry_date, value.best_before_date) if entry is not None]
    if not dates:
        return None
    nearest = min(dates)
    if nearest < today:
        return 'EXPIRED'
    if nearest <= today + timedelta(days=30):
        return 'APPROACHING'
    return 'VALID'


async def project_lot(db: AsyncSession, value: InventoryLot, cost_visible: bool, today: date | None = None) -> dict:
    balance = Decimal(await db.scalar(select(func.coalesce(func.sum(StockMovement.quantity), ZERO)).where(
        StockMovement.tenant_id == value.tenant_id, StockMovement.inventory_lot_id == value.id,
    )) or ZERO).quantize(QUANTITY_UNIT)
    result = {
        'id': value.id, 'location_id': value.location_id, 'warehouse_id': value.warehouse_id,
        'inventory_item_id': value.inventory_item_id, 'origin_type': value.origin_type,
        'goods_receipt_line_id': value.goods_receipt_line_id,
        'preparation_batch_output_id': value.preparation_batch_output_id,
        'lot_code': value.lot_code, 'origin_at': value.origin_at,
        'manufacture_date': value.manufacture_date, 'expiry_date': value.expiry_date,
        'best_before_date': value.best_before_date,
        'date_state': lot_date_state(value, today or date.today()),
        'original_quantity': _decimal(value.original_quantity), 'balance': _decimal(balance),
        'source_quantity': _decimal(value.source_quantity), 'source_uom': value.source_uom,
        'base_uom_evidence': value.base_uom_evidence, 'cost_evidence_status': value.cost_evidence_status,
        'unit_cost_evidence': _decimal(value.unit_cost_evidence) if cost_visible else None,
        'cost_currency_evidence': value.cost_currency_evidence if cost_visible else None,
        'cost_visible': cost_visible, 'status': value.status, 'created_at': value.created_at,
    }
    return result


async def list_lots(db: AsyncSession, tenant_id: int, location_id: int, cost_visible: bool) -> list[dict]:
    values = (await db.scalars(select(InventoryLot).where(
        InventoryLot.tenant_id == tenant_id, InventoryLot.location_id == location_id,
    ).order_by(InventoryLot.origin_at, InventoryLot.id))).all()
    return [await project_lot(db, value, cost_visible) for value in values]


async def project_snapshot(db: AsyncSession, value: InventoryValuationSnapshot, cost_visible: bool) -> dict:
    lines = (await db.scalars(select(InventoryValuationSnapshotLine).where(
        InventoryValuationSnapshotLine.snapshot_id == value.id,
    ).order_by(InventoryValuationSnapshotLine.inventory_item_id))).all()
    return {
        'id': value.id, 'location_id': value.location_id, 'warehouse_id': value.warehouse_id,
        'status': value.status, 'valuation_method': value.valuation_method,
        'as_of': value.as_of, 'movement_cursor': value.movement_cursor,
        'currency': value.currency if cost_visible else None,
        'derivable_total_value': _decimal(value.derivable_total_value) if cost_visible else None,
        'non_derivable_line_count': value.non_derivable_line_count,
        'cost_visible': cost_visible, 'created_at': value.created_at,
        'lines': [{
            'id': row.id, 'inventory_item_id': row.inventory_item_id,
            'quantity_as_of': _decimal(row.quantity_as_of), 'evidence_status': row.evidence_status,
            'cost_revision_id': row.cost_revision_id if cost_visible else None,
            'unit_cost_evidence': _decimal(row.unit_cost_evidence) if cost_visible else None,
            'cost_currency_evidence': row.cost_currency_evidence if cost_visible else None,
            'line_value': _decimal(row.line_value) if cost_visible else None,
        } for row in lines],
    }


async def create_snapshot(
    db: AsyncSession, *, context: ExecutionContext, warehouse_id: int, as_of: datetime,
    currency: str, idempotency_key: str, cost_visible: bool,
) -> tuple[dict, bool]:
    actor = _actor(context); actor_scope = _actor_scope(context)
    currency = currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise B10Error('Currency must be three uppercase letters')
    now = await _now(db)
    if as_of.tzinfo is not None:
        as_of = as_of.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
    else:
        as_of = as_of.replace(microsecond=0)
    if as_of > now:
        raise B10Error('Valuation as-of cannot be in the future')
    warehouse, _ = await _scope(db, context.tenant_id, warehouse_id, for_update=True)
    fingerprint = _fingerprint({'warehouse_id': warehouse_id, 'as_of': as_of.isoformat(), 'currency': currency, 'method': 'STANDARD_COST'})
    existing = await db.scalar(select(InventoryValuationSnapshot).where(
        InventoryValuationSnapshot.tenant_id == context.tenant_id,
        InventoryValuationSnapshot.idempotency_actor_scope == actor_scope,
        InventoryValuationSnapshot.idempotency_key == idempotency_key,
    ).with_for_update())
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise B10Error('Idempotency key was already used with different snapshot input')
        return await project_snapshot(db, existing, cost_visible), True
    cursor = int(await db.scalar(select(func.coalesce(func.max(StockMovement.id), 0)).where(
        StockMovement.tenant_id == context.tenant_id,
        StockMovement.warehouse_id == warehouse_id,
        StockMovement.recorded_at <= as_of,
    )) or 0)
    quantities = (await db.execute(select(
        StockMovement.inventory_item_id, func.sum(StockMovement.quantity),
    ).where(
        StockMovement.tenant_id == context.tenant_id,
        StockMovement.warehouse_id == warehouse_id,
        StockMovement.recorded_at <= as_of,
        StockMovement.id <= cursor,
    ).group_by(StockMovement.inventory_item_id).order_by(StockMovement.inventory_item_id))).all()
    snapshot = InventoryValuationSnapshot(
        tenant_id=context.tenant_id, organization_id=warehouse.organization_id,
        location_id=warehouse.location_id, warehouse_id=warehouse.id,
        status='FINALIZED', valuation_method='STANDARD_COST', as_of=as_of,
        movement_cursor=cursor, currency=currency, derivable_total_value=ZERO,
        non_derivable_line_count=0, created_by_actor_id=actor,
        idempotency_actor_scope=actor_scope, idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    db.add(snapshot)
    try:
        await db.flush(); total = ZERO; non_derivable = 0
        for item_id, raw_quantity in quantities:
            quantity = Decimal(raw_quantity).quantize(QUANTITY_UNIT)
            cost = await service.resolve_cost_as_of(db, tenant_id=context.tenant_id, inventory_item_id=item_id, as_of=as_of)
            if cost is None:
                evidence = 'COST_NON_DERIVABLE'; line_value = None; non_derivable += 1
            elif cost.currency != currency:
                evidence = 'CURRENCY_MISMATCH'; line_value = None; non_derivable += 1
            else:
                evidence = 'RESOLVED'; line_value = (quantity * cost.standard_unit_cost).quantize(VALUE_UNIT); total += line_value
            db.add(InventoryValuationSnapshotLine(
                tenant_id=context.tenant_id, organization_id=warehouse.organization_id,
                location_id=warehouse.location_id, warehouse_id=warehouse.id,
                snapshot_id=snapshot.id, inventory_item_id=item_id, quantity_as_of=quantity,
                cost_revision_id=cost.id if cost else None,
                unit_cost_evidence=cost.standard_unit_cost if cost else None,
                cost_currency_evidence=cost.currency if cost else None,
                line_value=line_value, evidence_status=evidence,
            ))
        snapshot.derivable_total_value = total.quantize(VALUE_UNIT)
        snapshot.non_derivable_line_count = non_derivable
        await db.commit(); await db.refresh(snapshot)
        return await project_snapshot(db, snapshot, cost_visible), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(select(InventoryValuationSnapshot).where(
            InventoryValuationSnapshot.tenant_id == context.tenant_id,
            InventoryValuationSnapshot.idempotency_actor_scope == actor_scope,
            InventoryValuationSnapshot.idempotency_key == idempotency_key,
        ))
        if winner is not None and winner.request_fingerprint == fingerprint:
            return await project_snapshot(db, winner, cost_visible), True
        raise B10Error('Valuation snapshot conflict') from exc
    except Exception:
        await db.rollback(); raise


async def list_snapshots(db: AsyncSession, tenant_id: int, location_id: int, cost_visible: bool) -> list[dict]:
    values = (await db.scalars(select(InventoryValuationSnapshot).where(
        InventoryValuationSnapshot.tenant_id == tenant_id,
        InventoryValuationSnapshot.location_id == location_id,
    ).order_by(InventoryValuationSnapshot.id.desc()))).all()
    return [await project_snapshot(db, value, cost_visible) for value in values]
