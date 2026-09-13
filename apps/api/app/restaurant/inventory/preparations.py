from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    InventoryItem, Location, PreparationBatch, PreparationBatchInput,
    PreparationBatchOutput, PreparationRecipeComponent,
    PreparationRecipeVersion, StockMovement, Warehouse,
)
from app.restaurant.inventory import errors, service
from app.restaurant.inventory.units import QUANTITY_UNIT, UnitConversionError, exact_quantity

ZERO = Decimal('0')
COST_UNIT = Decimal('0.000000000001')


class PreparationError(errors.InventoryError):
    code = 'PREPARATION_CONFLICT'


class PreparationNotFound(PreparationError):
    code = 'PREPARATION_NOT_FOUND'


def _actor(context: ExecutionContext) -> int:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise PreparationError('Preparation operations require an employee actor')
    return context.principal_id


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, 'f')


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


async def _now(db: AsyncSession) -> datetime:
    value = await db.scalar(select(func.current_timestamp()))
    assert value is not None
    return value


async def _recipe(db: AsyncSession, tenant_id: int, recipe_id: int, lock: bool = False) -> PreparationRecipeVersion:
    statement = select(PreparationRecipeVersion).where(PreparationRecipeVersion.id == recipe_id, PreparationRecipeVersion.tenant_id == tenant_id)
    value = await db.scalar(statement.with_for_update() if lock else statement)
    if value is None:
        raise PreparationNotFound('Preparation recipe version not found')
    return value


async def _batch(db: AsyncSession, tenant_id: int, batch_id: int, lock: bool = False) -> PreparationBatch:
    statement = select(PreparationBatch).where(PreparationBatch.id == batch_id, PreparationBatch.tenant_id == tenant_id)
    value = await db.scalar(statement.with_for_update() if lock else statement)
    if value is None:
        raise PreparationNotFound('Preparation batch not found')
    return value


async def location_for_recipe(db: AsyncSession, tenant_id: int, recipe_id: int) -> int:
    return (await _recipe(db, tenant_id, recipe_id)).location_id


async def location_for_batch(db: AsyncSession, tenant_id: int, batch_id: int) -> int:
    return (await _batch(db, tenant_id, batch_id)).location_id


async def project_recipe(db: AsyncSession, value: PreparationRecipeVersion) -> dict:
    components = (await db.scalars(select(PreparationRecipeComponent).where(PreparationRecipeComponent.recipe_version_id == value.id).order_by(PreparationRecipeComponent.line_number))).all()
    basis = next(component for component in components if component.yield_basis_slot == 1)
    expected_yield = value.normalized_expected_output_quantity / basis.normalized_expected_quantity
    return {
        'id': value.id, 'location_id': value.location_id,
        'output_inventory_item_id': value.output_inventory_item_id,
        'revision': value.revision, 'status': value.status,
        'publication_status': value.publication_status,
        'expected_output_quantity': _decimal(value.expected_output_quantity),
        'output_source_uom': value.output_source_uom,
        'normalized_expected_output_quantity': _decimal(value.normalized_expected_output_quantity),
        'output_base_uom_evidence': value.output_base_uom_evidence,
        'expected_yield': _decimal(expected_yield),
        'effective_from': value.effective_from, 'effective_to': value.effective_to,
        'published_at': value.published_at,
        'components': [{
            'id': row.id, 'inventory_item_id': row.inventory_item_id,
            'line_number': row.line_number,
            'expected_quantity': _decimal(row.expected_quantity),
            'source_uom': row.source_uom,
            'normalized_expected_quantity': _decimal(row.normalized_expected_quantity),
            'base_uom_evidence': row.base_uom_evidence,
            'yield_basis': row.yield_basis_slot == 1,
        } for row in components],
    }


async def publish_recipe(
    db: AsyncSession, *, context: ExecutionContext, location_id: int,
    output_inventory_item_id: int, expected_output_quantity: Decimal,
    output_uom: str, status: str, effective_from: datetime | None,
    effective_to: datetime | None, expected_revision: int,
    components: tuple[dict, ...],
) -> dict:
    actor_id = _actor(context)
    status = status.strip().upper()
    if status not in ('ACTIVE', 'INACTIVE'):
        raise PreparationError('Unsupported recipe status')
    if not components or sum(bool(row['yield_basis']) for row in components) != 1:
        raise PreparationError('A recipe requires inputs and exactly one yield-basis component')
    ids = [int(row['inventory_item_id']) for row in components]
    if len(ids) != len(set(ids)) or output_inventory_item_id in ids:
        raise PreparationError('Recipe inputs must be unique and distinct from the output')
    now = await _now(db)
    effective_from = effective_from or now
    if effective_to is not None and effective_to < effective_from:
        raise PreparationError('Recipe effectivity is invalid')
    try:
        location = await db.scalar(select(Location).where(Location.id == location_id, Location.tenant_id == context.tenant_id))
        if location is None:
            raise errors.InventoryScopeNotFoundError('Location not found')
        item_rows = (await db.scalars(select(InventoryItem).where(
            InventoryItem.tenant_id == context.tenant_id,
            InventoryItem.organization_id == location.organization_id,
            InventoryItem.location_id == location_id,
            InventoryItem.id.in_([output_inventory_item_id, *ids]),
        ).order_by(InventoryItem.id).with_for_update())).all()
        items = {row.id: row for row in item_rows}
        if set(items) != {output_inventory_item_id, *ids} or any(row.status != 'ACTIVE' for row in item_rows):
            raise errors.InventoryScopeNotFoundError('Active recipe item not found')
        latest = await db.scalar(select(PreparationRecipeVersion).where(
            PreparationRecipeVersion.tenant_id == context.tenant_id,
            PreparationRecipeVersion.location_id == location_id,
            PreparationRecipeVersion.output_inventory_item_id == output_inventory_item_id,
        ).order_by(PreparationRecipeVersion.revision.desc()).limit(1).with_for_update())
        current_revision = latest.revision if latest else 0
        if expected_revision != current_revision:
            raise PreparationError(f'Expected revision {expected_revision}, current revision is {current_revision}')
        if latest is not None and effective_from < latest.effective_from:
            raise PreparationError('Recipe versions cannot be backdated')
        try:
            output_quantity = exact_quantity(expected_output_quantity, positive=True)
            output_normalized, output_source_uom, output_conversion, output_factor = await service.resolve_quantity_evidence(db, item=items[output_inventory_item_id], quantity=output_quantity, source_uom=output_uom, as_of=now)
        except UnitConversionError as exc:
            raise PreparationError(str(exc)) from exc
        version = PreparationRecipeVersion(
            tenant_id=context.tenant_id, organization_id=location.organization_id,
            location_id=location_id, output_inventory_item_id=output_inventory_item_id,
            revision=current_revision + 1, status=status, publication_status='PUBLISHED',
            expected_output_quantity=output_quantity, output_source_uom=output_source_uom,
            output_conversion_revision_id=output_conversion.id if output_conversion else None,
            output_conversion_factor=output_factor,
            output_base_uom_evidence=items[output_inventory_item_id].base_uom,
            normalized_expected_output_quantity=output_normalized,
            effective_from=effective_from, effective_to=effective_to,
            actor_id=actor_id, source='STAFF_API', published_at=now,
        )
        db.add(version); await db.flush()
        for number, row in enumerate(components, 1):
            try:
                quantity = exact_quantity(row['expected_quantity'], positive=True)
                normalized, source_uom, conversion, factor = await service.resolve_quantity_evidence(db, item=items[int(row['inventory_item_id'])], quantity=quantity, source_uom=row['source_uom'], as_of=now)
            except UnitConversionError as exc:
                raise PreparationError(str(exc)) from exc
            db.add(PreparationRecipeComponent(
                tenant_id=context.tenant_id, organization_id=location.organization_id,
                location_id=location_id, recipe_version_id=version.id,
                inventory_item_id=int(row['inventory_item_id']), line_number=number,
                expected_quantity=quantity, source_uom=source_uom,
                conversion_revision_id=conversion.id if conversion else None,
                conversion_factor=factor, base_uom_evidence=items[int(row['inventory_item_id'])].base_uom,
                normalized_expected_quantity=normalized,
                yield_basis_slot=1 if row['yield_basis'] else None,
            ))
        await db.commit(); await db.refresh(version)
        return await project_recipe(db, version)
    except IntegrityError as exc:
        await db.rollback(); raise PreparationError('Recipe publication conflict') from exc
    except Exception:
        await db.rollback(); raise


async def list_recipes(db: AsyncSession, tenant_id: int, location_id: int) -> list[dict]:
    values = (await db.scalars(select(PreparationRecipeVersion).where(PreparationRecipeVersion.tenant_id == tenant_id, PreparationRecipeVersion.location_id == location_id).order_by(PreparationRecipeVersion.output_inventory_item_id, PreparationRecipeVersion.revision.desc()))).all()
    return [await project_recipe(db, row) for row in values]


async def project_batch(db: AsyncSession, value: PreparationBatch, cost_visible: bool) -> dict:
    inputs = (await db.scalars(select(PreparationBatchInput).where(PreparationBatchInput.batch_id == value.id).order_by(PreparationBatchInput.line_number))).all()
    output = await db.scalar(select(PreparationBatchOutput).where(PreparationBatchOutput.batch_id == value.id))
    assert output is not None
    movements = (await db.execute(select(StockMovement.id, StockMovement.movement_type, StockMovement.quantity).where(StockMovement.preparation_batch_id == value.id).order_by(StockMovement.id))).all()
    projected_inputs = []
    for row in inputs:
        item = {'id': row.id, 'recipe_component_id': row.recipe_component_id, 'inventory_item_id': row.inventory_item_id, 'source_quantity': _decimal(row.source_quantity), 'source_uom': row.source_uom, 'normalized_quantity': _decimal(row.normalized_quantity), 'base_uom_evidence': row.base_uom_evidence, 'evidence_status': row.evidence_status}
        if cost_visible: item.update(standard_unit_cost_evidence=_decimal(row.standard_unit_cost_evidence), extended_material_cost=_decimal(row.extended_material_cost), cost_currency_evidence=row.cost_currency_evidence)
        projected_inputs.append(item)
    projected_output = {'id': output.id, 'inventory_item_id': output.inventory_item_id, 'source_quantity': _decimal(output.source_quantity), 'source_uom': output.source_uom, 'normalized_quantity': _decimal(output.normalized_quantity), 'base_uom_evidence': output.base_uom_evidence, 'evidence_status': output.evidence_status}
    if cost_visible: projected_output.update(allocated_material_cost=_decimal(output.allocated_material_cost), unit_material_cost=_decimal(output.unit_material_cost), cost_currency_evidence=output.cost_currency_evidence)
    return {
        'id': value.id, 'location_id': value.location_id, 'warehouse_id': value.warehouse_id,
        'recipe_version_id': value.recipe_version_id, 'status': value.status,
        'version': value.version, 'reference': value.reference,
        'expected_yield': _decimal(value.expected_yield), 'actual_yield': _decimal(value.actual_yield), 'yield_variance': _decimal(value.yield_variance),
        'cost_evidence_status': value.cost_evidence_status,
        'material_cost': _decimal(value.material_cost) if cost_visible else None,
        'prepared_unit_material_cost': _decimal(value.prepared_unit_material_cost) if cost_visible else None,
        'cost_currency_evidence': value.cost_currency_evidence if cost_visible else None,
        'cost_visible': cost_visible, 'created_at': value.created_at,
        'started_at': value.started_at, 'completed_at': value.completed_at,
        'cancelled_at': value.cancelled_at, 'inputs': projected_inputs,
        'output': projected_output,
        'movements': [{'id': row.id, 'movement_type': row.movement_type, 'quantity': _decimal(row.quantity)} for row in movements],
    }


async def create_batch(
    db: AsyncSession, *, context: ExecutionContext, recipe_version_id: int,
    warehouse_id: int, reference: str | None, inputs: tuple[dict, ...],
    output_quantity: Decimal, output_uom: str, cost_visible: bool,
) -> dict:
    actor_id = _actor(context); now = await _now(db)
    recipe = await _recipe(db, context.tenant_id, recipe_version_id, True)
    if recipe.status != 'ACTIVE' or recipe.effective_from > now or (recipe.effective_to is not None and recipe.effective_to < now):
        raise PreparationError('Recipe version is not currently active')
    warehouse = await db.scalar(select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.tenant_id == context.tenant_id, Warehouse.organization_id == recipe.organization_id, Warehouse.location_id == recipe.location_id, Warehouse.status == 'ACTIVE').with_for_update())
    if warehouse is None: raise errors.InventoryScopeNotFoundError('Warehouse not found')
    components = (await db.scalars(select(PreparationRecipeComponent).where(PreparationRecipeComponent.recipe_version_id == recipe.id).order_by(PreparationRecipeComponent.line_number))).all()
    actual = {int(row['recipe_component_id']): row for row in inputs}
    if len(actual) != len(inputs) or set(actual) != {row.id for row in components}:
        raise PreparationError('Actual inputs must cover each recipe component exactly once')
    item_ids = [row.inventory_item_id for row in components] + [recipe.output_inventory_item_id]
    items = {row.id: row for row in (await db.scalars(select(InventoryItem).where(InventoryItem.tenant_id == context.tenant_id, InventoryItem.id.in_(item_ids)).order_by(InventoryItem.id).with_for_update())).all()}
    if set(items) != set(item_ids) or any(row.status != 'ACTIVE' for row in items.values()): raise errors.InventoryScopeNotFoundError('Active batch item not found')
    try:
        out_source = exact_quantity(output_quantity, positive=True)
        out_normalized, out_uom, out_conversion, out_factor = await service.resolve_quantity_evidence(db, item=items[recipe.output_inventory_item_id], quantity=out_source, source_uom=output_uom, as_of=now)
    except UnitConversionError as exc: raise PreparationError(str(exc)) from exc
    prepared_inputs = []
    currencies: set[str] = set(); material_cost = ZERO; derivable = True; actual_basis = None; expected_basis = None
    for component in components:
        row = actual[component.id]
        try:
            source = exact_quantity(row['source_quantity'], positive=True)
            normalized, source_uom, conversion, factor = await service.resolve_quantity_evidence(db, item=items[component.inventory_item_id], quantity=source, source_uom=row['source_uom'], as_of=now)
        except UnitConversionError as exc: raise PreparationError(str(exc)) from exc
        cost = await service.resolve_cost_as_of(db, tenant_id=context.tenant_id, inventory_item_id=component.inventory_item_id, as_of=now)
        extended = (normalized * cost.standard_unit_cost).quantize(COST_UNIT) if cost else None
        if cost is None: derivable = False
        else: currencies.add(cost.currency); material_cost += extended or ZERO
        if component.yield_basis_slot == 1: actual_basis, expected_basis = normalized, component.normalized_expected_quantity
        prepared_inputs.append((component, source, source_uom, normalized, conversion, factor, cost, extended))
    assert actual_basis is not None and expected_basis is not None
    expected_yield = (recipe.normalized_expected_output_quantity / expected_basis).quantize(COST_UNIT)
    actual_yield = (out_normalized / actual_basis).quantize(COST_UNIT)
    derivable = derivable and len(currencies) == 1
    currency = next(iter(currencies)) if derivable else None
    material = material_cost.quantize(COST_UNIT) if derivable else None
    unit_cost = (material_cost / out_normalized).quantize(COST_UNIT) if derivable else None
    batch = PreparationBatch(tenant_id=context.tenant_id, organization_id=recipe.organization_id, location_id=recipe.location_id, warehouse_id=warehouse.id, recipe_version_id=recipe.id, status='DRAFT', expected_yield=expected_yield, actual_yield=actual_yield, yield_variance=(actual_yield-expected_yield).quantize(COST_UNIT), cost_evidence_status='RESOLVED' if derivable else 'COST_NON_DERIVABLE', material_cost=material, prepared_unit_material_cost=unit_cost, cost_currency_evidence=currency, reference=reference.strip()[:200] if reference and reference.strip() else None, created_by_actor_id=actor_id)
    db.add(batch)
    try:
        await db.flush()
        for number, (component, source, source_uom, normalized, conversion, factor, cost, extended) in enumerate(prepared_inputs, 1):
            db.add(PreparationBatchInput(tenant_id=batch.tenant_id, organization_id=batch.organization_id, location_id=batch.location_id, warehouse_id=batch.warehouse_id, batch_id=batch.id, recipe_version_id=recipe.id, recipe_component_id=component.id, inventory_item_id=component.inventory_item_id, line_number=number, source_quantity=source, source_uom=source_uom, normalized_quantity=normalized, conversion_revision_id=conversion.id if conversion else None, conversion_factor=factor, base_uom_evidence=items[component.inventory_item_id].base_uom, standard_cost_revision_id=cost.id if cost else None, standard_unit_cost_evidence=cost.standard_unit_cost if cost else None, cost_currency_evidence=cost.currency if cost else None, extended_material_cost=extended, evidence_status='RESOLVED' if cost else 'COST_NON_DERIVABLE'))
        await db.flush()
        db.add(PreparationBatchOutput(tenant_id=batch.tenant_id, organization_id=batch.organization_id, location_id=batch.location_id, warehouse_id=batch.warehouse_id, batch_id=batch.id, recipe_version_id=recipe.id, inventory_item_id=recipe.output_inventory_item_id, source_quantity=out_source, source_uom=out_uom, normalized_quantity=out_normalized, conversion_revision_id=out_conversion.id if out_conversion else None, conversion_factor=out_factor, base_uom_evidence=items[recipe.output_inventory_item_id].base_uom, allocated_material_cost=material, unit_material_cost=unit_cost, cost_currency_evidence=currency, evidence_status='RESOLVED' if derivable else 'COST_NON_DERIVABLE'))
        await db.commit(); await db.refresh(batch); return await project_batch(db, batch, cost_visible)
    except IntegrityError as exc: await db.rollback(); raise PreparationError('Batch creation conflict') from exc
    except Exception: await db.rollback(); raise


async def list_batches(db: AsyncSession, tenant_id: int, location_id: int, cost_visible: bool) -> list[dict]:
    values = (await db.scalars(select(PreparationBatch).where(PreparationBatch.tenant_id == tenant_id, PreparationBatch.location_id == location_id).order_by(PreparationBatch.id.desc()))).all()
    return [await project_batch(db, row, cost_visible) for row in values]


async def transition(db: AsyncSession, *, context: ExecutionContext, batch_id: int, action: str, expected_version: int, key: str | None, cost_visible: bool) -> tuple[dict, bool]:
    actor_id = _actor(context); batch = await _batch(db, context.tenant_id, batch_id, True)
    if action == 'complete' and batch.status == 'COMPLETED' and batch.completion_command_key == key:
        return await project_batch(db, batch, cost_visible), True
    if batch.version != expected_version:
        raise PreparationError('Preparation batch state changed')
    now = await _now(db)
    if action == 'start':
        if batch.status != 'DRAFT': raise PreparationError('Only a DRAFT batch may start')
        batch.status='IN_PROGRESS'; batch.version += 1; batch.started_at=now; batch.started_by_actor_id=actor_id
        await db.commit(); await db.refresh(batch); return await project_batch(db,batch,cost_visible),False
    if action == 'cancel':
        if batch.status not in ('DRAFT','IN_PROGRESS'): raise PreparationError('Only an open batch may be cancelled')
        batch.status='CANCELLED'; batch.version += 1; batch.cancelled_at=now; batch.cancelled_by_actor_id=actor_id
        await db.commit(); await db.refresh(batch); return await project_batch(db,batch,cost_visible),False
    if action != 'complete' or batch.status != 'IN_PROGRESS' or not key:
        raise PreparationError('Only an IN_PROGRESS batch may complete')
    fingerprint = _fingerprint({'batch_id':batch.id,'version':batch.version,'inputs':'frozen','output':'frozen'})
    warehouse = await db.scalar(select(Warehouse).where(Warehouse.id==batch.warehouse_id,Warehouse.tenant_id==batch.tenant_id,Warehouse.location_id==batch.location_id).with_for_update())
    if warehouse is None or warehouse.status!='ACTIVE': raise errors.InventoryScopeNotFoundError('Active warehouse not found')
    inputs=(await db.scalars(select(PreparationBatchInput).where(PreparationBatchInput.batch_id==batch.id).order_by(PreparationBatchInput.inventory_item_id).with_for_update())).all()
    output=await db.scalar(select(PreparationBatchOutput).where(PreparationBatchOutput.batch_id==batch.id).with_for_update()); assert output is not None
    items={row.id:row for row in (await db.scalars(select(InventoryItem).where(InventoryItem.id.in_([*(row.inventory_item_id for row in inputs),output.inventory_item_id]),InventoryItem.tenant_id==batch.tenant_id).order_by(InventoryItem.id).with_for_update())).all()}
    current: dict[int,Decimal] = {}
    for item_id in sorted(items):
        current[item_id]=Decimal(await db.scalar(select(func.coalesce(func.sum(StockMovement.quantity),ZERO)).where(StockMovement.tenant_id==batch.tenant_id,StockMovement.warehouse_id==batch.warehouse_id,StockMovement.inventory_item_id==item_id)) or ZERO)
    for row in inputs:
        result=(current[row.inventory_item_id]-row.normalized_quantity).quantize(QUANTITY_UNIT)
        if warehouse.negative_stock_policy=='BLOCK' and result < ZERO:
            raise errors.NegativeStockBlockedError('Preparation input would make warehouse stock negative')
        current[row.inventory_item_id]=result
    try:
        for row in inputs:
            resolved=row.evidence_status=='RESOLVED'
            db.add(StockMovement(tenant_id=batch.tenant_id,organization_id=batch.organization_id,location_id=batch.location_id,warehouse_id=batch.warehouse_id,inventory_item_id=row.inventory_item_id,movement_type='PREPARATION_INPUT',quantity=-row.normalized_quantity,reason='Preparation batch input',reference=batch.reference,recorded_at=now,actor_type='EMPLOYEE',actor_id=actor_id,actor_reference=None,opening_balance_slot=None,idempotency_actor_scope=f'PREPARATION_BATCH:{batch.id}',idempotency_key=f'INPUT:{row.id}',request_schema_version=1,request_fingerprint=fingerprint,negative_stock_policy=warehouse.negative_stock_policy,negative_stock_warning=current[row.inventory_item_id]<ZERO and warehouse.negative_stock_policy in ('WARN','BLOCK'),resulting_stock_quantity=current[row.inventory_item_id],source_quantity=-row.source_quantity,source_uom=row.source_uom,conversion_revision_id=row.conversion_revision_id,conversion_factor=row.conversion_factor,base_uom_evidence=row.base_uom_evidence,standard_cost_revision_id=row.standard_cost_revision_id if resolved else None,standard_unit_cost_evidence=row.standard_unit_cost_evidence if resolved else None,cost_currency_evidence=row.cost_currency_evidence if resolved else None,extended_standard_cost=-row.extended_material_cost if resolved and row.extended_material_cost is not None else None,evidence_status=row.evidence_status,preparation_batch_id=batch.id,preparation_batch_input_id=row.id,preparation_batch_output_id=None))
        output_result=(current[output.inventory_item_id]+output.normalized_quantity).quantize(QUANTITY_UNIT)
        db.add(StockMovement(tenant_id=batch.tenant_id,organization_id=batch.organization_id,location_id=batch.location_id,warehouse_id=batch.warehouse_id,inventory_item_id=output.inventory_item_id,movement_type='PREPARATION_OUTPUT',quantity=output.normalized_quantity,reason='Preparation batch output',reference=batch.reference,recorded_at=now,actor_type='EMPLOYEE',actor_id=actor_id,actor_reference=None,opening_balance_slot=None,idempotency_actor_scope=f'PREPARATION_BATCH:{batch.id}',idempotency_key=f'OUTPUT:{output.id}',request_schema_version=1,request_fingerprint=fingerprint,negative_stock_policy=warehouse.negative_stock_policy,negative_stock_warning=False,resulting_stock_quantity=output_result,source_quantity=output.source_quantity,source_uom=output.source_uom,conversion_revision_id=output.conversion_revision_id,conversion_factor=output.conversion_factor,base_uom_evidence=output.base_uom_evidence,standard_cost_revision_id=None,standard_unit_cost_evidence=None,cost_currency_evidence=None,extended_standard_cost=None,evidence_status='COST_NON_DERIVABLE',preparation_batch_id=batch.id,preparation_batch_input_id=None,preparation_batch_output_id=output.id))
        batch.status='COMPLETED'; batch.version+=1; batch.completed_at=now; batch.completed_by_actor_id=actor_id; batch.completion_command_key=key; batch.completion_fingerprint=fingerprint
        await db.commit(); await db.refresh(batch); return await project_batch(db,batch,cost_visible),False
    except IntegrityError as exc:
        await db.rollback(); winner=await _batch(db,context.tenant_id,batch_id)
        if winner.status=='COMPLETED' and winner.completion_command_key==key: return await project_batch(db,winner,cost_visible),True
        raise PreparationError('Preparation completion conflict') from exc
    except Exception: await db.rollback(); raise
