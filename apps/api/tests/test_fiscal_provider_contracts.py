from __future__ import annotations

import asyncio
from decimal import Decimal
import inspect

import pytest
from pydantic import ValidationError

from app.restaurant.integrations.fiscal import contracts
from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceLine,
    FiscalIssuanceLineTax,
    FiscalIssuanceOutcome,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalProviderErrorKind,
    FiscalRecoveryOutcome,
    FrozenFiscalPartySnapshot,
)
from app.restaurant.integrations.fiscal.credentials import (
    FiscalProviderCredentialBinding,
    FiscalProviderCredentialResolver,
)
from app.restaurant.integrations.fiscal.errors import (
    DuplicateFiscalProviderRegistrationError,
    FiscalProviderCredentialResolutionError,
    FiscalProviderNotRegisteredError,
)
from app.restaurant.integrations.fiscal.fake import DeterministicFiscalProvider
from app.restaurant.integrations.fiscal.ports import FiscalIssuancePort
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry


SECRET = 'test-fiscal-secret-must-never-escape'


def _issuance_request(sequence: int = 1) -> FiscalIssuanceRequest:
    tax = FiscalIssuanceLineTax(
        billing_document_line_tax_id=sequence,
        category='GENERAL',
        treatment='TAXABLE',
        rate=Decimal('0.160000'),
        taxable_base=Decimal('100.0000'),
        amount=Decimal('16.0000'),
    )
    line = FiscalIssuanceLine(
        billing_document_line_id=sequence,
        description='Frozen canonical line',
        quantity=Decimal('1.0000'),
        unit_price=Decimal('100.0000'),
        base_amount=Decimal('100.0000'),
        discount_amount=Decimal('0.0000'),
        total=Decimal('100.0000'),
        taxes=(tax,),
    )
    return FiscalIssuanceRequest(
        tenant_id=1,
        organization_id=2,
        location_id=3,
        billing_document_id=4,
        operation_reference=f'issuance-{sequence}',
        provider_idempotency_key=f'provider-operation-{sequence}',
        request_fingerprint=f'{sequence:x}' * 64,
        request_schema_version=1,
        document_type='INVOICE',
        currency='mxn',
        subtotal=Decimal('100.0000'),
        discount_total=Decimal('0.0000'),
        tax_total=Decimal('16.0000'),
        total=Decimal('116.0000'),
        issuer=FrozenFiscalPartySnapshot(
            legal_name='Frozen Issuer',
            tax_identifier='ISSUER-1',
            tax_regime='GENERAL',
            postal_code='01000',
        ),
        recipient=FrozenFiscalPartySnapshot(
            legal_name='Frozen Recipient',
            tax_identifier='RECIPIENT-1',
            tax_regime='GENERAL',
            postal_code='02000',
            document_usage='GENERAL_EXPENSE',
        ),
        lines=(line,),
    )


def _recovery_request(sequence: int = 1) -> FiscalIssuanceRecoveryRequest:
    request = _issuance_request(sequence)
    return FiscalIssuanceRecoveryRequest(
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        location_id=request.location_id,
        billing_document_id=request.billing_document_id,
        operation_reference=request.operation_reference,
        provider_idempotency_key=request.provider_idempotency_key,
        request_fingerprint=request.request_fingerprint,
        request_schema_version=request.request_schema_version,
    )


def test_contracts_are_immutable_ordered_and_only_carry_frozen_evidence() -> None:
    request = _issuance_request()
    assert request.currency == 'MXN'
    assert isinstance(request.lines, tuple)
    assert isinstance(request.lines[0].taxes, tuple)
    assert request.lines[0].taxes[0].billing_document_line_tax_id == 1

    with pytest.raises(ValidationError):
        request.total = Decimal('1.0000')
    with pytest.raises(ValidationError):
        request.issuer.legal_name = 'Mutable name'
    with pytest.raises(ValidationError):
        FiscalIssuanceRequest.model_validate(
            _issuance_request().model_dump() | {'total': 1.2}
        )

    field_names = set(FiscalIssuanceRequest.model_fields)
    assert field_names == {
        'tenant_id', 'organization_id', 'location_id', 'billing_document_id',
        'operation_reference', 'provider_idempotency_key', 'request_fingerprint',
        'request_schema_version', 'document_type', 'currency', 'subtotal',
        'discount_total', 'tax_total', 'total', 'issuer', 'recipient', 'lines',
    }
    forbidden_names = ('product', 'tax_rule', 'payment', 'settlement', 'live_profile')
    assert not any(token in name for name in field_names for token in forbidden_names)
    source = inspect.getsource(contracts)
    assert 'app.models' not in source
    assert 'RestaurantTaxRule' not in source
    assert 'Payment' not in source
    assert 'Settlement' not in source


def test_fiscal_port_and_credential_resolver_protocols_are_async_compatible() -> None:
    class Resolver:
        async def resolve(
            self, *, binding: FiscalProviderCredentialBinding
        ) -> EphemeralFiscalProviderCredential:
            assert binding.provider_key == 'FAKE'
            return EphemeralFiscalProviderCredential(value=SECRET)

    provider = DeterministicFiscalProvider()
    resolver = Resolver()
    binding = FiscalProviderCredentialBinding(
        tenant_id=1,
        organization_id=2,
        location_id=3,
        provider_key='FAKE',
        credential_binding='vault-reference-not-secret-material',
        operation_reference='issuance-1',
    )

    assert isinstance(provider, FiscalIssuancePort)
    assert isinstance(resolver, FiscalProviderCredentialResolver)
    with pytest.raises(ValidationError):
        binding.provider_key = 'OTHER'
    credential = asyncio.run(resolver.resolve(binding=binding))
    result = asyncio.run(
        provider.issue(request=_issuance_request(), credential=credential)
    )
    recovered = asyncio.run(
        provider.recover(request=_recovery_request(), credential=credential)
    )
    assert result.outcome is FiscalIssuanceOutcome.SUCCEEDED
    assert recovered.outcome is FiscalRecoveryOutcome.RECOVERED_SUCCESS


def test_registry_resolves_exact_provider_and_rejects_unknown_or_duplicate() -> None:
    provider = DeterministicFiscalProvider()
    registry = FiscalProviderRegistry()
    registry.register('FAKE', provider)

    assert registry.resolve('FAKE') is provider
    with pytest.raises(FiscalProviderNotRegisteredError):
        registry.resolve('UNKNOWN')
    with pytest.raises(DuplicateFiscalProviderRegistrationError):
        registry.register('FAKE', DeterministicFiscalProvider())


def test_ephemeral_credential_is_redacted_and_outside_persistence_surfaces(
    caplog,
) -> None:
    credential = EphemeralFiscalProviderCredential(value=SECRET)
    provider = DeterministicFiscalProvider(
        issuance_outcomes=(FiscalIssuanceOutcome.DEFINITE_FAILURE,)
    )
    result = asyncio.run(
        provider.issue(request=_issuance_request(), credential=credential)
    )
    resolution_error = FiscalProviderCredentialResolutionError()

    assert SECRET not in repr(credential)
    assert SECRET not in str(credential)
    assert SECRET not in credential.model_dump_json()
    assert SECRET not in repr(provider.__dict__)
    assert SECRET not in result.error_message
    assert SECRET not in str(resolution_error)
    assert SECRET not in caplog.text
    assert not hasattr(EphemeralFiscalProviderCredential, '__table__')
    assert 'sqlalchemy' not in inspect.getsource(contracts).lower()


def test_deterministic_fake_covers_issue_and_recovery_outcomes() -> None:
    issue_outcomes = tuple(FiscalIssuanceOutcome)
    recovery_outcomes = tuple(FiscalRecoveryOutcome)
    provider = DeterministicFiscalProvider(
        issuance_outcomes=issue_outcomes,
        recovery_outcomes=recovery_outcomes,
    )

    issued = tuple(
        asyncio.run(provider.issue(request=_issuance_request(index), credential=None))
        for index in range(1, len(issue_outcomes) + 1)
    )
    recovered = tuple(
        asyncio.run(provider.recover(request=_recovery_request(index), credential=None))
        for index in range(1, len(recovery_outcomes) + 1)
    )

    assert tuple(result.outcome for result in issued) == issue_outcomes
    assert tuple(result.outcome for result in recovered) == recovery_outcomes
    assert issued[0].external_reference is not None
    assert issued[1].error_kind is FiscalProviderErrorKind.TECHNICAL_FAILURE
    assert issued[2].error_kind is FiscalProviderErrorKind.BUSINESS_REJECTION
    assert issued[3].error_kind is FiscalProviderErrorKind.AMBIGUOUS_RESULT
    assert recovered[0].external_reference is not None
    assert recovered[1].external_reference is None
    assert recovered[-1].error_kind is FiscalProviderErrorKind.AMBIGUOUS_RESULT

    replay = asyncio.run(
        provider.issue(request=_issuance_request(1), credential=None)
    )
    assert replay == issued[0]
    assert provider.issue_calls == len(issue_outcomes)
