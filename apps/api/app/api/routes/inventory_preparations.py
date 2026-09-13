from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import errors, preparations

router = APIRouter(prefix='/inventory', tags=['inventory-preparations'])


def exact(value: Any) -> Any:
    if isinstance(value, float): raise ValueError('Binary floating-point values are not valid exact decimals')
    return value


ExactDecimal = Annotated[Decimal, BeforeValidator(exact)]


class RecipeComponentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    inventory_item_id: int = Field(gt=0)
    expected_quantity: ExactDecimal = Field(gt=0)
    source_uom: str = Field(min_length=1, max_length=32)
    yield_basis: bool = False


class RecipeIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    location_id: int = Field(gt=0)
    output_inventory_item_id: int = Field(gt=0)
    expected_output_quantity: ExactDecimal = Field(gt=0)
    output_uom: str = Field(min_length=1, max_length=32)
    status: str = 'ACTIVE'
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    expected_revision: int = Field(ge=0)
    components: tuple[RecipeComponentIn, ...] = Field(min_length=1)


class BatchInputIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recipe_component_id: int = Field(gt=0)
    source_quantity: ExactDecimal = Field(gt=0)
    source_uom: str = Field(min_length=1, max_length=32)


class BatchIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recipe_version_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    reference: str | None = Field(default=None, max_length=200)
    inputs: tuple[BatchInputIn, ...] = Field(min_length=1)
    output_quantity: ExactDecimal = Field(gt=0)
    output_uom: str = Field(min_length=1, max_length=32)


class ActionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


def ctx(value: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(ActorType.EMPLOYEE, value.tenant_id, value.membership_id, None, get_correlation_id())


def authorize(value: AuthenticatedContext, location_id: int) -> None:
    if location_id not in value.authorized_location_ids: raise HTTPException(404, 'Location not found')


def mapped(exc: Exception) -> Exception:
    if isinstance(exc, (preparations.PreparationNotFound, errors.InventoryScopeNotFoundError)): return HTTPException(404, {'code': getattr(exc, 'code', 'NOT_FOUND'), 'message': str(exc)})
    if isinstance(exc, errors.InventoryError): return HTTPException(409, {'code': exc.code, 'message': str(exc)})
    return exc


@router.post('/preparation-recipes', status_code=201)
async def publish(payload: RecipeIn, context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.preparation.manage'))], db: Annotated[AsyncSession, Depends(get_db)]) -> Any:
    authorize(context, payload.location_id)
    try:
        data=payload.model_dump(); components=tuple(data.pop('components'))
        return await preparations.publish_recipe(db, context=ctx(context), components=components, **data)
    except Exception as exc: raise mapped(exc) from exc


@router.get('/preparation-recipes')
async def recipes(context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.preparation.read'))], db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0)) -> Any:
    authorize(context, location_id)
    return {'items': await preparations.list_recipes(db, context.tenant_id, location_id)}


@router.post('/preparation-batches', status_code=201)
async def create(payload: BatchIn, context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.preparation.manage'))], db: Annotated[AsyncSession, Depends(get_db)]) -> Any:
    try:
        authorize(context, await preparations.location_for_recipe(db, context.tenant_id, payload.recipe_version_id))
        data=payload.model_dump(); inputs=tuple(data.pop('inputs'))
        return await preparations.create_batch(db, context=ctx(context), inputs=inputs, cost_visible='inventory.cost.read' in context.permissions, **data)
    except Exception as exc: raise mapped(exc) from exc


@router.get('/preparation-batches')
async def batches(context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.preparation.read'))], db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0)) -> Any:
    authorize(context, location_id)
    return {'items': await preparations.list_batches(db, context.tenant_id, location_id, 'inventory.cost.read' in context.permissions)}


@router.post('/preparation-batches/{batch_id}:{action}')
async def action(batch_id: int, action: str, payload: ActionIn, response: Response, context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.preparation.manage'))], db: Annotated[AsyncSession, Depends(get_db)], key: Annotated[str | None, Header(alias='Idempotency-Key', max_length=128)] = None) -> Any:
    if action not in ('start','complete','cancel'): raise HTTPException(404, 'Action not found')
    if action == 'complete' and 'inventory.preparation.complete' not in context.permissions: raise HTTPException(status.HTTP_403_FORBIDDEN, 'Insufficient permission')
    try:
        authorize(context, await preparations.location_for_batch(db, context.tenant_id, batch_id))
        value,replay=await preparations.transition(db,context=ctx(context),batch_id=batch_id,action=action,expected_version=payload.expected_version,key=key,cost_visible='inventory.cost.read' in context.permissions)
        if replay: response.headers['Idempotent-Replay']='true'
        return value
    except Exception as exc: raise mapped(exc) from exc
