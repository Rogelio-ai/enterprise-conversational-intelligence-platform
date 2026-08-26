from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.models import Menu, Organization, Product, ProductCategory
from app.restaurant.catalog.queries import product_statement
from app.restaurant.catalog import structure


Lifecycle = Literal['ACTIVE', 'INACTIVE']
router = APIRouter(tags=['products'])
logger = logging.getLogger('ecip.products')
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_CATEGORY_NAME_CONSTRAINT = 'uq_product_categories_tenant_org_name'


class ProductCategoryCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    organization_id: int = Field(gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=200)
    display_order: int = Field(default=0, ge=0)


class ProductCategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    parent_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'ProductCategoryUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set - {'parent_id'}
        ):
            raise ValueError('Product Category fields cannot be null')
        return self


class ProductCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    parent_id: int | None
    name: str
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class ProductCategoryListResponse(BaseModel):
    items: list[ProductCategoryResponse]
    limit: int
    offset: int


class ProductCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    organization_id: int = Field(gt=0)
    category_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)


class ProductUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'ProductUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        for field in self.model_fields_set - {'category_id', 'description'}:
            if getattr(self, field) is None:
                raise ValueError('Product name and status cannot be null')
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    category_id: int | None
    name: str
    description: str | None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    limit: int
    offset: int


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{entity} not found')


def _duplicate_category() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='Product Category name already exists in this Organization',
    )


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


async def _get_organization(
    db: AsyncSession, *, tenant_id: int, organization_id: int
) -> Organization:
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == tenant_id,
        )
    )
    if organization is None:
        raise _not_found('Organization')
    return organization


async def _get_category(
    db: AsyncSession,
    *,
    tenant_id: int,
    category_id: int,
    organization_id: int | None = None,
    for_update: bool = False,
) -> ProductCategory:
    statement = select(ProductCategory).where(
        ProductCategory.id == category_id,
        ProductCategory.tenant_id == tenant_id,
    )
    if organization_id is not None:
        statement = statement.where(ProductCategory.organization_id == organization_id)
    if for_update:
        statement = statement.with_for_update()
    category = await db.scalar(statement)
    if category is None:
        raise _not_found('Product Category')
    return category


async def _get_product(
    db: AsyncSession, *, tenant_id: int, product_id: int, for_update: bool = False
) -> Product:
    statement = select(Product).where(
        Product.id == product_id,
        Product.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    product = await db.scalar(statement)
    if product is None:
        raise _not_found('Product')
    return product


@router.get('/product-categories', response_model=ProductCategoryListResponse)
async def list_product_categories(
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    status_filter: Lifecycle | None = Query(default=None, alias='status'),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductCategoryListResponse:
    await _get_organization(db, tenant_id=context.tenant_id, organization_id=organization_id)
    statement = select(ProductCategory).where(
        ProductCategory.tenant_id == context.tenant_id,
        ProductCategory.organization_id == organization_id,
    )
    if status_filter is not None:
        statement = statement.where(ProductCategory.status == status_filter)
    result = await db.execute(
        statement.order_by(ProductCategory.display_order, ProductCategory.id)
        .limit(limit)
        .offset(offset)
    )
    return ProductCategoryListResponse(
        items=list(result.scalars().all()), limit=limit, offset=offset
    )


@router.post(
    '/product-categories',
    response_model=ProductCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_category(
    payload: ProductCategoryCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCategory:
    await _get_organization(
        db, tenant_id=context.tenant_id, organization_id=payload.organization_id
    )
    if payload.parent_id is not None:
        try:
            await structure.validate_new_category_parent(
                db,
                tenant_id=context.tenant_id,
                organization_id=payload.organization_id,
                parent_id=payload.parent_id,
            )
        except structure.StructureNotFoundError as exc:
            await db.rollback()
            raise _not_found('Parent Product Category') from exc
    category = ProductCategory(
        tenant_id=context.tenant_id,
        organization_id=payload.organization_id,
        parent_id=payload.parent_id,
        name=payload.name,
        display_order=payload.display_order,
        status='ACTIVE',
    )
    db.add(category)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, _CATEGORY_NAME_CONSTRAINT):
            raise _duplicate_category() from exc
        raise
    await db.refresh(category)
    logger.info(
        'Product Category created',
        extra={
            'event': 'product_category_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'organization_id': category.organization_id,
            'product_category_id': category.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return category


@router.patch('/product-categories/{category_id}', response_model=ProductCategoryResponse)
async def update_product_category(
    category_id: Annotated[int, Path(gt=0)],
    payload: ProductCategoryUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCategory:
    updates = payload.model_dump(exclude_unset=True)
    if 'parent_id' in updates:
        try:
            category = await structure.set_category_parent(
                db,
                tenant_id=context.tenant_id,
                category_id=category_id,
                parent_id=updates.pop('parent_id'),
            )
        except structure.StructureNotFoundError as exc:
            await db.rollback()
            raise _not_found(str(exc).removesuffix(' not found')) from exc
        except structure.StructureConflictError as exc:
            await db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    else:
        category = await _get_category(
            db, tenant_id=context.tenant_id, category_id=category_id, for_update=True
        )
    for field, value in updates.items():
        setattr(category, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, _CATEGORY_NAME_CONSTRAINT):
            raise _duplicate_category() from exc
        raise
    await db.refresh(category)
    logger.info(
        'Product Category updated',
        extra={
            'event': 'product_category_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'organization_id': category.organization_id,
            'product_category_id': category.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return category


@router.get('/products', response_model=ProductListResponse)
async def list_products(
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    status_filter: Lifecycle | None = Query(default=None, alias='status'),
    category_id: int | None = Query(default=None, gt=0),
    menu_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductListResponse:
    await _get_organization(db, tenant_id=context.tenant_id, organization_id=organization_id)
    normalized_q = q.strip() if q is not None else None
    if category_id is not None:
        await _get_category(
            db,
            tenant_id=context.tenant_id,
            category_id=category_id,
            organization_id=organization_id,
        )
    statement = product_statement(
        tenant_id=context.tenant_id,
        organization_id=organization_id,
        status=status_filter,
        category_id=category_id,
        menu_id=menu_id,
        query_text=normalized_q,
    )
    if menu_id is not None:
        menu = await db.scalar(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.tenant_id == context.tenant_id,
                Menu.organization_id == organization_id,
            )
        )
        if menu is None:
            raise _not_found('Menu')
    if q is not None:
        if not normalized_q:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Product search text cannot be blank',
            )
    result = await db.execute(statement.order_by(Product.id).limit(limit).offset(offset))
    return ProductListResponse(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('/products', response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Product:
    await _get_organization(
        db, tenant_id=context.tenant_id, organization_id=payload.organization_id
    )
    if payload.category_id is not None:
        await _get_category(
            db,
            tenant_id=context.tenant_id,
            category_id=payload.category_id,
            organization_id=payload.organization_id,
        )
    product = Product(
        tenant_id=context.tenant_id,
        organization_id=payload.organization_id,
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
        status='ACTIVE',
        source='PLATFORM',
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    logger.info(
        'Product created',
        extra={
            'event': 'product_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'organization_id': product.organization_id,
            'product_id': product.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return product


@router.get('/products/{product_id}', response_model=ProductResponse)
async def get_product(
    product_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Product:
    return await _get_product(db, tenant_id=context.tenant_id, product_id=product_id)


@router.patch('/products/{product_id}', response_model=ProductResponse)
async def update_product(
    product_id: Annotated[int, Path(gt=0)],
    payload: ProductUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Product:
    product = await _get_product(
        db, tenant_id=context.tenant_id, product_id=product_id, for_update=True
    )
    updates = payload.model_dump(exclude_unset=True)
    if 'category_id' in updates and updates['category_id'] is not None:
        await _get_category(
            db,
            tenant_id=context.tenant_id,
            category_id=updates['category_id'],
            organization_id=product.organization_id,
        )
    for field, value in updates.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    logger.info(
        'Product updated',
        extra={
            'event': 'product_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'organization_id': product.organization_id,
            'product_id': product.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
        },
    )
    return product
