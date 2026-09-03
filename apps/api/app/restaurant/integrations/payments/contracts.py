from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact money')
    return value


ExactPositiveAmount = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=0, allow_inf_nan=False)]


class PaymentContractValue(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)


class PaymentExecutionOutcome(StrEnum):
    SUCCEEDED = 'SUCCEEDED'
    DEFINITE_FAILURE = 'DEFINITE_FAILURE'
    REJECTED = 'REJECTED'
    UNCERTAIN = 'UNCERTAIN'


class PaymentRecoveryOutcome(StrEnum):
    CONFIRMED_SUCCESS = 'CONFIRMED_SUCCESS'
    DEFINITE_ABSENCE = 'DEFINITE_ABSENCE'
    DEFINITE_FAILURE = 'DEFINITE_FAILURE'
    STILL_UNCERTAIN = 'STILL_UNCERTAIN'


class EphemeralExecutionCredential(PaymentContractValue):
    """Secret execution material that must never enter canonical persistence."""

    value: SecretStr


class PaymentExecutionRequest(PaymentContractValue):
    operation_reference: str = Field(min_length=1, max_length=200)
    amount: ExactPositiveAmount
    currency: str = Field(min_length=3, max_length=3)
    method_category: str = Field(pattern='^(CARD|TRANSFER)$')
    idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')

    @field_validator('currency', mode='before')
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class PaymentRecoveryRequest(PaymentContractValue):
    operation_reference: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')


class SafePaymentEvidence(PaymentContractValue):
    external_reference: str | None = Field(default=None, max_length=200)
    external_status: str | None = Field(default=None, max_length=64)
    instrument_brand: str | None = Field(default=None, max_length=64)
    instrument_last_four: str | None = Field(default=None, min_length=4, max_length=4, pattern='^[0-9]{4}$')
    instrument_display: str | None = Field(default=None, max_length=100)


class PaymentExecutionResult(SafePaymentEvidence):
    outcome: PaymentExecutionOutcome
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def validate_success_reference(self):
        if self.outcome is PaymentExecutionOutcome.SUCCEEDED and not self.external_reference:
            raise ValueError('Successful execution requires an external reference')
        return self


class PaymentRecoveryResult(SafePaymentEvidence):
    outcome: PaymentRecoveryOutcome
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def validate_success_reference(self):
        if self.outcome is PaymentRecoveryOutcome.CONFIRMED_SUCCESS and not self.external_reference:
            raise ValueError('Confirmed recovery success requires an external reference')
        return self
