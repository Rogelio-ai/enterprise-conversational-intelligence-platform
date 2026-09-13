from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    InventoryItem,
    InventoryReconciliation,
    PhysicalCount,
    PhysicalCountLine,
    StockMovement,
    Warehouse,
)
from app.restaurant.inventory import errors
from app.restaurant.inventory import service as inventory_service
from app.restaurant.inventory.units import QUANTITY_UNIT, UnitConversionError, exact_quantity


ZERO = Decimal('0.000000')
MONEY_UNIT = Decimal('0.000000000001')
PERCENT_UNIT = Decimal('0.000001')


def _actor(context: ExecutionContext) -> tuple[int, str]:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise errors.InvalidPhysicalCountError('Physical count requires an employee actor')
    return context.principal_id, f'EMPLOYEE:{context.principal_id}'


def _text(value: str | None, maximum: int) -> str | None:
    result = value.strip() if value else None
    if result and len(result) > maximum:
        raise errors.InvalidPhysicalCountError(f'Text exceeds {maximum} characters')
    return result


def _quantity(value: Decimal) -> Decimal:
    try:
        result = exact_quantity(value)
    except UnitConversionError as exc:
        raise errors.InvalidPhysicalCountError(str(exc)) from exc
    if result < ZERO:
        raise errors.InvalidPhysicalCountError('Counted quantity cannot be negative')
    return result


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


async def _count(
    db: AsyncSession, *, tenant_id: int, count_id: int, for_update: bool = False,
) -> PhysicalCount:
    query = select(PhysicalCount).where(
        PhysicalCount.id == count_id, PhysicalCount.tenant_id == tenant_id,
    )
    if for_update:
        query = query.with_for_update()
    value = await db.scalar(query)
    if value is None:
        raise errors.PhysicalCountNotFoundError()
    return value


async def count_location(db: AsyncSession, *, tenant_id: int, count_id: int) -> int:
    return (await _count(db, tenant_id=tenant_id, count_id=count_id)).location_id


async def reconciliation_location(
    db: AsyncSession, *, tenant_id: int, reconciliation_id: int,
) -> int:
    value = await db.scalar(select(InventoryReconciliation).where(
        InventoryReconciliation.id == reconciliation_id,
        InventoryReconciliation.tenant_id == tenant_id,
    ))
    if value is None:
        raise errors.InventoryReconciliationNotFoundError()
    return value.location_id


async def count_line_location(
    db: AsyncSession, *, tenant_id: int, physical_count_line_id: int,
) -> int:
    value = await db.scalar(select(PhysicalCountLine).where(
        PhysicalCountLine.id == physical_count_line_id,
        PhysicalCountLine.tenant_id == tenant_id,
    ))
    if value is None:
        raise errors.PhysicalCountNotFoundError()
    return value.location_id


async def _lines(db: AsyncSession, value: PhysicalCount, *, lock: bool = False):
    query = select(PhysicalCountLine).where(
        PhysicalCountLine.tenant_id == value.tenant_id,
        PhysicalCountLine.physical_count_id == value.id,
    ).order_by(PhysicalCountLine.id)
    if lock:
        query = query.with_for_update()
    return tuple((await db.scalars(query)).all())


async def _adjustment_id(db: AsyncSession, line_id: int) -> int | None:
    return await db.scalar(select(StockMovement.id).where(
        StockMovement.physical_count_line_id == line_id,
    ))


async def _line_projection(db: AsyncSession, line: PhysicalCountLine, include_cost: bool) -> dict:
    return {
        'id': line.id, 'physical_count_id': line.physical_count_id,
        'inventory_item_id': line.inventory_item_id,
        'expected_quantity_at_cursor': line.expected_quantity_at_cursor,
        'source_quantity': line.source_quantity, 'source_uom': line.source_uom,
        'conversion_revision_id': line.conversion_revision_id,
        'conversion_factor': line.conversion_factor,
        'base_uom_evidence': line.base_uom_evidence,
        'normalized_counted_quantity': line.normalized_counted_quantity,
        'variance_quantity': line.variance_quantity,
        'standard_cost_revision_id': line.standard_cost_revision_id if include_cost else None,
        'standard_unit_cost_evidence': line.standard_unit_cost_evidence if include_cost else None,
        'cost_currency_evidence': line.cost_currency_evidence if include_cost else None,
        'variance_value': line.variance_value if include_cost else None,
        'evidence_status': line.evidence_status, 'cost_visible': include_cost,
        'version': line.version, 'counted_by_actor_id': line.counted_by_actor_id,
        'counted_at': line.counted_at,
        'adjustment_stock_movement_id': await _adjustment_id(db, line.id),
    }


async def _projection(db: AsyncSession, value: PhysicalCount, include_cost: bool) -> dict:
    return {
        'id': value.id, 'tenant_id': value.tenant_id,
        'organization_id': value.organization_id, 'location_id': value.location_id,
        'warehouse_id': value.warehouse_id, 'count_scope': value.count_scope,
        'status': value.status, 'opened_at': value.opened_at,
        'cursor_at': value.cursor_at, 'cursor_movement_id': value.cursor_movement_id,
        'opened_by_actor_id': value.opened_by_actor_id,
        'submitted_at': value.submitted_at,
        'submitted_by_actor_id': value.submitted_by_actor_id,
        'approved_at': value.approved_at,
        'approved_by_actor_id': value.approved_by_actor_id,
        'posted_at': value.posted_at, 'posted_by_actor_id': value.posted_by_actor_id,
        'cancelled_at': value.cancelled_at,
        'cancelled_by_actor_id': value.cancelled_by_actor_id,
        'reason': value.reason, 'reference': value.reference, 'version': value.version,
        'lines': [
            await _line_projection(db, line, include_cost)
            for line in await _lines(db, value)
        ],
    }


async def create_count(
    db: AsyncSession, *, context: ExecutionContext, warehouse_id: int,
    count_scope: str = 'PARTIAL', reason: str | None, reference: str | None,
    include_cost: bool,
) -> dict:
    actor_id, _ = _actor(context)
    count_scope = count_scope.strip().upper()
    if count_scope not in ('PARTIAL', 'FULL'):
        raise errors.InvalidPhysicalCountError('Count scope must be PARTIAL or FULL')
    try:
        warehouse = await db.scalar(select(Warehouse).where(
            Warehouse.id == warehouse_id, Warehouse.tenant_id == context.tenant_id,
        ))
        if warehouse is None:
            raise errors.WarehouseNotFoundError()
        if warehouse.status != 'ACTIVE':
            raise errors.InvalidPhysicalCountError('Count requires an active Warehouse')
        now = await inventory_service._database_now(db)
        cursor_id = await db.scalar(select(func.coalesce(func.max(StockMovement.id), 0)).where(
            StockMovement.tenant_id == context.tenant_id,
            StockMovement.warehouse_id == warehouse.id,
        ))
        value = PhysicalCount(
            tenant_id=warehouse.tenant_id, organization_id=warehouse.organization_id,
            location_id=warehouse.location_id, warehouse_id=warehouse.id,
            count_scope=count_scope, status='DRAFT', opened_at=now, cursor_at=now,
            cursor_movement_id=int(cursor_id or 0), opened_by_actor_id=actor_id,
            reason=_text(reason, 500), reference=_text(reference, 200), version=1,
        )
        db.add(value)
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost)
    except Exception:
        await db.rollback()
        raise


async def put_line(
    db: AsyncSession, *, context: ExecutionContext, count_id: int,
    inventory_item_id: int, source_quantity: Decimal, source_uom: str,
    expected_count_version: int, expected_line_version: int,
    include_cost: bool,
) -> dict:
    actor_id, _ = _actor(context)
    quantity = _quantity(source_quantity)
    try:
        count = await _count(db, tenant_id=context.tenant_id, count_id=count_id, for_update=True)
        if count.status not in ('DRAFT', 'COUNTING') or count.version != expected_count_version:
            raise errors.PhysicalCountConflictError('Only the expected editable count may change')
        item = await inventory_service._item(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
            for_update=True,
        )
        warehouse = await inventory_service._warehouse_for_scope(
            db, tenant_id=context.tenant_id, organization_id=item.organization_id,
            location_id=item.location_id, warehouse_id=count.warehouse_id,
            for_update=True,
        )
        if item.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
            raise errors.InvalidPhysicalCountError('Count line requires active authorities')
        normalized, normalized_uom, conversion, factor = await inventory_service.resolve_quantity_evidence(
            db, item=item, quantity=quantity, source_uom=source_uom,
            as_of=count.cursor_at,
        )
        normalized = normalized.quantize(QUANTITY_UNIT)
        expected = await db.scalar(select(func.coalesce(func.sum(StockMovement.quantity), 0)).where(
            StockMovement.tenant_id == count.tenant_id,
            StockMovement.warehouse_id == count.warehouse_id,
            StockMovement.inventory_item_id == item.id,
            StockMovement.id <= count.cursor_movement_id,
        ))
        expected = Decimal(expected or 0).quantize(QUANTITY_UNIT)
        variance = (normalized - expected).quantize(QUANTITY_UNIT)
        cost = await inventory_service.resolve_cost_as_of(
            db, tenant_id=count.tenant_id, inventory_item_id=item.id,
            as_of=count.cursor_at,
        )
        line = await db.scalar(select(PhysicalCountLine).where(
            PhysicalCountLine.physical_count_id == count.id,
            PhysicalCountLine.inventory_item_id == item.id,
        ).with_for_update())
        if line is None:
            if expected_line_version != 0:
                raise errors.PhysicalCountConflictError('New line expected version must be zero')
            line = PhysicalCountLine(
                tenant_id=count.tenant_id, organization_id=count.organization_id,
                location_id=count.location_id, warehouse_id=count.warehouse_id,
                physical_count_id=count.id, inventory_item_id=item.id, version=1,
                counted_by_actor_id=actor_id,
            )
            db.add(line)
        elif line.version != expected_line_version:
            raise errors.PhysicalCountConflictError('Count line version conflict')
        else:
            line.version += 1
        line.expected_quantity_at_cursor = expected
        line.source_quantity = quantity
        line.source_uom = normalized_uom
        line.conversion_revision_id = conversion.id if conversion else None
        line.conversion_factor = factor
        line.base_uom_evidence = item.base_uom
        line.normalized_counted_quantity = normalized
        line.variance_quantity = variance
        line.counted_at = await inventory_service._database_now(db)
        if cost is None:
            line.standard_cost_revision_id = None
            line.standard_unit_cost_evidence = None
            line.cost_currency_evidence = None
            line.variance_value = None
            line.evidence_status = 'COST_NON_DERIVABLE'
        else:
            line.standard_cost_revision_id = cost.id
            line.standard_unit_cost_evidence = cost.standard_unit_cost
            line.cost_currency_evidence = cost.currency
            line.variance_value = (variance * cost.standard_unit_cost).quantize(MONEY_UNIT)
            line.evidence_status = 'RESOLVED'
        count.status = 'COUNTING'
        count.version += 1
        await db.commit()
        await db.refresh(count)
        return await _projection(db, count, include_cost)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.PhysicalCountConflictError('Count line changed concurrently') from exc
    except Exception:
        await db.rollback()
        raise


async def get_count(db: AsyncSession, *, tenant_id: int, count_id: int, include_cost: bool) -> dict:
    return await _projection(db, await _count(db, tenant_id=tenant_id, count_id=count_id), include_cost)


async def list_counts(db: AsyncSession, *, tenant_id: int, location_id: int, include_cost: bool):
    values = (await db.scalars(select(PhysicalCount).where(
        PhysicalCount.tenant_id == tenant_id, PhysicalCount.location_id == location_id,
    ).order_by(PhysicalCount.id.desc()))).all()
    return [await _projection(db, value, include_cost) for value in values]


async def transition_count(
    db: AsyncSession, *, context: ExecutionContext, count_id: int,
    expected_version: int, action: str, include_cost: bool,
) -> dict:
    actor_id, _ = _actor(context)
    expected = {'submit': ('COUNTING', 'SUBMITTED'), 'approve': ('SUBMITTED', 'APPROVED')}
    source, target = expected[action]
    try:
        value = await _count(db, tenant_id=context.tenant_id, count_id=count_id, for_update=True)
        if value.status != source or value.version != expected_version:
            raise errors.PhysicalCountConflictError(f'Only the expected {source} count may {action}')
        if action == 'submit' and not await _lines(db, value):
            raise errors.InvalidPhysicalCountError('A count must contain at least one line')
        if action == 'approve' and value.submitted_by_actor_id == actor_id:
            raise errors.InvalidPhysicalCountError('Counter cannot self-approve')
        now = await inventory_service._database_now(db)
        value.status = target
        value.version += 1
        if action == 'submit':
            value.submitted_at, value.submitted_by_actor_id = now, actor_id
        else:
            value.approved_at, value.approved_by_actor_id = now, actor_id
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost)
    except Exception:
        await db.rollback()
        raise


async def cancel_count(
    db: AsyncSession, *, context: ExecutionContext, count_id: int,
    expected_version: int, include_cost: bool,
) -> dict:
    actor_id, _ = _actor(context)
    try:
        value = await _count(db, tenant_id=context.tenant_id, count_id=count_id, for_update=True)
        if value.status not in ('DRAFT', 'COUNTING', 'SUBMITTED') or value.version != expected_version:
            raise errors.PhysicalCountConflictError('Only an expected non-approved count may cancel')
        value.status = 'CANCELLED'
        value.version += 1
        value.cancelled_at = await inventory_service._database_now(db)
        value.cancelled_by_actor_id = actor_id
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost)
    except Exception:
        await db.rollback()
        raise


async def post_count(
    db: AsyncSession, *, context: ExecutionContext, count_id: int,
    expected_version: int, idempotency_key: str, include_cost: bool,
) -> tuple[dict, bool]:
    actor_id, actor_scope = _actor(context)
    fingerprint = _fingerprint({'command': 'POST_COUNT', 'count_id': count_id, 'version': expected_version})
    try:
        value = await _count(db, tenant_id=context.tenant_id, count_id=count_id, for_update=True)
        if value.status == 'POSTED':
            if (value.post_actor_scope, value.post_idempotency_key, value.post_fingerprint) == (
                actor_scope, idempotency_key, fingerprint,
            ):
                return await _projection(db, value, include_cost), True
            raise errors.PhysicalCountConflictError('Count already posted')
        if value.status != 'APPROVED' or value.version != expected_version:
            raise errors.PhysicalCountConflictError('Only the expected approved count may post')
        warehouse = await db.scalar(select(Warehouse).where(
            Warehouse.id == value.warehouse_id, Warehouse.tenant_id == value.tenant_id,
        ).with_for_update())
        if warehouse is None or warehouse.status != 'ACTIVE':
            raise errors.InvalidPhysicalCountError('Posting requires an active Warehouse')
        lines = await _lines(db, value, lock=True)
        if value.count_scope == 'FULL':
            required_item_ids = set((await db.scalars(select(InventoryItem.id).where(
                InventoryItem.tenant_id == value.tenant_id,
                InventoryItem.organization_id == value.organization_id,
                InventoryItem.location_id == value.location_id,
                InventoryItem.status == 'ACTIVE',
            ).with_for_update())).all())
            counted_item_ids = {line.inventory_item_id for line in lines}
            missing_count = len(required_item_ids - counted_item_ids)
            if missing_count:
                raise errors.InvalidPhysicalCountError(
                    f'FULL count is incomplete: {missing_count} active item(s) are not counted'
                )
        now = await inventory_service._database_now(db)
        value.post_actor_scope = actor_scope
        value.post_idempotency_key = idempotency_key
        value.post_fingerprint = fingerprint
        for line in lines:
            item = await inventory_service._item(
                db, tenant_id=value.tenant_id, inventory_item_id=line.inventory_item_id,
                for_update=True,
            )
            if item.status != 'ACTIVE':
                raise errors.InvalidPhysicalCountError('Posting requires active Inventory Items')
            if line.variance_quantity == ZERO:
                continue
            current = await inventory_service.stock_quantity(
                db, tenant_id=value.tenant_id, warehouse_id=value.warehouse_id,
                inventory_item_id=item.id,
            )
            resulting = (current + line.variance_quantity).quantize(QUANTITY_UNIT)
            warning = resulting < ZERO and warehouse.negative_stock_policy in ('WARN', 'BLOCK')
            if warning and warehouse.negative_stock_policy == 'BLOCK':
                raise errors.NegativeStockBlockedError('Count adjustment would make stock negative')
            db.add(StockMovement(
                tenant_id=value.tenant_id, organization_id=value.organization_id,
                location_id=value.location_id, warehouse_id=value.warehouse_id,
                inventory_item_id=line.inventory_item_id, movement_type='ADJUSTMENT',
                quantity=line.variance_quantity, reversal_of_movement_id=None,
                reason=value.reason or 'Physical count reconciliation',
                reference=f'PHYSICAL_COUNT:{value.id}:LINE:{line.id}', recorded_at=now,
                actor_type='EMPLOYEE', actor_id=actor_id, actor_reference=None,
                opening_balance_slot=None, idempotency_actor_scope=f'PHYSICAL_COUNT:{value.id}',
                idempotency_key=f'LINE:{line.id}', request_schema_version=1,
                request_fingerprint=fingerprint,
                negative_stock_policy=warehouse.negative_stock_policy,
                negative_stock_warning=warning, resulting_stock_quantity=resulting,
                source_quantity=line.variance_quantity, source_uom=line.base_uom_evidence,
                conversion_revision_id=None, conversion_factor=Decimal('1.000000000000'),
                base_uom_evidence=line.base_uom_evidence,
                standard_cost_revision_id=line.standard_cost_revision_id,
                standard_unit_cost_evidence=line.standard_unit_cost_evidence,
                cost_currency_evidence=line.cost_currency_evidence,
                extended_standard_cost=line.variance_value,
                evidence_status=line.evidence_status,
                physical_count_id=value.id, physical_count_line_id=line.id,
            ))
        value.status = 'POSTED'
        value.version += 1
        value.posted_at, value.posted_by_actor_id = now, actor_id
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(select(PhysicalCount).where(
            PhysicalCount.tenant_id == context.tenant_id,
            PhysicalCount.post_actor_scope == actor_scope,
            PhysicalCount.post_idempotency_key == idempotency_key,
        ))
        if winner and winner.id == count_id and winner.post_fingerprint == fingerprint:
            return await _projection(db, winner, include_cost), True
        raise errors.PhysicalCountConflictError('Count post conflict') from exc
    except Exception:
        await db.rollback()
        raise


def _reconciliation_projection(value: InventoryReconciliation, include_cost: bool) -> dict:
    result = {column.name: getattr(value, column.name) for column in value.__table__.columns}
    if not include_cost:
        for name in ('standard_cost_revision_id', 'standard_unit_cost_evidence',
                     'cost_currency_evidence', 'variance_value'):
            result[name] = None
    result['cost_visible'] = include_cost
    return result


async def create_reconciliation(
    db: AsyncSession, *, context: ExecutionContext, physical_count_line_id: int,
    period_start: datetime, include_cost: bool,
) -> dict:
    actor_id, _ = _actor(context)
    try:
        line = await db.scalar(select(PhysicalCountLine).where(
            PhysicalCountLine.id == physical_count_line_id,
            PhysicalCountLine.tenant_id == context.tenant_id,
        ))
        if line is None:
            raise errors.PhysicalCountNotFoundError()
        count = await _count(db, tenant_id=context.tenant_id, count_id=line.physical_count_id)
        if count.status != 'POSTED' or period_start >= count.cursor_at:
            raise errors.InvalidPhysicalCountError('Reconciliation requires a posted count and earlier start')
        value = InventoryReconciliation(
            tenant_id=line.tenant_id, organization_id=line.organization_id,
            location_id=line.location_id, warehouse_id=line.warehouse_id,
            inventory_item_id=line.inventory_item_id, physical_count_id=count.id,
            physical_count_line_id=line.id, period_start=period_start,
            period_end=count.cursor_at, status='OPEN', created_by_actor_id=actor_id,
            version=1,
        )
        db.add(value)
        await db.commit()
        await db.refresh(value)
        return _reconciliation_projection(value, include_cost)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.InventoryReconciliationConflictError('Count line already reconciled') from exc
    except Exception:
        await db.rollback()
        raise


async def get_reconciliation(db: AsyncSession, *, tenant_id: int, reconciliation_id: int, include_cost: bool) -> dict:
    value = await db.scalar(select(InventoryReconciliation).where(
        InventoryReconciliation.id == reconciliation_id,
        InventoryReconciliation.tenant_id == tenant_id,
    ))
    if value is None:
        raise errors.InventoryReconciliationNotFoundError()
    return _reconciliation_projection(value, include_cost)


async def list_reconciliations(db: AsyncSession, *, tenant_id: int, location_id: int, include_cost: bool):
    values = (await db.scalars(select(InventoryReconciliation).where(
        InventoryReconciliation.tenant_id == tenant_id,
        InventoryReconciliation.location_id == location_id,
    ).order_by(InventoryReconciliation.id.desc()))).all()
    return [_reconciliation_projection(value, include_cost) for value in values]


async def close_reconciliation(
    db: AsyncSession, *, context: ExecutionContext, reconciliation_id: int,
    expected_version: int, include_cost: bool,
) -> dict:
    actor_id, _ = _actor(context)
    try:
        value = await db.scalar(select(InventoryReconciliation).where(
            InventoryReconciliation.id == reconciliation_id,
            InventoryReconciliation.tenant_id == context.tenant_id,
        ).with_for_update())
        if value is None:
            raise errors.InventoryReconciliationNotFoundError()
        if value.status != 'OPEN' or value.version != expected_version:
            raise errors.InventoryReconciliationConflictError('Only the expected open reconciliation may close')
        line = await db.scalar(select(PhysicalCountLine).where(
            PhysicalCountLine.id == value.physical_count_line_id,
        ).with_for_update())
        count = await _count(db, tenant_id=value.tenant_id, count_id=value.physical_count_id, for_update=True)
        movements = (await db.scalars(select(StockMovement).where(
            StockMovement.tenant_id == value.tenant_id,
            StockMovement.warehouse_id == value.warehouse_id,
            StockMovement.inventory_item_id == value.inventory_item_id,
            StockMovement.id <= count.cursor_movement_id,
        ).order_by(StockMovement.id))).all()
        opening = sum((row.quantity for row in movements if row.created_at < value.period_start), ZERO)
        # cursor_movement_id is the tie-break for the half-open end boundary because
        # the inherited ledger stores created_at at whole-second precision.
        window = [row for row in movements if value.period_start <= row.created_at]
        receiving = sum((row.quantity for row in window if row.movement_type == 'GOODS_RECEIPT'), ZERO)
        consumption = -sum((row.quantity for row in window if row.movement_type == 'CONSUMPTION'), ZERO)
        loss = -sum((row.quantity for row in window if row.inventory_loss_id is not None), ZERO)
        classified = {'GOODS_RECEIPT', 'CONSUMPTION'}
        # Preparation inputs/outputs remain explicit ledger events. For this
        # item-level reconciliation they belong once in the net "other"
        # material flow; their batch provenance remains queryable on each row.
        preparation = sum((row.quantity for row in window if row.movement_type in {'PREPARATION_INPUT', 'PREPARATION_OUTPUT'}), ZERO)
        other = preparation + sum((row.quantity for row in window if row.movement_type not in classified | {'PREPARATION_INPUT', 'PREPARATION_OUTPUT'} and row.inventory_loss_id is None), ZERO)
        theoretical = (opening + receiving - consumption - loss + other).quantize(QUANTITY_UNIT)
        variance = (line.normalized_counted_quantity - theoretical).quantize(QUANTITY_UNIT)
        value.opening_quantity = opening.quantize(QUANTITY_UNIT)
        value.receiving_quantity = receiving.quantize(QUANTITY_UNIT)
        value.theoretical_consumption_quantity = consumption.quantize(QUANTITY_UNIT)
        value.dedicated_loss_quantity = loss.quantize(QUANTITY_UNIT)
        value.other_adjustment_quantity = other.quantize(QUANTITY_UNIT)
        value.physical_count_quantity = line.normalized_counted_quantity
        value.count_adjustment_quantity = line.variance_quantity
        value.theoretical_closing_quantity = theoretical
        value.closing_quantity = (theoretical + line.variance_quantity).quantize(QUANTITY_UNIT)
        value.variance_quantity = variance
        value.variance_percentage = (
            (variance / abs(theoretical) * Decimal(100)).quantize(PERCENT_UNIT)
            if theoretical != ZERO else None
        )
        value.standard_cost_revision_id = line.standard_cost_revision_id
        value.standard_unit_cost_evidence = line.standard_unit_cost_evidence
        value.cost_currency_evidence = line.cost_currency_evidence
        value.variance_value = line.variance_value
        value.evidence_status = line.evidence_status
        value.status = 'CLOSED'
        value.version += 1
        value.closed_at = await inventory_service._database_now(db)
        value.closed_by_actor_id = actor_id
        await db.commit()
        await db.refresh(value)
        return _reconciliation_projection(value, include_cost)
    except Exception:
        await db.rollback()
        raise
