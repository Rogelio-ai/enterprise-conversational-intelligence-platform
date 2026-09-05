from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MexicoCfdi40PaymentEvidence:
    """The minimal immutable settled-payment evidence needed by CFDI mapping."""

    method_category: str
    amount: Decimal
    state: str = 'SUCCEEDED'


@dataclass(frozen=True, slots=True)
class MexicoCfdi40SettlementEvidence:
    """Authoritative whole-check settlement evidence supplied to the pure mapper."""

    restaurant_check_id: int
    check_status: str
    check_version: int
    check_fingerprint: str
    currency: str
    liability_total: Decimal
    confirmed_settlement: Decimal
    reserved_financial_exposure: Decimal
    uncertain_exposure: Decimal
    payments: tuple[MexicoCfdi40PaymentEvidence, ...]


@dataclass(frozen=True, slots=True)
class MexicoCfdi40Issuer:
    rfc: str
    nombre: str
    regimen_fiscal: str


@dataclass(frozen=True, slots=True)
class MexicoCfdi40Recipient:
    rfc: str
    nombre: str
    domicilio_fiscal_receptor: str
    regimen_fiscal_receptor: str
    uso_cfdi: str


@dataclass(frozen=True, slots=True)
class MexicoCfdi40ConceptTax:
    base: Decimal
    impuesto: str
    tipo_factor: str
    tasa_o_cuota: Decimal | None
    importe: Decimal | None


@dataclass(frozen=True, slots=True)
class MexicoCfdi40Concept:
    clave_prod_serv: str
    cantidad: Decimal
    clave_unidad: str
    descripcion: str
    valor_unitario: Decimal
    importe: Decimal
    descuento: Decimal | None
    objeto_imp: str
    impuestos_trasladados: tuple[MexicoCfdi40ConceptTax, ...]


@dataclass(frozen=True, slots=True)
class MexicoCfdi40TaxSummaryTransfer:
    base: Decimal
    impuesto: str
    tipo_factor: str
    tasa_o_cuota: Decimal | None
    importe: Decimal | None


@dataclass(frozen=True, slots=True)
class MexicoCfdi40TaxSummary:
    total_impuestos_trasladados: Decimal
    traslados: tuple[MexicoCfdi40TaxSummaryTransfer, ...]


@dataclass(frozen=True, slots=True)
class MexicoCfdi40Invoice:
    version: str
    tipo_de_comprobante: str
    moneda: str
    metodo_pago: str
    forma_pago: str
    exportacion: str
    lugar_expedicion: str
    subtotal: Decimal
    descuento: Decimal | None
    total: Decimal
    issuer: MexicoCfdi40Issuer
    recipient: MexicoCfdi40Recipient
    concepts: tuple[MexicoCfdi40Concept, ...]
    tax_summary: MexicoCfdi40TaxSummary
