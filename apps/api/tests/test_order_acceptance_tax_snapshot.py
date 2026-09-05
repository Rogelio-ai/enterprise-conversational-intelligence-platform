from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.orders import acceptance
from app.restaurant.tax.contracts import ResolvedTaxEvidence, TaxEffect, TaxTreatment
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _execute,
    _open_and_join,
    _preview,
    _product,
    _scope,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _default_rule(connection, product_id: int) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT r.* FROM restaurant_tax_rules r '
            'JOIN products p ON p.tenant_id=r.tenant_id '
            'AND p.organization_id=r.organization_id '
            'AND p.tax_classification_code=r.tax_classification_code '
            'WHERE p.id=%s AND r.location_id IS NULL ORDER BY r.id',
            (product_id,),
        )
        return cursor.fetchone()


def _snapshot(connection, order_id: int) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT s.*,o.accepted_at,o.commercial_fingerprint,o.fingerprint_schema_version '
            'FROM restaurant_order_item_tax_snapshots s '
            'JOIN restaurant_orders o ON o.id=s.restaurant_order_id '
            'WHERE s.restaurant_order_id=%s ORDER BY s.id',
            (order_id,),
        )
        return cursor.fetchone()


def _counts(connection, tenant_id: int) -> tuple[int, int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s',
            (tenant_id,),
        )
        orders = cursor.fetchone()['count']
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_order_items WHERE tenant_id=%s',
            (tenant_id,),
        )
        items = cursor.fetchone()['count']
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_order_item_tax_snapshots '
            'WHERE tenant_id=%s',
            (tenant_id,),
        )
        snapshots = cursor.fetchone()['count']
    return orders, items, snapshots


def _accept(client, connection, scope, *, amount='116.0000', key='tax-accept'):
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, amount=amount)
    preview = _preview(client, diner_headers, product_id)
    response = _confirm(client, diner_headers, preview, key)
    return product_id, preview, response, diner_headers


@pytest.mark.parametrize(
    ('treatment', 'rate', 'amount', 'expected_base', 'expected_tax'),
    [
        ('TAXABLE', '0.160000', '116.0000', '100.0000', '16.0000'),
        ('ZERO_RATE', '0.000000', '100.0000', '100.0000', '0.0000'),
        ('EXEMPT', '0.000000', '100.0000', '100.0000', '0.0000'),
    ],
)
def test_acceptance_persists_explicit_tax_treatment_evidence(
    client, sql_connection, treatment, rate, amount, expected_base, expected_tax,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, amount=amount)
    rule = _default_rule(connection, product_id)
    connection.cursor().execute(
        'UPDATE restaurant_tax_rules SET tax_treatment=%s,tax_rate=%s WHERE id=%s',
        (treatment, rate, rule['id']),
    )
    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, f'{treatment}-accept')
    assert accepted.status_code == 201, accepted.text

    snapshot = _snapshot(connection, accepted.json()['id'])
    assert snapshot['source_tax_rule_id'] == rule['id']
    assert snapshot['tax_treatment'] == treatment
    assert snapshot['tax_effect'] == 'TRANSFERRED'
    assert snapshot['tax_rate'] == Decimal(rate)
    assert snapshot['fiscal_unit_value'] == Decimal(expected_base)
    assert snapshot['fiscal_line_amount'] == Decimal(expected_base)
    assert snapshot['fiscal_discount_amount'] == Decimal('0.0000')
    assert snapshot['taxable_base'] == Decimal(expected_base)
    assert snapshot['tax_amount'] == Decimal(expected_tax)
    assert snapshot['jurisdiction_code'] == rule['jurisdiction_code']
    assert snapshot['calculation_policy'] == rule['calculation_policy']
    assert snapshot['rounding_policy'] == rule['rounding_policy']


@pytest.mark.parametrize('failure', ['classification', 'rule', 'ambiguous'])
def test_tax_resolution_failure_is_atomic(client, sql_connection, failure) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope)
    rule = _default_rule(connection, product_id)
    if failure == 'classification':
        connection.cursor().execute(
            'UPDATE products SET tax_classification_code=NULL WHERE id=%s', (product_id,)
        )
    elif failure == 'rule':
        connection.cursor().execute(
            'DELETE FROM restaurant_tax_rules WHERE id=%s', (rule['id'],)
        )
    else:
        _execute(
            connection,
            "INSERT INTO restaurant_tax_rules (tenant_id,organization_id,location_id,"
            "tax_classification_code,jurisdiction_code,tax_category,tax_treatment,tax_rate,"
            "calculation_policy,rounding_policy,effective_from,status) "
            "VALUES (%s,%s,NULL,%s,'OTHER','SALES_TAX','TAXABLE',0.080000,"
            "'INCLUDED_PRICE_SINGLE_TAX','DECIMAL_4_HALF_UP',CURRENT_TIMESTAMP - INTERVAL 1 DAY,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, rule['tax_classification_code']),
        )
    preview = _preview(client, diner_headers, product_id)
    rejected = _confirm(client, diner_headers, preview, f'{failure}-failure')
    assert rejected.status_code == 409
    assert _counts(connection, scope.tenant_id) == (0, 0, 0)


def test_location_override_and_organization_default_are_frozen(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id, _, first, diner_headers = _accept(
        client, connection, scope, key='default-rule'
    )
    assert first.status_code == 201, first.text
    default_snapshot = _snapshot(connection, first.json()['id'])
    default_rule = _default_rule(connection, product_id)
    assert default_snapshot['source_tax_rule_id'] == default_rule['id']

    override_id = _execute(
        connection,
        "INSERT INTO restaurant_tax_rules (tenant_id,organization_id,location_id,"
        "tax_classification_code,jurisdiction_code,tax_category,tax_treatment,tax_rate,"
        "calculation_policy,rounding_policy,effective_from,status) "
        "VALUES (%s,%s,%s,%s,'LOCATION','SALES_TAX','TAXABLE',0.100000,"
        "'INCLUDED_PRICE_SINGLE_TAX','DECIMAL_4_HALF_UP',CURRENT_TIMESTAMP - INTERVAL 1 DAY,'ACTIVE')",
        (
            scope.tenant_id,
            scope.organization_id,
            scope.location_id,
            default_rule['tax_classification_code'],
        ),
    )
    second_preview = _preview(client, diner_headers, product_id)
    second = _confirm(client, diner_headers, second_preview, 'location-rule')
    assert second.status_code == 201, second.text
    override_snapshot = _snapshot(connection, second.json()['id'])
    assert override_snapshot['source_tax_rule_id'] == override_id
    assert override_snapshot['jurisdiction_code'] == 'LOCATION'
    assert override_snapshot['tax_rate'] == Decimal('0.100000')
    assert default_snapshot['source_tax_rule_id'] == default_rule['id']


def test_resolver_fingerprint_and_single_acceptance_instant_are_persisted(
    client, sql_connection, monkeypatch,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    first_product = _product(connection, scope, amount='50.0000')
    second_product = _product(connection, scope, amount='66.0000')
    draft = client.post('/diner/order-draft', headers=diner_headers).json()
    first = client.post('/diner/order-draft/items', headers=diner_headers, json={
        'product_id': first_product, 'quantity': '1', 'expected_version': draft['version'],
    }).json()
    client.post('/diner/order-draft/items', headers=diner_headers, json={
        'product_id': second_product, 'quantity': '1', 'expected_version': first['version'],
    })
    preview = client.get('/diner/checkout-preview', headers=diner_headers).json()
    rule_id = _default_rule(connection, first_product)['id']
    fingerprints = iter(('a' * 64, 'b' * 64))

    async def resolved(db, candidate):
        return ResolvedTaxEvidence(
            source_tax_rule_id=rule_id,
            tax_category='SALES_TAX',
            tax_treatment=TaxTreatment.EXEMPT,
            tax_effect=TaxEffect.TRANSFERRED,
            tax_rate=Decimal('0.000000'),
            fiscal_unit_value=candidate.unit_price,
            fiscal_line_amount=candidate.base_amount,
            fiscal_discount_amount=candidate.discount_amount,
            taxable_base=candidate.commercial_amount,
            tax_amount=Decimal('0.0000'),
            jurisdiction_code='TEST-JURISDICTION',
            calculation_policy='INCLUDED_PRICE_SINGLE_TAX',
            rounding_policy='DECIMAL_4_HALF_UP',
            schema_version=2,
            evidence_fingerprint=next(fingerprints),
        )

    monkeypatch.setattr(acceptance.tax_service, 'resolve_tax_evidence', resolved)
    accepted = _confirm(client, diner_headers, preview, 'fingerprint-instant')
    assert accepted.status_code == 201, accepted.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT evidence_fingerprint,created_at FROM '
            'restaurant_order_item_tax_snapshots WHERE restaurant_order_id=%s ORDER BY id',
            (accepted.json()['id'],),
        )
        snapshots = cursor.fetchall()
        cursor.execute(
            'SELECT accepted_at,commercial_fingerprint,fingerprint_schema_version '
            'FROM restaurant_orders WHERE id=%s',
            (accepted.json()['id'],),
        )
        order = cursor.fetchone()
        cursor.execute(
            'SELECT evidence_fingerprint FROM restaurant_order_item_fiscal_snapshots '
            'WHERE restaurant_order_id=%s ORDER BY restaurant_order_item_id',
            (accepted.json()['id'],),
        )
        fiscal_snapshots = cursor.fetchall()
    assert [value['evidence_fingerprint'] for value in snapshots] == ['a' * 64, 'b' * 64]
    assert {value['created_at'] for value in snapshots} == {order['accepted_at']}
    assert order['fingerprint_schema_version'] == 3
    assert order['commercial_fingerprint'] == acceptance._accepted_fingerprint(
        preview['commercial_fingerprint'],
        tuple(
            (line['draft_item_id'], fingerprint)
            for line, fingerprint in zip(preview['lines'], ('a' * 64, 'b' * 64))
        ),
        tuple(
            (line['draft_item_id'], snapshot['evidence_fingerprint'])
            for line, snapshot in zip(preview['lines'], fiscal_snapshots)
        ),
    )


def test_replay_does_not_duplicate_tax_snapshot(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, preview, accepted, diner_headers = _accept(client, connection, scope)
    assert accepted.status_code == 201, accepted.text
    original = _snapshot(connection, accepted.json()['id'])
    replay = _confirm(client, diner_headers, preview, 'tax-accept')
    assert replay.status_code == 200
    assert _snapshot(connection, accepted.json()['id']) == original
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count,MIN(evidence_fingerprint) AS fingerprint, '
            'MIN(fiscal_line_amount) AS fiscal_line_amount '
            'FROM restaurant_order_item_tax_snapshots '
            'WHERE restaurant_order_id=%s',
            (accepted.json()['id'],),
        )
        frozen = cursor.fetchone()
        assert frozen['count'] == 1
        assert frozen['fingerprint']
        assert frozen['fiscal_line_amount'] is not None


def test_promotion_discount_is_the_taxable_commercial_basis(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, amount='116.0000')
    promotion_id = _execute(
        connection,
        "INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,"
        "benefit_value,starts_at,ends_at,applies_to_all_locations,is_combinable,priority,"
        "status,source) VALUES (%s,%s,'Discount','PERCENTAGE_DISCOUNT',10,"
        "CURRENT_TIMESTAMP - INTERVAL 1 DAY,CURRENT_TIMESTAMP + INTERVAL 1 DAY,1,0,1,"
        "'ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id),
    )
    _execute(
        connection,
        "INSERT INTO promotion_products (tenant_id,organization_id,promotion_id,product_id,"
        "status) VALUES (%s,%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, promotion_id, product_id),
    )
    preview = _preview(client, diner_headers, product_id)
    assert Decimal(preview['lines'][0]['commercial_amount']) == Decimal('104.4000')
    accepted = _confirm(client, diner_headers, preview, 'discounted-tax')
    assert accepted.status_code == 201, accepted.text
    snapshot = _snapshot(connection, accepted.json()['id'])
    assert snapshot['fiscal_unit_value'] == Decimal('100.0000')
    assert snapshot['fiscal_line_amount'] == Decimal('100.0000')
    assert snapshot['fiscal_discount_amount'] == Decimal('10.0000')
    assert snapshot['taxable_base'] == Decimal('90.0000')
    assert snapshot['tax_amount'] == Decimal('14.4000')
    assert snapshot['fiscal_line_amount'] - snapshot['fiscal_discount_amount'] == (
        snapshot['taxable_base']
    )


def test_new_acceptance_does_not_mutate_historical_tax_evidence_or_other_domains(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id, _, first, diner_headers = _accept(client, connection, scope, key='historical')
    assert first.status_code == 201, first.text
    historical = _snapshot(connection, first.json()['id'])
    rule = _default_rule(connection, product_id)
    connection.cursor().execute(
        'UPDATE restaurant_tax_rules SET tax_rate=0.100000 WHERE id=%s', (rule['id'],)
    )
    second_preview = _preview(client, diner_headers, product_id)
    second = _confirm(client, diner_headers, second_preview, 'current')
    assert second.status_code == 201, second.text
    assert _snapshot(connection, first.json()['id']) == historical
    with connection.cursor() as cursor:
        for table in ('billing_documents', 'restaurant_payments', 'restaurant_check_settlements'):
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (scope.tenant_id,))
            assert cursor.fetchone()['count'] == 0
