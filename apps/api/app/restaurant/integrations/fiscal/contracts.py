from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact numbers')
    return value


ExactAmount = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(ge=0, allow_inf_nan=False),
]
PositiveQuantity = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(gt=0, allow_inf_nan=False),
]
TaxRate = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(ge=0, allow_inf_nan=False),
]


class FiscalContractValue(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)


class FiscalIssuanceOutcome(StrEnum):
    SUCCEEDED = 'SUCCEEDED'
    DEFINITE_FAILURE = 'DEFINITE_FAILURE'
    REJECTED = 'REJECTED'
    UNCERTAIN = 'UNCERTAIN'


class FiscalRecoveryOutcome(StrEnum):
    RECOVERED_SUCCESS = 'RECOVERED_SUCCESS'
    DEFINITE_ABSENCE = 'DEFINITE_ABSENCE'
    DEFINITE_FAILURE = 'DEFINITE_FAILURE'
    REJECTED = 'REJECTED'
    STILL_UNCERTAIN = 'STILL_UNCERTAIN'


class FiscalProviderErrorKind(StrEnum):
    TECHNICAL_FAILURE = 'TECHNICAL_FAILURE'
    BUSINESS_REJECTION = 'BUSINESS_REJECTION'
    AMBIGUOUS_RESULT = 'AMBIGUOUS_RESULT'


class EphemeralFiscalProviderCredential(FiscalContractValue):
    """Opaque provider authentication material that must never become durable."""

    value: SecretStr


class FrozenFiscalPartySnapshot(FiscalContractValue):
    legal_name: str = Field(min_length=1, max_length=200)
    tax_identifier: str = Field(min_length=1, max_length=64)
    tax_regime: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=32)
    document_usage: str | None = Field(default=None, min_length=1, max_length=64)


class FiscalIssuanceLineTax(FiscalContractValue):
    billing_document_line_tax_id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=64)
    treatment: str = Field(min_length=1, max_length=32)
    rate: TaxRate
    taxable_base: ExactAmount
    amount: ExactAmount


class FiscalIssuanceLine(FiscalContractValue):
    billing_document_line_id: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=500)
    quantity: PositiveQuantity
    unit_price: ExactAmount
    base_amount: ExactAmount
    discount_amount: ExactAmount
    total: ExactAmount
    taxes: tuple[FiscalIssuanceLineTax, ...] = ()


class FiscalIssuanceRequest(FiscalContractValue):
    tenant_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    billing_document_id: int = Field(gt=0)
    operation_reference: str = Field(min_length=1, max_length=200)
    provider_idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(
        min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    request_schema_version: int = Field(ge=1)
    document_type: str = Field(min_length=1, max_length=16)
    currency: str = Field(min_length=3, max_length=3)
    subtotal: ExactAmount
    discount_total: ExactAmount
    tax_total: ExactAmount
    total: ExactAmount
    issuer: FrozenFiscalPartySnapshot
    recipient: FrozenFiscalPartySnapshot
    lines: tuple[FiscalIssuanceLine, ...] = Field(min_length=1)

    @field_validator('currency', mode='before')
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if not value.isalpha() or not value.isascii():
            raise ValueError('Currency must be a three-letter ASCII code')
        return value


class FiscalIssuanceRecoveryRequest(FiscalContractValue):
    tenant_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    billing_document_id: int = Field(gt=0)
    operation_reference: str = Field(min_length=1, max_length=200)
    provider_idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(
        min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    request_schema_version: int = Field(ge=1)
    external_reference: str | None = Field(default=None, min_length=1, max_length=200)


class SafeFiscalProviderEvidence(FiscalContractValue):
    external_reference: str | None = Field(default=None, min_length=1, max_length=200)
    external_status: str | None = Field(default=None, min_length=1, max_length=64)
    error_kind: FiscalProviderErrorKind | None = None
    error_message: str | None = Field(default=None, min_length=1, max_length=500)


class FiscalIssuanceResult(SafeFiscalProviderEvidence):
    outcome: FiscalIssuanceOutcome

    @model_validator(mode='after')
    def validate_outcome_evidence(self):
        if self.outcome is FiscalIssuanceOutcome.SUCCEEDED:
            if self.external_reference is None:
                raise ValueError('Successful issuance requires an external reference')
            if self.error_kind is not None or self.error_message is not None:
                raise ValueError('Successful issuance cannot carry error evidence')
        elif self.error_kind is None:
            raise ValueError('Non-successful issuance requires an error kind')
        return self


class FiscalRecoveryResult(SafeFiscalProviderEvidence):
    outcome: FiscalRecoveryOutcome

    @model_validator(mode='after')
    def validate_outcome_evidence(self):
        if self.outcome is FiscalRecoveryOutcome.RECOVERED_SUCCESS:
            if self.external_reference is None:
                raise ValueError('Recovered success requires an external reference')
            if self.error_kind is not None or self.error_message is not None:
                raise ValueError('Recovered success cannot carry error evidence')
        elif self.outcome is FiscalRecoveryOutcome.DEFINITE_ABSENCE:
            if self.external_reference is not None:
                raise ValueError('Definite absence cannot carry an external reference')
            if self.error_kind is not None or self.error_message is not None:
                raise ValueError('Definite absence cannot carry error evidence')
        elif self.error_kind is None:
            raise ValueError('Failed or uncertain recovery requires an error kind')
        return self
