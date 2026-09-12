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
from app.restaurant.inventory import errors, losses
from app.restaurant.inventory import service as inventory_service


router = APIRouter(prefix='/inventory', tags=['inventory-losses'])
LossCategory = Literal[
    'WASTE', 'SPOILAGE', 'BREAKAGE', 'EXPIRY', 'PREPARATION_LOSS', 'OTHER',
]
LossStatus = Literal['DRAFT', 'PENDING_APPROVAL', 'POSTED', 'CANCELLED', 'REVERSED']
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


class LossPolicyPutRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_version: int = Field(ge=0)
    approval_value_threshold: ExactDecimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    status: Lifecycle = 'ACTIVE'


class LossPolicyResponse(BaseModel):
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    warehouse_id: int
    approval_value_threshold: Decimal
    currency: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class LossCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    warehouse_id: int = Field(gt=0)
    inventory_item_id: int = Field(gt=0)
    category: LossCategory
    source_quantity: ExactDecimal = Field(gt=0)
    source_uom: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None

    @model_validator(mode='after')
    def other_requires_reason(self) -> 'LossCreateRequest':
        if self.category == 'OTHER' and not self.reason:
            raise ValueError('OTHER loss requires a reason')
        return self


class LossUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    expected_version: int = Field(ge=1)
    category: LossCategory | None = None
    source_quantity: ExactDecimal | None = Field(default=None, gt=0)
    source_uom: str | None = Field(default=None, min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None

    @model_validator(mode='after')
    def require_change(self) -> 'LossUpdateRequest':
        if not (self.model_fields_set - {'expected_version'}):
            raise ValueError('At least one mutable field is required')
        return self


class LossActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class LossReverseRequest(LossActionRequest):
    reason: str = Field(min_length=1, max_length=500)


class LossResponse(BaseModel):
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    warehouse_id: int
    inventory_item_id: int
    category: str
    source_quantity: Decimal
    source_uom: str
    conversion_revision_id: int | None
    conversion_factor: Decimal | None
    base_uom_evidence: str | None
    normalized_quantity: Decimal | None
    standard_cost_revision_id: int | None
    standard_unit_cost_evidence: Decimal | None
    cost_currency_evidence: str | None
    extended_loss_cost: Decimal | None
    evidence_status: str
    cost_visible: bool
    reason: str | None
    occurred_at: datetime
    created_by_actor_id: int
    status: LossStatus
    version: int
    approval_required: bool
    approval_reason: str | None
    approval_requested_at: datetime | None
    approval_requested_by_actor_id: int | None
    approved_at: datetime | None
    approved_by_actor_id: int | None
    posted_at: datetime | None
    posted_by_actor_id: int | None
    cancelled_at: datetime | None
    cancelled_by_actor_id: int | None
    reversed_at: datetime | None
    reversed_by_actor_id: int | None
    stock_movement_id: int | None
    reversal_stock_movement_id: int | None
    created_at: datetime
    updated_at: datetime


class LossListResponse(BaseModel):
    items: list[LossResponse]


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.EMPLOYEE, context.tenant_id, context.membership_id, None,
        get_correlation_id(),
    )


def _authorize_location(context: AuthenticatedContext, location_id: int) -> None:
    if location_id not in context.authorized_location_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Location not found')


def _include_cost(context: AuthenticatedContext) -> bool:
    return 'inventory.cost.read' in context.permissions


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (
        errors.InventoryScopeNotFoundError, errors.InventoryItemNotFoundError,
        errors.WarehouseNotFoundError, errors.InventoryLossNotFoundError,
        errors.InventoryLossPolicyNotFoundError,
    )):
        return HTTPException(
            status.HTTP_404_NOT_FOUND, {'code': exc.code, 'message': str(exc)}
        )
    if isinstance(exc, errors.InvalidInventoryLossError):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, errors.InventoryError):
        return HTTPException(
            status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)}
        )
    raise exc


async def _authorized_loss(
    db: AsyncSession, context: AuthenticatedContext, loss_id: int,
) -> None:
    _authorize_location(
        context,
        await losses.loss_location(db, tenant_id=context.tenant_id, loss_id=loss_id),
    )


@router.put('/loss-policies/{warehouse_id}', response_model=LossPolicyResponse)
async def put_loss_policy(
    warehouse_id: Annotated[int, Path(gt=0)], payload: LossPolicyPutRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.approve'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    if not _include_cost(context):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Insufficient cost permission')
    try:
        _authorize_location(
            context, await losses.policy_location(
                db, tenant_id=context.tenant_id, warehouse_id=warehouse_id,
            ),
        )
        return await losses.put_policy(
            db, tenant_id=context.tenant_id, warehouse_id=warehouse_id,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/loss-policies/{warehouse_id}', response_model=LossPolicyResponse)
async def get_loss_policy(
    warehouse_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.approve'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    if not _include_cost(context):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Insufficient cost permission')
    try:
        _authorize_location(
            context, await losses.policy_location(
                db, tenant_id=context.tenant_id, warehouse_id=warehouse_id,
            ),
        )
        return await losses.get_policy(
            db, tenant_id=context.tenant_id, warehouse_id=warehouse_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/losses', response_model=LossResponse, status_code=201)
async def create_loss(
    payload: LossCreateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        _authorize_location(
            context, await inventory_service.inventory_item_location(
                db, tenant_id=context.tenant_id,
                inventory_item_id=payload.inventory_item_id,
            ),
        )
        data = payload.model_dump()
        data['occurred_at'] = _utc_naive(data['occurred_at'])
        return await losses.create_loss(
            db, context=_execution(context), include_cost=_include_cost(context), **data,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.patch('/losses/{loss_id}', response_model=LossResponse)
async def update_loss(
    loss_id: Annotated[int, Path(gt=0)], payload: LossUpdateRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        await _authorized_loss(db, context, loss_id)
        changes = payload.model_dump(exclude_unset=True)
        expected_version = changes.pop('expected_version')
        if 'occurred_at' in changes:
            changes['occurred_at'] = _utc_naive(changes['occurred_at'])
        return await losses.update_loss(
            db, context=_execution(context), loss_id=loss_id,
            expected_version=expected_version, changes=changes,
            include_cost=_include_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/losses', response_model=LossListResponse)
async def list_losses(
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> LossListResponse:
    _authorize_location(context, location_id)
    values = await losses.list_losses(
        db, tenant_id=context.tenant_id, location_id=location_id,
        include_cost=_include_cost(context),
    )
    return LossListResponse(items=list(values))


@router.get('/losses/{loss_id}', response_model=LossResponse)
async def get_loss(
    loss_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        await _authorized_loss(db, context, loss_id)
        return await losses.get_loss(
            db, tenant_id=context.tenant_id, loss_id=loss_id,
            include_cost=_include_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc


async def _post_action(
    *, action: str, loss_id: int, payload: LossActionRequest,
    response: Response, context: AuthenticatedContext, db: AsyncSession,
    idempotency_key: str,
) -> Any:
    await _authorized_loss(db, context, loss_id)
    operation = losses.post_loss if action == 'post' else losses.approve_loss
    value, replayed = await operation(
        db, context=_execution(context), loss_id=loss_id,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key, include_cost=_include_cost(context),
    )
    if replayed:
        response.headers['Idempotent-Replay'] = 'true'
    return value


@router.post('/losses/{loss_id}:post', response_model=LossResponse)
async def post_loss(
    loss_id: Annotated[int, Path(gt=0)], payload: LossActionRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> Any:
    try:
        return await _post_action(
            action='post', loss_id=loss_id, payload=payload, response=response,
            context=context, db=db, idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/losses/{loss_id}:approve', response_model=LossResponse)
async def approve_loss(
    loss_id: Annotated[int, Path(gt=0)], payload: LossActionRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.approve'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> Any:
    try:
        return await _post_action(
            action='approve', loss_id=loss_id, payload=payload, response=response,
            context=context, db=db, idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc




@router.post('/losses/{loss_id}:cancel', response_model=LossResponse)
async def cancel_loss(
    loss_id: Annotated[int, Path(gt=0)], payload: LossActionRequest,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        await _authorized_loss(db, context, loss_id)
        return await losses.cancel_loss(
            db, context=_execution(context), loss_id=loss_id,
            expected_version=payload.expected_version,
            include_cost=_include_cost(context),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/losses/{loss_id}:reverse', response_model=LossResponse)
async def reverse_loss(
    loss_id: Annotated[int, Path(gt=0)], payload: LossReverseRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('inventory.loss.approve'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> Any:
    try:
        await _authorized_loss(db, context, loss_id)
        value, replayed = await losses.reverse_loss(
            db, context=_execution(context), loss_id=loss_id,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key, reason=payload.reason,
            include_cost=_include_cost(context),
        )
        if replayed:
            response.headers['Idempotent-Replay'] = 'true'
        return value
    except Exception as exc:
        raise _error(exc) from exc
