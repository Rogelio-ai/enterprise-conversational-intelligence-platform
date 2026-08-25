from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Menu, MenuItem, MenuLocation, MenuSection, Product


def escaped_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def product_statement(
    *,
    tenant_id: int,
    organization_id: int,
    status: str | None = None,
    category_id: int | None = None,
    menu_id: int | None = None,
    query_text: str | None = None,
    active_menu_items_only: bool = False,
) -> Select:
    statement = select(Product).where(
        Product.tenant_id == tenant_id,
        Product.organization_id == organization_id,
    )
    if menu_id is not None:
        statement = statement.join(
            MenuItem,
            (MenuItem.product_id == Product.id)
            & (MenuItem.tenant_id == Product.tenant_id),
        ).where(MenuItem.menu_id == menu_id)
        if active_menu_items_only:
            statement = statement.where(MenuItem.status == 'ACTIVE')
    if status is not None:
        statement = statement.where(Product.status == status)
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if query_text is not None:
        statement = statement.where(
            Product.name.like(f'%{escaped_like(query_text)}%', escape='\\')
        )
    return statement


def menu_statement(
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int | None = None,
    status: str | None = None,
    query_text: str | None = None,
    active_location_assignment_only: bool = False,
) -> Select:
    statement = select(Menu).where(
        Menu.tenant_id == tenant_id,
        Menu.organization_id == organization_id,
    )
    if location_id is not None:
        statement = statement.join(
            MenuLocation,
            (MenuLocation.menu_id == Menu.id) & (MenuLocation.tenant_id == Menu.tenant_id),
        ).where(MenuLocation.location_id == location_id)
        if active_location_assignment_only:
            statement = statement.where(MenuLocation.status == 'ACTIVE')
    if status is not None:
        statement = statement.where(Menu.status == status)
    if query_text is not None:
        statement = statement.where(
            Menu.name.like(f'%{escaped_like(query_text)}%', escape='\\')
        )
    return statement


@dataclass(frozen=True, slots=True)
class MenuSectionRecords:
    section: MenuSection
    items: tuple[tuple[MenuItem, Product], ...]


@dataclass(frozen=True, slots=True)
class MenuGraphRecords:
    menu: Menu
    locations: tuple[MenuLocation, ...]
    sections: tuple[MenuSectionRecords, ...]


async def load_menu_graph(
    db: AsyncSession,
    *,
    tenant_id: int,
    menu_id: int,
    active_only: bool,
) -> MenuGraphRecords | None:
    menu_query = select(Menu).where(Menu.id == menu_id, Menu.tenant_id == tenant_id)
    if active_only:
        menu_query = menu_query.where(Menu.status == 'ACTIVE')
    menu = await db.scalar(menu_query)
    if menu is None:
        return None

    location_query = select(MenuLocation).where(
        MenuLocation.tenant_id == tenant_id,
        MenuLocation.menu_id == menu.id,
    )
    section_query = select(MenuSection).where(
        MenuSection.tenant_id == tenant_id,
        MenuSection.menu_id == menu.id,
    )
    item_query = (
        select(MenuItem, Product)
        .join(
            Product,
            (Product.id == MenuItem.product_id)
            & (Product.tenant_id == MenuItem.tenant_id),
        )
        .where(MenuItem.tenant_id == tenant_id, MenuItem.menu_id == menu.id)
    )
    if active_only:
        location_query = location_query.where(MenuLocation.status == 'ACTIVE')
        section_query = section_query.where(MenuSection.status == 'ACTIVE')
        item_query = item_query.where(MenuItem.status == 'ACTIVE', Product.status == 'ACTIVE')

    locations = tuple(
        (
            await db.execute(location_query.order_by(MenuLocation.id))
        ).scalars().all()
    )
    sections = tuple(
        (
            await db.execute(
                section_query.order_by(MenuSection.display_order, MenuSection.id)
            )
        ).scalars().all()
    )
    item_rows = tuple(
        (
            await db.execute(item_query.order_by(MenuItem.display_order, MenuItem.id))
        ).all()
    )
    items_by_section: dict[int, list[tuple[MenuItem, Product]]] = {}
    for item, product in item_rows:
        items_by_section.setdefault(item.section_id, []).append((item, product))
    return MenuGraphRecords(
        menu=menu,
        locations=locations,
        sections=tuple(
            MenuSectionRecords(
                section=section,
                items=tuple(items_by_section.get(section.id, ())),
            )
            for section in sections
        ),
    )
