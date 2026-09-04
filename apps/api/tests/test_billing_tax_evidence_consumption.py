from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.tax import service as tax_service
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _execute,
    _open_and_join,
    _preview,
    _product,
    _scope,
    _staff_headers,
)
from test_restaurant_payment_settlement_foundation import _check, _grant


@dataclass(frozen=True)
class BillingSource:
    scope: object
    diner_headers: dict[str, str]
    product_id: int
    order_id: int
    order_item_id: int
    tax_rule_id: int
    check_id: int
    issuer_profile_id: int
    recipient_profile_id: int


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _profiles(connection, scope) -> tuple[int, int]:
    issuer_id = _execute(
        connection,
        "INSERT INTO issuer_fiscal_profiles (tenant_id,organization_id,legal_name,"
        "tax_identifier,tax_regime,fiscal_postal_code,status) "
        "VALUES (%s,%s,'Issuer Legal','ISSUER-ID','GENERAL','01000','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    customer_id = _execute(
        connection,
        "INSERT INTO customers (tenant_id,display_name,status,source) "
        "VALUES (%s,'Billing Customer','ACTIVE','PLATFORM')",
        (scope.tenant_id,),
    )
    recipient_id = _execute(
        connection,
        "INSERT INTO customer_fiscal_profiles (tenant_id,customer_id,legal_name,"
        "tax_identifier,tax_regime,fiscal_postal_code,invoice_usage,status) "
        "VALUES (%s,%s,'Recipient Legal','RECIPIENT-ID','GENERAL','02000',"
        "'GENERAL_EXPENSE','ACTIVE')",
        (scope.tenant_id, customer_id),
    )
    return issuer_id, recipient_id


def _source(
    client,
    connection,
    prefix: str,
    *,
    amount='116.0000',
    treatment='TAXABLE',
    rate='0.160000',
    two_items: bool = False,
) -> BillingSource:
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, amount=amount)
    connection.cursor().execute(
        'UPDATE restaurant_tax_rules SET tax_treatment=%s,tax_rate=%s '
        'WHERE tenant_id=%s AND organization_id=%s AND tax_classification_code='
        '(SELECT tax_classification_code FROM products WHERE id=%s)',
        (treatment, rate, scope.tenant_id, scope.organization_id, product_id),
    )
    if two_items:
        second_product_id = _product(connection, scope, name='Second item', amount=amount)
        draft = client.post('/diner/order-draft', headers=diner_headers).json()
        first = client.post('/diner/order-draft/items', headers=diner_headers, json={
            'product_id': product_id, 'quantity': '1', 'expected_version': draft['version'],
        }).json()
        client.post('/diner/order-draft/items', headers=diner_headers, json={
            'product_id': second_product_id,
            'quantity': '1',
            'expected_version': first['version'],
        })
        preview = client.get('/diner/checkout-preview', headers=diner_headers).json()
    else:
        preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, 'billing-source-order')
    assert accepted.status_code == 201, accepted.text
    order_id = accepted.json()['id']
    check = _check(client, diner_headers, 'billing-source-check')
    diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
    paid = client.post(
        f"/restaurant-checks/{check['id']}/payments",
        headers={**_staff_headers(client, scope), 'Idempotency-Key': 'billing-source-cash'},
        json={
            'expected_check_version': check['version'],
            'expected_check_fingerprint': check['fingerprint'],
            'amount': check['liability_total'],
            'currency': check['currency'],
            'method_category': 'CASH',
            'payer_type': 'DINER',
            'payer_diner_session_id': diner_id,
            'cash_tendered_amount': check['liability_total'],
        },
    )
    assert paid.status_code == 201, paid.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT i.id AS item_id,s.source_tax_rule_id FROM restaurant_order_items i '
            'JOIN restaurant_order_item_tax_snapshots s '
            'ON s.restaurant_order_item_id=i.id WHERE i.order_id=%s',
            (order_id,),
        )
        evidence = cursor.fetchone()
        cursor.execute(
            'SELECT status FROM restaurant_checks WHERE id=%s', (check['id'],)
        )
        assert cursor.fetchone()['status'] == 'SETTLED'
    issuer_id, recipient_id = _profiles(connection, scope)
    return BillingSource(
        scope=scope,
        diner_headers=diner_headers,
        product_id=product_id,
        order_id=order_id,
        order_item_id=evidence['item_id'],
        tax_rule_id=evidence['source_tax_rule_id'],
        check_id=check['id'],
        issuer_profile_id=issuer_id,
        recipient_profile_id=recipient_id,
    )


def _payload(source: BillingSource, *, recipient_id: int | None = None) -> dict:
    return {
        'organization_id': source.scope.organization_id,
        'location_id': source.scope.location_id,
        'issuer_fiscal_profile_id': source.issuer_profile_id,
        'recipient_fiscal_profile_id': recipient_id or source.recipient_profile_id,
    }


def _bill(client, source: BillingSource, *, key='billing-tax'):
    return client.post(
        f'/restaurant-checks/{source.check_id}/billing-documents',
        headers={**_staff_headers(client, source.scope), 'Idempotency-Key': key},
        json=_payload(source),
    )


def _detail(client, source: BillingSource, document_id: int) -> dict:
    response = client.get(
        f'/billing-documents/{document_id}',
        headers=_staff_headers(client, source.scope),
        params={
            'organization_id': source.scope.organization_id,
            'location_id': source.scope.location_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ('treatment', 'rate', 'amount', 'expected_base', 'expected_tax'),
    [
        ('TAXABLE', '0.160000', '116.0000', '100.0000', '16.0000'),
        ('ZERO_RATE', '0.000000', '100.0000', '100.0000', '0.0000'),
        ('EXEMPT', '0.000000', '100.0000', '100.0000', '0.0000'),
    ],
)
def test_billing_copies_authoritative_tax_evidence_exactly(
    client, sql_connection, treatment, rate, amount, expected_base, expected_tax,
) -> None:
    connection, prefix = sql_connection
    source = _source(
        client, connection, prefix, amount=amount, treatment=treatment, rate=rate
    )
    billed = _bill(client, source, key=f'billing-{treatment}')
    assert billed.status_code == 201, billed.text
    detail = _detail(client, source, billed.json()['id'])
    tax = detail['lines'][0]['taxes'][0]
    assert tax['tax_category'] == 'SALES_TAX'
    assert Decimal(tax['tax_rate']) == Decimal(rate)
    assert Decimal(tax['taxable_base']) == Decimal(expected_base)
    assert Decimal(tax['tax_amount']) == Decimal(expected_tax)
    assert tax['tax_treatment'] == treatment
    assert Decimal(detail['tax_total']) == Decimal(expected_tax)


def test_multiple_snapshots_create_multiple_line_taxes_and_authoritative_total(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    original = None
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT * FROM restaurant_order_item_tax_snapshots '
            'WHERE restaurant_order_item_id=%s',
            (source.order_item_id,),
        )
        original = cursor.fetchone()
    _execute(
        connection,
        "INSERT INTO restaurant_order_item_tax_snapshots (tenant_id,organization_id,"
        "location_id,restaurant_order_id,restaurant_order_item_id,source_tax_rule_id,"
        "tax_category,tax_treatment,tax_rate,taxable_base,tax_amount,jurisdiction_code,"
        "calculation_policy,rounding_policy,schema_version,evidence_fingerprint) "
        "VALUES (%s,%s,%s,%s,%s,%s,'SECONDARY','ZERO_RATE',0.000000,116.0000,0.0000,"
        "'SECONDARY','INCLUDED_PRICE_SINGLE_TAX','DECIMAL_4_HALF_UP',1,%s)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            source.order_id,
            source.order_item_id,
            source.tax_rule_id,
            'c' * 64,
        ),
    )
    billed = _bill(client, source)
    assert billed.status_code == 201, billed.text
    detail = _detail(client, source, billed.json()['id'])
    assert len(detail['lines'][0]['taxes']) == 2
    assert Decimal(detail['tax_total']) == Decimal(original['tax_amount'])
    assert Decimal(detail['total']) == Decimal('116.0000')


@pytest.mark.parametrize('missing', ['all', 'one_of_mixed'])
def test_missing_tax_snapshot_blocks_entire_billing_document(
    client, sql_connection, missing,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix, two_items=missing == 'one_of_mixed')
    if missing == 'one_of_mixed':
        connection.cursor().execute(
            'DELETE FROM restaurant_order_item_tax_snapshots '
            'WHERE restaurant_order_id=%s AND restaurant_order_item_id<>%s',
            (source.order_id, source.order_item_id),
        )
    else:
        connection.cursor().execute(
            'DELETE FROM restaurant_order_item_tax_snapshots '
            'WHERE restaurant_order_item_id=%s',
            (source.order_item_id,),
        )
    rejected = _bill(client, source, key=f'missing-{missing}')
    assert rejected.status_code == 409
    assert rejected.json()['error']['code'] == 'BILLING_TAX_EVIDENCE_UNAVAILABLE'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_documents WHERE tenant_id=%s',
            (source.scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0


def test_billing_uses_historical_snapshot_after_product_and_rule_changes(
    client, sql_connection, monkeypatch,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tax_rate,taxable_base,tax_amount,tax_treatment FROM '
            'restaurant_order_item_tax_snapshots WHERE restaurant_order_item_id=%s',
            (source.order_item_id,),
        )
        accepted_tax = cursor.fetchone()
        cursor.execute(
            "UPDATE products SET tax_classification_code='CHANGED' WHERE id=%s",
            (source.product_id,),
        )
        cursor.execute(
            "UPDATE restaurant_tax_rules SET status='INACTIVE',tax_rate=0.990000 "
            'WHERE id=%s',
            (source.tax_rule_id,),
        )

    async def forbidden_resolution(*_args, **_kwargs):
        raise AssertionError('Billing must not invoke the tax resolver')

    monkeypatch.setattr(tax_service, 'resolve_tax_evidence', forbidden_resolution)
    billed = _bill(client, source)
    assert billed.status_code == 201, billed.text
    tax = _detail(client, source, billed.json()['id'])['lines'][0]['taxes'][0]
    assert Decimal(tax['tax_rate']) == accepted_tax['tax_rate']
    assert Decimal(tax['taxable_base']) == accepted_tax['taxable_base']
    assert Decimal(tax['tax_amount']) == accepted_tax['tax_amount']
    assert tax['tax_treatment'] == accepted_tax['tax_treatment']


def test_billing_idempotency_does_not_duplicate_document_lines_or_taxes(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    before = {}
    with connection.cursor() as cursor:
        for table in ('restaurant_orders', 'restaurant_payments', 'restaurant_check_settlements'):
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (source.scope.tenant_id,))
            before[table] = cursor.fetchone()['count']
    first = _bill(client, source, key='same-billing')
    replay = _bill(client, source, key='same-billing')
    assert first.status_code == 201 and replay.status_code == 200
    assert first.json()['id'] == replay.json()['id']
    with connection.cursor() as cursor:
        for table in ('billing_documents', 'billing_document_lines', 'billing_document_line_taxes'):
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table}')
            assert cursor.fetchone()['count'] >= 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_documents WHERE tenant_id=%s',
            (source.scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_document_lines WHERE billing_document_id=%s',
            (first.json()['id'],),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_document_line_taxes t JOIN '
            'billing_document_lines l ON l.id=t.billing_document_line_id '
            'WHERE l.billing_document_id=%s',
            (first.json()['id'],),
        )
        assert cursor.fetchone()['count'] == 1
        for table, count in before.items():
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (source.scope.tenant_id,))
            assert cursor.fetchone()['count'] == count

    other_recipient = _execute(
        connection,
        "INSERT INTO customer_fiscal_profiles (tenant_id,customer_id,legal_name,"
        "tax_identifier,tax_regime,fiscal_postal_code,invoice_usage,status) SELECT tenant_id,"
        "customer_id,'Other Recipient','OTHER-ID',tax_regime,fiscal_postal_code,invoice_usage,"
        "status FROM customer_fiscal_profiles WHERE id=%s",
        (source.recipient_profile_id,),
    )
    conflict = client.post(
        f'/restaurant-checks/{source.check_id}/billing-documents',
        headers={**_staff_headers(client, source.scope), 'Idempotency-Key': 'same-billing'},
        json=_payload(source, recipient_id=other_recipient),
    )
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'BILLING_IDEMPOTENCY_CONFLICT'
