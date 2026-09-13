from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (InventoryCostLayer, InventoryItem, InventoryLot,
    InventoryMovementCostAllocation, InventoryTransfer, InventoryTransferLine,
    InventoryTransferReceipt, InventoryValuationSnapshot,
    InventoryValuationSnapshotFifoLayer, StockMovement, Warehouse)
from app.restaurant.inventory import errors
from app.restaurant.inventory.units import QUANTITY_UNIT, exact_quantity

ZERO=Decimal('0'); VALUE=Decimal('0.000000000001')

class B11Error(errors.InventoryError): code='FIFO_TRANSFER_CONFLICT'
class B11NotFound(B11Error): code='FIFO_TRANSFER_NOT_FOUND'
class FifoNonDerivable(B11Error): code='FIFO_NON_DERIVABLE'

def _actor(c:ExecutionContext)->int:
    if c.actor_type is not ActorType.EMPLOYEE or c.principal_id is None: raise B11Error('Employee authority is required')
    return c.principal_id
def _hash(v:object)->str: return hashlib.sha256(json.dumps(v,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def _d(v:Decimal|None)->str|None: return None if v is None else format(v,'f')
async def _now(db:AsyncSession)->datetime: return (await db.scalar(select(func.current_timestamp()))) or datetime.now(timezone.utc).replace(tzinfo=None)

async def create_layer(db:AsyncSession, *, warehouse:Warehouse, item:InventoryItem,
    origin_type:str, origin_id:int, origin_at:datetime, quantity:Decimal,
    unit_cost:Decimal, currency:str, inventory_lot_id:int|None=None,
    origin_layer_id:int|None=None, source_inventory_lot_id:int|None=None)->InventoryCostLayer:
    quantity=exact_quantity(quantity,positive=True)
    value=InventoryCostLayer(tenant_id=item.tenant_id,organization_id=item.organization_id,
        location_id=item.location_id,warehouse_id=warehouse.id,inventory_item_id=item.id,
        inventory_lot_id=inventory_lot_id,source_inventory_lot_id=source_inventory_lot_id,
        origin_type=origin_type,origin_id=origin_id,origin_layer_id=origin_layer_id,
        origin_at=origin_at,original_quantity=quantity,remaining_quantity=quantity,
        unit_cost=Decimal(unit_cost).quantize(VALUE),currency=currency,status='ACTIVE')
    db.add(value); await db.flush(); return value

async def allocate_fifo(db:AsyncSession, *, movement:StockMovement, quantity:Decimal,
    require_complete:bool=False)->list[InventoryMovementCostAllocation]:
    quantity=exact_quantity(quantity,positive=True)
    layers=(await db.scalars(select(InventoryCostLayer).where(
        InventoryCostLayer.tenant_id==movement.tenant_id,
        InventoryCostLayer.warehouse_id==movement.warehouse_id,
        InventoryCostLayer.inventory_item_id==movement.inventory_item_id,
        InventoryCostLayer.status=='ACTIVE',InventoryCostLayer.remaining_quantity>ZERO,
    ).order_by(InventoryCostLayer.origin_at,InventoryCostLayer.id).with_for_update())).all()
    available=sum((Decimal(x.remaining_quantity) for x in layers),ZERO)
    currencies={x.currency for x in layers if x.remaining_quantity>ZERO}
    if require_complete and (available<quantity or len(currencies)!=1):
        raise FifoNonDerivable('Transfer requires complete, single-currency FIFO evidence')
    await db.flush(); remaining=quantity; result=[]; total=ZERO; currency=None
    for order,layer in enumerate(layers,1):
        if remaining<=ZERO: break
        take=min(remaining,Decimal(layer.remaining_quantity)).quantize(QUANTITY_UNIT)
        if take<=ZERO: continue
        if currency is not None and currency!=layer.currency:
            if require_complete: raise FifoNonDerivable('Transfer FIFO layers use incompatible currencies')
            break
        currency=layer.currency; extended=(take*layer.unit_cost).quantize(VALUE)
        allocation=InventoryMovementCostAllocation(tenant_id=movement.tenant_id,
            stock_movement_id=movement.id,cost_layer_id=layer.id,quantity=take,
            unit_cost=layer.unit_cost,extended_cost=extended,currency=layer.currency,
            allocation_order=order)
        db.add(allocation); result.append(allocation); total+=extended
        layer.remaining_quantity=(Decimal(layer.remaining_quantity)-take).quantize(QUANTITY_UNIT)
        if layer.remaining_quantity==ZERO: layer.status='DEPLETED'
        remaining=(remaining-take).quantize(QUANTITY_UNIT)
    if remaining==ZERO:
        movement.fifo_evidence_status='RESOLVED'; movement.fifo_extended_cost=total.quantize(VALUE); movement.fifo_currency=currency
    else:
        movement.fifo_evidence_status='FIFO_NON_DERIVABLE'; movement.fifo_extended_cost=None; movement.fifo_currency=None
    return result

async def list_layers(db:AsyncSession,tenant_id:int,location_id:int,cost_visible:bool)->list[dict]:
    rows=(await db.scalars(select(InventoryCostLayer).where(InventoryCostLayer.tenant_id==tenant_id,InventoryCostLayer.location_id==location_id).order_by(InventoryCostLayer.warehouse_id,InventoryCostLayer.inventory_item_id,InventoryCostLayer.origin_at,InventoryCostLayer.id))).all()
    return [{'id':x.id,'warehouse_id':x.warehouse_id,'inventory_item_id':x.inventory_item_id,
      'inventory_lot_id':x.inventory_lot_id,'source_inventory_lot_id':x.source_inventory_lot_id,
      'origin_type':x.origin_type,'origin_id':x.origin_id,'origin_layer_id':x.origin_layer_id,
      'origin_at':x.origin_at,'original_quantity':_d(x.original_quantity),'remaining_quantity':_d(x.remaining_quantity),
      'unit_cost':_d(x.unit_cost) if cost_visible else None,'currency':x.currency if cost_visible else None,
      'status':x.status,'cost_visible':cost_visible} for x in rows]

async def _transfer(db:AsyncSession,tenant_id:int,transfer_id:int,lock:bool=False)->InventoryTransfer:
    q=select(InventoryTransfer).where(InventoryTransfer.id==transfer_id,InventoryTransfer.tenant_id==tenant_id)
    if lock:q=q.with_for_update()
    x=await db.scalar(q)
    if x is None: raise B11NotFound('Transfer not found')
    return x
async def transfer_location(db:AsyncSession,tenant_id:int,transfer_id:int)->int: return (await _transfer(db,tenant_id,transfer_id)).location_id

async def project_transfer(db:AsyncSession,x:InventoryTransfer,cost_visible:bool)->dict:
    lines=(await db.scalars(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id==x.id).order_by(InventoryTransferLine.line_number))).all()
    projected=[]
    for line in lines:
        receipts=(await db.scalars(select(InventoryTransferReceipt).where(InventoryTransferReceipt.transfer_line_id==line.id).order_by(InventoryTransferReceipt.receipt_sequence,InventoryTransferReceipt.id))).all()
        source=[]
        if line.source_movement_id:
            source=(await db.scalars(select(InventoryMovementCostAllocation).where(InventoryMovementCostAllocation.stock_movement_id==line.source_movement_id).order_by(InventoryMovementCostAllocation.allocation_order))).all()
        projected.append({'id':line.id,'line_number':line.line_number,'inventory_item_id':line.inventory_item_id,
          'sent_quantity':_d(line.sent_quantity),'received_quantity':_d(line.received_quantity),
          'remaining_in_transit':_d(line.sent_quantity-line.received_quantity),'source_movement_id':line.source_movement_id,
          'source_allocations':[{'cost_layer_id':a.cost_layer_id,'quantity':_d(a.quantity),'unit_cost':_d(a.unit_cost) if cost_visible else None,'extended_cost':_d(a.extended_cost) if cost_visible else None,'currency':a.currency if cost_visible else None,'allocation_order':a.allocation_order} for a in source],
          'receipts':[{'sequence':r.receipt_sequence,'source_layer_id':r.source_layer_id,'destination_layer_id':r.destination_layer_id,'destination_movement_id':r.destination_movement_id,'quantity':_d(r.quantity),'unit_cost':_d(r.unit_cost) if cost_visible else None,'extended_cost':_d(r.extended_cost) if cost_visible else None,'currency':r.currency if cost_visible else None} for r in receipts]})
    return {'id':x.id,'location_id':x.location_id,'source_warehouse_id':x.source_warehouse_id,'destination_warehouse_id':x.destination_warehouse_id,'status':x.status,'reference':x.reference,'version':x.version,'submitted_at':x.submitted_at,'shipped_at':x.shipped_at,'received_at':x.received_at,'cancelled_at':x.cancelled_at,'cost_visible':cost_visible,'lines':projected}

async def create_transfer(db:AsyncSession,*,context:ExecutionContext,source_warehouse_id:int,destination_warehouse_id:int,reference:str|None,lines:list[dict],cost_visible:bool)->dict:
    actor=_actor(context)
    if source_warehouse_id==destination_warehouse_id or not lines: raise B11Error('Transfer requires different warehouses and at least one line')
    warehouses=(await db.scalars(select(Warehouse).where(Warehouse.tenant_id==context.tenant_id,Warehouse.id.in_([source_warehouse_id,destination_warehouse_id])).order_by(Warehouse.id).with_for_update())).all()
    if len(warehouses)!=2 or warehouses[0].location_id!=warehouses[1].location_id or any(w.status!='ACTIVE' for w in warehouses): raise B11NotFound('Active warehouses in one authorized location are required')
    source=next(w for w in warehouses if w.id==source_warehouse_id)
    ids=[int(v['inventory_item_id']) for v in lines]
    if len(ids)!=len(set(ids)): raise B11Error('Each item may appear once')
    items=(await db.scalars(select(InventoryItem).where(InventoryItem.tenant_id==context.tenant_id,InventoryItem.location_id==source.location_id,InventoryItem.id.in_(ids)).order_by(InventoryItem.id).with_for_update())).all()
    if len(items)!=len(ids): raise B11NotFound('Inventory item not found in transfer scope')
    x=InventoryTransfer(tenant_id=context.tenant_id,organization_id=source.organization_id,location_id=source.location_id,source_warehouse_id=source_warehouse_id,destination_warehouse_id=destination_warehouse_id,status='DRAFT',reference=reference.strip()[:200] if reference and reference.strip() else None,version=1,created_by_actor_id=actor)
    db.add(x); await db.flush()
    for n,v in enumerate(lines,1):
        q=exact_quantity(Decimal(v['quantity']),positive=True)
        db.add(InventoryTransferLine(tenant_id=x.tenant_id,organization_id=x.organization_id,location_id=x.location_id,transfer_id=x.id,inventory_item_id=int(v['inventory_item_id']),line_number=n,sent_quantity=q,received_quantity=ZERO))
    await db.commit(); await db.refresh(x); return await project_transfer(db,x,cost_visible)

async def list_transfers(db:AsyncSession,tenant_id:int,location_id:int,cost_visible:bool)->list[dict]:
    rows=(await db.scalars(select(InventoryTransfer).where(InventoryTransfer.tenant_id==tenant_id,InventoryTransfer.location_id==location_id).order_by(InventoryTransfer.id.desc()))).all()
    return [await project_transfer(db,x,cost_visible) for x in rows]

def _movement(x:InventoryTransfer,line:InventoryTransferLine,warehouse:Warehouse,*,kind:str,quantity:Decimal,now:datetime,actor:int,key:str,result:Decimal)->StockMovement:
    sign=-quantity if kind=='TRANSFER_OUT' else quantity
    return StockMovement(tenant_id=x.tenant_id,organization_id=x.organization_id,location_id=x.location_id,warehouse_id=warehouse.id,inventory_item_id=line.inventory_item_id,movement_type=kind,quantity=sign,reason=f'Inventory transfer #{x.id}',reference=x.reference,recorded_at=now,actor_type='EMPLOYEE',actor_id=actor,actor_reference=None,opening_balance_slot=None,idempotency_actor_scope=f'INVENTORY_TRANSFER:{x.id}:{kind}',idempotency_key=key,request_schema_version=1,request_fingerprint=_hash({'transfer':x.id,'line':line.id,'kind':kind,'quantity':str(quantity),'key':key}),negative_stock_policy=warehouse.negative_stock_policy,negative_stock_warning=result<ZERO and warehouse.negative_stock_policy=='WARN',resulting_stock_quantity=result,source_quantity=sign,source_uom=(None),conversion_revision_id=None,conversion_factor=Decimal('1'),base_uom_evidence=None,standard_cost_revision_id=None,standard_unit_cost_evidence=None,cost_currency_evidence=None,extended_standard_cost=None,evidence_status='COST_NON_DERIVABLE')

async def command(db:AsyncSession,*,context:ExecutionContext,transfer_id:int,action:str,expected_version:int,key:str,cost_visible:bool,receipts:list[dict]|None=None)->tuple[dict,bool]:
    actor=_actor(context); x=await _transfer(db,context.tenant_id,transfer_id,True)
    if x.last_command_action==action and x.last_command_key==key: return await project_transfer(db,x,cost_visible),True
    if x.version!=expected_version: raise B11Error('Transfer state changed')
    now=await _now(db); lines=(await db.scalars(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id==x.id).order_by(InventoryTransferLine.inventory_item_id).with_for_update())).all()
    if action=='submit':
        if x.status!='DRAFT': raise B11Error('Only DRAFT may be submitted')
        x.status='SUBMITTED';x.submitted_at=now
    elif action=='cancel':
        if x.status not in ('DRAFT','SUBMITTED'): raise B11Error('A shipped transfer cannot be cancelled')
        x.status='CANCELLED';x.cancelled_at=now
    elif action=='ship':
        if x.status!='SUBMITTED': raise B11Error('Only SUBMITTED may be shipped')
        warehouses=(await db.scalars(select(Warehouse).where(Warehouse.id.in_([x.source_warehouse_id,x.destination_warehouse_id])).order_by(Warehouse.id).with_for_update())).all(); source=next(w for w in warehouses if w.id==x.source_warehouse_id)
        for line in lines:
            stock=Decimal(await db.scalar(select(func.coalesce(func.sum(StockMovement.quantity),ZERO)).where(StockMovement.tenant_id==x.tenant_id,StockMovement.warehouse_id==source.id,StockMovement.inventory_item_id==line.inventory_item_id)) or ZERO)
            result=(stock-line.sent_quantity).quantize(QUANTITY_UNIT)
            if source.negative_stock_policy=='BLOCK' and result<ZERO: raise errors.NegativeStockBlockedError('Transfer would make source stock negative')
            item=await db.scalar(select(InventoryItem).where(InventoryItem.id==line.inventory_item_id)); assert item
            m=_movement(x,line,source,kind='TRANSFER_OUT',quantity=line.sent_quantity,now=now,actor=actor,key=f'{key}:{line.id}',result=result); m.source_uom=item.base_uom;m.base_uom_evidence=item.base_uom
            db.add(m);await db.flush();await allocate_fifo(db,movement=m,quantity=line.sent_quantity,require_complete=True);line.source_movement_id=m.id
        x.status='IN_TRANSIT';x.shipped_at=now
    elif action=='receive':
        if x.status!='IN_TRANSIT' or not receipts: raise B11Error('IN_TRANSIT transfer and receipt quantities are required')
        destination=await db.scalar(select(Warehouse).where(Warehouse.id==x.destination_warehouse_id).with_for_update()); assert destination
        requested={int(v['line_id']):exact_quantity(Decimal(v['quantity']),positive=True) for v in receipts}
        if set(requested)-{l.id for l in lines}: raise B11Error('Receipt line is outside transfer')
        for line in lines:
            q=requested.get(line.id)
            if q is None: continue
            if line.received_quantity+q>line.sent_quantity: raise B11Error('Receipt exceeds remaining in-transit quantity')
            item=await db.scalar(select(InventoryItem).where(InventoryItem.id==line.inventory_item_id)); assert item
            stock=Decimal(await db.scalar(select(func.coalesce(func.sum(StockMovement.quantity),ZERO)).where(StockMovement.tenant_id==x.tenant_id,StockMovement.warehouse_id==destination.id,StockMovement.inventory_item_id==line.inventory_item_id)) or ZERO)
            m=_movement(x,line,destination,kind='TRANSFER_IN',quantity=q,now=now,actor=actor,key=f'{key}:{line.id}',result=(stock+q).quantize(QUANTITY_UNIT));m.source_uom=item.base_uom;m.base_uom_evidence=item.base_uom
            db.add(m);await db.flush()
            allocations=(await db.scalars(select(InventoryMovementCostAllocation).where(InventoryMovementCostAllocation.stock_movement_id==line.source_movement_id).order_by(InventoryMovementCostAllocation.allocation_order))).all()
            already={layer_id:Decimal(amount) for layer_id,amount in (await db.execute(select(InventoryTransferReceipt.source_layer_id,func.sum(InventoryTransferReceipt.quantity)).where(InventoryTransferReceipt.transfer_line_id==line.id).group_by(InventoryTransferReceipt.source_layer_id))).all()}
            remaining=q; total=ZERO; currency=None; sequence=int(await db.scalar(select(func.coalesce(func.max(InventoryTransferReceipt.receipt_sequence),0)).where(InventoryTransferReceipt.transfer_line_id==line.id)) or 0)+1
            for a in allocations:
                available=Decimal(a.quantity)-already.get(a.cost_layer_id,ZERO)
                take=min(remaining,available).quantize(QUANTITY_UNIT)
                if take<=ZERO: continue
                source_layer=await db.scalar(select(InventoryCostLayer).where(InventoryCostLayer.id==a.cost_layer_id)); assert source_layer
                layer=await create_layer(db,warehouse=destination,item=item,origin_type='TRANSFER',origin_id=m.id,origin_at=now,quantity=take,unit_cost=a.unit_cost,currency=a.currency,origin_layer_id=a.cost_layer_id,source_inventory_lot_id=source_layer.inventory_lot_id or source_layer.source_inventory_lot_id)
                extended=(take*a.unit_cost).quantize(VALUE);total+=extended;currency=a.currency
                db.add(InventoryTransferReceipt(tenant_id=x.tenant_id,transfer_line_id=line.id,receipt_sequence=sequence,source_layer_id=a.cost_layer_id,destination_layer_id=layer.id,destination_movement_id=m.id,quantity=take,unit_cost=a.unit_cost,extended_cost=extended,currency=a.currency));remaining-=take
            if remaining!=ZERO: raise FifoNonDerivable('Transfer receipt cannot reproduce shipped FIFO evidence')
            m.fifo_evidence_status='RESOLVED';m.fifo_extended_cost=total.quantize(VALUE);m.fifo_currency=currency;line.received_quantity=(line.received_quantity+q).quantize(QUANTITY_UNIT)
        if all(l.received_quantity==l.sent_quantity for l in lines):x.status='RECEIVED';x.received_at=now
    else: raise B11Error('Unsupported transfer action')
    x.version+=1;x.last_command_action=action;x.last_command_key=key
    try: await db.commit();await db.refresh(x);return await project_transfer(db,x,cost_visible),False
    except IntegrityError as exc:
        await db.rollback();raise B11Error('Transfer command conflict') from exc

async def create_fifo_snapshot(db:AsyncSession,*,context:ExecutionContext,warehouse_id:int,as_of:datetime,currency:str,idempotency_key:str,cost_visible:bool)->tuple[dict,bool]:
    from app.restaurant.inventory import replenishment_lots_valuation as b10
    actor=_actor(context); warehouse=await db.scalar(select(Warehouse).where(Warehouse.id==warehouse_id,Warehouse.tenant_id==context.tenant_id).with_for_update())
    if warehouse is None: raise B11NotFound('Warehouse not found')
    if as_of.tzinfo is not None: as_of=as_of.astimezone(timezone.utc).replace(tzinfo=None,microsecond=0)
    currency=currency.upper(); fp=_hash({'warehouse':warehouse_id,'as_of':as_of.isoformat(),'currency':currency,'method':'FIFO'})
    existing=await db.scalar(select(InventoryValuationSnapshot).where(InventoryValuationSnapshot.tenant_id==context.tenant_id,InventoryValuationSnapshot.idempotency_actor_scope==f'EMPLOYEE:{actor}',InventoryValuationSnapshot.idempotency_key==idempotency_key).with_for_update())
    if existing:
        if existing.request_fingerprint!=fp: raise B11Error('Idempotency key conflict')
        return await b10.project_snapshot(db,existing,cost_visible),True
    movement_cursor=int(await db.scalar(select(func.coalesce(func.max(StockMovement.id),0)).where(StockMovement.tenant_id==context.tenant_id,StockMovement.warehouse_id==warehouse_id,StockMovement.recorded_at<=as_of)) or 0)
    layer_cursor=int(await db.scalar(select(func.coalesce(func.max(InventoryCostLayer.id),0)).where(InventoryCostLayer.tenant_id==context.tenant_id,InventoryCostLayer.warehouse_id==warehouse_id,InventoryCostLayer.origin_at<=as_of)) or 0)
    snap=InventoryValuationSnapshot(tenant_id=context.tenant_id,organization_id=warehouse.organization_id,location_id=warehouse.location_id,warehouse_id=warehouse.id,status='FINALIZED',valuation_method='FIFO',as_of=as_of,movement_cursor=movement_cursor,layer_cursor=layer_cursor,currency=currency,derivable_total_value=ZERO,non_derivable_line_count=0,created_by_actor_id=actor,idempotency_actor_scope=f'EMPLOYEE:{actor}',idempotency_key=idempotency_key,request_fingerprint=fp)
    db.add(snap);await db.flush();total=ZERO
    layers=(await db.scalars(select(InventoryCostLayer).where(InventoryCostLayer.tenant_id==context.tenant_id,InventoryCostLayer.warehouse_id==warehouse_id,InventoryCostLayer.origin_at<=as_of,InventoryCostLayer.id<=layer_cursor).order_by(InventoryCostLayer.inventory_item_id,InventoryCostLayer.origin_at,InventoryCostLayer.id))).all()
    layered:dict[int,Decimal]={}
    for layer in layers:
        allocated=Decimal(await db.scalar(select(func.coalesce(func.sum(InventoryMovementCostAllocation.quantity),ZERO)).join(StockMovement,StockMovement.id==InventoryMovementCostAllocation.stock_movement_id).where(InventoryMovementCostAllocation.cost_layer_id==layer.id,StockMovement.recorded_at<=as_of,StockMovement.id<=movement_cursor)) or ZERO)
        q=(layer.original_quantity-allocated).quantize(QUANTITY_UNIT)
        if q<=ZERO:continue
        evidence='RESOLVED' if layer.currency==currency else 'CURRENCY_MISMATCH'; value=(q*layer.unit_cost).quantize(VALUE) if evidence=='RESOLVED' else None
        if value is not None:total+=value
        else:snap.non_derivable_line_count+=1
        layered[layer.inventory_item_id]=layered.get(layer.inventory_item_id,ZERO)+q
        db.add(InventoryValuationSnapshotFifoLayer(tenant_id=context.tenant_id,snapshot_id=snap.id,inventory_item_id=layer.inventory_item_id,cost_layer_id=layer.id,quantity_as_of=q,unit_cost_evidence=layer.unit_cost,cost_currency_evidence=layer.currency,line_value=value,evidence_status=evidence))
    stock=dict((i,Decimal(q)) for i,q in (await db.execute(select(StockMovement.inventory_item_id,func.sum(StockMovement.quantity)).where(StockMovement.tenant_id==context.tenant_id,StockMovement.warehouse_id==warehouse_id,StockMovement.recorded_at<=as_of,StockMovement.id<=movement_cursor).group_by(StockMovement.inventory_item_id))).all())
    snap.non_derivable_line_count+=sum(1 for i,q in stock.items() if q!=layered.get(i,ZERO));snap.derivable_total_value=total.quantize(VALUE)
    await db.commit();await db.refresh(snap);return await b10.project_snapshot(db,snap,cost_visible),False
