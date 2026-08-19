from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.models import Organization


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
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    limit: int
    offset: int


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
        status='ACTIVE',
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

    for field, value in payload.model_dump(exclude_unset=True).items():
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
