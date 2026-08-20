from __future__ import annotations

import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pymysql
import pytest

from app import models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base


APPLICATION_TABLES = {
    'tenants',
    'users',
    'permissions',
    'tenant_memberships',
    'roles',
    'role_permissions',
    'membership_roles',
    'organizations',
    'locations',
    'resources',
    'customers',
    'customer_external_identities',
}

LEGACY_APPLICATION_TABLES = APPLICATION_TABLES - {
    'organizations',
    'locations',
    'resources',
    'customers',
    'customer_external_identities',
}

EXPECTED_FOREIGN_KEY_COLUMNS = {
    ('fk_tenant_memberships_tenant', 'tenant_memberships', 'tenant_id', 'tenants', 'id', 1),
    ('fk_tenant_memberships_user', 'tenant_memberships', 'user_id', 'users', 'id', 1),
    ('fk_roles_tenant', 'roles', 'tenant_id', 'tenants', 'id', 1),
    ('fk_role_permissions_role', 'role_permissions', 'role_id', 'roles', 'id', 1),
    (
        'fk_role_permissions_permission',
        'role_permissions',
        'permission_id',
        'permissions',
        'id',
        1,
    ),
    (
        'fk_membership_roles_membership_tenant',
        'membership_roles',
        'membership_id',
        'tenant_memberships',
        'id',
        1,
    ),
    (
        'fk_membership_roles_membership_tenant',
        'membership_roles',
        'tenant_id',
        'tenant_memberships',
        'tenant_id',
        2,
    ),
    (
        'fk_membership_roles_role_tenant',
        'membership_roles',
        'role_id',
        'roles',
        'id',
        1,
    ),
    (
        'fk_membership_roles_role_tenant',
        'membership_roles',
        'tenant_id',
        'roles',
        'tenant_id',
        2,
    ),
    ('fk_organizations_tenant', 'organizations', 'tenant_id', 'tenants', 'id', 1),
    ('fk_locations_tenant', 'locations', 'tenant_id', 'tenants', 'id', 1),
    (
        'fk_locations_organization_tenant',
        'locations',
        'organization_id',
        'organizations',
        'id',
        1,
    ),
    (
        'fk_locations_organization_tenant',
        'locations',
        'tenant_id',
        'organizations',
        'tenant_id',
        2,
    ),
    ('fk_resources_tenant', 'resources', 'tenant_id', 'tenants', 'id', 1),
    (
        'fk_resources_location_tenant',
        'resources',
        'location_id',
        'locations',
        'id',
        1,
    ),
    (
        'fk_resources_location_tenant',
        'resources',
        'tenant_id',
        'locations',
        'tenant_id',
        2,
    ),
    ('fk_customers_tenant', 'customers', 'tenant_id', 'tenants', 'id', 1),
    (
        'fk_customer_external_identities_tenant',
        'customer_external_identities',
        'tenant_id',
        'tenants',
        'id',
        1,
    ),
    (
        'fk_customer_external_identities_customer_tenant',
        'customer_external_identities',
        'customer_id',
        'customers',
        'id',
        1,
    ),
    (
        'fk_customer_external_identities_customer_tenant',
        'customer_external_identities',
        'tenant_id',
        'customers',
        'tenant_id',
        2,
    ),
}

EXPECTED_INDEX_COLUMNS = {
    ('organizations', 'uq_organizations_id_tenant', 'id', 1, 0),
    ('organizations', 'uq_organizations_id_tenant', 'tenant_id', 2, 0),
    ('organizations', 'uq_organizations_tenant_code', 'tenant_id', 1, 0),
    ('organizations', 'uq_organizations_tenant_code', 'code', 2, 0),
    ('organizations', 'ix_organizations_tenant_status', 'tenant_id', 1, 1),
    ('organizations', 'ix_organizations_tenant_status', 'status', 2, 1),
    ('organizations', 'ix_organizations_tenant_status', 'id', 3, 1),
    ('locations', 'uq_locations_id_tenant', 'id', 1, 0),
    ('locations', 'uq_locations_id_tenant', 'tenant_id', 2, 0),
    ('locations', 'uq_locations_organization_code', 'organization_id', 1, 0),
    ('locations', 'uq_locations_organization_code', 'code', 2, 0),
    ('locations', 'ix_locations_tenant_organization_status', 'tenant_id', 1, 1),
    ('locations', 'ix_locations_tenant_organization_status', 'organization_id', 2, 1),
    ('locations', 'ix_locations_tenant_organization_status', 'status', 3, 1),
    ('locations', 'ix_locations_tenant_organization_status', 'id', 4, 1),
    ('resources', 'uq_resources_id_tenant', 'id', 1, 0),
    ('resources', 'uq_resources_id_tenant', 'tenant_id', 2, 0),
    ('resources', 'uq_resources_location_code', 'location_id', 1, 0),
    ('resources', 'uq_resources_location_code', 'code', 2, 0),
    ('resources', 'ix_resources_tenant_location_type_status', 'tenant_id', 1, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'location_id', 2, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'resource_type', 3, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'status', 4, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'id', 5, 1),
    ('customers', 'uq_customers_id_tenant', 'id', 1, 0),
    ('customers', 'uq_customers_id_tenant', 'tenant_id', 2, 0),
    ('customers', 'ix_customers_tenant_status', 'tenant_id', 1, 1),
    ('customers', 'ix_customers_tenant_status', 'status', 2, 1),
    ('customers', 'ix_customers_tenant_status', 'id', 3, 1),
    ('customers', 'ix_customers_tenant_email', 'tenant_id', 1, 1),
    ('customers', 'ix_customers_tenant_email', 'email', 2, 1),
    ('customers', 'ix_customers_tenant_email', 'id', 3, 1),
    ('customers', 'ix_customers_tenant_phone', 'tenant_id', 1, 1),
    ('customers', 'ix_customers_tenant_phone', 'phone', 2, 1),
    ('customers', 'ix_customers_tenant_phone', 'id', 3, 1),
    (
        'customer_external_identities',
        'uq_customer_external_identity_source',
        'tenant_id',
        1,
        0,
    ),
    (
        'customer_external_identities',
        'uq_customer_external_identity_source',
        'connector_key',
        2,
        0,
    ),
    (
        'customer_external_identities',
        'uq_customer_external_identity_source',
        'external_customer_id',
        3,
        0,
    ),
    (
        'customer_external_identities',
        'ix_customer_external_identities_customer',
        'tenant_id',
        1,
        1,
    ),
    (
        'customer_external_identities',
        'ix_customer_external_identities_customer',
        'customer_id',
        2,
        1,
    ),
    (
        'customer_external_identities',
        'ix_customer_external_identities_customer',
        'id',
        3,
        1,
    ),
}

EXPECTED_DOMAIN_CHECKS = {
    ('resources', 'ck_resources_status'),
    ('resources', 'ck_resources_type'),
    ('customers', 'ck_customers_status'),
    ('customers', 'ck_customers_source'),
}

API_ROOT = Path(__file__).resolve().parents[1]


def _database_contract(connection) -> tuple[set[tuple], set[tuple], set[tuple]]:
    with connection.cursor() as cursor:
        placeholders = ', '.join(['%s'] * len(APPLICATION_TABLES))
        cursor.execute(
            f'''
            SELECT TABLE_NAME, ENGINE, TABLE_COLLATION,
                   CCSA.CHARACTER_SET_NAME AS CHARACTER_SET_NAME
            FROM information_schema.TABLES AS T
            JOIN information_schema.COLLATION_CHARACTER_SET_APPLICABILITY AS CCSA
              ON CCSA.COLLATION_NAME = T.TABLE_COLLATION
            WHERE T.TABLE_SCHEMA = DATABASE()
              AND T.TABLE_NAME IN ({placeholders})
            ''',
            tuple(sorted(APPLICATION_TABLES)),
        )
        tables = {
            (
                row['TABLE_NAME'],
                row['ENGINE'],
                row['CHARACTER_SET_NAME'],
                row['TABLE_COLLATION'],
            )
            for row in cursor.fetchall()
        }
        cursor.execute(
            '''
            SELECT KCU.CONSTRAINT_NAME, KCU.TABLE_NAME, KCU.COLUMN_NAME,
                   KCU.REFERENCED_TABLE_NAME, KCU.REFERENCED_COLUMN_NAME,
                   KCU.ORDINAL_POSITION
            FROM information_schema.KEY_COLUMN_USAGE AS KCU
            WHERE KCU.TABLE_SCHEMA = DATABASE()
              AND KCU.REFERENCED_TABLE_NAME IS NOT NULL
            '''
        )
        foreign_keys = {
            (
                row['CONSTRAINT_NAME'],
                row['TABLE_NAME'],
                row['COLUMN_NAME'],
                row['REFERENCED_TABLE_NAME'],
                row['REFERENCED_COLUMN_NAME'],
                row['ORDINAL_POSITION'],
            )
            for row in cursor.fetchall()
        }
        index_names = {row[1] for row in EXPECTED_INDEX_COLUMNS}
        index_placeholders = ', '.join(['%s'] * len(index_names))
        cursor.execute(
            f'''
            SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND INDEX_NAME IN ({index_placeholders})
            ''',
            tuple(sorted(index_names)),
        )
        indexes = {
            (
                row['TABLE_NAME'],
                row['INDEX_NAME'],
                row['COLUMN_NAME'],
                row['SEQ_IN_INDEX'],
                row['NON_UNIQUE'],
            )
            for row in cursor.fetchall()
        }
    return tables, foreign_keys, indexes


def _assert_database_contract(connection) -> None:
    tables, foreign_keys, indexes = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}
    assert foreign_keys == EXPECTED_FOREIGN_KEY_COLUMNS
    assert indexes == EXPECTED_INDEX_COLUMNS
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND CONSTRAINT_TYPE = 'CHECK'
              AND TABLE_NAME IN ('resources', 'customers')
            '''
        )
        assert {(row['TABLE_NAME'], row['CONSTRAINT_NAME']) for row in cursor.fetchall()} == (
            EXPECTED_DOMAIN_CHECKS
        )
        cursor.execute(
            '''
            SELECT COLLATION_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'customer_external_identities'
              AND COLUMN_NAME = 'external_customer_id'
            '''
        )
        assert cursor.fetchone()['COLLATION_NAME'] == 'utf8mb4_bin'


def _run_alembic(database_name: str, revision: str) -> None:
    environment = os.environ.copy()
    environment['MYSQL_DATABASE'] = database_name
    environment['MYSQL_USER'] = 'root'
    environment['MYSQL_PASSWORD'] = environment['MYSQL_ROOT_PASSWORD']
    subprocess.run(
        ['alembic', 'upgrade', revision],
        cwd=API_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def isolated_database(integration_settings: Settings):
    root_password = os.getenv('MYSQL_ROOT_PASSWORD')
    assert root_password, 'MYSQL_ROOT_PASSWORD is required for isolated migration-path tests'

    database_name = f'ecip_portability_{uuid4().hex}'
    server_connection = pymysql.connect(
        host=integration_settings.mysql_host,
        port=integration_settings.mysql_port,
        user='root',
        password=root_password,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with server_connection.cursor() as cursor:
        cursor.execute(
            f'CREATE DATABASE `{database_name}` '
            'CHARACTER SET latin1 COLLATE latin1_swedish_ci'
        )
    try:
        yield database_name, server_connection
    finally:
        with server_connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{database_name}`')
        server_connection.close()


def _connect_isolated_database(integration_settings: Settings, database_name: str):
    return pymysql.connect(
        host=integration_settings.mysql_host,
        port=integration_settings.mysql_port,
        user='root',
        password=os.environ['MYSQL_ROOT_PASSWORD'],
        database=database_name,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def test_model_metadata_declares_portable_mysql_table_options() -> None:
    assert set(Base.metadata.tables) == APPLICATION_TABLES
    for table in Base.metadata.sorted_tables:
        options = table.dialect_options['mysql']
        assert options['engine'] == 'InnoDB'
        assert options['charset'] == 'utf8mb4'
        assert options['collate'] == 'utf8mb4_unicode_ci'


def test_database_tables_enforce_storage_contract(sql_connection) -> None:
    connection, _ = sql_connection
    tables, _, _ = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}


def test_database_has_all_expected_foreign_keys(sql_connection) -> None:
    connection, _ = sql_connection
    _, foreign_keys, indexes = _database_contract(connection)
    assert foreign_keys == EXPECTED_FOREIGN_KEY_COLUMNS
    assert indexes == EXPECTED_INDEX_COLUMNS
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND CONSTRAINT_TYPE = 'CHECK'
              AND TABLE_NAME IN ('resources', 'customers')
            '''
        )
        assert {(row['TABLE_NAME'], row['CONSTRAINT_NAME']) for row in cursor.fetchall()} == (
            EXPECTED_DOMAIN_CHECKS
        )
        cursor.execute(
            '''
            SELECT COLLATION_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'customer_external_identities'
              AND COLUMN_NAME = 'external_customer_id'
            '''
        )
        assert cursor.fetchone()['COLLATION_NAME'] == 'utf8mb4_bin'


def test_foreign_key_is_actually_enforced(sql_connection) -> None:
    connection, _ = sql_connection
    with pytest.raises(pymysql.err.IntegrityError):
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO tenant_memberships (tenant_id, user_id, status)
                VALUES (%s, %s, 'ACTIVE')
                ''',
                (9_000_000_001, 9_000_000_002),
            )


def test_fresh_install_reaches_portable_database_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()


def test_upgrade_from_0003_reaches_contract_and_upgrades_existing_tenant_admin(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0003_database_portability_remediation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) VALUES ('Upgrade Tenant', 'upgrade', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO permissions (code, description)
                VALUES ('organization.read', 'Preexisting permission')
                '''
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN (
                      'organization.read', 'organization.manage',
                      'location.read', 'location.manage',
                      'resource.read', 'resource.manage',
                      'customer.read', 'customer.manage'
                  )
                ORDER BY P.code
                ''',
                (role_id,),
            )
            assert [row['code'] for row in cursor.fetchall()] == [
                'customer.manage',
                'customer.read',
                'location.manage',
                'location.read',
                'organization.manage',
                'organization.read',
                'resource.manage',
                'resource.read',
            ]
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN (
                      'organization.read', 'organization.manage',
                      'location.read', 'location.manage',
                      'resource.read', 'resource.manage',
                      'customer.read', 'customer.manage'
                  )
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'customer.manage': 1,
                'customer.read': 1,
                'location.manage': 1,
                'location.read': 1,
                'organization.manage': 1,
                'organization.read': 1,
                'resource.manage': 1,
                'resource.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0004_reaches_contract_and_upgrades_existing_tenant_admin(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0004_organization_location_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO tenants (name, slug, status)
                VALUES ('Resource Tenant', 'resource', 'ACTIVE')
                '''
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO permissions (code, description)
                VALUES ('resource.read', 'Preexisting')
                '''
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('resource.read', 'resource.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'resource.manage': 1,
                'resource.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0005_reaches_customer_contract_and_upgrades_existing_tenant_admin(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0005_resource_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) "
                "VALUES ('Customer Tenant', 'customer', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO permissions (code, description) "
                "VALUES ('customer.read', 'Preexisting')"
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('customer.read', 'customer.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'customer.manage': 1,
                'customer.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_unsafe_0002_schema_reaches_portable_database_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0002_auth_tenant_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT DISTINCT TABLE_NAME, CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                '''
            )
            for row in cursor.fetchall():
                cursor.execute(
                    f"ALTER TABLE `{row['TABLE_NAME']}` "
                    f"DROP FOREIGN KEY `{row['CONSTRAINT_NAME']}`"
                )
            for table_name in LEGACY_APPLICATION_TABLES:
                cursor.execute(
                    f'ALTER TABLE `{table_name}` ENGINE=MyISAM, '
                    'CONVERT TO CHARACTER SET latin1 COLLATE latin1_swedish_ci'
                )

        unsafe_tables, unsafe_foreign_keys, _ = _database_contract(connection)
        assert {row[1] for row in unsafe_tables} == {'MyISAM'}
        assert {row[2] for row in unsafe_tables} == {'latin1'}
        assert {row[3] for row in unsafe_tables} == {'latin1_swedish_ci'}
        assert unsafe_foreign_keys == set()
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()
