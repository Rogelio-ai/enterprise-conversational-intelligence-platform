from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import replenishment_lots_valuation as b10


router = APIRouter(prefix='/inventory', tags=['inventory-replenishment-lots-valuation'])


def _exact(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact decimals')
    return value


ExactDecimal = Annotated[Decimal, BeforeValidator(_exact)]


class PolicyIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'
    minimum_quantity: ExactDecimal | None = Field(default=None, ge=0)
    target_quantity: ExactDecimal | None = Field(default=None, ge=0)
    source_uom: str = Field(min_length=1, max_length=32)


class SnapshotIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    warehouse_id: int = Field(gt=0)
    as_of: datetime
    currency: str = Field(min_length=3, max_length=3)
    valuation_method: Literal['STANDARD_COST'] = 'STANDARD_COST'


def _ctx(value: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(ActorType.EMPLOYEE, value.tenant_id, value.membership_id, None, get_correlation_id())


def _authorize(value: AuthenticatedContext, location_id: int) -> None:
    if location_id not in value.authorized_location_ids:
        raise HTTPException(404, 'Location not found')


def _mapped(exc: Exception) -> Exception:
    if isinstance(exc, b10.B10NotFound):
        return HTTPException(404, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, b10.B10Error):
        return HTTPException(409, {'code': exc.code, 'message': str(exc)})
    return exc


@router.put('/replenishment-policies/{warehouse_id}/{inventory_item_id}')
async def put_policy(
    warehouse_id: int, inventory_item_id: int, payload: PolicyIn,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.replenishment.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        location_id = await b10.service.warehouse_location(db, tenant_id=context.tenant_id, warehouse_id=warehouse_id)
        _authorize(context, location_id)
        return await b10.put_policy(db, context=_ctx(context), warehouse_id=warehouse_id, inventory_item_id=inventory_item_id, **payload.model_dump())
    except Exception as exc:
        raise _mapped(exc) from exc


@router.get('/replenishment-policies')
async def policies(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.replenishment.read'))],
    db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0),
) -> Any:
    _authorize(context, location_id)
    return {'items': await b10.list_policies(db, context.tenant_id, location_id)}


@router.get('/lots')
async def lots(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.lot.read'))],
    db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0),
) -> Any:
    _authorize(context, location_id)
    return {'items': await b10.list_lots(db, context.tenant_id, location_id, 'inventory.cost.read' in context.permissions)}


@router.post('/valuation-snapshots', status_code=201)
async def create_snapshot(
    payload: SnapshotIn, response: Response,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.valuation.create'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128)],
) -> Any:
    try:
        location_id = await b10.service.warehouse_location(db, tenant_id=context.tenant_id, warehouse_id=payload.warehouse_id)
        _authorize(context, location_id)
        data = payload.model_dump(); data.pop('valuation_method')
        value, replay = await b10.create_snapshot(db, context=_ctx(context), idempotency_key=idempotency_key, cost_visible='inventory.cost.read' in context.permissions, **data)
        if replay:
            response.headers['Idempotent-Replay'] = 'true'
        return value
    except Exception as exc:
        raise _mapped(exc) from exc


@router.get('/valuation-snapshots')
async def snapshots(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.valuation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0),
) -> Any:
    _authorize(context, location_id)
    return {'items': await b10.list_snapshots(db, context.tenant_id, location_id, 'inventory.cost.read' in context.permissions)}
