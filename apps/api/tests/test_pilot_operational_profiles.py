from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.bootstrap_pilot_minimum import (
    DEMO_MODE,
    OPERATIONAL_PROFILE_PERMISSIONS,
    _staff,
)
from app.db.session import DatabaseManager
from app.models import (
    MembershipLocationGrant,
    MembershipRole,
    Permission,
    Role,
    RolePermission,
)


PASSWORD = 'Test Password 123!'

WORKSPACE_REQUIREMENTS = {
    'HOST': {'location.read', 'resource.read', 'restaurant_service.read'},
    'WAITER': {
        'location.read', 'restaurant_service.read', 'restaurant_order.read',
        'restaurant_check.read', 'operational_request.read',
    },
    'KITCHEN': {'location.read', 'preparation.read'},
    'CASHIER': {
        'location.read', 'resource.read', 'cash_management.read',
        'restaurant_check.read', 'restaurant_payment.read',
    },
    'INVENTORY_MANAGER': {'location.read', 'inventory.read'},
}

UNRELATED_HIGH_VALUE_PERMISSIONS = {
    'HOST': {'tenant.manage', 'operational_request.manage', 'inventory.manage'},
    'WAITER': {'tenant.manage', 'cash_session.manage', 'inventory.manage'},
    'KITCHEN': {'tenant.manage', 'cash_session.manage', 'restaurant_payment.manage'},
    'CASHIER': {'tenant.manage', 'restaurant_service.manage', 'inventory.manage'},
    'INVENTORY_MANAGER': {
        'tenant.manage', 'restaurant_service.manage', 'cash_session.manage',
    },
}


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def test_operational_profiles_match_workspace_contracts_without_admin_escalation() -> None:
    assert set(OPERATIONAL_PROFILE_PERMISSIONS) == set(WORKSPACE_REQUIREMENTS)
    for profile, required in WORKSPACE_REQUIREMENTS.items():
        granted = set(OPERATIONAL_PROFILE_PERMISSIONS[profile])
        assert required <= granted
        assert granted.isdisjoint(UNRELATED_HIGH_VALUE_PERMISSIONS[profile])


def test_canonical_staff_authority_provisions_profiles_idempotently_with_location_scope(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES (%s,%s,'ACTIVE')",
        ('Operational profiles', prefix),
    )
    organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,%s,'ACTIVE')",
        (tenant_id, 'OPS', 'Operational profiles'),
    )
    location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,%s,%s,%s,'ACTIVE')",
        (tenant_id, organization_id, 'OPS', 'Operational profiles', 'America/Mexico_City'),
    )

    async def exercise() -> tuple[dict[str, dict[str, object]], tuple[str, ...]]:
        database = DatabaseManager(integration_settings)
        try:
            async with database.session_factory() as session:
                created: list[str] = []
                async with session.begin():
                    for profile, permissions in OPERATIONAL_PROFILE_PERMISSIONS.items():
                        await _staff(
                            session, tenant_id, location_id, PASSWORD, created,
                            profile, f'{prefix}-{profile.casefold()}@example.test',
                            f'{profile} Test', permissions,
                        )
                    await session.flush()

                replay_created: list[str] = []
                async with session.begin():
                    for profile, permissions in OPERATIONAL_PROFILE_PERMISSIONS.items():
                        await _staff(
                            session, tenant_id, location_id, PASSWORD, replay_created,
                            profile, f'{prefix}-{profile.casefold()}@example.test',
                            f'{profile} Test', permissions,
                        )
                    await session.flush()

                    evidence: dict[str, dict[str, object]] = {}
                    role_prefix = 'DEMO' if DEMO_MODE else 'PREPILOT'
                    for profile in OPERATIONAL_PROFILE_PERMISSIONS:
                        role = await session.scalar(select(Role).where(
                            Role.tenant_id == tenant_id,
                            Role.name == f'{role_prefix}_{profile}',
                        ))
                        assert role is not None
                        permission_codes = set((await session.scalars(
                            select(Permission.code)
                            .join(RolePermission, RolePermission.permission_id == Permission.id)
                            .where(RolePermission.role_id == role.id)
                        )).all())
                        membership_id = await session.scalar(
                            select(MembershipRole.membership_id).where(
                                MembershipRole.tenant_id == tenant_id,
                                MembershipRole.role_id == role.id,
                            )
                        )
                        location_ids = set((await session.scalars(
                            select(MembershipLocationGrant.location_id).where(
                                MembershipLocationGrant.tenant_id == tenant_id,
                                MembershipLocationGrant.membership_id == membership_id,
                            )
                        )).all())
                        evidence[profile] = {
                            'permissions': permission_codes,
                            'location_ids': location_ids,
                        }
                return evidence, tuple(replay_created)
        finally:
            await database.dispose()

    evidence, replay_created = asyncio.run(exercise())

    assert replay_created == ()
    for profile, expected_permissions in OPERATIONAL_PROFILE_PERMISSIONS.items():
        assert evidence[profile] == {
            'permissions': set(expected_permissions),
            'location_ids': {location_id},
        }
