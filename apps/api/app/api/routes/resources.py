from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedContext,
    get_db,
    require_permission,
    require_staff_location_access,
)
from app.core.middleware import get_correlation_id
from app.models import Location, Resource
from app.restaurant import resource_provisioning


ResourceType = Literal[
    'AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', 'VEHICLE', 'DEVICE',
    'CASH_REGISTER',
]
ResourceStatus = Literal['ACTIVE', 'INACTIVE']

router = APIRouter(prefix='/resources', tags=['resources'])
logger = logging.getLogger('ecip.resources')


def normalize_code(value: str) -> str:
    return resource_provisioning.normalize_code(value)


class ResourceCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    location_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    resource_type: ResourceType

    @field_validator('code')
    @classmethod
    def validate_code(cls, value: str) -> str:
        return normalize_code(value)


class ResourceUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    resource_type: ResourceType | None = None
    status: ResourceStatus | None = None

    @field_validator('code')
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        return normalize_code(value) if value is not None else None

    @model_validator(mode='after')
    def validate_patch(self) -> 'ResourceUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Resource fields cannot be null')
        return self


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    location_id: int
    code: str
    name: str
    resource_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class ResourceListResponse(BaseModel):
    items: list[ResourceResponse]
    limit: int
    offset: int


def _resource_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Resource not found')


def _location_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')


def _inactive_parent() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Location must be active',
    )


def _duplicate_code() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Resource code already exists in this Location',
    )


def _is_duplicate_code_error(exc: IntegrityError) -> bool:
    return resource_provisioning.is_duplicate_code_error(exc)


async def _get_location(
    db: AsyncSession,
    *,
    location_id: int,
    tenant_id: int,
    for_update: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    location = await db.scalar(statement)
    if location is None:
        raise _location_not_found()
    return location


@router.get('', response_model=ResourceListResponse)
async def list_resources(
    context: Annotated[AuthenticatedContext, Depends(require_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int | None = Query(default=None, gt=0),
    resource_type: ResourceType | None = Query(default=None),
    status_filter: ResourceStatus | None = Query(default=None, alias='status'),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ResourceListResponse:
    if location_id is not None:
        await require_staff_location_access(location_id, context, db)
        await _get_location(
            db,
            location_id=location_id,
            tenant_id=context.tenant_id,
        )
    statement = select(Resource).where(Resource.tenant_id == context.tenant_id)
    if location_id is not None:
        statement = statement.where(Resource.location_id == location_id)
    if resource_type is not None:
        statement = statement.where(Resource.resource_type == resource_type)
    if status_filter is not None:
        statement = statement.where(Resource.status == status_filter)
    result = await db.execute(statement.order_by(Resource.id).limit(limit).offset(offset))
    return ResourceListResponse(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('', response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    payload: ResourceCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('resource.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Resource:
    try:
        resource = await resource_provisioning.create_resource(
            db, tenant_id=context.tenant_id, location_id=payload.location_id,
            code=payload.code, name=payload.name,
            resource_type=payload.resource_type,
        )
    except resource_provisioning.ResourceScopeNotFoundError as exc:
        await db.rollback()
        raise _location_not_found() from exc
    except resource_provisioning.ResourceConflictError as exc:
        if str(exc) == 'Location must be active':
            raise _inactive_parent() from exc
        raise _duplicate_code() from exc
    logger.info(
        'Resource created',
        extra={
            'event': 'resource_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'location_id': resource.location_id,
            'resource_id': resource.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return resource


@router.get('/{resource_id}', response_model=ResourceResponse)
async def get_resource(
    resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Resource:
    resource = await db.scalar(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.tenant_id == context.tenant_id,
        )
    )
    if resource is None:
        raise _resource_not_found()
    return resource


@router.patch('/{resource_id}', response_model=ResourceResponse)
async def update_resource(
    resource_id: Annotated[int, Path(gt=0)],
    payload: ResourceUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('resource.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Resource:
    updates = payload.model_dump(exclude_unset=True)
    try:
        resource = await resource_provisioning.update_resource(
            db, tenant_id=context.tenant_id,
            resource_id=resource_id, changes=updates,
        )
    except resource_provisioning.ResourceScopeNotFoundError as exc:
        await db.rollback()
        raise _resource_not_found() from exc
    except resource_provisioning.ResourceConflictError as exc:
        if str(exc) == 'Location must be active':
            raise _inactive_parent() from exc
        raise _duplicate_code() from exc
    logger.info(
        'Resource updated',
        extra={
            'event': 'resource_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'location_id': resource.location_id,
            'resource_id': resource.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return resource
