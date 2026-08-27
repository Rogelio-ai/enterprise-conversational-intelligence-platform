from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import create_app
from app.restaurant.commercial.service import round_payable_total


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_id: int
    conversation_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _scope(
    connection,
    prefix: str,
    *,
    permissions: tuple[str, ...] = ('order_draft.read', 'order_draft.manage'),
) -> Scope:
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES ('Commercial Tenant',%s,'ACTIVE')",
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
        (tenant_id, f'COMMERCIAL_{uuid4().hex}'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for code in permissions:
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
    location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,%s,'Location','America/Mexico_City','ACTIVE')",
        (tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'),
    )
    conversation_id = _execute(
        connection,
        "INSERT INTO conversations "
        "(tenant_id,organization_id,location_id,channel,status,next_message_sequence) "
        "VALUES (%s,%s,%s,'MOBILE_APP','ACTIVE',1)",
        (tenant_id, organization_id, location_id),
    )
    return Scope(tenant_id, organization_id, location_id, conversation_id, email)


def _product(connection, scope: Scope, name: str) -> int:
    return _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) "
        "VALUES (%s,%s,%s,'ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, name),
    )


def _expose(connection, scope: Scope, product_ids: tuple[int, ...]) -> None:
    menu_id = _execute(
        connection,
        "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,'Menu','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    _execute(
        connection,
        "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) "
        "VALUES (%s,%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, menu_id, scope.location_id),
    )
    section_id = _execute(
        connection,
        "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) "
        "VALUES (%s,%s,%s,'Section','ACTIVE')",
        (scope.tenant_id, scope.organization_id, menu_id),
    )
    for product_id in product_ids:
        _execute(
            connection,
            "INSERT INTO menu_items "
            "(tenant_id,organization_id,menu_id,section_id,product_id,status) "
            "VALUES (%s,%s,%s,%s,%s,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, menu_id, section_id, product_id),
        )


def _composition(connection, scope: Scope, parent_id: int, label: str):
    fixed_id = _product(connection, scope, f'{label} included side')
    option_id = _product(connection, scope, f'{label} included choice')
    composition_id = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) "
        "VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, parent_id),
    )
    _execute(
        connection,
        "INSERT INTO product_components "
        "(tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) "
        "VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id, fixed_id),
    )
    group_id = _execute(
        connection,
        "INSERT INTO product_choice_groups "
        "(tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) "
        "VALUES (%s,%s,%s,%s,1,1,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id, f'{label} choice'),
    )
    choice_option_id = _execute(
        connection,
        "INSERT INTO product_choice_options "
        "(tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) "
        "VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, group_id, option_id),
    )
    return fixed_id, option_id, group_id, choice_option_id


def _price(
    connection,
    scope: Scope,
    product_id: int,
    amount: str,
    *,
    currency: str = 'MXN',
    location_id: int | None = None,
) -> int:
    return _execute(
        connection,
        "INSERT INTO product_prices "
        "(tenant_id,organization_id,product_id,location_id,amount,currency,status,source) "
        "VALUES (%s,%s,%s,%s,%s,%s,'ACTIVE','PLATFORM')",
        (
            scope.tenant_id,
            scope.organization_id,
            product_id,
            location_id or scope.location_id,
            amount,
            currency,
        ),
    )


def _promotion(
    connection,
    scope: Scope,
    product_id: int,
    *,
    name: str,
    promotion_type: str,
    value: str,
    priority: int,
    combinable: bool,
    currency: str | None = None,
    active_now: bool = True,
    location_id: int | None = None,
) -> int:
    now = datetime.now(UTC).replace(tzinfo=None)
    starts_at = now - timedelta(hours=1) if active_now else now - timedelta(hours=3)
    ends_at = now + timedelta(hours=1) if active_now else now - timedelta(hours=2)
    all_locations = location_id is None
    promotion_id = _execute(
        connection,
        "INSERT INTO promotions "
        "(tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,"
        "applies_to_all_locations,is_combinable,priority,status,source) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE','PLATFORM')",
        (
            scope.tenant_id,
            scope.organization_id,
            name,
            promotion_type,
            value,
            currency,
            starts_at,
            ends_at,
            all_locations,
            combinable,
            priority,
        ),
    )
    _execute(
        connection,
        "INSERT INTO promotion_products "
        "(tenant_id,organization_id,promotion_id,product_id,status) "
        "VALUES (%s,%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, promotion_id, product_id),
    )
    if location_id is not None:
        _execute(
            connection,
            "INSERT INTO promotion_locations "
            "(tenant_id,organization_id,promotion_id,location_id,status) "
            "VALUES (%s,%s,%s,%s,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, promotion_id, location_id),
        )
    return promotion_id


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _draft(client: TestClient, scope: Scope, product_quantities: tuple[tuple[int, str], ...]):
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    for product_id, quantity in product_quantities:
        response = client.post(
            f"/order-drafts/{draft['draft_id']}/items",
            headers=headers,
            json={
                'product_id': product_id,
                'quantity': quantity,
                'expected_version': draft['version'],
            },
        )
        assert response.status_code == 201, response.text
        draft = response.json()
    return headers, draft


def _select(client, headers, draft, item_id, group_id, option_id):
    response = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item_id}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': [option_id], 'expected_version': draft['version']},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        ('145.01', '145.00'),
        ('145.10', '145.00'),
        ('145.49', '145.00'),
        ('145.50', '145.00'),
        ('145.51', '146.00'),
        ('145.99', '146.00'),
        ('146.50', '146.00'),
        ('146.51', '147.00'),
    ),
)
def test_commercial_rounding_policy(value, expected):
    assert round_payable_total(Decimal(value)) == Decimal(expected)
    with pytest.raises(TypeError):
        round_payable_total(float(value))


def test_ready_complex_menu_uses_only_parent_prices_and_rounds_once(
    client, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parents = tuple(
        _product(connection, scope, name)
        for name in ('Desayuno con elección', 'Paquete', 'Combo')
    )
    structures = tuple(
        _composition(connection, scope, parent_id, label)
        for parent_id, label in zip(parents, ('Breakfast', 'Package', 'Combo'), strict=True)
    )
    _expose(connection, scope, parents)
    parent_prices = tuple(
        _price(connection, scope, product_id, amount)
        for product_id, amount in zip(parents, ('72.5000', '50.0000', '22.5100'), strict=True)
    )
    for fixed_id, option_id, _, _ in structures:
        _price(connection, scope, fixed_id, '999.0000')
        _price(connection, scope, option_id, '888.0000')

    headers, draft = _draft(
        client, scope, ((parents[0], '2.0000'), (parents[1], '1'), (parents[2], '1'))
    )
    for item, structure in zip(draft['items'], structures, strict=True):
        draft = _select(client, headers, draft, item['item_id'], structure[2], structure[3])
    assert draft['readiness'] == 'READY'

    response = client.get(
        f"/order-drafts/{draft['draft_id']}/checkout-preview", headers=headers
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['status'] == 'COMPLETE'
    assert preview['draft_version'] == draft['version']
    assert preview['currency'] == 'MXN' and preview['tax_mode'] == 'INCLUDED'
    assert [line['price_id'] for line in preview['lines']] == list(parent_prices)
    assert [Decimal(line['base_amount']) for line in preview['lines']] == [
        Decimal('145.0000'),
        Decimal('50.0000'),
        Decimal('22.5100'),
    ]
    assert Decimal(preview['subtotal']) == Decimal('217.5100')
    assert Decimal(preview['total_discount']) == Decimal('0')
    assert Decimal(preview['pre_round_total']) == Decimal('217.5100')
    assert Decimal(preview['rounding_adjustment']) == Decimal('0.4900')
    assert Decimal(preview['payable_total']) == Decimal('218.00')
    assert len(preview['commercial_fingerprint']) == 64
    repeated = client.get(
        f"/order-drafts/{draft['draft_id']}/checkout-preview", headers=headers
    ).json()
    assert repeated['commercial_fingerprint'] == preview['commercial_fingerprint']


def test_readiness_revalidation_missing_price_and_wrong_location_are_explicit(
    client, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent = _product(connection, scope, 'Configurable meal')
    _, _, group_id, choice_id = _composition(connection, scope, parent, 'Meal')
    _expose(connection, scope, (parent,))
    headers = _headers(client, scope)
    empty = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    endpoint = f"/order-drafts/{empty['draft_id']}/checkout-preview"
    assert client.get(endpoint, headers=headers).status_code == 409

    added = client.post(
        f"/order-drafts/{empty['draft_id']}/items",
        headers=headers,
        json={'product_id': parent, 'quantity': '1', 'expected_version': empty['version']},
    ).json()
    assert added['readiness'] == 'INCOMPLETE'
    assert client.get(endpoint, headers=headers).status_code == 409
    ready = _select(
        client, headers, added, added['items'][0]['item_id'], group_id, choice_id
    )
    assert ready['readiness'] == 'READY'
    assert client.get(endpoint, headers=headers).status_code == 409

    other_location = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,'OTHER','Other','UTC','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    _price(connection, scope, parent, '90.0000', location_id=other_location)
    assert client.get(endpoint, headers=headers).status_code == 409
    _price(connection, scope, parent, '100.0000')
    assert client.get(endpoint, headers=headers).status_code == 200

    with connection.cursor() as cursor:
        cursor.execute("UPDATE products SET status='INACTIVE' WHERE id=%s", (parent,))
    invalid = client.get(endpoint, headers=headers)
    assert invalid.status_code == 409
    assert 'INVALID' in invalid.json()['error']['message']


def test_incompatible_line_currencies_fail_without_conversion(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    products = (_product(connection, scope, 'MXN item'), _product(connection, scope, 'USD item'))
    _expose(connection, scope, products)
    _price(connection, scope, products[0], '10.0000', currency='MXN')
    _price(connection, scope, products[1], '10.0000', currency='USD')
    headers, draft = _draft(client, scope, ((products[0], '1'), (products[1], '1')))
    response = client.get(
        f"/order-drafts/{draft['draft_id']}/checkout-preview", headers=headers
    )
    assert response.status_code == 409
    assert 'incompatible currencies' in response.json()['error']['message']


def test_non_combinable_promotions_use_priority_not_largest_discount(
    client, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product = _product(connection, scope, 'Priority item')
    _expose(connection, scope, (product,))
    _price(connection, scope, product, '100.0000')
    largest_id = _promotion(
        connection,
        scope,
        product,
        name='Largest but lower authority',
        promotion_type='PERCENTAGE_DISCOUNT',
        value='90',
        priority=20,
        combinable=False,
    )
    authoritative_id = _promotion(
        connection,
        scope,
        product,
        name='Priority authority',
        promotion_type='PERCENTAGE_DISCOUNT',
        value='10',
        priority=10,
        combinable=False,
    )
    _promotion(
        connection,
        scope,
        product,
        name='Expired',
        promotion_type='PERCENTAGE_DISCOUNT',
        value='99',
        priority=0,
        combinable=False,
        active_now=False,
    )
    headers, draft = _draft(client, scope, ((product, '1'),))
    preview = client.get(
        f"/order-drafts/{draft['draft_id']}/checkout-preview", headers=headers
    ).json()
    applied = preview['lines'][0]['applied_promotions']
    assert [value['promotion_id'] for value in applied] == [authoritative_id]
    assert applied[0]['promotion_id'] != largest_id
    assert Decimal(preview['total_discount']) == Decimal('10.0000')
    assert Decimal(preview['pre_round_total']) == Decimal('90.0000')


def test_combinable_promotions_are_stable_scoped_sequential_and_capped(
    client, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    products = (_product(connection, scope, 'Stack item'), _product(connection, scope, 'Cap item'))
    _expose(connection, scope, products)
    _price(connection, scope, products[0], '100.0000')
    _price(connection, scope, products[1], '5.0000')
    first_id = _promotion(
        connection,
        scope,
        products[0],
        name='Ten percent',
        promotion_type='PERCENTAGE_DISCOUNT',
        value='10',
        priority=5,
        combinable=True,
    )
    second_id = _promotion(
        connection,
        scope,
        products[0],
        name='Twenty fixed',
        promotion_type='FIXED_AMOUNT_DISCOUNT',
        value='20',
        currency='MXN',
        priority=5,
        combinable=True,
    )
    _promotion(
        connection,
        scope,
        products[0],
        name='Non-combinable lower authority',
        promotion_type='PERCENTAGE_DISCOUNT',
        value='80',
        priority=50,
        combinable=False,
    )
    _promotion(
        connection,
        scope,
        products[1],
        name='Capped fixed',
        promotion_type='FIXED_AMOUNT_DISCOUNT',
        value='10',
        currency='MXN',
        priority=1,
        combinable=True,
    )
    other_location = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,'PROMO-OTHER','Other','UTC','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    _promotion(
        connection,
        scope,
        products[0],
        name='Wrong location',
        promotion_type='PERCENTAGE_DISCOUNT',
        value='99',
        priority=0,
        combinable=True,
        location_id=other_location,
    )
    headers, draft = _draft(client, scope, ((products[0], '1'), (products[1], '1')))
    preview = client.get(
        f"/order-drafts/{draft['draft_id']}/checkout-preview", headers=headers
    ).json()
    first_line, second_line = preview['lines']
    assert [value['promotion_id'] for value in first_line['applied_promotions']] == [
        first_id,
        second_id,
    ]
    assert Decimal(first_line['discount_amount']) == Decimal('30.0000')
    assert Decimal(first_line['commercial_amount']) == Decimal('70.0000')
    assert Decimal(second_line['discount_amount']) == Decimal('5.0000')
    assert Decimal(second_line['commercial_amount']) == Decimal('0.0000')
    assert Decimal(preview['subtotal']) == Decimal('105.0000')
    assert Decimal(preview['total_discount']) == Decimal('35.0000')
    assert Decimal(preview['pre_round_total']) == Decimal('70.0000')


def test_rounding_occurs_after_summing_exact_lines(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    products = (_product(connection, scope, 'First half'), _product(connection, scope, 'Second half'))
    _expose(connection, scope, products)
    for product in products:
        _price(connection, scope, product, '72.5000')
    headers, draft = _draft(client, scope, ((products[0], '1'), (products[1], '1')))
    preview = client.get(
        f"/order-drafts/{draft['draft_id']}/checkout-preview", headers=headers
    ).json()
    assert [Decimal(line['commercial_amount']) for line in preview['lines']] == [
        Decimal('72.5000'),
        Decimal('72.5000'),
    ]
    assert Decimal(preview['pre_round_total']) == Decimal('145.0000')
    assert Decimal(preview['rounding_adjustment']) == Decimal('0.0000')
    assert Decimal(preview['payable_total']) == Decimal('145.00')


def test_preview_rbac_tenant_isolation_and_no_pos_side_effects(
    client, sql_connection, monkeypatch
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product = _product(connection, scope, 'Local price only')
    _expose(connection, scope, (product,))
    _price(connection, scope, product, '12.3400')
    headers, draft = _draft(client, scope, ((product, '1'),))
    endpoint = f"/order-drafts/{draft['draft_id']}/checkout-preview"
    monkeypatch.setattr(
        'app.restaurant.pricing.service.resolve_external_price',
        lambda *args, **kwargs: pytest.fail('Checkout Preview must not call a POS resolver'),
    )
    assert client.get(endpoint).status_code == 401

    forbidden = _scope(connection, f'{prefix}-forbidden', permissions=())
    assert client.get(endpoint, headers=_headers(client, forbidden)).status_code == 403
    isolated = _scope(connection, f'{prefix}-isolated', permissions=('order_draft.read',))
    assert client.get(endpoint, headers=_headers(client, isolated)).status_code == 404

    response = client.get(endpoint, headers=headers)
    assert response.status_code == 200
    preview = response.json()
    assert preview['tenant_id'] == scope.tenant_id
    assert preview['organization_id'] == scope.organization_id
    assert preview['location_id'] == scope.location_id
    assert preview['lines'][0]['price_source'] == 'PLATFORM'
    assert 'language' not in preview
