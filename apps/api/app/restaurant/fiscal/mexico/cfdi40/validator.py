from __future__ import annotations

import re
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from app.restaurant.fiscal.mexico.cfdi40.contracts import MexicoCfdi40Invoice
from app.restaurant.fiscal.mexico.cfdi40.errors import MexicoCfdi40ValidationError


ZERO = Decimal('0.0000')
MONEY_UNIT = Decimal('0.0001')
RFC = re.compile(r'^[A-Z&\u00d1]{3,4}[0-9]{6}[A-Z0-9]{3}$')
POSTAL_CODE = re.compile(r'^[0-9]{5}$')
PRODUCT_CODE = re.compile(r'^[0-9]{8}$')
UNIT_CODE = re.compile(r'^[A-Z0-9]{2,3}$')
GENERIC_RFCS = {'XAXX010101000', 'XEXX010101000'}


def _fail(message: str) -> None:
    raise MexicoCfdi40ValidationError(message)


class MexicoCfdi40Validator:
    """Validate the bounded semantic model before any XML exists."""

    def validate(self, invoice: MexicoCfdi40Invoice) -> None:
        if (
            invoice.version != '4.0'
            or invoice.tipo_de_comprobante != 'I'
            or invoice.moneda != 'MXN'
            or invoice.exportacion != '01'
            or invoice.metodo_pago != 'PUE'
        ):
            _fail('CFDI header is outside the approved domestic income/PUE scope')
        if invoice.forma_pago not in {'01', '03'}:
            _fail('FormaPago is unsupported or ambiguous')
        if not POSTAL_CODE.fullmatch(invoice.lugar_expedicion):
            _fail('LugarExpedicion must be a five-digit postal code')
        self._party(invoice)
        if not invoice.concepts:
            _fail('At least one concept is required')

        subtotal = ZERO
        discount = ZERO
        grouped: dict[tuple[str, str, Decimal | None], list[Decimal]] = defaultdict(
            lambda: [ZERO, ZERO]
        )
        for concept in invoice.concepts:
            if not PRODUCT_CODE.fullmatch(concept.clave_prod_serv):
                _fail('ClaveProdServ is not structurally SAT-compatible')
            if not UNIT_CODE.fullmatch(concept.clave_unidad):
                _fail('ClaveUnidad is not structurally SAT-compatible')
            amounts = (
                concept.cantidad,
                concept.valor_unitario,
                concept.importe,
                concept.descuento if concept.descuento is not None else ZERO,
            )
            if any(not value.is_finite() for value in amounts) or (
                concept.cantidad <= ZERO
                or concept.valor_unitario < ZERO
                or concept.importe < ZERO
                or (concept.descuento is not None and concept.descuento < ZERO)
            ):
                _fail('Concept contains an invalid quantity or fiscal amount')
            if not concept.descripcion or concept.descripcion != concept.descripcion.strip():
                _fail('Concept description is missing or malformed')
            if concept.importe != concept.valor_unitario * concept.cantidad:
                _fail('Concept Importe contradicts authoritative unit value and quantity')
            concept_discount = concept.descuento or ZERO
            if concept_discount > concept.importe:
                _fail('Concept discount exceeds Importe')
            if concept.objeto_imp != '02' or len(concept.impuestos_trasladados) != 1:
                _fail('ObjetoImp and concept tax nodes are inconsistent')
            tax = concept.impuestos_trasladados[0]
            if tax.base != concept.importe - concept_discount:
                _fail('Concept tax base contradicts fiscal line evidence')
            self._tax(tax)
            subtotal += concept.importe
            discount += concept_discount
            values = grouped[(tax.impuesto, tax.tipo_factor, tax.tasa_o_cuota)]
            values[0] += tax.base
            values[1] += tax.importe or ZERO

        if invoice.subtotal != subtotal:
            _fail('Invoice SubTotal does not equal concept Importe evidence')
        expected_discount = discount if discount > ZERO else None
        if invoice.descuento != expected_discount:
            _fail('Invoice Descuento does not equal concept discount evidence')
        summary_groups = {
            (item.impuesto, item.tipo_factor, item.tasa_o_cuota): (
                item.base, item.importe or ZERO
            )
            for item in invoice.tax_summary.traslados
        }
        expected_groups = {key: tuple(values) for key, values in grouped.items()}
        if (
            len(summary_groups) != len(invoice.tax_summary.traslados)
            or summary_groups != expected_groups
        ):
            _fail('Invoice tax summary does not equal concept tax evidence')
        transferred = sum((values[1] for values in expected_groups.values()), start=ZERO)
        if invoice.tax_summary.total_impuestos_trasladados != transferred:
            _fail('TotalImpuestosTrasladados is inconsistent')
        if invoice.subtotal - discount + transferred != invoice.total:
            _fail('SubTotal, Descuento, transferred taxes, and Total are inconsistent')

    @staticmethod
    def _party(invoice: MexicoCfdi40Invoice) -> None:
        parties = (
            ('Issuer', invoice.issuer.rfc, invoice.issuer.nombre),
            ('Recipient', invoice.recipient.rfc, invoice.recipient.nombre),
        )
        for label, rfc, name in parties:
            if not RFC.fullmatch(rfc) or rfc in GENERIC_RFCS:
                _fail(f'{label} RFC is not a supported domestic named-party RFC')
            if not name or name != name.strip():
                _fail(f'{label} name is missing or malformed')
        if invoice.issuer.regimen_fiscal != '601':
            _fail('Issuer RegimenFiscal is unsupported')
        if invoice.recipient.regimen_fiscal_receptor != '601':
            _fail('Recipient RegimenFiscalReceptor is unsupported')
        if invoice.recipient.uso_cfdi != 'G03':
            _fail('Recipient UsoCFDI is unsupported')
        if not POSTAL_CODE.fullmatch(invoice.recipient.domicilio_fiscal_receptor):
            _fail('DomicilioFiscalReceptor must be a five-digit postal code')

    @staticmethod
    def _tax(tax) -> None:
        if not tax.base.is_finite() or tax.base < ZERO or tax.impuesto != '002':
            _fail('Only nonnegative transferred IVA evidence is supported')
        if tax.tipo_factor == 'Exento':
            if tax.tasa_o_cuota is not None or tax.importe is not None:
                _fail('Exempt IVA must omit TasaOCuota and Importe')
            return
        if tax.tipo_factor != 'Tasa' or tax.tasa_o_cuota not in {
            Decimal('0.000000'), Decimal('0.160000')
        }:
            _fail('Only IVA Tasa at 0% or 16% is supported')
        if (
            not tax.tasa_o_cuota.is_finite()
            or tax.importe is None
            or not tax.importe.is_finite()
            or tax.importe < ZERO
        ):
            _fail('IVA Tasa requires a nonnegative Importe')
        expected = (tax.base * tax.tasa_o_cuota).quantize(
            MONEY_UNIT, rounding=ROUND_HALF_UP
        )
        if tax.importe != expected:
            _fail('IVA amount is inconsistent with Base and TasaOCuota')
