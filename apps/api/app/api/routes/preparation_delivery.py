from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.models import (
    Location,
    PreparationArea,
    PreparationDeliveryConnector,
    PreparationDeliveryDestination,
    PreparationWork,
)
from app.restaurant.preparation_delivery import errors, service


router = APIRouter(tags=['preparation-delivery'])
_CODE = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')
_TARGET = re.compile(r'^[A-Za-z][A-Za-z0-9._:-]{0,127}$')


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.PreparationDeliveryNotFoundError):
        return _not_found(str(exc))
    if isinstance(exc, (errors.PreparationDeliveryConflictError, errors.PreparationDeliveryConfigurationError)):
        return _conflict(str(exc))
    raise exc


async def _location(db: AsyncSession, tenant_id: int, location_id: int) -> Location:
    value = await db.scalar(select(Location).where(
        Location.id == location_id, Location.tenant_id == tenant_id,
    ))
    if value is None:
        raise _not_found('Location not found')
    return value


def _normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CODE.fullmatch(normalized):
        raise ValueError('Code must contain only letters, numbers, underscores, or hyphens')
    return normalized


class ConnectorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    location_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)

    @field_validator('code')
    @classmethod
    def code_value(cls, value: str) -> str:
        return _normalize_code(value)


class ConnectorPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal['ACTIVE', 'INACTIVE'] | None = None

    @model_validator(mode='after')
    def nonempty(self) -> 'ConnectorPatch':
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('At least one non-null field is required')
        return self


class ConnectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    code: str
    name: str
    auth_subject: str
    status: str
    created_at: datetime
    updated_at: datetime


@router.get('/preparation-delivery-connectors', response_model=tuple[ConnectorResponse, ...])
async def list_connectors(
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> object:
    await _location(db, context.tenant_id, location_id)
    return tuple((await db.execute(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.tenant_id == context.tenant_id,
        PreparationDeliveryConnector.location_id == location_id,
    ).order_by(PreparationDeliveryConnector.code, PreparationDeliveryConnector.id))).scalars().all())


@router.post('/preparation-delivery-connectors', response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    payload: ConnectorCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    location = await _location(db, context.tenant_id, payload.location_id)
    value = PreparationDeliveryConnector(
        tenant_id=context.tenant_id, organization_id=location.organization_id,
        location_id=location.id, code=payload.code, name=payload.name,
        auth_subject=f'preparation-connector:{uuid4().hex}', status='ACTIVE',
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Preparation Delivery Connector code already exists in this Location') from exc
    await db.refresh(value)
    return value


@router.patch('/preparation-delivery-connectors/{connector_id}', response_model=ConnectorResponse)
async def patch_connector(
    connector_id: Annotated[int, Path(gt=0)], payload: ConnectorPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    value = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == connector_id,
        PreparationDeliveryConnector.tenant_id == context.tenant_id,
    ).with_for_update())
    if value is None:
        raise _not_found('Preparation Delivery Connector not found')
    for key, item in payload.model_dump(exclude_unset=True).items():
        setattr(value, key, item)
    await db.commit()
    await db.refresh(value)
    return value


class DestinationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    location_id: int = Field(gt=0)
    preparation_area_id: int = Field(gt=0)
    connector_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    channel: Literal['PRINTER'] = 'PRINTER'
    local_target_key: str = Field(min_length=1, max_length=128)

    @field_validator('code')
    @classmethod
    def code_value(cls, value: str) -> str:
        return _normalize_code(value)

    @field_validator('local_target_key')
    @classmethod
    def target_value(cls, value: str) -> str:
        if not _TARGET.fullmatch(value) or '://' in value:
            raise ValueError('local_target_key must be an opaque connector-side identifier')
        return value


class DestinationPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=200)
    local_target_key: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal['ACTIVE', 'INACTIVE'] | None = None

    @field_validator('local_target_key')
    @classmethod
    def target_value(cls, value: str | None) -> str | None:
        if value is not None and (not _TARGET.fullmatch(value) or '://' in value):
            raise ValueError('local_target_key must be an opaque connector-side identifier')
        return value

    @model_validator(mode='after')
    def nonempty(self) -> 'DestinationPatch':
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('At least one non-null field is required')
        return self


class DestinationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    preparation_area_id: int
    connector_id: int
    code: str
    name: str
    channel: str
    local_target_key: str
    status: str
    created_at: datetime
    updated_at: datetime


async def _active_destination_scope(
    db: AsyncSession, *, tenant_id: int, location_id: int, area_id: int, connector_id: int,
) -> tuple[PreparationArea, PreparationDeliveryConnector]:
    area = await db.scalar(select(PreparationArea).where(
        PreparationArea.id == area_id, PreparationArea.tenant_id == tenant_id,
        PreparationArea.location_id == location_id, PreparationArea.status == 'ACTIVE',
    ))
    connector = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == connector_id,
        PreparationDeliveryConnector.tenant_id == tenant_id,
        PreparationDeliveryConnector.location_id == location_id,
        PreparationDeliveryConnector.status == 'ACTIVE',
    ))
    if area is None:
        raise _not_found('Active Preparation Area not found in this Location')
    if connector is None:
        raise _not_found('Active Preparation Delivery Connector not found in this Location')
    return area, connector


@router.get('/preparation-delivery-destinations', response_model=tuple[DestinationResponse, ...])
async def list_destinations(
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    preparation_area_id: int | None = Query(default=None, gt=0),
) -> object:
    await _location(db, context.tenant_id, location_id)
    statement = select(PreparationDeliveryDestination).where(
        PreparationDeliveryDestination.tenant_id == context.tenant_id,
        PreparationDeliveryDestination.location_id == location_id,
    )
    if preparation_area_id is not None:
        statement = statement.where(PreparationDeliveryDestination.preparation_area_id == preparation_area_id)
    return tuple((await db.execute(statement.order_by(
        PreparationDeliveryDestination.code, PreparationDeliveryDestination.id,
    ))).scalars().all())


@router.post('/preparation-delivery-destinations', response_model=DestinationResponse, status_code=status.HTTP_201_CREATED)
async def create_destination(
    payload: DestinationCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    location = await _location(db, context.tenant_id, payload.location_id)
    await _active_destination_scope(
        db, tenant_id=context.tenant_id, location_id=location.id,
        area_id=payload.preparation_area_id, connector_id=payload.connector_id,
    )
    value = PreparationDeliveryDestination(
        tenant_id=context.tenant_id, organization_id=location.organization_id,
        location_id=location.id, preparation_area_id=payload.preparation_area_id,
        connector_id=payload.connector_id, code=payload.code, name=payload.name,
        channel=payload.channel, local_target_key=payload.local_target_key,
        status='ACTIVE', active_slot=1,
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Destination code or active connector target already exists') from exc
    await db.refresh(value)
    return value


@router.patch('/preparation-delivery-destinations/{destination_id}', response_model=DestinationResponse)
async def patch_destination(
    destination_id: Annotated[int, Path(gt=0)], payload: DestinationPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    value = await db.scalar(select(PreparationDeliveryDestination).where(
        PreparationDeliveryDestination.id == destination_id,
        PreparationDeliveryDestination.tenant_id == context.tenant_id,
    ).with_for_update())
    if value is None:
        raise _not_found('Preparation Delivery Destination not found')
    updates = payload.model_dump(exclude_unset=True)
    if updates.get('status') == 'ACTIVE':
        await _active_destination_scope(
            db, tenant_id=context.tenant_id, location_id=value.location_id,
            area_id=value.preparation_area_id, connector_id=value.connector_id,
        )
    for key, item in updates.items():
        setattr(value, key, item)
    value.active_slot = 1 if value.status == 'ACTIVE' else None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Active connector target already exists') from exc
    await db.refresh(value)
    return value


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    attempt_sequence: int
    attempt_type: str
    connector_id: int
    actor_type: str
    actor_membership_id: int | None
    actor_principal_reference: str | None
    correlation_id: str | None
    started_at: datetime
    ended_at: datetime | None
    result: str
    result_fingerprint: str | None
    local_job_reference: str | None
    error_kind: str | None
    error_message: str | None


class DispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    restaurant_order_id: int
    preparation_work_id: int
    preparation_area_id: int
    destination_id: int
    operation_kind: str
    generation: int
    operation_id: str
    reprint_of_dispatch_id: int | None
    state: str
    payload_schema: str
    payload_text: str
    payload_fingerprint: str
    destination_code: str
    destination_name: str
    destination_channel: str
    connector_id: int
    connector_code: str
    connector_name: str
    local_target_key: str
    claim_expires_at: datetime | None
    attempt_count: int
    available_at: datetime
    last_error_kind: str | None
    last_error_message: str | None
    initiating_actor_type: str
    initiating_membership_id: int | None
    initiating_principal_reference: str | None
    correlation_id: str | None
    causation_id: str | None
    terminal_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: tuple[AttemptResponse, ...]


@router.get('/preparation-dispatches', response_model=tuple[DispatchResponse, ...])
async def list_dispatches(
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    state: Literal['PENDING', 'IN_PROGRESS', 'DESTINATION_SUBMISSION_ACCEPTED', 'RETRYABLE_FAILURE', 'UNCERTAIN', 'ACTION_REQUIRED'] | None = None,
    destination_id: int | None = Query(default=None, gt=0),
    preparation_work_id: int | None = Query(default=None, gt=0),
    restaurant_order_id: int | None = Query(default=None, gt=0),
    after_dispatch_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> object:
    await _location(db, context.tenant_id, location_id)
    try:
        return await service.list_dispatches(
            db, tenant_id=context.tenant_id, location_id=location_id, state=state,
            destination_id=destination_id, work_id=preparation_work_id,
            order_id=restaurant_order_id, after_dispatch_id=after_dispatch_id, limit=limit,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/preparation-dispatches/{dispatch_id}', response_model=DispatchResponse)
async def read_dispatch(
    dispatch_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_dispatch(db, tenant_id=context.tenant_id, dispatch_id=dispatch_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.get('/preparation-works/{work_id}/dispatches', response_model=tuple[DispatchResponse, ...])
async def read_work_dispatches(
    work_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    work = await db.scalar(select(PreparationWork).where(
        PreparationWork.id == work_id, PreparationWork.tenant_id == context.tenant_id,
    ))
    if work is None:
        raise _not_found('Preparation Work not found')
    return await service.list_dispatches(
        db, tenant_id=context.tenant_id, location_id=work.location_id, work_id=work.id,
        limit=200,
    )


@router.post(
    '/preparation-dispatches/{dispatch_id}/reprints',
    response_model=DispatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reprint_dispatch(
    dispatch_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.dispatch'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    execution = ExecutionContext(
        actor_type=ActorType.EMPLOYEE,
        tenant_id=context.tenant_id,
        principal_id=context.membership_id,
        principal_reference=None,
        correlation_id=get_correlation_id(),
    )
    try:
        return await service.create_reprint(
            db, source_dispatch_id=dispatch_id, execution=execution,
        )
    except Exception as exc:
        raise _error(exc) from exc
