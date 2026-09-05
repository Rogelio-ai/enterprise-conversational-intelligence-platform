from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db
from app.main import create_app
from app.models import BillingDocument, BillingDocumentLine, BillingDocumentLineTax
from app.restaurant.billing import errors, service
from app.restaurant.billing.contracts import BillingDocumentProjection


class EmptySession:
    pass


class Rows:
    def __init__(self, values: tuple[object, ...]):
        self.values = values

    def scalars(self):
        return self

    def all(self) -> list[object]:
        return list(self.values)


class PersistedBillingSession:
    def __init__(
        self,
        document: BillingDocument,
        lines: tuple[BillingDocumentLine, ...],
        taxes: tuple[BillingDocumentLineTax, ...],
    ):
        self.document = document
        self.lines = lines
        self.taxes = taxes

    async def scalar(self, query):
        criteria = {
            clause.left.name: clause.right.value
            for clause in query._where_criteria
            if hasattr(clause, 'left') and hasattr(clause.right, 'value')
        }
        expected = {
            'id': self.document.id,
            'tenant_id': self.document.tenant_id,
            'organization_id': self.document.organization_id,
            'location_id': self.document.location_id,
        }
        return self.document if criteria == expected else None

    async def execute(self, query):
        entity = query.column_descriptions[0]['entity']
        if entity is BillingDocumentLine:
            return Rows(self.lines)
        if entity is BillingDocumentLineTax:
            return Rows(self.taxes)
        raise AssertionError(f'Unexpected billing read entity: {entity}')


def _auth(tenant_id: int = 11) -> AuthenticatedContext:
    return AuthenticatedContext(
        user_id=1,
        email='billing@example.test',
        display_name='Billing User',
        tenant_id=tenant_id,
        tenant_name='Billing Tenant',
        tenant_slug='billing-tenant',
        membership_id=22,
        roles=('TENANT_ADMIN',),
        permissions=frozenset({'restaurant_check.read', 'restaurant_check.manage'}),
    )


@contextmanager
def _client(settings, database, *, session=EmptySession(), tenant_id: int = 11):
    app = create_app(settings=settings, database=database)

    async def authenticated_context():
        return _auth(tenant_id)

    async def database_session():
        yield session

    app.dependency_overrides[get_authenticated_context] = authenticated_context
    app.dependency_overrides[get_db] = database_session
    with TestClient(app) as client:
        yield client


def _payload(*, recipient_profile_id: int = 501) -> dict[str, int]:
    return {
        'organization_id': 201,
        'location_id': 301,
        'issuer_fiscal_profile_id': 401,
        'recipient_fiscal_profile_id': recipient_profile_id,
    }


def _projection() -> BillingDocumentProjection:
    recorded_at = datetime(2026, 9, 3, 12, 0, 0)
    return BillingDocumentProjection(
        id=1001,
        tenant_id=11,
        organization_id=201,
        location_id=301,
        restaurant_check_id=101,
        source_check_version=4,
        source_check_fingerprint='a' * 64,
        document_type='INVOICE',
        status='DRAFT',
        currency='MXN',
        subtotal=Decimal('100.0000'),
        discount_total=Decimal('0.0000'),
        tax_total=Decimal('0.0000'),
        total=Decimal('100.0000'),
        issuer_snapshot={
            'legal_name': 'Issuer Legal Name',
            'tax_identifier': 'ISSUER-TAX-ID',
            'tax_regime': 'GENERAL',
            'fiscal_postal_code': '01000',
        },
        recipient_snapshot={
            'legal_name': 'Recipient Legal Name',
            'tax_identifier': 'RECIPIENT-TAX-ID',
            'tax_regime': 'GENERAL',
            'fiscal_postal_code': '02000',
            'invoice_usage': 'GENERAL_EXPENSE',
        },
        issuer_fiscal_postal_code='01000',
        readiness_evidence_fingerprint='c' * 64,
        created_at=recorded_at,
        updated_at=recorded_at,
    )


def test_authenticated_create_reaches_billing_service(
    settings, database, monkeypatch,
) -> None:
    captured = {}

    async def create(_db, *, context, command):
        captured['context'] = context
        captured['command'] = command
        raise errors.BillingTaxEvidenceUnavailableError()

    monkeypatch.setattr(service, 'create_billing_document', create)
    with _client(settings, database) as client:
        response = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-1'},
            json=_payload(),
        )

    assert response.status_code == 409
    assert captured['context'].tenant_id == 11
    assert captured['context'].principal_id == 22
    assert captured['command'].restaurant_check_id == 101
    assert captured['command'].idempotency_key == 'billing-api-1'


def test_non_settled_source_has_controlled_public_error(
    settings, database, monkeypatch,
) -> None:
    async def create(*_args, **_kwargs):
        raise errors.BillingCheckNotSettledError()

    monkeypatch.setattr(service, 'create_billing_document', create)
    with _client(settings, database) as client:
        response = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-2'},
            json=_payload(),
        )

    assert response.status_code == 409
    assert response.json()['error']['code'] == 'BILLING_CHECK_NOT_SETTLED'


def test_missing_tax_evidence_has_controlled_public_error(
    settings, database, monkeypatch,
) -> None:
    async def create(*_args, **_kwargs):
        raise errors.BillingTaxEvidenceUnavailableError()

    monkeypatch.setattr(service, 'create_billing_document', create)
    with _client(settings, database) as client:
        response = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-3'},
            json=_payload(),
        )

    assert response.status_code == 409
    assert response.json()['error']['code'] == 'BILLING_TAX_EVIDENCE_UNAVAILABLE'


def test_same_idempotency_key_and_request_returns_replay(
    settings, database, monkeypatch,
) -> None:
    calls = []

    async def create(_db, *, context, command):
        calls.append((context.tenant_id, command))
        return _projection(), True

    monkeypatch.setattr(service, 'create_billing_document', create)
    with _client(settings, database) as client:
        first = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-replay'},
            json=_payload(),
        )
        second = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-replay'},
            json=_payload(),
        )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls[0] == calls[1]


def test_changed_request_with_same_key_has_controlled_conflict(
    settings, database, monkeypatch,
) -> None:
    commands = []

    async def create(_db, *, context, command):
        commands.append(command)
        if len(commands) == 1:
            return _projection(), True
        raise errors.BillingIdempotencyConflictError()

    monkeypatch.setattr(service, 'create_billing_document', create)
    with _client(settings, database) as client:
        first = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-conflict'},
            json=_payload(),
        )
        changed = client.post(
            '/restaurant-checks/101/billing-documents',
            headers={'Idempotency-Key': 'billing-api-conflict'},
            json=_payload(recipient_profile_id=502),
        )

    assert first.status_code == 200
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'BILLING_IDEMPOTENCY_CONFLICT'
    assert commands[0].recipient_fiscal_profile_id != commands[1].recipient_fiscal_profile_id


def _persisted_evidence():
    created_at = datetime(2026, 9, 3, 12, 0, 0)
    projection = _projection()
    document = BillingDocument(
        **asdict(projection),
        actor_scope='EMPLOYEE:22',
        idempotency_key='persisted-billing-document',
        request_fingerprint='b' * 64,
    )
    line = BillingDocumentLine(
        id=1101,
        billing_document_id=document.id,
        source_restaurant_order_id=701,
        source_restaurant_order_item_id=801,
        description='Immutable product description',
        quantity=Decimal('1.0000'),
        unit_price=Decimal('100.0000'),
        base_amount=Decimal('100.0000'),
        discount_amount=Decimal('0.0000'),
        commercial_total=Decimal('100.0000'),
        fiscal_product_classification_scheme='TEST-PRODUCT-SCHEME',
        fiscal_product_classification_code='TEST-PRODUCT',
        fiscal_unit_classification_scheme='TEST-UNIT-SCHEME',
        fiscal_unit_classification_code='EACH',
        fiscal_unit_value=Decimal('100.0000'),
        fiscal_line_amount=Decimal('100.0000'),
        fiscal_discount_amount=Decimal('0.0000'),
        source_fiscal_evidence_fingerprint='d' * 64,
        created_at=created_at,
    )
    tax = BillingDocumentLineTax(
        id=1201,
        billing_document_line_id=line.id,
        tax_category='AUTHORITATIVE_TEST_EVIDENCE',
        tax_rate=Decimal('0.000000'),
        taxable_base=Decimal('100.0000'),
        tax_amount=Decimal('0.0000'),
        tax_treatment='EXEMPT',
        jurisdiction_code='TEST-JURISDICTION',
        tax_effect='TRANSFERRED',
        source_tax_evidence_fingerprint='e' * 64,
        created_at=created_at,
    )
    return document, (line,), (tax,)


def test_get_returns_authorized_immutable_stored_evidence(settings, database) -> None:
    document, lines, taxes = _persisted_evidence()
    session = PersistedBillingSession(document, lines, taxes)
    with _client(settings, database, session=session) as client:
        response = client.get(
            f'/billing-documents/{document.id}',
            params={'organization_id': 201, 'location_id': 301},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body['issuer_snapshot'] == document.issuer_snapshot
    assert body['recipient_snapshot'] == document.recipient_snapshot
    assert body['issuer_fiscal_postal_code'] == '01000'
    assert body['readiness_evidence_fingerprint'] == 'c' * 64
    assert body['lines'][0]['description'] == lines[0].description
    assert body['lines'][0]['fiscal_product_classification_code'] == 'TEST-PRODUCT'
    assert body['lines'][0]['fiscal_unit_classification_code'] == 'EACH'
    assert body['lines'][0]['taxes'][0]['tax_category'] == taxes[0].tax_category
    assert body['lines'][0]['taxes'][0]['tax_effect'] == 'TRANSFERRED'
    assert 'actor_scope' not in response.text
    assert 'idempotency_key' not in response.text
    assert 'request_fingerprint' not in response.text


def test_cross_tenant_get_does_not_leak_document(settings, database) -> None:
    document, lines, taxes = _persisted_evidence()
    session = PersistedBillingSession(document, lines, taxes)
    with _client(settings, database, session=session, tenant_id=12) as client:
        response = client.get(
            f'/billing-documents/{document.id}',
            params={'organization_id': 201, 'location_id': 301},
        )

    assert response.status_code == 404
    assert response.json()['error']['code'] == 'BILLING_DOCUMENT_NOT_FOUND'
