from __future__ import annotations

import asyncio

import pytest

from app.bootstrap_admin import BootstrapInput, bootstrap_admin
from app.identity.permission_catalog import (
    ADMIN_BOOTSTRAP_PERMISSION_CODES,
    CANONICAL_PERMISSIONS,
    PermissionCatalogConflictError,
    initialize_permission_catalog,
)
from test_auth_foundation import PASSWORD


BOOTSTRAP_DEPENDENT_CODES = frozenset({
    'operational_request.manage',
    'operational_request.read',
    'role.manage',
    'role.read',
    'staff_credentials.manage',
    'tenant.manage',
    'tenant.read',
    'user.manage',
    'user.read',
})


def _permissions(connection) -> dict[str, tuple[int, str]]:
    with connection.cursor() as cursor:
        cursor.execute('SELECT id,code,description FROM permissions ORDER BY code')
        return {
            row['code']: (int(row['id']), row['description'])
            for row in cursor.fetchall()
        }


def _non_permission_table_counts(connection) -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT table_name FROM information_schema.tables '
            'WHERE table_schema=DATABASE() AND table_type=%s '
            "AND table_name NOT IN ('alembic_version','permissions') "
            'ORDER BY table_name',
            ('BASE TABLE',),
        )
        table_names = tuple(row['TABLE_NAME'] for row in cursor.fetchall())
        counts: dict[str, int] = {}
        for table_name in table_names:
            cursor.execute(f'SELECT COUNT(*) AS amount FROM `{table_name}`')
            counts[table_name] = int(cursor.fetchone()['amount'])
        return counts


def test_canonical_permission_initialization_is_complete_idempotent_and_isolated(
    integration_settings, sql_connection,
) -> None:
    connection, _ = sql_connection
    before_permissions = _permissions(connection)
    before_other_tables = _non_permission_table_counts(connection)

    assert len(CANONICAL_PERMISSIONS) == 83
    assert len(before_permissions) == 74
    assert set(CANONICAL_PERMISSIONS) - set(before_permissions) == BOOTSTRAP_DEPENDENT_CODES

    first = asyncio.run(initialize_permission_catalog(settings=integration_settings))
    after_first = _permissions(connection)
    second = asyncio.run(initialize_permission_catalog(settings=integration_settings))
    after_second = _permissions(connection)

    assert set(first.created_codes) == BOOTSTRAP_DEPENDENT_CODES
    assert first.total_permissions == 83
    assert second.created_codes == ()
    assert second.total_permissions == 83
    assert len(after_first) == len(after_second) == 83
    assert after_second == after_first
    assert {
        code: description for code, (_, description) in after_first.items()
    } == dict(CANONICAL_PERMISSIONS)
    assert all(after_first[code] == value for code, value in before_permissions.items())
    assert _non_permission_table_counts(connection) == before_other_tables
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT code,COUNT(*) AS amount FROM permissions '
            'GROUP BY code HAVING COUNT(*) <> 1'
        )
        assert cursor.fetchall() == ()


def test_description_conflict_fails_closed_without_partial_initialization(
    integration_settings, sql_connection,
) -> None:
    connection, _ = sql_connection
    asyncio.run(initialize_permission_catalog(settings=integration_settings))
    conflict_code = 'tenant.read'
    missing_code = 'tenant.manage'
    canonical_description = CANONICAL_PERMISSIONS[conflict_code]
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE permissions SET description=%s WHERE code=%s',
                ('Conflicting test description.', conflict_code),
            )
            cursor.execute('DELETE FROM permissions WHERE code=%s', (missing_code,))

        with pytest.raises(PermissionCatalogConflictError):
            asyncio.run(initialize_permission_catalog(settings=integration_settings))

        stored = _permissions(connection)
        assert stored[conflict_code][1] == 'Conflicting test description.'
        assert missing_code not in stored
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE permissions SET description=%s WHERE code=%s',
                (canonical_description, conflict_code),
            )
        asyncio.run(initialize_permission_catalog(settings=integration_settings))


def test_administrative_bootstrap_reuses_catalog_without_grant_expansion(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    values = BootstrapInput(
        tenant_name='Permission Catalog Bootstrap',
        tenant_slug=f'{prefix}-permission-catalog',
        admin_email=f'{prefix}-permission-catalog@example.test',
        admin_password=PASSWORD,
        admin_display_name='Permission Catalog Admin',
    )

    first = asyncio.run(bootstrap_admin(settings=integration_settings, values=values))
    second = asyncio.run(bootstrap_admin(settings=integration_settings, values=values))

    assert len(ADMIN_BOOTSTRAP_PERMISSION_CODES) == 59
    assert second.created == ()
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT p.code FROM role_permissions rp '
            'JOIN permissions p ON p.id=rp.permission_id '
            'WHERE rp.role_id=%s ORDER BY p.code',
            (first.role_id,),
        )
        granted_codes = tuple(row['code'] for row in cursor.fetchall())
    assert granted_codes == tuple(sorted(ADMIN_BOOTSTRAP_PERMISSION_CODES))
    assert set(CANONICAL_PERMISSIONS) - set(granted_codes)
