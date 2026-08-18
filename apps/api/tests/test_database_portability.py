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
}

API_ROOT = Path(__file__).resolve().parents[1]


def _database_contract(connection) -> tuple[set[tuple], set[tuple]]:
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
    return tables, foreign_keys


def _assert_database_contract(connection) -> None:
    tables, foreign_keys = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}
    assert foreign_keys == EXPECTED_FOREIGN_KEY_COLUMNS


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
    tables, _ = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}


def test_database_has_all_expected_foreign_keys(sql_connection) -> None:
    connection, _ = sql_connection
    _, foreign_keys = _database_contract(connection)
    assert foreign_keys == EXPECTED_FOREIGN_KEY_COLUMNS


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
            for table_name in APPLICATION_TABLES:
                cursor.execute(
                    f'ALTER TABLE `{table_name}` ENGINE=MyISAM, '
                    'CONVERT TO CHARACTER SET latin1 COLLATE latin1_swedish_ci'
                )

        unsafe_tables, unsafe_foreign_keys = _database_contract(connection)
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
