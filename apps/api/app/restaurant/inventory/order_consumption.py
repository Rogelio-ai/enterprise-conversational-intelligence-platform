from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InventoryItem,
    Product,
    ProductConsumptionComponent,
    ProductConsumptionDefinition,
    RestaurantOrder,
    RestaurantOrderConsumption,
    RestaurantOrderItem,
    RestaurantOrderItemComponent,
    StockMovement,
)
from app.restaurant.inventory import errors
from app.restaurant.inventory.contracts import (
    OrderConsumptionMovementProjection,
    OrderConsumptionProjection,
    OrderItemConsumptionProjection,
)
from app.restaurant.inventory.units import UnitConversionError, exact_quantity


SCHEMA_VERSION = 1
ZERO = Decimal('0')
PERCENT_UNIT = Decimal('0.0001')


@dataclass(frozen=True, slots=True)
class _Source:
    order_item: RestaurantOrderItem
    order_item_component_id: int | None
    product_id: int
    multiplier: Decimal
    source_key_prefix: str


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=True
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _decimal(value: Decimal) -> str:
    return format(value, 'f')


async def materialize_accepted_order(
    db: AsyncSession, *, order: RestaurantOrder
) -> RestaurantOrderConsumption:
    existing = await db.scalar(
        select(RestaurantOrderConsumption).where(
            RestaurantOrderConsumption.tenant_id == order.tenant_id,
            RestaurantOrderConsumption.restaurant_order_id == order.id,
        )
    )
    if existing is not None:
        return existing

    items = tuple(
        (
            await db.execute(
                select(RestaurantOrderItem)
                .where(
                    RestaurantOrderItem.tenant_id == order.tenant_id,
                    RestaurantOrderItem.order_id == order.id,
                )
                .order_by(RestaurantOrderItem.position, RestaurantOrderItem.id)
            )
        ).scalars().all()
    )
    components = tuple(
        (
            await db.execute(
                select(RestaurantOrderItemComponent)
                .where(
                    RestaurantOrderItemComponent.tenant_id == order.tenant_id,
                    RestaurantOrderItemComponent.order_id == order.id,
                )
                .order_by(
                    RestaurantOrderItemComponent.order_item_id,
                    RestaurantOrderItemComponent.position,
                    RestaurantOrderItemComponent.id,
                )
            )
        ).scalars().all()
    )
    components_by_item: dict[int, list[RestaurantOrderItemComponent]] = defaultdict(list)
    for component in components:
        components_by_item[component.order_item_id].append(component)

    sources: list[_Source] = []
    for item in items:
        sources.append(
            _Source(
                item, None, item.product_id, Decimal(item.quantity),
                f'item:{item.id}:parent',
            )
        )
        for component in components_by_item[item.id]:
            sources.append(
                _Source(
                    item,
                    component.id,
                    component.product_id,
                    Decimal(item.quantity) * Decimal(component.quantity),
                    f'item:{item.id}:component:{component.id}',
                )
            )

    product_ids = sorted({source.product_id for source in sources})
    if product_ids:
        await db.execute(
            select(Product.id)
            .where(
                Product.tenant_id == order.tenant_id,
                Product.organization_id == order.organization_id,
                Product.id.in_(product_ids),
            )
            .order_by(Product.id)
            .with_for_update()
        )
    definitions = tuple(
        (
            await db.execute(
                select(ProductConsumptionDefinition)
                .where(
                    ProductConsumptionDefinition.tenant_id == order.tenant_id,
                    ProductConsumptionDefinition.organization_id == order.organization_id,
                    ProductConsumptionDefinition.location_id == order.location_id,
                    ProductConsumptionDefinition.product_id.in_(product_ids),
                )
                .order_by(ProductConsumptionDefinition.product_id)
                .with_for_update()
            )
        ).scalars().all()
    ) if product_ids else ()
    definitions_by_product = {value.product_id: value for value in definitions}
    definition_ids = [value.id for value in definitions]
    rows = tuple(
        (
            await db.execute(
                select(ProductConsumptionComponent, InventoryItem)
                .join(
                    InventoryItem,
                    (InventoryItem.id == ProductConsumptionComponent.inventory_item_id)
                    & (InventoryItem.tenant_id == ProductConsumptionComponent.tenant_id)
                    & (InventoryItem.organization_id == ProductConsumptionComponent.organization_id)
                    & (InventoryItem.location_id == ProductConsumptionComponent.location_id),
                )
                .where(
                    ProductConsumptionComponent.tenant_id == order.tenant_id,
                    ProductConsumptionComponent.definition_id.in_(definition_ids),
                )
                .order_by(
                    ProductConsumptionComponent.definition_id,
                    ProductConsumptionComponent.inventory_item_id,
                )
                .with_for_update()
            )
        ).all()
    ) if definition_ids else ()
    recipe_rows: dict[int, list[tuple[ProductConsumptionComponent, InventoryItem]]] = (
        defaultdict(list)
    )
    for component, item in rows:
        recipe_rows[component.definition_id].append((component, item))

    unresolved: list[dict[str, object]] = []
    staged: list[dict[str, object]] = []
    fingerprint_sources: list[dict[str, object]] = []
    for source in sources:
        definition = definitions_by_product.get(source.product_id)
        source_evidence = {
            'restaurant_order_item_id': source.order_item.id,
            'restaurant_order_item_component_id': source.order_item_component_id,
            'product_id': source.product_id,
            'multiplier': _decimal(source.multiplier),
        }
        if definition is None or definition.status != 'ACTIVE':
            unresolved.append({**source_evidence, 'reason': 'MISSING_DEFINITION'})
            fingerprint_sources.append({**source_evidence, 'resolution': 'MISSING'})
            continue
        if definition.tracking_mode == 'NON_DERIVABLE':
            unresolved.append({**source_evidence, 'reason': 'NON_DERIVABLE'})
            fingerprint_sources.append(
                {
                    **source_evidence, 'resolution': 'NON_DERIVABLE',
                    'definition_id': definition.id,
                    'definition_version': definition.version,
                }
            )
            continue
        fingerprint_sources.append(
            {
                **source_evidence, 'resolution': 'DERIVABLE',
                'definition_id': definition.id,
                'definition_version': definition.version,
            }
        )
        for recipe_component, item in recipe_rows[definition.id]:
            consumed = source.multiplier * Decimal(recipe_component.quantity)
            try:
                consumed = exact_quantity(consumed, positive=True)
            except UnitConversionError:
                unresolved.append(
                    {
                        **source_evidence,
                        'inventory_item_id': item.id,
                        'reason': 'UNREPRESENTABLE_QUANTITY',
                    }
                )
                continue
            extended_cost = consumed * Decimal(item.standard_unit_cost)
            source_key = f'{source.source_key_prefix}:recipe-component:{recipe_component.id}'
            staged.append(
                {
                    'source_key': source_key,
                    'source': source,
                    'definition': definition,
                    'item': item,
                    'quantity': consumed,
                    'extended_cost': extended_cost,
                }
            )
            if item.currency != order.currency:
                unresolved.append(
                    {
                        **source_evidence,
                        'inventory_item_id': item.id,
                        'currency': item.currency,
                        'order_currency': order.currency,
                        'reason': 'CURRENCY_MISMATCH',
                    }
                )

    fingerprint = _fingerprint(
        {
            'schema_version': SCHEMA_VERSION,
            'restaurant_order_id': order.id,
            'items': [
                {
                    'id': item.id, 'product_id': item.product_id,
                    'quantity': _decimal(Decimal(item.quantity)),
                    'components': [
                        {
                            'id': value.id, 'product_id': value.product_id,
                            'quantity': _decimal(Decimal(value.quantity)),
                        }
                        for value in components_by_item[item.id]
                    ],
                }
                for item in items
            ],
            'sources': fingerprint_sources,
            'movements': [
                {
                    'source_key': str(value['source_key']),
                    'inventory_item_id': value['item'].id,
                    'quantity': _decimal(value['quantity']),
                    'definition_id': value['definition'].id,
                    'definition_version': value['definition'].version,
                    'unit_cost': _decimal(value['item'].standard_unit_cost),
                    'currency': value['item'].currency,
                    'extended_cost': _decimal(value['extended_cost']),
                }
                for value in staged
            ],
            'unresolved': unresolved,
        }
    )
    header = RestaurantOrderConsumption(
        tenant_id=order.tenant_id,
        organization_id=order.organization_id,
        location_id=order.location_id,
        restaurant_order_id=order.id,
        coverage_status='PARTIAL' if unresolved else 'COMPLETE',
        schema_version=SCHEMA_VERSION,
        source_fingerprint=fingerprint,
        unresolved_evidence=unresolved,
        created_at=order.accepted_at,
    )
    db.add(header)
    await db.flush()
    for value in staged:
        source = value['source']
        definition = value['definition']
        item = value['item']
        assert isinstance(source, _Source)
        assert isinstance(definition, ProductConsumptionDefinition)
        assert isinstance(item, InventoryItem)
        source_key = str(value['source_key'])
        movement_fingerprint = _fingerprint(
            {
                'header_fingerprint': fingerprint,
                'source_key': source_key,
                'quantity': _decimal(value['quantity']),
                'unit_cost': _decimal(Decimal(item.standard_unit_cost)),
                'currency': item.currency,
            }
        )
        db.add(
            StockMovement(
                tenant_id=order.tenant_id,
                organization_id=order.organization_id,
                location_id=order.location_id,
                inventory_item_id=item.id,
                movement_type='CONSUMPTION',
                quantity=-value['quantity'],
                reversal_of_movement_id=None,
                reason='Accepted RestaurantOrder theoretical consumption',
                reference=f'restaurant-order:{order.id}',
                recorded_at=order.accepted_at,
                actor_type='SYSTEM',
                actor_id=None,
                actor_reference=f'restaurant-order:{order.id}',
                opening_balance_slot=None,
                idempotency_actor_scope='SYSTEM:RESTAURANT_ORDER_CONSUMPTION',
                idempotency_key=f'order:{order.id}:{hashlib.sha256(source_key.encode()).hexdigest()}',
                request_schema_version=SCHEMA_VERSION,
                request_fingerprint=movement_fingerprint,
                restaurant_order_consumption_id=header.id,
                restaurant_order_id=order.id,
                restaurant_order_item_id=source.order_item.id,
                restaurant_order_item_component_id=source.order_item_component_id,
                source_product_id=source.product_id,
                consumption_definition_id=definition.id,
                consumption_definition_version=definition.version,
                inventory_item_name_snapshot=item.name,
                base_uom_snapshot=item.base_uom,
                unit_cost_snapshot=item.standard_unit_cost,
                currency_snapshot=item.currency,
                extended_cost_snapshot=value['extended_cost'],
                consumption_source_key=source_key,
            )
        )
    try:
        await db.flush()
    except IntegrityError as exc:
        raise errors.OrderConsumptionConflictError(
            'Restaurant Order consumption was materialized concurrently'
        ) from exc
    return header


def _margin_percent(margin: Decimal, commercial: Decimal) -> Decimal | None:
    if commercial == ZERO:
        return None
    return ((margin / commercial) * Decimal('100')).quantize(
        PERCENT_UNIT, rounding=ROUND_HALF_UP
    )


async def get_order_consumption(
    db: AsyncSession, *, tenant_id: int, order_id: int
) -> OrderConsumptionProjection:
    order = await db.scalar(
        select(RestaurantOrder).where(
            RestaurantOrder.id == order_id, RestaurantOrder.tenant_id == tenant_id
        )
    )
    if order is None:
        raise errors.OrderConsumptionNotFoundError('Restaurant Order not found')
    header = await db.scalar(
        select(RestaurantOrderConsumption).where(
            RestaurantOrderConsumption.tenant_id == tenant_id,
            RestaurantOrderConsumption.restaurant_order_id == order_id,
        )
    )
    if header is None:
        raise errors.OrderConsumptionNotFoundError(
            'Theoretical consumption is not available for this Restaurant Order'
        )
    items = tuple(
        (
            await db.execute(
                select(RestaurantOrderItem)
                .where(
                    RestaurantOrderItem.tenant_id == tenant_id,
                    RestaurantOrderItem.order_id == order_id,
                )
                .order_by(RestaurantOrderItem.position, RestaurantOrderItem.id)
            )
        ).scalars().all()
    )
    movements = tuple(
        (
            await db.execute(
                select(StockMovement)
                .where(
                    StockMovement.tenant_id == tenant_id,
                    StockMovement.restaurant_order_consumption_id == header.id,
                )
                .order_by(StockMovement.restaurant_order_item_id, StockMovement.id)
            )
        ).scalars().all()
    )
    movements_by_item: dict[int, list[StockMovement]] = defaultdict(list)
    for movement in movements:
        assert movement.restaurant_order_item_id is not None
        movements_by_item[movement.restaurant_order_item_id].append(movement)
    unresolved = tuple(header.unresolved_evidence)
    projected_items: list[OrderItemConsumptionProjection] = []
    for item in items:
        item_unresolved = tuple(
            value for value in unresolved
            if value.get('restaurant_order_item_id') == item.id
        )
        item_movements = tuple(movements_by_item[item.id])
        complete = not item_unresolved
        cost = (
            sum(
                (Decimal(value.extended_cost_snapshot) for value in item_movements),
                ZERO,
            )
            if complete else None
        )
        margin = Decimal(item.commercial_amount) - cost if cost is not None else None
        projected_items.append(
            OrderItemConsumptionProjection(
                restaurant_order_item_id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                commercial_amount=item.commercial_amount,
                coverage_status='COMPLETE' if complete else 'PARTIAL',
                unresolved_evidence=item_unresolved,
                movements=tuple(
                    OrderConsumptionMovementProjection(
                        stock_movement_id=value.id,
                        restaurant_order_item_id=item.id,
                        restaurant_order_item_component_id=(
                            value.restaurant_order_item_component_id
                        ),
                        source_product_id=value.source_product_id,
                        inventory_item_id=value.inventory_item_id,
                        inventory_item_name=value.inventory_item_name_snapshot,
                        base_uom=value.base_uom_snapshot,
                        consumed_quantity=-Decimal(value.quantity),
                        consumption_definition_version=(
                            value.consumption_definition_version
                        ),
                        unit_cost=value.unit_cost_snapshot,
                        currency=value.currency_snapshot,
                        extended_cost=value.extended_cost_snapshot,
                    )
                    for value in item_movements
                ),
                historical_theoretical_cost=cost,
                theoretical_gross_margin=margin,
                theoretical_margin_percent=(
                    _margin_percent(margin, Decimal(item.commercial_amount))
                    if margin is not None else None
                ),
            )
        )
    total_cost = (
        sum(
            (
                Decimal(value.extended_cost_snapshot)
                for value in movements
            ),
            ZERO,
        )
        if header.coverage_status == 'COMPLETE' else None
    )
    total_margin = Decimal(order.payable_total) - total_cost if total_cost is not None else None
    return OrderConsumptionProjection(
        restaurant_order_id=order.id,
        currency=order.currency,
        coverage_status=header.coverage_status,
        schema_version=header.schema_version,
        source_fingerprint=header.source_fingerprint,
        unresolved_evidence=unresolved,
        items=tuple(projected_items),
        commercial_amount=order.payable_total,
        historical_theoretical_cost=total_cost,
        theoretical_gross_margin=total_margin,
        theoretical_margin_percent=(
            _margin_percent(total_margin, Decimal(order.payable_total))
            if total_margin is not None else None
        ),
    )
