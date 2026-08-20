from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.models import Product, ProductExternalMapping
from app.restaurant.catalog.service import resolve_external_product
from app.restaurant.integrations.pos.contracts import (
    ExternalEntityStatus,
    ExternalProduct,
    PosRequestContext,
)
from app.restaurant.integrations.pos.errors import PosMappingError
from app.restaurant.integrations.pos.mock import MockPosAdapter, build_mock_pos_dataset


PASSWORD = 'Test Password 123!'
WS_08_PERMISSIONS = ('product.read', 'product.manage', 'menu.read', 'menu.manage')


@dataclass(frozen=True)
class Authority:
    tenant_id: int
    role_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _assign_permission(connection, role_id: int, code: str) -> None:
    _execute(
        connection,
        'INSERT IGNORE INTO permissions (code, description) VALUES (%s, %s)',
        (code, f'Permission {code}'),
    )
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM permissions WHERE code = %s', (code,))
        permission_id = int(cursor.fetchone()['id'])
    _execute(
        connection,
        'INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
        (role_id, permission_id),
    )


def _seed_authority(connection, slug: str, permissions=WS_08_PERMISSIONS) -> Authority:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Catalog Tenant', slug, 'ACTIVE'),
    )
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email, password_hash, display_name, status) VALUES (%s, %s, %s, %s)',
        (email, hash_password(PASSWORD), 'Catalog User', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id, name, description, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, 'CATALOG_TEST_ROLE', 'Catalog test role', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id, membership_id, role_id) VALUES (%s, %s, %s)',
        (tenant_id, membership_id, role_id),
    )
    for permission in permissions:
        _assign_permission(connection, role_id, permission)
    return Authority(tenant_id=tenant_id, role_id=role_id, email=email)


def _login(client: TestClient, authority: Authority) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': authority.email, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _organization(connection, tenant_id: int, code: str) -> int:
    return _execute(
        connection,
        'INSERT INTO organizations (tenant_id, code, name, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, code, f'Organization {code}', 'ACTIVE'),
    )


def _location(connection, tenant_id: int, organization_id: int, code: str) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id, organization_id, code, name, timezone, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (tenant_id, organization_id, code, f'Location {code}', 'America/Mexico_City', 'ACTIVE'),
    )


def _category(connection, tenant_id: int, organization_id: int, name='Category') -> int:
    return _execute(
        connection,
        '''
        INSERT INTO product_categories (tenant_id, organization_id, name, status)
        VALUES (%s, %s, %s, 'ACTIVE')
        ''',
        (tenant_id, organization_id, name),
    )


def _product(
    connection,
    tenant_id: int,
    organization_id: int,
    *,
    category_id: int | None = None,
    name='Product',
) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO products
            (tenant_id, organization_id, category_id, name, description, status, source)
        VALUES (%s, %s, %s, %s, NULL, 'ACTIVE', 'PLATFORM')
        ''',
        (tenant_id, organization_id, category_id, name),
    )


def _menu(connection, tenant_id: int, organization_id: int, name='Menu') -> int:
    return _execute(
        connection,
        'INSERT INTO menus (tenant_id, organization_id, name, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, organization_id, name, 'ACTIVE'),
    )


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_product_category_and_product_permissions_crud_and_safe_logging(
    client, sql_connection, caplog: pytest.LogCaptureFixture
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permissions=())
    organization_id = _organization(connection, authority.tenant_id, 'ORG-A')
    other_organization_id = _organization(connection, authority.tenant_id, 'ORG-B')
    headers = _login(client, authority)

    assert client.get(f'/products?organization_id={organization_id}').status_code == 401
    assert client.get(f'/products?organization_id={organization_id}', headers=headers).status_code == 403
    _assign_permission(connection, authority.role_id, 'product.read')
    assert client.get(f'/products?organization_id={organization_id}', headers=headers).status_code == 200
    assert client.post('/products', headers=headers, json={'organization_id': organization_id, 'name': 'Soup'}).status_code == 403
    _assign_permission(connection, authority.role_id, 'product.manage')

    with caplog.at_level(logging.INFO, logger='ecip.products'):
        category = client.post(
            '/product-categories',
            headers=headers,
            json={'organization_id': organization_id, 'name': '  Entrées  '},
        )
        product = client.post(
            '/products',
            headers=headers,
            json={
                'organization_id': organization_id,
                'category_id': category.json()['id'],
                'name': '  Tomato Soup  ',
                'description': '  House recipe  ',
            },
        )
    assert category.status_code == 201, category.text
    assert product.status_code == 201, product.text
    assert product.json()['name'] == 'Tomato Soup'
    assert product.json()['source'] == 'PLATFORM'
    assert product.json()['status'] == 'ACTIVE'
    assert {'price', 'currency', 'promotion', 'availability', 'sold_out', 'stock_status'}.isdisjoint(product.json())
    assert [record.event for record in caplog.records if record.name == 'ecip.products'][-2:] == [
        'product_category_created',
        'product_created',
    ]
    assert 'House recipe' not in ' '.join(record.getMessage() for record in caplog.records)

    duplicate = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': organization_id, 'name': 'ENTRÉES'},
    )
    assert duplicate.status_code == 409
    same_other_org = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': other_organization_id, 'name': 'Entrées'},
    )
    assert same_other_org.status_code == 201


def test_product_search_patch_nonunique_name_immutability_and_no_delete(
    client, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG-A')
    headers = _login(client, authority)
    category = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': organization_id, 'name': 'Drinks'},
    ).json()
    first = client.post(
        '/products',
        headers=headers,
        json={'organization_id': organization_id, 'name': '100% Juice'},
    ).json()
    second = client.post(
        '/products',
        headers=headers,
        json={'organization_id': organization_id, 'name': '100% Juice'},
    ).json()
    assert first['id'] != second['id']

    literal_percent = client.get(
        f'/products?organization_id={organization_id}&q=%25', headers=headers
    ).json()['items']
    assert [item['id'] for item in literal_percent] == [first['id'], second['id']]
    updated = client.patch(
        f"/products/{first['id']}",
        headers=headers,
        json={'category_id': category['id'], 'description': None, 'status': 'INACTIVE'},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['category_id'] == category['id']
    assert updated.json()['description'] is None
    assert updated.json()['status'] == 'INACTIVE'
    assert client.patch(f"/products/{first['id']}", headers=headers, json={}).status_code == 422
    for field, value in (
        ('source', 'POS'),
        ('organization_id', organization_id),
        ('tenant_id', authority.tenant_id),
        ('price', 10),
        ('availability', True),
    ):
        assert client.patch(f"/products/{first['id']}", headers=headers, json={field: value}).status_code == 422
    assert client.delete(f"/products/{first['id']}", headers=headers).status_code == 405
    assert client.delete(f"/product-categories/{category['id']}", headers=headers).status_code == 405


def test_product_tenant_and_category_organization_isolation(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other = _seed_authority(connection, f'{prefix}-other')
    organization_id = _organization(connection, authority.tenant_id, 'ORG-A')
    sibling_organization_id = _organization(connection, authority.tenant_id, 'ORG-B')
    other_organization_id = _organization(connection, other.tenant_id, 'ORG-X')
    sibling_category = _category(connection, authority.tenant_id, sibling_organization_id)
    foreign_product = _product(connection, other.tenant_id, other_organization_id)
    headers = _login(client, authority)

    response = client.post(
        '/products',
        headers=headers,
        json={
            'organization_id': organization_id,
            'category_id': sibling_category,
            'name': 'Wrong category',
        },
    )
    assert response.status_code == 404
    assert client.get(f'/products/{foreign_product}', headers=headers).status_code == 404
    assert client.get(f'/products?organization_id={other_organization_id}', headers=headers).status_code == 404


def test_menu_management_location_sections_items_ordering_and_reuse(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG-A')
    location_a = _location(connection, authority.tenant_id, organization_id, 'LOC-A')
    location_b = _location(connection, authority.tenant_id, organization_id, 'LOC-B')
    product_a = _product(connection, authority.tenant_id, organization_id, name='Soup')
    product_b = _product(connection, authority.tenant_id, organization_id, name='Salad')
    headers = _login(client, authority)

    menu = client.post('/menus', headers=headers, json={'organization_id': organization_id, 'name': 'Dinner'})
    assert menu.status_code == 201, menu.text
    menu_id = menu.json()['id']
    for location_id in (location_a, location_b):
        assert client.post(f'/menus/{menu_id}/locations', headers=headers, json={'location_id': location_id}).status_code == 201
    assert client.post(f'/menus/{menu_id}/locations', headers=headers, json={'location_id': location_a}).status_code == 409

    later = client.post(
        f'/menus/{menu_id}/sections',
        headers=headers,
        json={'name': 'Mains', 'display_order': 20},
    ).json()
    earlier = client.post(
        f'/menus/{menu_id}/sections',
        headers=headers,
        json={'name': 'Starters', 'display_order': 10},
    ).json()
    first_item = client.post(
        f'/menus/{menu_id}/items',
        headers=headers,
        json={'section_id': earlier['id'], 'product_id': product_a, 'display_order': 20},
    )
    second_item = client.post(
        f'/menus/{menu_id}/items',
        headers=headers,
        json={'section_id': earlier['id'], 'product_id': product_b, 'display_order': 10},
    )
    assert first_item.status_code == second_item.status_code == 201
    assert client.post(
        f'/menus/{menu_id}/items',
        headers=headers,
        json={'section_id': later['id'], 'product_id': product_a},
    ).status_code == 409
    moved = client.patch(
        f"/menus/{menu_id}/items/{first_item.json()['id']}",
        headers=headers,
        json={'section_id': later['id'], 'display_order': 5, 'status': 'INACTIVE'},
    )
    assert moved.status_code == 200

    detail = client.get(f'/menus/{menu_id}', headers=headers).json()
    assert [section['id'] for section in detail['sections']] == [earlier['id'], later['id']]
    assert [item['product']['id'] for item in detail['sections'][0]['items']] == [product_b]
    assert [item['product']['id'] for item in detail['sections'][1]['items']] == [product_a]
    assert {'price', 'availability', 'currency', 'promotion'}.isdisjoint(
        detail['sections'][0]['items'][0]['product']
    )
    filtered = client.get(
        f'/menus?organization_id={organization_id}&location_id={location_a}&q=inn',
        headers=headers,
    ).json()['items']
    assert [entry['id'] for entry in filtered] == [menu_id]

    other_menu = client.post(
        '/menus', headers=headers, json={'organization_id': organization_id, 'name': 'Lunch'}
    ).json()
    other_section = client.post(
        f"/menus/{other_menu['id']}/sections",
        headers=headers,
        json={'name': 'Lunch', 'display_order': 0},
    ).json()
    assert client.post(
        f"/menus/{other_menu['id']}/items",
        headers=headers,
        json={'section_id': other_section['id'], 'product_id': product_a},
    ).status_code == 201
    assert client.delete(f'/menus/{menu_id}', headers=headers).status_code == 405


def test_menu_permissions_cross_organization_validation_and_immutable_relations(
    client, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permissions=())
    organization_a = _organization(connection, authority.tenant_id, 'ORG-A')
    organization_b = _organization(connection, authority.tenant_id, 'ORG-B')
    location_b = _location(connection, authority.tenant_id, organization_b, 'LOC-B')
    product_b = _product(connection, authority.tenant_id, organization_b)
    headers = _login(client, authority)
    assert client.get(f'/menus?organization_id={organization_a}', headers=headers).status_code == 403
    _assign_permission(connection, authority.role_id, 'menu.read')
    assert client.get(f'/menus?organization_id={organization_a}', headers=headers).status_code == 200
    assert client.post('/menus', headers=headers, json={'organization_id': organization_a, 'name': 'Menu'}).status_code == 403
    _assign_permission(connection, authority.role_id, 'menu.manage')
    menu = client.post('/menus', headers=headers, json={'organization_id': organization_a, 'name': 'Menu'}).json()
    section = client.post(f"/menus/{menu['id']}/sections", headers=headers, json={'name': 'Section'}).json()
    assert client.post(f"/menus/{menu['id']}/locations", headers=headers, json={'location_id': location_b}).status_code == 404
    assert client.post(
        f"/menus/{menu['id']}/items",
        headers=headers,
        json={'section_id': section['id'], 'product_id': product_b},
    ).status_code == 404
    own_product = _product(connection, authority.tenant_id, organization_a, name='Own')
    item = client.post(
        f"/menus/{menu['id']}/items",
        headers=headers,
        json={'section_id': section['id'], 'product_id': own_product},
    ).json()
    assert client.patch(
        f"/menus/{menu['id']}/items/{item['id']}",
        headers=headers,
        json={'product_id': product_b},
    ).status_code == 422


def test_raw_database_rejects_cross_tenant_and_cross_organization_relations(
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_a = _seed_authority(connection, prefix)
    tenant_b = _seed_authority(connection, f'{prefix}-other')
    org_a = _organization(connection, tenant_a.tenant_id, 'ORG-A')
    org_sibling = _organization(connection, tenant_a.tenant_id, 'ORG-B')
    org_b = _organization(connection, tenant_b.tenant_id, 'ORG-X')
    location_sibling = _location(connection, tenant_a.tenant_id, org_sibling, 'LOC-B')
    category_a = _category(connection, tenant_a.tenant_id, org_a)
    product_a = _product(connection, tenant_a.tenant_id, org_a, category_id=category_a)
    product_sibling = _product(connection, tenant_a.tenant_id, org_sibling)
    menu_a = _menu(connection, tenant_a.tenant_id, org_a)
    section_a = _execute(
        connection,
        '''INSERT INTO menu_sections
           (tenant_id, organization_id, menu_id, name, display_order, status)
           VALUES (%s, %s, %s, 'Section', 0, 'ACTIVE')''',
        (tenant_a.tenant_id, org_a, menu_a),
    )

    invalid_statements = (
        (
            "INSERT INTO product_categories (tenant_id, organization_id, name, status) VALUES (%s, %s, 'Bad', 'ACTIVE')",
            (tenant_a.tenant_id, org_b),
        ),
        (
            "INSERT INTO products (tenant_id, organization_id, name, status, source) VALUES (%s, %s, 'Bad', 'ACTIVE', 'PLATFORM')",
            (tenant_a.tenant_id, org_b),
        ),
        (
            "INSERT INTO menus (tenant_id, organization_id, name, status) VALUES (%s, %s, 'Bad', 'ACTIVE')",
            (tenant_a.tenant_id, org_b),
        ),
        (
            "INSERT INTO products (tenant_id, organization_id, category_id, name, status, source) VALUES (%s, %s, %s, 'Bad', 'ACTIVE', 'PLATFORM')",
            (tenant_a.tenant_id, org_sibling, category_a),
        ),
        (
            "INSERT INTO menu_locations (tenant_id, organization_id, menu_id, location_id, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (tenant_a.tenant_id, org_a, menu_a, location_sibling),
        ),
        (
            "INSERT INTO menu_sections (tenant_id, organization_id, menu_id, name, display_order, status) VALUES (%s, %s, %s, 'Bad', 0, 'ACTIVE')",
            (tenant_a.tenant_id, org_sibling, menu_a),
        ),
        (
            "INSERT INTO menu_items (tenant_id, organization_id, menu_id, section_id, product_id, display_order, status) VALUES (%s, %s, %s, %s, %s, 0, 'ACTIVE')",
            (tenant_a.tenant_id, org_a, menu_a, section_a, product_sibling),
        ),
        (
            "INSERT INTO product_external_mappings (tenant_id, product_id, connector_key, external_product_id) VALUES (%s, %s, 'pos', 'bad')",
            (tenant_b.tenant_id, product_a),
        ),
    )
    for statement, parameters in invalid_statements:
        with pytest.raises(pymysql.err.IntegrityError):
            _execute(connection, statement, parameters)


def test_product_external_mapping_scope_and_case_sensitivity(sql_connection) -> None:
    connection, prefix = sql_connection
    tenant_a = _seed_authority(connection, prefix)
    tenant_b = _seed_authority(connection, f'{prefix}-other')
    org_a = _organization(connection, tenant_a.tenant_id, 'ORG-A')
    org_b = _organization(connection, tenant_b.tenant_id, 'ORG-B')
    product_a = _product(connection, tenant_a.tenant_id, org_a)
    product_b = _product(connection, tenant_b.tenant_id, org_b)

    def mapping(tenant_id: int, product_id: int, connector: str, external_id: str) -> int:
        return _execute(
            connection,
            '''INSERT INTO product_external_mappings
               (tenant_id, product_id, connector_key, external_product_id)
               VALUES (%s, %s, %s, %s)''',
            (tenant_id, product_id, connector, external_id),
        )

    mapping(tenant_a.tenant_id, product_a, 'primary', 'ABC')
    with pytest.raises(pymysql.err.IntegrityError):
        mapping(tenant_a.tenant_id, product_a, 'primary', 'ABC')
    mapping(tenant_a.tenant_id, product_a, 'primary', 'abc')
    mapping(tenant_a.tenant_id, product_a, 'secondary', 'ABC')
    mapping(tenant_b.tenant_id, product_b, 'primary', 'ABC')


def test_catalog_port_resolution_is_idempotent_non_merging_and_canonical_safe(
    integration_settings, sql_connection, caplog: pytest.LogCaptureFixture
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG-A')
    existing_id = _product(connection, authority.tenant_id, organization_id, name='Hamburger')
    adapter = MockPosAdapter(
        build_mock_pos_dataset(
            tenant_id=authority.tenant_id,
            connector_key='primary-pos',
            location_ids=(101, 102),
        )
    )
    context = PosRequestContext(
        tenant_id=authority.tenant_id,
        connector_key='primary-pos',
        correlation_id='product-resolution-test',
    )

    async def exercise() -> tuple[int, int]:
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                first = await resolve_external_product(
                    db,
                    adapter,
                    context,
                    organization_id=organization_id,
                    external_product_id='product-001',
                )
                assert first.source == 'POS'
                assert first.category_id is None
                first_id = first.id
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE products SET name = %s WHERE id = %s', ('Canonical Hamburger', first_id)
                )
            async with manager.session_factory() as db:
                second = await resolve_external_product(
                    db,
                    adapter,
                    context,
                    organization_id=organization_id,
                    external_product_id='product-001',
                )
                assert second.name == 'Canonical Hamburger'
                assert await db.scalar(
                    select(func.count(Product.id)).where(
                        Product.tenant_id == authority.tenant_id,
                        Product.name.in_(['Hamburger', 'Canonical Hamburger']),
                    )
                ) == 2
                assert await db.scalar(
                    select(func.count(ProductExternalMapping.id)).where(
                        ProductExternalMapping.tenant_id == authority.tenant_id
                    )
                ) == 1
                return first_id, second.id
        finally:
            await manager.dispose()

    with caplog.at_level(logging.INFO, logger='ecip.products'):
        first_id, second_id = asyncio.run(exercise())
    assert first_id == second_id
    assert first_id != existing_id
    rendered = ' '.join(record.getMessage() for record in caplog.records)
    for raw_value in ('product-001', 'Classic hamburger'):
        assert raw_value not in rendered


def test_catalog_resolution_case_distinct_mismatch_and_organization_fail_closed(
    integration_settings, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_a = _organization(connection, authority.tenant_id, 'ORG-A')
    organization_b = _organization(connection, authority.tenant_id, 'ORG-B')
    context = PosRequestContext(
        tenant_id=authority.tenant_id,
        connector_key='case-pos',
        correlation_id='case-resolution-test',
    )

    class EchoCatalogPort:
        async def get_product(self, context, *, product_external_id):
            return ExternalProduct(
                external_id=product_external_id,
                name='Same Name',
                status=ExternalEntityStatus.ACTIVE,
            )

        async def list_products(self, context):
            return ()

    class MismatchCatalogPort(EchoCatalogPort):
        async def get_product(self, context, *, product_external_id):
            return ExternalProduct(
                external_id='different-id',
                name='Mismatch',
                status=ExternalEntityStatus.ACTIVE,
            )

    async def exercise() -> tuple[int, int]:
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                upper = await resolve_external_product(
                    db,
                    EchoCatalogPort(),  # type: ignore[arg-type]
                    context,
                    organization_id=organization_a,
                    external_product_id='ABC',
                )
            async with manager.session_factory() as db:
                lower = await resolve_external_product(
                    db,
                    EchoCatalogPort(),  # type: ignore[arg-type]
                    context,
                    organization_id=organization_a,
                    external_product_id='abc',
                )
            async with manager.session_factory() as db:
                with pytest.raises(PosMappingError):
                    await resolve_external_product(
                        db,
                        EchoCatalogPort(),  # type: ignore[arg-type]
                        context,
                        organization_id=organization_b,
                        external_product_id='ABC',
                    )
            async with manager.session_factory() as db:
                with pytest.raises(PosMappingError):
                    await resolve_external_product(
                        db,
                        MismatchCatalogPort(),  # type: ignore[arg-type]
                        context,
                        organization_id=organization_a,
                        external_product_id='requested-id',
                    )
                assert await db.scalar(
                    select(func.count(ProductExternalMapping.id)).where(
                        ProductExternalMapping.tenant_id == authority.tenant_id,
                        ProductExternalMapping.external_product_id == 'requested-id',
                    )
                ) == 0
            return upper.id, lower.id
        finally:
            await manager.dispose()

    upper_id, lower_id = asyncio.run(exercise())
    assert upper_id != lower_id


def test_catalog_resolution_recovers_concurrent_mapping_race(
    integration_settings, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG-A')
    context = PosRequestContext(
        tenant_id=authority.tenant_id,
        connector_key='race-pos',
        correlation_id='race-resolution-test',
    )

    class BarrierCatalogPort:
        def __init__(self) -> None:
            self.calls = 0
            self.release = asyncio.Event()

        async def get_product(self, context, *, product_external_id):
            self.calls += 1
            if self.calls == 2:
                self.release.set()
            await self.release.wait()
            return ExternalProduct(
                external_id=product_external_id,
                name='Concurrent Product',
                status=ExternalEntityStatus.ACTIVE,
            )

        async def list_products(self, context):
            return ()

    async def exercise() -> tuple[int, int, int, int]:
        manager = DatabaseManager(integration_settings)
        port = BarrierCatalogPort()
        try:
            async with manager.session_factory() as first_db, manager.session_factory() as second_db:
                first, second = await asyncio.gather(
                    resolve_external_product(
                        first_db,
                        port,  # type: ignore[arg-type]
                        context,
                        organization_id=organization_id,
                        external_product_id='race-product',
                    ),
                    resolve_external_product(
                        second_db,
                        port,  # type: ignore[arg-type]
                        context,
                        organization_id=organization_id,
                        external_product_id='race-product',
                    ),
                )
            async with manager.session_factory() as db:
                product_count = await db.scalar(
                    select(func.count(Product.id)).where(
                        Product.tenant_id == authority.tenant_id,
                        Product.name == 'Concurrent Product',
                    )
                )
                mapping_count = await db.scalar(
                    select(func.count(ProductExternalMapping.id)).where(
                        ProductExternalMapping.tenant_id == authority.tenant_id,
                        ProductExternalMapping.connector_key == 'race-pos',
                    )
                )
            return first.id, second.id, int(product_count or 0), int(mapping_count or 0)
        finally:
            await manager.dispose()

    first_id, second_id, product_count, mapping_count = asyncio.run(exercise())
    assert first_id == second_id
    assert product_count == 1
    assert mapping_count == 1


def test_ws08_routes_have_no_delete_or_availability_endpoint(client) -> None:
    paths = client.app.openapi()['paths']
    for path, methods in paths.items():
        if path.startswith(('/products', '/product-categories', '/menus')):
            assert 'delete' not in methods
    assert '/products/{product_id}/availability' not in paths
