from __future__ import annotations

import logging
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
from app.core.middleware import get_correlation_id
from app.models import Location, Organization
from app.organization_location import (
    OrganizationLocationConflictError,
    assign_headquarters_in_transaction,
    validate_organization_activation,
)


router = APIRouter(prefix='/organizations', tags=['organizations'])
logger = logging.getLogger('ecip.organizations')
_CODE_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_CODE_CONSTRAINT = 'uq_organizations_tenant_code'


def normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise ValueError('Code must contain only letters, numbers, underscores, or hyphens')
    return normalized


class OrganizationCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)

    @field_validator('code')
    @classmethod
    def validate_code(cls, value: str) -> str:
        return normalize_code(value)


class OrganizationUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal['ACTIVE', 'INACTIVE'] | None = None

    @field_validator('code')
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        return normalize_code(value) if value is not None else None

    @model_validator(mode='after')
    def validate_patch(self) -> 'OrganizationUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Organization fields cannot be null')
        return self


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    status: str
    headquarters_location_id: int | None
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    limit: int
    offset: int


class HeadquartersUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    location_id: int = Field(gt=0)
    deactivate_previous: bool = False


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Organization not found')


def _duplicate_code() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Organization code already exists in this Tenant',
    )


def _is_duplicate_code_error(exc: IntegrityError) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == _CODE_CONSTRAINT


@router.get('', response_model=OrganizationListResponse)
async def list_organizations(
    context: Annotated[AuthenticatedContext, Depends(require_permission('organization.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OrganizationListResponse:
    result = await db.execute(
        select(Organization)
        .where(Organization.tenant_id == context.tenant_id)
        .order_by(Organization.id)
        .limit(limit)
        .offset(offset)
    )
    return OrganizationListResponse(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('', response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('organization.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    organization = Organization(
        tenant_id=context.tenant_id,
        code=payload.code,
        name=payload.name,
        status='INACTIVE',
    )
    db.add(organization)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate_code_error(exc):
            raise _duplicate_code() from exc
        raise
    await db.refresh(organization)
    logger.info(
        'Organization created',
        extra={
            'event': 'organization_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'organization_id': organization.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return organization


@router.get('/{organization_id}', response_model=OrganizationResponse)
async def get_organization(
    organization_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('organization.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == context.tenant_id,
        )
    )
    if organization is None:
        raise _not_found()
    return organization


@router.patch('/{organization_id}', response_model=OrganizationResponse)
async def update_organization(
    organization_id: Annotated[int, Path(gt=0)],
    payload: OrganizationUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('organization.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    organization = await db.scalar(
        select(Organization)
        .where(
            Organization.id == organization_id,
            Organization.tenant_id == context.tenant_id,
        )
        .with_for_update()
    )
    if organization is None:
        raise _not_found()

    updates = payload.model_dump(exclude_unset=True)
    if updates.get('status') == 'ACTIVE':
        try:
            await validate_organization_activation(db, organization=organization)
        except OrganizationLocationConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    for field, value in updates.items():
        setattr(organization, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate_code_error(exc):
            raise _duplicate_code() from exc
        raise
    await db.refresh(organization)
    logger.info(
        'Organization updated',
        extra={
            'event': 'organization_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'organization_id': organization.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return organization


@router.put('/{organization_id}/headquarters', response_model=OrganizationResponse)
async def update_headquarters(
    organization_id: Annotated[int, Path(gt=0)],
    payload: HeadquartersUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('organization.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    organization = await db.scalar(
        select(Organization)
        .where(
            Organization.id == organization_id,
            Organization.tenant_id == context.tenant_id,
        )
        .with_for_update()
    )
    if organization is None:
        raise _not_found()

    headquarters_scope_ids = tuple(
        value for value in {
            organization.headquarters_location_id,
            payload.location_id,
        }
        if value is not None
    )
    scoped_locations = tuple((await db.scalars(
        select(Location).where(
            Location.id.in_(headquarters_scope_ids),
            Location.tenant_id == context.tenant_id,
            Location.organization_id == organization.id,
        )
    )).all())
    scoped_ids = {value.id for value in scoped_locations}
    if payload.location_id not in scoped_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')
    required_location_ids = {payload.location_id}
    if organization.headquarters_location_id is not None:
        required_location_ids.add(organization.headquarters_location_id)
    if any(
        context.authority_for_location(location_id) is None
        or 'location.manage' not in context.authority_for_location(location_id).permissions
        for location_id in required_location_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Insufficient Location permission',
        )
    try:
        await assign_headquarters_in_transaction(
            db,
            organization=organization,
            location_id=payload.location_id,
            actor_membership_id=context.membership_id,
            operation_id=str(uuid4()),
            deactivate_previous=payload.deactivate_previous,
        )
        await db.commit()
    except OrganizationLocationConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Headquarters update conflicted with concurrent state',
        )
    await db.refresh(organization)
    logger.info(
        'Organization headquarters updated',
        extra={
            'event': 'organization_headquarters_updated',
            'operation': 'update_headquarters',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'organization_id': organization.id,
            'location_id': payload.location_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return organization
