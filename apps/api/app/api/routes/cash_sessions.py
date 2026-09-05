from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.cash_management import errors, service


router = APIRouter(tags=['cash-management'])
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key', min_length=1, max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


class OpenCashSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    currency: str = Field(min_length=3, max_length=3)


def _exact(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact money')
    return value


SignedMoney = Annotated[Decimal, BeforeValidator(_exact), Field(allow_inf_nan=False)]
CountedMoney = Annotated[
    Decimal, BeforeValidator(_exact), Field(ge=0, allow_inf_nan=False)
]


class CashMovementRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    movement_type: str = Field(min_length=1, max_length=24)
    amount: SignedMoney
    currency: str = Field(min_length=3, max_length=3)
    reason: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=200)


class CashCountRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    counted_amount: CountedMoney
    currency: str = Field(min_length=3, max_length=3)


class CloseCashSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    cash_count_id: int = Field(gt=0)
    variance_reason: str | None = Field(default=None, max_length=500)


class CashSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    cashier_membership_id: int
    currency: str
    status: str
    movement_version: int
    expected_cash: Decimal
    opened_at: datetime
    opened_by_actor_type: str
    opened_by_actor_id: int | None
    opened_by_actor_reference: str | None
    selected_cash_count_id: int | None
    final_movement_version: int | None
    frozen_expected_cash: Decimal | None
    frozen_variance: Decimal | None
    variance_reason: str | None
    closed_at: datetime | None
    closed_by_actor_type: str | None
    closed_by_actor_id: int | None
    closed_by_actor_reference: str | None


class CashMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cash_session_id: int
    movement_type: str
    amount: Decimal
    currency: str
    reason: str | None
    reference: str | None
    recorded_at: datetime
    actor_type: str
    actor_id: int | None
    actor_reference: str | None
    authorized_by_actor_type: str
    authorized_by_actor_id: int | None
    authorized_by_actor_reference: str | None


class CashCountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cash_session_id: int
    counted_amount: Decimal
    currency: str
    captured_movement_version: int
    counted_at: datetime
    actor_type: str
    actor_id: int | None
    actor_reference: str | None


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.EMPLOYEE,
        context.tenant_id,
        context.membership_id,
        None,
        get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.CashSessionPermissionError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, (
        errors.CashSessionNotFoundError,
        errors.CashRegisterNotFoundError,
        errors.CashCountNotFoundError,
    )):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, (
        errors.InvalidCashSessionRequestError,
        errors.InvalidCashMovementError,
        errors.InvalidCashCountError,
        errors.CashSessionVarianceReasonRequiredError,
    )):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, errors.CashManagementError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': exc.code, 'message': str(exc)},
        )
    raise exc


@router.post(
    '/resources/{resource_id}/cash-sessions',
    response_model=CashSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def open_cash_session(
    resource_id: Annotated[int, Path(gt=0)],
    payload: OpenCashSessionRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('cash_session.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> Any:
    try:
        value, replayed = await service.open_cash_session(
            db,
            context=_execution(context),
            resource_id=resource_id,
            currency=payload.currency,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.post(
    '/cash-sessions/{cash_session_id}/movements',
    response_model=CashMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cash_movement(
    cash_session_id: Annotated[int, Path(gt=0)],
    payload: CashMovementRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('cash_movement.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> Any:
    try:
        value, replayed = await service.create_manual_movement(
            db,
            context=_execution(context),
            cash_session_id=cash_session_id,
            movement_type=payload.movement_type,
            amount=payload.amount,
            currency=payload.currency,
            reason=payload.reason,
            reference=payload.reference,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.post(
    '/cash-sessions/{cash_session_id}/counts',
    response_model=CashCountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cash_count(
    cash_session_id: Annotated[int, Path(gt=0)],
    payload: CashCountRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('cash_session.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> Any:
    try:
        value, replayed = await service.create_cash_count(
            db,
            context=_execution(context),
            cash_session_id=cash_session_id,
            counted_amount=payload.counted_amount,
            currency=payload.currency,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.post(
    '/cash-sessions/{cash_session_id}/close',
    response_model=CashSessionResponse,
)
async def close_cash_session(
    cash_session_id: Annotated[int, Path(gt=0)],
    payload: CloseCashSessionRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('cash_session.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> Any:
    try:
        value, replayed = await service.close_cash_session(
            db,
            context=_execution(context),
            cash_session_id=cash_session_id,
            cash_count_id=payload.cash_count_id,
            variance_reason=payload.variance_reason,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.get(
    '/cash-sessions/{cash_session_id}', response_model=CashSessionResponse
)
async def get_cash_session(
    cash_session_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('cash_management.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    try:
        return await service.get_cash_session(
            db, tenant_id=context.tenant_id, cash_session_id=cash_session_id
        )
    except Exception as exc:
        raise _error(exc) from exc
