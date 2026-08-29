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
    field_validator,
    model_validator,
)


def _reject_binary_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact numbers')
    return value


ExactAmount = Annotated[
    Decimal,
    BeforeValidator(_reject_binary_float),
    Field(ge=0, allow_inf_nan=False),
]
PositiveQuantity = Annotated[
    Decimal,
    BeforeValidator(_reject_binary_float),
    Field(gt=0, allow_inf_nan=False),
]
RequiredText = Annotated[str, Field(min_length=1)]
ExternalIdentifier = Annotated[str, Field(min_length=1, max_length=200)]


class PosContractValue(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        str_strip_whitespace=True,
    )


class PosRequestContext(PosContractValue):
    """Trusted scope supplied by ECIP, never inferred from a POS payload."""

    tenant_id: int = Field(gt=0)
    location_id: int | None = Field(default=None, gt=0)
    connector_key: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)


class LocationScopedPosRequestContext(PosRequestContext):
    """Trusted POS scope for an operation that requires an internal Location."""

    location_id: int = Field(gt=0)


class ExternalEntityStatus(StrEnum):
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'


class CanonicalOrderStatus(StrEnum):
    """Operational POS order states exposed to Restaurant callers."""

    SUBMITTED = 'SUBMITTED'
    ACCEPTED = 'ACCEPTED'
    IN_PREPARATION = 'IN_PREPARATION'
    READY = 'READY'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    FAILED = 'FAILED'


class CurrencyValue(PosContractValue):
    currency: str = Field(min_length=3, max_length=3)

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


class ExternalLocation(PosContractValue):
    """A POS location whose external_id is scoped by Tenant and connector."""

    external_id: ExternalIdentifier
    name: RequiredText
    status: ExternalEntityStatus


class ExternalCustomer(PosContractValue):
    """Minimal POS customer data; external_id is not a canonical Customer ID."""

    external_id: ExternalIdentifier
    name: RequiredText | None = None
    email: RequiredText | None = None
    phone: RequiredText | None = None
    status: ExternalEntityStatus


class ExternalProduct(PosContractValue):
    """Minimal normalized POS product observation."""

    external_id: ExternalIdentifier
    name: RequiredText
    description: RequiredText | None = None
    status: ExternalEntityStatus


class ExternalPrice(CurrencyValue):
    product_external_id: ExternalIdentifier
    amount: ExactAmount


class ExternalPromotion(PosContractValue):
    external_id: ExternalIdentifier
    name: RequiredText
    status: ExternalEntityStatus


class CreateOrderComponent(PosContractValue):
    accepted_component_reference: RequiredText
    kind: RequiredText
    product_external_id: ExternalIdentifier
    name: RequiredText
    quantity: PositiveQuantity
    choice_group_name: RequiredText | None = None


class CreateOrderPromotion(PosContractValue):
    accepted_promotion_reference: RequiredText
    name: RequiredText
    promotion_type: RequiredText
    calculated_discount: ExactAmount


class CreateOrderItem(PosContractValue):
    accepted_item_reference: RequiredText
    external_line_reference: ExternalIdentifier
    product_external_id: ExternalIdentifier
    name: RequiredText
    quantity: PositiveQuantity
    unit_price: ExactAmount
    base_amount: ExactAmount
    discount_amount: ExactAmount
    line_total: ExactAmount
    components: tuple[CreateOrderComponent, ...] = ()
    promotions: tuple[CreateOrderPromotion, ...] = ()


class CreateOrderRequest(CurrencyValue):
    """Immutable accepted commercial request sent to a POS create boundary."""

    canonical_order_reference: RequiredText
    items: tuple[CreateOrderItem, ...] = Field(min_length=1)
    subtotal: ExactAmount
    total_discount: ExactAmount
    payable_total: ExactAmount
    external_customer_id: ExternalIdentifier | None = None


class ExternalOrderItem(PosContractValue):
    external_line_id: ExternalIdentifier | None = None
    product_external_id: ExternalIdentifier
    name: RequiredText
    quantity: PositiveQuantity
    unit_price: ExactAmount
    line_total: ExactAmount


class ExternalOrder(CurrencyValue):
    """A POS observation/result, not the canonical Restaurant Order model."""

    external_id: ExternalIdentifier
    status: CanonicalOrderStatus
    items: tuple[ExternalOrderItem, ...] = Field(min_length=1)
    subtotal: ExactAmount
    total: ExactAmount
    created_at: datetime
    updated_at: datetime | None = None


class ExternalOrderStatus(PosContractValue):
    external_order_id: ExternalIdentifier
    status: CanonicalOrderStatus
    observed_at: datetime


class CreateRecoveryOutcome(StrEnum):
    RECOVERED_SUCCESS = 'RECOVERED_SUCCESS'
    DEFINITE_ABSENCE = 'DEFINITE_ABSENCE'
    UNCERTAIN = 'UNCERTAIN'
    UNSUPPORTED = 'UNSUPPORTED'


class CreateOrderRecovery(PosContractValue):
    outcome: CreateRecoveryOutcome
    order: ExternalOrder | None = None

    @model_validator(mode='after')
    def validate_order_matches_outcome(self):
        if (self.outcome is CreateRecoveryOutcome.RECOVERED_SUCCESS) != (self.order is not None):
            raise ValueError('Only RECOVERED_SUCCESS carries an ExternalOrder')
        return self
