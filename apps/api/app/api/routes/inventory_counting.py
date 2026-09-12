from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.inventory import counting, errors, losses


router = APIRouter(prefix='/inventory', tags=['inventory-counting'])
ExactDecimal = Annotated[Decimal, BeforeValidator(
    lambda value: (_ for _ in ()).throw(ValueError('Exact decimal required'))
    if isinstance(value, float) else value
)]
IdempotencyKey = Annotated[str, Header(
    alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[\x21-\x7e]+$',
)]


class CountCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    warehouse_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=200)


class CountLinePutRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_count_version: int = Field(ge=1)
    expected_line_version: int = Field(ge=0)
    source_quantity: ExactDecimal = Field(ge=0)
    source_uom: str = Field(min_length=1, max_length=32)


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class CountLineResponse(BaseModel):
    id: int
    physical_count_id: int
    inventory_item_id: int
    expected_quantity_at_cursor: Decimal
    source_quantity: Decimal
    source_uom: str
    conversion_revision_id: int | None
    conversion_factor: Decimal
    base_uom_evidence: str
    normalized_counted_quantity: Decimal
    variance_quantity: Decimal
    standard_cost_revision_id: int | None
    standard_unit_cost_evidence: Decimal | None
    cost_currency_evidence: str | None
    variance_value: Decimal | None
    evidence_status: str
    cost_visible: bool
    version: int
    counted_by_actor_id: int
    counted_at: datetime
    adjustment_stock_movement_id: int | None


class CountResponse(BaseModel):
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    warehouse_id: int
    count_scope: Literal['PARTIAL']
    status: Literal['DRAFT', 'COUNTING', 'SUBMITTED', 'APPROVED', 'POSTED', 'CANCELLED']
    opened_at: datetime
    cursor_at: datetime
    cursor_movement_id: int
    opened_by_actor_id: int
    submitted_at: datetime | None
    submitted_by_actor_id: int | None
    approved_at: datetime | None
    approved_by_actor_id: int | None
    posted_at: datetime | None
    posted_by_actor_id: int | None
    cancelled_at: datetime | None
    cancelled_by_actor_id: int | None
    reason: str | None
    reference: str | None
    version: int
    lines: list[CountLineResponse]


class CountListResponse(BaseModel):
    items: list[CountResponse]


class ReconciliationCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    physical_count_line_id: int = Field(gt=0)
    period_start: datetime


class ReconciliationResponse(BaseModel):
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    warehouse_id: int
    inventory_item_id: int
    physical_count_id: int
    physical_count_line_id: int
    period_start: datetime
    period_end: datetime
    status: Literal['OPEN', 'CLOSED']
    opening_quantity: Decimal | None
    receiving_quantity: Decimal | None
    theoretical_consumption_quantity: Decimal | None
    dedicated_loss_quantity: Decimal | None
    other_adjustment_quantity: Decimal | None
    physical_count_quantity: Decimal | None
    count_adjustment_quantity: Decimal | None
    theoretical_closing_quantity: Decimal | None
    closing_quantity: Decimal | None
    variance_quantity: Decimal | None
    variance_percentage: Decimal | None
    standard_cost_revision_id: int | None
    standard_unit_cost_evidence: Decimal | None
    cost_currency_evidence: str | None
    variance_value: Decimal | None
    evidence_status: str | None
    cost_visible: bool
    created_by_actor_id: int
    closed_at: datetime | None
    closed_by_actor_id: int | None
    version: int
    created_at: datetime
    updated_at: datetime


class ReconciliationListResponse(BaseModel):
    items: list[ReconciliationResponse]


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.EMPLOYEE, context.tenant_id, context.membership_id, None,
        get_correlation_id(),
    )


def _authorize(context: AuthenticatedContext, location_id: int) -> None:
    if location_id not in context.authorized_location_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Location not found')


def _cost(context: AuthenticatedContext) -> bool:
    return 'inventory.cost.read' in context.permissions


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (
        errors.InventoryScopeNotFoundError, errors.InventoryItemNotFoundError,
        errors.WarehouseNotFoundError, errors.PhysicalCountNotFoundError,
        errors.InventoryReconciliationNotFoundError,
    )):
        return HTTPException(404, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, errors.InvalidPhysicalCountError):
        return HTTPException(422, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, errors.InventoryError):
        return HTTPException(409, {'code': exc.code, 'message': str(exc)})
    raise exc


async def _authorize_count(db: AsyncSession, context: AuthenticatedContext, count_id: int):
    _authorize(context, await counting.count_location(
        db, tenant_id=context.tenant_id, count_id=count_id,
    ))


@router.post('/physical-counts', response_model=CountResponse, status_code=201)
async def create_count(
    payload: CountCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize(context, await losses.policy_location(
            db, tenant_id=context.tenant_id, warehouse_id=payload.warehouse_id,
        ))
        return await counting.create_count(
            db, context=_execution(context), include_cost=_cost(context), **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.put('/physical-counts/{count_id}/lines/{inventory_item_id}', response_model=CountResponse)
async def put_count_line(
    count_id: Annotated[int, Path(gt=0)], inventory_item_id: Annotated[int, Path(gt=0)],
    payload: CountLinePutRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        await _authorize_count(db, context, count_id)
        return await counting.put_line(
            db, context=_execution(context), count_id=count_id,
            inventory_item_id=inventory_item_id, include_cost=_cost(context),
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/physical-counts', response_model=CountListResponse)
async def list_counts(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.read'))],
    db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0),
) -> Any:
    _authorize(context, location_id)
    return {'items': await counting.list_counts(
        db, tenant_id=context.tenant_id, location_id=location_id, include_cost=_cost(context),
    )}


@router.get('/physical-counts/{count_id}', response_model=CountResponse)
async def get_count(
    count_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        await _authorize_count(db, context, count_id)
        return await counting.get_count(
            db, tenant_id=context.tenant_id, count_id=count_id, include_cost=_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc


async def _transition(action: str, count_id: int, payload: ActionRequest,
                      context: AuthenticatedContext, db: AsyncSession) -> Any:
    await _authorize_count(db, context, count_id)
    return await counting.transition_count(
        db, context=_execution(context), count_id=count_id,
        expected_version=payload.expected_version, action=action, include_cost=_cost(context),
    )


@router.post('/physical-counts/{count_id}:submit', response_model=CountResponse)
async def submit_count(
    count_id: Annotated[int, Path(gt=0)], payload: ActionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        return await _transition('submit', count_id, payload, context, db)
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/physical-counts/{count_id}:approve', response_model=CountResponse)
async def approve_count(
    count_id: Annotated[int, Path(gt=0)], payload: ActionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.approve'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        return await _transition('approve', count_id, payload, context, db)
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/physical-counts/{count_id}:post', response_model=CountResponse)
async def post_count(
    count_id: Annotated[int, Path(gt=0)], payload: ActionRequest, response: Response,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.post'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> Any:
    try:
        await _authorize_count(db, context, count_id)
        value, replay = await counting.post_count(
            db, context=_execution(context), count_id=count_id,
            expected_version=payload.expected_version, idempotency_key=idempotency_key,
            include_cost=_cost(context),
        )
        if replay:
            response.headers['Idempotent-Replay'] = 'true'
        return value
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/physical-counts/{count_id}:cancel', response_model=CountResponse)
async def cancel_count(
    count_id: Annotated[int, Path(gt=0)], payload: ActionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.count.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        await _authorize_count(db, context, count_id)
        return await counting.cancel_count(
            db, context=_execution(context), count_id=count_id,
            expected_version=payload.expected_version, include_cost=_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/reconciliations', response_model=ReconciliationResponse, status_code=201)
async def create_reconciliation(
    payload: ReconciliationCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.reconciliation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize(context, await counting.count_line_location(
            db, tenant_id=context.tenant_id,
            physical_count_line_id=payload.physical_count_line_id,
        ))
        data = payload.model_dump()
        data['period_start'] = _naive(data['period_start'])
        value = await counting.create_reconciliation(
            db, context=_execution(context), include_cost=_cost(context), **data,
        )
        return value
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/reconciliations', response_model=ReconciliationListResponse)
async def list_reconciliations(
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.reconciliation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)], location_id: int = Query(gt=0),
) -> Any:
    _authorize(context, location_id)
    return {'items': await counting.list_reconciliations(
        db, tenant_id=context.tenant_id, location_id=location_id, include_cost=_cost(context),
    )}


@router.get('/reconciliations/{reconciliation_id}', response_model=ReconciliationResponse)
async def get_reconciliation(
    reconciliation_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.reconciliation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize(context, await counting.reconciliation_location(
            db, tenant_id=context.tenant_id, reconciliation_id=reconciliation_id,
        ))
        return await counting.get_reconciliation(
            db, tenant_id=context.tenant_id, reconciliation_id=reconciliation_id,
            include_cost=_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/reconciliations/{reconciliation_id}:close', response_model=ReconciliationResponse)
async def close_reconciliation(
    reconciliation_id: Annotated[int, Path(gt=0)], payload: ActionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('inventory.reconciliation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize(context, await counting.reconciliation_location(
            db, tenant_id=context.tenant_id, reconciliation_id=reconciliation_id,
        ))
        return await counting.close_reconciliation(
            db, context=_execution(context), reconciliation_id=reconciliation_id,
            expected_version=payload.expected_version, include_cost=_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc
