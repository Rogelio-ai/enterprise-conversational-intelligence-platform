from decimal import Decimal
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import fifo_transfers as service
from app.restaurant.inventory import service as inventory_service

router=APIRouter(prefix='/inventory',tags=['inventory-fifo-transfers'])
def exact(v:Any)->Any:
    if isinstance(v,float): raise ValueError('Binary floating point is not exact')
    return v
Exact=Annotated[Decimal,BeforeValidator(exact)]
class LineIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    inventory_item_id:int=Field(gt=0); quantity:Exact=Field(gt=0)
class CreateIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_warehouse_id:int=Field(gt=0);destination_warehouse_id:int=Field(gt=0);reference:str|None=Field(default=None,max_length=200);lines:list[LineIn]=Field(min_length=1)
class ReceiptIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    line_id:int=Field(gt=0);quantity:Exact=Field(gt=0)
class ActionIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1);receipts:list[ReceiptIn]|None=None
def ctx(c:AuthenticatedContext)->ExecutionContext:return ExecutionContext(ActorType.EMPLOYEE,c.tenant_id,c.membership_id,None,get_correlation_id())
def authorize(c:AuthenticatedContext,location_id:int)->None:
    if location_id not in c.authorized_location_ids:raise HTTPException(404,'Location not found')
def mapped(exc:Exception)->Exception:
    if isinstance(exc,service.B11NotFound):return HTTPException(404,{'code':exc.code,'message':str(exc)})
    if isinstance(exc,service.B11Error):return HTTPException(409,{'code':exc.code,'message':str(exc)})
    return exc
@router.get('/fifo-layers')
async def layers(c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.fifo.read'))],db:Annotated[AsyncSession,Depends(get_db)],location_id:int=Query(gt=0)):
    authorize(c,location_id);return {'items':await service.list_layers(db,c.tenant_id,location_id,'inventory.cost.read' in c.permissions)}
@router.post('/transfers',status_code=201)
async def create(p:CreateIn,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.transfer.manage'))],db:Annotated[AsyncSession,Depends(get_db)]):
    try:
        a=await inventory_service.warehouse_location(db,tenant_id=c.tenant_id,warehouse_id=p.source_warehouse_id);b=await inventory_service.warehouse_location(db,tenant_id=c.tenant_id,warehouse_id=p.destination_warehouse_id);authorize(c,a);authorize(c,b)
        return await service.create_transfer(db,context=ctx(c),cost_visible='inventory.cost.read' in c.permissions,**p.model_dump())
    except Exception as exc:raise mapped(exc) from exc
@router.get('/transfers')
async def listing(c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.transfer.read'))],db:Annotated[AsyncSession,Depends(get_db)],location_id:int=Query(gt=0)):
    authorize(c,location_id);return {'items':await service.list_transfers(db,c.tenant_id,location_id,'inventory.cost.read' in c.permissions)}
@router.get('/transfers/{transfer_id}')
async def detail(transfer_id:int,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.transfer.read'))],db:Annotated[AsyncSession,Depends(get_db)]):
    try:
        authorize(c,await service.transfer_location(db,c.tenant_id,transfer_id));x=await service._transfer(db,c.tenant_id,transfer_id);return await service.project_transfer(db,x,'inventory.cost.read' in c.permissions)
    except Exception as exc:raise mapped(exc) from exc
@router.post('/transfers/{transfer_id}:{action}')
async def action(transfer_id:int,action:Literal['submit','ship','receive','cancel'],p:ActionIn,response:Response,c:Annotated[AuthenticatedContext,Depends(require_permission('inventory.transfer.manage'))],db:Annotated[AsyncSession,Depends(get_db)],key:Annotated[str,Header(alias='Idempotency-Key',min_length=1,max_length=80)]):
    try:
        authorize(c,await service.transfer_location(db,c.tenant_id,transfer_id));value,replay=await service.command(db,context=ctx(c),transfer_id=transfer_id,action=action,expected_version=p.expected_version,key=key,receipts=[x.model_dump() for x in p.receipts] if p.receipts else None,cost_visible='inventory.cost.read' in c.permissions)
        if replay:response.headers['Idempotent-Replay']='true'
        return value
    except Exception as exc:raise mapped(exc) from exc
