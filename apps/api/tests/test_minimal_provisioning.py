from __future__ import annotations

import asyncio

import pytest

from app.db.session import DatabaseManager
from app.minimal_provisioning import (
    MinimalProvisioningError,
    MinimalProvisioningManifest,
    provision_minimal_core,
)
from test_organization_location_foundation import PASSWORD, _assign_permission, _seed_authority


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _count(connection, table: str, tenant_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT COUNT(*) AS amount FROM {table} WHERE tenant_id=%s', (tenant_id,))
        return int(cursor.fetchone()['amount'])


def _manifest(authority, prefix: str, **updates) -> MinimalProvisioningManifest:
    values = {
        'operation_id': f'{prefix}-operation',
        'tenant_id': authority.tenant_id,
        'actor_membership_id': authority.membership_id,
        'organization_code': 'NEW-ORG',
        'organization_name': 'New Organization',
        'location_code': 'HQ',
        'location_name': 'Headquarters',
        'location_timezone': 'America/Mexico_City',
        'staff_username': f'{prefix}.staff',
        'staff_display_name': 'Provisioned Staff',
        'role_name': f'{prefix}-STAFF',
    }
    values.update(updates)
    return MinimalProvisioningManifest.model_validate(values)


def _role(connection, authority, prefix: str) -> None:
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (authority.tenant_id, f'{prefix}-STAFF', 'Minimal Staff', 'ACTIVE'),
    )
    _assign_permission(connection, role_id, 'location.read')


def test_minimal_provisioning_is_atomic_replayable_and_core_only(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    _assign_permission(connection, authority.role_id, 'user.manage')
    _assign_permission(connection, authority.role_id, 'role.manage')
    _role(connection, authority, prefix)
    manifest = _manifest(authority, prefix)
    commercial_before = {
        table: _count(connection, table, authority.tenant_id)
        for table in ('products', 'restaurant_orders', 'restaurant_payments')
    }

    async def exercise():
        database = DatabaseManager(integration_settings)
        try:
            async with database.session_factory() as session:
                first = await provision_minimal_core(
                    session,
                    manifest=manifest,
                    staff_password=PASSWORD,
                    password_minimum_length=12,
                )
            async with database.session_factory() as session:
                replay = await provision_minimal_core(
                    session,
                    manifest=manifest,
                    staff_password='A different ignored replay secret 123!',
                    password_minimum_length=12,
                )
            async with database.session_factory() as session:
                with pytest.raises(MinimalProvisioningError):
                    await provision_minimal_core(
                        session,
                        manifest=_manifest(authority, prefix, organization_name='Drifted'),
                        staff_password=PASSWORD,
                        password_minimum_length=12,
                    )
            return first, replay
        finally:
            await database.dispose()

    first, replay = asyncio.run(exercise())
    assert not first.replayed
    assert replay.replayed
    assert first.organization_id == replay.organization_id
    assert first.location_id == replay.location_id
    assert first.staff_user_id == replay.staff_user_id
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT status,headquarters_location_id FROM organizations WHERE id=%s',
            (first.organization_id,),
        )
        assert cursor.fetchone() == {
            'status': 'ACTIVE',
            'headquarters_location_id': first.location_id,
        }
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM minimal_provisioning_runs '
            'WHERE tenant_id=%s AND operation_id=%s',
            (authority.tenant_id, manifest.operation_id),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM organization_headquarters_changes '
            'WHERE organization_id=%s',
            (first.organization_id,),
        )
        assert cursor.fetchone()['amount'] == 1
    assert commercial_before == {
        table: _count(connection, table, authority.tenant_id)
        for table in commercial_before
    }


def test_minimal_provisioning_identity_conflict_rolls_back_all_core_writes(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    _assign_permission(connection, authority.role_id, 'user.manage')
    _assign_permission(connection, authority.role_id, 'role.manage')
    _role(connection, authority, prefix)
    _execute(
        connection,
        'INSERT INTO users (username,email,password_hash,display_name,status) '
        'VALUES (%s,NULL,%s,%s,%s)',
        (f'{prefix}.staff', 'not-a-real-hash', 'Existing', 'ACTIVE'),
    )
    manifest = _manifest(authority, prefix)

    async def exercise() -> None:
        database = DatabaseManager(integration_settings)
        try:
            async with database.session_factory() as session:
                with pytest.raises(MinimalProvisioningError):
                    await provision_minimal_core(
                        session,
                        manifest=manifest,
                        staff_password=PASSWORD,
                        password_minimum_length=12,
                    )
        finally:
            await database.dispose()

    asyncio.run(exercise())
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM organizations WHERE tenant_id=%s AND code=%s',
            (authority.tenant_id, manifest.organization_code),
        )
        assert cursor.fetchone()['amount'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM minimal_provisioning_runs '
            'WHERE tenant_id=%s AND operation_id=%s',
            (authority.tenant_id, manifest.operation_id),
        )
        assert cursor.fetchone()['amount'] == 0
