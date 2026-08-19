from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import inspect

from pydantic import ValidationError
import pytest

from app.restaurant.integrations.pos import (
    CanonicalOrderStatus,
    CatalogPort,
    CustomerPort,
    ExternalEntityStatus,
    ExternalOrderItem,
    LocationPort,
    LocationScopedPosRequestContext,
    MockPosAdapter,
    MockPosDataset,
    MockPosFailureMode,
    OrderPort,
    OrderStatusPort,
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
    build_mock_pos_dataset,
)
from app.restaurant.integrations.pos import mock as mock_module


TENANT_ID = 11
CONNECTOR_KEY = 'mock-primary'
FIRST_LOCATION_ID = 101
SECOND_LOCATION_ID = 202


def run(awaitable):
    return asyncio.run(awaitable)


@pytest.fixture
def dataset() -> MockPosDataset:
    return build_mock_pos_dataset(
        tenant_id=TENANT_ID,
        connector_key=CONNECTOR_KEY,
        location_ids=(FIRST_LOCATION_ID, SECOND_LOCATION_ID),
    )


@pytest.fixture
def adapter(dataset: MockPosDataset) -> MockPosAdapter:
    return MockPosAdapter(dataset)


def context(
    *,
    tenant_id: int = TENANT_ID,
    connector_key: str = CONNECTOR_KEY,
    location_id: int | None = FIRST_LOCATION_ID,
) -> PosRequestContext:
    context_type = LocationScopedPosRequestContext if location_id is not None else PosRequestContext
    return context_type(
        tenant_id=tenant_id,
        connector_key=connector_key,
        location_id=location_id,
        correlation_id='mock-correlation-001',
    )


def location_context(location_id: int = FIRST_LOCATION_ID) -> LocationScopedPosRequestContext:
    scoped = context(location_id=location_id)
    assert isinstance(scoped, LocationScopedPosRequestContext)
    return scoped


def order_item(
    product_external_id: str = 'product-001',
    *,
    quantity: str = '1',
    unit_price: str = '99.90',
    line_total: str = '99.90',
) -> ExternalOrderItem:
    return ExternalOrderItem(
        product_external_id=product_external_id,
        name='Order Product',
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        line_total=Decimal(line_total),
    )


def create_order(
    adapter: MockPosAdapter,
    *,
    idempotency_key: str = 'create-001',
    item: ExternalOrderItem | None = None,
    currency: str = 'MXN',
    location_id: int = FIRST_LOCATION_ID,
):
    return adapter.create_order(
        location_context(location_id),
        items=(item or order_item(),),
        currency=currency,
        idempotency_key=idempotency_key,
        external_customer_id='customer-001',
    )


def test_adapter_satisfies_all_committed_async_ports(adapter: MockPosAdapter) -> None:
    port_types = (
        LocationPort,
        CustomerPort,
        CatalogPort,
        PricingPort,
        PromotionPort,
        OrderPort,
        OrderStatusPort,
    )
    for port_type in port_types:
        assert isinstance(adapter, port_type)
        for name, member in inspect.getmembers(port_type, inspect.isfunction):
            if not name.startswith('_'):
                assert inspect.iscoroutinefunction(getattr(adapter, name))


def test_dataset_is_bounded_immutable_and_deterministic(dataset: MockPosDataset) -> None:
    assert len(dataset.locations) == 2
    assert len(dataset.customers) == 3
    assert len(dataset.products) == 4
    assert len(dataset.prices) == 8
    assert len(dataset.promotions) == 2
    assert len(dataset.orders) == 5
    assert dataset.timestamp.tzinfo is not None
    assert [value.external_id for _, value in dataset.locations] == [
        'location-001',
        'location-002',
    ]
    with pytest.raises(FrozenInstanceError):
        dataset.tenant_id = 22  # type: ignore[misc]
    with pytest.raises(ValidationError):
        dataset.products[0].name = 'Changed'  # type: ignore[misc]


def test_tenant_connector_and_instance_state_are_isolated(dataset: MockPosDataset) -> None:
    first = MockPosAdapter(dataset)
    second_dataset = build_mock_pos_dataset(
        tenant_id=22,
        connector_key='mock-secondary',
        location_ids=(FIRST_LOCATION_ID, SECOND_LOCATION_ID),
    )
    second = MockPosAdapter(second_dataset)

    assert run(first.get_product(context(location_id=None), product_external_id='product-001'))
    second_context = context(tenant_id=22, connector_key='mock-secondary')
    assert run(second.get_product(second_context, product_external_id='product-001'))
    with pytest.raises(PosNotFoundError):
        run(first.get_product(second_context, product_external_id='product-001'))
    with pytest.raises(PosNotFoundError):
        run(second.get_product(context(), product_external_id='product-001'))

    created = run(create_order(first))
    with pytest.raises(PosNotFoundError):
        run(second.get_order(second_context, external_order_id=created.external_id))


def test_location_listing_lookup_and_scope(adapter: MockPosAdapter) -> None:
    unscoped = context(location_id=None)
    assert [item.external_id for item in run(adapter.list_locations(unscoped))] == [
        'location-001',
        'location-002',
    ]
    assert [item.external_id for item in run(adapter.list_locations(location_context()))] == [
        'location-001'
    ]
    assert (
        run(adapter.get_location(unscoped, external_location_id='location-002')).external_id
        == 'location-002'
    )
    with pytest.raises(PosNotFoundError):
        run(adapter.get_location(location_context(), external_location_id='location-002'))
    with pytest.raises(PosNotFoundError):
        run(adapter.get_location(unscoped, external_location_id='location-missing'))
    with pytest.raises(PosNotFoundError):
        run(adapter.list_locations(location_context(999)))


def test_customer_lookup_behavior(adapter: MockPosAdapter) -> None:
    unscoped = context(location_id=None)
    assert (
        run(adapter.get_customer(unscoped, external_customer_id='customer-001')).email
        == 'ana@example.test'
    )
    assert run(adapter.find_customer(unscoped, email=' ANA@EXAMPLE.TEST ')).external_id == (
        'customer-001'
    )
    assert run(adapter.find_customer(unscoped, phone=' +525500000002 ')).external_id == (
        'customer-002'
    )
    assert run(
        adapter.find_customer(
            unscoped,
            email='marta@example.test',
            phone='+525500000003',
        )
    ).status is ExternalEntityStatus.INACTIVE
    assert run(adapter.find_customer(unscoped, email='missing@example.test')) is None
    assert (
        run(
            adapter.find_customer(
                unscoped,
                email='ana@example.test',
                phone='+525500000002',
            )
        )
        is None
    )
    with pytest.raises(PosInvalidDataError):
        run(adapter.find_customer(unscoped))
    with pytest.raises(PosNotFoundError):
        run(adapter.get_customer(unscoped, external_customer_id='customer-missing'))


def test_catalog_is_stable_and_preserves_inactive_products(adapter: MockPosAdapter) -> None:
    unscoped = context(location_id=None)
    products = run(adapter.list_products(unscoped))
    assert [product.external_id for product in products] == [
        'product-001',
        'product-002',
        'product-003',
        'product-004',
    ]
    assert run(adapter.get_product(unscoped, product_external_id='product-001')).status is (
        ExternalEntityStatus.ACTIVE
    )
    assert run(adapter.get_product(unscoped, product_external_id='product-004')).status is (
        ExternalEntityStatus.INACTIVE
    )
    with pytest.raises(PosNotFoundError):
        run(adapter.get_product(unscoped, product_external_id='product-missing'))


def test_prices_are_exact_explicit_and_location_specific(
    adapter: MockPosAdapter, dataset: MockPosDataset
) -> None:
    first = run(adapter.get_price(location_context(), product_external_id='product-001'))
    second = run(
        adapter.get_price(
            location_context(SECOND_LOCATION_ID),
            product_external_id='product-001',
        )
    )
    assert first.amount == Decimal('99.90')
    assert second.amount == Decimal('109.90')
    assert first.amount != second.amount
    assert first.currency == second.currency == 'MXN'
    assert isinstance(first.amount, Decimal)
    with pytest.raises(PosNotFoundError):
        run(adapter.get_price(location_context(), product_external_id='product-missing'))
    with pytest.raises(PosNotFoundError):
        run(adapter.get_price(location_context(999), product_external_id='product-001'))

    dataset_without_price = replace(
        dataset,
        prices=tuple(
            entry
            for entry in dataset.prices
            if not (
                entry[0] == FIRST_LOCATION_ID
                and entry[1].product_external_id == 'product-003'
            )
        ),
    )
    adapter_without_price = MockPosAdapter(dataset_without_price)
    with pytest.raises(PosNotFoundError):
        run(
            adapter_without_price.get_price(
                location_context(),
                product_external_id='product-003',
            )
        )


def test_promotions_are_deterministic_and_filterable(adapter: MockPosAdapter) -> None:
    all_promotions = run(adapter.list_promotions(location_context()))
    assert [promotion.external_id for promotion in all_promotions] == [
        'promotion-001',
        'promotion-002',
    ]
    hamburger_promotions = run(
        adapter.list_promotions(location_context(), product_external_id='product-001')
    )
    assert [promotion.external_id for promotion in hamburger_promotions] == [
        'promotion-001',
        'promotion-002',
    ]
    fries_promotions = run(
        adapter.list_promotions(location_context(), product_external_id='product-002')
    )
    assert [promotion.external_id for promotion in fries_promotions] == ['promotion-001']
    with pytest.raises(PosNotFoundError):
        run(adapter.list_promotions(location_context(), product_external_id='product-missing'))


def test_unsupported_promotions_use_canonical_error(dataset: MockPosDataset) -> None:
    adapter = MockPosAdapter(
        dataset,
        failure_mode=MockPosFailureMode.PROMOTIONS_UNSUPPORTED,
    )
    with pytest.raises(PosUnsupportedCapabilityError):
        run(adapter.list_promotions(location_context()))


def test_order_creation_is_deterministic_and_location_scoped(adapter: MockPosAdapter) -> None:
    created = run(create_order(adapter))
    assert created.external_id == 'mock-order-0001'
    assert created.status is CanonicalOrderStatus.SUBMITTED
    assert created.currency == 'MXN'
    assert created.subtotal == created.total == Decimal('99.90')
    assert created.items[0].external_line_id == 'mock-line-0001'
    assert created.items[0].quantity == Decimal('1')
    assert run(
        adapter.get_order(location_context(), external_order_id=created.external_id)
    ) == created
    with pytest.raises(PosNotFoundError):
        run(
            adapter.get_order(
                location_context(SECOND_LOCATION_ID),
                external_order_id=created.external_id,
            )
        )
    with pytest.raises(PosNotFoundError):
        run(create_order(adapter, idempotency_key='wrong-location', location_id=999))


def test_order_creation_rejects_invalid_product_and_currency(adapter: MockPosAdapter) -> None:
    with pytest.raises(PosInvalidDataError):
        run(
            adapter.create_order(
                location_context(),
                items=(),
                currency='MXN',
                idempotency_key='empty-order',
            )
        )
    with pytest.raises(PosInvalidDataError):
        run(
            adapter.create_order(
                location_context(),
                items=(order_item(),),
                currency='MXN',
                idempotency_key=' ',
            )
        )
    with pytest.raises(PosRejectedError):
        run(
            create_order(
                adapter,
                idempotency_key='inactive',
                item=order_item('product-004', unit_price='129.00', line_total='129.00'),
            )
        )
    with pytest.raises(PosNotFoundError):
        run(create_order(adapter, idempotency_key='unknown', item=order_item('missing')))
    with pytest.raises(PosInvalidDataError):
        run(create_order(adapter, idempotency_key='currency', currency='USD'))


def test_create_order_idempotent_retry_returns_original_result(adapter: MockPosAdapter) -> None:
    first = run(create_order(adapter, currency='mxn'))
    retry = run(create_order(adapter, currency='MXN'))
    assert retry is first

    next_order = run(create_order(adapter, idempotency_key='create-002'))
    assert next_order.external_id == 'mock-order-0002'


def test_create_order_idempotency_conflict_does_not_create_order(adapter: MockPosAdapter) -> None:
    first = run(create_order(adapter))
    different_item = order_item(quantity='2', line_total='199.80')
    with pytest.raises(PosInvalidDataError):
        run(create_order(adapter, item=different_item))

    next_order = run(create_order(adapter, idempotency_key='create-002'))
    assert first.external_id == 'mock-order-0001'
    assert next_order.external_id == 'mock-order-0002'


def test_all_canonical_order_statuses_are_observable(adapter: MockPosAdapter) -> None:
    seeded_orders = (
        (FIRST_LOCATION_ID, 'order-accepted-001'),
        (FIRST_LOCATION_ID, 'order-preparation-001'),
        (FIRST_LOCATION_ID, 'order-ready-001'),
        (SECOND_LOCATION_ID, 'order-completed-001'),
        (SECOND_LOCATION_ID, 'order-failed-001'),
    )
    statuses = {
        run(
            adapter.get_order_status(
                location_context(location_id),
                external_order_id=external_order_id,
            )
        ).status
        for location_id, external_order_id in seeded_orders
    }
    created = run(create_order(adapter))
    statuses.add(created.status)
    cancelled = run(
        adapter.cancel_order(
            location_context(),
            external_order_id=created.external_id,
            idempotency_key='cancel-001',
        )
    )
    statuses.add(cancelled.status)
    assert statuses == set(CanonicalOrderStatus)


def test_cancellation_is_idempotent_and_rejects_conflicts(adapter: MockPosAdapter) -> None:
    first = run(
        adapter.cancel_order(
            location_context(),
            external_order_id='order-accepted-001',
            idempotency_key='cancel-001',
        )
    )
    retry = run(
        adapter.cancel_order(
            location_context(),
            external_order_id='order-accepted-001',
            idempotency_key='cancel-001',
        )
    )
    assert first.status is CanonicalOrderStatus.CANCELLED
    assert retry is first
    with pytest.raises(PosInvalidDataError):
        run(
            adapter.cancel_order(
                location_context(),
                external_order_id='order-preparation-001',
                idempotency_key='cancel-001',
            )
        )

    for external_order_id in ('order-completed-001', 'order-failed-001'):
        with pytest.raises(PosRejectedError):
            run(
                adapter.cancel_order(
                    location_context(SECOND_LOCATION_ID),
                    external_order_id=external_order_id,
                    idempotency_key=f'cancel-{external_order_id}',
                )
            )


def test_uncertain_result_creates_once_and_reconciles_on_retry(dataset: MockPosDataset) -> None:
    adapter = MockPosAdapter(
        dataset,
        failure_mode=MockPosFailureMode.ORDER_UNCERTAIN_ONCE,
    )
    with pytest.raises(PosUncertainResultError):
        run(create_order(adapter))

    reconciled = run(create_order(adapter))
    assert reconciled.external_id == 'mock-order-0001'
    assert run(
        adapter.get_order(location_context(), external_order_id=reconciled.external_id)
    ) == reconciled
    next_order = run(create_order(adapter, idempotency_key='create-002'))
    assert next_order.external_id == 'mock-order-0002'


def test_configured_failures_use_only_canonical_errors(dataset: MockPosDataset) -> None:
    unavailable = MockPosAdapter(dataset, failure_mode=MockPosFailureMode.POS_UNAVAILABLE)
    with pytest.raises(PosTemporaryFailureError):
        run(unavailable.list_products(context(location_id=None)))

    rejected = MockPosAdapter(dataset, failure_mode=MockPosFailureMode.ORDER_REJECTED)
    with pytest.raises(PosRejectedError):
        run(create_order(rejected))

    mapping = MockPosAdapter(
        dataset,
        failure_mode=MockPosFailureMode.ORDER_STATUS_MAPPING_FAILURE,
    )
    with pytest.raises(PosMappingError):
        run(
            mapping.get_order_status(
                location_context(),
                external_order_id='order-ready-001',
            )
        )


def test_reset_restores_seed_state_counters_and_idempotency(adapter: MockPosAdapter) -> None:
    created = run(create_order(adapter))
    run(
        adapter.cancel_order(
            location_context(),
            external_order_id='order-accepted-001',
            idempotency_key='cancel-001',
        )
    )
    adapter.reset()

    with pytest.raises(PosNotFoundError):
        run(adapter.get_order(location_context(), external_order_id=created.external_id))
    restored = run(
        adapter.get_order(location_context(), external_order_id='order-accepted-001')
    )
    assert restored.status is CanonicalOrderStatus.ACCEPTED
    recreated = run(create_order(adapter))
    assert recreated.external_id == 'mock-order-0001'
    assert recreated.items[0].external_line_id == 'mock-line-0001'


def test_reset_restores_uncertain_once_behavior(dataset: MockPosDataset) -> None:
    adapter = MockPosAdapter(
        dataset,
        failure_mode=MockPosFailureMode.ORDER_UNCERTAIN_ONCE,
    )
    with pytest.raises(PosUncertainResultError):
        run(create_order(adapter))
    assert run(create_order(adapter)).external_id == 'mock-order-0001'

    adapter.reset()
    with pytest.raises(PosUncertainResultError):
        run(create_order(adapter))
    assert run(create_order(adapter)).external_id == 'mock-order-0001'


def test_mock_has_no_database_http_network_random_or_vendor_dependency() -> None:
    source = inspect.getsource(mock_module).lower()
    forbidden_dependencies = (
        'aiomysql',
        'fastapi',
        'httpx',
        'pymysql',
        'random',
        'requests',
        'socket',
        'sqlalchemy',
        'urllib',
    )
    for dependency in forbidden_dependencies:
        assert dependency not in source
