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
from app.models import Organization, Product, ProductAlias
from app.restaurant.catalog.resolution import (
    normalize_alias,
    validate_language_tag,
)


router = APIRouter(prefix='/product-aliases', tags=['product aliases'])
logger = logging.getLogger('ecip.product_aliases')
Lifecycle = Literal['ACTIVE', 'INACTIVE']
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_IDENTITY_CONSTRAINT = 'uq_product_aliases_product_identity'


def _validate_language(value: str | None) -> str | None:
    if not validate_language_tag(value):
        raise ValueError('Language must be a valid BCP-47-style tag')
    return value


class ProductAliasCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    organization_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    alias: str = Field(min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=63)
    status: Lifecycle = 'ACTIVE'

    _language = field_validator('language')(_validate_language)


class ProductAliasUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    alias: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=63)
    status: Lifecycle | None = None

    _language = field_validator('language')(_validate_language)

    @model_validator(mode='after')
    def validate_patch(self) -> 'ProductAliasUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if 'alias' in self.model_fields_set and self.alias is None:
            raise ValueError('Alias cannot be null')
        if 'status' in self.model_fields_set and self.status is None:
            raise ValueError('Status cannot be null')
        return self


class ProductAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    product_id: int
    alias: str
    normalized_alias: str
    language: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @field_validator('language', mode='before')
    @classmethod
    def neutral_language_as_null(cls, value: object) -> object:
        return None if value == '' else value


class ProductAliasListResponse(BaseModel):
    items: list[ProductAliasResponse]
    limit: int
    offset: int


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f'{entity} not found')


def _duplicate_alias() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        'Product Alias already exists for this Product and language',
    )


def _is_duplicate(exc: IntegrityError) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == _IDENTITY_CONSTRAINT


async def _require_product(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    product_id: int,
) -> Product:
    product = await db.scalar(
        select(Product)
        .join(
            Organization,
            (Organization.id == Product.organization_id)
            & (Organization.tenant_id == Product.tenant_id),
        )
        .where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.organization_id == organization_id,
        )
    )
    if product is None:
        raise _not_found('Product')
    return product


async def _require_alias(
    db: AsyncSession, *, tenant_id: int, alias_id: int, for_update: bool = False
) -> ProductAlias:
    query = select(ProductAlias).where(
        ProductAlias.id == alias_id, ProductAlias.tenant_id == tenant_id
    )
    if for_update:
        query = query.with_for_update()
    alias = await db.scalar(query)
    if alias is None:
        raise _not_found('Product Alias')
    return alias


@router.post('', response_model=ProductAliasResponse, status_code=status.HTTP_201_CREATED)
async def create_product_alias(
    payload: ProductAliasCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductAlias:
    await _require_product(
        db,
        tenant_id=context.tenant_id,
        organization_id=payload.organization_id,
        product_id=payload.product_id,
    )
    try:
        normalized = normalize_alias(payload.alias)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    alias = ProductAlias(
        tenant_id=context.tenant_id,
        organization_id=payload.organization_id,
        product_id=payload.product_id,
        alias=payload.alias,
        normalized_alias=normalized,
        language=payload.language or '',
        status=payload.status,
    )
    db.add(alias)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate(exc):
            raise _duplicate_alias() from exc
        raise
    await db.refresh(alias)
    logger.info(
        'Product Alias created',
        extra={
            'event': 'product_alias_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'organization_id': alias.organization_id,
            'product_id': alias.product_id,
            'product_alias_id': alias.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return alias


@router.get('', response_model=ProductAliasListResponse)
async def list_product_aliases(
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    product_id: int = Query(gt=0),
    status_filter: Lifecycle | None = Query(default=None, alias='status'),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductAliasListResponse:
    await _require_product(
        db,
        tenant_id=context.tenant_id,
        organization_id=organization_id,
        product_id=product_id,
    )
    query = select(ProductAlias).where(
        ProductAlias.tenant_id == context.tenant_id,
        ProductAlias.organization_id == organization_id,
        ProductAlias.product_id == product_id,
    )
    if status_filter is not None:
        query = query.where(ProductAlias.status == status_filter)
    aliases = (
        await db.execute(query.order_by(ProductAlias.id).limit(limit).offset(offset))
    ).scalars().all()
    return ProductAliasListResponse(items=list(aliases), limit=limit, offset=offset)


@router.get('/{alias_id}', response_model=ProductAliasResponse)
async def get_product_alias(
    alias_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductAlias:
    return await _require_alias(db, tenant_id=context.tenant_id, alias_id=alias_id)


@router.patch('/{alias_id}', response_model=ProductAliasResponse)
async def update_product_alias(
    alias_id: Annotated[int, Path(gt=0)],
    payload: ProductAliasUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductAlias:
    alias = await _require_alias(
        db, tenant_id=context.tenant_id, alias_id=alias_id, for_update=True
    )
    updates = payload.model_dump(exclude_unset=True)
    if 'alias' in updates:
        try:
            alias.normalized_alias = normalize_alias(updates['alias'])
        except ValueError as exc:
            await db.rollback()
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        alias.alias = updates['alias']
    if 'language' in updates:
        alias.language = updates['language'] or ''
    if 'status' in updates:
        alias.status = updates['status']
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_duplicate(exc):
            raise _duplicate_alias() from exc
        raise
    await db.refresh(alias)
    logger.info(
        'Product Alias updated',
        extra={
            'event': 'product_alias_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'organization_id': alias.organization_id,
            'product_id': alias.product_id,
            'product_alias_id': alias.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return alias
