from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.models import (
    GoodsReceipt, GoodsReceiptLine, InventoryCostRevision, InventoryItem,
    InventoryLoss, InventoryReconciliation, PhysicalCount, StockMovement,
    Supplier, Warehouse,
)


router = APIRouter(prefix='/inventory', tags=['inventory-intelligence'])
ZERO = Decimal('0')
MONEY = Decimal('0.000001')


class PurchaseCostProjection(BaseModel):
    evidence_status: str
    last_purchase_cost: Decimal | None
    recent_weighted_purchase_cost: Decimal | None
    currency: str | None
    selected_window_days: int | None
    accepted_receipt_events: int
    last_vs_standard_absolute: Decimal | None
    last_vs_standard_percentage: Decimal | None
    weighted_vs_standard_absolute: Decimal | None
    weighted_vs_standard_percentage: Decimal | None
    source: str


class StockIntelligenceRow(BaseModel):
    inventory_item_id: int
    code: str
    name: str
    warehouse_id: int
    warehouse_name: str
    base_uom: str
    quantity: Decimal
    negative_stock_policy: str
    attention: tuple[str, ...]
    last_material_activity_at: datetime | None
    standard_unit_cost: Decimal | None
    cost_currency: str | None
    inventory_value_at_standard_cost: Decimal | None
    purchase_cost: PurchaseCostProjection | None
    stock_source: str
    valuation_source: str | None


class ActivityProjection(BaseModel):
    id: int
    warehouse_id: int
    inventory_item_id: int | None = None
    label: str
    status: str
    occurred_at: datetime
    quantity: Decimal | None = None
    value: Decimal | None = None
    currency: str | None = None
    evidence_status: str | None = None
    source: str


class ReconciliationProjection(BaseModel):
    id: int
    warehouse_id: int
    inventory_item_id: int
    physical_count_id: int
    status: str
    version: int
    period_start: datetime
    period_end: datetime
    opening_quantity: Decimal | None
    receipts: Decimal | None
    theoretical_consumption: Decimal | None
    registered_losses: Decimal | None
    other_adjustments: Decimal | None
    physical_count: Decimal | None
    count_adjustment: Decimal | None
    closing_quantity: Decimal | None
    unexplained_variance: Decimal | None
    variance_percentage: Decimal | None
    variance_value: Decimal | None
    currency: str | None
    evidence_status: str | None
    source: str


class InventoryIntelligenceResponse(BaseModel):
    location_id: int
    generated_at: datetime
    cost_visible: bool
    active_warehouse_count: int
    active_inventory_item_count: int
    stock_position_count: int
    negative_stock_count: int
    counts_requiring_action: int
    reconciliations_requiring_action: int
    warehouses: list[dict[str, Any]]
    stock: list[StockIntelligenceRow]
    recent_receipts: list[ActivityProjection]
    recent_losses: list[ActivityProjection]
    recent_counts: list[ActivityProjection]
    reconciliations: list[ReconciliationProjection]
    sources: dict[str, str]
    limit: int
    offset: int


def _deviations(value: Decimal | None, standard: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    if value is None or standard is None:
        return None, None
    absolute = (value - standard).quantize(MONEY)
    percentage = ((absolute / standard) * Decimal('100')).quantize(MONEY) if standard > ZERO else None
    return absolute, percentage


@router.get('/intelligence', response_model=InventoryIntelligenceResponse)
async def inventory_intelligence(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    warehouse_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    if location_id not in context.authorized_location_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Location not found')
    now = (await db.scalar(select(func.current_timestamp(6)))) or datetime.now()
    cost_visible = 'inventory.cost.read' in context.permissions
    warehouses = (await db.scalars(select(Warehouse).where(
        Warehouse.tenant_id == context.tenant_id,
        Warehouse.location_id == location_id,
        Warehouse.status == 'ACTIVE',
        *([Warehouse.id == warehouse_id] if warehouse_id else []),
    ).order_by(Warehouse.name, Warehouse.id))).all()
    warehouse_ids = [value.id for value in warehouses]
    if warehouse_id and not warehouse_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Warehouse not found')

    active_item_count = int(await db.scalar(select(func.count()).select_from(InventoryItem).where(
        InventoryItem.tenant_id == context.tenant_id,
        InventoryItem.location_id == location_id,
        InventoryItem.status == 'ACTIVE',
    )) or 0)
    items = (await db.scalars(select(InventoryItem).where(
        InventoryItem.tenant_id == context.tenant_id,
        InventoryItem.location_id == location_id,
        InventoryItem.status == 'ACTIVE',
    ).order_by(InventoryItem.name, InventoryItem.id).limit(limit).offset(offset))).all()
    item_ids = [value.id for value in items]

    movement_rows = []
    if warehouse_ids and item_ids:
        movement_rows = (await db.execute(select(
            StockMovement.warehouse_id, StockMovement.inventory_item_id,
            func.coalesce(func.sum(StockMovement.quantity), 0),
            func.max(StockMovement.created_at),
        ).where(
            StockMovement.tenant_id == context.tenant_id,
            StockMovement.location_id == location_id,
            StockMovement.warehouse_id.in_(warehouse_ids),
            StockMovement.inventory_item_id.in_(item_ids),
        ).group_by(StockMovement.warehouse_id, StockMovement.inventory_item_id))).all()
    stock_map = {(row[0], row[1]): (Decimal(row[2]), row[3]) for row in movement_rows}

    latest_cost: dict[int, InventoryCostRevision] = {}
    if cost_visible and item_ids:
        revisions = (await db.scalars(select(InventoryCostRevision).where(
            InventoryCostRevision.tenant_id == context.tenant_id,
            InventoryCostRevision.inventory_item_id.in_(item_ids),
            InventoryCostRevision.effective_at <= now,
        ).order_by(
            InventoryCostRevision.inventory_item_id,
            InventoryCostRevision.effective_at.desc(),
            InventoryCostRevision.revision.desc(),
        ))).all()
        for revision in revisions:
            latest_cost.setdefault(revision.inventory_item_id, revision)

    purchase_rows: dict[int, list[Any]] = defaultdict(list)
    if cost_visible and item_ids:
        evidence = (await db.execute(select(
            GoodsReceiptLine.inventory_item_id, GoodsReceipt.id,
            GoodsReceipt.accepted_at, GoodsReceiptLine.normalized_quantity,
            GoodsReceiptLine.extended_cost, GoodsReceiptLine.currency,
        ).join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id).where(
            GoodsReceipt.tenant_id == context.tenant_id,
            GoodsReceipt.location_id == location_id,
            GoodsReceipt.status == 'ACCEPTED',
            GoodsReceipt.accepted_at >= now - timedelta(days=90),
            GoodsReceiptLine.inventory_item_id.in_(item_ids),
            GoodsReceiptLine.evidence_status == 'RESOLVED',
            GoodsReceiptLine.normalized_quantity > 0,
        ).order_by(GoodsReceipt.accepted_at.desc(), GoodsReceipt.id.desc()))).all()
        for row in evidence:
            purchase_rows[row[0]].append(row)

    stock: list[dict[str, Any]] = []
    negative_count = 0
    for warehouse in warehouses:
        for item in items:
            quantity, last_activity = stock_map.get((warehouse.id, item.id), (ZERO, None))
            attention: list[str] = []
            if quantity < ZERO:
                attention.append('NEGATIVE_STOCK')
                negative_count += 1
            if warehouse.negative_stock_policy in {'WARN', 'BLOCK'}:
                attention.append(f'{warehouse.negative_stock_policy}_POLICY')
            standard_revision = latest_cost.get(item.id)
            standard = Decimal(standard_revision.standard_unit_cost) if standard_revision else None
            currency = standard_revision.currency if standard_revision else None
            purchase = None
            if cost_visible:
                rows = purchase_rows.get(item.id, [])
                last = (Decimal(rows[0][4]) / Decimal(rows[0][3])).quantize(MONEY) if rows else None
                weighted = None
                window = None
                event_count = 0
                purchase_currency = rows[0][5] if rows else None
                for days in (30, 60, 90):
                    selected = [row for row in rows if row[2] >= now - timedelta(days=days)]
                    currencies = {row[5] for row in selected}
                    event_count = len({row[1] for row in selected})
                    total_quantity = sum((Decimal(row[3]) for row in selected), ZERO)
                    if event_count >= 3 and total_quantity > ZERO and len(currencies) == 1:
                        weighted = (sum((Decimal(row[4]) for row in selected), ZERO) / total_quantity).quantize(MONEY)
                        window = days
                        purchase_currency = next(iter(currencies))
                        break
                last_abs, last_pct = _deviations(last, standard if currency == purchase_currency else None)
                weighted_abs, weighted_pct = _deviations(weighted, standard if currency == purchase_currency else None)
                purchase = {
                    'evidence_status': 'DERIVABLE' if last is not None else 'NOT_AVAILABLE',
                    'last_purchase_cost': last,
                    'recent_weighted_purchase_cost': weighted,
                    'currency': purchase_currency,
                    'selected_window_days': window,
                    'accepted_receipt_events': event_count,
                    'last_vs_standard_absolute': last_abs,
                    'last_vs_standard_percentage': last_pct,
                    'weighted_vs_standard_absolute': weighted_abs,
                    'weighted_vs_standard_percentage': weighted_pct,
                    'source': 'ACCEPTED_GOODS_RECEIPT_LINE_NORMALIZED_EVIDENCE',
                }
                if standard is None:
                    attention.append('STANDARD_COST_NON_DERIVABLE')
                if last is None:
                    attention.append('PURCHASE_COST_NOT_AVAILABLE')
            stock.append({
                'inventory_item_id': item.id, 'code': item.code, 'name': item.name,
                'warehouse_id': warehouse.id, 'warehouse_name': warehouse.name,
                'base_uom': item.base_uom, 'quantity': quantity,
                'negative_stock_policy': warehouse.negative_stock_policy,
                'attention': tuple(attention), 'last_material_activity_at': last_activity,
                'standard_unit_cost': standard if cost_visible else None,
                'cost_currency': currency if cost_visible else None,
                'inventory_value_at_standard_cost': (quantity * standard).quantize(MONEY) if cost_visible and standard is not None else None,
                'purchase_cost': purchase if cost_visible else None,
                'stock_source': 'SUM_STOCK_MOVEMENT_QUANTITY',
                'valuation_source': 'LEDGER_QUANTITY_X_INVENTORY_COST_REVISION' if cost_visible and standard is not None else None,
            })

    receipts: list[dict[str, Any]] = []
    if warehouse_ids:
        receipt_rows = (await db.execute(select(GoodsReceipt, Supplier.name).join(
            Supplier, Supplier.id == GoodsReceipt.supplier_id,
        ).where(
            GoodsReceipt.tenant_id == context.tenant_id,
            GoodsReceipt.location_id == location_id,
            GoodsReceipt.warehouse_id.in_(warehouse_ids),
            GoodsReceipt.status == 'ACCEPTED',
        ).order_by(GoodsReceipt.accepted_at.desc(), GoodsReceipt.id.desc()).limit(10))).all()
        receipts = [{
            'id': value.id, 'warehouse_id': value.warehouse_id,
            'label': supplier_name, 'status': value.status,
            'occurred_at': value.accepted_at, 'source': 'GOODS_RECEIPT_ACCEPTED',
        } for value, supplier_name in receipt_rows]

    loss_rows = (await db.scalars(select(InventoryLoss).where(
        InventoryLoss.tenant_id == context.tenant_id,
        InventoryLoss.location_id == location_id,
        *([InventoryLoss.warehouse_id.in_(warehouse_ids)] if warehouse_ids else [InventoryLoss.id < 0]),
    ).order_by(InventoryLoss.occurred_at.desc(), InventoryLoss.id.desc()).limit(10))).all()
    recent_losses = [{
        'id': value.id, 'warehouse_id': value.warehouse_id,
        'inventory_item_id': value.inventory_item_id, 'label': value.category,
        'status': value.status, 'occurred_at': value.occurred_at,
        'quantity': value.normalized_quantity,
        'value': value.extended_loss_cost if cost_visible else None,
        'currency': value.cost_currency_evidence if cost_visible else None,
        'evidence_status': value.evidence_status, 'source': 'INVENTORY_LOSS',
    } for value in loss_rows]

    count_rows = (await db.scalars(select(PhysicalCount).where(
        PhysicalCount.tenant_id == context.tenant_id,
        PhysicalCount.location_id == location_id,
        *([PhysicalCount.warehouse_id.in_(warehouse_ids)] if warehouse_ids else [PhysicalCount.id < 0]),
    ).order_by(PhysicalCount.opened_at.desc(), PhysicalCount.id.desc()).limit(10))).all()
    recent_counts = [{
        'id': value.id, 'warehouse_id': value.warehouse_id,
        'label': value.reference or 'Conteo parcial', 'status': value.status,
        'occurred_at': value.cursor_at, 'source': 'PHYSICAL_COUNT',
    } for value in count_rows]

    reconciliation_rows = (await db.scalars(select(InventoryReconciliation).where(
        InventoryReconciliation.tenant_id == context.tenant_id,
        InventoryReconciliation.location_id == location_id,
        *([InventoryReconciliation.warehouse_id.in_(warehouse_ids)] if warehouse_ids else [InventoryReconciliation.id < 0]),
    ).order_by(InventoryReconciliation.period_end.desc(), InventoryReconciliation.id.desc()).limit(20))).all()
    reconciliations = [{
        'id': value.id, 'warehouse_id': value.warehouse_id,
        'inventory_item_id': value.inventory_item_id,
        'physical_count_id': value.physical_count_id, 'status': value.status,
        'version': value.version,
        'period_start': value.period_start, 'period_end': value.period_end,
        'opening_quantity': value.opening_quantity,
        'receipts': value.receiving_quantity,
        'theoretical_consumption': value.theoretical_consumption_quantity,
        'registered_losses': value.dedicated_loss_quantity,
        'other_adjustments': value.other_adjustment_quantity,
        'physical_count': value.physical_count_quantity,
        'count_adjustment': value.count_adjustment_quantity,
        'closing_quantity': value.closing_quantity,
        'unexplained_variance': value.variance_quantity,
        'variance_percentage': value.variance_percentage,
        'variance_value': value.variance_value if cost_visible else None,
        'currency': value.cost_currency_evidence if cost_visible else None,
        'evidence_status': value.evidence_status,
        'source': 'INVENTORY_RECONCILIATION',
    } for value in reconciliation_rows]

    actionable_counts = {'DRAFT', 'COUNTING', 'SUBMITTED', 'APPROVED'}
    count_action_total = int(await db.scalar(select(func.count()).select_from(PhysicalCount).where(
        PhysicalCount.tenant_id == context.tenant_id,
        PhysicalCount.location_id == location_id,
        PhysicalCount.status.in_(actionable_counts),
        *([PhysicalCount.warehouse_id.in_(warehouse_ids)] if warehouse_ids else [PhysicalCount.id < 0]),
    )) or 0)
    reconciliation_action_total = int(await db.scalar(select(func.count()).select_from(InventoryReconciliation).where(
        InventoryReconciliation.tenant_id == context.tenant_id,
        InventoryReconciliation.location_id == location_id,
        InventoryReconciliation.status == 'OPEN',
        *([InventoryReconciliation.warehouse_id.in_(warehouse_ids)] if warehouse_ids else [InventoryReconciliation.id < 0]),
    )) or 0)
    return {
        'location_id': location_id, 'generated_at': now, 'cost_visible': cost_visible,
        'active_warehouse_count': len(warehouses),
        'active_inventory_item_count': active_item_count,
        'stock_position_count': len(stock), 'negative_stock_count': negative_count,
        'counts_requiring_action': count_action_total,
        'reconciliations_requiring_action': reconciliation_action_total,
        'warehouses': [{
            'id': value.id, 'code': value.code, 'name': value.name,
            'negative_stock_policy': value.negative_stock_policy,
            'is_default': value.default_slot == 1,
        } for value in warehouses],
        'stock': stock, 'recent_receipts': receipts,
        'recent_losses': recent_losses, 'recent_counts': recent_counts,
        'reconciliations': reconciliations,
        'sources': {
            'stock': 'StockMovement', 'receipts': 'GoodsReceipt',
            'losses': 'InventoryLoss', 'counts': 'PhysicalCount',
            'reconciliations': 'InventoryReconciliation',
            'standard_cost': 'InventoryCostRevision',
            'purchase_cost': 'Accepted GoodsReceiptLine frozen UOM/cost evidence',
        },
        'limit': limit, 'offset': offset,
    }
