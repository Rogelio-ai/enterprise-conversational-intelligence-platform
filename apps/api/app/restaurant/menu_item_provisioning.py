"""Canonical Menu Item placement provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Menu, MenuItem, MenuSection, Product
from app.restaurant import menu_provisioning, menu_section_provisioning
from app.restaurant.catalog import provisioning as product_provisioning


ITEM_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_DUPLICATE_KEY_PATTERN = re.compile(
    r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE,
)
_ITEM_CONSTRAINT = 'uq_menu_items_tenant_menu_product'


class MenuItemProvisioningError(ValueError):
    pass


class MenuItemScopeNotFoundError(MenuItemProvisioningError):
    pass


class MenuItemConflictError(MenuItemProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class MenuItemProvisioningPlan:
    operation: str
    menu_id: int | None
    section_id: int | None
    product_id: int | None
    menu_item_id: int | None


@dataclass(frozen=True, slots=True)
class MenuItemProvisioningResult:
    menu: Menu
    section: MenuSection
    product: Product
    menu_item: MenuItem
    operation: str


def _display_order(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MenuItemProvisioningError(
            'Menu Item display order must be a non-negative integer'
        )
    return value


def _status(value: object) -> str:
    if not isinstance(value, str):
        raise MenuItemProvisioningError('Invalid Menu Item status')
    normalized = value.strip().upper()
    if normalized not in ITEM_STATUSES:
        raise MenuItemProvisioningError('Unsupported Menu Item status')
    return normalized


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


async def _menu(
    db: AsyncSession, *, tenant_id: int, menu_id: int,
    for_update: bool = False,
) -> Menu:
    statement = select(Menu).where(
        Menu.id == menu_id, Menu.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    menu = await db.scalar(statement)
    if menu is None:
        raise MenuItemScopeNotFoundError('Menu not found')
    return menu


async def _section(
    db: AsyncSession, *, tenant_id: int, menu: Menu, section_id: int,
) -> MenuSection:
    section = await db.scalar(select(MenuSection).where(
        MenuSection.id == section_id,
        MenuSection.tenant_id == tenant_id,
        MenuSection.organization_id == menu.organization_id,
        MenuSection.menu_id == menu.id,
    ))
    if section is None:
        raise MenuItemScopeNotFoundError('Menu Section not found')
    return section


async def _product(
    db: AsyncSession, *, tenant_id: int, menu: Menu, product_id: int,
) -> Product:
    product = await db.scalar(select(Product).where(
        Product.id == product_id,
        Product.tenant_id == tenant_id,
        Product.organization_id == menu.organization_id,
    ))
    if product is None:
        raise MenuItemScopeNotFoundError('Product not found')
    return product


async def _item(
    db: AsyncSession, *, tenant_id: int, menu_id: int, product_id: int,
    for_update: bool = False,
) -> MenuItem | None:
    statement = select(MenuItem).where(
        MenuItem.tenant_id == tenant_id,
        MenuItem.menu_id == menu_id,
        MenuItem.product_id == product_id,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def create_menu_item(
    db: AsyncSession, *, tenant_id: int, menu_id: int, section_id: int,
    product_id: int, display_order: int = 0, status: str = 'ACTIVE',
    commit: bool = True,
) -> MenuItem:
    menu = await _menu(db, tenant_id=tenant_id, menu_id=menu_id)
    section = await _section(
        db, tenant_id=tenant_id, menu=menu, section_id=section_id,
    )
    product = await _product(
        db, tenant_id=tenant_id, menu=menu, product_id=product_id,
    )
    item = MenuItem(
        tenant_id=tenant_id, organization_id=menu.organization_id,
        menu_id=menu.id, section_id=section.id, product_id=product.id,
        display_order=_display_order(display_order), status=_status(status),
    )
    db.add(item)
    try:
        if commit:
            await db.commit()
            await db.refresh(item)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, _ITEM_CONSTRAINT):
            raise MenuItemConflictError(
                'Product is already placed in this Menu'
            ) from exc
        raise
    return item


async def update_menu_item(
    db: AsyncSession, *, tenant_id: int, menu_id: int, menu_item_id: int,
    changes: dict[str, object], commit: bool = True,
) -> MenuItem:
    allowed = {'section_id', 'display_order', 'status'}
    if not changes or not set(changes) <= allowed:
        raise MenuItemProvisioningError('Invalid Menu Item update fields')
    menu = await _menu(db, tenant_id=tenant_id, menu_id=menu_id)
    item = await db.scalar(select(MenuItem).where(
        MenuItem.id == menu_item_id,
        MenuItem.tenant_id == tenant_id,
        MenuItem.menu_id == menu.id,
    ).with_for_update())
    if item is None:
        raise MenuItemScopeNotFoundError('Menu Item not found')
    updates = dict(changes)
    if 'section_id' in updates:
        section_id = updates['section_id']
        if isinstance(section_id, bool) or not isinstance(section_id, int):
            raise MenuItemProvisioningError('Invalid Menu Section identifier')
        section = await _section(
            db, tenant_id=tenant_id, menu=menu, section_id=section_id,
        )
        updates['section_id'] = section.id
    if 'display_order' in updates:
        updates['display_order'] = _display_order(updates['display_order'])
    if 'status' in updates:
        updates['status'] = _status(updates['status'])
    for field, value in updates.items():
        setattr(item, field, value)
    if commit:
        await db.commit()
        await db.refresh(item)
    else:
        await db.flush()
    return item


async def _resolve_dependencies(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str,
    product_key: str, lock_menu: bool = False,
) -> tuple[Menu, MenuSection, Product]:
    try:
        menu = await menu_provisioning.resolve_menu_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, menu_key=menu_key,
            for_update=lock_menu,
        )
        section = await menu_section_provisioning.resolve_menu_section_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, menu_key=menu_key,
            section_key=section_key,
        )
        product = await product_provisioning.resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except (
        menu_provisioning.MenuProvisioningError,
        menu_section_provisioning.MenuSectionProvisioningError,
        product_provisioning.ProductProvisioningError,
    ) as exc:
        raise MenuItemScopeNotFoundError(str(exc)) from exc
    if section.menu_id != menu.id:
        raise MenuItemConflictError('Menu Section does not belong to the selected Menu')
    if product.organization_id != menu.organization_id:
        raise MenuItemConflictError('Product does not belong to the selected Menu scope')
    return menu, section, product


async def resolve_menu_item(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str,
    product_key: str,
) -> MenuItem:
    menu, section, product = await _resolve_dependencies(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, menu_key=menu_key,
        section_key=section_key, product_key=product_key,
    )
    item = await _item(
        db, tenant_id=tenant_id, menu_id=menu.id, product_id=product.id,
    )
    if item is None:
        raise MenuItemScopeNotFoundError('Menu Item not found')
    if item.section_id != section.id:
        raise MenuItemConflictError(
            'Product placement belongs to a different Section in this Menu'
        )
    return item


async def plan_menu_item(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str,
    product_key: str, display_order: int, status: str,
    allow_unresolved_menu: bool = False,
    allow_unresolved_section: bool = False,
    allow_unresolved_product: bool = False,
) -> MenuItemProvisioningPlan:
    normalized_order = _display_order(display_order)
    normalized_status = _status(status)
    menu: Menu | None = None
    section: MenuSection | None = None
    product: Product | None = None
    try:
        menu = await menu_provisioning.resolve_menu_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, menu_key=menu_key,
        )
    except menu_provisioning.MenuProvisioningError as exc:
        if not allow_unresolved_menu:
            raise MenuItemScopeNotFoundError(str(exc)) from exc
    try:
        section = await menu_section_provisioning.resolve_menu_section_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, menu_key=menu_key,
            section_key=section_key,
        )
    except menu_section_provisioning.MenuSectionProvisioningError as exc:
        if not allow_unresolved_section:
            raise MenuItemScopeNotFoundError(str(exc)) from exc
    try:
        product = await product_provisioning.resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except product_provisioning.ProductProvisioningError as exc:
        if not allow_unresolved_product:
            raise MenuItemScopeNotFoundError(str(exc)) from exc
    if menu is None or section is None or product is None:
        return MenuItemProvisioningPlan(
            'CREATE', None if menu is None else menu.id,
            None if section is None else section.id,
            None if product is None else product.id, None,
        )
    if section.menu_id != menu.id:
        raise MenuItemConflictError('Menu Section does not belong to the selected Menu')
    if product.organization_id != menu.organization_id:
        raise MenuItemConflictError('Product does not belong to the selected Menu scope')
    item = await _item(
        db, tenant_id=tenant_id, menu_id=menu.id, product_id=product.id,
    )
    if item is None:
        operation, item_id = 'CREATE', None
    else:
        unchanged = (
            item.section_id == section.id
            and item.display_order == normalized_order
            and item.status == normalized_status
        )
        operation, item_id = ('UNCHANGED' if unchanged else 'UPDATE'), item.id
    return MenuItemProvisioningPlan(
        operation, menu.id, section.id, product.id, item_id,
    )


async def provision_menu_item(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str,
    product_key: str, display_order: int, status: str,
) -> MenuItemProvisioningResult:
    normalized_order = _display_order(display_order)
    normalized_status = _status(status)
    menu, section, product = await _resolve_dependencies(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, menu_key=menu_key,
        section_key=section_key, product_key=product_key, lock_menu=True,
    )
    menu_id = menu.id
    section_id = section.id
    product_id = product.id
    item = await _item(
        db, tenant_id=tenant_id, menu_id=menu_id, product_id=product_id,
    )
    if item is None:
        item = MenuItem(
            tenant_id=tenant_id, organization_id=organization_id,
            menu_id=menu_id, section_id=section_id, product_id=product_id,
            display_order=normalized_order, status=normalized_status,
        )
        db.add(item)
        operation = 'CREATE'
    else:
        operation = (
            'UNCHANGED'
            if item.section_id == section_id
            and item.display_order == normalized_order
            and item.status == normalized_status
            else 'UPDATE'
        )
        item.section_id = section_id
        item.display_order = normalized_order
        item.status = normalized_status
    try:
        await db.commit()
        await db.refresh(item)
    except IntegrityError as exc:
        await db.rollback()
        if not _is_constraint(exc, _ITEM_CONSTRAINT):
            raise
        winner = await _item(
            db, tenant_id=tenant_id, menu_id=menu_id,
            product_id=product_id, for_update=True,
        )
        if winner is None:
            raise MenuItemConflictError(
                'Product placement could not be reconciled'
            ) from exc
        operation = (
            'UNCHANGED'
            if winner.section_id == section_id
            and winner.display_order == normalized_order
            and winner.status == normalized_status
            else 'UPDATE'
        )
        winner.section_id = section_id
        winner.display_order = normalized_order
        winner.status = normalized_status
        await db.commit()
        await db.refresh(winner)
        item = winner
    return MenuItemProvisioningResult(menu, section, product, item, operation)
