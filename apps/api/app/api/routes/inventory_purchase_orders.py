from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import AuthenticatedContext,get_db,require_permission
from app.core.execution import ActorType,ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import errors,purchase_orders

router=APIRouter(prefix='/inventory/purchase-orders',tags=['purchase-orders'])
def exact(value:Any)->Any:
    if isinstance(value,float): raise ValueError('Binary floating-point values are not valid exact decimals')
    return value
ExactDecimal=Annotated[Decimal,BeforeValidator(exact)]
class LineIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    supplier_offering_id:int=Field(gt=0); ordered_quantity:ExactDecimal=Field(gt=0); agreed_unit_price:ExactDecimal=Field(ge=0)
class CreateIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    location_id:int=Field(gt=0); warehouse_id:int=Field(gt=0); supplier_id:int=Field(gt=0); currency:str=Field(min_length=3,max_length=3); expected_delivery_at:datetime|None=None; external_reference:str|None=Field(default=None,max_length=200); notes:str|None=Field(default=None,max_length=1000); lines:tuple[LineIn,...]=Field(min_length=1)
class ActionIn(BaseModel): expected_version:int=Field(ge=1)
class AmendIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1); expected_delivery_at:datetime|None=None; external_reference:str|None=Field(default=None,max_length=200); notes:str|None=Field(default=None,max_length=1000); lines:tuple[LineIn,...]=Field(min_length=1)
def ctx(c): return ExecutionContext(ActorType.EMPLOYEE,c.tenant_id,c.membership_id,None,get_correlation_id())
def auth(c,l):
    if l not in c.authorized_location_ids: raise HTTPException(404,'Location not found')
def err(e):
    if isinstance(e,(purchase_orders.PurchaseOrderNotFound,errors.InventoryScopeNotFoundError)): return HTTPException(404,{'code':e.code,'message':str(e)})
    if isinstance(e,errors.InventoryError): return HTTPException(409,{'code':e.code,'message':str(e)})
    return e
@router.post('',status_code=201)
async def create(payload:CreateIn,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.purchase_order.manage'))],db:Annotated[AsyncSession,Depends(get_db)]) -> Any:
    auth(c,payload.location_id)
    try:
        d=payload.model_dump(); lines=tuple(d.pop('lines')); return await purchase_orders.create(db,ctx(c),lines=lines,cost_visible='inventory.cost.read' in c.permissions,**d)
    except Exception as e: raise err(e) from e
@router.get('')
async def listing(c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.purchase_order.read'))],db:Annotated[AsyncSession,Depends(get_db)],location_id:int=Query(gt=0)):
    auth(c,location_id); return {'items':await purchase_orders.list_orders(db,c.tenant_id,location_id,'inventory.cost.read' in c.permissions)}
@router.get('/{order_id}')
async def detail(order_id:int,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.purchase_order.read'))],db:Annotated[AsyncSession,Depends(get_db)]):
    try:
        auth(c,await purchase_orders.location(db,c.tenant_id,order_id)); return await purchase_orders.project(db,await purchase_orders._order(db,c.tenant_id,order_id),'inventory.cost.read' in c.permissions)
    except Exception as e: raise err(e) from e
@router.patch('/{order_id}')
async def amend(order_id:int,payload:AmendIn,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.purchase_order.manage'))],db:Annotated[AsyncSession,Depends(get_db)]):
    try:
        auth(c,await purchase_orders.location(db,c.tenant_id,order_id)); d=payload.model_dump(); lines=tuple(d.pop('lines')); return await purchase_orders.amend(db,ctx(c),order_id,lines=lines,cost_visible='inventory.cost.read' in c.permissions,**d)
    except Exception as e: raise err(e) from e
@router.post('/{order_id}:{action}')
async def action(order_id:int,action:str,payload:ActionIn,response:Response,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.purchase_order.manage'))],db:Annotated[AsyncSession,Depends(get_db)],key:Annotated[str,Header(alias='Idempotency-Key',min_length=1,max_length=128)]):
    if action not in ('submit','approve','cancel','close'): raise HTTPException(404,'Action not found')
    if action=='approve' and 'inventory.purchase_order.approve' not in c.permissions: raise HTTPException(status.HTTP_403_FORBIDDEN,'Insufficient permission')
    try:
        auth(c,await purchase_orders.location(db,c.tenant_id,order_id)); value,replay=await purchase_orders.command(db,ctx(c),order_id,action,payload.expected_version,key,'inventory.cost.read' in c.permissions)
        if replay: response.headers['Idempotent-Replay']='true'
        return value
    except Exception as e: raise err(e) from e
