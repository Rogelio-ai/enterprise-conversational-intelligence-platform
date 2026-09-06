from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.paid_check_printing import errors, service


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
) -> object:
    try:
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
) -> object:
    try:
        return await service.get_dispatch(
            db, tenant_id=context.tenant_id, dispatch_id=dispatch_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
