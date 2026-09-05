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
        RESTAURANT_ACCESS_CODE_SECRET='test-only-independent-access-code-secret-32-chars',
        DINER_ACCESS_TOKEN_TTL_MINUTES=720,
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
        RESTAURANT_ACCESS_CODE_SECRET='integration-independent-access-code-secret-32-chars',
        DINER_ACCESS_TOKEN_TTL_MINUTES=720,
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
                'DELETE FROM billing_fiscal_artifacts WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM billing_fiscal_results WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM billing_issuance_attempts WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM billing_issuances WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM billing_document_line_taxes WHERE billing_document_line_id IN '
                '(SELECT id FROM billing_document_lines WHERE billing_document_id IN '
                '(SELECT id FROM billing_documents WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)))',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM billing_document_lines WHERE billing_document_id IN '
                '(SELECT id FROM billing_documents WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s))',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM billing_documents WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'UPDATE preparation_delivery_connector_credentials SET replaces_credential_id=NULL '
                'WHERE tenant_id IN (SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM preparation_dispatch_attempts WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM preparation_dispatches WHERE reprint_of_dispatch_id IS NOT NULL '
                'AND tenant_id IN (SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            for table in (
                'preparation_delivery_connector_credentials',
                'preparation_delivery_connector_enrollments',
                'preparation_dispatch_attempts',
                'preparation_dispatches',
                'preparation_delivery_destinations',
                'preparation_delivery_connectors',
                'preparation_item_transitions',
                'preparation_work_items',
                'preparation_works',
                'preparation_routings',
                'pos_order_submission_attempts',
                'pos_order_submission_components',
                'pos_order_submission_lines',
                'pos_order_submissions',
                'location_pos_connections',
                'product_preparation_routes',
                'preparation_areas',
                'location_preparation_configurations',
            ):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            for table in (
                'restaurant_check_settlements',
                'restaurant_payment_attempts',
                'restaurant_payments',
                'restaurant_check_commands',
                'restaurant_check_table_scopes',
                'restaurant_check_gratuities',
                'restaurant_check_versions',
                'restaurant_check_members',
                'restaurant_check_allocations',
                'restaurant_checks',
            ):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            for table in (
                'location_payment_executor_capabilities',
                'location_payment_executor_configurations',
            ):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            for table in (
                'restaurant_order_item_fiscal_snapshots',
                'restaurant_order_item_tax_snapshots',
                'restaurant_order_promotions',
                'restaurant_order_item_components',
                'restaurant_order_items',
                'restaurant_orders',
            ):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            cursor.execute(
                'DELETE FROM diner_sessions WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            for table in (
                'order_draft_item_selections',
                'order_draft_items',
                'order_drafts',
            ):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            for table in ('restaurant_message_intents', 'intelligence_derivations'):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            for table in ('conversation_messages', 'conversation_participants', 'conversations'):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            cursor.execute(
                'DELETE FROM restaurant_service_sessions WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM cash_sessions WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            for table in ('promotion_locations', 'promotion_products', 'promotions', 'product_prices'):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
            for table in (
                'product_aliases',
                'product_choice_options',
                'product_choice_groups',
                'product_components',
                'product_compositions',
            ):
                cursor.execute(
                    f'DELETE FROM {table} WHERE tenant_id IN '
                    '(SELECT id FROM tenants WHERE slug LIKE %s)',
                    (f'{prefix}%',),
                )
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
                'DELETE FROM product_fiscal_classifications WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM products WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'UPDATE product_categories SET parent_id = NULL WHERE tenant_id IN '
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
                'DELETE FROM customer_fiscal_profiles WHERE tenant_id IN '
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
                'DELETE FROM issuer_fiscal_profiles WHERE tenant_id IN '
                '(SELECT id FROM tenants WHERE slug LIKE %s)',
                (f'{prefix}%',),
            )
            cursor.execute(
                'DELETE FROM restaurant_tax_rules WHERE tenant_id IN '
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
