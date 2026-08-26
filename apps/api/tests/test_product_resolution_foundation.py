from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.restaurant.catalog import resolution, structure
from app.restaurant.catalog.resolution_contracts import (
    ChoiceResolutionRequest,
    MatchSource,
    ProductResolutionRequest,
    ResolutionStatus,
)


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_a: int
    location_b: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _scope(connection, prefix: str) -> Scope:
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES ('Resolution Tenant',%s,'ACTIVE')",
        (prefix,),
    )
    email = f'{prefix}@example.test'
    user_id = _execute(
        connection,
        "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'User','ACTIVE')",
        (email, hash_password(PASSWORD)),
    )
    membership_id = _execute(
        connection,
        "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')",
        (tenant_id, user_id),
    )
    role_id = _execute(
        connection,
        "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Role','ACTIVE')",
        (tenant_id, f'RESOLUTION_{uuid4().hex}'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for code in ('product.read', 'product.manage'):
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
            (role_id, permission_id),
        )
    organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Organization','ACTIVE')",
        (tenant_id, f'ORG-{uuid4().hex[:12]}'),
    )
    locations = tuple(
        _execute(
            connection,
            "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
            "VALUES (%s,%s,%s,%s,'America/Mexico_City','ACTIVE')",
            (tenant_id, organization_id, code, name),
        )
        for code, name in (('A', 'Location A'), ('B', 'Location B'))
    )
    return Scope(tenant_id, organization_id, locations[0], locations[1], email)


def _product(connection, scope: Scope, name: str, status: str = 'ACTIVE') -> int:
    return _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) "
        "VALUES (%s,%s,%s,%s,'PLATFORM')",
        (scope.tenant_id, scope.organization_id, name, status),
    )


def _expose(connection, scope: Scope, product_ids: tuple[int, ...]):
    menu_id = _execute(
        connection,
        "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, f'Menu-{uuid4().hex}'),
    )
    menu_location_id = _execute(
        connection,
        "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) "
        "VALUES (%s,%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, menu_id, scope.location_a),
    )
    section_id = _execute(
        connection,
        "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) "
        "VALUES (%s,%s,%s,'Section','ACTIVE')",
        (scope.tenant_id, scope.organization_id, menu_id),
    )
    item_ids = tuple(
        _execute(
            connection,
            "INSERT INTO menu_items "
            "(tenant_id,organization_id,menu_id,section_id,product_id,status) "
            "VALUES (%s,%s,%s,%s,%s,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, menu_id, section_id, product_id),
        )
        for product_id in product_ids
    )
    return menu_id, menu_location_id, section_id, item_ids


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


async def _with_session(settings, operation):
    manager = DatabaseManager(settings)
    try:
        async with manager.session_factory() as session:
            return await operation(session)
    finally:
        await manager.dispose()


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_normalization_is_bounded_deterministic_and_unicode_aware():
    assert resolution.normalize_reference('  Café\t  LATTE  ') == 'café latte'
    assert resolution.normalize_reference('ＣＡＦＥ\u0301') == resolution.normalize_reference('Café')
    assert resolution.normalize_reference('Straße') == 'strasse'
    with pytest.raises(ValueError, match='empty'):
        resolution.normalize_alias(' \n\t ')
    assert resolution.validate_language_tag('es-MX')
    assert not resolution.validate_language_tag('és-MX')


def test_product_alias_api_normalizes_scopes_lifecycle_and_duplicates(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id = _product(connection, scope, 'Canonical')
    sibling_org = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Sibling','ACTIVE')",
        (scope.tenant_id, f'SIB-{uuid4().hex[:12]}'),
    )
    other = _scope(connection, f'{prefix}-other')
    other_product = _product(connection, other, 'Other')
    headers = _headers(client, scope)

    payload = {
        'organization_id': scope.organization_id,
        'product_id': product_id,
        'alias': '  ＣＯＣＡ   Cola  ',
        'language': 'es-MX',
    }
    assert client.post('/product-aliases', json=payload).status_code == 401
    created = client.post('/product-aliases', headers=headers, json=payload)
    assert created.status_code == 201
    assert created.json()['normalized_alias'] == 'coca cola'
    assert created.json()['language'] == 'es-MX'
    duplicate = client.post(
        '/product-aliases', headers=headers, json={**payload, 'alias': 'coca cola'}
    )
    assert duplicate.status_code == 409
    for organization_id, invalid_product in (
        (sibling_org, product_id),
        (scope.organization_id, other_product),
    ):
        response = client.post(
            '/product-aliases',
            headers=headers,
            json={
                'organization_id': organization_id,
                'product_id': invalid_product,
                'alias': 'Invalid',
            },
        )
        assert response.status_code == 404
    listed = client.get(
        '/product-aliases',
        headers=headers,
        params={'organization_id': scope.organization_id, 'product_id': product_id},
    )
    assert listed.status_code == 200 and [item['id'] for item in listed.json()['items']] == [
        created.json()['id']
    ]
    patched = client.patch(
        f"/product-aliases/{created.json()['id']}",
        headers=headers,
        json={'alias': ' Nueva   Alias ', 'language': None, 'status': 'INACTIVE'},
    )
    assert patched.status_code == 200
    assert patched.json()['normalized_alias'] == 'nueva alias'
    assert patched.json()['language'] is None and patched.json()['status'] == 'INACTIVE'
    assert client.delete(
        f"/product-aliases/{created.json()['id']}", headers=headers
    ).status_code == 405


def test_product_resolution_is_menu_location_language_and_ambiguity_aware(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    coffee = _product(connection, scope, '  Café   Latte ')
    coke_small = _product(connection, scope, 'Cola 355')
    coke_large = _product(connection, scope, 'Cola 600')
    inactive = _product(connection, scope, 'Inactive Product', status='INACTIVE')
    _expose(connection, scope, (coffee, coke_small, coke_large, inactive))
    _execute(
        connection,
        "INSERT INTO product_aliases "
        "(tenant_id,organization_id,product_id,alias,normalized_alias,language,status) "
        "VALUES (%s,%s,%s,'Café Latte','café latte','','ACTIVE')",
        (scope.tenant_id, scope.organization_id, coffee),
    )
    _execute(
        connection,
        "INSERT INTO product_aliases "
        "(tenant_id,organization_id,product_id,alias,normalized_alias,language,status) "
        "VALUES (%s,%s,%s,'Sleeping','sleeping','','INACTIVE')",
        (scope.tenant_id, scope.organization_id, coffee),
    )
    for product_id in (coke_small, coke_large):
        _execute(
            connection,
            "INSERT INTO product_aliases "
            "(tenant_id,organization_id,product_id,alias,normalized_alias,language,status) "
            "VALUES (%s,%s,%s,'Coca','coca','es-MX','ACTIVE')",
            (scope.tenant_id, scope.organization_id, product_id),
        )
    other_scope = _scope(connection, f'{prefix}-resolver-other')

    async def scenario(session):
        canonical = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id, scope.organization_id, scope.location_a, 'CAFÉ LATTE'
            ),
        )
        wrong_location = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id, scope.organization_id, scope.location_b, 'café latte'
            ),
        )
        ambiguous = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id, scope.organization_id, scope.location_a, 'coca', 'es-MX'
            ),
        )
        wrong_language = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id, scope.organization_id, scope.location_a, 'coca', 'en-US'
            ),
        )
        inactive_alias = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id, scope.organization_id, scope.location_a, 'sleeping'
            ),
        )
        inactive_result = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id,
                scope.organization_id,
                scope.location_a,
                'inactive product',
            ),
        )
        invalid = await resolution.resolve_product(
            session,
            ProductResolutionRequest(scope.tenant_id, scope.organization_id, None, 'coffee'),
        )
        cross_tenant = await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id,
                scope.organization_id,
                other_scope.location_a,
                'café latte',
            ),
        )
        return (
            canonical,
            wrong_location,
            ambiguous,
            wrong_language,
            inactive_alias,
            inactive_result,
            invalid,
            cross_tenant,
        )

    (
        canonical,
        wrong_location,
        ambiguous,
        wrong_language,
        inactive_alias,
        inactive_result,
        invalid,
        cross_tenant,
    ) = asyncio.run(_with_session(integration_settings, scenario))
    assert canonical.status == ResolutionStatus.RESOLVED
    assert canonical.candidate.product_id == coffee
    assert canonical.candidate.matched_by == MatchSource.CANONICAL_NAME
    assert wrong_location.status == ResolutionStatus.NOT_ORDERABLE
    assert ambiguous.status == ResolutionStatus.AMBIGUOUS
    assert [candidate.product_id for candidate in ambiguous.candidates] == sorted(
        (coke_small, coke_large)
    )
    assert wrong_language.status == ResolutionStatus.NOT_FOUND
    assert inactive_alias.status == ResolutionStatus.NOT_FOUND
    assert inactive_result.status == ResolutionStatus.NOT_ORDERABLE
    assert invalid.status == ResolutionStatus.INVALID_CONTEXT
    assert cross_tenant.status == ResolutionStatus.INVALID_CONTEXT


@pytest.mark.parametrize('disabled_level', ['menu_location', 'menu', 'section', 'item'])
def test_inactive_menu_chain_suppresses_orderability(
    disabled_level, integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id = _product(connection, scope, 'Orderable Product')
    menu_id, menu_location_id, section_id, item_ids = _expose(connection, scope, (product_id,))
    target = {
        'menu_location': ('menu_locations', menu_location_id),
        'menu': ('menus', menu_id),
        'section': ('menu_sections', section_id),
        'item': ('menu_items', item_ids[0]),
    }[disabled_level]
    with connection.cursor() as cursor:
        cursor.execute(f'UPDATE {target[0]} SET status=\'INACTIVE\' WHERE id=%s', (target[1],))

    async def scenario(session):
        return await resolution.resolve_product(
            session,
            ProductResolutionRequest(
                scope.tenant_id, scope.organization_id, scope.location_a, 'orderable product'
            ),
        )

    result = asyncio.run(_with_session(integration_settings, scenario))
    assert result.status == ResolutionStatus.NOT_ORDERABLE


def test_choice_resolution_is_composition_bounded_and_reuses_ws12_validation(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent = _product(connection, scope, 'Breakfast')
    juice = _product(connection, scope, 'Juice')
    coffee = _product(connection, scope, 'Coffee')
    outsider = _product(connection, scope, 'Outside')
    _execute(
        connection,
        "INSERT INTO product_aliases "
        "(tenant_id,organization_id,product_id,alias,normalized_alias,language,status) "
        "VALUES (%s,%s,%s,'Jugo','jugo','es-MX','ACTIVE')",
        (scope.tenant_id, scope.organization_id, juice),
    )
    composition_id = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) "
        "VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, parent),
    )
    group_ids = tuple(
        _execute(
            connection,
            "INSERT INTO product_choice_groups "
            "(tenant_id,organization_id,composition_id,name,min_selections,max_selections,status) "
            "VALUES (%s,%s,%s,%s,0,1,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, composition_id, name),
        )
        for name in ('Drink', 'Second drink')
    )
    juice_options = tuple(
        _execute(
            connection,
            "INSERT INTO product_choice_options "
            "(tenant_id,organization_id,group_id,option_product_id,quantity,status) "
            "VALUES (%s,%s,%s,%s,1,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, group_id, juice),
        )
        for group_id in group_ids
    )
    _execute(
        connection,
        "INSERT INTO product_choice_options "
        "(tenant_id,organization_id,group_id,option_product_id,quantity,status) "
        "VALUES (%s,%s,%s,%s,1,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, group_ids[0], coffee),
    )
    inactive_option_product = _product(connection, scope, 'Milk')
    _execute(
        connection,
        "INSERT INTO product_choice_options "
        "(tenant_id,organization_id,group_id,option_product_id,quantity,status) "
        "VALUES (%s,%s,%s,%s,1,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, group_ids[0], inactive_option_product),
    )
    inactive_group = _execute(
        connection,
        "INSERT INTO product_choice_groups "
        "(tenant_id,organization_id,composition_id,name,min_selections,max_selections,status) "
        "VALUES (%s,%s,%s,'Inactive group',0,1,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    hidden_product = _product(connection, scope, 'Hidden Choice')
    _execute(
        connection,
        "INSERT INTO product_choice_options "
        "(tenant_id,organization_id,group_id,option_product_id,quantity,status) "
        "VALUES (%s,%s,%s,%s,1,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, inactive_group, hidden_product),
    )

    async def scenario(session):
        ambiguous = await resolution.resolve_choice(
            session,
            ChoiceResolutionRequest(
                scope.tenant_id, scope.organization_id, parent, 'jugo', 'es-MX'
            ),
        )
        resolved = await resolution.resolve_choice(
            session,
            ChoiceResolutionRequest(
                scope.tenant_id,
                scope.organization_id,
                parent,
                'jugo',
                'es-MX',
                group_ids[0],
            ),
        )
        invalid_option = await resolution.resolve_choice(
            session,
            ChoiceResolutionRequest(
                scope.tenant_id, scope.organization_id, parent, 'outside'
            ),
        )
        inactive_option = await resolution.resolve_choice(
            session,
            ChoiceResolutionRequest(scope.tenant_id, scope.organization_id, parent, 'milk'),
        )
        inactive_group_result = await resolution.resolve_choice(
            session,
            ChoiceResolutionRequest(
                scope.tenant_id, scope.organization_id, parent, 'hidden choice'
            ),
        )
        validation = await structure.validate_selection(
            session,
            tenant_id=scope.tenant_id,
            product_id=parent,
            selections=(structure.ChoiceSelection(group_ids[0], (juice_options[0],)),),
        )
        return (
            ambiguous,
            resolved,
            invalid_option,
            inactive_option,
            inactive_group_result,
            validation,
        )

    (
        ambiguous,
        resolved,
        invalid_option,
        inactive_option,
        inactive_group_result,
        validation,
    ) = asyncio.run(_with_session(integration_settings, scenario))
    assert ambiguous.status == ResolutionStatus.AMBIGUOUS
    assert [(item.choice_group_id, item.choice_option_id) for item in ambiguous.candidates] == [
        (group_ids[0], juice_options[0]),
        (group_ids[1], juice_options[1]),
    ]
    assert resolved.status == ResolutionStatus.RESOLVED
    assert resolved.candidate.choice_option_id == juice_options[0]
    assert resolved.candidate.matched_by == MatchSource.ALIAS
    assert invalid_option.status == ResolutionStatus.NOT_FOUND
    assert inactive_option.status == ResolutionStatus.NOT_FOUND
    assert inactive_group_result.status == ResolutionStatus.NOT_FOUND
    assert validation.is_valid
    assert validation.selected_options[0].option_id == juice_options[0]


def test_product_alias_raw_scope_foreign_keys_and_identity_are_enforced(sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    sibling_org = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Sibling','ACTIVE')",
        (scope.tenant_id, f'SIB-{uuid4().hex[:12]}'),
    )
    product_id = _product(connection, scope, 'Scoped')
    other = _scope(connection, f'{prefix}-other')
    other_product = _product(connection, other, 'Other')
    statement = (
        "INSERT INTO product_aliases "
        "(tenant_id,organization_id,product_id,alias,normalized_alias,language,status) "
        "VALUES (%s,%s,%s,'Alias','alias','','ACTIVE')"
    )
    for parameters in (
        (scope.tenant_id, sibling_org, product_id),
        (scope.tenant_id, scope.organization_id, other_product),
        (other.tenant_id, other.organization_id, product_id),
    ):
        with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
            _execute(connection, statement, parameters)
    _execute(connection, statement, (scope.tenant_id, scope.organization_id, product_id))
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(connection, statement, (scope.tenant_id, scope.organization_id, product_id))
