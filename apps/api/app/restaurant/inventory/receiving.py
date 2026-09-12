from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryItem,
    Location,
    StockMovement,
    Supplier,
    SupplierLocation,
    SupplierOffering,
    PurchaseOrder,
    PurchaseOrderLine,
    Warehouse,
)
from app.restaurant.inventory import errors
from app.restaurant.inventory import service as inventory_service
from app.restaurant.inventory.units import QUANTITY_UNIT, UnitConversionError, exact_quantity


_CODE = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')
_UOM = re.compile(r'^[A-Z][A-Z0-9_]{0,31}$')
_CURRENCY = re.compile(r'^[A-Z]{3}$')


async def _now(db: AsyncSession) -> datetime:
    return await db.scalar(select(func.current_timestamp()))


def _text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > limit:
        raise errors.InvalidGoodsReceiptError(f'Value exceeds {limit} characters')
    return normalized


def _quantity(value: Decimal, *, positive: bool = False) -> Decimal:
    try:
        return exact_quantity(value, positive=positive)
    except UnitConversionError as exc:
        raise errors.InvalidGoodsReceiptError(str(exc)) from exc


def _cost(value: Decimal) -> Decimal:
    if (
        isinstance(value, float) or not isinstance(value, Decimal)
        or not value.is_finite() or value < 0
        or value != value.quantize(QUANTITY_UNIT)
    ):
        raise errors.InvalidGoodsReceiptError(
            'Unit cost must be a non-negative exact Decimal with at most six decimals'
        )
    return value


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _actor_scope(context: ExecutionContext) -> str:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise errors.InvalidGoodsReceiptError('Goods receiving requires an employee actor')
    return f'EMPLOYEE:{context.principal_id}'


async def _supplier(
    db: AsyncSession, *, tenant_id: int, supplier_id: int, for_update: bool = False,
) -> Supplier:
    statement = select(Supplier).where(
        Supplier.id == supplier_id, Supplier.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.SupplierNotFoundError()
    return value


async def supplier_organization(
    db: AsyncSession, *, tenant_id: int, supplier_id: int,
) -> int:
    return (await _supplier(
        db, tenant_id=tenant_id, supplier_id=supplier_id,
    )).organization_id


async def supplier_locations(
    db: AsyncSession, *, tenant_id: int, supplier_id: int,
) -> tuple[int, ...]:
    await _supplier(db, tenant_id=tenant_id, supplier_id=supplier_id)
    return tuple((await db.scalars(
        select(SupplierLocation.location_id).where(
            SupplierLocation.tenant_id == tenant_id,
            SupplierLocation.supplier_id == supplier_id,
            SupplierLocation.status == 'ACTIVE',
        )
    )).all())


async def _validate_locations(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_ids: tuple[int, ...],
) -> tuple[int, ...]:
    unique = tuple(dict.fromkeys(location_ids))
    if not unique:
        raise errors.InvalidSupplierError('At least one Location is required')
    rows = (await db.scalars(select(Location.id).where(
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
        Location.id.in_(unique),
    ))).all()
    if set(rows) != set(unique):
        raise errors.InventoryScopeNotFoundError()
    return unique


def _supplier_projection(value: Supplier, locations: tuple[SupplierLocation, ...]) -> dict:
    return {
        'id': value.id, 'tenant_id': value.tenant_id,
        'organization_id': value.organization_id, 'code': value.code,
        'name': value.name, 'status': value.status,
        'contact_reference': value.contact_reference, 'version': value.version,
        'location_ids': tuple(row.location_id for row in locations if row.status == 'ACTIVE'),
        'created_at': value.created_at, 'updated_at': value.updated_at,
    }


async def _project_supplier(db: AsyncSession, value: Supplier) -> dict:
    locations = tuple((await db.scalars(select(SupplierLocation).where(
        SupplierLocation.tenant_id == value.tenant_id,
        SupplierLocation.supplier_id == value.id,
    ).order_by(SupplierLocation.location_id))).all())
    return _supplier_projection(value, locations)


async def create_supplier(
    db: AsyncSession, *, tenant_id: int, organization_id: int, code: str,
    name: str, contact_reference: str | None, location_ids: tuple[int, ...],
) -> dict:
    code = code.strip().upper()
    if _CODE.fullmatch(code) is None:
        raise errors.InvalidSupplierError('Invalid Supplier code')
    name = name.strip()
    if not name or len(name) > 200:
        raise errors.InvalidSupplierError('Invalid Supplier name')
    location_ids = await _validate_locations(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_ids=location_ids,
    )
    value = Supplier(
        tenant_id=tenant_id, organization_id=organization_id, code=code,
        name=name, contact_reference=_text(contact_reference, 200), status='ACTIVE',
    )
    db.add(value)
    try:
        await db.flush()
        for location_id in location_ids:
            db.add(SupplierLocation(
                tenant_id=tenant_id, organization_id=organization_id,
                location_id=location_id, supplier_id=value.id, status='ACTIVE',
            ))
        await db.commit()
        await db.refresh(value)
        return await _project_supplier(db, value)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.SupplierConflictError('Supplier code or availability already exists') from exc


async def update_supplier(
    db: AsyncSession, *, tenant_id: int, supplier_id: int, expected_version: int,
    name: str | None, status: str | None, contact_reference: str | None,
    location_ids: tuple[int, ...] | None,
) -> dict:
    value = await _supplier(
        db, tenant_id=tenant_id, supplier_id=supplier_id, for_update=True,
    )
    if value.version != expected_version:
        raise errors.SupplierConflictError('Supplier version conflict')
    if name is not None:
        value.name = name.strip()
        if not value.name or len(value.name) > 200:
            raise errors.InvalidSupplierError('Invalid Supplier name')
    if status is not None:
        value.status = status
    if contact_reference is not None:
        value.contact_reference = _text(contact_reference, 200)
    if location_ids is not None:
        location_ids = await _validate_locations(
            db, tenant_id=tenant_id, organization_id=value.organization_id,
            location_ids=location_ids,
        )
        current = tuple((await db.scalars(select(SupplierLocation).where(
            SupplierLocation.tenant_id == tenant_id,
            SupplierLocation.supplier_id == value.id,
        ).with_for_update())).all())
        by_location = {row.location_id: row for row in current}
        for row in current:
            row.status = 'ACTIVE' if row.location_id in location_ids else 'INACTIVE'
        for location_id in location_ids:
            if location_id not in by_location:
                db.add(SupplierLocation(
                    tenant_id=tenant_id, organization_id=value.organization_id,
                    location_id=location_id, supplier_id=value.id, status='ACTIVE',
                ))
    value.version += 1
    try:
        await db.commit()
        await db.refresh(value)
        return await _project_supplier(db, value)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.SupplierConflictError() from exc


async def list_suppliers(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> tuple[dict, ...]:
    values = (await db.scalars(select(Supplier).join(
        SupplierLocation,
        (SupplierLocation.supplier_id == Supplier.id)
        & (SupplierLocation.tenant_id == Supplier.tenant_id),
    ).where(
        Supplier.tenant_id == tenant_id,
        SupplierLocation.location_id == location_id,
        SupplierLocation.status == 'ACTIVE',
    ).order_by(Supplier.name, Supplier.id))).all()
    return tuple([await _project_supplier(db, value) for value in values])


async def get_supplier(
    db: AsyncSession, *, tenant_id: int, supplier_id: int, location_id: int,
) -> dict:
    value = await _supplier(db, tenant_id=tenant_id, supplier_id=supplier_id)
    available = await db.scalar(select(SupplierLocation.id).where(
        SupplierLocation.tenant_id == tenant_id,
        SupplierLocation.supplier_id == supplier_id,
        SupplierLocation.location_id == location_id,
        SupplierLocation.status == 'ACTIVE',
    ))
    if available is None:
        raise errors.SupplierNotFoundError()
    return await _project_supplier(db, value)


def _offering_projection(value: SupplierOffering) -> dict:
    return {
        'id': value.id, 'supplier_id': value.supplier_id,
        'location_id': value.location_id, 'inventory_item_id': value.inventory_item_id,
        'supplier_item_code': value.supplier_item_code,
        'purchase_uom': value.purchase_uom, 'status': value.status,
        'version': value.version, 'created_at': value.created_at,
        'updated_at': value.updated_at,
    }


async def _offering(
    db: AsyncSession, *, tenant_id: int, offering_id: int,
    for_update: bool = False,
) -> SupplierOffering:
    statement = select(SupplierOffering).where(
        SupplierOffering.id == offering_id,
        SupplierOffering.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.SupplierOfferingNotFoundError()
    return value


async def offering_location(
    db: AsyncSession, *, tenant_id: int, offering_id: int,
) -> int:
    return (await _offering(
        db, tenant_id=tenant_id, offering_id=offering_id,
    )).location_id


async def create_offering(
    db: AsyncSession, *, tenant_id: int, supplier_id: int, location_id: int,
    inventory_item_id: int, supplier_item_code: str | None, purchase_uom: str,
) -> dict:
    supplier = await _supplier(db, tenant_id=tenant_id, supplier_id=supplier_id)
    item = await db.scalar(select(InventoryItem).where(
        InventoryItem.id == inventory_item_id, InventoryItem.tenant_id == tenant_id,
        InventoryItem.organization_id == supplier.organization_id,
        InventoryItem.location_id == location_id,
    ))
    availability = await db.scalar(select(SupplierLocation).where(
        SupplierLocation.tenant_id == tenant_id,
        SupplierLocation.supplier_id == supplier_id,
        SupplierLocation.location_id == location_id,
        SupplierLocation.status == 'ACTIVE',
    ))
    if item is None or availability is None:
        raise errors.InventoryScopeNotFoundError()
    if supplier.status != 'ACTIVE' or item.status != 'ACTIVE':
        raise errors.InvalidSupplierOfferingError('Supplier and item must be active')
    purchase_uom = purchase_uom.strip().upper()
    if _UOM.fullmatch(purchase_uom) is None:
        raise errors.InvalidSupplierOfferingError('Invalid purchase UOM')
    now = await _now(db)
    try:
        await inventory_service.resolve_quantity_evidence(
            db, item=item, quantity=Decimal('1.000000'),
            source_uom=purchase_uom, as_of=now,
        )
    except errors.InventoryError as exc:
        raise errors.InvalidSupplierOfferingError(str(exc)) from exc
    value = SupplierOffering(
        tenant_id=tenant_id, organization_id=supplier.organization_id,
        location_id=location_id, supplier_id=supplier.id,
        inventory_item_id=item.id,
        supplier_item_code=_text(supplier_item_code, 100),
        purchase_uom=purchase_uom, status='ACTIVE',
    )
    db.add(value)
    try:
        await db.commit()
        await db.refresh(value)
        return _offering_projection(value)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.SupplierOfferingConflictError('Offering already exists') from exc


async def update_offering(
    db: AsyncSession, *, tenant_id: int, offering_id: int, expected_version: int,
    status: str | None, supplier_item_code: str | None,
) -> dict:
    value = await _offering(
        db, tenant_id=tenant_id, offering_id=offering_id, for_update=True,
    )
    if value.version != expected_version:
        raise errors.SupplierOfferingConflictError('Offering version conflict')
    if status is not None:
        value.status = status
    if supplier_item_code is not None:
        value.supplier_item_code = _text(supplier_item_code, 100)
    value.version += 1
    await db.commit()
    await db.refresh(value)
    return _offering_projection(value)


async def list_offerings(
    db: AsyncSession, *, tenant_id: int, supplier_id: int, location_id: int,
) -> tuple[dict, ...]:
    await _supplier(db, tenant_id=tenant_id, supplier_id=supplier_id)
    availability = await db.scalar(select(SupplierLocation.id).where(
        SupplierLocation.tenant_id == tenant_id,
        SupplierLocation.supplier_id == supplier_id,
        SupplierLocation.location_id == location_id,
        SupplierLocation.status == 'ACTIVE',
    ))
    if availability is None:
        raise errors.SupplierNotFoundError()
    values = (await db.scalars(select(SupplierOffering).where(
        SupplierOffering.tenant_id == tenant_id,
        SupplierOffering.supplier_id == supplier_id,
        SupplierOffering.location_id == location_id,
    ).order_by(SupplierOffering.id))).all()
    return tuple(_offering_projection(value) for value in values)


def _line_projection(value: GoodsReceiptLine) -> dict:
    return {
        'id': value.id, 'line_number': value.line_number,
        'supplier_offering_id': value.supplier_offering_id,
        'inventory_item_id': value.inventory_item_id,
        'purchase_order_line_id': value.purchase_order_line_id,
        'received_quantity': value.received_quantity,
        'accepted_quantity': value.accepted_quantity,
        'rejected_quantity': value.rejected_quantity,
        'source_uom': value.source_uom, 'unit_cost': value.unit_cost,
        'currency': value.currency,
        'conversion_revision_id': value.conversion_revision_id,
        'conversion_factor': value.conversion_factor,
        'base_uom_evidence': value.base_uom_evidence,
        'normalized_quantity': value.normalized_quantity,
        'extended_cost': value.extended_cost,
        'evidence_status': value.evidence_status,
    }


async def _receipt(
    db: AsyncSession, *, tenant_id: int, receipt_id: int,
    for_update: bool = False,
) -> GoodsReceipt:
    statement = select(GoodsReceipt).where(
        GoodsReceipt.id == receipt_id, GoodsReceipt.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.GoodsReceiptNotFoundError()
    return value


async def receipt_location(
    db: AsyncSession, *, tenant_id: int, receipt_id: int,
) -> int:
    return (await _receipt(
        db, tenant_id=tenant_id, receipt_id=receipt_id,
    )).location_id


async def _receipt_projection(db: AsyncSession, value: GoodsReceipt) -> dict:
    lines = tuple((await db.scalars(select(GoodsReceiptLine).where(
        GoodsReceiptLine.tenant_id == value.tenant_id,
        GoodsReceiptLine.goods_receipt_id == value.id,
    ).order_by(GoodsReceiptLine.line_number))).all())
    movement_rows = (await db.execute(select(
        StockMovement.goods_receipt_line_id, StockMovement.id,
    ).where(
        StockMovement.tenant_id == value.tenant_id,
        StockMovement.goods_receipt_id == value.id,
    ))).all()
    movement_ids = {line_id: movement_id for line_id, movement_id in movement_rows}
    projected_lines = []
    for line in lines:
        projected = _line_projection(line)
        projected['stock_movement_id'] = movement_ids.get(line.id)
        projected_lines.append(projected)
    return {
        'id': value.id, 'tenant_id': value.tenant_id,
        'organization_id': value.organization_id, 'location_id': value.location_id,
        'warehouse_id': value.warehouse_id, 'supplier_id': value.supplier_id,
        'purchase_order_id': value.purchase_order_id,
        'external_reference': value.external_reference, 'status': value.status,
        'version': value.version, 'created_by_actor_id': value.created_by_actor_id,
        'accepted_at': value.accepted_at,
        'accepted_by_actor_id': value.accepted_by_actor_id,
        'cancelled_at': value.cancelled_at,
        'cancelled_by_actor_id': value.cancelled_by_actor_id,
        'lines': tuple(projected_lines), 'created_at': value.created_at,
        'updated_at': value.updated_at,
    }


async def create_receipt(
    db: AsyncSession, *, context: ExecutionContext, supplier_id: int,
    location_id: int, warehouse_id: int, external_reference: str | None,
    lines: tuple[dict, ...], purchase_order_id: int | None = None,
) -> dict:
    actor_scope = _actor_scope(context)
    del actor_scope
    if not lines:
        raise errors.InvalidGoodsReceiptError('At least one receipt line is required')
    supplier = await _supplier(db, tenant_id=context.tenant_id, supplier_id=supplier_id)
    availability = await db.scalar(select(SupplierLocation).where(
        SupplierLocation.tenant_id == context.tenant_id,
        SupplierLocation.supplier_id == supplier_id,
        SupplierLocation.location_id == location_id,
        SupplierLocation.status == 'ACTIVE',
    ))
    warehouse = await db.scalar(select(Warehouse).where(
        Warehouse.id == warehouse_id, Warehouse.tenant_id == context.tenant_id,
        Warehouse.organization_id == supplier.organization_id,
        Warehouse.location_id == location_id,
    ))
    if availability is None or warehouse is None:
        raise errors.InventoryScopeNotFoundError()
    if supplier.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
        raise errors.InvalidGoodsReceiptError('Supplier and Warehouse must be active')
    purchase_order = None
    if purchase_order_id is not None:
        purchase_order = await db.scalar(select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.tenant_id == context.tenant_id,
            PurchaseOrder.organization_id == supplier.organization_id,
            PurchaseOrder.location_id == location_id,
            PurchaseOrder.supplier_id == supplier.id,
            PurchaseOrder.warehouse_id == warehouse.id,
        ))
        if purchase_order is None:
            raise errors.InventoryScopeNotFoundError()
        if purchase_order.status not in ('APPROVED', 'PARTIALLY_RECEIVED'):
            raise errors.GoodsReceiptConflictError('Purchase order is not receivable')
    elif any(data.get('purchase_order_line_id') is not None for data in lines):
        raise errors.InvalidGoodsReceiptError(
            'A direct receipt cannot allocate a purchase-order line'
        )
    receipt = GoodsReceipt(
        tenant_id=context.tenant_id, organization_id=supplier.organization_id,
        location_id=location_id, warehouse_id=warehouse.id,
        supplier_id=supplier.id, external_reference=_text(external_reference, 200),
        purchase_order_id=purchase_order_id,
        status='DRAFT', created_by_actor_id=context.principal_id,
    )
    db.add(receipt)
    try:
        await db.flush()
        seen: set[int] = set()
        for index, data in enumerate(lines, 1):
            offering_id = int(data['supplier_offering_id'])
            if offering_id in seen:
                raise errors.InvalidGoodsReceiptError('Offering may appear only once per receipt')
            seen.add(offering_id)
            offering = await _offering(
                db, tenant_id=context.tenant_id, offering_id=offering_id,
            )
            item = await db.scalar(select(InventoryItem).where(
                InventoryItem.id == offering.inventory_item_id,
                InventoryItem.tenant_id == context.tenant_id,
            ))
            if (
                offering.supplier_id != supplier.id or offering.location_id != location_id
                or offering.status != 'ACTIVE' or item is None or item.status != 'ACTIVE'
            ):
                raise errors.InvalidSupplierOfferingError('Offering is not active in receipt scope')
            purchase_order_line_id = data.get('purchase_order_line_id')
            if purchase_order is not None:
                purchase_order_line = await db.scalar(select(PurchaseOrderLine).where(
                    PurchaseOrderLine.id == purchase_order_line_id,
                    PurchaseOrderLine.purchase_order_id == purchase_order.id,
                    PurchaseOrderLine.tenant_id == context.tenant_id,
                    PurchaseOrderLine.organization_id == supplier.organization_id,
                    PurchaseOrderLine.location_id == location_id,
                    PurchaseOrderLine.warehouse_id == warehouse.id,
                    PurchaseOrderLine.supplier_id == supplier.id,
                    PurchaseOrderLine.supplier_offering_id == offering.id,
                    PurchaseOrderLine.inventory_item_id == item.id,
                ))
                if purchase_order_line is None:
                    raise errors.InvalidGoodsReceiptError(
                        'Receipt line does not match purchase order'
                    )
            received = _quantity(data['received_quantity'], positive=True)
            accepted = _quantity(data['accepted_quantity'])
            rejected = _quantity(data['rejected_quantity'])
            if accepted < 0 or rejected < 0 or accepted + rejected != received:
                raise errors.InvalidGoodsReceiptError(
                    'Accepted plus rejected quantity must equal received quantity'
                )
            currency = str(data['currency']).strip().upper()
            if _CURRENCY.fullmatch(currency) is None or currency != item.currency:
                raise errors.InvalidGoodsReceiptError('Receipt currency does not match item policy')
            db.add(GoodsReceiptLine(
                tenant_id=context.tenant_id, organization_id=supplier.organization_id,
                location_id=location_id, warehouse_id=warehouse.id,
                supplier_id=supplier.id, goods_receipt_id=receipt.id,
                supplier_offering_id=offering.id, inventory_item_id=item.id,
                line_number=index, received_quantity=received,
                purchase_order_line_id=purchase_order_line_id,
                accepted_quantity=accepted, rejected_quantity=rejected,
                source_uom=offering.purchase_uom,
                unit_cost=_cost(data['unit_cost']), currency=currency,
                evidence_status='PENDING',
            ))
        await db.commit()
        await db.refresh(receipt)
        return await _receipt_projection(db, receipt)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.GoodsReceiptConflictError('Receipt identity already exists') from exc
    except Exception:
        await db.rollback()
        raise


async def get_receipt(
    db: AsyncSession, *, tenant_id: int, receipt_id: int,
) -> dict:
    return await _receipt_projection(
        db, await _receipt(db, tenant_id=tenant_id, receipt_id=receipt_id),
    )


async def list_receipts(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> tuple[dict, ...]:
    values = (await db.scalars(select(GoodsReceipt).where(
        GoodsReceipt.tenant_id == tenant_id,
        GoodsReceipt.location_id == location_id,
    ).order_by(GoodsReceipt.id.desc()))).all()
    return tuple([await _receipt_projection(db, value) for value in values])


async def accept_receipt(
    db: AsyncSession, *, context: ExecutionContext, receipt_id: int,
    expected_version: int, idempotency_key: str,
) -> tuple[dict, bool]:
    actor_scope = _actor_scope(context)
    receipt = await _receipt(
        db, tenant_id=context.tenant_id, receipt_id=receipt_id, for_update=True,
    )
    if receipt.status == 'ACCEPTED':
        if (
            receipt.acceptance_actor_scope == actor_scope
            and receipt.acceptance_idempotency_key == idempotency_key
        ):
            return await _receipt_projection(db, receipt), True
        raise errors.GoodsReceiptConflictError('Receipt was already accepted')
    if receipt.status != 'DRAFT':
        raise errors.GoodsReceiptConflictError('Only a draft receipt may be accepted')
    if receipt.version != expected_version:
        raise errors.GoodsReceiptConflictError('Receipt version conflict')
    accepted_at = await _now(db)
    supplier = await _supplier(
        db, tenant_id=context.tenant_id, supplier_id=receipt.supplier_id,
        for_update=True,
    )
    availability = await db.scalar(select(SupplierLocation).where(
        SupplierLocation.tenant_id == context.tenant_id,
        SupplierLocation.supplier_id == supplier.id,
        SupplierLocation.location_id == receipt.location_id,
        SupplierLocation.status == 'ACTIVE',
    ).with_for_update())
    warehouse = await db.scalar(select(Warehouse).where(
        Warehouse.id == receipt.warehouse_id,
        Warehouse.tenant_id == context.tenant_id,
        Warehouse.organization_id == receipt.organization_id,
        Warehouse.location_id == receipt.location_id,
    ).with_for_update())
    if availability is None or warehouse is None:
        raise errors.InventoryScopeNotFoundError()
    if supplier.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
        raise errors.InvalidGoodsReceiptError('Supplier and Warehouse must be active')
    lines = tuple((await db.scalars(select(GoodsReceiptLine).where(
        GoodsReceiptLine.tenant_id == context.tenant_id,
        GoodsReceiptLine.goods_receipt_id == receipt.id,
    ).order_by(GoodsReceiptLine.line_number).with_for_update())).all())
    if not lines:
        raise errors.InvalidGoodsReceiptError('Receipt has no lines')
    purchase_order = None
    if receipt.purchase_order_id is not None:
        purchase_order = await db.scalar(select(PurchaseOrder).where(
            PurchaseOrder.id == receipt.purchase_order_id,
            PurchaseOrder.tenant_id == context.tenant_id,
            PurchaseOrder.location_id == receipt.location_id,
            PurchaseOrder.supplier_id == receipt.supplier_id,
            PurchaseOrder.warehouse_id == receipt.warehouse_id,
        ).with_for_update())
        if purchase_order is None:
            raise errors.InventoryScopeNotFoundError()
        if purchase_order.status not in ('APPROVED', 'PARTIALLY_RECEIVED'):
            raise errors.GoodsReceiptConflictError('Purchase order is not receivable')
        for line in lines:
            po_line = await db.scalar(select(PurchaseOrderLine).where(
                PurchaseOrderLine.id == line.purchase_order_line_id,
                PurchaseOrderLine.purchase_order_id == purchase_order.id,
                PurchaseOrderLine.supplier_offering_id == line.supplier_offering_id,
            ).with_for_update())
            if (
                po_line is None or po_line.source_uom != line.source_uom
                or po_line.currency != line.currency
            ):
                raise errors.InvalidGoodsReceiptError('Receipt line does not match purchase order')
            prior = await db.scalar(select(func.coalesce(func.sum(GoodsReceiptLine.accepted_quantity), Decimal('0'))).join(
                GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id,
            ).where(GoodsReceipt.status == 'ACCEPTED', GoodsReceiptLine.purchase_order_line_id == po_line.id))
            if prior + line.accepted_quantity > po_line.ordered_quantity:
                raise errors.GoodsReceiptConflictError('Accepted quantity exceeds remaining purchase order obligation')
    fingerprint = _fingerprint({
        'schema_version': 1, 'receipt_id': receipt.id,
        'receipt_version': receipt.version,
        'lines': [{
            'id': line.id, 'offering_id': line.supplier_offering_id,
            'received': str(line.received_quantity),
            'accepted': str(line.accepted_quantity),
            'rejected': str(line.rejected_quantity), 'uom': line.source_uom,
            'unit_cost': str(line.unit_cost), 'currency': line.currency,
        } for line in lines],
    })
    try:
        for line in lines:
            offering = await _offering(
                db, tenant_id=context.tenant_id,
                offering_id=line.supplier_offering_id, for_update=True,
            )
            item = await db.scalar(select(InventoryItem).where(
                InventoryItem.id == line.inventory_item_id,
                InventoryItem.tenant_id == context.tenant_id,
                InventoryItem.organization_id == receipt.organization_id,
                InventoryItem.location_id == receipt.location_id,
            ).with_for_update())
            if (
                item is None or item.status != 'ACTIVE' or offering.status != 'ACTIVE'
                or offering.supplier_id != receipt.supplier_id
                or offering.location_id != receipt.location_id
                or offering.inventory_item_id != line.inventory_item_id
                or offering.purchase_uom != line.source_uom
            ):
                raise errors.InvalidSupplierOfferingError(
                    'Receipt Offering or Inventory Item is no longer valid'
                )
            if line.currency != item.currency:
                raise errors.InvalidGoodsReceiptError(
                    'Receipt currency does not match item policy'
                )
            evidence_quantity = (
                line.accepted_quantity
                if line.accepted_quantity > 0 else Decimal('1.000000')
            )
            normalized, source_uom, conversion, factor = (
                await inventory_service.resolve_quantity_evidence(
                    db, item=item, quantity=evidence_quantity,
                    source_uom=line.source_uom, as_of=accepted_at,
                )
            )
            if line.accepted_quantity == 0:
                normalized = Decimal('0.000000')
            line.conversion_revision_id = conversion.id if conversion is not None else None
            line.conversion_factor = factor
            line.base_uom_evidence = item.base_uom
            line.normalized_quantity = normalized
            line.extended_cost = (line.accepted_quantity * line.unit_cost).quantize(
                Decimal('0.000000000001')
            )
            line.evidence_status = 'RESOLVED' if normalized > 0 else 'REJECTED_ONLY'
            if normalized == 0:
                continue
            current_stock = await db.scalar(select(func.coalesce(
                func.sum(StockMovement.quantity), Decimal('0.000000')
            )).where(
                StockMovement.tenant_id == context.tenant_id,
                StockMovement.location_id == receipt.location_id,
                StockMovement.warehouse_id == receipt.warehouse_id,
                StockMovement.inventory_item_id == item.id,
            ))
            cost_revision = await inventory_service.resolve_cost_as_of(
                db, tenant_id=context.tenant_id,
                inventory_item_id=item.id, as_of=accepted_at,
            )
            movement = StockMovement(
                tenant_id=context.tenant_id, organization_id=receipt.organization_id,
                location_id=receipt.location_id, warehouse_id=receipt.warehouse_id,
                inventory_item_id=item.id, movement_type='GOODS_RECEIPT',
                quantity=normalized, reversal_of_movement_id=None,
                reason='Goods receipt acceptance', reference=receipt.external_reference,
                recorded_at=accepted_at, actor_type='EMPLOYEE',
                actor_id=context.principal_id, actor_reference=None,
                opening_balance_slot=None,
                idempotency_actor_scope=f'GOODS_RECEIPT:{receipt.id}',
                idempotency_key=f'LINE:{line.id}', request_schema_version=1,
                request_fingerprint=fingerprint,
                negative_stock_policy=warehouse.negative_stock_policy,
                negative_stock_warning=False,
                resulting_stock_quantity=current_stock + normalized,
                source_quantity=line.accepted_quantity, source_uom=source_uom,
                conversion_revision_id=line.conversion_revision_id,
                conversion_factor=factor, base_uom_evidence=item.base_uom,
                standard_cost_revision_id=(cost_revision.id if cost_revision else None),
                standard_unit_cost_evidence=(
                    cost_revision.standard_unit_cost if cost_revision else None
                ),
                cost_currency_evidence=(cost_revision.currency if cost_revision else None),
                extended_standard_cost=(
                    (normalized * cost_revision.standard_unit_cost).quantize(
                        Decimal('0.000000000001')
                    ) if cost_revision else None
                ),
                evidence_status='RESOLVED' if cost_revision else 'COST_NON_DERIVABLE',
                goods_receipt_id=receipt.id, goods_receipt_line_id=line.id,
            )
            db.add(movement)
            await db.flush()
        receipt.status = 'ACCEPTED'
        receipt.version += 1
        receipt.accepted_at = accepted_at
        receipt.accepted_by_actor_id = context.principal_id
        receipt.acceptance_actor_scope = actor_scope
        receipt.acceptance_idempotency_key = idempotency_key
        receipt.acceptance_fingerprint = fingerprint
        if purchase_order is not None:
            await db.flush()
            po_lines = (await db.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == purchase_order.id))).all()
            complete = True
            any_received = False
            for po_line in po_lines:
                accepted = await db.scalar(select(func.coalesce(func.sum(GoodsReceiptLine.accepted_quantity), Decimal('0'))).join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id).where(GoodsReceipt.status == 'ACCEPTED', GoodsReceiptLine.purchase_order_line_id == po_line.id))
                any_received = any_received or accepted > 0
                complete = complete and accepted >= po_line.ordered_quantity
            purchase_order.status = 'RECEIVED' if complete else 'PARTIALLY_RECEIVED' if any_received else 'APPROVED'
            purchase_order.version += 1
        await db.commit()
        await db.refresh(receipt)
        return await _receipt_projection(db, receipt), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(select(GoodsReceipt).where(
            GoodsReceipt.id == receipt_id,
            GoodsReceipt.tenant_id == context.tenant_id,
        ))
        if (
            winner is not None and winner.status == 'ACCEPTED'
            and winner.acceptance_actor_scope == actor_scope
            and winner.acceptance_idempotency_key == idempotency_key
        ):
            return await _receipt_projection(db, winner), True
        raise errors.GoodsReceiptConflictError('Receipt acceptance conflict') from exc
    except Exception:
        await db.rollback()
        raise


async def cancel_receipt(
    db: AsyncSession, *, context: ExecutionContext, receipt_id: int,
    expected_version: int,
) -> dict:
    _actor_scope(context)
    receipt = await _receipt(
        db, tenant_id=context.tenant_id, receipt_id=receipt_id, for_update=True,
    )
    if receipt.status != 'DRAFT' or receipt.version != expected_version:
        raise errors.GoodsReceiptConflictError('Only the expected draft may be cancelled')
    receipt.status = 'CANCELLED'
    receipt.version += 1
    receipt.cancelled_at = await _now(db)
    receipt.cancelled_by_actor_id = context.principal_id
    await db.commit()
    await db.refresh(receipt)
    return await _receipt_projection(db, receipt)
