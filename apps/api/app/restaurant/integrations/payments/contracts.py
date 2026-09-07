from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
import re
from typing import Annotated, Any

from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact money')
    return value


ExactPositiveAmount = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=0, allow_inf_nan=False)]
_EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_PHONE_SEPARATORS = re.compile(r'[\s().-]+')
_INTERNATIONAL_PHONE = re.compile(r'^\+[0-9]{8,15}$')


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


class EphemeralMerchantCredential(PaymentContractValue):
    """Opaque server-side merchant authentication material; never durable."""

    value: SecretStr


class EphemeralCustomerPaymentSource(PaymentContractValue):
    """Opaque single-execution customer payment source; never durable."""

    value: SecretStr


class PaymentCustomerIdentity(PaymentContractValue):
    """Provider-neutral contact snapshot for one payment execution request."""

    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    phone: str = Field(min_length=9, max_length=32)

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Payment customer display name is required')
        return normalized

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError('A valid payment customer email is required')
        return normalized

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        normalized = _PHONE_SEPARATORS.sub('', value.strip())
        if not _INTERNATIONAL_PHONE.fullmatch(normalized):
            raise ValueError(
                'Payment customer phone must use international format with a leading plus sign'
            )
        return normalized


class PaymentExecutionRequest(PaymentContractValue):
    operation_reference: str = Field(min_length=1, max_length=200)
    amount: ExactPositiveAmount
    currency: str = Field(min_length=3, max_length=3)
    method_category: str = Field(pattern='^(CARD|TRANSFER)$')
    idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    customer_identity: PaymentCustomerIdentity

    @field_validator('currency', mode='before')
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class PaymentRecoveryRequest(PaymentContractValue):
    operation_reference: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=128)
    request_fingerprint: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    external_reference: str | None = Field(default=None, max_length=200)


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
