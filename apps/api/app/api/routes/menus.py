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
from app.models import (
    Location,
    Menu,
    MenuItem,
    MenuLocation,
    MenuSection,
    Organization,
    Product,
)


Lifecycle = Literal['ACTIVE', 'INACTIVE']
router = APIRouter(prefix='/menus', tags=['menus'])
logger = logging.getLogger('ecip.menus')
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)


class MenuCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    organization_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)


class MenuUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'MenuUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Menu fields cannot be null')
        return self


class MenuResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class MenuListResponse(BaseModel):
    items: list[MenuResponse]
    limit: int
    offset: int


class MenuLocationCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    location_id: int = Field(gt=0)


class StatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'StatusUpdateRequest':
        if self.model_fields_set != {'status'} or self.status is None:
            raise ValueError('A non-null status is required')
        return self


class MenuLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    menu_id: int
    location_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class MenuSectionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(min_length=1, max_length=200)
    display_order: int = Field(default=0, ge=0)


class MenuSectionUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'MenuSectionUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Menu Section fields cannot be null')
        return self


class MenuSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    menu_id: int
    name: str
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class MenuItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    section_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    display_order: int = Field(default=0, ge=0)
    status: Lifecycle = 'ACTIVE'


class MenuItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    section_id: int | None = Field(default=None, gt=0)
    display_order: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'MenuItemUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Menu Item fields cannot be null')
        return self


class MenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    menu_id: int
    section_id: int
    product_id: int
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class MenuProductSummary(BaseModel):
    id: int
    category_id: int | None
    name: str
    description: str | None
    status: str


class MenuItemDetailResponse(MenuItemResponse):
    product: MenuProductSummary


class MenuSectionDetailResponse(MenuSectionResponse):
    items: list[MenuItemDetailResponse]


class MenuDetailResponse(MenuResponse):
    locations: list[MenuLocationResponse]
    sections: list[MenuSectionDetailResponse]


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{entity} not found')


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


def _escaped_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


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


async def _get_menu(
    db: AsyncSession, *, tenant_id: int, menu_id: int, for_update: bool = False
) -> Menu:
    statement = select(Menu).where(Menu.id == menu_id, Menu.tenant_id == tenant_id)
    if for_update:
        statement = statement.with_for_update()
    menu = await db.scalar(statement)
    if menu is None:
        raise _not_found('Menu')
    return menu


async def _get_location(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    organization_id: int | None = None,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
    )
    if organization_id is not None:
        statement = statement.where(Location.organization_id == organization_id)
    location = await db.scalar(statement)
    if location is None:
        raise _not_found('Location')
    return location


async def _get_section(
    db: AsyncSession,
    *,
    tenant_id: int,
    menu_id: int,
    section_id: int,
    for_update: bool = False,
) -> MenuSection:
    statement = select(MenuSection).where(
        MenuSection.id == section_id,
        MenuSection.menu_id == menu_id,
        MenuSection.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    section = await db.scalar(statement)
    if section is None:
        raise _not_found('Menu Section')
    return section


async def _get_item(
    db: AsyncSession,
    *,
    tenant_id: int,
    menu_id: int,
    item_id: int,
    for_update: bool = False,
) -> MenuItem:
    statement = select(MenuItem).where(
        MenuItem.id == item_id,
        MenuItem.menu_id == menu_id,
        MenuItem.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    item = await db.scalar(statement)
    if item is None:
        raise _not_found('Menu Item')
    return item


def _log_mutation(
    event: str,
    operation: str,
    context: AuthenticatedContext,
    menu: Menu,
    **identifiers: int,
) -> None:
    logger.info(
        event.replace('_', ' ').capitalize(),
        extra={
            'event': event,
            'operation': operation,
            'tenant_id': context.tenant_id,
            'organization_id': menu.organization_id,
            'menu_id': menu.id,
            'user_id': context.user_id,
            'correlation_id': get_correlation_id(),
            **identifiers,
        },
    )


@router.get('', response_model=MenuListResponse)
async def list_menus(
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    location_id: int | None = Query(default=None, gt=0),
    status_filter: Lifecycle | None = Query(default=None, alias='status'),
    q: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MenuListResponse:
    await _get_organization(db, tenant_id=context.tenant_id, organization_id=organization_id)
    statement = select(Menu).where(
        Menu.tenant_id == context.tenant_id,
        Menu.organization_id == organization_id,
    )
    if location_id is not None:
        await _get_location(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            organization_id=organization_id,
        )
        statement = statement.join(
            MenuLocation,
            (MenuLocation.menu_id == Menu.id) & (MenuLocation.tenant_id == Menu.tenant_id),
        ).where(MenuLocation.location_id == location_id)
    if status_filter is not None:
        statement = statement.where(Menu.status == status_filter)
    if q is not None:
        normalized_q = q.strip()
        if not normalized_q:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Menu search text cannot be blank',
            )
        statement = statement.where(Menu.name.like(f'%{_escaped_like(normalized_q)}%', escape='\\'))
    result = await db.execute(statement.order_by(Menu.id).limit(limit).offset(offset))
    return MenuListResponse(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('', response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
async def create_menu(
    payload: MenuCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Menu:
    await _get_organization(
        db, tenant_id=context.tenant_id, organization_id=payload.organization_id
    )
    menu = Menu(
        tenant_id=context.tenant_id,
        organization_id=payload.organization_id,
        name=payload.name,
        status='ACTIVE',
    )
    db.add(menu)
    await db.commit()
    await db.refresh(menu)
    _log_mutation('menu_created', 'create', context, menu)
    return menu


@router.get('/{menu_id}', response_model=MenuDetailResponse)
async def get_menu(
    menu_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuDetailResponse:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    location_result = await db.execute(
        select(MenuLocation)
        .where(MenuLocation.tenant_id == context.tenant_id, MenuLocation.menu_id == menu.id)
        .order_by(MenuLocation.id)
    )
    section_result = await db.execute(
        select(MenuSection)
        .where(MenuSection.tenant_id == context.tenant_id, MenuSection.menu_id == menu.id)
        .order_by(MenuSection.display_order, MenuSection.id)
    )
    item_result = await db.execute(
        select(MenuItem, Product)
        .join(
            Product,
            (Product.id == MenuItem.product_id)
            & (Product.tenant_id == MenuItem.tenant_id),
        )
        .where(MenuItem.tenant_id == context.tenant_id, MenuItem.menu_id == menu.id)
        .order_by(MenuItem.display_order, MenuItem.id)
    )
    items_by_section: dict[int, list[MenuItemDetailResponse]] = {}
    for item, product in item_result.all():
        detail = MenuItemDetailResponse(
            **MenuItemResponse.model_validate(item).model_dump(),
            product=MenuProductSummary(
                id=product.id,
                category_id=product.category_id,
                name=product.name,
                description=product.description,
                status=product.status,
            ),
        )
        items_by_section.setdefault(item.section_id, []).append(detail)
    sections = [
        MenuSectionDetailResponse(
            **MenuSectionResponse.model_validate(section).model_dump(),
            items=items_by_section.get(section.id, []),
        )
        for section in section_result.scalars().all()
    ]
    return MenuDetailResponse(
        **MenuResponse.model_validate(menu).model_dump(),
        locations=[
            MenuLocationResponse.model_validate(location)
            for location in location_result.scalars().all()
        ],
        sections=sections,
    )


@router.patch('/{menu_id}', response_model=MenuResponse)
async def update_menu(
    menu_id: Annotated[int, Path(gt=0)],
    payload: MenuUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Menu:
    menu = await _get_menu(
        db, tenant_id=context.tenant_id, menu_id=menu_id, for_update=True
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(menu, field, value)
    await db.commit()
    await db.refresh(menu)
    _log_mutation('menu_updated', 'update', context, menu)
    return menu


@router.post(
    '/{menu_id}/locations',
    response_model=MenuLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_menu_location(
    menu_id: Annotated[int, Path(gt=0)],
    payload: MenuLocationCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuLocation:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    await _get_location(
        db,
        tenant_id=context.tenant_id,
        location_id=payload.location_id,
        organization_id=menu.organization_id,
    )
    assignment = MenuLocation(
        tenant_id=context.tenant_id,
        organization_id=menu.organization_id,
        menu_id=menu.id,
        location_id=payload.location_id,
        status='ACTIVE',
    )
    db.add(assignment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, 'uq_menu_locations_tenant_menu_location'):
            raise _conflict('Menu is already assigned to this Location') from exc
        raise
    await db.refresh(assignment)
    _log_mutation(
        'menu_location_updated',
        'assign',
        context,
        menu,
        menu_location_id=assignment.id,
        location_id=assignment.location_id,
    )
    return assignment


@router.patch('/{menu_id}/locations/{location_id}', response_model=MenuLocationResponse)
async def update_menu_location(
    menu_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Path(gt=0)],
    payload: StatusUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuLocation:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    assignment = await db.scalar(
        select(MenuLocation)
        .where(
            MenuLocation.tenant_id == context.tenant_id,
            MenuLocation.menu_id == menu.id,
            MenuLocation.location_id == location_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise _not_found('Menu Location')
    assignment.status = payload.status
    await db.commit()
    await db.refresh(assignment)
    _log_mutation(
        'menu_location_updated',
        'update',
        context,
        menu,
        menu_location_id=assignment.id,
        location_id=assignment.location_id,
    )
    return assignment


@router.post(
    '/{menu_id}/sections',
    response_model=MenuSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_section(
    menu_id: Annotated[int, Path(gt=0)],
    payload: MenuSectionCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuSection:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    section = MenuSection(
        tenant_id=context.tenant_id,
        organization_id=menu.organization_id,
        menu_id=menu.id,
        name=payload.name,
        display_order=payload.display_order,
        status='ACTIVE',
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    _log_mutation(
        'menu_section_created',
        'create',
        context,
        menu,
        menu_section_id=section.id,
    )
    return section


@router.patch('/{menu_id}/sections/{section_id}', response_model=MenuSectionResponse)
async def update_menu_section(
    menu_id: Annotated[int, Path(gt=0)],
    section_id: Annotated[int, Path(gt=0)],
    payload: MenuSectionUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuSection:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    section = await _get_section(
        db,
        tenant_id=context.tenant_id,
        menu_id=menu.id,
        section_id=section_id,
        for_update=True,
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    await db.commit()
    await db.refresh(section)
    _log_mutation(
        'menu_section_updated',
        'update',
        context,
        menu,
        menu_section_id=section.id,
    )
    return section


@router.post(
    '/{menu_id}/items',
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_item(
    menu_id: Annotated[int, Path(gt=0)],
    payload: MenuItemCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuItem:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    await _get_section(
        db,
        tenant_id=context.tenant_id,
        menu_id=menu.id,
        section_id=payload.section_id,
    )
    product = await db.scalar(
        select(Product).where(
            Product.id == payload.product_id,
            Product.tenant_id == context.tenant_id,
            Product.organization_id == menu.organization_id,
        )
    )
    if product is None:
        raise _not_found('Product')
    item = MenuItem(
        tenant_id=context.tenant_id,
        organization_id=menu.organization_id,
        menu_id=menu.id,
        section_id=payload.section_id,
        product_id=payload.product_id,
        display_order=payload.display_order,
        status=payload.status,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, 'uq_menu_items_tenant_menu_product'):
            raise _conflict('Product is already placed in this Menu') from exc
        raise
    await db.refresh(item)
    _log_mutation('menu_item_created', 'create', context, menu, menu_item_id=item.id)
    return item


@router.patch('/{menu_id}/items/{item_id}', response_model=MenuItemResponse)
async def update_menu_item(
    menu_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
    payload: MenuItemUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('menu.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuItem:
    menu = await _get_menu(db, tenant_id=context.tenant_id, menu_id=menu_id)
    item = await _get_item(
        db,
        tenant_id=context.tenant_id,
        menu_id=menu.id,
        item_id=item_id,
        for_update=True,
    )
    updates = payload.model_dump(exclude_unset=True)
    if 'section_id' in updates:
        await _get_section(
            db,
            tenant_id=context.tenant_id,
            menu_id=menu.id,
            section_id=updates['section_id'],
        )
    for field, value in updates.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    _log_mutation('menu_item_updated', 'update', context, menu, menu_item_id=item.id)
    return item
