from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import base64
import json
import os
from xml.etree import ElementTree as ET

import pytest
from pydantic import SecretStr

from app.main import create_app
from app.restaurant.fiscal.mexico.cfdi40.serializer import CFDI_NAMESPACE
from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceLine,
    FiscalIssuanceLineTax,
    FiscalIssuanceOutcome,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalRecoveryOutcome,
    FrozenFiscalPartySnapshot,
    FrozenFiscalPaymentEvidence,
    FrozenFiscalSettlementEvidence,
)
from app.restaurant.integrations.fiscal.finkok import (
    FinkokAmbiguousTransportError,
    FinkokDefiniteTransportError,
    FinkokFiscalIssuanceAdapter,
    FinkokIncidence,
    FinkokStampResponse,
    HttpxFinkokSoapTransport,
)
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry


NOW = datetime(2026, 9, 5, 12, 30, 15)
UUID = '12345678-1234-1234-1234-123456789ABC'
TFD_NAMESPACE = 'http://www.sat.gob.mx/TimbreFiscalDigital'
SECRET_USERNAME = 'merchant@example.test'
SECRET_PASSWORD = 'super-secret-password'


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.sign_calls = []
        self.recovery_calls = []

    async def sign_stamp(self, **values):
        self.sign_calls.append(values)
        if self.error:
            raise self.error
        return self.response

    async def stamped(self, **values):
        self.recovery_calls.append(values)
        if self.error:
            raise self.error
        return self.response


def _credential() -> EphemeralFiscalProviderCredential:
    return EphemeralFiscalProviderCredential(value=SecretStr(json.dumps({
        'username': SECRET_USERNAME,
        'password': SECRET_PASSWORD,
    })))


def _request(
    *,
    method: str = 'CASH',
    treatment: str = 'TAXABLE',
) -> FiscalIssuanceRequest:
    rate = Decimal('0.160000') if treatment == 'TAXABLE' else Decimal('0.000000')
    tax_amount = Decimal('16.0000') if treatment == 'TAXABLE' else Decimal('0.0000')
    total = Decimal('116.0000') if treatment == 'TAXABLE' else Decimal('100.0000')
    return FiscalIssuanceRequest(
        tenant_id=1,
        organization_id=2,
        location_id=3,
        billing_document_id=4,
        operation_reference='fiscal-issuance-v1:1:4',
        provider_idempotency_key='finkok-operation-4',
        request_fingerprint='a' * 64,
        request_schema_version=1,
        document_type='INVOICE',
        currency='MXN',
        subtotal=Decimal('100.0000'),
        discount_total=Decimal('0.0000'),
        tax_total=tax_amount,
        total=total,
        issuer=FrozenFiscalPartySnapshot(
            legal_name='EMISOR SA DE CV',
            tax_identifier='AAA010101AAA',
            tax_regime='GENERAL',
            postal_code='01000',
        ),
        recipient=FrozenFiscalPartySnapshot(
            legal_name='RECEPTOR SA DE CV',
            tax_identifier='BBB010101BBB',
            tax_regime='GENERAL',
            postal_code='02000',
            document_usage='GENERAL_EXPENSE',
        ),
        lines=(FiscalIssuanceLine(
            billing_document_line_id=10,
            description='Consumo de alimentos & bebidas',
            quantity=Decimal('1.0000'),
            unit_price=total,
            base_amount=total,
            discount_amount=Decimal('0.0000'),
            total=total,
            fiscal_product_classification_scheme='SAT-CFDI-4.0-c_ClaveProdServ',
            fiscal_product_classification_code='90101501',
            fiscal_unit_classification_scheme='SAT-CFDI-4.0-c_ClaveUnidad',
            fiscal_unit_classification_code='E48',
            fiscal_unit_value=Decimal('100.0000'),
            fiscal_line_amount=Decimal('100.0000'),
            fiscal_discount_amount=Decimal('0.0000'),
            source_fiscal_evidence_fingerprint='b' * 64,
            taxes=(FiscalIssuanceLineTax(
                billing_document_line_tax_id=11,
                category='IVA',
                treatment=treatment,
                rate=rate,
                taxable_base=Decimal('100.0000'),
                amount=tax_amount,
                jurisdiction_code='MX',
                tax_effect='TRANSFERRED',
                source_tax_evidence_fingerprint='c' * 64,
            ),),
        ),),
        source_check_version=2,
        source_check_fingerprint='d' * 64,
        readiness_evidence_fingerprint='e' * 64,
        settlement=FrozenFiscalSettlementEvidence(
            restaurant_check_id=5,
            check_status='SETTLED',
            check_version=2,
            check_fingerprint='d' * 64,
            currency='MXN',
            liability_total=total,
            confirmed_settlement=total,
            reserved_financial_exposure=Decimal('0.0000'),
            uncertain_exposure=Decimal('0.0000'),
            payments=(FrozenFiscalPaymentEvidence(
                method_category=method,
                amount=total,
                state='SUCCEEDED',
            ),),
        ),
        issued_at=NOW,
    )


def _source_xml(request: FiscalIssuanceRequest) -> bytes:
    adapter = FinkokFiscalIssuanceAdapter(transport=FakeTransport())
    return adapter._xml(request)


def _stamped_xml(request: FiscalIssuanceRequest, mismatch: str | None = None) -> str:
    root = ET.fromstring(_source_xml(request))
    if mismatch == 'issuer':
        root.find(f'{{{CFDI_NAMESPACE}}}Emisor').set('Rfc', 'CCC010101CCC')
    elif mismatch == 'recipient':
        root.find(f'{{{CFDI_NAMESPACE}}}Receptor').set('Rfc', 'CCC010101CCC')
    elif mismatch == 'total':
        root.set('Total', '999.00')
    complement = ET.SubElement(root, f'{{{CFDI_NAMESPACE}}}Complemento')
    ET.SubElement(complement, f'{{{TFD_NAMESPACE}}}TimbreFiscalDigital', {
        'Version': '1.1',
        'UUID': UUID,
        'FechaTimbrado': '2026-09-05T12:31:00',
    })
    return ET.tostring(root, encoding='unicode')


def _success(request: FiscalIssuanceRequest, mismatch=None) -> FinkokStampResponse:
    return FinkokStampResponse(
        xml=_stamped_xml(request, mismatch),
        uuid=UUID,
        fecha='2026-09-05T12:31:00',
        status='Comprobante timbrado satisfactoriamente',
    )


def test_valid_invoice_serializes_deterministically_with_cfdi_namespace() -> None:
    request = _request()
    first = _source_xml(request)
    second = _source_xml(request)
    assert first == second
    root = ET.fromstring(first)
    assert root.tag == f'{{{CFDI_NAMESPACE}}}Comprobante'
    assert root.attrib['Version'] == '4.0'


def test_xml_maps_parties_concept_and_escapes_text() -> None:
    xml = _source_xml(_request())
    root = ET.fromstring(xml)
    assert root.find(f'{{{CFDI_NAMESPACE}}}Emisor').attrib['Rfc'] == 'AAA010101AAA'
    assert root.find(f'{{{CFDI_NAMESPACE}}}Receptor').attrib['Rfc'] == 'BBB010101BBB'
    concept = root.find(f'.//{{{CFDI_NAMESPACE}}}Concepto')
    assert concept.attrib['ClaveProdServ'] == '90101501'
    assert concept.attrib['Descripcion'] == 'Consumo de alimentos & bebidas'
    assert b'&amp;' in xml


@pytest.mark.parametrize(
    ('treatment', 'factor', 'rate_present', 'amount_present'),
    [
        ('TAXABLE', 'Tasa', True, True),
        ('ZERO_RATE', 'Tasa', True, True),
        ('EXEMPT', 'Exento', False, False),
    ],
)
def test_xml_serializes_supported_iva_semantics(
    treatment, factor, rate_present, amount_present
) -> None:
    root = ET.fromstring(_source_xml(_request(treatment=treatment)))
    transfer = root.find(f'.//{{{CFDI_NAMESPACE}}}Concepto/'
                         f'{{{CFDI_NAMESPACE}}}Impuestos/'
                         f'{{{CFDI_NAMESPACE}}}Traslados/'
                         f'{{{CFDI_NAMESPACE}}}Traslado')
    assert transfer.attrib['TipoFactor'] == factor
    assert ('TasaOCuota' in transfer.attrib) is rate_present
    assert ('Importe' in transfer.attrib) is amount_present


@pytest.mark.parametrize(('method', 'code'), [('CASH', '01'), ('TRANSFER', '03')])
def test_xml_preserves_payment_form(method, code) -> None:
    root = ET.fromstring(_source_xml(_request(method=method)))
    assert root.attrib['FormaPago'] == code


def test_registry_resolves_finkok_adapter() -> None:
    adapter = FinkokFiscalIssuanceAdapter(transport=FakeTransport())
    assert FiscalProviderRegistry({'FINKOK': adapter}).resolve('FINKOK') is adapter


def test_default_app_registry_selects_finkok_demo(settings) -> None:
    app = create_app(settings=settings)
    assert isinstance(
        app.state.fiscal_provider_registry.resolve('FINKOK'),
        FinkokFiscalIssuanceAdapter,
    )
    assert settings.finkok_environment == 'demo'
    assert settings.resolved_finkok_wsdl_endpoint == (
        'https://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl'
    )
    production = settings.model_copy(update={
        'finkok_environment': 'production',
        'finkok_wsdl_endpoint': None,
    })
    assert production.resolved_finkok_wsdl_endpoint == (
        'https://facturacion.finkok.com/servicios/soap/stamp.wsdl'
    )


@pytest.mark.asyncio
async def test_success_normalizes_uuid_timestamp_and_artifact() -> None:
    request = _request()
    adapter = FinkokFiscalIssuanceAdapter(
        transport=FakeTransport(_success(request))
    )
    result = await adapter.issue(request=request, credential=_credential())
    assert result.outcome is FiscalIssuanceOutcome.SUCCEEDED
    assert result.external_reference == UUID
    assert result.fiscal_result.issued_at == datetime(2026, 9, 5, 12, 31)
    artifact = result.fiscal_result.artifacts[0]
    assert (artifact.artifact_kind, artifact.media_type) == (
        'STAMPED_FISCAL_DOCUMENT', 'application/xml'
    )
    assert UUID.encode() in artifact.content


@pytest.mark.asyncio
async def test_rejection_is_sanitized_and_credentials_remain_ephemeral() -> None:
    response = FinkokStampResponse(incidences=(FinkokIncidence(
        code='CFDI40101',
        message=f'Invalid XML for {SECRET_USERNAME} using {SECRET_PASSWORD}',
        work_process_id='work-1',
    ),))
    transport = FakeTransport(response)
    adapter = FinkokFiscalIssuanceAdapter(transport=transport)
    result = await adapter.issue(request=_request(), credential=_credential())
    assert result.outcome is FiscalIssuanceOutcome.REJECTED
    assert result.external_status == 'CFDI40101'
    assert SECRET_USERNAME not in result.error_message
    assert SECRET_PASSWORD not in result.error_message
    assert SECRET_PASSWORD not in repr(_credential())
    assert len(transport.sign_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('error', 'outcome'),
    [
        (FinkokDefiniteTransportError('connect'), FiscalIssuanceOutcome.DEFINITE_FAILURE),
        (FinkokAmbiguousTransportError('timeout'), FiscalIssuanceOutcome.UNCERTAIN),
    ],
)
async def test_transport_failures_normalize_safely(error, outcome) -> None:
    adapter = FinkokFiscalIssuanceAdapter(transport=FakeTransport(error=error))
    result = await adapter.issue(request=_request(), credential=_credential())
    assert result.outcome is outcome
    assert SECRET_PASSWORD not in (result.error_message or '')


@pytest.mark.asyncio
async def test_retry_after_uncertainty_does_not_blindly_restamp() -> None:
    transport = FakeTransport(_success(_request()))
    adapter = FinkokFiscalIssuanceAdapter(transport=transport)
    result = await adapter.issue(
        request=_request().model_copy(update={'is_retry': True}),
        credential=_credential(),
    )
    assert result.outcome is FiscalIssuanceOutcome.UNCERTAIN
    assert not transport.sign_calls


@pytest.mark.asyncio
async def test_recovery_uses_stamped_and_converges_to_same_result() -> None:
    original = _request()
    transport = FakeTransport(_success(original))
    adapter = FinkokFiscalIssuanceAdapter(transport=transport)
    issued = await adapter.issue(request=original, credential=_credential())
    recovered = await adapter.recover(
        request=FiscalIssuanceRecoveryRequest(
            tenant_id=1,
            organization_id=2,
            location_id=3,
            billing_document_id=4,
            operation_reference=original.operation_reference,
            provider_idempotency_key=original.provider_idempotency_key,
            request_fingerprint=original.request_fingerprint,
            request_schema_version=1,
            original_request=original.model_copy(update={'is_retry': True}),
        ),
        credential=_credential(),
    )
    assert recovered.outcome is FiscalRecoveryOutcome.RECOVERED_SUCCESS
    assert recovered.fiscal_result == issued.fiscal_result
    assert len(transport.sign_calls) == 1
    assert len(transport.recovery_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('mismatch', [None, 'issuer', 'recipient', 'total'])
async def test_unverifiable_success_fails_closed(mismatch) -> None:
    request = _request()
    response = (
        FinkokStampResponse(xml='<broken', uuid=UUID, fecha='2026-09-05T12:31:00')
        if mismatch is None else _success(request, mismatch)
    )
    adapter = FinkokFiscalIssuanceAdapter(transport=FakeTransport(response))
    result = await adapter.issue(request=request, credential=_credential())
    assert result.outcome is FiscalIssuanceOutcome.UNCERTAIN


@pytest.mark.asyncio
async def test_missing_credentials_fail_without_transport() -> None:
    transport = FakeTransport(_success(_request()))
    adapter = FinkokFiscalIssuanceAdapter(transport=transport)
    result = await adapter.issue(request=_request(), credential=None)
    assert result.outcome is FiscalIssuanceOutcome.DEFINITE_FAILURE
    assert not transport.sign_calls


@pytest.mark.asyncio
async def test_finkok_demo_smoke_is_separately_opt_in() -> None:
    """Optional DEMO-only transport smoke with externally registered issuer CSD."""
    if os.getenv('RUN_FINKOK_DEMO_TEST') != '1':
        pytest.skip('Set RUN_FINKOK_DEMO_TEST=1 for the explicit DEMO smoke test')
    username = os.getenv('FINKOK_DEMO_USERNAME')
    password = os.getenv('FINKOK_DEMO_PASSWORD')
    encoded_xml = os.getenv('FINKOK_DEMO_UNSIGNED_CFDI_BASE64')
    if not username or not password or not encoded_xml:
        pytest.skip('FINKOK DEMO credentials/XML are not configured')
    try:
        xml = base64.b64decode(encoded_xml, validate=True)
    except ValueError:
        pytest.fail('FINKOK_DEMO_UNSIGNED_CFDI_BASE64 is malformed')
    transport = HttpxFinkokSoapTransport(
        endpoint='https://demo-facturacion.finkok.com/servicios/soap/stamp',
        connect_timeout_seconds=5,
        read_timeout_seconds=30,
    )
    response = await transport.sign_stamp(
        xml=xml,
        username=username,
        password=password,
    )
    assert response.uuid and response.xml
