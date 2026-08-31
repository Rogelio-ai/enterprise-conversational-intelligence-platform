from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.connector_deps import ConnectorContext, get_connector_context
from app.api.deps import get_db
from app.core.connector_security import PROTOCOL_VERSION
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.models import PreparationDeliveryConnector, PreparationDispatch
from app.restaurant.preparation_delivery import errors, service
from app.restaurant.preparation_delivery.contracts import DeliveryResult


router = APIRouter(prefix='/connector/v1', tags=['restaurant-local-connector'])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _execution(context: ConnectorContext) -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EXTERNAL_SYSTEM, tenant_id=context.tenant_id,
        principal_id=None, principal_reference=context.auth_subject,
        correlation_id=get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.PreparationDeliveryNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, (errors.PreparationDeliveryConflictError, errors.PreparationDeliveryConfigurationError)):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


async def _touch(
    db: AsyncSession, context: ConnectorContext, *, connector_version: str | None = None,
    protocol_version: str | None = None,
) -> PreparationDeliveryConnector:
    connector = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == context.connector_id,
        PreparationDeliveryConnector.tenant_id == context.tenant_id,
        PreparationDeliveryConnector.organization_id == context.organization_id,
        PreparationDeliveryConnector.location_id == context.location_id,
    ))
    if connector is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid connector authentication credentials')
    connector.last_seen_at = _now()
    if connector_version is not None:
        connector.connector_version = connector_version
    if protocol_version is not None:
        connector.protocol_version = protocol_version
    return connector


def _wire(value: object) -> dict[str, object]:
    return asdict(value)  # FastAPI encodes datetimes safely.


@router.get('/dispatches/eligible')
async def eligible_dispatches(
    context: Annotated[ConnectorContext, Depends(get_connector_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, object]:
    await _touch(db, context)
    statement = select(PreparationDispatch).where(
        PreparationDispatch.tenant_id == context.tenant_id,
        PreparationDispatch.organization_id == context.organization_id,
        PreparationDispatch.location_id == context.location_id,
        PreparationDispatch.connector_id_snapshot == context.connector_id,
        PreparationDispatch.state.in_(('PENDING', 'RETRYABLE_FAILURE')),
        PreparationDispatch.available_at <= _now(),
    )
    if cursor is not None:
        statement = statement.where(PreparationDispatch.id > cursor)
    rows = tuple((await db.execute(statement.order_by(
        PreparationDispatch.created_at, PreparationDispatch.id,
    ).limit(limit + 1))).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    await db.commit()
    return {
        'items': [{
            'dispatch_id': row.id, 'operation_id': row.operation_id,
            'generation': row.generation, 'operation_kind': row.operation_kind,
            'state': row.state, 'available_at': row.available_at,
            'created_at': row.created_at,
        } for row in rows],
        'next_cursor': rows[-1].id if has_more and rows else None,
    }


@router.get('/dispatches/{dispatch_id}')
async def get_dispatch(
    dispatch_id: Annotated[int, Path(gt=0)],
    context: Annotated[ConnectorContext, Depends(get_connector_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    await _touch(db, context)
    value = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.id == dispatch_id,
        PreparationDispatch.tenant_id == context.tenant_id,
        PreparationDispatch.organization_id == context.organization_id,
        PreparationDispatch.location_id == context.location_id,
        PreparationDispatch.connector_id_snapshot == context.connector_id,
    ))
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Preparation Dispatch not found')
    projection = await service.get_dispatch(
        db, tenant_id=context.tenant_id, dispatch_id=value.id,
    )
    await db.commit()
    return _wire(projection)


class ClaimRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False, extra='forbid')
    claim_request_id: str = Field(min_length=1, max_length=128)


class RecoveryClaimRequest(ClaimRequest):
    resolution: Literal['NO_SUBMISSION_CONFIRMED', 'CONFIGURATION_REPAIRED']


async def _claim(
    *, dispatch_id: int, claim_request_id: str, recovery: bool,
    context: ConnectorContext, db: AsyncSession, lease_seconds: int,
) -> dict[str, object]:
    await _touch(db, context)
    try:
        outcome = await service.claim_dispatch(
            db, dispatch_id=dispatch_id, connector_id=context.connector_id,
            execution=_execution(context), recovery=recovery,
            claim_request_id=claim_request_id, claim_lease_seconds=lease_seconds,
        )
    except Exception as exc:
        raise _error(exc) from exc
    dispatch = _wire(outcome.dispatch)
    return {
        'dispatch_id': outcome.dispatch.id,
        'operation_id': outcome.dispatch.operation_id,
        'generation': outcome.dispatch.generation,
        'operation_kind': outcome.dispatch.operation_kind,
        'destination': {
            'code': outcome.dispatch.destination_code,
            'name': outcome.dispatch.destination_name,
            'channel': outcome.dispatch.destination_channel,
            'connector_id': outcome.dispatch.connector_id,
        },
        'local_target_key': outcome.dispatch.local_target_key,
        'payload_schema': outcome.dispatch.payload_schema,
        'payload_text': outcome.dispatch.payload_text,
        'payload_fingerprint': outcome.dispatch.payload_fingerprint,
        'claim_request_id': claim_request_id,
        'claim_token': outcome.claim_token,
        'claim_expires_at': outcome.dispatch.claim_expires_at,
        'attempt': _wire(outcome.attempt),
        'immutable_metadata': {
            'tenant_id': outcome.dispatch.tenant_id,
            'organization_id': outcome.dispatch.organization_id,
            'location_id': outcome.dispatch.location_id,
            'restaurant_order_id': outcome.dispatch.restaurant_order_id,
            'preparation_work_id': outcome.dispatch.preparation_work_id,
            'preparation_area_id': outcome.dispatch.preparation_area_id,
            'destination_id': outcome.dispatch.destination_id,
            'created_at': outcome.dispatch.created_at,
        },
        'dispatch': dispatch,
    }


@router.post('/dispatches/{dispatch_id}/claims')
async def claim_dispatch(
    dispatch_id: Annotated[int, Path(gt=0)], payload: ClaimRequest, request: Request,
    context: Annotated[ConnectorContext, Depends(get_connector_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _claim(
        dispatch_id=dispatch_id, claim_request_id=payload.claim_request_id,
        recovery=False, context=context, db=db,
        lease_seconds=request.app.state.settings.preparation_dispatch_claim_lease_seconds,
    )


@router.post('/dispatches/{dispatch_id}/recovery-claims')
async def recovery_claim(
    dispatch_id: Annotated[int, Path(gt=0)], payload: RecoveryClaimRequest, request: Request,
    context: Annotated[ConnectorContext, Depends(get_connector_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    current = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.id == dispatch_id,
        PreparationDispatch.tenant_id == context.tenant_id,
        PreparationDispatch.connector_id_snapshot == context.connector_id,
    ))
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Preparation Dispatch not found')
    if current.state == 'UNCERTAIN' and payload.resolution != 'NO_SUBMISSION_CONFIRMED':
        raise HTTPException(status.HTTP_409_CONFLICT, 'UNCERTAIN recovery requires definitive non-submission evidence')
    if current.state == 'ACTION_REQUIRED' and payload.resolution != 'CONFIGURATION_REPAIRED':
        raise HTTPException(status.HTTP_409_CONFLICT, 'ACTION_REQUIRED recovery requires repair confirmation')
    if current.state == 'IN_PROGRESS' and payload.resolution != 'NO_SUBMISSION_CONFIRMED':
        raise HTTPException(status.HTTP_409_CONFLICT, 'Expired claim recovery requires definitive non-submission evidence')
    return await _claim(
        dispatch_id=dispatch_id, claim_request_id=payload.claim_request_id,
        recovery=True, context=context, db=db,
        lease_seconds=request.app.state.settings.preparation_dispatch_claim_lease_seconds,
    )


class ResultRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claim_token: str = Field(min_length=36, max_length=36)
    result: Literal['DESTINATION_SUBMISSION_ACCEPTED', 'RETRYABLE_FAILURE', 'UNCERTAIN', 'ACTION_REQUIRED']
    result_fingerprint: str = Field(min_length=64, max_length=64)
    local_job_reference: str | None = Field(default=None, max_length=200)
    error_kind: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)


@router.post('/dispatches/{dispatch_id}/results')
async def report_result(
    dispatch_id: Annotated[int, Path(gt=0)], payload: ResultRequest,
    context: Annotated[ConnectorContext, Depends(get_connector_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    await _touch(db, context)
    try:
        outcome = await service.record_result(
            db, dispatch_id=dispatch_id, connector_id=context.connector_id,
            claim_token=payload.claim_token,
            delivery_result=DeliveryResult(
                result=payload.result, result_fingerprint=payload.result_fingerprint,
                local_job_reference=payload.local_job_reference,
                error_kind=payload.error_kind, error_message=payload.error_message,
            ), execution=_execution(context),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return {
        'dispatch': _wire(outcome.dispatch), 'attempt': _wire(outcome.attempt),
        'replayed': outcome.replayed,
    }


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    connector_version: str = Field(min_length=1, max_length=64)
    protocol_version: Literal['restaurant-local-connector-v1'] = PROTOCOL_VERSION
    runtime_status: str | None = Field(default=None, max_length=64)
    capabilities: tuple[str, ...] = Field(default=(), max_length=32)


@router.post('/heartbeat')
async def heartbeat(
    payload: HeartbeatRequest,
    context: Annotated[ConnectorContext, Depends(get_connector_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    connector = await _touch(
        db, context, connector_version=payload.connector_version,
        protocol_version=payload.protocol_version,
    )
    await db.commit()
    return {
        'observed_at': connector.last_seen_at,
        'connector_id': connector.id,
        'protocol_version': PROTOCOL_VERSION,
    }
