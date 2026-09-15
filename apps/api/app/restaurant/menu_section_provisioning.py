"""Canonical Menu Section provisioning and workbook binding authority."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Menu, MenuSection, MenuSectionExternalMapping
from app.restaurant import menu_provisioning


SECTION_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_DUPLICATE_KEY_PATTERN = re.compile(
    r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE,
)
_MAPPING_CONSTRAINT = 'uq_menu_section_external_mapping_source'


class MenuSectionProvisioningError(ValueError):
    pass


class MenuSectionScopeNotFoundError(MenuSectionProvisioningError):
    pass


class MenuSectionConflictError(MenuSectionProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class MenuSectionProvisioningPlan:
    operation: str
    binding_namespace: str
    menu_key: str
    section_key: str
    menu_id: int | None
    section_id: int | None


@dataclass(frozen=True, slots=True)
class MenuSectionProvisioningResult:
    menu: Menu
    section: MenuSection
    operation: str
    binding_namespace: str
    menu_key: str
    section_key: str


def _text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise MenuSectionProvisioningError(f'Invalid {field}')
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise MenuSectionProvisioningError(
            f'{field} must contain between 1 and {maximum} characters'
        )
    return normalized


def _display_order(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MenuSectionProvisioningError(
            'Menu Section display order must be a non-negative integer'
        )
    return value


def _status(value: object) -> str:
    if not isinstance(value, str):
        raise MenuSectionProvisioningError('Invalid Menu Section status')
    normalized = value.strip().upper()
    if normalized not in SECTION_STATUSES:
        raise MenuSectionProvisioningError('Unsupported Menu Section status')
    return normalized


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


def _translate_integrity_error(exc: IntegrityError) -> None:
    if _is_constraint(exc, _MAPPING_CONSTRAINT):
        raise MenuSectionConflictError(
            'Section key already resolves inside this Menu binding scope'
        ) from exc
    raise exc


async def _menu(
    db: AsyncSession, *, tenant_id: int, menu_id: int,
    organization_id: int | None = None, for_update: bool = False,
) -> Menu:
    statement = select(Menu).where(
        Menu.id == menu_id, Menu.tenant_id == tenant_id,
    )
    if organization_id is not None:
        statement = statement.where(Menu.organization_id == organization_id)
    if for_update:
        statement = statement.with_for_update()
    menu = await db.scalar(statement)
    if menu is None:
        raise MenuSectionScopeNotFoundError('Menu not found')
    return menu


async def _section(
    db: AsyncSession, *, tenant_id: int, menu_id: int, section_id: int,
    for_update: bool = False,
) -> MenuSection:
    statement = select(MenuSection).where(
        MenuSection.id == section_id,
        MenuSection.tenant_id == tenant_id,
        MenuSection.menu_id == menu_id,
    )
    if for_update:
        statement = statement.with_for_update()
    section = await db.scalar(statement)
    if section is None:
        raise MenuSectionScopeNotFoundError('Menu Section not found')
    return section


async def create_menu_section(
    db: AsyncSession, *, tenant_id: int, menu_id: int, name: str,
    display_order: int = 0, commit: bool = True,
) -> MenuSection:
    menu = await _menu(db, tenant_id=tenant_id, menu_id=menu_id)
    section = MenuSection(
        tenant_id=tenant_id, organization_id=menu.organization_id,
        menu_id=menu.id,
        name=_text(name, field='Menu Section name', maximum=200),
        display_order=_display_order(display_order), status='ACTIVE',
    )
    db.add(section)
    if commit:
        await db.commit()
        await db.refresh(section)
    else:
        await db.flush()
    return section


async def update_menu_section(
    db: AsyncSession, *, tenant_id: int, menu_id: int, section_id: int,
    changes: dict[str, object], commit: bool = True,
) -> MenuSection:
    allowed = {'name', 'display_order', 'status'}
    if not changes or not set(changes) <= allowed:
        raise MenuSectionProvisioningError('Invalid Menu Section update fields')
    await _menu(db, tenant_id=tenant_id, menu_id=menu_id)
    section = await _section(
        db, tenant_id=tenant_id, menu_id=menu_id, section_id=section_id,
        for_update=True,
    )
    updates = dict(changes)
    if 'name' in updates:
        updates['name'] = _text(
            updates['name'], field='Menu Section name', maximum=200,
        )
    if 'display_order' in updates:
        updates['display_order'] = _display_order(updates['display_order'])
    if 'status' in updates:
        updates['status'] = _status(updates['status'])
    for field, value in updates.items():
        setattr(section, field, value)
    if commit:
        await db.commit()
        await db.refresh(section)
    else:
        await db.flush()
    return section


async def _resolve_menu(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, for_update: bool = False,
) -> Menu:
    try:
        resolved = await menu_provisioning.resolve_menu_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, menu_key=menu_key,
            for_update=for_update,
        )
    except menu_provisioning.MenuProvisioningError as exc:
        raise MenuSectionScopeNotFoundError(str(exc)) from exc
    return resolved


async def _mapped_section(
    db: AsyncSession, *, tenant_id: int, organization_id: int, menu_id: int,
    binding_namespace: str, section_key: str,
) -> MenuSection | None:
    return await db.scalar(select(MenuSection).join(
        MenuSectionExternalMapping,
        (MenuSectionExternalMapping.section_id == MenuSection.id)
        & (MenuSectionExternalMapping.menu_id == MenuSection.menu_id)
        & (MenuSectionExternalMapping.tenant_id == MenuSection.tenant_id)
        & (
            MenuSectionExternalMapping.organization_id
            == MenuSection.organization_id
        ),
    ).where(
        MenuSectionExternalMapping.tenant_id == tenant_id,
        MenuSectionExternalMapping.organization_id == organization_id,
        MenuSectionExternalMapping.menu_id == menu_id,
        MenuSectionExternalMapping.connector_key == binding_namespace,
        MenuSectionExternalMapping.external_section_id == section_key,
    ))


async def resolve_menu_section_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str,
) -> MenuSection:
    namespace = _text(
        binding_namespace, field='Menu Section binding namespace', maximum=128,
    )
    normalized_menu_key = _text(
        menu_key, field='Menu operator key', maximum=200,
    )
    normalized_section_key = _text(
        section_key, field='Menu Section operator key', maximum=200,
    )
    menu = await _resolve_menu(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, menu_key=normalized_menu_key,
    )
    section = await _mapped_section(
        db, tenant_id=tenant_id, organization_id=organization_id,
        menu_id=menu.id, binding_namespace=namespace,
        section_key=normalized_section_key,
    )
    if section is None:
        raise MenuSectionScopeNotFoundError('Menu Section binding not found')
    return section


async def plan_menu_section(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str, name: str,
    display_order: int, status: str, allow_unresolved_menu: bool = False,
) -> MenuSectionProvisioningPlan:
    namespace = _text(
        binding_namespace, field='Menu Section binding namespace', maximum=128,
    )
    normalized_menu_key = _text(
        menu_key, field='Menu operator key', maximum=200,
    )
    normalized_section_key = _text(
        section_key, field='Menu Section operator key', maximum=200,
    )
    normalized_name = _text(name, field='Menu Section name', maximum=200)
    normalized_order = _display_order(display_order)
    normalized_status = _status(status)
    try:
        menu = await _resolve_menu(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=namespace, menu_key=normalized_menu_key,
        )
    except MenuSectionScopeNotFoundError:
        if not allow_unresolved_menu:
            raise
        if normalized_status != 'ACTIVE':
            raise MenuSectionConflictError('New Menu Sections must be ACTIVE')
        return MenuSectionProvisioningPlan(
            'CREATE', namespace, normalized_menu_key,
            normalized_section_key, None, None,
        )
    section = await _mapped_section(
        db, tenant_id=tenant_id, organization_id=organization_id,
        menu_id=menu.id, binding_namespace=namespace,
        section_key=normalized_section_key,
    )
    if section is None:
        if normalized_status != 'ACTIVE':
            raise MenuSectionConflictError('New Menu Sections must be ACTIVE')
        return MenuSectionProvisioningPlan(
            'CREATE', namespace, normalized_menu_key,
            normalized_section_key, menu.id, None,
        )
    unchanged = (
        section.name == normalized_name
        and section.display_order == normalized_order
        and section.status == normalized_status
    )
    return MenuSectionProvisioningPlan(
        'UNCHANGED' if unchanged else 'UPDATE', namespace,
        normalized_menu_key, normalized_section_key, menu.id, section.id,
    )


async def provision_menu_section(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, section_key: str, name: str,
    display_order: int, status: str,
) -> MenuSectionProvisioningResult:
    namespace = _text(
        binding_namespace, field='Menu Section binding namespace', maximum=128,
    )
    normalized_menu_key = _text(
        menu_key, field='Menu operator key', maximum=200,
    )
    normalized_section_key = _text(
        section_key, field='Menu Section operator key', maximum=200,
    )
    normalized_name = _text(name, field='Menu Section name', maximum=200)
    normalized_order = _display_order(display_order)
    normalized_status = _status(status)
    menu = await _resolve_menu(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, menu_key=normalized_menu_key,
        for_update=True,
    )
    section = await _mapped_section(
        db, tenant_id=tenant_id, organization_id=organization_id,
        menu_id=menu.id, binding_namespace=namespace,
        section_key=normalized_section_key,
    )
    if section is None:
        if normalized_status != 'ACTIVE':
            raise MenuSectionConflictError('New Menu Sections must be ACTIVE')
        section = MenuSection(
            tenant_id=tenant_id, organization_id=organization_id,
            menu_id=menu.id, name=normalized_name,
            display_order=normalized_order, status='ACTIVE',
        )
        db.add(section)
        await db.flush()
        db.add(MenuSectionExternalMapping(
            tenant_id=tenant_id, organization_id=organization_id,
            menu_id=menu.id, section_id=section.id,
            connector_key=namespace,
            external_section_id=normalized_section_key,
        ))
        operation = 'CREATE'
    else:
        operation = (
            'UNCHANGED'
            if section.name == normalized_name
            and section.display_order == normalized_order
            and section.status == normalized_status
            else 'UPDATE'
        )
        section.name = normalized_name
        section.display_order = normalized_order
        section.status = normalized_status
    try:
        await db.commit()
        await db.refresh(menu)
        await db.refresh(section)
    except IntegrityError as exc:
        await db.rollback()
        _translate_integrity_error(exc)
    return MenuSectionProvisioningResult(
        menu, section, operation, namespace,
        normalized_menu_key, normalized_section_key,
    )
