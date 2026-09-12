from __future__ import annotations

from datetime import UTC, datetime
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
NegativeStockPolicy = Literal['ALLOW', 'WARN', 'BLOCK']
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
    uom: str = Field(min_length=1, max_length=32)


class ConsumptionDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    status: Lifecycle = 'ACTIVE'
    tracking_mode: TrackingMode
    components: tuple[ConsumptionComponentRequest, ...] = ()
    effective_from: datetime | None = None


class ConsumptionComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    inventory_item_id: int
    inventory_item_code: str
    inventory_item_name: str
    quantity: Decimal
    base_uom: str
    source_quantity: Decimal | None = None
    source_uom: str | None = None
    conversion_revision_id: int | None = None
    conversion_factor: Decimal | None = None


class ConsumptionDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    location_id: int
    version: int
    status: str
    tracking_mode: str
    components: tuple[ConsumptionComponentResponse, ...]
    recipe_version_id: int | None = None
    recipe_revision: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    published_at: datetime | None = None


class ConsumptionDefinitionVersionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ConsumptionDefinitionResponse]


class StockMovementRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    inventory_item_id: int = Field(gt=0)
    warehouse_id: int | None = Field(default=None, gt=0)
    movement_type: str = Field(min_length=1, max_length=24)
    quantity: ExactDecimal | None = None
    uom: str | None = Field(default=None, min_length=1, max_length=32)
    reversal_of_movement_id: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=200)


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inventory_item_id: int
    location_id: int
    warehouse_id: int
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
    negative_stock_policy: str
    negative_stock_warning: bool
    resulting_stock_quantity: Decimal | None
    source_quantity: Decimal | None
    source_uom: str | None
    conversion_revision_id: int | None
    conversion_factor: Decimal | None
    base_uom_evidence: str | None
    standard_cost_revision_id: int | None
    standard_unit_cost_evidence: Decimal | None
    cost_currency_evidence: str | None
    extended_standard_cost: Decimal | None
    evidence_status: str
    goods_receipt_id: int | None
    goods_receipt_line_id: int | None
    inventory_loss_id: int | None
    loss_movement_role: str | None
    physical_count_id: int | None
    physical_count_line_id: int | None


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
    warehouse_id: int
    base_uom: str
    quantity: Decimal


class StockListResponse(BaseModel):
    items: list[StockResponse]


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    code: str
    name: str
    status: str
    is_default: bool
    negative_stock_policy: str
    version: int
    created_at: datetime
    updated_at: datetime


class WarehouseListResponse(BaseModel):
    items: list[WarehouseResponse]


class WarehousePolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    negative_stock_policy: NegativeStockPolicy


class ItemUomConversionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    operational_uom: str = Field(min_length=1, max_length=32)
    factor_to_base: ExactDecimal = Field(gt=0)
    effective_at: datetime | None = None
    reference: str | None = Field(default=None, max_length=200)


class ItemUomConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inventory_item_id: int
    operational_uom: str
    base_uom: str
    factor_to_base: Decimal
    revision: int
    effective_at: datetime
    actor_id: int
    reference: str | None
    created_at: datetime


class ItemUomConversionListResponse(BaseModel):
    items: list[ItemUomConversionResponse]


class InventoryCostRevisionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_version: int = Field(ge=1)
    standard_unit_cost: ExactDecimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    effective_at: datetime | None = None
    reference: str | None = Field(default=None, max_length=200)


class InventoryCostRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inventory_item_id: int
    revision: int
    standard_unit_cost: Decimal
    currency: str
    effective_at: datetime
    source: str
    actor_id: int | None
    reference: str | None
    created_at: datetime


class InventoryCostRevisionListResponse(BaseModel):
    items: list[InventoryCostRevisionResponse]


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


def _authorize_location(context: AuthenticatedContext, location_id: int) -> None:
    if location_id not in context.authorized_location_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Location not found')


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (
        errors.InventoryScopeNotFoundError,
        errors.InventoryItemNotFoundError,
        errors.ItemUomConversionNotFoundError,
        errors.WarehouseNotFoundError,
        errors.ConsumptionDefinitionNotFoundError,
        errors.StockMovementNotFoundError,
    )):
        return HTTPException(
            status.HTTP_404_NOT_FOUND, {'code': exc.code, 'message': str(exc)}
        )
    if isinstance(exc, (
        errors.InvalidInventoryItemError,
        errors.InvalidItemUomConversionError,
        errors.InvalidInventoryCostRevisionError,
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
    _authorize_location(context, payload.location_id)
    try:
        return await service.create_inventory_item(
            db, tenant_id=context.tenant_id, actor_id=context.membership_id,
            **payload.model_dump(),
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
        _authorize_location(
            context,
            await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=inventory_item_id,
            ),
        )
        return await service.update_inventory_item(
            db, tenant_id=context.tenant_id,
            inventory_item_id=inventory_item_id, actor_id=context.membership_id,
            **values,
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
    _authorize_location(context, location_id)
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
    as_of: datetime | None = Query(default=None),
) -> Any:
    _authorize_location(context, location_id)
    try:
        return await service.get_consumption_definition(
            db, tenant_id=context.tenant_id, product_id=product_id,
            location_id=location_id, as_of=_utc_naive(as_of),
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
    _authorize_location(context, location_id)
    try:
        return await service.put_consumption_definition(
            db,
            tenant_id=context.tenant_id,
            product_id=product_id,
            location_id=location_id,
            expected_version=payload.expected_version,
            status=payload.status,
            tracking_mode=payload.tracking_mode,
            effective_from=_utc_naive(payload.effective_from),
            actor_id=context.membership_id,
            components=tuple(
                ConsumptionComponentInput(**component.model_dump())
                for component in payload.components
            ),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/products/{product_id}/consumption-definition/versions',
    response_model=ConsumptionDefinitionVersionListResponse,
)
async def list_consumption_definition_versions(
    product_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> ConsumptionDefinitionVersionListResponse:
    _authorize_location(context, location_id)
    try:
        values = await service.list_consumption_definition_versions(
            db, tenant_id=context.tenant_id, product_id=product_id,
            location_id=location_id,
        )
        return ConsumptionDefinitionVersionListResponse(items=list(values))
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
        _authorize_location(
            context,
            await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=payload.inventory_item_id,
            ),
        )
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
    warehouse_id: int | None = Query(default=None, gt=0),
) -> StockListResponse:
    _authorize_location(context, location_id)
    try:
        values = await service.list_stock(
            db, tenant_id=context.tenant_id, location_id=location_id,
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
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
    warehouse_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> StockMovementListResponse:
    _authorize_location(context, location_id)
    try:
        values = await service.list_stock_movements(
            db, tenant_id=context.tenant_id, location_id=location_id,
            inventory_item_id=inventory_item_id, warehouse_id=warehouse_id,
            limit=limit, offset=offset,
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
    _authorize_location(context, payload.location_id)
    try:
        return await service.resolve_current_product_cost(
            db, tenant_id=context.tenant_id, product_id=product_id,
            location_id=payload.location_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/inventory/warehouses', response_model=WarehouseListResponse)
async def list_warehouses(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> WarehouseListResponse:
    _authorize_location(context, location_id)
    try:
        values = await service.list_warehouses(
            db, tenant_id=context.tenant_id, location_id=location_id,
        )
        return WarehouseListResponse(items=list(values))
    except Exception as exc:
        raise _error(exc) from exc


@router.patch('/inventory/warehouses/{warehouse_id}', response_model=WarehouseResponse)
async def update_warehouse_policy(
    warehouse_id: Annotated[int, Path(gt=0)],
    payload: WarehousePolicyUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context,
            await service.warehouse_location(
                db, tenant_id=context.tenant_id, warehouse_id=warehouse_id,
            ),
        )
        return await service.update_warehouse_policy(
            db, tenant_id=context.tenant_id, warehouse_id=warehouse_id,
            expected_version=payload.expected_version,
            negative_stock_policy=payload.negative_stock_policy,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/inventory-items/{inventory_item_id}/uom-conversions',
    response_model=ItemUomConversionResponse, status_code=status.HTTP_201_CREATED,
)
async def create_item_uom_conversion(
    inventory_item_id: Annotated[int, Path(gt=0)],
    payload: ItemUomConversionCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context, await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=inventory_item_id,
            ),
        )
        return await service.append_item_uom_conversion(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
            operational_uom=payload.operational_uom,
            factor_to_base=payload.factor_to_base,
            effective_at=_utc_naive(payload.effective_at),
            actor_id=context.membership_id, reference=payload.reference,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/inventory-items/{inventory_item_id}/uom-conversions',
    response_model=ItemUomConversionListResponse,
)
async def get_item_uom_conversions(
    inventory_item_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ItemUomConversionListResponse:
    try:
        _authorize_location(
            context, await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=inventory_item_id,
            ),
        )
        values = await service.list_item_uom_conversions(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
        )
        return ItemUomConversionListResponse(items=list(values))
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/inventory-items/{inventory_item_id}/cost-revisions',
    response_model=InventoryCostRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_cost_revision(
    inventory_item_id: Annotated[int, Path(gt=0)],
    payload: InventoryCostRevisionCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context, await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=inventory_item_id,
            ),
        )
        return await service.create_cost_revision(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
            expected_version=payload.expected_version,
            standard_unit_cost=payload.standard_unit_cost, currency=payload.currency,
            effective_at=_utc_naive(payload.effective_at),
            actor_id=context.membership_id, reference=payload.reference,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/inventory-items/{inventory_item_id}/cost-revisions',
    response_model=InventoryCostRevisionListResponse,
)
async def get_inventory_cost_revisions(
    inventory_item_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryCostRevisionListResponse:
    try:
        _authorize_location(
            context, await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=inventory_item_id,
            ),
        )
        values = await service.list_cost_revisions(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
        )
        return InventoryCostRevisionListResponse(items=list(values))
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/inventory-items/{inventory_item_id}/standard-cost',
    response_model=InventoryCostRevisionResponse,
)
async def get_inventory_cost_as_of(
    inventory_item_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    as_of: datetime = Query(),
) -> Any:
    try:
        _authorize_location(
            context, await service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=inventory_item_id,
            ),
        )
        return await service.get_cost_as_of(
            db, tenant_id=context.tenant_id, inventory_item_id=inventory_item_id,
            as_of=_utc_naive(as_of) or datetime.now(UTC).replace(tzinfo=None),
        )
    except Exception as exc:
        raise _error(exc) from exc
