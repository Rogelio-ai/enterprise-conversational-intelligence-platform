from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Product, ProductFiscalClassification
from app.restaurant.fiscal_product.contracts import FiscalProductClassificationCandidate
from app.restaurant.fiscal_product.errors import (
    FiscalProductEvidenceAmbiguousError,
    FiscalProductEvidenceUnavailableError,
    FiscalProductScopeError,
)
from app.restaurant.fiscal_product.service import resolve_fiscal_product_evidence
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _open_and_join,
    _preview,
    _product,
    _scope,
)


NOW = datetime(2026, 9, 4, 12, 0, 0)


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _Scalars(self._values)


class FakeSession:
    def __init__(self, *, product=None, classifications=()):
        self.product = product
        self.classifications = classifications

    async def scalar(self, statement):
        return self.product

    async def execute(self, statement):
        return _Result(self.classifications)


def _canonical_product(**changes) -> Product:
    values = {
        'id': 30,
        'tenant_id': 10,
        'organization_id': 20,
        'tax_classification_code': 'INTERNAL-TAX-CLASS',
    }
    values.update(changes)
    return Product(**values)


def _classification(classification_id: int = 40, **changes) -> ProductFiscalClassification:
    values = {
        'id': classification_id,
        'tenant_id': 10,
        'organization_id': 20,
        'product_id': 30,
        'fiscal_jurisdiction_code': 'MX',
        'product_classification_scheme': 'PRODUCT-SCHEME',
        'product_classification_code': 'PRODUCT-CODE',
        'unit_classification_scheme': 'UNIT-SCHEME',
        'unit_classification_code': 'EACH',
        'effective_from': NOW - timedelta(days=1),
        'effective_to': None,
        'status': 'ACTIVE',
    }
    values.update(changes)
    return ProductFiscalClassification(**values)


def _candidate(**changes) -> FiscalProductClassificationCandidate:
    values = {
        'tenant_id': 10,
        'organization_id': 20,
        'product_id': 30,
        'fiscal_jurisdiction_code': 'MX',
        'effective_at': NOW,
    }
    values.update(changes)
    return FiscalProductClassificationCandidate(**values)


def _resolve(*, product=None, classifications=(), candidate=None):
    session = FakeSession(
        product=product if product is not None else _canonical_product(),
        classifications=classifications,
    )
    return asyncio.run(
        resolve_fiscal_product_evidence(session, candidate or _candidate())
    )


def test_valid_resolution_is_deterministic_immutable_and_provider_neutral() -> None:
    first = _resolve(classifications=(_classification(),))
    second = _resolve(classifications=(_classification(),))

    assert first == second
    assert first.fiscal_jurisdiction_code == 'MX'
    assert first.product_classification_scheme == 'PRODUCT-SCHEME'
    assert first.product_classification_code == 'PRODUCT-CODE'
    assert first.unit_classification_scheme == 'UNIT-SCHEME'
    assert first.unit_classification_code == 'EACH'
    assert len(first.evidence_fingerprint) == 64
    with pytest.raises(FrozenInstanceError):
        first.product_classification_code = 'CHANGED'


@pytest.mark.parametrize(
    'product',
    [
        _canonical_product(tenant_id=99),
        _canonical_product(organization_id=99),
        _canonical_product(id=99),
    ],
)
def test_product_tenant_and_organization_isolation(product) -> None:
    with pytest.raises(FiscalProductScopeError):
        _resolve(product=product, classifications=(_classification(),))


def test_classification_tenant_and_organization_isolation() -> None:
    with pytest.raises(FiscalProductScopeError):
        _resolve(classifications=(_classification(tenant_id=99),))
    with pytest.raises(FiscalProductScopeError):
        _resolve(classifications=(_classification(organization_id=99),))


def test_missing_and_historical_product_without_snapshot_fail_closed() -> None:
    product = _canonical_product(tax_classification_code='STILL-NOT-FISCAL-EVIDENCE')
    with pytest.raises(FiscalProductEvidenceUnavailableError):
        _resolve(product=product, classifications=())


def test_ambiguous_classifications_fail_closed() -> None:
    with pytest.raises(FiscalProductEvidenceAmbiguousError):
        _resolve(classifications=(_classification(40), _classification(41)))


@pytest.mark.parametrize(
    'classification',
    [
        _classification(status='INACTIVE'),
        _classification(effective_from=NOW + timedelta(seconds=1)),
        _classification(effective_to=NOW),
    ],
)
def test_inactive_and_out_of_range_classifications_fail_closed(classification) -> None:
    with pytest.raises(FiscalProductEvidenceUnavailableError):
        _resolve(classifications=(classification,))


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _accepted_fiscal_snapshot(client, connection, prefix: str):
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope)
    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, 'fiscal-evidence-accept')
    assert accepted.status_code == 201, accepted.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT s.*,o.accepted_at FROM restaurant_order_item_fiscal_snapshots s '
            'JOIN restaurant_orders o ON o.id=s.restaurant_order_id '
            'WHERE s.restaurant_order_id=%s',
            (accepted.json()['id'],),
        )
        snapshot = cursor.fetchone()
    return scope, diner_headers, product_id, preview, accepted, snapshot


def test_acceptance_freezes_product_and_unit_evidence_at_acceptance_instant(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    _, _, product_id, _, accepted, snapshot = _accepted_fiscal_snapshot(
        client, connection, prefix
    )

    assert snapshot['product_classification_scheme'] == 'TEST-PRODUCT-SCHEME'
    assert snapshot['product_classification_code'] == f'FISCAL-{product_id}'
    assert snapshot['unit_classification_scheme'] == 'TEST-UNIT-SCHEME'
    assert snapshot['unit_classification_code'] == 'EACH'
    assert snapshot['created_at'] == snapshot['accepted_at']
    assert snapshot['schema_version'] == 1
    assert len(snapshot['evidence_fingerprint']) == 64
    assert accepted.json()['status'] == 'ACCEPTED'


def test_master_data_changes_do_not_mutate_accepted_evidence(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    _, _, product_id, _, accepted, original = _accepted_fiscal_snapshot(
        client, connection, prefix
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE product_fiscal_classifications SET product_classification_code='NEW',"
            "unit_classification_code='NEW-UNIT' WHERE product_id=%s",
            (product_id,),
        )
        cursor.execute(
            'SELECT product_classification_code,unit_classification_code,'
            'evidence_fingerprint FROM restaurant_order_item_fiscal_snapshots '
            'WHERE restaurant_order_id=%s',
            (accepted.json()['id'],),
        )
        frozen = cursor.fetchone()
    assert frozen['product_classification_code'] == original['product_classification_code']
    assert frozen['unit_classification_code'] == original['unit_classification_code']
    assert frozen['evidence_fingerprint'] == original['evidence_fingerprint']


def test_replay_does_not_duplicate_fiscal_evidence(client, sql_connection) -> None:
    connection, prefix = sql_connection
    _, diner_headers, _, preview, accepted, _ = _accepted_fiscal_snapshot(
        client, connection, prefix
    )
    replay = _confirm(client, diner_headers, preview, 'fiscal-evidence-accept')
    assert replay.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_order_item_fiscal_snapshots '
            'WHERE restaurant_order_id=%s',
            (accepted.json()['id'],),
        )
        assert cursor.fetchone()['count'] == 1


def test_missing_evidence_rolls_back_order_acceptance(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope)
    preview = _preview(client, diner_headers, product_id)
    with connection.cursor() as cursor:
        cursor.execute(
            'DELETE FROM product_fiscal_classifications WHERE product_id=%s',
            (product_id,),
        )

    rejected = _confirm(client, diner_headers, preview, 'missing-fiscal-evidence')
    assert rejected.status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_order_item_fiscal_snapshots '
            'WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
