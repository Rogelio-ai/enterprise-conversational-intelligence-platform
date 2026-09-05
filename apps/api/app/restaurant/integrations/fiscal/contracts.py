from __future__ import annotations

from datetime import datetime
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
    jurisdiction_code: str | None = Field(default=None, min_length=1, max_length=64)
    tax_effect: str | None = Field(default=None, min_length=1, max_length=32)
    source_tax_evidence_fingerprint: str | None = Field(
        default=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )


class FiscalIssuanceLine(FiscalContractValue):
    billing_document_line_id: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=500)
    quantity: PositiveQuantity
    unit_price: ExactAmount
    base_amount: ExactAmount
    discount_amount: ExactAmount
    total: ExactAmount
    taxes: tuple[FiscalIssuanceLineTax, ...] = ()
    fiscal_product_classification_scheme: str | None = Field(
        default=None, min_length=1, max_length=128
    )
    fiscal_product_classification_code: str | None = Field(
        default=None, min_length=1, max_length=64
    )
    fiscal_unit_classification_scheme: str | None = Field(
        default=None, min_length=1, max_length=128
    )
    fiscal_unit_classification_code: str | None = Field(
        default=None, min_length=1, max_length=64
    )
    fiscal_unit_value: ExactAmount | None = None
    fiscal_line_amount: ExactAmount | None = None
    fiscal_discount_amount: ExactAmount | None = None
    source_fiscal_evidence_fingerprint: str | None = Field(
        default=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )


class FrozenFiscalPaymentEvidence(FiscalContractValue):
    method_category: str = Field(min_length=1, max_length=32)
    amount: ExactAmount
    state: str = Field(min_length=1, max_length=32)


class FrozenFiscalSettlementEvidence(FiscalContractValue):
    restaurant_check_id: int = Field(gt=0)
    check_status: str = Field(min_length=1, max_length=32)
    check_version: int = Field(ge=1)
    check_fingerprint: str = Field(
        min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    currency: str = Field(min_length=3, max_length=3)
    liability_total: ExactAmount
    confirmed_settlement: ExactAmount
    reserved_financial_exposure: ExactAmount
    uncertain_exposure: ExactAmount
    payments: tuple[FrozenFiscalPaymentEvidence, ...]


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
    source_check_version: int | None = Field(default=None, ge=1)
    source_check_fingerprint: str | None = Field(
        default=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    readiness_evidence_fingerprint: str | None = Field(
        default=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    settlement: FrozenFiscalSettlementEvidence | None = None
    issued_at: datetime | None = None
    is_retry: bool = False

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
    external_status: str | None = Field(default=None, min_length=1, max_length=64)
    original_request: FiscalIssuanceRequest | None = None


class SafeFiscalProviderEvidence(FiscalContractValue):
    external_reference: str | None = Field(default=None, min_length=1, max_length=200)
    external_status: str | None = Field(default=None, min_length=1, max_length=64)
    error_kind: FiscalProviderErrorKind | None = None
    error_message: str | None = Field(default=None, min_length=1, max_length=500)


class FiscalArtifactEvidence(FiscalContractValue):
    """Provider artifact payload or an already-durable provider reference."""

    artifact_kind: str = Field(min_length=1, max_length=64)
    media_type: str = Field(min_length=1, max_length=128)
    content: bytes | None = None
    storage_strategy: str | None = Field(default=None, min_length=1, max_length=64)
    storage_reference: str | None = Field(default=None, min_length=1, max_length=500)
    content_hash: str | None = Field(
        default=None, min_length=64, max_length=64, pattern='^[0-9a-f]{64}$'
    )
    byte_size: int | None = Field(default=None, gt=0)
    provider_artifact_reference: str | None = Field(
        default=None, min_length=1, max_length=500
    )

    @model_validator(mode='after')
    def validate_storage_evidence(self):
        inline = self.content is not None
        referenced = self.storage_reference is not None
        if inline == referenced:
            raise ValueError(
                'Artifact must carry either inline content or one durable reference'
            )
        if inline:
            if not self.content:
                raise ValueError('Inline artifact content must not be empty')
            if any(value is not None for value in (
                self.storage_strategy, self.content_hash, self.byte_size,
            )):
                raise ValueError('Inline artifact storage metadata is assigned by storage')
        elif (
            self.storage_strategy is None
            or self.content_hash is None
            or self.byte_size is None
        ):
            raise ValueError('Referenced artifact requires strategy, hash, and byte size')
        return self


class AuthoritativeFiscalResult(FiscalContractValue):
    external_fiscal_identifier: str = Field(min_length=1, max_length=200)
    fiscal_document_type: str = Field(min_length=1, max_length=64)
    fiscal_document_version: str = Field(min_length=1, max_length=32)
    issued_at: datetime
    artifacts: tuple[FiscalArtifactEvidence, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_artifacts(self):
        kinds = tuple(artifact.artifact_kind for artifact in self.artifacts)
        if len(kinds) != len(set(kinds)):
            raise ValueError('Fiscal artifact kinds must be unique within a result')
        if 'STAMPED_FISCAL_DOCUMENT' not in kinds:
            raise ValueError('Successful fiscal result requires a stamped document artifact')
        return self


class FiscalIssuanceResult(SafeFiscalProviderEvidence):
    outcome: FiscalIssuanceOutcome
    fiscal_result: AuthoritativeFiscalResult | None = None

    @model_validator(mode='after')
    def validate_outcome_evidence(self):
        if self.outcome is FiscalIssuanceOutcome.SUCCEEDED:
            if self.external_reference is None:
                raise ValueError('Successful issuance requires an external reference')
            if self.fiscal_result is None:
                raise ValueError('Successful issuance requires authoritative fiscal evidence')
            if self.error_kind is not None or self.error_message is not None:
                raise ValueError('Successful issuance cannot carry error evidence')
        else:
            if self.fiscal_result is not None:
                raise ValueError('Non-successful issuance cannot carry fiscal result evidence')
            if self.error_kind is None:
                raise ValueError('Non-successful issuance requires an error kind')
        return self


class FiscalRecoveryResult(SafeFiscalProviderEvidence):
    outcome: FiscalRecoveryOutcome
    fiscal_result: AuthoritativeFiscalResult | None = None

    @model_validator(mode='after')
    def validate_outcome_evidence(self):
        if self.outcome is FiscalRecoveryOutcome.RECOVERED_SUCCESS:
            if self.external_reference is None:
                raise ValueError('Recovered success requires an external reference')
            if self.fiscal_result is None:
                raise ValueError('Recovered success requires authoritative fiscal evidence')
            if self.error_kind is not None or self.error_message is not None:
                raise ValueError('Recovered success cannot carry error evidence')
        elif self.outcome is FiscalRecoveryOutcome.DEFINITE_ABSENCE:
            if self.external_reference is not None:
                raise ValueError('Definite absence cannot carry an external reference')
            if self.error_kind is not None or self.error_message is not None:
                raise ValueError('Definite absence cannot carry error evidence')
            if self.fiscal_result is not None:
                raise ValueError('Definite absence cannot carry fiscal result evidence')
        else:
            if self.fiscal_result is not None:
                raise ValueError('Failed recovery cannot carry fiscal result evidence')
            if self.error_kind is None:
                raise ValueError('Failed or uncertain recovery requires an error kind')
        return self
