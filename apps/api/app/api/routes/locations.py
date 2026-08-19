from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.models import Location, Organization


router = APIRouter(prefix='/locations', tags=['locations'])
logger = logging.getLogger('ecip.locations')
_CODE_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')
_COUNTRY_PATTERN = re.compile(r'^[A-Z]{2}$')
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_CODE_CONSTRAINT = 'uq_locations_organization_code'


def normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise ValueError('Code must contain only letters, numbers, underscores, or hyphens')
    return normalized


def validate_timezone(value: str) -> str:
    normalized = value.strip()
    try:
        ZoneInfo(normalized)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError('A valid IANA timezone is required')
    return normalized


def normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not _COUNTRY_PATTERN.fullmatch(normalized):
        raise ValueError('Country code must contain two letters')
    return normalized


def normalize_optional_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if '@' not in normalized or normalized.startswith('@') or normalized.endswith('@'):
        raise ValueError('A valid email is required')
    return normalized


class LocationFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    timezone: str = Field(min_length=1, max_length=64)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    locality: str | None = Field(default=None, max_length=100)
    administrative_area: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, max_length=2)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)

    @field_validator('code')
    @classmethod
    def validate_code(cls, value: str) -> str:
        return normalize_code(value)

    @field_validator('timezone')
    @classmethod
    def validate_timezone_field(cls, value: str) -> str:
        return validate_timezone(value)

    @field_validator('country_code')
    @classmethod
    def validate_country_code(cls, value: str | None) -> str | None:
        return normalize_country_code(value)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_optional_email(value)


class LocationCreateRequest(LocationFields):
    organization_id: int = Field(gt=0)


class LocationUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    status: Literal['ACTIVE', 'INACTIVE'] | None = None
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    locality: str | None = Field(default=None, max_length=100)
    administrative_area: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, max_length=2)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)

    @field_validator('code')
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        return normalize_code(value) if value is not None else None

    @field_validator('timezone')
    @classmethod
    def validate_timezone_field(cls, value: str | None) -> str | None:
        return validate_timezone(value) if value is not None else None

    @field_validator('country_code')
    @classmethod
    def validate_country_code(cls, value: str | None) -> str | None:
        return normalize_country_code(value)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_optional_email(value)

    @model_validator(mode='after')
    def validate_patch(self) -> 'LocationUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        required_when_present = {'code', 'name', 'timezone', 'status'}
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set.intersection(required_when_present)
        ):
            raise ValueError('Required Location fields cannot be null')
        return self


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    code: str
    name: str
    timezone: str
    status: str
    address_line1: str | None
    address_line2: str | None
    locality: str | None
    administrative_area: str | None
    postal_code: str | None
    country_code: str | None
    phone: str | None
    email: str | None
    created_at: datetime
    updated_at: datetime


class LocationListResponse(BaseModel):
    items: list[LocationResponse]
    limit: int
    offset: int


def _location_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')


def _organization_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Organization not found')


def _inactive_parent() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Organization must be active',
    )


def _duplicate_code() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Location code already exists in this Organization',
    )


def _is_duplicate_code_error(exc: IntegrityError) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == _CODE_CONSTRAINT


async def _get_organization(
    db: AsyncSession,
    *,
    organization_id: int,
    tenant_id: int,
    for_update: bool = False,
) -> Organization:
    statement = select(Organization).where(
        Organization.id == organization_id,
        Organization.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    organization = await db.scalar(statement)
    if organization is None:
        raise _organization_not_found()
    return organization


@router.get('', response_model=LocationListResponse)
async def list_locations(
    context: Annotated[AuthenticatedContext, Depends(require_permission('location.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LocationListResponse:
    if organization_id is not None:
        await _get_organization(
            db,
            organization_id=organization_id,
            tenant_id=context.tenant_id,
        )
    statement = select(Location).where(Location.tenant_id == context.tenant_id)
    if organization_id is not None:
        statement = statement.where(Location.organization_id == organization_id)
    result = await db.execute(statement.order_by(Location.id).limit(limit).offset(offset))
    return LocationListResponse(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('', response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('location.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Location:
    organization = await _get_organization(
        db,
        organization_id=payload.organization_id,
        tenant_id=context.tenant_id,
        for_update=True,
    )
    if organization.status != 'ACTIVE':
        raise _inactive_parent()

    values = payload.model_dump()
    values['tenant_id'] = context.tenant_id
    location = Location(**values, status='ACTIVE')
    db.add(location)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate_code_error(exc):
            raise _duplicate_code() from exc
        raise
    await db.refresh(location)
    logger.info(
        'Location created',
        extra={
            'event': 'location_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'organization_id': location.organization_id,
            'location_id': location.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return location


@router.get('/{location_id}', response_model=LocationResponse)
async def get_location(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('location.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Location:
    location = await db.scalar(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == context.tenant_id,
        )
    )
    if location is None:
        raise _location_not_found()
    return location


@router.patch('/{location_id}', response_model=LocationResponse)
async def update_location(
    location_id: Annotated[int, Path(gt=0)],
    payload: LocationUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('location.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Location:
    location = await db.scalar(
        select(Location)
        .where(
            Location.id == location_id,
            Location.tenant_id == context.tenant_id,
        )
        .with_for_update()
    )
    if location is None:
        raise _location_not_found()

    updates = payload.model_dump(exclude_unset=True)
    if updates.get('status') == 'ACTIVE':
        organization = await _get_organization(
            db,
            organization_id=location.organization_id,
            tenant_id=context.tenant_id,
            for_update=True,
        )
        if organization.status != 'ACTIVE':
            raise _inactive_parent()
    for field, value in updates.items():
        setattr(location, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate_code_error(exc):
            raise _duplicate_code() from exc
        raise
    await db.refresh(location)
    logger.info(
        'Location updated',
        extra={
            'event': 'location_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'organization_id': location.organization_id,
            'location_id': location.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return location
