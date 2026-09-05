from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

from app.restaurant.fiscal.mexico.cfdi40.contracts import MexicoCfdi40Invoice
from app.restaurant.fiscal.mexico.cfdi40.validator import MexicoCfdi40Validator


CFDI_NAMESPACE = 'http://www.sat.gob.mx/cfd/4'
XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
CFDI_SCHEMA_LOCATION = (
    'http://www.sat.gob.mx/cfd/4 '
    'http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd'
)
MEXICO_CITY = ZoneInfo('America/Mexico_City')

ET.register_namespace('cfdi', CFDI_NAMESPACE)
ET.register_namespace('xsi', XSI_NAMESPACE)


def _tag(name: str) -> str:
    return f'{{{CFDI_NAMESPACE}}}{name}'


def _decimal(value: Decimal, *, fixed: int | None = None) -> str:
    if fixed is not None:
        return f'{value:.{fixed}f}'
    rendered = format(value, 'f')
    if '.' in rendered:
        rendered = rendered.rstrip('0').rstrip('.')
    return rendered or '0'


class MexicoCfdi40XmlSerializer:
    """Serialize a validated bounded CFDI model without reconstructing evidence."""

    def __init__(self, validator: MexicoCfdi40Validator | None = None) -> None:
        self._validator = validator or MexicoCfdi40Validator()

    def serialize(self, invoice: MexicoCfdi40Invoice, *, issued_at: datetime) -> bytes:
        self._validator.validate(invoice)
        instant = issued_at.replace(tzinfo=UTC) if issued_at.tzinfo is None else issued_at
        fecha = instant.astimezone(MEXICO_CITY).replace(
            tzinfo=None, microsecond=0
        ).isoformat()
        root_attributes = {
            'Version': invoice.version,
            'Fecha': fecha,
            'Sello': '',
            'FormaPago': invoice.forma_pago,
            'NoCertificado': '',
            'Certificado': '',
            'SubTotal': _decimal(invoice.subtotal),
        }
        if invoice.descuento is not None:
            root_attributes['Descuento'] = _decimal(invoice.descuento)
        root_attributes.update({
            'Moneda': invoice.moneda,
            'Total': _decimal(invoice.total),
            'TipoDeComprobante': invoice.tipo_de_comprobante,
            'Exportacion': invoice.exportacion,
            'MetodoPago': invoice.metodo_pago,
            'LugarExpedicion': invoice.lugar_expedicion,
            f'{{{XSI_NAMESPACE}}}schemaLocation': CFDI_SCHEMA_LOCATION,
        })
        root = ET.Element(_tag('Comprobante'), root_attributes)
        ET.SubElement(root, _tag('Emisor'), {
            'Rfc': invoice.issuer.rfc,
            'Nombre': invoice.issuer.nombre,
            'RegimenFiscal': invoice.issuer.regimen_fiscal,
        })
        ET.SubElement(root, _tag('Receptor'), {
            'Rfc': invoice.recipient.rfc,
            'Nombre': invoice.recipient.nombre,
            'DomicilioFiscalReceptor': (
                invoice.recipient.domicilio_fiscal_receptor
            ),
            'RegimenFiscalReceptor': invoice.recipient.regimen_fiscal_receptor,
            'UsoCFDI': invoice.recipient.uso_cfdi,
        })
        concepts = ET.SubElement(root, _tag('Conceptos'))
        for concept in invoice.concepts:
            attributes = {
                'ClaveProdServ': concept.clave_prod_serv,
                'Cantidad': _decimal(concept.cantidad),
                'ClaveUnidad': concept.clave_unidad,
                'Descripcion': concept.descripcion,
                'ValorUnitario': _decimal(concept.valor_unitario),
                'Importe': _decimal(concept.importe),
            }
            if concept.descuento is not None:
                attributes['Descuento'] = _decimal(concept.descuento)
            attributes['ObjetoImp'] = concept.objeto_imp
            concept_node = ET.SubElement(concepts, _tag('Concepto'), attributes)
            taxes = ET.SubElement(concept_node, _tag('Impuestos'))
            transfers = ET.SubElement(taxes, _tag('Traslados'))
            for tax in concept.impuestos_trasladados:
                tax_attributes = {
                    'Base': _decimal(tax.base),
                    'Impuesto': tax.impuesto,
                    'TipoFactor': tax.tipo_factor,
                }
                if tax.tasa_o_cuota is not None:
                    tax_attributes['TasaOCuota'] = _decimal(
                        tax.tasa_o_cuota, fixed=6
                    )
                if tax.importe is not None:
                    tax_attributes['Importe'] = _decimal(tax.importe)
                ET.SubElement(transfers, _tag('Traslado'), tax_attributes)

        summary_attributes = {}
        if any(
            tax.tipo_factor != 'Exento'
            for tax in invoice.tax_summary.traslados
        ):
            summary_attributes['TotalImpuestosTrasladados'] = _decimal(
                invoice.tax_summary.total_impuestos_trasladados
            )
        taxes = ET.SubElement(root, _tag('Impuestos'), summary_attributes)
        transfers = ET.SubElement(taxes, _tag('Traslados'))
        for tax in invoice.tax_summary.traslados:
            attributes = {
                'Base': _decimal(tax.base),
                'Impuesto': tax.impuesto,
                'TipoFactor': tax.tipo_factor,
            }
            if tax.tasa_o_cuota is not None:
                attributes['TasaOCuota'] = _decimal(tax.tasa_o_cuota, fixed=6)
            if tax.importe is not None:
                attributes['Importe'] = _decimal(tax.importe)
            ET.SubElement(transfers, _tag('Traslado'), attributes)
        return ET.tostring(root, encoding='utf-8', xml_declaration=True)
