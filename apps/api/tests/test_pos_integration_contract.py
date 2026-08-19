from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import inspect
from typing import get_type_hints

from pydantic import ValidationError
import pytest

from app.restaurant.integrations import pos
from app.restaurant.integrations.pos import (
    CanonicalOrderStatus,
    CatalogPort,
    CustomerPort,
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
    LocationPort,
    OrderPort,
    OrderStatusPort,
    PosErrorKind,
    PosInvalidDataError,
    PosMappingError,
    PosNotFoundError,
    PosRejectedError,
    PosRequestContext,
    PosTemporaryFailureError,
    PosUncertainResultError,
    PosUnsupportedCapabilityError,
    PricingPort,
    PromotionPort,
)


NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


def _context(*, location_id: int | None = 17) -> PosRequestContext:
    context_type = LocationScopedPosRequestContext if location_id is not None else PosRequestContext
    return context_type(
        tenant_id=11,
        location_id=location_id,
        connector_key='primary-pos',
        correlation_id='correlation-123',
    )


def _item() -> ExternalOrderItem:
    return ExternalOrderItem(
        product_external_id='product-1',
        name='Hamburger',
        quantity=Decimal('2'),
        unit_price=Decimal('10.10'),
        line_total=Decimal('20.20'),
    )


def _order(*, status: CanonicalOrderStatus = CanonicalOrderStatus.SUBMITTED) -> ExternalOrder:
    return ExternalOrder(
        external_id='order-1',
        status=status,
        items=(_item(),),
        subtotal=Decimal('20.20'),
        total=Decimal('20.20'),
        currency='mxn',
        created_at=NOW,
    )


class ContractFake:
    """Test-only contract implementation; it is not the WS-05 Mock POS."""

    def __init__(self) -> None:
        self.contexts: list[PosRequestContext] = []

    def _record(self, context: PosRequestContext) -> None:
        self.contexts.append(context)

    async def get_location(
        self, context: PosRequestContext, *, external_location_id: str
    ) -> ExternalLocation:
        self._record(context)
        return ExternalLocation(
            external_id=external_location_id,
            name='Downtown',
            status=ExternalEntityStatus.ACTIVE,
        )

    async def list_locations(
        self, context: PosRequestContext
    ) -> tuple[ExternalLocation, ...]:
        return (await self.get_location(context, external_location_id='location-1'),)

    async def get_customer(
        self, context: PosRequestContext, *, external_customer_id: str
    ) -> ExternalCustomer:
        self._record(context)
        return ExternalCustomer(
            external_id=external_customer_id,
            name='Customer',
            status=ExternalEntityStatus.ACTIVE,
        )

    async def find_customer(
        self,
        context: PosRequestContext,
        *,
        email: str | None = None,
        phone: str | None = None,
    ) -> ExternalCustomer | None:
        return await self.get_customer(context, external_customer_id=email or phone or 'customer-1')

    async def get_product(
        self, context: PosRequestContext, *, product_external_id: str
    ) -> ExternalProduct:
        self._record(context)
        return ExternalProduct(
            external_id=product_external_id,
            name='Hamburger',
            status=ExternalEntityStatus.ACTIVE,
        )

    async def list_products(
        self, context: PosRequestContext
    ) -> tuple[ExternalProduct, ...]:
        return (await self.get_product(context, product_external_id='product-1'),)

    async def get_price(
        self, context: PosRequestContext, *, product_external_id: str
    ) -> ExternalPrice:
        self._record(context)
        return ExternalPrice(
            product_external_id=product_external_id,
            amount=Decimal('10.10'),
            currency='MXN',
        )

    async def list_promotions(
        self,
        context: PosRequestContext,
        *,
        product_external_id: str | None = None,
    ) -> tuple[ExternalPromotion, ...]:
        self._record(context)
        return (
            ExternalPromotion(
                external_id=f'promotion-{product_external_id or "all"}',
                name='Lunch Promotion',
                status=ExternalEntityStatus.ACTIVE,
            ),
        )

    async def create_order(
        self,
        context: PosRequestContext,
        *,
        items: tuple[ExternalOrderItem, ...],
        currency: str,
        idempotency_key: str,
        external_customer_id: str | None = None,
    ) -> ExternalOrder:
        self._record(context)
        assert items and currency and idempotency_key
        return _order()

    async def get_order(
        self, context: PosRequestContext, *, external_order_id: str
    ) -> ExternalOrder:
        self._record(context)
        assert external_order_id
        return _order()

    async def cancel_order(
        self,
        context: PosRequestContext,
        *,
        external_order_id: str,
        idempotency_key: str,
    ) -> ExternalOrder:
        self._record(context)
        assert external_order_id and idempotency_key
        return _order(status=CanonicalOrderStatus.CANCELLED)

    async def get_order_status(
        self, context: PosRequestContext, *, external_order_id: str
    ) -> ExternalOrderStatus:
        self._record(context)
        return ExternalOrderStatus(
            external_order_id=external_order_id,
            status=CanonicalOrderStatus.READY,
            observed_at=NOW,
        )


PORTS = (
    LocationPort,
    CustomerPort,
    CatalogPort,
    PricingPort,
    PromotionPort,
    OrderPort,
    OrderStatusPort,
)


def test_all_ports_are_async_scoped_and_implemented_by_contract_fake() -> None:
    fake = ContractFake()
    for port_type in PORTS:
        assert isinstance(fake, port_type)
        for name, member in inspect.getmembers(port_type, inspect.isfunction):
            if name.startswith('_'):
                continue
            assert inspect.iscoroutinefunction(member)
            parameters = list(inspect.signature(member).parameters.values())
            assert parameters[0].name == 'self'
            assert parameters[1].name == 'context'
            assert parameters[1].default is inspect.Parameter.empty

    location_scoped_operations = (
        PricingPort.get_price,
        PromotionPort.list_promotions,
        OrderPort.create_order,
        OrderPort.get_order,
        OrderPort.cancel_order,
        OrderStatusPort.get_order_status,
    )
    for operation in location_scoped_operations:
        assert get_type_hints(operation)['context'] is LocationScopedPosRequestContext

    with pytest.raises(ValidationError):
        LocationScopedPosRequestContext(
            tenant_id=11,
            connector_key='primary-pos',
            correlation_id='correlation-123',
        )


def test_dtos_travel_across_ports_with_trusted_location_context() -> None:
    async def exercise() -> tuple[ContractFake, ExternalOrderStatus]:
        fake = ContractFake()
        context = _context()
        assert (await fake.get_location(context, external_location_id='location-1')).external_id
        assert (await fake.get_customer(context, external_customer_id='customer-1')).external_id
        assert (await fake.get_product(context, product_external_id='product-1')).external_id
        assert (await fake.get_price(context, product_external_id='product-1')).currency == 'MXN'
        assert await fake.list_promotions(context, product_external_id='product-1')
        created = await fake.create_order(
            context,
            items=(_item(),),
            currency='MXN',
            idempotency_key='submission-1',
        )
        status = await fake.get_order_status(context, external_order_id=created.external_id)
        return fake, status

    fake, status = asyncio.run(exercise())
    assert status.status is CanonicalOrderStatus.READY
    assert fake.contexts
    assert {context.tenant_id for context in fake.contexts} == {11}
    assert {context.location_id for context in fake.contexts} == {17}


def test_boundary_is_independent_from_orm_fastapi_and_vendor_libraries() -> None:
    modules = (pos.contracts, pos.ports, pos.errors)
    source = '\n'.join(inspect.getsource(module) for module in modules).lower()
    for forbidden_dependency in ('sqlalchemy', 'fastapi', 'pymysql', 'aiomysql'):
        assert forbidden_dependency not in source


def test_external_identifiers_are_explicit_and_source_scoped() -> None:
    dto_types = (
        ExternalLocation,
        ExternalCustomer,
        ExternalProduct,
        ExternalPromotion,
        ExternalOrder,
    )
    for dto_type in dto_types:
        assert 'external_id' in dto_type.model_fields
        assert 'id' not in dto_type.model_fields
    context = _context(location_id=None)
    assert context.tenant_id == 11
    assert context.connector_key == 'primary-pos'


@pytest.mark.parametrize(
    ('model_type', 'values'),
    [
        (
            PosRequestContext,
            dict(tenant_id=1, connector_key=' ', correlation_id='correlation'),
        ),
        (
            ExternalLocation,
            dict(external_id=' ', name='Location', status='ACTIVE'),
        ),
        (
            ExternalProduct,
            dict(external_id='product-1', name=' ', status='ACTIVE'),
        ),
        (
            ExternalPrice,
            dict(product_external_id='product-1', amount='1.00', currency=''),
        ),
        (
            ExternalOrderItem,
            dict(
                product_external_id='product-1',
                name='Product',
                quantity='0',
                unit_price='1.00',
                line_total='0.00',
            ),
        ),
        (
            ExternalOrder,
            dict(
                external_id='order-1',
                status='SUBMITTED',
                items=(),
                subtotal='0',
                total='0',
                currency='MXN',
                created_at=NOW,
            ),
        ),
        (
            ExternalOrderStatus,
            dict(external_order_id='order-1', status='UNKNOWN', observed_at=NOW),
        ),
    ],
)
def test_contract_dtos_reject_invalid_values(model_type, values) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(values)


def test_money_and_quantity_are_exact_and_reject_binary_floats() -> None:
    price = ExternalPrice(
        product_external_id='product-1',
        amount=Decimal('0.1') + Decimal('0.2'),
        currency='mxn',
    )
    assert price.amount == Decimal('0.3')
    assert price.currency == 'MXN'

    with pytest.raises(ValidationError):
        ExternalPrice(product_external_id='product-1', amount=0.1, currency='MXN')
    with pytest.raises(ValidationError):
        ExternalOrderItem(
            product_external_id='product-1',
            name='Product',
            quantity=1.5,
            unit_price='1.00',
            line_total='1.50',
        )
    with pytest.raises(ValidationError):
        ExternalPrice(product_external_id='product-1', amount='-0.01', currency='MXN')


def test_vendor_status_mapping_is_adapter_owned_and_unknown_values_fail() -> None:
    def map_test_vendor_status(raw_status: int) -> CanonicalOrderStatus:
        try:
            return {7: CanonicalOrderStatus.READY}[raw_status]
        except KeyError as exc:
            raise PosMappingError(
                'External order status cannot be mapped',
                operation='get_order_status',
                connector_key='test-source',
                correlation_id='correlation-123',
                external_entity_type='order',
            ) from exc

    assert map_test_vendor_status(7) is CanonicalOrderStatus.READY
    with pytest.raises(PosMappingError) as error:
        map_test_vendor_status(999)
    assert error.value.kind is PosErrorKind.MAPPING


@pytest.mark.parametrize(
    ('error_type', 'kind'),
    [
        (PosInvalidDataError, PosErrorKind.INVALID_DATA),
        (PosMappingError, PosErrorKind.MAPPING),
        (PosNotFoundError, PosErrorKind.NOT_FOUND),
        (PosUnsupportedCapabilityError, PosErrorKind.UNSUPPORTED_CAPABILITY),
        (PosTemporaryFailureError, PosErrorKind.TEMPORARY_FAILURE),
        (PosRejectedError, PosErrorKind.REJECTED),
        (PosUncertainResultError, PosErrorKind.UNCERTAIN_RESULT),
    ],
)
def test_canonical_error_categories_are_stable(error_type, kind) -> None:
    error = error_type(
        'Safe diagnostic message',
        operation='operation',
        connector_key='primary-pos',
        correlation_id='correlation-123',
        external_entity_type='order',
    )
    assert error.kind is kind
    assert error.operation == 'operation'
    assert error.connector_key == 'primary-pos'
    assert error.correlation_id == 'correlation-123'
    assert not hasattr(error, 'credentials')
    assert not hasattr(error, 'payload')


def test_order_write_contract_requires_idempotency_keys() -> None:
    create_parameters = inspect.signature(OrderPort.create_order).parameters
    cancel_parameters = inspect.signature(OrderPort.cancel_order).parameters
    assert create_parameters['idempotency_key'].default is inspect.Parameter.empty
    assert cancel_parameters['idempotency_key'].default is inspect.Parameter.empty

    fake = ContractFake()
    with pytest.raises(TypeError):
        fake.create_order(_context(), items=(_item(),), currency='MXN')  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        fake.cancel_order(_context(), external_order_id='order-1')  # type: ignore[call-arg]


def test_public_contract_has_no_vendor_specific_fields() -> None:
    dto_types = (
        PosRequestContext,
        LocationScopedPosRequestContext,
        ExternalLocation,
        ExternalCustomer,
        ExternalProduct,
        ExternalPrice,
        ExternalPromotion,
        ExternalOrderItem,
        ExternalOrder,
        ExternalOrderStatus,
    )
    forbidden_fields = {
        'article_id',
        'client_id',
        'database_column',
        'raw_payload',
        'table_name',
        'ticket_id',
        'ticket_state',
        'vendor_status',
    }
    exposed_fields = {field for dto_type in dto_types for field in dto_type.model_fields}
    assert forbidden_fields.isdisjoint(exposed_fields)
