from __future__ import annotations

from dataclasses import dataclass
import os
from uuid import uuid4

import pytest
import pymysql

from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_NAME='ECIP Test API',
        APP_ENV='test',
        API_HOST='127.0.0.1',
        API_PORT=8000,
        LOG_LEVEL='INFO',
        MYSQL_HOST='mysql.test',
        MYSQL_PORT=3306,
        MYSQL_DATABASE='ecip_test',
        MYSQL_USER='ecip_test',
        MYSQL_PASSWORD='test-only-password',
        MYSQL_POOL_SIZE=1,
        MYSQL_MAX_OVERFLOW=0,
        AUTH_JWT_SECRET='test-only-secret-that-is-at-least-32-characters',
        AUTH_ACCESS_TOKEN_TTL_MINUTES=60,
        PASSWORD_MIN_LENGTH=12,
    )


@dataclass
class FakeDatabase:
    available: bool = True
    checks: int = 0
    disposed: bool = False

    async def check_connection(self) -> None:
        self.checks += 1
        if not self.available:
            raise ConnectionError('simulated unavailable database')

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def database() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def integration_settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_NAME='ECIP Integration Test API',
        APP_ENV='test',
        API_HOST='127.0.0.1',
        API_PORT=8000,
        LOG_LEVEL='INFO',
        MYSQL_HOST=os.getenv('MYSQL_HOST', 'mysql'),
        MYSQL_PORT=int(os.getenv('MYSQL_PORT', '3306')),
        MYSQL_DATABASE=os.environ['MYSQL_DATABASE'],
        MYSQL_USER=os.environ['MYSQL_USER'],
        MYSQL_PASSWORD=os.environ['MYSQL_PASSWORD'],
        MYSQL_POOL_SIZE=2,
        MYSQL_MAX_OVERFLOW=1,
        AUTH_JWT_SECRET='integration-test-secret-that-is-at-least-32-characters',
        AUTH_ACCESS_TOKEN_TTL_MINUTES=60,
        PASSWORD_MIN_LENGTH=12,
    )


@pytest.fixture
def sql_connection(integration_settings: Settings):
    connection = pymysql.connect(
        host=integration_settings.mysql_host,
        port=integration_settings.mysql_port,
        user=integration_settings.mysql_user,
        password=integration_settings.mysql_password.get_secret_value(),
        database=integration_settings.mysql_database,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    prefix = f'test-{uuid4().hex}'
    try:
        yield connection, prefix
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                'DELETE FROM menu_items WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM menu_sections WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM menu_locations WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM product_external_mappings WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM menus WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM products WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM product_categories WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM customer_external_identities WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM customers WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM resources WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM locations WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM organizations WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute('DELETE FROM tenants WHERE slug LIKE %s', (f'{prefix}%',))
            cursor.execute('DELETE FROM users WHERE email LIKE %s', (f'{prefix}%@example.test',))
            cursor.execute('DELETE FROM permissions WHERE code LIKE %s', (f'{prefix}.%',))
        connection.close()
