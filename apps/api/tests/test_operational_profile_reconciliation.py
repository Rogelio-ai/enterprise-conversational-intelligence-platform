from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.bootstrap_pilot_minimum import (
    OPERATIONAL_PROFILE_PERMISSIONS,
    operational_role_name,
)
from app.bootstrap_admin import CORE_PERMISSIONS
from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.models import Permission, Role, RolePermission
from app.reconcile_operational_profiles import reconcile_operational_profiles


PASSWORD = 'Test Password 123!'


def test_every_operational_permission_has_canonical_catalog_authority() -> None:
    required = {
        code
        for permission_codes in OPERATIONAL_PROFILE_PERMISSIONS.values()
        for code in permission_codes
    }
    assert required <= CORE_PERMISSIONS.keys()


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _rows(connection, statement: str, parameters=()) -> tuple[tuple[object, ...], ...]:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return tuple(tuple(row.values()) for row in cursor.fetchall())


def _scope(connection, prefix: str) -> tuple[int, int, int]:
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES (%s,%s,'ACTIVE')",
        ('Profile reconciliation', prefix),
    )
    organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,%s,'ACTIVE')",
        (tenant_id, 'OPS', 'Profile reconciliation'),
    )
    location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,%s,%s,%s,'ACTIVE')",
        (tenant_id, organization_id, 'OPS', 'Profile reconciliation', 'America/Mexico_City'),
    )
    return tenant_id, organization_id, location_id


def _role(connection, tenant_id: int, profile: str, status: str = 'ACTIVE') -> int:
    return _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, operational_role_name(profile), f'{profile} fixture', status),
    )


def _grant_permissions(connection, role_id: int, permission_codes: tuple[str, ...]) -> None:
    for code in permission_codes:
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id,permission_id) '
            'SELECT %s,id FROM permissions WHERE code=%s',
            (role_id, code),
        )


def test_reconciliation_repairs_stale_waiter_and_preserves_unrelated_state(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id, organization_id, location_id = _scope(connection, prefix)
    waiter_role_id = _role(connection, tenant_id, 'WAITER')
    stale_waiter_permissions = tuple(
        code for code in OPERATIONAL_PROFILE_PERMISSIONS['WAITER']
        if code not in {'location.read', 'operational_request.read'}
    )
    _grant_permissions(connection, waiter_role_id, stale_waiter_permissions)

    user_id = _execute(
        connection,
        "INSERT INTO users (email,password_hash,display_name,status) "
        "VALUES (%s,%s,%s,'ACTIVE')",
        (f'{prefix}@example.test', hash_password(PASSWORD), 'Existing waiter'),
    )
    membership_id = _execute(
        connection,
        "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')",
        (tenant_id, user_id),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, waiter_role_id),
    )
    _execute(
        connection,
        'INSERT INTO membership_location_grants (tenant_id,membership_id,location_id) '
        'VALUES (%s,%s,%s)',
        (tenant_id, membership_id, location_id),
    )
    executor_id = _execute(
        connection,
        'INSERT INTO location_payment_executor_configurations '
        '(tenant_id,organization_id,location_id,executor_key,display_name,adapter_kind,'
        'topology,status,credential_binding,selection_priority) '
        "VALUES (%s,%s,%s,%s,%s,%s,'EXTERNAL','ACTIVE',%s,100)",
        (
            tenant_id, organization_id, location_id, f'{prefix}-conekta', 'Conekta TEST',
            'conekta', f'{prefix}-credential',
        ),
    )
    membership_before = _rows(
        connection,
        'SELECT id,tenant_id,user_id,status FROM tenant_memberships WHERE tenant_id=%s',
        (tenant_id,),
    )
    roles_before = _rows(
        connection,
        'SELECT tenant_id,membership_id,role_id FROM membership_roles WHERE tenant_id=%s',
        (tenant_id,),
    )
    grants_before = _rows(
        connection,
        'SELECT tenant_id,membership_id,location_id FROM membership_location_grants '
        'WHERE tenant_id=%s',
        (tenant_id,),
    )

    async def exercise():
        database = DatabaseManager(integration_settings)
        try:
            async with database.session_factory() as session:
                async with session.begin():
                    first = await reconcile_operational_profiles(session, tenant_id=tenant_id)
                async with session.begin():
                    second = await reconcile_operational_profiles(session, tenant_id=tenant_id)
                async with session.begin():
                    evidence = {}
                    for profile, expected in OPERATIONAL_PROFILE_PERMISSIONS.items():
                        role = await session.scalar(select(Role).where(
                            Role.tenant_id == tenant_id,
                            Role.name == operational_role_name(profile),
                        ))
                        assert role is not None
                        actual = set((await session.scalars(
                            select(Permission.code)
                            .join(RolePermission, RolePermission.permission_id == Permission.id)
                            .where(RolePermission.role_id == role.id)
                        )).all())
                        evidence[profile] = (set(expected), actual)
                return first, second, evidence
        finally:
            await database.dispose()

    first, second, evidence = asyncio.run(exercise())

    assert first.profiles_checked == 5
    assert first.roles_created == 4
    assert first.permission_links_added > 2
    assert second.permission_links_added == 0
    assert second.roles_created == 0
    for expected, actual in evidence.values():
        assert expected <= actual
        assert 'tenant.manage' not in actual
    assert set(stale_waiter_permissions) <= evidence['WAITER'][1]
    assert {'location.read', 'operational_request.read'} <= evidence['WAITER'][1]
    assert _rows(
        connection,
        'SELECT id,tenant_id,user_id,status FROM tenant_memberships WHERE tenant_id=%s',
        (tenant_id,),
    ) == membership_before
    assert _rows(
        connection,
        'SELECT tenant_id,membership_id,role_id FROM membership_roles WHERE tenant_id=%s',
        (tenant_id,),
    ) == roles_before
    assert _rows(
        connection,
        'SELECT tenant_id,membership_id,location_id FROM membership_location_grants '
        'WHERE tenant_id=%s',
        (tenant_id,),
    ) == grants_before
    assert _rows(
        connection,
        'SELECT status,credential_binding FROM location_payment_executor_configurations '
        'WHERE id=%s',
        (executor_id,),
    ) == (('ACTIVE', f'{prefix}-credential'),)


def test_reconciliation_rolls_back_all_changes_on_controlled_failure(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id, _, _ = _scope(connection, prefix)
    host_role_id = _role(connection, tenant_id, 'HOST')
    _role(connection, tenant_id, 'CASHIER', status='INACTIVE')

    async def exercise() -> None:
        database = DatabaseManager(integration_settings)
        try:
            async with database.session_factory() as session:
                with pytest.raises(RuntimeError, match='CASHIER role is not active'):
                    async with session.begin():
                        await reconcile_operational_profiles(session, tenant_id=tenant_id)
        finally:
            await database.dispose()

    asyncio.run(exercise())

    assert _rows(
        connection,
        'SELECT permission_id FROM role_permissions WHERE role_id=%s',
        (host_role_id,),
    ) == ()
    assert _rows(
        connection,
        'SELECT name FROM roles WHERE tenant_id=%s AND name=%s',
        (tenant_id, operational_role_name('KITCHEN')),
    ) == ()
