from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
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
    opened_at: datetime
    opened_by_actor_type: str
    opened_by_actor_id: int | None
    opened_by_actor_reference: str | None


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
    )):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, errors.InvalidCashSessionRequestError):
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
