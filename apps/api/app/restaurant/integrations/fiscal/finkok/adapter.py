from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from app.restaurant.billing.contracts import (
    BillingDocumentDetailProjection,
    BillingDocumentLineProjection,
    BillingDocumentLineTaxProjection,
)
from app.restaurant.fiscal.mexico.cfdi40 import (
    MexicoCfdi40Mapper,
    MexicoCfdi40PaymentEvidence,
    MexicoCfdi40SettlementEvidence,
    MexicoCfdi40XmlSerializer,
)
from app.restaurant.integrations.fiscal.contracts import (
    AuthoritativeFiscalResult,
    EphemeralFiscalProviderCredential,
    FiscalArtifactEvidence,
    FiscalIssuanceOutcome,
    FiscalIssuanceRecoveryRequest,
    FiscalIssuanceRequest,
    FiscalIssuanceResult,
    FiscalProviderErrorKind,
    FiscalRecoveryOutcome,
    FiscalRecoveryResult,
)
from app.restaurant.integrations.fiscal.finkok.transport import (
    FinkokAmbiguousTransportError,
    FinkokDefiniteTransportError,
    FinkokSoapTransport,
    FinkokStampResponse,
)


CFDI_NAMESPACE = 'http://www.sat.gob.mx/cfd/4'
TFD_NAMESPACE = 'http://www.sat.gob.mx/TimbreFiscalDigital'
UUID = re.compile(
    r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$'
)


@dataclass(frozen=True, slots=True)
class _Credentials:
    username: str
    password: str


class _InvalidProviderResult(ValueError):
    pass


def _safe(value: str | None, *, secrets: tuple[str, ...], maximum: int) -> str | None:
    if value is None:
        return None
    sanitized = ' '.join(value.split())
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, '[REDACTED]')
    return sanitized[:maximum] or None


def _credentials(
    credential: EphemeralFiscalProviderCredential | None,
) -> _Credentials:
    if credential is None:
        raise ValueError('FINKOK credential is required')
    try:
        raw = json.loads(credential.value.get_secret_value())
        username = raw['username'].strip()
        password = raw['password']
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        raise ValueError('FINKOK credential is malformed') from None
    if not username or not isinstance(password, str) or not password:
        raise ValueError('FINKOK credential is malformed')
    return _Credentials(username=username, password=password)


def _source(request: FiscalIssuanceRequest) -> tuple[BillingDocumentDetailProjection, MexicoCfdi40SettlementEvidence]:
    settlement = request.settlement
    if (
        settlement is None
        or request.source_check_version is None
        or request.source_check_fingerprint is None
        or request.readiness_evidence_fingerprint is None
        or request.issued_at is None
    ):
        raise ValueError('FINKOK requires complete frozen CFDI issuance evidence')
    now = request.issued_at
    lines = tuple(BillingDocumentLineProjection(
        id=line.billing_document_line_id,
        source_restaurant_order_id=line.billing_document_line_id,
        source_restaurant_order_item_id=line.billing_document_line_id,
        description=line.description,
        quantity=line.quantity,
        unit_price=line.unit_price,
        base_amount=line.base_amount,
        discount_amount=line.discount_amount,
        commercial_total=line.total,
        fiscal_product_classification_scheme=line.fiscal_product_classification_scheme,
        fiscal_product_classification_code=line.fiscal_product_classification_code,
        fiscal_unit_classification_scheme=line.fiscal_unit_classification_scheme,
        fiscal_unit_classification_code=line.fiscal_unit_classification_code,
        fiscal_unit_value=line.fiscal_unit_value,
        fiscal_line_amount=line.fiscal_line_amount,
        fiscal_discount_amount=line.fiscal_discount_amount,
        source_fiscal_evidence_fingerprint=line.source_fiscal_evidence_fingerprint,
        created_at=now,
        taxes=tuple(BillingDocumentLineTaxProjection(
            id=tax.billing_document_line_tax_id,
            tax_category=tax.category,
            tax_rate=tax.rate,
            taxable_base=tax.taxable_base,
            tax_amount=tax.amount,
            tax_treatment=tax.treatment,
            jurisdiction_code=tax.jurisdiction_code,
            tax_effect=tax.tax_effect,
            source_tax_evidence_fingerprint=tax.source_tax_evidence_fingerprint,
            created_at=now,
        ) for tax in line.taxes),
    ) for line in request.lines)
    issuer = {
        'legal_name': request.issuer.legal_name,
        'tax_identifier': request.issuer.tax_identifier,
        'tax_regime': request.issuer.tax_regime,
        'fiscal_postal_code': request.issuer.postal_code,
    }
    recipient = {
        'legal_name': request.recipient.legal_name,
        'tax_identifier': request.recipient.tax_identifier,
        'tax_regime': request.recipient.tax_regime,
        'fiscal_postal_code': request.recipient.postal_code,
        'invoice_usage': request.recipient.document_usage,
    }
    document = BillingDocumentDetailProjection(
        id=request.billing_document_id,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        location_id=request.location_id,
        restaurant_check_id=settlement.restaurant_check_id,
        source_check_version=request.source_check_version,
        source_check_fingerprint=request.source_check_fingerprint,
        document_type=request.document_type,
        status='DRAFT',
        currency=request.currency,
        subtotal=request.subtotal,
        discount_total=request.discount_total,
        tax_total=request.tax_total,
        total=request.total,
        issuer_snapshot=issuer,
        recipient_snapshot=recipient,
        issuer_fiscal_postal_code=request.issuer.postal_code,
        readiness_evidence_fingerprint=request.readiness_evidence_fingerprint,
        created_at=now,
        updated_at=now,
        lines=lines,
    )
    evidence = MexicoCfdi40SettlementEvidence(
        restaurant_check_id=settlement.restaurant_check_id,
        check_status=settlement.check_status,
        check_version=settlement.check_version,
        check_fingerprint=settlement.check_fingerprint,
        currency=settlement.currency,
        liability_total=settlement.liability_total,
        confirmed_settlement=settlement.confirmed_settlement,
        reserved_financial_exposure=settlement.reserved_financial_exposure,
        uncertain_exposure=settlement.uncertain_exposure,
        payments=tuple(MexicoCfdi40PaymentEvidence(
            method_category=payment.method_category,
            amount=payment.amount,
            state=payment.state,
        ) for payment in settlement.payments),
    )
    return document, evidence


class FinkokFiscalIssuanceAdapter:
    """FINKOK Sign_Stamp adapter; issuer CSD registration is external."""

    def __init__(
        self,
        *,
        transport: FinkokSoapTransport,
        mapper: MexicoCfdi40Mapper | None = None,
        serializer: MexicoCfdi40XmlSerializer | None = None,
    ) -> None:
        self._transport = transport
        self._mapper = mapper or MexicoCfdi40Mapper()
        self._serializer = serializer or MexicoCfdi40XmlSerializer()

    def _xml(self, request: FiscalIssuanceRequest) -> bytes:
        document, settlement = _source(request)
        invoice = self._mapper.map(document, settlement)
        assert request.issued_at is not None
        return self._serializer.serialize(invoice, issued_at=request.issued_at)

    async def issue(
        self,
        *,
        request: FiscalIssuanceRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalIssuanceResult:
        if request.is_retry:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.UNCERTAIN,
                error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
                error_message='FINKOK recovery is required before another stamp attempt',
            )
        try:
            auth = _credentials(credential)
            source_xml = self._xml(request)
        except ValueError:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.DEFINITE_FAILURE,
                error_kind=FiscalProviderErrorKind.TECHNICAL_FAILURE,
                error_message='FINKOK request evidence or credential is invalid',
            )
        try:
            response = await self._transport.sign_stamp(
                xml=source_xml,
                username=auth.username,
                password=auth.password,
            )
        except FinkokDefiniteTransportError:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.DEFINITE_FAILURE,
                error_kind=FiscalProviderErrorKind.TECHNICAL_FAILURE,
                error_message='FINKOK could not be reached before acceptance',
            )
        except FinkokAmbiguousTransportError:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.UNCERTAIN,
                error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
                error_message='FINKOK may have accepted the CFDI; recovery is required',
            )
        return self._issuance_result(response, request=request, auth=auth)

    async def recover(
        self,
        *,
        request: FiscalIssuanceRecoveryRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalRecoveryResult:
        try:
            auth = _credentials(credential)
            if request.original_request is None:
                raise ValueError('Original evidence is unavailable')
            source_xml = self._xml(request.original_request)
        except ValueError:
            return FiscalRecoveryResult(
                outcome=FiscalRecoveryOutcome.STILL_UNCERTAIN,
                error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
                error_message='FINKOK recovery evidence or credential is invalid',
            )
        try:
            response = await self._transport.stamped(
                xml=source_xml,
                username=auth.username,
                password=auth.password,
            )
        except (FinkokDefiniteTransportError, FinkokAmbiguousTransportError):
            return FiscalRecoveryResult(
                outcome=FiscalRecoveryOutcome.STILL_UNCERTAIN,
                error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
                error_message='FINKOK recovery remains inconclusive',
            )
        if response.incidences or response.fault_code or response.fault_message:
            evidence = self._rejection(response, auth)
            return FiscalRecoveryResult(
                outcome=FiscalRecoveryOutcome.REJECTED,
                **evidence,
            )
        try:
            fiscal_result, status = self._verified(response, request.original_request)
        except _InvalidProviderResult:
            return FiscalRecoveryResult(
                outcome=FiscalRecoveryOutcome.STILL_UNCERTAIN,
                error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
                error_message='FINKOK recovery did not provide authoritative evidence',
            )
        return FiscalRecoveryResult(
            outcome=FiscalRecoveryOutcome.RECOVERED_SUCCESS,
            external_reference=fiscal_result.external_fiscal_identifier,
            external_status=status,
            fiscal_result=fiscal_result,
        )

    def _issuance_result(
        self,
        response: FinkokStampResponse,
        *,
        request: FiscalIssuanceRequest,
        auth: _Credentials,
    ) -> FiscalIssuanceResult:
        if response.incidences:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.REJECTED,
                **self._rejection(response, auth),
            )
        if response.fault_code or response.fault_message:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.DEFINITE_FAILURE,
                **self._technical_failure(response, auth),
            )
        try:
            fiscal_result, status = self._verified(response, request)
        except _InvalidProviderResult:
            return FiscalIssuanceResult(
                outcome=FiscalIssuanceOutcome.UNCERTAIN,
                error_kind=FiscalProviderErrorKind.AMBIGUOUS_RESULT,
                error_message='FINKOK response did not establish authoritative success',
            )
        return FiscalIssuanceResult(
            outcome=FiscalIssuanceOutcome.SUCCEEDED,
            external_reference=fiscal_result.external_fiscal_identifier,
            external_status=status,
            fiscal_result=fiscal_result,
        )

    @staticmethod
    def _rejection(response: FinkokStampResponse, auth: _Credentials) -> dict:
        incidence = response.incidences[0] if response.incidences else None
        secrets = (auth.username, auth.password)
        return {
            'external_reference': _safe(
                incidence.work_process_id if incidence else None,
                secrets=secrets,
                maximum=200,
            ),
            'external_status': _safe(
                incidence.code if incidence else response.fault_code,
                secrets=secrets,
                maximum=64,
            ),
            'error_kind': FiscalProviderErrorKind.BUSINESS_REJECTION,
            'error_message': _safe(
                incidence.message if incidence else response.fault_message,
                secrets=secrets,
                maximum=500,
            ) or 'FINKOK rejected the CFDI',
        }

    @staticmethod
    def _technical_failure(response: FinkokStampResponse, auth: _Credentials) -> dict:
        secrets = (auth.username, auth.password)
        return {
            'external_status': _safe(
                response.fault_code, secrets=secrets, maximum=64
            ),
            'error_kind': FiscalProviderErrorKind.TECHNICAL_FAILURE,
            'error_message': _safe(
                response.fault_message, secrets=secrets, maximum=500
            ) or 'FINKOK returned a technical fault',
        }

    @staticmethod
    def _verified(
        response: FinkokStampResponse,
        request: FiscalIssuanceRequest,
    ) -> tuple[AuthoritativeFiscalResult, str]:
        if not response.xml or not response.uuid:
            raise _InvalidProviderResult('Missing stamped evidence')
        uuid = response.uuid.strip().upper()
        if not UUID.fullmatch(uuid):
            raise _InvalidProviderResult('Malformed UUID')
        stamped = response.xml.encode('utf-8')
        try:
            root = ET.fromstring(stamped)
            issuer = root.find(f'{{{CFDI_NAMESPACE}}}Emisor')
            recipient = root.find(f'{{{CFDI_NAMESPACE}}}Receptor')
            timbre = root.find(f'.//{{{TFD_NAMESPACE}}}TimbreFiscalDigital')
            total = Decimal(root.attrib['Total'])
        except (ET.ParseError, KeyError, InvalidOperation) as exc:
            raise _InvalidProviderResult('Malformed stamped XML') from exc
        if (
            root.tag != f'{{{CFDI_NAMESPACE}}}Comprobante'
            or root.attrib.get('Version') != '4.0'
            or issuer is None
            or issuer.attrib.get('Rfc') != request.issuer.tax_identifier
            or recipient is None
            or recipient.attrib.get('Rfc') != request.recipient.tax_identifier
            or total != request.total
            or timbre is None
            or timbre.attrib.get('UUID', '').upper() != uuid
        ):
            raise _InvalidProviderResult('Stamped XML contradicts expected invoice')
        xml_timestamp = timbre.attrib.get('FechaTimbrado')
        timestamp = response.fecha or xml_timestamp
        if not timestamp:
            raise _InvalidProviderResult('Missing stamped timestamp')
        try:
            issued_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if response.fecha and xml_timestamp:
                response_instant = datetime.fromisoformat(
                    response.fecha.replace('Z', '+00:00')
                )
                xml_instant = datetime.fromisoformat(
                    xml_timestamp.replace('Z', '+00:00')
                )
                if response_instant != xml_instant:
                    raise _InvalidProviderResult(
                        'Response timestamp contradicts stamped XML'
                    )
        except ValueError as exc:
            raise _InvalidProviderResult('Malformed stamped timestamp') from exc
        if issued_at.tzinfo is not None:
            issued_at = issued_at.astimezone(UTC).replace(tzinfo=None)
        status = (response.status or 'STAMPED')[:64]
        return AuthoritativeFiscalResult(
            external_fiscal_identifier=uuid,
            fiscal_document_type='CFDI',
            fiscal_document_version='4.0',
            issued_at=issued_at,
            artifacts=(FiscalArtifactEvidence(
                artifact_kind='STAMPED_FISCAL_DOCUMENT',
                media_type='application/xml',
                content=stamped,
                provider_artifact_reference=uuid,
            ),),
        ), status
