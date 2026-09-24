"""Reconcile current operational profile permissions for an existing installation."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap_pilot_minimum import (
    OPERATIONAL_PROFILE_PERMISSIONS,
    OPERATIONAL_ROLE_PREFIX,
    operational_role_description,
    operational_role_name,
)
from app.bootstrap_admin import CORE_PERMISSIONS
from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.models import Permission, Role, RolePermission


@dataclass(frozen=True)
class ReconciliationResult:
    tenant_id: int
    profiles_checked: int
    roles_created: int
    permission_links_added: int


async def resolve_operational_tenant_id(session: AsyncSession) -> int:
    """Resolve one existing installation using only canonical operational roles."""
    role_names = tuple(operational_role_name(profile) for profile in OPERATIONAL_PROFILE_PERMISSIONS)
    tenant_ids = set((await session.scalars(
        select(Role.tenant_id).where(Role.name.in_(role_names)).distinct()
    )).all())
    if not tenant_ids:
        raise RuntimeError(
            f'no existing {OPERATIONAL_ROLE_PREFIX} operational roles identify an installation'
        )
    if len(tenant_ids) != 1:
        raise RuntimeError(
            f'{OPERATIONAL_ROLE_PREFIX} operational roles identify multiple installations'
        )
    return tenant_ids.pop()


async def reconcile_operational_profiles(
    session: AsyncSession,
    *,
    tenant_id: int,
) -> ReconciliationResult:
    """Add only missing roles and RolePermission links from the current contract."""
    required_codes = {
        code
        for codes in OPERATIONAL_PROFILE_PERMISSIONS.values()
        for code in codes
    }
    permissions = tuple((await session.scalars(
        select(Permission).where(Permission.code.in_(required_codes)).with_for_update()
    )).all())
    permissions_by_code = {permission.code: permission for permission in permissions}
    missing_codes = required_codes - permissions_by_code.keys()
    unknown_codes = missing_codes - CORE_PERMISSIONS.keys()
    if unknown_codes:
        raise RuntimeError(
            f'canonical permission catalog is incomplete: {sorted(unknown_codes)}'
        )
    for code in sorted(missing_codes):
        permission = Permission(code=code, description=CORE_PERMISSIONS[code])
        session.add(permission)
        await session.flush()
        permissions_by_code[code] = permission

    roles_created = 0
    permission_links_added = 0
    for profile, permission_codes in OPERATIONAL_PROFILE_PERMISSIONS.items():
        role_name = operational_role_name(profile)
        roles = tuple((await session.scalars(
            select(Role).where(
                Role.tenant_id == tenant_id,
                Role.name == role_name,
            ).with_for_update()
        )).all())
        if len(roles) > 1:
            raise RuntimeError(f'duplicate authoritative {profile} roles exist')
        if roles:
            role = roles[0]
            if role.status != 'ACTIVE':
                raise RuntimeError(f'authoritative {profile} role is not active')
        else:
            role = Role(
                tenant_id=tenant_id,
                name=role_name,
                description=operational_role_description(profile),
                status='ACTIVE',
            )
            session.add(role)
            await session.flush()
            roles_created += 1

        required_permission_ids = {
            permissions_by_code[code].id for code in permission_codes
        }
        existing_permission_ids = set((await session.scalars(
            select(RolePermission.permission_id).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id.in_(required_permission_ids),
            ).with_for_update()
        )).all())
        for permission_id in required_permission_ids - existing_permission_ids:
            session.add(RolePermission(role_id=role.id, permission_id=permission_id))
            permission_links_added += 1

    await session.flush()
    return ReconciliationResult(
        tenant_id=tenant_id,
        profiles_checked=len(OPERATIONAL_PROFILE_PERMISSIONS),
        roles_created=roles_created,
        permission_links_added=permission_links_added,
    )


async def _main() -> None:
    database = DatabaseManager(get_settings())
    try:
        async with database.session_factory() as session:
            async with session.begin():
                tenant_id = await resolve_operational_tenant_id(session)
                result = await reconcile_operational_profiles(session, tenant_id=tenant_id)
        output = asdict(result)
        output['status'] = (
            'reconciled'
            if result.roles_created or result.permission_links_added
            else 'already_current'
        )
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    finally:
        await database.dispose()


if __name__ == '__main__':
    asyncio.run(_main())
