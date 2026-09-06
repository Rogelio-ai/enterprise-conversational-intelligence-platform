from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import errors, service
from app.restaurant.inventory.contracts import ConsumptionComponentInput


router = APIRouter(tags=['inventory'])
Lifecycle = Literal['ACTIVE', 'INACTIVE']
TrackingMode = Literal['DERIVABLE', 'NON_DERIVABLE']
UnitCode = Literal['KG', 'G', 'L', 'ML', 'UNIT', 'PORTION']
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key', min_length=1, max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


def _exact(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact decimals')
    return value


ExactDecimal = Annotated[Decimal, BeforeValidator(_exact)]


class InventoryItemCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    location_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    base_uom: UnitCode
    standard_unit_cost: ExactDecimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)


class InventoryItemUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    standard_unit_cost: ExactDecimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def require_change(self) -> 'InventoryItemUpdateRequest':
        if not (self.model_fields_set - {'expected_version'}):
            raise ValueError('At least one mutable field is required')
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set - {'expected_version'}
        ):
            raise ValueError('Inventory Item fields cannot be null')
        return self


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    code: str
    name: str
    base_uom: str
    standard_unit_cost: Decimal
    currency: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemResponse]
    limit: int
    offset: int


class ConsumptionComponentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    inventory_item_id: int = Field(gt=0)
    quantity: ExactDecimal = Field(gt=0)
    uom: UnitCode


class ConsumptionDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    status: Lifecycle = 'ACTIVE'
    tracking_mode: TrackingMode
    components: tuple[ConsumptionComponentRequest, ...] = ()


class ConsumptionComponentResponse(BaseModel):
    inventory_item_id: int
    inventory_item_code: str
    inventory_item_name: str
    quantity: Decimal
    base_uom: str


class ConsumptionDefinitionResponse(BaseModel):
    id: int
    product_id: int
    location_id: int
    version: int
    status: str
    tracking_mode: str
    components: tuple[ConsumptionComponentResponse, ...]


class StockMovementRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    inventory_item_id: int = Field(gt=0)
    movement_type: str = Field(min_length=1, max_length=24)
    quantity: ExactDecimal | None = None
    reversal_of_movement_id: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=200)


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inventory_item_id: int
    location_id: int
    movement_type: str
    quantity: Decimal
    base_uom: str
    reversal_of_movement_id: int | None
    reason: str | None
    reference: str | None
    recorded_at: datetime
    actor_type: str
    actor_id: int | None
    actor_reference: str | None


class StockMovementListResponse(BaseModel):
    items: list[StockMovementResponse]
    limit: int
    offset: int


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    inventory_item_id: int
    code: str
    name: str
    location_id: int
    base_uom: str
    quantity: Decimal


class StockListResponse(BaseModel):
    items: list[StockResponse]


class ProductCostResolveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    location_id: int = Field(gt=0)


class CostComponentResponse(BaseModel):
    inventory_item_id: int
    inventory_item_code: str
    inventory_item_name: str
    quantity: Decimal
    base_uom: str
    standard_unit_cost: Decimal
    currency: str
    theoretical_cost: Decimal


class ProductCostResponse(BaseModel):
    product_id: int
    location_id: int
    definition_version: int
    tracking_mode: str
    cost_status: str
    currency: str | None
    components: tuple[CostComponentResponse, ...]
    total_theoretical_cost: Decimal | None


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.EMPLOYEE,
        context.tenant_id,
        context.membership_id,
        None,
        get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (
        errors.InventoryScopeNotFoundError,
        errors.InventoryItemNotFoundError,
        errors.ConsumptionDefinitionNotFoundError,
        errors.StockMovementNotFoundError,
    )):
        return HTTPException(
            status.HTTP_404_NOT_FOUND, {'code': exc.code, 'message': str(exc)}
        )
    if isinstance(exc, (
        errors.InvalidInventoryItemError,
        errors.InvalidConsumptionDefinitionError,
        errors.InvalidStockMovementError,
    )):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, errors.InventoryError):
        return HTTPException(
            status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)}
        )
    raise exc


@router.post('/inventory-items', response_model=InventoryItemResponse, status_code=201)
async def create_inventory_item(
    payload: InventoryItemCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        return await service.create_inventory_item(
            db, tenant_id=context.tenant_id, **payload.model_dump()
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.patch('/inventory-items/{inventory_item_id}', response_model=InventoryItemResponse)
async def update_inventory_item(
    inventory_item_id: Annotated[int, Path(gt=0)],
    payload: InventoryItemUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    values = payload.model_dump(exclude_unset=True)
    try:
        return await service.update_inventory_item(
            db, tenant_id=context.tenant_id,
            inventory_item_id=inventory_item_id, **values,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/inventory-items', response_model=InventoryItemListResponse)
async def list_inventory_items(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    status_filter: Lifecycle | None = Query(default=None, alias='status'),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> InventoryItemListResponse:
    try:
        values = await service.list_inventory_items(
            db, tenant_id=context.tenant_id, location_id=location_id,
            status=status_filter, limit=limit, offset=offset,
        )
        return InventoryItemListResponse(items=list(values), limit=limit, offset=offset)
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/products/{product_id}/consumption-definition',
    response_model=ConsumptionDefinitionResponse,
)
async def get_consumption_definition(
    product_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> Any:
    try:
        return await service.get_consumption_definition(
            db, tenant_id=context.tenant_id, product_id=product_id,
            location_id=location_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.put(
    '/products/{product_id}/consumption-definition',
    response_model=ConsumptionDefinitionResponse,
)
async def put_consumption_definition(
    product_id: Annotated[int, Path(gt=0)],
    payload: ConsumptionDefinitionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> Any:
    try:
        return await service.put_consumption_definition(
            db,
            tenant_id=context.tenant_id,
            product_id=product_id,
            location_id=location_id,
            expected_version=payload.expected_version,
            status=payload.status,
            tracking_mode=payload.tracking_mode,
            components=tuple(
                ConsumptionComponentInput(**component.model_dump())
                for component in payload.components
            ),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/inventory/stock-movements', response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_movement(
    payload: StockMovementRequest,
    response: Response,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> Any:
    try:
        value, replayed = await service.create_stock_movement(
            db, context=_execution(context), idempotency_key=idempotency_key,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.get('/inventory/stock', response_model=StockListResponse)
async def list_stock(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    inventory_item_id: int | None = Query(default=None, gt=0),
) -> StockListResponse:
    try:
        values = await service.list_stock(
            db, tenant_id=context.tenant_id, location_id=location_id,
            inventory_item_id=inventory_item_id,
        )
        return StockListResponse(items=list(values))
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/inventory/stock-movements', response_model=StockMovementListResponse)
async def list_stock_movements(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    inventory_item_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> StockMovementListResponse:
    try:
        values = await service.list_stock_movements(
            db, tenant_id=context.tenant_id, location_id=location_id,
            inventory_item_id=inventory_item_id, limit=limit, offset=offset,
        )
        return StockMovementListResponse(items=list(values), limit=limit, offset=offset)
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/products/{product_id}/theoretical-cost:resolve',
    response_model=ProductCostResponse,
)
async def resolve_current_product_cost(
    product_id: Annotated[int, Path(gt=0)],
    payload: ProductCostResolveRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        return await service.resolve_current_product_cost(
            db, tenant_id=context.tenant_id, product_id=product_id,
            location_id=payload.location_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
