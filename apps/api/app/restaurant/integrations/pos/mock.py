from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TypeVar

from app.restaurant.integrations.pos.contracts import (
    CanonicalOrderStatus,
    CreateOrderRecovery,
    CreateOrderRequest,
    CreateRecoveryOutcome,
    ExternalCustomer,
    ExternalEntityStatus,
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
from app.restaurant.integrations.pos.errors import (
    PosIntegrationError,
    PosInvalidDataError,
    PosMappingError,
    PosNotFoundError,
    PosRejectedError,
    PosTemporaryFailureError,
    PosUncertainResultError,
    PosUnsupportedCapabilityError,
)


FIXED_TIMESTAMP = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class MockPosFailureMode(StrEnum):
    NONE = 'NONE'
    POS_UNAVAILABLE = 'POS_UNAVAILABLE'
    PROMOTIONS_UNSUPPORTED = 'PROMOTIONS_UNSUPPORTED'
    ORDER_REJECTED = 'ORDER_REJECTED'
    ORDER_UNCERTAIN_ONCE = 'ORDER_UNCERTAIN_ONCE'
    RECOVERY_UNSUPPORTED = 'RECOVERY_UNSUPPORTED'
    RECOVERY_DEFINITE_ABSENCE = 'RECOVERY_DEFINITE_ABSENCE'
    ORDER_STATUS_MAPPING_FAILURE = 'ORDER_STATUS_MAPPING_FAILURE'


@dataclass(frozen=True)
class MockPosDataset:
    """Immutable seed values for one Tenant and POS connector."""

    tenant_id: int
    connector_key: str
    timestamp: datetime
    locations: tuple[tuple[int, ExternalLocation], ...]
    customers: tuple[ExternalCustomer, ...]
    products: tuple[ExternalProduct, ...]
    prices: tuple[tuple[int, ExternalPrice], ...]
    promotions: tuple[ExternalPromotion, ...]
    promotion_products: tuple[tuple[str, str | None], ...]
    orders: tuple[tuple[int, ExternalOrder], ...]

    def __post_init__(self) -> None:
        if self.tenant_id <= 0:
            raise ValueError('Mock POS tenant_id must be positive')
        if not self.connector_key.strip():
            raise ValueError('Mock POS connector_key is required')
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError('Mock POS timestamp must be timezone-aware')


def _seed_order(
    *,
    external_id: str,
    status: CanonicalOrderStatus,
    product: ExternalProduct,
    price: ExternalPrice,
    timestamp: datetime,
) -> ExternalOrder:
    item = ExternalOrderItem(
        external_line_id=f'{external_id}-line-001',
        product_external_id=product.external_id,
        name=product.name,
        quantity=Decimal('1'),
        unit_price=price.amount,
        line_total=price.amount,
    )
    return ExternalOrder(
        external_id=external_id,
        status=status,
        items=(item,),
        subtotal=price.amount,
        total=price.amount,
        currency=price.currency,
        created_at=timestamp,
        updated_at=timestamp,
    )


def build_mock_pos_dataset(
    *,
    tenant_id: int,
    connector_key: str,
    location_ids: tuple[int, int],
) -> MockPosDataset:
    """Build the bounded deterministic WS-05 fixture dataset."""

    if len(set(location_ids)) != 2 or any(location_id <= 0 for location_id in location_ids):
        raise ValueError('Exactly two distinct positive Location IDs are required')
    first_location_id, second_location_id = location_ids

    locations = (
        (
            first_location_id,
            ExternalLocation(
                external_id='location-001',
                name='Centro',
                status=ExternalEntityStatus.ACTIVE,
            ),
        ),
        (
            second_location_id,
            ExternalLocation(
                external_id='location-002',
                name='Norte',
                status=ExternalEntityStatus.ACTIVE,
            ),
        ),
    )
    customers = (
        ExternalCustomer(
            external_id='customer-001',
            name='Ana Rivera',
            email='ana@example.test',
            phone='+525500000001',
            status=ExternalEntityStatus.ACTIVE,
        ),
        ExternalCustomer(
            external_id='customer-002',
            name='Luis Torres',
            phone='+525500000002',
            status=ExternalEntityStatus.ACTIVE,
        ),
        ExternalCustomer(
            external_id='customer-003',
            name='Marta Silva',
            email='marta@example.test',
            phone='+525500000003',
            status=ExternalEntityStatus.INACTIVE,
        ),
    )
    products = (
        ExternalProduct(
            external_id='product-001',
            name='Hamburger',
            description='Classic hamburger',
            status=ExternalEntityStatus.ACTIVE,
        ),
        ExternalProduct(
            external_id='product-002',
            name='French Fries',
            status=ExternalEntityStatus.ACTIVE,
        ),
        ExternalProduct(
            external_id='product-003',
            name='Soft Drink',
            status=ExternalEntityStatus.ACTIVE,
        ),
        ExternalProduct(
            external_id='product-004',
            name='Seasonal Special',
            status=ExternalEntityStatus.INACTIVE,
        ),
    )
    price_amounts = (
        (Decimal('99.90'), Decimal('109.90')),
        (Decimal('49.00'), Decimal('54.00')),
        (Decimal('35.00'), Decimal('38.00')),
        (Decimal('129.00'), Decimal('139.00')),
    )
    prices = tuple(
        (
            location_id,
            ExternalPrice(
                product_external_id=product.external_id,
                amount=price_amounts[product_index][location_index],
                currency='MXN',
            ),
        )
        for product_index, product in enumerate(products)
        for location_index, location_id in enumerate(location_ids)
    )
    promotions = (
        ExternalPromotion(
            external_id='promotion-001',
            name='Everyday Promotion',
            status=ExternalEntityStatus.ACTIVE,
        ),
        ExternalPromotion(
            external_id='promotion-002',
            name='Hamburger Promotion',
            status=ExternalEntityStatus.ACTIVE,
        ),
    )
    promotion_products = (
        ('promotion-001', None),
        ('promotion-002', 'product-001'),
    )
    price_lookup = {
        (location_id, price.product_external_id): price for location_id, price in prices
    }
    seed_specs = (
        (first_location_id, 'order-accepted-001', CanonicalOrderStatus.ACCEPTED, products[0]),
        (
            first_location_id,
            'order-preparation-001',
            CanonicalOrderStatus.IN_PREPARATION,
            products[1],
        ),
        (first_location_id, 'order-ready-001', CanonicalOrderStatus.READY, products[2]),
        (second_location_id, 'order-completed-001', CanonicalOrderStatus.COMPLETED, products[0]),
        (second_location_id, 'order-failed-001', CanonicalOrderStatus.FAILED, products[1]),
    )
    orders = tuple(
        (
            location_id,
            _seed_order(
                external_id=external_id,
                status=status,
                product=product,
                price=price_lookup[(location_id, product.external_id)],
                timestamp=FIXED_TIMESTAMP,
            ),
        )
        for location_id, external_id, status, product in seed_specs
    )
    return MockPosDataset(
        tenant_id=tenant_id,
        connector_key=connector_key.strip(),
        timestamp=FIXED_TIMESTAMP,
        locations=locations,
        customers=customers,
        products=products,
        prices=prices,
        promotions=promotions,
        promotion_products=promotion_products,
        orders=orders,
    )


@dataclass(frozen=True)
class _IdempotencyRecord:
    fingerprint: str
    result: ExternalOrder


PosError = TypeVar('PosError', bound=PosIntegrationError)


class MockPosAdapter:
    """Deterministic in-memory implementation of the vendor-neutral POS ports."""

    def __init__(
        self,
        dataset: MockPosDataset,
        *,
        failure_mode: MockPosFailureMode = MockPosFailureMode.NONE,
    ) -> None:
        self.dataset = dataset
        self.failure_mode = failure_mode
        self._locations_by_id = dict(dataset.locations)
        self._locations_by_external_id = {
            location.external_id: (location_id, location)
            for location_id, location in dataset.locations
        }
        self._customers = {customer.external_id: customer for customer in dataset.customers}
        self._products = {product.external_id: product for product in dataset.products}
        self._prices = {
            (location_id, price.product_external_id): price
            for location_id, price in dataset.prices
        }
        self._promotions = {
            promotion.external_id: promotion for promotion in dataset.promotions
        }
        self._promotion_products = dict(dataset.promotion_products)
        self._seed_orders = {
            (location_id, order.external_id): order for location_id, order in dataset.orders
        }
        self._validate_dataset()
        self.reset()

    def _validate_dataset(self) -> None:
        if len(self._locations_by_id) != len(self.dataset.locations):
            raise ValueError('Mock POS dataset contains duplicate internal Location IDs')
        if len(self._locations_by_external_id) != len(self.dataset.locations):
            raise ValueError('Mock POS dataset contains duplicate external Location IDs')
        if len(self._customers) != len(self.dataset.customers):
            raise ValueError('Mock POS dataset contains duplicate Customer IDs')
        if len(self._products) != len(self.dataset.products):
            raise ValueError('Mock POS dataset contains duplicate Product IDs')
        if len(self._promotions) != len(self.dataset.promotions):
            raise ValueError('Mock POS dataset contains duplicate Promotion IDs')
        if len(self._seed_orders) != len(self.dataset.orders):
            raise ValueError('Mock POS dataset contains duplicate scoped Order IDs')
        for location_id, price in self.dataset.prices:
            if location_id not in self._locations_by_id:
                raise ValueError('Mock POS Price references an unknown Location')
            if price.product_external_id not in self._products:
                raise ValueError('Mock POS Price references an unknown Product')
        for promotion_id, product_external_id in self.dataset.promotion_products:
            if promotion_id not in self._promotions:
                raise ValueError('Mock POS applicability references an unknown Promotion')
            if product_external_id is not None and product_external_id not in self._products:
                raise ValueError('Mock POS applicability references an unknown Product')

    def reset(self) -> None:
        self._orders = dict(self._seed_orders)
        self._idempotency: dict[tuple[int, str, str], _IdempotencyRecord] = {}
        self._order_counter = 1
        self._line_counter = 1
        self._uncertain_result_raised = False
        self.create_history: list[CreateOrderRequest] = []
        self.recovery_calls = 0

    def _error(
        self,
        error_type: type[PosError],
        message: str,
        *,
        context: PosRequestContext,
        operation: str,
        external_entity_type: str | None = None,
    ) -> PosError:
        return error_type(
            message,
            operation=operation,
            connector_key=context.connector_key,
            correlation_id=context.correlation_id,
            external_entity_type=external_entity_type,
        )

    def _validate_scope(self, context: PosRequestContext, *, operation: str) -> None:
        if (
            context.tenant_id != self.dataset.tenant_id
            or context.connector_key != self.dataset.connector_key
        ):
            raise self._error(
                PosNotFoundError,
                'POS scope not found',
                context=context,
                operation=operation,
            )
        if self.failure_mode is MockPosFailureMode.POS_UNAVAILABLE:
            raise self._error(
                PosTemporaryFailureError,
                'POS is temporarily unavailable',
                context=context,
                operation=operation,
            )

    def _location(
        self,
        context: LocationScopedPosRequestContext,
        *,
        operation: str,
    ) -> ExternalLocation:
        self._validate_scope(context, operation=operation)
        location = self._locations_by_id.get(context.location_id)
        if location is None:
            raise self._error(
                PosNotFoundError,
                'POS Location not found',
                context=context,
                operation=operation,
                external_entity_type='location',
            )
        return location

    def _require_text(
        self,
        value: object,
        *,
        field: str,
        context: PosRequestContext,
        operation: str,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self._error(
                PosInvalidDataError,
                f'{field} is required',
                context=context,
                operation=operation,
            )
        return value.strip()

    async def list_locations(
        self, context: PosRequestContext
    ) -> tuple[ExternalLocation, ...]:
        operation = 'list_locations'
        self._validate_scope(context, operation=operation)
        if context.location_id is not None:
            location = self._locations_by_id.get(context.location_id)
            if location is None:
                raise self._error(
                    PosNotFoundError,
                    'POS Location not found',
                    context=context,
                    operation=operation,
                    external_entity_type='location',
                )
            return (location,)
        return tuple(sorted(self._locations_by_id.values(), key=lambda item: item.external_id))

    async def get_location(
        self,
        context: PosRequestContext,
        *,
        external_location_id: str,
    ) -> ExternalLocation:
        operation = 'get_location'
        self._validate_scope(context, operation=operation)
        external_location_id = self._require_text(
            external_location_id,
            field='external_location_id',
            context=context,
            operation=operation,
        )
        match = self._locations_by_external_id.get(external_location_id)
        if match is None or (context.location_id is not None and match[0] != context.location_id):
            raise self._error(
                PosNotFoundError,
                'POS Location not found',
                context=context,
                operation=operation,
                external_entity_type='location',
            )
        return match[1]

    async def get_customer(
        self,
        context: PosRequestContext,
        *,
        external_customer_id: str,
    ) -> ExternalCustomer:
        operation = 'get_customer'
        self._validate_scope(context, operation=operation)
        external_customer_id = self._require_text(
            external_customer_id,
            field='external_customer_id',
            context=context,
            operation=operation,
        )
        customer = self._customers.get(external_customer_id)
        if customer is None:
            raise self._error(
                PosNotFoundError,
                'POS Customer not found',
                context=context,
                operation=operation,
                external_entity_type='customer',
            )
        return customer

    async def find_customer(
        self,
        context: PosRequestContext,
        *,
        email: str | None = None,
        phone: str | None = None,
    ) -> ExternalCustomer | None:
        operation = 'find_customer'
        self._validate_scope(context, operation=operation)
        normalized_email = email.strip().casefold() if isinstance(email, str) else None
        normalized_phone = phone.strip() if isinstance(phone, str) else None
        if not normalized_email and not normalized_phone:
            raise self._error(
                PosInvalidDataError,
                'At least one Customer search criterion is required',
                context=context,
                operation=operation,
                external_entity_type='customer',
            )
        for customer in sorted(self._customers.values(), key=lambda item: item.external_id):
            email_matches = normalized_email is None or (
                customer.email is not None and customer.email.casefold() == normalized_email
            )
            phone_matches = normalized_phone is None or customer.phone == normalized_phone
            if email_matches and phone_matches:
                return customer
        return None

    async def list_products(
        self, context: PosRequestContext
    ) -> tuple[ExternalProduct, ...]:
        self._validate_scope(context, operation='list_products')
        return tuple(sorted(self._products.values(), key=lambda item: item.external_id))

    async def get_product(
        self,
        context: PosRequestContext,
        *,
        product_external_id: str,
    ) -> ExternalProduct:
        operation = 'get_product'
        self._validate_scope(context, operation=operation)
        product_external_id = self._require_text(
            product_external_id,
            field='product_external_id',
            context=context,
            operation=operation,
        )
        product = self._products.get(product_external_id)
        if product is None:
            raise self._error(
                PosNotFoundError,
                'POS Product not found',
                context=context,
                operation=operation,
                external_entity_type='product',
            )
        return product

    async def get_price(
        self,
        context: LocationScopedPosRequestContext,
        *,
        product_external_id: str,
    ) -> ExternalPrice:
        operation = 'get_price'
        self._location(context, operation=operation)
        product_external_id = self._require_text(
            product_external_id,
            field='product_external_id',
            context=context,
            operation=operation,
        )
        price = self._prices.get((context.location_id, product_external_id))
        if price is None:
            raise self._error(
                PosNotFoundError,
                'POS Price not found',
                context=context,
                operation=operation,
                external_entity_type='price',
            )
        return price

    async def list_promotions(
        self,
        context: LocationScopedPosRequestContext,
        *,
        product_external_id: str | None = None,
    ) -> tuple[ExternalPromotion, ...]:
        operation = 'list_promotions'
        self._location(context, operation=operation)
        if self.failure_mode is MockPosFailureMode.PROMOTIONS_UNSUPPORTED:
            raise self._error(
                PosUnsupportedCapabilityError,
                'POS Promotions are not supported',
                context=context,
                operation=operation,
                external_entity_type='promotion',
            )
        if product_external_id is not None:
            product_external_id = self._require_text(
                product_external_id,
                field='product_external_id',
                context=context,
                operation=operation,
            )
            if product_external_id not in self._products:
                raise self._error(
                    PosNotFoundError,
                    'POS Product not found',
                    context=context,
                    operation=operation,
                    external_entity_type='product',
                )
        promotions = (
            promotion
            for promotion_id, promotion in self._promotions.items()
            if product_external_id is None
            or self._promotion_products[promotion_id] in (None, product_external_id)
        )
        return tuple(sorted(promotions, key=lambda item: item.external_id))

    def _idempotent_result(
        self,
        *,
        key: tuple[int, str, str],
        fingerprint: str,
        context: LocationScopedPosRequestContext,
        operation: str,
    ) -> ExternalOrder | None:
        existing = self._idempotency.get(key)
        if existing is None:
            return None
        if existing.fingerprint != fingerprint:
            raise self._error(
                PosInvalidDataError,
                'Idempotency key is already bound to a different request',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        return existing.result

    async def create_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        request: CreateOrderRequest,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> ExternalOrder:
        operation = 'create_order'
        self._location(context, operation=operation)
        idempotency_key = self._require_text(
            idempotency_key,
            field='idempotency_key',
            context=context,
            operation=operation,
        )
        request_fingerprint = self._require_text(
            request_fingerprint,
            field='request_fingerprint',
            context=context,
            operation=operation,
        )
        if not isinstance(request, CreateOrderRequest):
            raise self._error(
                PosInvalidDataError,
                'Order request must use the create-order contract value',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        self.create_history.append(request)
        if not request.items:
            raise self._error(
                PosInvalidDataError,
                'At least one Order Item is required',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        for item in request.items:
            product = self._products.get(item.product_external_id)
            if product is None:
                raise self._error(
                    PosNotFoundError,
                    'POS Product not found',
                    context=context,
                    operation=operation,
                    external_entity_type='product',
                )
            if product.status is not ExternalEntityStatus.ACTIVE:
                raise self._error(
                    PosRejectedError,
                    'POS rejected an unavailable Product',
                    context=context,
                    operation=operation,
                    external_entity_type='product',
                )
            price = self._prices.get((context.location_id, item.product_external_id))
            if price is None:
                raise self._error(
                    PosNotFoundError,
                    'POS Price not found',
                    context=context,
                    operation=operation,
                    external_entity_type='price',
                )
            if price.currency != request.currency:
                raise self._error(
                    PosInvalidDataError,
                    'Order currency does not match the POS Price currency',
                    context=context,
                    operation=operation,
                    external_entity_type='order',
                )
        if request.external_customer_id is not None:
            external_customer_id = self._require_text(
                request.external_customer_id,
                field='external_customer_id',
                context=context,
                operation=operation,
            )
            if external_customer_id not in self._customers:
                raise self._error(
                    PosNotFoundError,
                    'POS Customer not found',
                    context=context,
                    operation=operation,
                    external_entity_type='customer',
                )
        idempotency_scope = (context.location_id, operation, idempotency_key)
        existing = self._idempotent_result(
            key=idempotency_scope,
            fingerprint=request_fingerprint,
            context=context,
            operation=operation,
        )
        if existing is not None:
            return existing
        if self.failure_mode is MockPosFailureMode.ORDER_REJECTED:
            raise self._error(
                PosRejectedError,
                'POS rejected the Order',
                context=context,
                operation=operation,
                external_entity_type='order',
            )

        external_order_id = self._next_order_id()
        normalized_items = tuple(
            self._normalize_line(
                ExternalOrderItem(
                    external_line_id=None,
                    product_external_id=item.product_external_id,
                    name=item.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
            )
            for item in request.items
        )
        order = ExternalOrder(
            external_id=external_order_id,
            status=CanonicalOrderStatus.SUBMITTED,
            items=normalized_items,
            subtotal=request.subtotal,
            total=request.payable_total,
            currency=request.currency,
            created_at=self.dataset.timestamp,
        )
        self._orders[(context.location_id, external_order_id)] = order
        self._idempotency[idempotency_scope] = _IdempotencyRecord(request_fingerprint, order)
        if (
            self.failure_mode is MockPosFailureMode.ORDER_UNCERTAIN_ONCE
            and not self._uncertain_result_raised
        ):
            self._uncertain_result_raised = True
            raise self._error(
                PosUncertainResultError,
                'POS Order result is uncertain and requires reconciliation',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        return order

    async def recover_create_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> CreateOrderRecovery:
        operation = 'recover_create_order'
        self.recovery_calls += 1
        self._location(context, operation=operation)
        idempotency_key = self._require_text(
            idempotency_key, field='idempotency_key', context=context, operation=operation
        )
        request_fingerprint = self._require_text(
            request_fingerprint,
            field='request_fingerprint',
            context=context,
            operation=operation,
        )
        if self.failure_mode is MockPosFailureMode.RECOVERY_UNSUPPORTED:
            return CreateOrderRecovery(outcome=CreateRecoveryOutcome.UNSUPPORTED)
        if self.failure_mode is MockPosFailureMode.RECOVERY_DEFINITE_ABSENCE:
            return CreateOrderRecovery(outcome=CreateRecoveryOutcome.DEFINITE_ABSENCE)
        existing = self._idempotency.get((context.location_id, 'create_order', idempotency_key))
        if existing is None:
            return CreateOrderRecovery(outcome=CreateRecoveryOutcome.DEFINITE_ABSENCE)
        if existing.fingerprint != request_fingerprint:
            raise self._error(
                PosInvalidDataError,
                'Create recovery fingerprint does not match the original request',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        return CreateOrderRecovery(
            outcome=CreateRecoveryOutcome.RECOVERED_SUCCESS,
            order=existing.result,
        )

    def _next_order_id(self) -> str:
        while True:
            external_order_id = f'mock-order-{self._order_counter:04d}'
            self._order_counter += 1
            if all(key[1] != external_order_id for key in self._orders):
                return external_order_id

    def _normalize_line(self, item: ExternalOrderItem) -> ExternalOrderItem:
        if item.external_line_id is not None:
            return item
        external_line_id = f'mock-line-{self._line_counter:04d}'
        self._line_counter += 1
        return item.model_copy(update={'external_line_id': external_line_id})

    async def get_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        external_order_id: str,
    ) -> ExternalOrder:
        operation = 'get_order'
        self._location(context, operation=operation)
        external_order_id = self._require_text(
            external_order_id,
            field='external_order_id',
            context=context,
            operation=operation,
        )
        return self._get_order(context, external_order_id=external_order_id, operation=operation)

    def _get_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        external_order_id: str,
        operation: str,
    ) -> ExternalOrder:
        order = self._orders.get((context.location_id, external_order_id))
        if order is None:
            raise self._error(
                PosNotFoundError,
                'POS Order not found',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        return order

    async def cancel_order(
        self,
        context: LocationScopedPosRequestContext,
        *,
        external_order_id: str,
        idempotency_key: str,
    ) -> ExternalOrder:
        operation = 'cancel_order'
        self._location(context, operation=operation)
        external_order_id = self._require_text(
            external_order_id,
            field='external_order_id',
            context=context,
            operation=operation,
        )
        idempotency_key = self._require_text(
            idempotency_key,
            field='idempotency_key',
            context=context,
            operation=operation,
        )
        fingerprint: tuple[object, ...] = (external_order_id,)
        idempotency_scope = (context.location_id, operation, idempotency_key)
        existing = self._idempotent_result(
            key=idempotency_scope,
            fingerprint=fingerprint,
            context=context,
            operation=operation,
        )
        if existing is not None:
            return existing
        order = self._get_order(
            context,
            external_order_id=external_order_id,
            operation=operation,
        )
        if order.status in {CanonicalOrderStatus.COMPLETED, CanonicalOrderStatus.FAILED}:
            raise self._error(
                PosRejectedError,
                'POS rejected cancellation of a terminal Order',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        cancelled = order.model_copy(
            update={
                'status': CanonicalOrderStatus.CANCELLED,
                'updated_at': self.dataset.timestamp,
            }
        )
        self._orders[(context.location_id, external_order_id)] = cancelled
        self._idempotency[idempotency_scope] = _IdempotencyRecord(fingerprint, cancelled)
        return cancelled

    async def get_order_status(
        self,
        context: LocationScopedPosRequestContext,
        *,
        external_order_id: str,
    ) -> ExternalOrderStatus:
        operation = 'get_order_status'
        self._location(context, operation=operation)
        if self.failure_mode is MockPosFailureMode.ORDER_STATUS_MAPPING_FAILURE:
            raise self._error(
                PosMappingError,
                'External Order status cannot be mapped',
                context=context,
                operation=operation,
                external_entity_type='order',
            )
        external_order_id = self._require_text(
            external_order_id,
            field='external_order_id',
            context=context,
            operation=operation,
        )
        order = self._get_order(
            context,
            external_order_id=external_order_id,
            operation=operation,
        )
        return ExternalOrderStatus(
            external_order_id=order.external_id,
            status=order.status,
            observed_at=self.dataset.timestamp,
        )
