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
    InventoryItem,
    InventoryLoss,
    InventoryLossPolicy,
    StockMovement,
    Warehouse,
)
from app.restaurant.inventory import errors
from app.restaurant.inventory import service as inventory_service
from app.restaurant.inventory.units import QUANTITY_UNIT, UnitConversionError, exact_quantity


CATEGORIES = frozenset({
    'WASTE', 'SPOILAGE', 'BREAKAGE', 'EXPIRY', 'PREPARATION_LOSS', 'OTHER',
})
_UOM = re.compile(r'^[A-Z][A-Z0-9_]{0,31}$')
_CURRENCY = re.compile(r'^[A-Z]{3}$')
_ZERO = Decimal('0.000000')
_MONEY_UNIT = Decimal('0.000000000001')


def _actor_scope(context: ExecutionContext) -> str:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise errors.InvalidInventoryLossError('Inventory loss requires an employee actor')
    return f'EMPLOYEE:{context.principal_id}'


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _reason(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else ''
    if not normalized:
        return None
    if len(normalized) > 500:
        raise errors.InvalidInventoryLossError('Reason exceeds 500 characters')
    return normalized


def _category(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in CATEGORIES:
        raise errors.InvalidInventoryLossError('Unsupported Inventory Loss category')
    return normalized


def _source_quantity(value: Decimal) -> Decimal:
    try:
        return exact_quantity(value, positive=True)
    except UnitConversionError as exc:
        raise errors.InvalidInventoryLossError(str(exc)) from exc


def _source_uom(value: str) -> str:
    normalized = value.strip().upper()
    if _UOM.fullmatch(normalized) is None:
        raise errors.InvalidInventoryLossError('Invalid source UOM')
    return normalized


def _threshold(value: Decimal) -> Decimal:
    if (
        isinstance(value, float) or not isinstance(value, Decimal)
        or not value.is_finite() or value < 0 or value != value.quantize(_MONEY_UNIT)
    ):
        raise errors.InvalidInventoryLossError(
            'Approval threshold must be an exact non-negative Decimal with at most 12 decimals'
        )
    return value


def _currency(value: str) -> str:
    normalized = value.strip().upper()
    if _CURRENCY.fullmatch(normalized) is None:
        raise errors.InvalidInventoryLossError('Invalid policy currency')
    return normalized


async def _loss(
    db: AsyncSession, *, tenant_id: int, loss_id: int, for_update: bool = False,
) -> InventoryLoss:
    statement = select(InventoryLoss).where(
        InventoryLoss.id == loss_id, InventoryLoss.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise errors.InventoryLossNotFoundError()
    return value


async def loss_location(db: AsyncSession, *, tenant_id: int, loss_id: int) -> int:
    return (await _loss(db, tenant_id=tenant_id, loss_id=loss_id)).location_id


async def policy_location(
    db: AsyncSession, *, tenant_id: int, warehouse_id: int,
) -> int:
    warehouse = await db.scalar(select(Warehouse).where(
        Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id,
    ))
    if warehouse is None:
        raise errors.WarehouseNotFoundError()
    return warehouse.location_id


def _policy_projection(value: InventoryLossPolicy) -> dict:
    return {
        'id': value.id, 'tenant_id': value.tenant_id,
        'organization_id': value.organization_id, 'location_id': value.location_id,
        'warehouse_id': value.warehouse_id,
        'approval_value_threshold': value.approval_value_threshold,
        'currency': value.currency, 'status': value.status, 'version': value.version,
        'created_at': value.created_at, 'updated_at': value.updated_at,
    }


async def put_policy(
    db: AsyncSession, *, tenant_id: int, warehouse_id: int,
    expected_version: int, approval_value_threshold: Decimal,
    currency: str, status: str,
) -> dict:
    threshold = _threshold(approval_value_threshold)
    currency = _currency(currency)
    status = status.strip().upper()
    if status not in ('ACTIVE', 'INACTIVE'):
        raise errors.InvalidInventoryLossError('Unsupported policy status')
    try:
        warehouse = await db.scalar(select(Warehouse).where(
            Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id,
        ).with_for_update())
        if warehouse is None:
            raise errors.WarehouseNotFoundError()
        value = await db.scalar(select(InventoryLossPolicy).where(
            InventoryLossPolicy.tenant_id == tenant_id,
            InventoryLossPolicy.warehouse_id == warehouse_id,
        ).with_for_update())
        if value is None:
            if expected_version != 0:
                raise errors.InventoryLossPolicyConflictError(
                    'Expected version must be 0 when creating a policy'
                )
            value = InventoryLossPolicy(
                tenant_id=tenant_id, organization_id=warehouse.organization_id,
                location_id=warehouse.location_id, warehouse_id=warehouse.id,
                approval_value_threshold=threshold, currency=currency,
                status=status, version=1,
            )
            db.add(value)
        else:
            if value.version != expected_version:
                raise errors.InventoryLossPolicyConflictError('Policy version conflict')
            value.approval_value_threshold = threshold
            value.currency = currency
            value.status = status
            value.version += 1
        await db.commit()
        await db.refresh(value)
        return _policy_projection(value)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.InventoryLossPolicyConflictError('Policy changed concurrently') from exc
    except Exception:
        await db.rollback()
        raise


async def get_policy(
    db: AsyncSession, *, tenant_id: int, warehouse_id: int,
) -> dict:
    value = await db.scalar(select(InventoryLossPolicy).where(
        InventoryLossPolicy.tenant_id == tenant_id,
        InventoryLossPolicy.warehouse_id == warehouse_id,
    ))
    if value is None:
        raise errors.InventoryLossPolicyNotFoundError()
    return _policy_projection(value)


async def _movement_ids(db: AsyncSession, value: InventoryLoss) -> tuple[int | None, int | None]:
    rows = (await db.execute(select(
        StockMovement.id, StockMovement.loss_movement_role,
    ).where(
        StockMovement.tenant_id == value.tenant_id,
        StockMovement.inventory_loss_id == value.id,
    ))).all()
    by_role = {role: movement_id for movement_id, role in rows}
    return by_role.get('ORIGINAL'), by_role.get('REVERSAL')


async def _projection(
    db: AsyncSession, value: InventoryLoss, *, include_cost: bool,
) -> dict:
    movement_id, reversal_movement_id = await _movement_ids(db, value)
    return {
        'id': value.id, 'tenant_id': value.tenant_id,
        'organization_id': value.organization_id, 'location_id': value.location_id,
        'warehouse_id': value.warehouse_id,
        'inventory_item_id': value.inventory_item_id, 'category': value.category,
        'source_quantity': value.source_quantity, 'source_uom': value.source_uom,
        'conversion_revision_id': value.conversion_revision_id,
        'conversion_factor': value.conversion_factor,
        'base_uom_evidence': value.base_uom_evidence,
        'normalized_quantity': value.normalized_quantity,
        'standard_cost_revision_id': (
            value.standard_cost_revision_id if include_cost else None
        ),
        'standard_unit_cost_evidence': (
            value.standard_unit_cost_evidence if include_cost else None
        ),
        'cost_currency_evidence': (
            value.cost_currency_evidence if include_cost else None
        ),
        'extended_loss_cost': value.extended_loss_cost if include_cost else None,
        'evidence_status': value.evidence_status,
        'cost_visible': include_cost, 'reason': value.reason,
        'occurred_at': value.occurred_at,
        'created_by_actor_id': value.created_by_actor_id,
        'status': value.status, 'version': value.version,
        'approval_required': value.approval_required,
        'approval_reason': value.approval_reason,
        'approval_requested_at': value.approval_requested_at,
        'approval_requested_by_actor_id': value.approval_requested_by_actor_id,
        'approved_at': value.approved_at,
        'approved_by_actor_id': value.approved_by_actor_id,
        'posted_at': value.posted_at, 'posted_by_actor_id': value.posted_by_actor_id,
        'cancelled_at': value.cancelled_at,
        'cancelled_by_actor_id': value.cancelled_by_actor_id,
        'reversed_at': value.reversed_at,
        'reversed_by_actor_id': value.reversed_by_actor_id,
        'stock_movement_id': movement_id,
        'reversal_stock_movement_id': reversal_movement_id,
        'created_at': value.created_at, 'updated_at': value.updated_at,
    }


async def _scope(
    db: AsyncSession, *, tenant_id: int, inventory_item_id: int,
    warehouse_id: int, for_update: bool,
) -> tuple[InventoryItem, Warehouse]:
    item = await inventory_service._item(
        db, tenant_id=tenant_id, inventory_item_id=inventory_item_id,
        for_update=for_update,
    )
    warehouse = await inventory_service._warehouse_for_scope(
        db, tenant_id=tenant_id, organization_id=item.organization_id,
        location_id=item.location_id, warehouse_id=warehouse_id,
        for_update=for_update,
    )
    return item, warehouse


async def _validate_uom(
    db: AsyncSession, *, item: InventoryItem, quantity: Decimal,
    source_uom: str, as_of: datetime,
) -> None:
    try:
        await inventory_service.resolve_quantity_evidence(
            db, item=item, quantity=quantity, source_uom=source_uom, as_of=as_of,
        )
    except errors.InventoryError as exc:
        raise errors.InvalidInventoryLossError(str(exc)) from exc


async def create_loss(
    db: AsyncSession, *, context: ExecutionContext, warehouse_id: int,
    inventory_item_id: int, category: str, source_quantity: Decimal,
    source_uom: str, reason: str | None, occurred_at: datetime | None,
    include_cost: bool,
) -> dict:
    _actor_scope(context)
    category = _category(category)
    quantity = _source_quantity(source_quantity)
    source_uom = _source_uom(source_uom)
    reason = _reason(reason)
    if category == 'OTHER' and reason is None:
        raise errors.InvalidInventoryLossError('OTHER loss requires a reason')
    occurred_at = occurred_at or await inventory_service._database_now(db)
    try:
        item, warehouse = await _scope(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id, for_update=False,
        )
        if item.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
            raise errors.InvalidInventoryLossError(
                'Draft loss requires an active Inventory Item and Warehouse'
            )
        await _validate_uom(
            db, item=item, quantity=quantity, source_uom=source_uom,
            as_of=occurred_at,
        )
        value = InventoryLoss(
            tenant_id=item.tenant_id, organization_id=item.organization_id,
            location_id=item.location_id, warehouse_id=warehouse.id,
            inventory_item_id=item.id, category=category,
            source_quantity=quantity, source_uom=source_uom,
            reason=reason, occurred_at=occurred_at,
            created_by_actor_id=context.principal_id, status='DRAFT', version=1,
            approval_required=False, evidence_status='PENDING',
        )
        db.add(value)
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost=include_cost)
    except Exception:
        await db.rollback()
        raise


async def update_loss(
    db: AsyncSession, *, context: ExecutionContext, loss_id: int,
    expected_version: int, changes: dict, include_cost: bool,
) -> dict:
    _actor_scope(context)
    try:
        value = await _loss(
            db, tenant_id=context.tenant_id, loss_id=loss_id, for_update=True,
        )
        if value.status != 'DRAFT' or value.version != expected_version:
            raise errors.InventoryLossConflictError('Only the expected draft may be updated')
        category = _category(changes.get('category', value.category))
        quantity = _source_quantity(changes.get('source_quantity', value.source_quantity))
        source_uom = _source_uom(changes.get('source_uom', value.source_uom))
        reason = _reason(changes['reason']) if 'reason' in changes else value.reason
        occurred_at = changes.get('occurred_at', value.occurred_at)
        if category == 'OTHER' and reason is None:
            raise errors.InvalidInventoryLossError('OTHER loss requires a reason')
        item, warehouse = await _scope(
            db, tenant_id=context.tenant_id,
            inventory_item_id=value.inventory_item_id,
            warehouse_id=value.warehouse_id, for_update=True,
        )
        if item.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
            raise errors.InvalidInventoryLossError(
                'Draft loss requires an active Inventory Item and Warehouse'
            )
        await _validate_uom(
            db, item=item, quantity=quantity, source_uom=source_uom,
            as_of=occurred_at,
        )
        value.category = category
        value.source_quantity = quantity
        value.source_uom = source_uom
        value.reason = reason
        value.occurred_at = occurred_at
        value.version += 1
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost=include_cost)
    except Exception:
        await db.rollback()
        raise


async def get_loss(
    db: AsyncSession, *, tenant_id: int, loss_id: int, include_cost: bool,
) -> dict:
    return await _projection(
        db, await _loss(db, tenant_id=tenant_id, loss_id=loss_id),
        include_cost=include_cost,
    )


async def list_losses(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    include_cost: bool,
) -> tuple[dict, ...]:
    values = tuple((await db.scalars(select(InventoryLoss).where(
        InventoryLoss.tenant_id == tenant_id,
        InventoryLoss.location_id == location_id,
    ).order_by(InventoryLoss.id.desc()))).all())
    return tuple([
        await _projection(db, value, include_cost=include_cost) for value in values
    ])


async def _resolve_evidence(
    db: AsyncSession, *, value: InventoryLoss, item: InventoryItem,
) -> None:
    normalized, source_uom, conversion, factor = (
        await inventory_service.resolve_quantity_evidence(
            db, item=item, quantity=value.source_quantity,
            source_uom=value.source_uom, as_of=value.occurred_at,
        )
    )
    cost_revision = await inventory_service.resolve_cost_as_of(
        db, tenant_id=value.tenant_id, inventory_item_id=item.id,
        as_of=value.occurred_at,
    )
    value.source_uom = source_uom
    value.conversion_revision_id = conversion.id if conversion is not None else None
    value.conversion_factor = factor
    value.base_uom_evidence = item.base_uom
    value.normalized_quantity = normalized
    if cost_revision is None:
        value.standard_cost_revision_id = None
        value.standard_unit_cost_evidence = None
        value.cost_currency_evidence = None
        value.extended_loss_cost = None
        value.evidence_status = 'COST_NON_DERIVABLE'
    else:
        value.standard_cost_revision_id = cost_revision.id
        value.standard_unit_cost_evidence = cost_revision.standard_unit_cost
        value.cost_currency_evidence = cost_revision.currency
        value.extended_loss_cost = (
            normalized * cost_revision.standard_unit_cost
        ).quantize(_MONEY_UNIT)
        value.evidence_status = 'RESOLVED'


async def _approval_decision(
    db: AsyncSession, *, value: InventoryLoss,
) -> tuple[bool, str]:
    with db.no_autoflush:
        policy = await db.scalar(select(InventoryLossPolicy).where(
            InventoryLossPolicy.tenant_id == value.tenant_id,
            InventoryLossPolicy.warehouse_id == value.warehouse_id,
            InventoryLossPolicy.status == 'ACTIVE',
        ).with_for_update())
    if value.evidence_status == 'COST_NON_DERIVABLE':
        return True, 'COST_NON_DERIVABLE'
    if policy is None:
        return True, 'NO_POLICY'
    if value.cost_currency_evidence != policy.currency:
        return True, 'CURRENCY_MISMATCH'
    if value.extended_loss_cost >= policy.approval_value_threshold:
        return True, 'VALUE_THRESHOLD'
    return False, 'BELOW_THRESHOLD'


async def _post_movement(
    db: AsyncSession, *, value: InventoryLoss, item: InventoryItem,
    warehouse: Warehouse, actor_id: int,
) -> StockMovement:
    if value.normalized_quantity is None or value.conversion_factor is None:
        raise errors.InvalidInventoryLossError('Loss evidence is not resolved')
    current = await inventory_service.stock_quantity(
        db, tenant_id=value.tenant_id, warehouse_id=warehouse.id,
        inventory_item_id=item.id,
    )
    quantity = -value.normalized_quantity
    resulting = (current + quantity).quantize(QUANTITY_UNIT)
    warning = resulting < _ZERO and warehouse.negative_stock_policy in ('WARN', 'BLOCK')
    if warehouse.negative_stock_policy == 'BLOCK' and resulting < _ZERO:
        raise errors.NegativeStockBlockedError(
            'Inventory Loss would make Warehouse stock negative'
        )
    movement = StockMovement(
        tenant_id=value.tenant_id, organization_id=value.organization_id,
        location_id=value.location_id, warehouse_id=value.warehouse_id,
        inventory_item_id=value.inventory_item_id, movement_type='WASTE',
        quantity=quantity, reversal_of_movement_id=None,
        reason=value.reason or value.category, reference=f'INVENTORY_LOSS:{value.id}',
        recorded_at=value.occurred_at, actor_type='EMPLOYEE', actor_id=actor_id,
        actor_reference=None, opening_balance_slot=None,
        idempotency_actor_scope=f'INVENTORY_LOSS:{value.id}',
        idempotency_key='POST', request_schema_version=1,
        request_fingerprint=value.post_fingerprint,
        negative_stock_policy=warehouse.negative_stock_policy,
        negative_stock_warning=warning, resulting_stock_quantity=resulting,
        source_quantity=-value.source_quantity, source_uom=value.source_uom,
        conversion_revision_id=value.conversion_revision_id,
        conversion_factor=value.conversion_factor,
        base_uom_evidence=value.base_uom_evidence,
        standard_cost_revision_id=value.standard_cost_revision_id,
        standard_unit_cost_evidence=value.standard_unit_cost_evidence,
        cost_currency_evidence=value.cost_currency_evidence,
        extended_standard_cost=(
            -value.extended_loss_cost if value.extended_loss_cost is not None else None
        ),
        evidence_status=value.evidence_status,
        inventory_loss_id=value.id, loss_movement_role='ORIGINAL',
    )
    db.add(movement)
    await db.flush()
    return movement


async def post_loss(
    db: AsyncSession, *, context: ExecutionContext, loss_id: int,
    expected_version: int, idempotency_key: str, include_cost: bool,
) -> tuple[dict, bool]:
    actor_scope = _actor_scope(context)
    fingerprint = _fingerprint({
        'schema_version': 1, 'command': 'POST', 'loss_id': loss_id,
        'expected_version': expected_version,
    })
    try:
        value = await _loss(
            db, tenant_id=context.tenant_id, loss_id=loss_id, for_update=True,
        )
        if value.status in ('PENDING_APPROVAL', 'POSTED'):
            if (
                value.post_actor_scope == actor_scope
                and value.post_idempotency_key == idempotency_key
                and value.post_fingerprint == fingerprint
            ):
                return await _projection(db, value, include_cost=include_cost), True
            raise errors.InventoryLossConflictError('Loss was already submitted or posted')
        if value.status != 'DRAFT' or value.version != expected_version:
            raise errors.InventoryLossConflictError('Only the expected draft may be posted')
        item, warehouse = await _scope(
            db, tenant_id=context.tenant_id,
            inventory_item_id=value.inventory_item_id,
            warehouse_id=value.warehouse_id, for_update=True,
        )
        if item.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
            raise errors.InvalidInventoryLossError(
                'Posting requires an active Inventory Item and Warehouse'
            )
        await _resolve_evidence(db, value=value, item=item)
        required, approval_reason = await _approval_decision(db, value=value)
        now = await inventory_service._database_now(db)
        value.approval_required = required
        value.approval_reason = approval_reason
        value.approval_requested_at = now if required else None
        value.approval_requested_by_actor_id = context.principal_id if required else None
        value.post_actor_scope = actor_scope
        value.post_idempotency_key = idempotency_key
        value.post_fingerprint = fingerprint
        value.version += 1
        if required:
            value.status = 'PENDING_APPROVAL'
        else:
            value.status = 'POSTED'
            value.posted_at = now
            value.posted_by_actor_id = context.principal_id
            await _post_movement(
                db, value=value, item=item, warehouse=warehouse,
                actor_id=context.principal_id,
            )
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost=include_cost), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(select(InventoryLoss).where(
            InventoryLoss.tenant_id == context.tenant_id,
            InventoryLoss.post_actor_scope == actor_scope,
            InventoryLoss.post_idempotency_key == idempotency_key,
        ))
        if winner is not None and winner.id == loss_id and winner.post_fingerprint == fingerprint:
            return await _projection(db, winner, include_cost=include_cost), True
        raise errors.InventoryLossConflictError('Loss post conflict') from exc
    except Exception:
        await db.rollback()
        raise


async def approve_loss(
    db: AsyncSession, *, context: ExecutionContext, loss_id: int,
    expected_version: int, idempotency_key: str, include_cost: bool,
) -> tuple[dict, bool]:
    actor_scope = _actor_scope(context)
    fingerprint = _fingerprint({
        'schema_version': 1, 'command': 'APPROVE', 'loss_id': loss_id,
        'expected_version': expected_version,
    })
    try:
        value = await _loss(
            db, tenant_id=context.tenant_id, loss_id=loss_id, for_update=True,
        )
        if value.status == 'POSTED':
            if (
                value.approval_actor_scope == actor_scope
                and value.approval_idempotency_key == idempotency_key
                and value.approval_fingerprint == fingerprint
            ):
                return await _projection(db, value, include_cost=include_cost), True
            raise errors.InventoryLossConflictError('Loss was already posted')
        if value.status != 'PENDING_APPROVAL' or value.version != expected_version:
            raise errors.InventoryLossConflictError(
                'Only the expected pending loss may be approved'
            )
        if value.approval_requested_by_actor_id == context.principal_id:
            raise errors.InvalidInventoryLossError('A requester cannot self-approve a loss')
        item, warehouse = await _scope(
            db, tenant_id=context.tenant_id,
            inventory_item_id=value.inventory_item_id,
            warehouse_id=value.warehouse_id, for_update=True,
        )
        if item.status != 'ACTIVE' or warehouse.status != 'ACTIVE':
            raise errors.InvalidInventoryLossError(
                'Approval requires an active Inventory Item and Warehouse'
            )
        await _post_movement(
            db, value=value, item=item, warehouse=warehouse,
            actor_id=context.principal_id,
        )
        now = await inventory_service._database_now(db)
        value.status = 'POSTED'
        value.version += 1
        value.approved_at = now
        value.approved_by_actor_id = context.principal_id
        value.posted_at = now
        value.posted_by_actor_id = context.principal_id
        value.approval_actor_scope = actor_scope
        value.approval_idempotency_key = idempotency_key
        value.approval_fingerprint = fingerprint
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost=include_cost), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(select(InventoryLoss).where(
            InventoryLoss.tenant_id == context.tenant_id,
            InventoryLoss.approval_actor_scope == actor_scope,
            InventoryLoss.approval_idempotency_key == idempotency_key,
        ))
        if winner is not None and winner.id == loss_id and winner.approval_fingerprint == fingerprint:
            return await _projection(db, winner, include_cost=include_cost), True
        raise errors.InventoryLossConflictError('Loss approval conflict') from exc
    except Exception:
        await db.rollback()
        raise


async def cancel_loss(
    db: AsyncSession, *, context: ExecutionContext, loss_id: int,
    expected_version: int, include_cost: bool,
) -> dict:
    _actor_scope(context)
    try:
        value = await _loss(
            db, tenant_id=context.tenant_id, loss_id=loss_id, for_update=True,
        )
        if value.status not in ('DRAFT', 'PENDING_APPROVAL') or value.version != expected_version:
            raise errors.InventoryLossConflictError(
                'Only the expected non-posted loss may be cancelled'
            )
        value.status = 'CANCELLED'
        value.version += 1
        value.cancelled_at = await inventory_service._database_now(db)
        value.cancelled_by_actor_id = context.principal_id
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost=include_cost)
    except Exception:
        await db.rollback()
        raise


async def reverse_loss(
    db: AsyncSession, *, context: ExecutionContext, loss_id: int,
    expected_version: int, idempotency_key: str, reason: str,
    include_cost: bool,
) -> tuple[dict, bool]:
    actor_scope = _actor_scope(context)
    reason = _reason(reason)
    if reason is None:
        raise errors.InvalidInventoryLossError('Reversal reason is required')
    fingerprint = _fingerprint({
        'schema_version': 1, 'command': 'REVERSE', 'loss_id': loss_id,
        'expected_version': expected_version, 'reason': reason,
    })
    try:
        value = await _loss(
            db, tenant_id=context.tenant_id, loss_id=loss_id, for_update=True,
        )
        if value.status == 'REVERSED':
            if (
                value.reversal_actor_scope == actor_scope
                and value.reversal_idempotency_key == idempotency_key
                and value.reversal_fingerprint == fingerprint
            ):
                return await _projection(db, value, include_cost=include_cost), True
            raise errors.InventoryLossConflictError('Loss was already reversed')
        if value.status != 'POSTED' or value.version != expected_version:
            raise errors.InventoryLossConflictError('Only the expected posted loss may be reversed')
        item, warehouse = await _scope(
            db, tenant_id=context.tenant_id,
            inventory_item_id=value.inventory_item_id,
            warehouse_id=value.warehouse_id, for_update=True,
        )
        original = await db.scalar(select(StockMovement).where(
            StockMovement.tenant_id == value.tenant_id,
            StockMovement.inventory_loss_id == value.id,
            StockMovement.loss_movement_role == 'ORIGINAL',
        ).with_for_update())
        if original is None:
            raise errors.InvalidInventoryLossError('Posted loss movement is missing')
        prior = await db.scalar(select(StockMovement.id).where(
            StockMovement.reversal_of_movement_id == original.id,
        ).with_for_update())
        if prior is not None:
            raise errors.InventoryLossConflictError('Loss movement was already reversed')
        current = await inventory_service.stock_quantity(
            db, tenant_id=value.tenant_id, warehouse_id=warehouse.id,
            inventory_item_id=item.id,
        )
        quantity = -original.quantity
        now = await inventory_service._database_now(db)
        reversal = StockMovement(
            tenant_id=original.tenant_id, organization_id=original.organization_id,
            location_id=original.location_id, warehouse_id=original.warehouse_id,
            inventory_item_id=original.inventory_item_id, movement_type='REVERSAL',
            quantity=quantity, reversal_of_movement_id=original.id,
            reason=reason, reference=f'INVENTORY_LOSS_REVERSAL:{value.id}',
            recorded_at=now, actor_type='EMPLOYEE', actor_id=context.principal_id,
            actor_reference=None, opening_balance_slot=None,
            idempotency_actor_scope=f'INVENTORY_LOSS:{value.id}',
            idempotency_key='REVERSAL', request_schema_version=1,
            request_fingerprint=fingerprint,
            negative_stock_policy=warehouse.negative_stock_policy,
            negative_stock_warning=False,
            resulting_stock_quantity=(current + quantity).quantize(QUANTITY_UNIT),
            source_quantity=(
                -original.source_quantity if original.source_quantity is not None else None
            ),
            source_uom=original.source_uom,
            conversion_revision_id=original.conversion_revision_id,
            conversion_factor=original.conversion_factor,
            base_uom_evidence=original.base_uom_evidence,
            standard_cost_revision_id=original.standard_cost_revision_id,
            standard_unit_cost_evidence=original.standard_unit_cost_evidence,
            cost_currency_evidence=original.cost_currency_evidence,
            extended_standard_cost=(
                -original.extended_standard_cost
                if original.extended_standard_cost is not None else None
            ),
            evidence_status=original.evidence_status,
            inventory_loss_id=value.id, loss_movement_role='REVERSAL',
        )
        db.add(reversal)
        value.status = 'REVERSED'
        value.version += 1
        value.reversed_at = now
        value.reversed_by_actor_id = context.principal_id
        value.reversal_actor_scope = actor_scope
        value.reversal_idempotency_key = idempotency_key
        value.reversal_fingerprint = fingerprint
        await db.commit()
        await db.refresh(value)
        return await _projection(db, value, include_cost=include_cost), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await db.scalar(select(InventoryLoss).where(
            InventoryLoss.tenant_id == context.tenant_id,
            InventoryLoss.reversal_actor_scope == actor_scope,
            InventoryLoss.reversal_idempotency_key == idempotency_key,
        ))
        if winner is not None and winner.id == loss_id and winner.reversal_fingerprint == fingerprint:
            return await _projection(db, winner, include_cost=include_cost), True
        raise errors.InventoryLossConflictError('Loss reversal conflict') from exc
    except Exception:
        await db.rollback()
        raise
