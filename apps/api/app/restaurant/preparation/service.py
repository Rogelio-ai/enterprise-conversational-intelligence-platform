from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    LocationPosConnection,
    LocationPreparationConfiguration,
    PosOrderSubmission,
    PreparationArea,
    PreparationItemTransition,
    PreparationRouting,
    PreparationWork,
    PreparationWorkItem,
    ProductPreparationRoute,
    Resource,
    RestaurantOrder,
    RestaurantOrderItem,
    RestaurantOrderItemComponent,
)
from app.restaurant.preparation import errors
from app.restaurant.preparation.contracts import (
    PreparationExecutionItemProjection,
    PreparationExecutionWorkProjection,
    PreparationItemDetailProjection,
    PreparationItemTransitionProjection,
    PreparationOrderContextProjection,
    PreparationRoutingProjection,
    PreparationTransitionResult,
    PreparationWorkItemProjection,
    PreparationWorkProjection,
)
from app.restaurant.preparation_delivery import service as delivery_service


ROUTING_SCHEMA_VERSION = 1
EXECUTION_STATES = ('NEW', 'IN_PROGRESS', 'COMPLETED')


def _now() -> datetime:
    # Portable DATETIME storage in the certified MySQL/MariaDB schema has
    # second precision, so use the persisted precision for stable projections.
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _actor(execution: ExecutionContext) -> dict[str, object]:
    return {
        'initiating_actor_type': execution.actor_type.value,
        'initiating_membership_id': execution.principal_id if execution.actor_type is ActorType.EMPLOYEE else None,
        'initiating_principal_reference': execution.principal_reference,
        'correlation_id': execution.correlation_id,
    }


async def lock_order(db: AsyncSession, *, tenant_id: int, order_id: int) -> RestaurantOrder:
    order = await db.scalar(
        select(RestaurantOrder)
        .where(RestaurantOrder.id == order_id, RestaurantOrder.tenant_id == tenant_id)
        .with_for_update()
    )
    if order is None:
        raise errors.PreparationNotFoundError('Restaurant Order not found')
    if order.status != 'ACCEPTED':
        raise errors.PreparationConflictError('Only an accepted Restaurant Order may be routed')
    return order


async def freeze_ownership(
    db: AsyncSession,
    *,
    order: RestaurantOrder,
    execution: ExecutionContext,
    reject_legacy_submission: bool,
) -> PreparationRouting:
    routing = await db.scalar(
        select(PreparationRouting).where(
            PreparationRouting.tenant_id == order.tenant_id,
            PreparationRouting.restaurant_order_id == order.id,
        ).with_for_update()
    )
    if routing is not None:
        return routing

    if reject_legacy_submission:
        legacy = await db.scalar(
            select(PosOrderSubmission.id).where(
                PosOrderSubmission.tenant_id == order.tenant_id,
                PosOrderSubmission.restaurant_order_id == order.id,
            ).limit(1)
        )
        if legacy is not None:
            routing = PreparationRouting(
                tenant_id=order.tenant_id,
                organization_id=order.organization_id,
                location_id=order.location_id,
                restaurant_order_id=order.id,
                preparation_owner=None,
                state='ACTION_REQUIRED',
                routing_schema_version=ROUTING_SCHEMA_VERSION,
                error_code='LEGACY_PREPARATION_OWNERSHIP_UNRESOLVED',
                error_detail='Existing POS submission predates preparation ownership freezing',
                **_actor(execution),
            )
            db.add(routing)
            await db.flush()
            return routing

    configuration = await db.scalar(
        select(LocationPreparationConfiguration).where(
            LocationPreparationConfiguration.tenant_id == order.tenant_id,
            LocationPreparationConfiguration.organization_id == order.organization_id,
            LocationPreparationConfiguration.location_id == order.location_id,
        )
    )
    if configuration is None:
        routing = PreparationRouting(
            tenant_id=order.tenant_id,
            organization_id=order.organization_id,
            location_id=order.location_id,
            restaurant_order_id=order.id,
            preparation_owner=None,
            state='ACTION_REQUIRED',
            routing_schema_version=ROUTING_SCHEMA_VERSION,
            error_code='PREPARATION_OWNERSHIP_UNRESOLVED',
            error_detail='Location preparation ownership is not configured',
            **_actor(execution),
        )
    else:
        routing = PreparationRouting(
            tenant_id=order.tenant_id,
            organization_id=order.organization_id,
            location_id=order.location_id,
            restaurant_order_id=order.id,
            preparation_owner=configuration.preparation_owner,
            state='PENDING',
            routing_schema_version=ROUTING_SCHEMA_VERSION,
            **_actor(execution),
        )
    db.add(routing)
    await db.flush()
    return routing


async def validate_pos_dispatch_compatibility(
    db: AsyncSession, *, order: RestaurantOrder, routing: PreparationRouting, connection: LocationPosConnection
) -> None:
    if routing.preparation_owner is None:
        raise errors.PreparationConflictError(routing.error_code or 'PREPARATION_OWNERSHIP_UNRESOLVED')
    if (
        routing.preparation_owner == 'PLATFORM'
        and connection.external_preparation_behavior != 'NO_PREPARATION_OUTPUT'
    ):
        routing.state = 'ACTION_REQUIRED'
        routing.error_code = 'EXTERNAL_PREPARATION_OUTPUT_CONFLICT'
        routing.error_detail = 'The active POS connection may independently produce preparation output'
        raise errors.PreparationConflictError(routing.error_code)


def _action_required(routing: PreparationRouting, code: str, detail: str) -> None:
    routing.state = 'ACTION_REQUIRED'
    routing.error_code = code
    routing.error_detail = detail[:500]
    routing.routed_at = None
    routing.routing_fingerprint = None


def _fingerprint(order_id: int, owner: str, sources: list[dict[str, object]]) -> str:
    value = {
        'restaurant_order_id': order_id,
        'preparation_owner': owner,
        'routing_schema_version': ROUTING_SCHEMA_VERSION,
        'sources': sources,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


async def _projection(db: AsyncSession, routing: PreparationRouting) -> PreparationRoutingProjection:
    works = tuple((await db.execute(
        select(PreparationWork).where(
            PreparationWork.tenant_id == routing.tenant_id,
            PreparationWork.routing_id == routing.id,
        ).order_by(PreparationWork.preparation_area_id, PreparationWork.id)
    )).scalars().all())
    projected: list[PreparationWorkProjection] = []
    for work in works:
        items = tuple((await db.execute(
            select(PreparationWorkItem).where(
                PreparationWorkItem.tenant_id == routing.tenant_id,
                PreparationWorkItem.preparation_work_id == work.id,
            ).order_by(PreparationWorkItem.id)
        )).scalars().all())
        projected.append(PreparationWorkProjection(
            id=work.id,
            preparation_area_id=work.preparation_area_id,
            area_code=work.area_code_snapshot,
            area_name=work.area_name_snapshot,
            items=tuple(PreparationWorkItemProjection(
                id=item.id,
                source_restaurant_order_item_id=item.source_restaurant_order_item_id,
                source_restaurant_order_item_component_id=item.source_restaurant_order_item_component_id,
                required_quantity=item.required_quantity,
                route_id=item.route_id,
            ) for item in items),
        ))
    return PreparationRoutingProjection(
        id=routing.id,
        restaurant_order_id=routing.restaurant_order_id,
        preparation_owner=routing.preparation_owner,
        state=routing.state,
        routing_schema_version=routing.routing_schema_version,
        routing_fingerprint=routing.routing_fingerprint,
        error_code=routing.error_code,
        error_detail=routing.error_detail,
        routed_at=routing.routed_at,
        works=tuple(projected),
    )


async def get_routing(db: AsyncSession, *, tenant_id: int, order_id: int) -> PreparationRoutingProjection:
    routing = await db.scalar(select(PreparationRouting).where(
        PreparationRouting.tenant_id == tenant_id,
        PreparationRouting.restaurant_order_id == order_id,
    ))
    if routing is None:
        raise errors.PreparationNotFoundError('Preparation Routing not found')
    return await _projection(db, routing)


async def route_order(
    db: AsyncSession, *, order_id: int, execution: ExecutionContext
) -> PreparationRoutingProjection:
    if execution.actor_type is not ActorType.EMPLOYEE:
        raise errors.PreparationConflictError('This preparation endpoint requires an employee actor')
    try:
        order = await lock_order(db, tenant_id=execution.tenant_id, order_id=order_id)
        routing = await freeze_ownership(
            db, order=order, execution=execution, reject_legacy_submission=True
        )
        if routing.state in ('ROUTED', 'EXTERNAL_POS_OWNED'):
            await db.commit()
            return await _projection(db, routing)
        if routing.error_code == 'LEGACY_PREPARATION_OWNERSHIP_UNRESOLVED':
            await db.commit()
            return await _projection(db, routing)
        if routing.preparation_owner is None:
            configuration = await db.scalar(select(LocationPreparationConfiguration).where(
                LocationPreparationConfiguration.tenant_id == order.tenant_id,
                LocationPreparationConfiguration.organization_id == order.organization_id,
                LocationPreparationConfiguration.location_id == order.location_id,
            ))
            if configuration is None:
                _action_required(routing, 'PREPARATION_OWNERSHIP_UNRESOLVED', 'Location preparation ownership is not configured')
                await db.commit()
                return await _projection(db, routing)
            routing.preparation_owner = configuration.preparation_owner
        routing.state = 'PENDING'
        routing.error_code = None
        routing.error_detail = None

        connection = await db.scalar(select(LocationPosConnection).where(
            LocationPosConnection.tenant_id == order.tenant_id,
            LocationPosConnection.organization_id == order.organization_id,
            LocationPosConnection.location_id == order.location_id,
            LocationPosConnection.status == 'ACTIVE',
            LocationPosConnection.active_slot == 1,
        ))
        if routing.preparation_owner == 'EXTERNAL_POS':
            if connection is None:
                _action_required(routing, 'EXTERNAL_POS_CONNECTION_REQUIRED', 'External POS preparation ownership requires an active POS connection')
            else:
                now = _now()
                routing.state = 'EXTERNAL_POS_OWNED'
                routing.routed_at = now
                routing.routing_fingerprint = _fingerprint(order.id, 'EXTERNAL_POS', [])
            await db.commit()
            return await _projection(db, routing)
        if connection is not None and connection.external_preparation_behavior != 'NO_PREPARATION_OUTPUT':
            _action_required(routing, 'EXTERNAL_PREPARATION_OUTPUT_CONFLICT', 'The active POS connection may independently produce preparation output')
            await db.commit()
            return await _projection(db, routing)

        items = tuple((await db.execute(select(RestaurantOrderItem).where(
            RestaurantOrderItem.tenant_id == order.tenant_id,
            RestaurantOrderItem.order_id == order.id,
        ).order_by(RestaurantOrderItem.position, RestaurantOrderItem.id))).scalars().all())
        components: dict[int, tuple[RestaurantOrderItemComponent, ...]] = {}
        product_ids = {item.product_id for item in items}
        for item in items:
            values = tuple((await db.execute(select(RestaurantOrderItemComponent).where(
                RestaurantOrderItemComponent.tenant_id == order.tenant_id,
                RestaurantOrderItemComponent.order_id == order.id,
                RestaurantOrderItemComponent.order_item_id == item.id,
            ).order_by(RestaurantOrderItemComponent.position, RestaurantOrderItemComponent.id))).scalars().all())
            components[item.id] = values
            product_ids.update(value.product_id for value in values)

        route_rows = tuple((await db.execute(select(ProductPreparationRoute).where(
            ProductPreparationRoute.tenant_id == order.tenant_id,
            ProductPreparationRoute.organization_id == order.organization_id,
            ProductPreparationRoute.location_id == order.location_id,
            ProductPreparationRoute.product_id.in_(sorted(product_ids)),
            ProductPreparationRoute.status == 'ACTIVE',
            ProductPreparationRoute.active_slot == 1,
        ).order_by(ProductPreparationRoute.product_id, ProductPreparationRoute.id).with_for_update())).scalars().all()) if product_ids else ()
        routes: dict[int, ProductPreparationRoute] = {}
        for route in route_rows:
            if route.product_id in routes:
                _action_required(routing, 'AMBIGUOUS_PRODUCT_ROUTE', f'Product {route.product_id} has multiple active preparation routes')
                await db.commit()
                return await _projection(db, routing)
            routes[route.product_id] = route
        historical_products = set((await db.execute(select(ProductPreparationRoute.product_id).where(
            ProductPreparationRoute.tenant_id == order.tenant_id,
            ProductPreparationRoute.organization_id == order.organization_id,
            ProductPreparationRoute.location_id == order.location_id,
            ProductPreparationRoute.product_id.in_(sorted(product_ids)),
        ))).scalars().all()) if product_ids else set()

        selected: list[tuple[PreparationArea, ProductPreparationRoute, RestaurantOrderItem | None, RestaurantOrderItemComponent | None, Decimal]] = []
        for item in items:
            parent_route = routes.get(item.product_id)
            if parent_route is None:
                code = 'INACTIVE_PRODUCT_ROUTE' if item.product_id in historical_products else 'MISSING_PRODUCT_ROUTE'
                _action_required(routing, code, f'Product {item.product_id} has no active preparation route')
                await db.commit()
                return await _projection(db, routing)
            if parent_route.policy == 'NO_PREPARATION':
                continue
            if parent_route.policy == 'AREA':
                selected.append((None, parent_route, item, None, item.quantity))  # type: ignore[arg-type]
                continue
            if parent_route.policy != 'COMPONENTS':
                _action_required(routing, 'UNSUPPORTED_ROUTING_STATE', f'Unsupported route policy for Product {item.product_id}')
                await db.commit()
                return await _projection(db, routing)
            for component in components[item.id]:
                component_route = routes.get(component.product_id)
                if component_route is None:
                    code = 'INACTIVE_PRODUCT_ROUTE' if component.product_id in historical_products else 'MISSING_COMPONENT_ROUTE'
                    _action_required(routing, code, f'Component Product {component.product_id} has no active preparation route')
                    await db.commit()
                    return await _projection(db, routing)
                if component_route.policy == 'COMPONENTS':
                    _action_required(routing, 'INVALID_COMPONENT_ROUTE', f'Component Product {component.product_id} cannot use COMPONENTS')
                    await db.commit()
                    return await _projection(db, routing)
                if component_route.policy == 'AREA':
                    selected.append((None, component_route, None, component, item.quantity * component.quantity))  # type: ignore[arg-type]

        area_ids = sorted({route.preparation_area_id for _, route, _, _, _ in selected if route.preparation_area_id is not None})
        areas = {area.id: area for area in tuple((await db.execute(select(PreparationArea).where(
            PreparationArea.tenant_id == order.tenant_id,
            PreparationArea.organization_id == order.organization_id,
            PreparationArea.location_id == order.location_id,
            PreparationArea.id.in_(area_ids),
        ).order_by(PreparationArea.id).with_for_update())).scalars().all())} if area_ids else {}
        resolved = []
        for _, route, item, component, quantity in selected:
            area = areas.get(route.preparation_area_id)
            if area is None or area.status != 'ACTIVE':
                _action_required(routing, 'INACTIVE_OR_INVALID_PREPARATION_AREA', f'Route {route.id} does not resolve to an active in-scope area')
                await db.commit()
                return await _projection(db, routing)
            resolved.append((area, route, item, component, quantity))

        sources = [
            {
                'source_type': 'ITEM' if item is not None else 'COMPONENT',
                'source_id': item.id if item is not None else component.id,
                'quantity': str(quantity),
                'route_id': route.id,
                'area_id': area.id,
            }
            for area, route, item, component, quantity in resolved
        ]
        sources.sort(key=lambda value: (value['source_type'], value['source_id']))
        fingerprint = _fingerprint(order.id, 'PLATFORM', sources)
        now = _now()
        by_area: dict[int, list[tuple[PreparationArea, ProductPreparationRoute, RestaurantOrderItem | None, RestaurantOrderItemComponent | None, Decimal]]] = defaultdict(list)
        for value in resolved:
            by_area[value[0].id].append(value)
        for area_id in sorted(by_area):
            area = by_area[area_id][0][0]
            work = PreparationWork(
                tenant_id=order.tenant_id, organization_id=order.organization_id,
                location_id=order.location_id, restaurant_order_id=order.id,
                routing_id=routing.id, preparation_area_id=area.id,
                preparation_owner='PLATFORM', area_code_snapshot=area.code,
                area_name_snapshot=area.name, routing_schema_version=ROUTING_SCHEMA_VERSION,
                routing_fingerprint=fingerprint, routed_at=now,
            )
            db.add(work)
            await db.flush()
            for _, route, item, component, quantity in sorted(by_area[area_id], key=lambda value: (value[2].id if value[2] is not None else 10**30 + value[3].id)):
                db.add(PreparationWorkItem(
                    tenant_id=order.tenant_id, organization_id=order.organization_id,
                    location_id=order.location_id, restaurant_order_id=order.id,
                    preparation_work_id=work.id,
                    source_restaurant_order_item_id=item.id if item is not None else None,
                    source_restaurant_order_item_component_id=component.id if component is not None else None,
                    source_restaurant_order_item_id_for_component=component.order_item_id if component is not None else None,
                    route_id=route.id, route_policy='AREA', required_quantity=quantity,
                ))
            await db.flush()
            await delivery_service.materialize_initial_dispatches(
                db,
                work=work,
                correlation_id=execution.correlation_id,
                causation_id=execution.causation_id,
            )
        routing.state = 'ROUTED'
        routing.routing_fingerprint = fingerprint
        routing.routed_at = now
        routing.error_code = None
        routing.error_detail = None
        await db.commit()
        return await _projection(db, routing)
    except IntegrityError:
        await db.rollback()
        winner = await db.scalar(select(PreparationRouting).where(
            PreparationRouting.tenant_id == execution.tenant_id,
            PreparationRouting.restaurant_order_id == order_id,
        ))
        if winner is None:
            raise
        if winner.state not in ('ROUTED', 'EXTERNAL_POS_OWNED'):
            await db.rollback()
            return await route_order(db, order_id=order_id, execution=execution)
        return await _projection(db, winner)
    except Exception:
        await db.rollback()
        raise


def _transition_projection(value: PreparationItemTransition) -> PreparationItemTransitionProjection:
    return PreparationItemTransitionProjection(
        id=value.id,
        sequence=value.sequence,
        from_state=value.from_state,
        to_state=value.to_state,
        actor_type=value.actor_type,
        actor_membership_id=value.actor_membership_id,
        actor_principal_reference=value.actor_principal_reference,
        correlation_id=value.correlation_id,
        occurred_at=value.occurred_at,
    )


async def _execution_item_projection(
    db: AsyncSession, item: PreparationWorkItem
) -> PreparationExecutionItemProjection:
    if item.source_restaurant_order_item_id is not None:
        source = await db.scalar(select(RestaurantOrderItem).where(
            RestaurantOrderItem.id == item.source_restaurant_order_item_id,
            RestaurantOrderItem.tenant_id == item.tenant_id,
            RestaurantOrderItem.order_id == item.restaurant_order_id,
        ))
        if source is None:
            raise RuntimeError('Preparation Work Item source snapshot is missing')
        source_type = 'ITEM'
        product_name = source.product_name
        parent_product_name = None
    else:
        component = await db.scalar(select(RestaurantOrderItemComponent).where(
            RestaurantOrderItemComponent.id == item.source_restaurant_order_item_component_id,
            RestaurantOrderItemComponent.tenant_id == item.tenant_id,
            RestaurantOrderItemComponent.order_id == item.restaurant_order_id,
        ))
        parent = await db.scalar(select(RestaurantOrderItem).where(
            RestaurantOrderItem.id == item.source_restaurant_order_item_id_for_component,
            RestaurantOrderItem.tenant_id == item.tenant_id,
            RestaurantOrderItem.order_id == item.restaurant_order_id,
        ))
        if component is None or parent is None:
            raise RuntimeError('Preparation Work Item component snapshot is missing')
        source_type = 'COMPONENT'
        product_name = component.product_name
        parent_product_name = parent.product_name
    return PreparationExecutionItemProjection(
        id=item.id,
        preparation_work_id=item.preparation_work_id,
        source_type=source_type,
        source_restaurant_order_item_id=item.source_restaurant_order_item_id,
        source_restaurant_order_item_component_id=item.source_restaurant_order_item_component_id,
        product_name=product_name,
        parent_product_name=parent_product_name,
        required_quantity=item.required_quantity,
        execution_state=item.execution_state,
        execution_version=item.execution_version,
    )


def _derived_work_state(items: tuple[PreparationWorkItem, ...]) -> str:
    if all(item.execution_state == 'NEW' for item in items):
        return 'NEW'
    if items and all(item.execution_state == 'COMPLETED' for item in items):
        return 'COMPLETED'
    return 'IN_PROGRESS'


async def _execution_work_projection(
    db: AsyncSession, work: PreparationWork
) -> PreparationExecutionWorkProjection:
    item_rows = tuple((await db.execute(select(PreparationWorkItem).where(
        PreparationWorkItem.tenant_id == work.tenant_id,
        PreparationWorkItem.preparation_work_id == work.id,
    ).order_by(PreparationWorkItem.id))).scalars().all())
    order = await db.scalar(select(RestaurantOrder).where(
        RestaurantOrder.id == work.restaurant_order_id,
        RestaurantOrder.tenant_id == work.tenant_id,
    ))
    if order is None:
        raise RuntimeError('Preparation Work Restaurant Order is missing')
    resource = await db.scalar(select(Resource).where(
        Resource.id == order.resource_id,
        Resource.tenant_id == order.tenant_id,
        Resource.location_id == order.location_id,
    ))
    return PreparationExecutionWorkProjection(
        id=work.id,
        preparation_area_id=work.preparation_area_id,
        area_code=work.area_code_snapshot,
        area_name=work.area_name_snapshot,
        routed_at=work.routed_at,
        execution_state=_derived_work_state(item_rows),
        order=PreparationOrderContextProjection(
            restaurant_order_id=order.id,
            accepted_at=order.accepted_at,
            source_channel=order.source_channel,
            resource_id=order.resource_id,
            service_session_id=order.service_session_id,
            diner_session_id=order.diner_session_id,
            current_resource_code=resource.code if resource is not None else None,
            current_resource_name=resource.name if resource is not None else None,
        ),
        items=tuple([await _execution_item_projection(db, item) for item in item_rows]),
    )


async def list_preparation_work(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    preparation_area_id: int | None = None,
    execution_state: str | None = None,
    restaurant_order_id: int | None = None,
    after_work_id: int | None = None,
    limit: int = 50,
) -> tuple[PreparationExecutionWorkProjection, ...]:
    has_item_not_new = select(PreparationWorkItem.id).where(
        PreparationWorkItem.tenant_id == PreparationWork.tenant_id,
        PreparationWorkItem.preparation_work_id == PreparationWork.id,
        PreparationWorkItem.execution_state != 'NEW',
    ).exists()
    has_item_not_completed = select(PreparationWorkItem.id).where(
        PreparationWorkItem.tenant_id == PreparationWork.tenant_id,
        PreparationWorkItem.preparation_work_id == PreparationWork.id,
        PreparationWorkItem.execution_state != 'COMPLETED',
    ).exists()
    statement = (
        select(PreparationWork)
        .where(
            PreparationWork.tenant_id == tenant_id,
            PreparationWork.location_id == location_id,
            PreparationWork.preparation_owner == 'PLATFORM',
        )
    )
    if execution_state == 'NEW':
        statement = statement.where(~has_item_not_new)
    elif execution_state == 'IN_PROGRESS':
        statement = statement.where(has_item_not_new, has_item_not_completed)
    elif execution_state == 'COMPLETED':
        statement = statement.where(~has_item_not_completed)
    else:
        # The operational default includes NEW and IN_PROGRESS derived work states.
        statement = statement.where(has_item_not_completed)
    if preparation_area_id is not None:
        statement = statement.where(PreparationWork.preparation_area_id == preparation_area_id)
    if restaurant_order_id is not None:
        statement = statement.where(PreparationWork.restaurant_order_id == restaurant_order_id)
    if after_work_id is not None:
        cursor = await db.scalar(select(PreparationWork).where(
            PreparationWork.id == after_work_id,
            PreparationWork.tenant_id == tenant_id,
            PreparationWork.location_id == location_id,
        ))
        if cursor is None:
            raise errors.PreparationNotFoundError('Preparation Work cursor not found')
        statement = statement.where(or_(
            PreparationWork.routed_at > cursor.routed_at,
            and_(PreparationWork.routed_at == cursor.routed_at, PreparationWork.id > cursor.id),
        ))
    works = tuple((await db.execute(
        statement.order_by(PreparationWork.routed_at, PreparationWork.id).limit(limit)
    )).scalars().all())
    return tuple([await _execution_work_projection(db, work) for work in works])


async def get_preparation_work(
    db: AsyncSession, *, tenant_id: int, work_id: int
) -> PreparationExecutionWorkProjection:
    work = await db.scalar(select(PreparationWork).where(
        PreparationWork.id == work_id,
        PreparationWork.tenant_id == tenant_id,
        PreparationWork.preparation_owner == 'PLATFORM',
    ))
    if work is None:
        raise errors.PreparationNotFoundError('Preparation Work not found')
    return await _execution_work_projection(db, work)


async def get_preparation_work_item(
    db: AsyncSession, *, tenant_id: int, item_id: int
) -> PreparationItemDetailProjection:
    item = await db.scalar(select(PreparationWorkItem).where(
        PreparationWorkItem.id == item_id,
        PreparationWorkItem.tenant_id == tenant_id,
    ))
    if item is None:
        raise errors.PreparationNotFoundError('Preparation Work Item not found')
    transitions = tuple((await db.execute(select(PreparationItemTransition).where(
        PreparationItemTransition.tenant_id == tenant_id,
        PreparationItemTransition.preparation_work_item_id == item.id,
    ).order_by(PreparationItemTransition.sequence, PreparationItemTransition.id))).scalars().all())
    return PreparationItemDetailProjection(
        item=await _execution_item_projection(db, item),
        transitions=tuple(_transition_projection(value) for value in transitions),
    )


async def transition_work_item(
    db: AsyncSession,
    *,
    item_id: int,
    expected_state: str,
    expected_version: int,
    to_state: str,
    idempotency_key: str,
    execution: ExecutionContext,
) -> PreparationTransitionResult:
    if execution.actor_type is not ActorType.EMPLOYEE:
        raise errors.PreparationTransitionError('This preparation endpoint requires an employee actor')
    try:
        item = await db.scalar(select(PreparationWorkItem).where(
            PreparationWorkItem.id == item_id,
            PreparationWorkItem.tenant_id == execution.tenant_id,
        ).with_for_update())
        if item is None:
            raise errors.PreparationNotFoundError('Preparation Work Item not found')
        work_and_routing = (await db.execute(
            select(PreparationWork, PreparationRouting)
            .join(PreparationRouting, and_(
                PreparationRouting.id == PreparationWork.routing_id,
                PreparationRouting.tenant_id == PreparationWork.tenant_id,
                PreparationRouting.restaurant_order_id == PreparationWork.restaurant_order_id,
            ))
            .where(
                PreparationWork.id == item.preparation_work_id,
                PreparationWork.tenant_id == item.tenant_id,
                PreparationWork.restaurant_order_id == item.restaurant_order_id,
            )
        )).first()
        if work_and_routing is None:
            raise errors.PreparationOwnershipError('Preparation Work is not executable')
        work, routing = work_and_routing
        if (
            work.preparation_owner != 'PLATFORM'
            or routing.preparation_owner != 'PLATFORM'
            or routing.state != 'ROUTED'
        ):
            raise errors.PreparationOwnershipError('Preparation Work is not platform-owned and routed')

        replay = await db.scalar(select(PreparationItemTransition).where(
            PreparationItemTransition.tenant_id == item.tenant_id,
            PreparationItemTransition.preparation_work_item_id == item.id,
            PreparationItemTransition.idempotency_key == idempotency_key,
        ))
        if replay is not None:
            if (
                replay.from_state != expected_state
                or replay.sequence - 1 != expected_version
                or replay.to_state != to_state
                or replay.actor_type != execution.actor_type.value
                or replay.actor_membership_id != execution.principal_id
                or replay.actor_principal_reference != execution.principal_reference
            ):
                raise errors.PreparationIdempotencyError('Idempotency key was used for a different preparation transition')
            await db.commit()
            return PreparationTransitionResult(
                transition=_transition_projection(replay),
                current_execution_state=item.execution_state,
                current_execution_version=item.execution_version,
                replayed=True,
            )

        if item.execution_state != expected_state or item.execution_version != expected_version:
            raise errors.PreparationStaleError(
                f'Expected {expected_state}/{expected_version}, current state is '
                f'{item.execution_state}/{item.execution_version}'
            )
        legal = {
            ('NEW', 'IN_PROGRESS'),
            ('IN_PROGRESS', 'COMPLETED'),
        }
        if (expected_state, to_state) not in legal:
            raise errors.PreparationTransitionError(
                f'Invalid preparation transition {expected_state} -> {to_state}'
            )
        next_version = item.execution_version + 1
        actor = {
            'actor_type': execution.actor_type.value,
            'actor_membership_id': execution.principal_id,
            'actor_principal_reference': execution.principal_reference,
        }
        transition = PreparationItemTransition(
            tenant_id=item.tenant_id,
            organization_id=item.organization_id,
            location_id=item.location_id,
            restaurant_order_id=item.restaurant_order_id,
            preparation_work_id=item.preparation_work_id,
            preparation_work_item_id=item.id,
            sequence=next_version,
            from_state=item.execution_state,
            to_state=to_state,
            correlation_id=execution.correlation_id,
            idempotency_key=idempotency_key,
            occurred_at=_now(),
            **actor,
        )
        db.add(transition)
        item.execution_state = to_state
        item.execution_version = next_version
        await db.flush()
        result = PreparationTransitionResult(
            transition=_transition_projection(transition),
            current_execution_state=item.execution_state,
            current_execution_version=item.execution_version,
            replayed=False,
        )
        await db.commit()
        return result
    except Exception:
        await db.rollback()
        raise
