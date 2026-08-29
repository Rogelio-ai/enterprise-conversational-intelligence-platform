from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.pos_submissions import errors, service


router = APIRouter(tags=['pos-submissions'])


class PosSubmissionAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence: int
    attempt_type: str
    actor_type: str
    actor_membership_id: int | None
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    result: str
    error_kind: str | None
    error_message: str | None
    external_order_id: str | None


class PosSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_order_id: int
    connector_key: str
    external_location_id: str
    state: str
    idempotency_key: str
    request_fingerprint: str
    external_order_id: str | None
    external_status: str | None
    claim_expires_at: datetime | None
    last_error_kind: str | None
    last_error_message: str | None
    attempts: tuple[PosSubmissionAttemptResponse, ...]


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EMPLOYEE,
        tenant_id=context.tenant_id,
        principal_id=context.membership_id,
        principal_reference=None,
        correlation_id=get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.PosSubmissionNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, errors.PosSubmissionConfigurationError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, errors.PosSubmissionStateError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


async def _execute(
    *,
    order_id: int,
    action: str,
    request: Request,
    context: AuthenticatedContext,
    db: AsyncSession,
) -> PosSubmissionResponse:
    try:
        value = await service.execute_submission(
            db,
            order_id=order_id,
            execution=_execution(context),
            adapters=request.app.state.pos_adapters,
            action=action,
        )
    except Exception as exc:
        raise _error(exc) from exc
    return PosSubmissionResponse.model_validate(value)


@router.post('/restaurant-orders/{order_id}/pos-submission', response_model=PosSubmissionResponse)
async def submit_order_to_pos(
    order_id: Annotated[int, Path(gt=0)],
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('pos_submission.submit'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PosSubmissionResponse:
    return await _execute(order_id=order_id, action='submit', request=request, context=context, db=db)


@router.get('/restaurant-orders/{order_id}/pos-submission', response_model=PosSubmissionResponse)
async def read_order_pos_submission(
    order_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('pos_submission.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PosSubmissionResponse:
    try:
        value = await service.get_submission(db, tenant_id=context.tenant_id, order_id=order_id)
    except Exception as exc:
        raise _error(exc) from exc
    return PosSubmissionResponse.model_validate(value)


@router.post('/restaurant-orders/{order_id}/pos-submission/retry', response_model=PosSubmissionResponse)
async def retry_order_pos_submission(
    order_id: Annotated[int, Path(gt=0)],
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('pos_submission.retry'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PosSubmissionResponse:
    return await _execute(order_id=order_id, action='retry', request=request, context=context, db=db)


@router.post('/restaurant-orders/{order_id}/pos-submission/recover', response_model=PosSubmissionResponse)
async def recover_order_pos_submission(
    order_id: Annotated[int, Path(gt=0)],
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('pos_submission.recover'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PosSubmissionResponse:
    return await _execute(order_id=order_id, action='recover', request=request, context=context, db=db)
