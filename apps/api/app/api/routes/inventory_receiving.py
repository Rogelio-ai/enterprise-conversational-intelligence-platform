from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import errors
from app.restaurant.inventory import receiving


router = APIRouter(prefix='/inventory', tags=['inventory-receiving'])
Lifecycle = Literal['ACTIVE', 'INACTIVE']
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


class SupplierCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    organization_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    contact_reference: str | None = Field(default=None, max_length=200)
    location_ids: tuple[int, ...] = Field(min_length=1)


class SupplierUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Lifecycle | None = None
    contact_reference: str | None = Field(default=None, max_length=200)
    location_ids: tuple[int, ...] | None = None

    @model_validator(mode='after')
    def require_change(self) -> 'SupplierUpdateRequest':
        if not (self.model_fields_set - {'expected_version'}):
            raise ValueError('At least one mutable field is required')
        return self


class SupplierResponse(BaseModel):
    id: int
    tenant_id: int
    organization_id: int
    code: str
    name: str
    status: str
    contact_reference: str | None
    version: int
    location_ids: tuple[int, ...]
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]


class OfferingCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    location_id: int = Field(gt=0)
    inventory_item_id: int = Field(gt=0)
    supplier_item_code: str | None = Field(default=None, max_length=100)
    purchase_uom: str = Field(min_length=1, max_length=32)


class OfferingUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_version: int = Field(ge=1)
    status: Lifecycle | None = None
    supplier_item_code: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def require_change(self) -> 'OfferingUpdateRequest':
        if not (self.model_fields_set - {'expected_version'}):
            raise ValueError('At least one mutable field is required')
        return self


class OfferingResponse(BaseModel):
    id: int
    supplier_id: int
    location_id: int
    inventory_item_id: int
    supplier_item_code: str | None
    purchase_uom: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class OfferingListResponse(BaseModel):
    items: list[OfferingResponse]


class ReceiptLineCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    supplier_offering_id: int = Field(gt=0)
    received_quantity: ExactDecimal = Field(gt=0)
    accepted_quantity: ExactDecimal = Field(ge=0)
    rejected_quantity: ExactDecimal = Field(ge=0)
    unit_cost: ExactDecimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    purchase_order_line_id: int | None = Field(default=None, gt=0)
    lot_code: str | None = Field(default=None, min_length=1, max_length=100)
    manufacture_date: date | None = None
    expiry_date: date | None = None
    best_before_date: date | None = None

    @model_validator(mode='after')
    def quantities_balance(self) -> 'ReceiptLineCreateRequest':
        if self.accepted_quantity + self.rejected_quantity != self.received_quantity:
            raise ValueError('accepted_quantity + rejected_quantity must equal received_quantity')
        return self


class ReceiptCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    supplier_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    external_reference: str | None = Field(default=None, max_length=200)
    purchase_order_id: int | None = Field(default=None, gt=0)
    lines: tuple[ReceiptLineCreateRequest, ...] = Field(min_length=1)


class ReceiptActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class ReceiptLineResponse(BaseModel):
    id: int
    line_number: int
    supplier_offering_id: int
    inventory_item_id: int
    received_quantity: Decimal
    accepted_quantity: Decimal
    rejected_quantity: Decimal
    source_uom: str
    unit_cost: Decimal
    currency: str
    conversion_revision_id: int | None
    conversion_factor: Decimal | None
    base_uom_evidence: str | None
    normalized_quantity: Decimal | None
    extended_cost: Decimal | None
    evidence_status: str
    stock_movement_id: int | None
    purchase_order_line_id: int | None
    lot_code: str | None
    manufacture_date: date | None
    expiry_date: date | None
    best_before_date: date | None


class ReceiptResponse(BaseModel):
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    warehouse_id: int
    supplier_id: int
    purchase_order_id: int | None
    external_reference: str | None
    status: str
    version: int
    created_by_actor_id: int
    accepted_at: datetime | None
    accepted_by_actor_id: int | None
    cancelled_at: datetime | None
    cancelled_by_actor_id: int | None
    lines: tuple[ReceiptLineResponse, ...]
    created_at: datetime
    updated_at: datetime


class ReceiptListResponse(BaseModel):
    items: list[ReceiptResponse]


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.EMPLOYEE, context.tenant_id, context.membership_id, None,
        get_correlation_id(),
    )


def _authorize_location(context: AuthenticatedContext, location_id: int) -> None:
    if location_id not in context.authorized_location_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Location not found')


async def _receipt_read_context(
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.read'))
    ],
) -> AuthenticatedContext:
    if 'inventory.cost.read' not in context.permissions:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Insufficient permission')
    return context


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (
        errors.InventoryScopeNotFoundError, errors.InventoryItemNotFoundError,
        errors.WarehouseNotFoundError, errors.SupplierNotFoundError,
        errors.SupplierOfferingNotFoundError, errors.GoodsReceiptNotFoundError,
    )):
        return HTTPException(
            status.HTTP_404_NOT_FOUND, {'code': exc.code, 'message': str(exc)}
        )
    if isinstance(exc, (
        errors.InvalidSupplierError, errors.InvalidSupplierOfferingError,
        errors.InvalidGoodsReceiptError,
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


@router.post('/suppliers', response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.supplier.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    for location_id in payload.location_ids:
        _authorize_location(context, location_id)
    try:
        return await receiving.create_supplier(
            db, tenant_id=context.tenant_id, **payload.model_dump()
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/suppliers', response_model=SupplierListResponse)
async def list_suppliers(
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> SupplierListResponse:
    _authorize_location(context, location_id)
    values = await receiving.list_suppliers(
        db, tenant_id=context.tenant_id, location_id=location_id,
    )
    return SupplierListResponse(items=list(values))


@router.get('/suppliers/{supplier_id}', response_model=SupplierResponse)
async def get_supplier(
    supplier_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> Any:
    _authorize_location(context, location_id)
    try:
        return await receiving.get_supplier(
            db, tenant_id=context.tenant_id, supplier_id=supplier_id,
            location_id=location_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.patch('/suppliers/{supplier_id}', response_model=SupplierResponse)
async def update_supplier(
    supplier_id: Annotated[int, Path(gt=0)], payload: SupplierUpdateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.supplier.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        current_locations = await receiving.supplier_locations(
            db, tenant_id=context.tenant_id, supplier_id=supplier_id,
        )
        for location_id in current_locations:
            _authorize_location(context, location_id)
        if payload.location_ids is not None:
            for location_id in payload.location_ids:
                _authorize_location(context, location_id)
        return await receiving.update_supplier(
            db, tenant_id=context.tenant_id, supplier_id=supplier_id,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/suppliers/{supplier_id}/offerings', response_model=OfferingResponse,
    status_code=201,
)
async def create_offering(
    supplier_id: Annotated[int, Path(gt=0)], payload: OfferingCreateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.supplier.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    _authorize_location(context, payload.location_id)
    try:
        return await receiving.create_offering(
            db, tenant_id=context.tenant_id, supplier_id=supplier_id,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/suppliers/{supplier_id}/offerings', response_model=OfferingListResponse)
async def list_offerings(
    supplier_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> OfferingListResponse:
    _authorize_location(context, location_id)
    try:
        values = await receiving.list_offerings(
            db, tenant_id=context.tenant_id, supplier_id=supplier_id,
            location_id=location_id,
        )
        return OfferingListResponse(items=list(values))
    except Exception as exc:
        raise _error(exc) from exc


@router.patch('/supplier-offerings/{offering_id}', response_model=OfferingResponse)
async def update_offering(
    offering_id: Annotated[int, Path(gt=0)], payload: OfferingUpdateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.supplier.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context, await receiving.offering_location(
                db, tenant_id=context.tenant_id, offering_id=offering_id,
            ),
        )
        return await receiving.update_offering(
            db, tenant_id=context.tenant_id, offering_id=offering_id,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/goods-receipts', response_model=ReceiptResponse, status_code=201)
async def create_receipt(
    payload: ReceiptCreateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.receipt.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    _authorize_location(context, payload.location_id)
    try:
        data = payload.model_dump()
        lines = tuple(data.pop('lines'))
        return await receiving.create_receipt(
            db, context=_execution(context), lines=lines, **data,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/goods-receipts', response_model=ReceiptListResponse)
async def list_receipts(
    context: Annotated[AuthenticatedContext, Depends(_receipt_read_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> ReceiptListResponse:
    _authorize_location(context, location_id)
    values = await receiving.list_receipts(
        db, tenant_id=context.tenant_id, location_id=location_id,
    )
    return ReceiptListResponse(items=list(values))


@router.get('/goods-receipts/{receipt_id}', response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(_receipt_read_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context, await receiving.receipt_location(
                db, tenant_id=context.tenant_id, receipt_id=receipt_id,
            ),
        )
        return await receiving.get_receipt(
            db, tenant_id=context.tenant_id, receipt_id=receipt_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/goods-receipts/{receipt_id}:accept', response_model=ReceiptResponse)
async def accept_receipt(
    receipt_id: Annotated[int, Path(gt=0)], payload: ReceiptActionRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.receipt.accept'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> Any:
    try:
        _authorize_location(
            context, await receiving.receipt_location(
                db, tenant_id=context.tenant_id, receipt_id=receipt_id,
            ),
        )
        value, replayed = await receiving.accept_receipt(
            db, context=_execution(context), receipt_id=receipt_id,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
        )
        if replayed:
            response.headers['Idempotent-Replay'] = 'true'
        return value
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/goods-receipts/{receipt_id}:cancel', response_model=ReceiptResponse)
async def cancel_receipt(
    receipt_id: Annotated[int, Path(gt=0)], payload: ReceiptActionRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.receipt.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context, await receiving.receipt_location(
                db, tenant_id=context.tenant_id, receipt_id=receipt_id,
            ),
        )
        return await receiving.cancel_receipt(
            db, context=_execution(context), receipt_id=receipt_id,
            expected_version=payload.expected_version,
        )
    except Exception as exc:
        raise _error(exc) from exc
