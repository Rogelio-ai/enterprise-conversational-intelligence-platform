from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from app.restaurant.billing.contracts import (
    BillingDocumentDetailProjection,
    BillingDocumentLineProjection,
    BillingDocumentLineTaxProjection,
)
from app.restaurant.fiscal.mexico.cfdi40 import (
    MexicoCfdi40Mapper,
    MexicoCfdi40PaymentEvidence,
    MexicoCfdi40SettlementEvidence,
    MexicoCfdi40Validator,
)
from app.restaurant.fiscal.mexico.cfdi40.errors import (
    MexicoCfdi40MappingError,
    MexicoCfdi40ValidationError,
)
from app.restaurant.fiscal.mexico.cfdi40.mapper import (
    SAT_PRODUCT_CLASSIFICATION_SCHEME,
    SAT_UNIT_CLASSIFICATION_SCHEME,
)


NOW = datetime(2026, 1, 1)


def _tax(**changes: object) -> BillingDocumentLineTaxProjection:
    values = {
        'id': 31,
        'tax_category': 'IVA',
        'tax_rate': Decimal('0.160000'),
        'taxable_base': Decimal('100.0000'),
        'tax_amount': Decimal('16.0000'),
        'tax_treatment': 'TAXABLE',
        'jurisdiction_code': 'MX',
        'tax_effect': 'TRANSFERRED',
        'source_tax_evidence_fingerprint': 'c' * 64,
        'created_at': NOW,
    }
    values.update(changes)
    return BillingDocumentLineTaxProjection(**values)


def _line(**changes: object) -> BillingDocumentLineProjection:
    values = {
        'id': 21,
        'source_restaurant_order_id': 11,
        'source_restaurant_order_item_id': 12,
        'description': 'Consumo de alimentos',
        'quantity': Decimal('1.0000'),
        # Deliberately different commercial gross values prove E5 does not use them.
        'unit_price': Decimal('116.0000'),
        'base_amount': Decimal('116.0000'),
        'discount_amount': Decimal('0.0000'),
        'commercial_total': Decimal('116.0000'),
        'fiscal_product_classification_scheme': SAT_PRODUCT_CLASSIFICATION_SCHEME,
        'fiscal_product_classification_code': '90101501',
        'fiscal_unit_classification_scheme': SAT_UNIT_CLASSIFICATION_SCHEME,
        'fiscal_unit_classification_code': 'E48',
        'fiscal_unit_value': Decimal('100.0000'),
        'fiscal_line_amount': Decimal('100.0000'),
        'fiscal_discount_amount': Decimal('0.0000'),
        'source_fiscal_evidence_fingerprint': 'b' * 64,
        'created_at': NOW,
        'taxes': (_tax(),),
    }
    values.update(changes)
    return BillingDocumentLineProjection(**values)


def _document(**changes: object) -> BillingDocumentDetailProjection:
    values = {
        'id': 1,
        'tenant_id': 2,
        'organization_id': 3,
        'location_id': 4,
        'restaurant_check_id': 5,
        'source_check_version': 6,
        'source_check_fingerprint': 'a' * 64,
        'document_type': 'INVOICE',
        'status': 'DRAFT',
        'currency': 'MXN',
        'subtotal': Decimal('116.0000'),
        'discount_total': Decimal('0.0000'),
        'tax_total': Decimal('16.0000'),
        'total': Decimal('116.0000'),
        'issuer_snapshot': {
            'legal_name': 'EMISOR SA DE CV',
            'tax_identifier': 'AAA010101AAA',
            'tax_regime': 'GENERAL',
            'fiscal_postal_code': '01000',
        },
        'recipient_snapshot': {
            'legal_name': 'RECEPTOR SA DE CV',
            'tax_identifier': 'BBB010101BBB',
            'tax_regime': 'GENERAL',
            'fiscal_postal_code': '02000',
            'invoice_usage': 'GENERAL_EXPENSE',
        },
        'issuer_fiscal_postal_code': '01000',
        'readiness_evidence_fingerprint': 'd' * 64,
        'created_at': NOW,
        'updated_at': NOW,
        'lines': (_line(),),
    }
    values.update(changes)
    return BillingDocumentDetailProjection(**values)


def _settlement(method: str = 'CASH', **changes: object) -> MexicoCfdi40SettlementEvidence:
    values = {
        'restaurant_check_id': 5,
        'check_status': 'SETTLED',
        'check_version': 6,
        'check_fingerprint': 'a' * 64,
        'currency': 'MXN',
        'liability_total': Decimal('116.0000'),
        'confirmed_settlement': Decimal('116.0000'),
        'reserved_financial_exposure': Decimal('0.0000'),
        'uncertain_exposure': Decimal('0.0000'),
        'payments': (
            MexicoCfdi40PaymentEvidence(
                method_category=method, amount=Decimal('116.0000')
            ),
        ),
    }
    values.update(changes)
    return MexicoCfdi40SettlementEvidence(**values)


def _map(document=None, settlement=None):
    return MexicoCfdi40Mapper().map(document or _document(), settlement or _settlement())


def test_taxable_iva_16_maps_complete_cfdi_semantics() -> None:
    invoice = _map()
    concept = invoice.concepts[0]
    tax = concept.impuestos_trasladados[0]
    assert (invoice.version, invoice.tipo_de_comprobante, invoice.moneda) == ('4.0', 'I', 'MXN')
    assert (invoice.metodo_pago, invoice.exportacion) == ('PUE', '01')
    assert (concept.objeto_imp, tax.impuesto, tax.tipo_factor) == ('02', '002', 'Tasa')
    assert (tax.tasa_o_cuota, tax.importe) == (Decimal('0.160000'), Decimal('16.0000'))


@pytest.mark.parametrize(
    ('treatment', 'factor', 'rate', 'amount'),
    [
        ('ZERO_RATE', 'Tasa', Decimal('0.000000'), Decimal('0.0000')),
        ('EXEMPT', 'Exento', None, None),
    ],
)
def test_zero_rate_and_exempt_iva_map_correctly(treatment, factor, rate, amount) -> None:
    source_tax = _tax(
        tax_treatment=treatment,
        tax_rate=Decimal('0.000000'),
        tax_amount=Decimal('0.0000'),
    )
    document = _document(
        lines=(_line(taxes=(source_tax,), commercial_total=Decimal('100.0000')),),
        subtotal=Decimal('100.0000'),
        tax_total=Decimal('0.0000'),
        total=Decimal('100.0000'),
    )
    invoice = _map(document, _settlement(
        liability_total=Decimal('100.0000'),
        confirmed_settlement=Decimal('100.0000'),
        payments=(MexicoCfdi40PaymentEvidence('CASH', Decimal('100.0000')),),
    ))
    mapped = invoice.concepts[0].impuestos_trasladados[0]
    assert (mapped.tipo_factor, mapped.tasa_o_cuota, mapped.importe) == (factor, rate, amount)


def test_e2_classifications_and_e3_amounts_map_without_gross_recalculation() -> None:
    invoice = _map()
    concept = invoice.concepts[0]
    assert (concept.clave_prod_serv, concept.clave_unidad) == ('90101501', 'E48')
    assert (concept.valor_unitario, concept.importe, invoice.subtotal) == (
        Decimal('100.0000'), Decimal('100.0000'), Decimal('100.0000')
    )


def test_frozen_issuer_recipient_and_lugar_expedicion_map() -> None:
    invoice = _map()
    assert invoice.issuer == replace(invoice.issuer, rfc='AAA010101AAA')
    assert (invoice.issuer.nombre, invoice.issuer.regimen_fiscal) == ('EMISOR SA DE CV', '601')
    assert (
        invoice.recipient.rfc,
        invoice.recipient.nombre,
        invoice.recipient.domicilio_fiscal_receptor,
        invoice.recipient.regimen_fiscal_receptor,
        invoice.recipient.uso_cfdi,
    ) == ('BBB010101BBB', 'RECEPTOR SA DE CV', '02000', '601', 'G03')
    assert invoice.lugar_expedicion == '01000'


@pytest.mark.parametrize(('method', 'code'), [('CASH', '01'), ('TRANSFER', '03')])
def test_supported_single_payment_maps_pue_forma_pago(method, code) -> None:
    invoice = _map(settlement=_settlement(method))
    assert (invoice.metodo_pago, invoice.forma_pago) == ('PUE', code)


def test_withheld_tax_fails_closed() -> None:
    with pytest.raises(MexicoCfdi40MappingError, match='Withheld'):
        _map(_document(lines=(_line(taxes=(_tax(tax_effect='WITHHELD'),)),)))


def test_ambiguous_card_fails_closed() -> None:
    with pytest.raises(MexicoCfdi40MappingError, match='Payment form'):
        _map(settlement=_settlement('CARD'))


def test_multiple_payment_forms_fail_closed() -> None:
    payments = (
        MexicoCfdi40PaymentEvidence('CASH', Decimal('60.0000')),
        MexicoCfdi40PaymentEvidence('TRANSFER', Decimal('56.0000')),
    )
    with pytest.raises(MexicoCfdi40MappingError, match='Exactly one'):
        _map(settlement=_settlement(payments=payments))


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('fiscal_product_classification_scheme', 'INTERNAL', 'Product classification'),
        ('fiscal_unit_classification_scheme', 'INTERNAL', 'Unit classification'),
    ],
)
def test_unsupported_classification_scheme_fails_closed(field, value, message) -> None:
    with pytest.raises(MexicoCfdi40MappingError, match=message):
        _map(_document(lines=(_line(**{field: value}),)))


def test_unsupported_tax_category_fails_closed() -> None:
    with pytest.raises(MexicoCfdi40MappingError, match='Tax category'):
        _map(_document(lines=(_line(taxes=(_tax(tax_category='IEPS'),)),)))


def test_unsupported_uso_cfdi_fails_closed() -> None:
    recipient = dict(_document().recipient_snapshot)
    recipient['invoice_usage'] = 'UNSUPPORTED'
    with pytest.raises(MexicoCfdi40MappingError, match='invoice usage'):
        _map(_document(recipient_snapshot=recipient))


@pytest.mark.parametrize('party', ['issuer', 'recipient'])
def test_unsupported_tax_regime_fails_closed(party) -> None:
    document = _document()
    snapshot = dict(
        document.issuer_snapshot if party == 'issuer' else document.recipient_snapshot
    )
    snapshot['tax_regime'] = 'UNSUPPORTED'
    changes = {f'{party}_snapshot': snapshot}
    with pytest.raises(MexicoCfdi40MappingError, match='tax regime'):
        _map(_document(**changes))


def test_subtotal_discount_tax_total_inconsistency_fails_closed() -> None:
    with pytest.raises(MexicoCfdi40ValidationError, match='inconsistent'):
        _map(_document(total=Decimal('117.0000')), _settlement(
            liability_total=Decimal('117.0000'),
            confirmed_settlement=Decimal('117.0000'),
            payments=(MexicoCfdi40PaymentEvidence('CASH', Decimal('117.0000')),),
        ))


def test_frozen_billing_tax_total_must_equal_concept_summary() -> None:
    with pytest.raises(MexicoCfdi40MappingError, match='tax total'):
        _map(_document(tax_total=Decimal('15.0000')))


def test_validator_detects_tax_summary_drift() -> None:
    invoice = _map()
    bad_summary = replace(
        invoice.tax_summary, total_impuestos_trasladados=Decimal('15.0000')
    )
    with pytest.raises(MexicoCfdi40ValidationError, match='TotalImpuestos'):
        MexicoCfdi40Validator().validate(replace(invoice, tax_summary=bad_summary))


def test_incomplete_settlement_cannot_map_pue() -> None:
    with pytest.raises(MexicoCfdi40MappingError, match='PUE'):
        _map(settlement=_settlement(confirmed_settlement=Decimal('100.0000')))


def test_generic_recipient_rfc_fails_closed() -> None:
    recipient = dict(_document().recipient_snapshot)
    recipient['tax_identifier'] = 'XAXX010101000'
    with pytest.raises(MexicoCfdi40ValidationError, match='named-party RFC'):
        _map(_document(recipient_snapshot=recipient))


def test_discount_maps_from_fiscal_evidence() -> None:
    tax = _tax(taxable_base=Decimal('50.0000'), tax_amount=Decimal('8.0000'))
    line = _line(
        fiscal_discount_amount=Decimal('50.0000'),
        commercial_total=Decimal('58.0000'),
        taxes=(tax,),
    )
    document = _document(
        lines=(line,), discount_total=Decimal('58.0000'),
        tax_total=Decimal('8.0000'), total=Decimal('58.0000'),
    )
    settlement = _settlement(
        liability_total=Decimal('58.0000'), confirmed_settlement=Decimal('58.0000'),
        payments=(MexicoCfdi40PaymentEvidence('CASH', Decimal('58.0000')),),
    )
    invoice = _map(document, settlement)
    assert (invoice.descuento, invoice.concepts[0].descuento) == (
        Decimal('50.0000'), Decimal('50.0000')
    )


def test_repeated_mapping_is_deterministic_and_immutable() -> None:
    mapper = MexicoCfdi40Mapper()
    document = _document()
    settlement = _settlement()
    first = mapper.map(document, settlement)
    second = mapper.map(document, settlement)
    assert first == second
    with pytest.raises((AttributeError, TypeError)):
        first.total = Decimal('0.0000')
