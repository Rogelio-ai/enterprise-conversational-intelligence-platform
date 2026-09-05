from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.restaurant.billing.contracts import (
    BillingDocumentDetailProjection,
    BillingDocumentLineProjection,
    BillingDocumentLineTaxProjection,
)
from app.restaurant.fiscal.mexico.cfdi40.contracts import (
    MexicoCfdi40Concept,
    MexicoCfdi40ConceptTax,
    MexicoCfdi40Invoice,
    MexicoCfdi40Issuer,
    MexicoCfdi40Recipient,
    MexicoCfdi40SettlementEvidence,
    MexicoCfdi40TaxSummary,
    MexicoCfdi40TaxSummaryTransfer,
)
from app.restaurant.fiscal.mexico.cfdi40.errors import MexicoCfdi40MappingError
from app.restaurant.fiscal.mexico.cfdi40.validator import MexicoCfdi40Validator


ZERO = Decimal('0.0000')
IVA_RATE_16 = Decimal('0.160000')
IVA_RATE_ZERO = Decimal('0.000000')

# Explicit scheme identifiers prevent arbitrary provider-neutral codes from being
# mistaken for SAT catalog codes.
SAT_PRODUCT_CLASSIFICATION_SCHEME = 'SAT-CFDI-4.0-c_ClaveProdServ'
SAT_UNIT_CLASSIFICATION_SCHEME = 'SAT-CFDI-4.0-c_ClaveUnidad'

_TAX_CODES = {'IVA': '002'}
_TAX_REGIMES = {'GENERAL': '601', '601': '601'}
_USO_CFDI = {'GENERAL_EXPENSE': 'G03', 'G03': 'G03'}
_PAYMENT_FORMS = {'CASH': '01', 'TRANSFER': '03'}


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise MexicoCfdi40MappingError(f'{label} is missing or malformed')
    return value


def _mapped(mapping: dict[str, str], value: object, label: str) -> str:
    source = _required_text(value, label)
    try:
        return mapping[source]
    except KeyError as exc:
        raise MexicoCfdi40MappingError(f'{label} is unsupported: {source!r}') from exc


def _fingerprint(value: object, label: str) -> str:
    fingerprint = _required_text(value, label)
    if len(fingerprint) != 64 or any(
        character not in '0123456789abcdef' for character in fingerprint
    ):
        raise MexicoCfdi40MappingError(f'{label} is malformed')
    return fingerprint


class MexicoCfdi40Mapper:
    """Map only frozen BillingDocument and authoritative settlement evidence."""

    def __init__(self, validator: MexicoCfdi40Validator | None = None) -> None:
        self._validator = validator or MexicoCfdi40Validator()

    def map(
        self,
        document: BillingDocumentDetailProjection,
        settlement: MexicoCfdi40SettlementEvidence,
    ) -> MexicoCfdi40Invoice:
        self._validate_source_identity(document, settlement)
        forma_pago = self._forma_pago(settlement)
        concepts = tuple(self._concept(line) for line in document.lines)
        subtotal = sum((concept.importe for concept in concepts), start=ZERO)
        discount = sum((concept.descuento or ZERO for concept in concepts), start=ZERO)
        summary = self._tax_summary(concepts)

        if not isinstance(document.issuer_snapshot, dict) or not isinstance(
            document.recipient_snapshot, dict
        ):
            raise MexicoCfdi40MappingError('Frozen fiscal party evidence is malformed')
        issuer = document.issuer_snapshot
        recipient = document.recipient_snapshot
        _fingerprint(
            document.readiness_evidence_fingerprint, 'Readiness evidence fingerprint'
        )
        if issuer.get('fiscal_postal_code') != document.issuer_fiscal_postal_code:
            raise MexicoCfdi40MappingError(
                'Frozen issuer postal evidence is internally inconsistent'
            )
        invoice = MexicoCfdi40Invoice(
            version='4.0',
            tipo_de_comprobante='I',
            moneda='MXN',
            metodo_pago='PUE',
            forma_pago=forma_pago,
            exportacion='01',
            lugar_expedicion=_required_text(
                document.issuer_fiscal_postal_code, 'Issuer fiscal postal code'
            ),
            subtotal=subtotal,
            descuento=discount if discount > ZERO else None,
            total=Decimal(document.total),
            issuer=MexicoCfdi40Issuer(
                rfc=_required_text(issuer.get('tax_identifier'), 'Issuer RFC'),
                nombre=_required_text(issuer.get('legal_name'), 'Issuer name'),
                regimen_fiscal=_mapped(
                    _TAX_REGIMES, issuer.get('tax_regime'), 'Issuer tax regime'
                ),
            ),
            recipient=MexicoCfdi40Recipient(
                rfc=_required_text(recipient.get('tax_identifier'), 'Recipient RFC'),
                nombre=_required_text(recipient.get('legal_name'), 'Recipient name'),
                domicilio_fiscal_receptor=_required_text(
                    recipient.get('fiscal_postal_code'), 'Recipient fiscal postal code'
                ),
                regimen_fiscal_receptor=_mapped(
                    _TAX_REGIMES,
                    recipient.get('tax_regime'),
                    'Recipient tax regime',
                ),
                uso_cfdi=_mapped(
                    _USO_CFDI, recipient.get('invoice_usage'), 'Recipient invoice usage'
                ),
            ),
            concepts=concepts,
            tax_summary=summary,
        )
        if Decimal(document.tax_total) != summary.total_impuestos_trasladados:
            raise MexicoCfdi40MappingError(
                'Frozen BillingDocument tax total contradicts concept tax evidence'
            )
        self._validator.validate(invoice)
        return invoice

    @staticmethod
    def _validate_source_identity(
        document: BillingDocumentDetailProjection,
        settlement: MexicoCfdi40SettlementEvidence,
    ) -> None:
        if document.document_type != 'INVOICE' or document.status != 'DRAFT':
            raise MexicoCfdi40MappingError('BillingDocument is not CFDI-income eligible')
        if document.currency != 'MXN' or settlement.currency != document.currency:
            raise MexicoCfdi40MappingError('The initial CFDI scope supports MXN only')
        if document.readiness_evidence_fingerprint is None:
            raise MexicoCfdi40MappingError('BillingDocument is not CFDI-ready')
        if (
            settlement.restaurant_check_id != document.restaurant_check_id
            or settlement.check_version != document.source_check_version
            or settlement.check_fingerprint != document.source_check_fingerprint
        ):
            raise MexicoCfdi40MappingError('Settlement does not belong to BillingDocument')
        settlement_amounts = (
            Decimal(settlement.liability_total),
            Decimal(settlement.confirmed_settlement),
            Decimal(settlement.reserved_financial_exposure),
            Decimal(settlement.uncertain_exposure),
        )
        if any(not value.is_finite() or value < ZERO for value in settlement_amounts):
            raise MexicoCfdi40MappingError('Settlement monetary evidence is invalid')
        if (
            settlement.check_status != 'SETTLED'
            or Decimal(settlement.confirmed_settlement) != Decimal(settlement.liability_total)
            or Decimal(settlement.liability_total) != Decimal(document.total)
            or Decimal(settlement.reserved_financial_exposure) != ZERO
            or Decimal(settlement.uncertain_exposure) != ZERO
        ):
            raise MexicoCfdi40MappingError(
                'Whole-check settlement evidence does not prove PUE eligibility'
            )

    @staticmethod
    def _forma_pago(settlement: MexicoCfdi40SettlementEvidence) -> str:
        successful = []
        for payment in settlement.payments:
            amount = Decimal(payment.amount)
            if not amount.is_finite() or amount < ZERO:
                raise MexicoCfdi40MappingError('Payment monetary evidence is invalid')
            if payment.state == 'SUCCEEDED' and amount > ZERO:
                successful.append(payment)
        if len(successful) != 1:
            raise MexicoCfdi40MappingError(
                'Exactly one successful payment form is required'
            )
        payment = successful[0]
        if Decimal(payment.amount) != Decimal(settlement.confirmed_settlement):
            raise MexicoCfdi40MappingError(
                'Payment evidence does not unambiguously cover the settlement'
            )
        return _mapped(_PAYMENT_FORMS, payment.method_category, 'Payment form')

    @staticmethod
    def _concept(line: BillingDocumentLineProjection) -> MexicoCfdi40Concept:
        if line.fiscal_product_classification_scheme != SAT_PRODUCT_CLASSIFICATION_SCHEME:
            raise MexicoCfdi40MappingError('Product classification scheme is unsupported')
        if line.fiscal_unit_classification_scheme != SAT_UNIT_CLASSIFICATION_SCHEME:
            raise MexicoCfdi40MappingError('Unit classification scheme is unsupported')
        required_amounts = (
            line.fiscal_unit_value,
            line.fiscal_line_amount,
            line.fiscal_discount_amount,
        )
        if any(value is None for value in required_amounts):
            raise MexicoCfdi40MappingError('Frozen fiscal line evidence is incomplete')
        _fingerprint(
            line.source_fiscal_evidence_fingerprint,
            'Fiscal product evidence fingerprint',
        )
        taxes = tuple(MexicoCfdi40Mapper._tax(tax) for tax in line.taxes)
        if len(taxes) != 1:
            raise MexicoCfdi40MappingError(
                'The initial CFDI scope requires exactly one IVA tax per concept'
            )
        discount = Decimal(line.fiscal_discount_amount)
        return MexicoCfdi40Concept(
            clave_prod_serv=_required_text(
                line.fiscal_product_classification_code, 'ClaveProdServ'
            ),
            cantidad=Decimal(line.quantity),
            clave_unidad=_required_text(
                line.fiscal_unit_classification_code, 'ClaveUnidad'
            ),
            descripcion=_required_text(line.description, 'Concept description'),
            valor_unitario=Decimal(line.fiscal_unit_value),
            importe=Decimal(line.fiscal_line_amount),
            descuento=discount if discount > ZERO else None,
            objeto_imp='02',
            impuestos_trasladados=taxes,
        )

    @staticmethod
    def _tax(tax: BillingDocumentLineTaxProjection) -> MexicoCfdi40ConceptTax:
        _fingerprint(tax.source_tax_evidence_fingerprint, 'Tax evidence fingerprint')
        if tax.tax_effect == 'WITHHELD':
            raise MexicoCfdi40MappingError('Withheld taxes are outside the initial scope')
        if tax.tax_effect != 'TRANSFERRED':
            raise MexicoCfdi40MappingError('Tax effect is unsupported')
        impuesto = _mapped(_TAX_CODES, tax.tax_category, 'Tax category')
        treatment = tax.tax_treatment
        rate = Decimal(tax.tax_rate)
        amount = Decimal(tax.tax_amount)
        if treatment == 'TAXABLE':
            if rate != IVA_RATE_16:
                raise MexicoCfdi40MappingError('Only transferred IVA at 16% is taxable')
            tipo_factor, tasa_o_cuota, importe = 'Tasa', rate, amount
        elif treatment == 'ZERO_RATE':
            if rate != IVA_RATE_ZERO or amount != ZERO:
                raise MexicoCfdi40MappingError('Zero-rate IVA evidence is inconsistent')
            tipo_factor, tasa_o_cuota, importe = 'Tasa', IVA_RATE_ZERO, ZERO
        elif treatment == 'EXEMPT':
            if rate != IVA_RATE_ZERO or amount != ZERO:
                raise MexicoCfdi40MappingError('Exempt IVA evidence is inconsistent')
            tipo_factor, tasa_o_cuota, importe = 'Exento', None, None
        else:
            raise MexicoCfdi40MappingError(f'Tax treatment is unsupported: {treatment!r}')
        return MexicoCfdi40ConceptTax(
            base=Decimal(tax.taxable_base),
            impuesto=impuesto,
            tipo_factor=tipo_factor,
            tasa_o_cuota=tasa_o_cuota,
            importe=importe,
        )

    @staticmethod
    def _tax_summary(
        concepts: tuple[MexicoCfdi40Concept, ...],
    ) -> MexicoCfdi40TaxSummary:
        groups: dict[tuple[str, str, Decimal | None], list[Decimal]] = defaultdict(
            lambda: [ZERO, ZERO]
        )
        for concept in concepts:
            for tax in concept.impuestos_trasladados:
                values = groups[(tax.impuesto, tax.tipo_factor, tax.tasa_o_cuota)]
                values[0] += tax.base
                values[1] += tax.importe or ZERO
        transfers = tuple(
            MexicoCfdi40TaxSummaryTransfer(
                base=values[0],
                impuesto=key[0],
                tipo_factor=key[1],
                tasa_o_cuota=key[2],
                importe=None if key[1] == 'Exento' else values[1],
            )
            for key, values in sorted(
                groups.items(),
                key=lambda item: (
                    item[0][0], item[0][1],
                    Decimal('-1') if item[0][2] is None else item[0][2],
                ),
            )
        )
        return MexicoCfdi40TaxSummary(
            total_impuestos_trasladados=sum(
                (transfer.importe or ZERO for transfer in transfers), start=ZERO
            ),
            traslados=transfers,
        )
