from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
    SupplierLocation,
    SupplierOffering,
    Warehouse,
)
from app.restaurant.inventory import errors, service
from app.restaurant.inventory.units import QUANTITY_UNIT, UnitConversionError, exact_quantity


_CURRENCY = re.compile(r'^[A-Z]{3}$')


class PurchaseOrderError(errors.InventoryError):
    code = 'PURCHASE_ORDER_CONFLICT'


class PurchaseOrderNotFound(PurchaseOrderError):
    code = 'PURCHASE_ORDER_NOT_FOUND'


def _actor(context: ExecutionContext) -> int:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise PurchaseOrderError('Purchase-order operations require an employee actor')
    return context.principal_id


def _text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > limit:
        raise PurchaseOrderError(f'Value exceeds {limit} characters')
    return normalized


def _money(value: Decimal) -> Decimal:
    if (
        isinstance(value, float) or not isinstance(value, Decimal)
        or not value.is_finite() or value < 0
        or value != value.quantize(QUANTITY_UNIT)
    ):
        raise PurchaseOrderError(
            'Agreed unit price must be a non-negative exact Decimal with at most six decimals'
        )
    return value


def _currency(value: str) -> str:
    normalized = value.strip().upper()
    if _CURRENCY.fullmatch(normalized) is None:
        raise PurchaseOrderError('Currency must be a three-letter ISO code')
    return normalized


def _decimal(value: Decimal | int | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(value).quantize(QUANTITY_UNIT), 'f')


async def _order(
    db: AsyncSession, tenant_id: int, order_id: int, lock: bool = False,
) -> PurchaseOrder:
    statement = select(PurchaseOrder).where(
        PurchaseOrder.id == order_id, PurchaseOrder.tenant_id == tenant_id,
    )
    value = await db.scalar(statement.with_for_update() if lock else statement)
    if value is None:
        raise PurchaseOrderNotFound('Purchase order not found')
    return value


async def location(db: AsyncSession, tenant_id: int, order_id: int) -> int:
    return (await _order(db, tenant_id, order_id)).location_id


async def project(
    db: AsyncSession, value: PurchaseOrder, cost_visible: bool = True,
) -> dict:
    lines = tuple((await db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.purchase_order_id == value.id,
    ).order_by(PurchaseOrderLine.line_number))).all())
    receipt_rows = (await db.execute(select(
        GoodsReceipt.id, GoodsReceipt.status, GoodsReceipt.accepted_at,
    ).where(
        GoodsReceipt.tenant_id == value.tenant_id,
        GoodsReceipt.purchase_order_id == value.id,
    ).order_by(GoodsReceipt.id))).all()
    projected_lines = []
    for line in lines:
        allocations = (await db.execute(select(
            GoodsReceipt.id, GoodsReceipt.status, GoodsReceipt.accepted_at,
            GoodsReceiptLine.accepted_quantity, GoodsReceiptLine.rejected_quantity,
            GoodsReceiptLine.unit_cost, GoodsReceiptLine.currency,
        ).join(
            GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id,
        ).where(
            GoodsReceiptLine.tenant_id == value.tenant_id,
            GoodsReceiptLine.purchase_order_line_id == line.id,
        ).order_by(GoodsReceipt.id))).all()
        accepted_allocations = [row for row in allocations if row.status == 'ACCEPTED']
        accepted = sum(
            (Decimal(row.accepted_quantity) for row in accepted_allocations), Decimal('0')
        )
        rejected = sum(
            (Decimal(row.rejected_quantity) for row in accepted_allocations), Decimal('0')
        )
        remaining = max(Decimal('0'), line.ordered_quantity - accepted)
        received_price = None
        if accepted > 0:
            received_price = sum(
                (Decimal(row.accepted_quantity) * Decimal(row.unit_cost)
                 for row in accepted_allocations), Decimal('0')
            ) / accepted
        projected_allocations = []
        for row in allocations:
            allocation = {
                'goods_receipt_id': row.id,
                'status': row.status,
                'accepted_at': row.accepted_at,
                'accepted_quantity': _decimal(row.accepted_quantity),
                'rejected_quantity': _decimal(row.rejected_quantity),
            }
            if cost_visible:
                allocation.update(
                    unit_cost=_decimal(row.unit_cost), currency=row.currency,
                )
            projected_allocations.append(allocation)
        projected = {
            'id': line.id,
            'supplier_offering_id': line.supplier_offering_id,
            'inventory_item_id': line.inventory_item_id,
            'line_number': line.line_number,
            'ordered_quantity': _decimal(line.ordered_quantity),
            'source_uom': line.source_uom,
            'normalized_ordered_quantity': _decimal(line.normalized_ordered_quantity),
            'base_uom_evidence': line.base_uom_evidence,
            'conversion_factor': _decimal(line.conversion_factor),
            'accepted_quantity': _decimal(accepted),
            'rejected_quantity': _decimal(rejected),
            'remaining_quantity': _decimal(remaining),
            'receipt_allocations': projected_allocations,
        }
        if cost_visible:
            variance = received_price - line.agreed_unit_price if received_price is not None else None
            percentage = (
                variance / line.agreed_unit_price * Decimal('100')
                if variance is not None and line.agreed_unit_price != 0 else None
            )
            projected.update(
                agreed_unit_price=_decimal(line.agreed_unit_price),
                currency=line.currency,
                received_unit_price=_decimal(received_price),
                price_variance=_decimal(variance),
                price_variance_percentage=_decimal(percentage),
            )
        projected_lines.append(projected)
    return {
        'id': value.id,
        'tenant_id': value.tenant_id,
        'organization_id': value.organization_id,
        'location_id': value.location_id,
        'warehouse_id': value.warehouse_id,
        'supplier_id': value.supplier_id,
        'status': value.status,
        'currency': value.currency if cost_visible else None,
        'expected_delivery_at': value.expected_delivery_at,
        'external_reference': value.external_reference,
        'notes': value.notes,
        'version': value.version,
        'created_at': value.created_at,
        'updated_at': value.updated_at,
        'submitted_at': value.submitted_at,
        'approved_at': value.approved_at,
        'terminated_at': value.terminated_at,
        'receipts': [
            {'id': row.id, 'status': row.status, 'accepted_at': row.accepted_at}
            for row in receipt_rows
        ],
        'lines': projected_lines,
        'cost_visible': cost_visible,
    }


async def _scope(
    db: AsyncSession, context: ExecutionContext, location_id: int,
    warehouse_id: int, supplier_id: int,
) -> tuple[Supplier, Warehouse]:
    supplier = await db.scalar(select(Supplier).where(
        Supplier.id == supplier_id, Supplier.tenant_id == context.tenant_id,
        Supplier.status == 'ACTIVE',
    ))
    warehouse = await db.scalar(select(Warehouse).where(
        Warehouse.id == warehouse_id, Warehouse.tenant_id == context.tenant_id,
        Warehouse.location_id == location_id, Warehouse.status == 'ACTIVE',
    ))
    availability = await db.scalar(select(SupplierLocation).where(
        SupplierLocation.supplier_id == supplier_id,
        SupplierLocation.location_id == location_id,
        SupplierLocation.tenant_id == context.tenant_id,
        SupplierLocation.status == 'ACTIVE',
    ))
    if (
        supplier is None or warehouse is None or availability is None
        or supplier.organization_id != warehouse.organization_id
        or availability.organization_id != supplier.organization_id
    ):
        raise errors.InventoryScopeNotFoundError()
    return supplier, warehouse


async def _replace_lines(
    db: AsyncSession, po: PurchaseOrder, lines: tuple[dict, ...], now: datetime,
) -> None:
    if not lines:
        raise PurchaseOrderError('At least one line is required')
    offering_ids = [int(value['supplier_offering_id']) for value in lines]
    if len(set(offering_ids)) != len(offering_ids):
        raise PurchaseOrderError('An offering may appear only once per purchase order')
    for number, data in enumerate(lines, 1):
        offering = await db.scalar(select(SupplierOffering).where(
            SupplierOffering.id == int(data['supplier_offering_id']),
            SupplierOffering.tenant_id == po.tenant_id,
            SupplierOffering.organization_id == po.organization_id,
            SupplierOffering.location_id == po.location_id,
            SupplierOffering.supplier_id == po.supplier_id,
            SupplierOffering.status == 'ACTIVE',
        ))
        if offering is None:
            raise errors.InvalidSupplierOfferingError('Offering unavailable')
        item = await db.scalar(select(InventoryItem).where(
            InventoryItem.id == offering.inventory_item_id,
            InventoryItem.tenant_id == po.tenant_id,
            InventoryItem.organization_id == po.organization_id,
            InventoryItem.location_id == po.location_id,
            InventoryItem.status == 'ACTIVE',
        ))
        if item is None:
            raise errors.InventoryScopeNotFoundError()
        if item.currency != po.currency:
            raise PurchaseOrderError(
                'Purchase-order currency must match every inventory item currency; currency conversion is not supported'
            )
        try:
            quantity = exact_quantity(data['ordered_quantity'], positive=True)
        except UnitConversionError as exc:
            raise PurchaseOrderError(str(exc)) from exc
        normalized, source_uom, conversion, factor = await service.resolve_quantity_evidence(
            db, item=item, quantity=quantity,
            source_uom=offering.purchase_uom, as_of=now,
        )
        db.add(PurchaseOrderLine(
            tenant_id=po.tenant_id, organization_id=po.organization_id,
            location_id=po.location_id, warehouse_id=po.warehouse_id,
            supplier_id=po.supplier_id, purchase_order_id=po.id,
            supplier_offering_id=offering.id, inventory_item_id=item.id,
            line_number=number, ordered_quantity=quantity, source_uom=source_uom,
            conversion_revision_id=conversion.id if conversion else None,
            conversion_factor=factor, base_uom_evidence=item.base_uom,
            normalized_ordered_quantity=normalized,
            agreed_unit_price=_money(data['agreed_unit_price']), currency=po.currency,
        ))


async def create(
    db: AsyncSession, context: ExecutionContext, location_id: int, warehouse_id: int,
    supplier_id: int, currency: str, expected_delivery_at: datetime | None,
    external_reference: str | None, notes: str | None, lines: tuple[dict, ...],
    cost_visible: bool = True,
) -> dict:
    actor_id = _actor(context)
    supplier, warehouse = await _scope(
        db, context, location_id, warehouse_id, supplier_id,
    )
    po = PurchaseOrder(
        tenant_id=context.tenant_id, organization_id=supplier.organization_id,
        location_id=location_id, warehouse_id=warehouse.id, supplier_id=supplier.id,
        status='DRAFT', currency=_currency(currency),
        expected_delivery_at=expected_delivery_at,
        external_reference=_text(external_reference, 200),
        notes=_text(notes, 1000), created_by_actor_id=actor_id,
    )
    db.add(po)
    try:
        await db.flush()
        await _replace_lines(db, po, lines, await db.scalar(select(func.current_timestamp())))
        await db.commit()
        await db.refresh(po)
        return await project(db, po, cost_visible)
    except IntegrityError as exc:
        await db.rollback()
        raise PurchaseOrderError('Purchase-order identity conflict') from exc
    except Exception:
        await db.rollback()
        raise


async def list_orders(
    db: AsyncSession, tenant_id: int, location_id: int, cost_visible: bool,
) -> list[dict]:
    values = tuple((await db.scalars(select(PurchaseOrder).where(
        PurchaseOrder.tenant_id == tenant_id,
        PurchaseOrder.location_id == location_id,
    ).order_by(PurchaseOrder.id.desc()))).all())
    return [await project(db, value, cost_visible) for value in values]


async def amend(
    db: AsyncSession, context: ExecutionContext, order_id: int, expected_version: int,
    expected_delivery_at: datetime | None, external_reference: str | None,
    notes: str | None, lines: tuple[dict, ...], cost_visible: bool = True,
) -> dict:
    _actor(context)
    po = await _order(db, context.tenant_id, order_id, True)
    if po.status != 'DRAFT' or po.version != expected_version:
        raise PurchaseOrderError('Only the expected DRAFT may be amended')
    try:
        await db.execute(delete(PurchaseOrderLine).where(
            PurchaseOrderLine.purchase_order_id == po.id,
        ))
        await _replace_lines(
            db, po, lines, await db.scalar(select(func.current_timestamp())),
        )
        po.expected_delivery_at = expected_delivery_at
        po.external_reference = _text(external_reference, 200)
        po.notes = _text(notes, 1000)
        po.version += 1
        await db.commit()
        await db.refresh(po)
        return await project(db, po, cost_visible)
    except IntegrityError as exc:
        await db.rollback()
        raise PurchaseOrderError('Purchase-order amendment conflict') from exc
    except Exception:
        await db.rollback()
        raise


async def command(
    db: AsyncSession, context: ExecutionContext, order_id: int, action: str,
    expected_version: int, key: str, cost_visible: bool = True,
) -> tuple[dict, bool]:
    actor_id = _actor(context)
    po = await _order(db, context.tenant_id, order_id, True)
    replay_key = {
        'submit': po.submitted_command_key,
        'approve': po.approved_command_key,
        'cancel': po.terminated_command_key if po.terminated_action == 'cancel' else None,
        'close': po.terminated_command_key if po.terminated_action == 'close' else None,
    }[action]
    if replay_key == key:
        return await project(db, po, cost_visible), True
    allowed = {
        'submit': (('DRAFT',), 'SUBMITTED'),
        'approve': (('SUBMITTED',), 'APPROVED'),
        'cancel': (('DRAFT', 'SUBMITTED', 'APPROVED', 'PARTIALLY_RECEIVED'), 'CANCELLED'),
        'close': (('RECEIVED', 'PARTIALLY_RECEIVED'), 'CLOSED'),
    }
    sources, target = allowed[action]
    if po.version != expected_version or po.status not in sources:
        raise PurchaseOrderError('Purchase order state changed')
    now = await db.scalar(select(func.current_timestamp()))
    po.status = target
    po.version += 1
    po.last_command_key = key
    po.last_command_action = action
    if action == 'submit':
        po.submitted_at = now
        po.submitted_by_actor_id = actor_id
        po.submitted_command_key = key
    elif action == 'approve':
        po.approved_at = now
        po.approved_by_actor_id = actor_id
        po.approved_command_key = key
    else:
        po.terminated_at = now
        po.terminated_by_actor_id = actor_id
        po.terminated_command_key = key
        po.terminated_action = action
    await db.commit()
    await db.refresh(po)
    return await project(db, po, cost_visible), False
