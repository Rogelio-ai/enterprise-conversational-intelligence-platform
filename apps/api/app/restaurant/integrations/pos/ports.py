from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.restaurant.integrations.pos.contracts import (
    CreateOrderRecovery,
    CreateOrderRequest,
    ExternalCustomer,
    ExternalLocation,
    ExternalOrder,
    ExternalOrderItem,
    ExternalOrderStatus,
    ExternalPrice,
    ExternalProduct,
    ExternalPromotion,
    LocationScopedPosRequestContext,
    PosRequestContext,
)


@runtime_checkable
class LocationPort(Protocol):
    async def get_location(
        self, context: PosRequestContext, *, external_location_id: str
    ) -> ExternalLocation: ...

    async def list_locations(
        self, context: PosRequestContext
    ) -> tuple[ExternalLocation, ...]: ...


@runtime_checkable
class CustomerPort(Protocol):
    async def get_customer(
        self, context: PosRequestContext, *, external_customer_id: str
    ) -> ExternalCustomer: ...

    async def find_customer(
        self,
        context: PosRequestContext,
        *,
        email: str | None = None,
        phone: str | None = None,
    ) -> ExternalCustomer | None: ...


@runtime_checkable
class CatalogPort(Protocol):
    async def get_product(
        self, context: PosRequestContext, *, product_external_id: str
    ) -> ExternalProduct: ...

    async def list_products(
        self, context: PosRequestContext
    ) -> tuple[ExternalProduct, ...]: ...


@runtime_checkable
class PricingPort(Protocol):
    async def get_price(
        self, context: LocationScopedPosRequestContext, *, product_external_id: str
    ) -> ExternalPrice: ...


@runtime_checkable
class PromotionPort(Protocol):
    async def list_promotions(
        self,
        context: LocationScopedPosRequestContext,
        *,
        product_external_id: str | None = None,
    ) -> tuple[ExternalPromotion, ...]: ...


@runtime_checkable
class OrderPort(Protocol):
    async def create_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        request: CreateOrderRequest,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ExternalOrder: ...

    async def get_order(
        self, context: LocationScopedPosRequestContext, *, external_order_id: str
    ) -> ExternalOrder: ...

    async def cancel_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        external_order_id: str,
        idempotency_key: str,
    ) -> ExternalOrder: ...


@runtime_checkable
class OrderStatusPort(Protocol):
    async def get_order_status(
        self, context: LocationScopedPosRequestContext, *, external_order_id: str
    ) -> ExternalOrderStatus: ...


@runtime_checkable
class OrderRecoveryPort(Protocol):
    async def recover_create_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> CreateOrderRecovery: ...
