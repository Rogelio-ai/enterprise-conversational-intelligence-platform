from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.core.execution import ActorType, ExecutionContext
from app.db.base import Base
from app.models import (
    BillingDocument,
    CustomerFiscalProfile,
    IssuerFiscalProfile,
    RestaurantCheck,
    RestaurantCheckSettlement,
    RestaurantPayment,
)
from app.restaurant.billing import errors, service
from app.restaurant.billing.contracts import CreateBillingDocumentCommand


class StubSession:
    def __init__(self, *scalar_results: object):
        self.scalar_results = list(scalar_results)
        self.commits = 0
        self.rollbacks = 0
        self.added: list[object] = []

    async def scalar(self, _query):
        assert self.scalar_results, 'Unexpected scalar query'
        return self.scalar_results.pop(0)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    def add(self, value: object) -> None:
        self.added.append(value)


def _context() -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EMPLOYEE,
        tenant_id=11,
        principal_id=22,
        principal_reference=None,
        correlation_id='billing-test',
    )


def _command(**changes: object) -> CreateBillingDocumentCommand:
    values = {
        'restaurant_check_id': 101,
        'organization_id': 201,
        'location_id': 301,
        'issuer_fiscal_profile_id': 401,
        'recipient_fiscal_profile_id': 501,
        'idempotency_key': 'billing-request-1',
    }
    values.update(changes)
    return CreateBillingDocumentCommand(**values)


def _check(*, status: str = 'SETTLED') -> RestaurantCheck:
    return RestaurantCheck(
        id=101,
        tenant_id=11,
        organization_id=201,
        location_id=301,
        currency='MXN',
        status=status,
        version=4,
        current_fingerprint='a' * 64,
        fingerprint_schema_version=1,
        consumption_total=Decimal('100.0000'),
        gratuity_total=Decimal('0.0000'),
        liability_total=Decimal('100.0000'),
        controller_actor_type='EMPLOYEE',
        created_actor_type='EMPLOYEE',
        continuation_decision='PENDING' if status == 'SETTLED' else 'NONE',
    )


def _issuer() -> IssuerFiscalProfile:
    return IssuerFiscalProfile(
        id=401,
        tenant_id=11,
        organization_id=201,
        legal_name='Issuer Legal Name',
        tax_identifier='ISSUER-TAX-ID',
        tax_regime='GENERAL',
        fiscal_postal_code='01000',
        status='ACTIVE',
    )


def _recipient(*, legal_name: str = 'Recipient Legal Name') -> CustomerFiscalProfile:
    return CustomerFiscalProfile(
        id=501,
        tenant_id=11,
        customer_id=601,
        legal_name=legal_name,
        tax_identifier='RECIPIENT-TAX-ID',
        tax_regime='GENERAL',
        fiscal_postal_code='02000',
        invoice_usage='GENERAL_EXPENSE',
        status='ACTIVE',
    )


async def _no_document(*_args, **_kwargs):
    return None


async def _eligible_settlement(*_args, **_kwargs) -> None:
    return None


async def _version(*_args, **_kwargs):
    return object()


async def _issuer_profile(*_args, **_kwargs):
    return _issuer()


async def _recipient_profile(*_args, **_kwargs):
    return _recipient()


async def _lines(*_args, **_kwargs):
    return (
        service._CommercialLineEvidence(
            source_restaurant_order_id=701,
            source_restaurant_order_item_id=801,
            description='Accepted product snapshot',
            quantity=Decimal('1.0000'),
            unit_price=Decimal('100.0000'),
            base_amount=Decimal('100.0000'),
            discount_amount=Decimal('0.0000'),
            commercial_total=Decimal('100.0000'),
        ),
    )


def _patch_prior_eligibility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, '_document_by_key', _no_document)
    monkeypatch.setattr(service, '_settlement_is_final', _eligible_settlement)
    monkeypatch.setattr(service, '_current_check_version', _version)


def test_non_settled_check_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_prior_eligibility(monkeypatch)
    db = StubSession(_check(status='FROZEN'))

    with pytest.raises(errors.BillingCheckNotSettledError):
        asyncio.run(service.create_billing_document(db, context=_context(), command=_command()))

    assert db.rollbacks == 1
    assert db.added == []


def test_missing_issuer_profile_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_prior_eligibility(monkeypatch)
    db = StubSession(_check(), None)

    with pytest.raises(errors.BillingIssuerProfileMissingError):
        asyncio.run(service.create_billing_document(db, context=_context(), command=_command()))

    assert db.rollbacks == 1


@pytest.mark.parametrize('recipient', [None, _recipient(legal_name='   ')])
def test_missing_or_invalid_recipient_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    recipient: CustomerFiscalProfile | None,
) -> None:
    _patch_prior_eligibility(monkeypatch)
    monkeypatch.setattr(service, '_active_issuer', _issuer_profile)
    db = StubSession(_check(), recipient)

    with pytest.raises(errors.BillingRecipientInvalidError):
        asyncio.run(service.create_billing_document(db, context=_context(), command=_command()))

    assert db.rollbacks == 1


def test_missing_tax_evidence_rejects_without_financial_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, '_document_by_key', _no_document)
    monkeypatch.setattr(service, '_current_check_version', _version)
    monkeypatch.setattr(service, '_active_issuer', _issuer_profile)
    monkeypatch.setattr(service, '_active_recipient', _recipient_profile)
    monkeypatch.setattr(service, '_commercial_evidence', _lines)
    payment = RestaurantPayment(id=901, state='SUCCEEDED', amount=Decimal('100.0000'))
    settlement = RestaurantCheckSettlement(
        id=902,
        payment_id=901,
        check_id=101,
        amount=Decimal('100.0000'),
    )
    before = (payment.state, payment.amount, settlement.payment_id, settlement.amount)

    async def totals(*_args, **_kwargs):
        return settlement.amount, Decimal('0.0000'), Decimal('0.0000')

    monkeypatch.setattr(service.payment_service, '_totals', totals)
    check = _check()
    db = StubSession(check)

    with pytest.raises(errors.BillingTaxEvidenceUnavailableError):
        asyncio.run(service.create_billing_document(db, context=_context(), command=_command()))

    assert (payment.state, payment.amount, settlement.payment_id, settlement.amount) == before
    assert check.status == 'SETTLED'
    assert db.added == []
    assert db.rollbacks == 1


def test_billing_ownership_is_check_based_not_payment_based() -> None:
    table = Base.metadata.tables['billing_documents']
    assert 'restaurant_check_id' in table.c
    assert 'payment_id' not in table.c
    targets = {
        foreign_key.target_fullname
        for constraint in table.foreign_key_constraints
        for foreign_key in constraint.elements
    }
    assert 'restaurant_checks.id' in targets
    assert not any(target.startswith('restaurant_payments.') for target in targets)


def _existing_document(command: CreateBillingDocumentCommand) -> BillingDocument:
    return BillingDocument(
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
        issuer_snapshot=service._issuer_snapshot(_issuer()),
        recipient_snapshot=service._recipient_snapshot(_recipient()),
        actor_scope='EMPLOYEE:22',
        idempotency_key=command.idempotency_key,
        request_fingerprint=service._request_fingerprint(command),
    )


def test_same_idempotent_request_replays_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = _command()
    document = _existing_document(command)

    async def existing(*_args, **_kwargs):
        return document

    monkeypatch.setattr(service, '_document_by_key', existing)
    db = StubSession()

    projection, replayed = asyncio.run(
        service.create_billing_document(db, context=_context(), command=command)
    )

    assert replayed is True
    assert projection.id == document.id
    assert projection.restaurant_check_id == command.restaurant_check_id
    assert db.added == []


def test_changed_request_with_same_identity_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _command()
    changed = _command(recipient_fiscal_profile_id=502)
    document = _existing_document(original)

    async def existing(*_args, **_kwargs):
        return document

    monkeypatch.setattr(service, '_document_by_key', existing)

    with pytest.raises(errors.BillingIdempotencyConflictError):
        asyncio.run(
            service.create_billing_document(
                StubSession(), context=_context(), command=changed
            )
        )
