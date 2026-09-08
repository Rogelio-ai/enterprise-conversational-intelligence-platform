from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedContext,
    get_db,
    require_permission,
    require_staff_location_access,
)
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.paid_check_printing import errors, service
from app.models import PaidCheckDispatch, RestaurantCheck


router = APIRouter(tags=['paid-check-printing'])
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key', min_length=1, max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


class PaidCheckPrintRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cashier_resource_id: int = Field(gt=0)
    connector_id: int = Field(gt=0)
    local_target_key: str = Field(min_length=1, max_length=128)


class PaidCheckAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    attempt_sequence: int
    attempt_type: str
    connector_id: int
    claim_request_id: str | None
    started_at: datetime
    ended_at: datetime | None
    result: str
    result_fingerprint: str | None
    local_job_reference: str | None
    error_kind: str | None
    error_message: str | None


class PaidCheckDispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_check_id: int
    check_version: int
    check_fingerprint: str
    cashier_resource_id: int
    cashier_resource_code: str
    cashier_resource_name: str
    connector_id: int
    connector_code: str
    connector_name: str
    local_target_key: str
    operation_id: str
    state: str
    payload_schema: str
    payload_fingerprint: str
    claim_expires_at: datetime | None
    attempt_count: int
    available_at: datetime
    last_error_kind: str | None
    last_error_message: str | None
    created_by_membership_id: int
    terminal_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: tuple[PaidCheckAttemptResponse, ...] = ()


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EMPLOYEE,
        tenant_id=context.tenant_id,
        principal_id=context.membership_id,
        principal_reference=None,
        correlation_id=get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.PaidCheckDispatchNotFoundError):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            {'code': exc.code, 'message': str(exc)},
        )
    if isinstance(exc, errors.PaidCheckPrintingError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': exc.code, 'message': str(exc)},
        )
    raise exc


async def _authorize_check(
    db: AsyncSession,
    context: AuthenticatedContext,
    *,
    check_id: int,
    location_id: int | None,
) -> int:
    value = await db.scalar(select(RestaurantCheck.location_id).where(
        RestaurantCheck.id == check_id,
        RestaurantCheck.tenant_id == context.tenant_id,
        *((RestaurantCheck.location_id == location_id,) if location_id is not None else ()),
    ))
    if value is None:
        raise errors.PaidCheckDispatchNotFoundError('RestaurantCheck not found')
    authorized_location_id = int(value)
    await require_staff_location_access(authorized_location_id, context, db)
    return authorized_location_id


async def _authorize_dispatch(
    db: AsyncSession,
    context: AuthenticatedContext,
    *,
    dispatch_id: int,
    location_id: int | None,
) -> int:
    value = await db.scalar(select(PaidCheckDispatch.location_id).where(
        PaidCheckDispatch.id == dispatch_id,
        PaidCheckDispatch.tenant_id == context.tenant_id,
        *((PaidCheckDispatch.location_id == location_id,) if location_id is not None else ()),
    ))
    if value is None:
        raise errors.PaidCheckDispatchNotFoundError('Paid-check dispatch not found')
    authorized_location_id = int(value)
    await require_staff_location_access(authorized_location_id, context, db)
    return authorized_location_id


@router.post(
    '/restaurant-checks/{check_id}/paid-print',
    response_model=PaidCheckDispatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_paid_check_print(
    check_id: Annotated[int, Path(gt=0)],
    payload: PaidCheckPrintRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
    location_id: Annotated[int | None, Query(gt=0)] = None,
) -> object:
    try:
        await _authorize_check(
            db, context, check_id=check_id, location_id=location_id
        )
        value, replayed = await service.create_dispatch(
            db,
            execution=_execution(context),
            check_id=check_id,
            cashier_resource_id=payload.cashier_resource_id,
            connector_id=payload.connector_id,
            local_target_key=payload.local_target_key,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.get(
    '/paid-check-dispatches/{dispatch_id}',
    response_model=PaidCheckDispatchResponse,
)
async def read_paid_check_dispatch(
    dispatch_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_check.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: Annotated[int | None, Query(gt=0)] = None,
) -> object:
    try:
        await _authorize_dispatch(
            db, context, dispatch_id=dispatch_id, location_id=location_id
        )
        return await service.get_dispatch(
            db, tenant_id=context.tenant_id, dispatch_id=dispatch_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/restaurant-checks/{check_id}/paid-print-dispatches',
    response_model=tuple[PaidCheckDispatchResponse, ...],
)
async def list_paid_check_dispatches(
    check_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_check.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        await _authorize_check(
            db, context, check_id=check_id, location_id=location_id
        )
        values = tuple((await db.scalars(select(PaidCheckDispatch).where(
            PaidCheckDispatch.tenant_id == context.tenant_id,
            PaidCheckDispatch.location_id == location_id,
            PaidCheckDispatch.restaurant_check_id == check_id,
        ).order_by(PaidCheckDispatch.id))).all())
        return tuple([
            await service.get_dispatch(
                db, tenant_id=context.tenant_id, dispatch_id=value.id
            )
            for value in values
        ])
    except Exception as exc:
        raise _error(exc) from exc
