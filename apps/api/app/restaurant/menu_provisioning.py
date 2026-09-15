"""Canonical Menu and Location availability provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Location,
    Menu,
    MenuExternalMapping,
    MenuLocation,
    Organization,
)


MENU_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_DUPLICATE_KEY_PATTERN = re.compile(r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE)
_MAPPING_CONSTRAINT = 'uq_menu_external_mapping_source'
_LOCATION_CONSTRAINT = 'uq_menu_locations_tenant_menu_location'


class MenuProvisioningError(ValueError):
    pass


class MenuScopeNotFoundError(MenuProvisioningError):
    pass


class MenuConflictError(MenuProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class MenuProvisioningPlan:
    operation: str
    binding_namespace: str
    menu_key: str
    menu_id: int | None
    menu_location_id: int | None


@dataclass(frozen=True, slots=True)
class MenuProvisioningResult:
    menu: Menu
    menu_location: MenuLocation
    operation: str
    binding_namespace: str
    menu_key: str


def onboarding_binding_namespace(*, contract_version: str, organization_id: int) -> str:
    value = f'ONBOARDING:{contract_version}:ORG:{organization_id}'
    if organization_id <= 0 or len(value) > 128:
        raise MenuProvisioningError('Invalid Menu binding scope')
    return value


def _text(value: str, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise MenuProvisioningError(f'Invalid {field}')
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise MenuProvisioningError(
            f'{field} must contain between 1 and {maximum} characters'
        )
    return normalized


def _status(value: str) -> str:
    if not isinstance(value, str):
        raise MenuProvisioningError('Invalid Menu Location status')
    normalized = value.strip().upper()
    if normalized not in MENU_STATUSES:
        raise MenuProvisioningError('Unsupported Menu Location status')
    return normalized


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


def _translate_integrity_error(exc: IntegrityError) -> None:
    if _is_constraint(exc, _MAPPING_CONSTRAINT):
        raise MenuConflictError(
            'Menu key already resolves inside this Organization binding scope'
        ) from exc
    if _is_constraint(exc, _LOCATION_CONSTRAINT):
        raise MenuConflictError('Menu is already assigned to this Location') from exc
    raise exc


async def _organization(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
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
        raise MenuScopeNotFoundError('Organization not found')
    return organization


async def _location(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
) -> Location:
    location = await db.scalar(select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    ))
    if location is None:
        raise MenuScopeNotFoundError('Location not found')
    return location


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
        raise MenuScopeNotFoundError('Menu not found')
    return menu


async def create_menu(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    name: str, commit: bool = True,
) -> Menu:
    await _organization(db, tenant_id=tenant_id, organization_id=organization_id)
    menu = Menu(
        tenant_id=tenant_id, organization_id=organization_id,
        name=_text(name, field='Menu name', maximum=200), status='ACTIVE',
    )
    db.add(menu)
    if commit:
        await db.commit()
        await db.refresh(menu)
    else:
        await db.flush()
    return menu


async def update_menu(
    db: AsyncSession, *, tenant_id: int, menu_id: int,
    changes: dict[str, object], commit: bool = True,
) -> Menu:
    allowed = {'name', 'status'}
    if not changes or not set(changes) <= allowed:
        raise MenuProvisioningError('Invalid Menu update fields')
    menu = await _menu(
        db, tenant_id=tenant_id, menu_id=menu_id, for_update=True,
    )
    updates = dict(changes)
    if 'name' in updates:
        updates['name'] = _text(
            updates['name'], field='Menu name', maximum=200,
        )
    if 'status' in updates:
        updates['status'] = _status(updates['status'])
    for field, value in updates.items():
        setattr(menu, field, value)
    if commit:
        await db.commit()
        await db.refresh(menu)
    else:
        await db.flush()
    return menu


async def assign_menu_location(
    db: AsyncSession, *, tenant_id: int, menu_id: int, location_id: int,
    commit: bool = True,
) -> MenuLocation:
    menu = await _menu(db, tenant_id=tenant_id, menu_id=menu_id)
    await _location(
        db, tenant_id=tenant_id, organization_id=menu.organization_id,
        location_id=location_id,
    )
    assignment = MenuLocation(
        tenant_id=tenant_id, organization_id=menu.organization_id,
        menu_id=menu.id, location_id=location_id, status='ACTIVE',
    )
    db.add(assignment)
    try:
        if commit:
            await db.commit()
            await db.refresh(assignment)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        _translate_integrity_error(exc)
    return assignment


async def update_menu_location(
    db: AsyncSession, *, tenant_id: int, menu_id: int, location_id: int,
    status: str, commit: bool = True,
) -> MenuLocation:
    await _menu(db, tenant_id=tenant_id, menu_id=menu_id)
    assignment = await db.scalar(select(MenuLocation).where(
        MenuLocation.tenant_id == tenant_id,
        MenuLocation.menu_id == menu_id,
        MenuLocation.location_id == location_id,
    ).with_for_update())
    if assignment is None:
        raise MenuScopeNotFoundError('Menu Location not found')
    assignment.status = _status(status)
    if commit:
        await db.commit()
        await db.refresh(assignment)
    else:
        await db.flush()
    return assignment


async def _mapped_menu(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, for_update: bool = False,
) -> Menu | None:
    statement = select(Menu).join(
        MenuExternalMapping,
        (MenuExternalMapping.menu_id == Menu.id)
        & (MenuExternalMapping.tenant_id == Menu.tenant_id)
        & (MenuExternalMapping.organization_id == Menu.organization_id),
    ).where(
        MenuExternalMapping.tenant_id == tenant_id,
        MenuExternalMapping.organization_id == organization_id,
        MenuExternalMapping.connector_key == binding_namespace,
        MenuExternalMapping.external_menu_id == menu_key,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def resolve_menu_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, menu_key: str, for_update: bool = False,
) -> Menu:
    namespace = _text(
        binding_namespace, field='Menu binding namespace', maximum=128,
    )
    key = _text(menu_key, field='Menu operator key', maximum=200)
    menu = await _mapped_menu(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, menu_key=key, for_update=for_update,
    )
    if menu is None:
        raise MenuScopeNotFoundError('Menu binding not found')
    return menu


def validate_menu_definitions(definitions: tuple[tuple[str, str], ...]) -> None:
    names_by_key: dict[str, str] = {}
    for raw_key, raw_name in definitions:
        key = _text(raw_key, field='Menu operator key', maximum=200)
        name = _text(raw_name, field='Menu name', maximum=200)
        previous = names_by_key.setdefault(key, name)
        if previous != name:
            raise MenuConflictError(
                f'Menu key {key} has conflicting names across Location rows'
            )


async def _assignment(
    db: AsyncSession, *, tenant_id: int, menu_id: int, location_id: int,
) -> MenuLocation | None:
    return await db.scalar(select(MenuLocation).where(
        MenuLocation.tenant_id == tenant_id,
        MenuLocation.menu_id == menu_id,
        MenuLocation.location_id == location_id,
    ))


async def plan_menu(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, menu_key: str,
    name: str, status: str,
) -> MenuProvisioningPlan:
    await _organization(db, tenant_id=tenant_id, organization_id=organization_id)
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    namespace = _text(
        binding_namespace, field='Menu binding namespace', maximum=128,
    )
    key = _text(menu_key, field='Menu operator key', maximum=200)
    normalized_name = _text(name, field='Menu name', maximum=200)
    normalized_status = _status(status)
    menu = await _mapped_menu(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, menu_key=key,
    )
    if menu is None:
        if normalized_status != 'ACTIVE':
            raise MenuConflictError('New Menu Location assignments must be ACTIVE')
        return MenuProvisioningPlan('CREATE', namespace, key, None, None)
    if menu.status != 'ACTIVE':
        raise MenuConflictError(
            'Mapped Menu must be ACTIVE before provisioning Location availability'
        )
    assignment = await _assignment(
        db, tenant_id=tenant_id, menu_id=menu.id, location_id=location_id,
    )
    if assignment is None and normalized_status != 'ACTIVE':
        raise MenuConflictError('New Menu Location assignments must be ACTIVE')
    unchanged = (
        menu.name == normalized_name
        and assignment is not None
        and assignment.status == normalized_status
    )
    return MenuProvisioningPlan(
        'UNCHANGED' if unchanged else 'UPDATE', namespace, key, menu.id,
        None if assignment is None else assignment.id,
    )


async def provision_menu(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, menu_key: str,
    name: str, status: str,
) -> MenuProvisioningResult:
    namespace = _text(
        binding_namespace, field='Menu binding namespace', maximum=128,
    )
    key = _text(menu_key, field='Menu operator key', maximum=200)
    normalized_name = _text(name, field='Menu name', maximum=200)
    normalized_status = _status(status)
    await _organization(
        db, tenant_id=tenant_id, organization_id=organization_id,
        for_update=True,
    )
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    menu = await _mapped_menu(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=namespace, menu_key=key,
    )
    if menu is None:
        if normalized_status != 'ACTIVE':
            raise MenuConflictError('New Menu Location assignments must be ACTIVE')
        menu = Menu(
            tenant_id=tenant_id, organization_id=organization_id,
            name=normalized_name, status='ACTIVE',
        )
        db.add(menu)
        await db.flush()
        db.add(MenuExternalMapping(
            tenant_id=tenant_id, organization_id=organization_id,
            menu_id=menu.id, connector_key=namespace, external_menu_id=key,
        ))
        assignment = MenuLocation(
            tenant_id=tenant_id, organization_id=organization_id,
            menu_id=menu.id, location_id=location_id, status='ACTIVE',
        )
        db.add(assignment)
        operation = 'CREATE'
    else:
        if menu.status != 'ACTIVE':
            raise MenuConflictError(
                'Mapped Menu must be ACTIVE before provisioning Location availability'
            )
        assignment = await _assignment(
            db, tenant_id=tenant_id, menu_id=menu.id, location_id=location_id,
        )
        if assignment is None:
            if normalized_status != 'ACTIVE':
                raise MenuConflictError('New Menu Location assignments must be ACTIVE')
            assignment = MenuLocation(
                tenant_id=tenant_id, organization_id=organization_id,
                menu_id=menu.id, location_id=location_id, status='ACTIVE',
            )
            db.add(assignment)
            operation = 'UPDATE'
        else:
            operation = (
                'UNCHANGED'
                if menu.name == normalized_name
                and assignment.status == normalized_status
                else 'UPDATE'
            )
            assignment.status = normalized_status
        menu.name = normalized_name
    try:
        await db.commit()
        await db.refresh(menu)
        await db.refresh(assignment)
    except IntegrityError as exc:
        await db.rollback()
        _translate_integrity_error(exc)
    return MenuProvisioningResult(menu, assignment, operation, namespace, key)
