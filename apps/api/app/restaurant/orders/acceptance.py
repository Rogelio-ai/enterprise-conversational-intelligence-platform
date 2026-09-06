from __future__ import annotations

import hmac
import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Location,
    OrderDraft,
    Product,
    RestaurantOrder,
    RestaurantOrderItem,
    RestaurantOrderItemComponent,
    RestaurantOrderItemFiscalSnapshot,
    RestaurantOrderItemTaxSnapshot,
    RestaurantOrderPromotion,
)
from app.restaurant.catalog import structure
from app.restaurant.commercial import service as commercial_service
from app.restaurant.fiscal_product import service as fiscal_product_service
from app.restaurant.fiscal_product.contracts import FiscalProductClassificationCandidate
from app.restaurant.fiscal_product.errors import FiscalProductEvidenceError
from app.restaurant.orders import acceptance_errors as errors
from app.restaurant.orders import service as draft_service
from app.restaurant.orders.acceptance_contracts import (
    AcceptedComponent,
    AcceptedOrderItem,
    AcceptedPromotion,
    ConfirmationResult,
    RestaurantOrderProjection,
)
from app.restaurant.inventory import order_consumption
from app.restaurant.service_sessions import service as service_session_service
from app.restaurant.tax import service as tax_service
from app.restaurant.tax.contracts import RestaurantTaxLineCandidate
from app.restaurant.tax.errors import RestaurantTaxError


logger = logging.getLogger('ecip.restaurant_orders')
ACCEPTED_FINGERPRINT_SCHEMA_VERSION = 3


def _accepted_fingerprint(
    commercial_fingerprint: str,
    tax_evidence: tuple[tuple[int, str], ...],
    fiscal_product_evidence: tuple[tuple[int, str], ...],
) -> str:
    value = {
        'fingerprint_schema_version': ACCEPTED_FINGERPRINT_SCHEMA_VERSION,
        'commercial_fingerprint': commercial_fingerprint,
        'tax_evidence': [
            {'draft_item_id': item_id, 'evidence_fingerprint': fingerprint}
            for item_id, fingerprint in tax_evidence
        ],
        'fiscal_product_evidence': [
            {'draft_item_id': item_id, 'evidence_fingerprint': fingerprint}
            for item_id, fingerprint in fiscal_product_evidence
        ],
    }
    encoded = json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _event(name: str, *, correlation_id: str | None, **values: object) -> None:
    logger.info(
        name.replace('_', ' ').capitalize(),
        extra={'event': name, 'correlation_id': correlation_id, **values},
    )


async def _projection(db: AsyncSession, order: RestaurantOrder) -> RestaurantOrderProjection:
    item_rows = tuple(
        (
            await db.execute(
                select(RestaurantOrderItem)
                .where(
                    RestaurantOrderItem.tenant_id == order.tenant_id,
                    RestaurantOrderItem.order_id == order.id,
                )
                .order_by(RestaurantOrderItem.position, RestaurantOrderItem.id)
            )
        )
        .scalars()
        .all()
    )
    projected_items: list[AcceptedOrderItem] = []
    for item in item_rows:
        component_rows = tuple(
            (
                await db.execute(
                    select(RestaurantOrderItemComponent)
                    .where(
                        RestaurantOrderItemComponent.tenant_id == order.tenant_id,
                        RestaurantOrderItemComponent.order_id == order.id,
                        RestaurantOrderItemComponent.order_item_id == item.id,
                    )
                    .order_by(RestaurantOrderItemComponent.position, RestaurantOrderItemComponent.id)
                )
            )
            .scalars()
            .all()
        )
        promotion_rows = tuple(
            (
                await db.execute(
                    select(RestaurantOrderPromotion)
                    .where(
                        RestaurantOrderPromotion.tenant_id == order.tenant_id,
                        RestaurantOrderPromotion.order_id == order.id,
                        RestaurantOrderPromotion.order_item_id == item.id,
                    )
                    .order_by(RestaurantOrderPromotion.application_order, RestaurantOrderPromotion.id)
                )
            )
            .scalars()
            .all()
        )
        projected_items.append(
            AcceptedOrderItem(
                id=item.id,
                source_order_draft_item_id=item.source_order_draft_item_id,
                product_id=item.product_id,
                product_name=item.product_name,
                composition_id=item.composition_id,
                quantity=item.quantity,
                position=item.position,
                source_product_price_id=item.source_product_price_id,
                price_source=item.price_source,
                unit_price=item.unit_price,
                base_amount=item.base_amount,
                discount_amount=item.discount_amount,
                commercial_amount=item.commercial_amount,
                components=tuple(
                    AcceptedComponent(
                        kind=value.kind,
                        position=value.position,
                        source_component_id=value.source_component_id,
                        source_choice_group_id=value.source_choice_group_id,
                        source_choice_option_id=value.source_choice_option_id,
                        choice_group_name=value.choice_group_name,
                        product_id=value.product_id,
                        product_name=value.product_name,
                        quantity=value.quantity,
                    )
                    for value in component_rows
                ),
                promotions=tuple(
                    AcceptedPromotion(
                        promotion_id=value.promotion_id,
                        application_order=value.application_order,
                        promotion_name=value.promotion_name,
                        promotion_type=value.promotion_type,
                        promotion_value=value.promotion_value,
                        promotion_currency=value.promotion_currency,
                        priority=value.priority,
                        is_combinable=value.is_combinable,
                        calculated_discount=value.calculated_discount,
                    )
                    for value in promotion_rows
                ),
            )
        )
    return RestaurantOrderProjection(
        id=order.id,
        status=order.status,
        accepted_at=order.accepted_at,
        source_order_draft_id=order.source_order_draft_id,
        accepted_draft_version=order.accepted_draft_version,
        currency=order.currency,
        tax_mode=order.tax_mode,
        rounding_policy=order.rounding_policy,
        subtotal=order.subtotal,
        total_discount=order.total_discount,
        pre_round_total=order.pre_round_total,
        rounding_adjustment=order.rounding_adjustment,
        payable_total=order.payable_total,
        items=tuple(projected_items),
    )


async def _order_by_key(
    db: AsyncSession, *, tenant_id: int, diner_session_id: int, idempotency_key: str
) -> RestaurantOrder | None:
    return await db.scalar(
        select(RestaurantOrder)
        .where(
            RestaurantOrder.tenant_id == tenant_id,
            RestaurantOrder.diner_session_id == diner_session_id,
            RestaurantOrder.confirmation_idempotency_key == idempotency_key,
        )
        .with_for_update()
    )


async def confirm_current_order(
    db: AsyncSession,
    *,
    tenant_id: int,
    diner_session_id: int,
    conversation_id: int,
    expected_draft_version: int,
    expected_commercial_fingerprint: str,
    idempotency_key: str,
    correlation_id: str | None = None,
) -> ConfirmationResult:
    _event('order_confirmation_requested', correlation_id=correlation_id, tenant_id=tenant_id, diner_session_id=diner_session_id, conversation_id=conversation_id)
    try:
        session, diner, conversation = await service_session_service.lock_diner_write_context(
            db,
            tenant_id=tenant_id,
            diner_session_id=diner_session_id,
            conversation_id=conversation_id,
        )
        draft = await db.scalar(
            select(OrderDraft)
            .where(
                OrderDraft.tenant_id == tenant_id,
                OrderDraft.conversation_id == conversation_id,
                OrderDraft.status == 'OPEN',
                OrderDraft.current_slot == 1,
            )
            .with_for_update()
        )
        replay = await _order_by_key(
            db,
            tenant_id=tenant_id,
            diner_session_id=diner_session_id,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            if draft is not None and replay.source_order_draft_id != draft.id:
                raise errors.ConfirmationConflictError(
                    'Idempotency key was already used for a different Order Draft'
                )
            await db.commit()
            _event('order_confirmation_idempotent_replay', correlation_id=correlation_id, tenant_id=tenant_id, diner_session_id=diner_session_id, conversation_id=conversation_id, restaurant_order_id=replay.id, outcome='replayed')
            return ConfirmationResult(await _projection(db, replay), True)
        if draft is None:
            raise errors.DraftNotConfirmableError('No current Order Draft is available to confirm')
        if draft.version != expected_draft_version:
            raise errors.ConfirmationStaleError(
                f'Expected Draft version {expected_draft_version}, current version is {draft.version}'
            )
        preview = await commercial_service.resolve_checkout_preview(
            db,
            tenant_id=tenant_id,
            draft_id=draft.id,
            correlation_id=correlation_id,
        )
        if not hmac.compare_digest(
            preview.commercial_fingerprint, expected_commercial_fingerprint
        ):
            raise errors.ConfirmationStaleError('Commercial confirmation expectation is stale')

        accepted_at = datetime.now(UTC).replace(tzinfo=None)
        location = await db.scalar(
            select(Location).where(
                Location.id == diner.location_id,
                Location.tenant_id == tenant_id,
                Location.organization_id == diner.organization_id,
            ).with_for_update()
        )
        if location is None or location.country_code is None:
            raise errors.FiscalProductEvidenceUnavailableError(
                'Fiscal product jurisdiction is unavailable for this Location'
            )
        draft_projection = await draft_service.evaluate_draft(
            db, tenant_id=tenant_id, draft_id=draft.id, correlation_id=correlation_id
        )
        draft_items = {value.item_id: value for value in draft_projection.items}
        resolved_lines = []
        try:
            for line in preview.lines:
                draft_item = draft_items[line.draft_item_id]
                product = await db.scalar(
                    select(Product)
                    .where(
                        Product.id == line.product_id,
                        Product.tenant_id == tenant_id,
                        Product.organization_id == diner.organization_id,
                    )
                    .with_for_update()
                )
                if product is None:
                    raise errors.TaxEvidenceUnavailableError(
                        'Authoritative Product tax scope is unavailable'
                    )
                graph = None
                component_classifications: tuple[str | None, ...] = ()
                if line.composition_id is not None:
                    graph = await structure.load_composition_graph(
                        db, tenant_id=tenant_id, product_id=line.product_id, active_only=True
                    )
                    if graph is None or graph.composition.id != line.composition_id:
                        raise errors.DraftNotConfirmableError(
                            'Product composition is no longer valid'
                        )
                    selections = {value.choice_option_id for value in draft_item.selections}
                    component_classifications = tuple(
                        [value.product.tax_classification_code for value in graph.components]
                        + [
                            option.product.tax_classification_code
                            for group in graph.groups
                            for option in group.options
                            if option.option.id in selections
                        ]
                    )
                evidence = await tax_service.resolve_tax_evidence(
                    db,
                    RestaurantTaxLineCandidate(
                        tenant_id=tenant_id,
                        organization_id=diner.organization_id,
                        location_id=diner.location_id,
                        product_id=line.product_id,
                        product_tax_classification_code=product.tax_classification_code,
                        effective_at=accepted_at,
                        tax_mode=preview.tax_mode.value,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        base_amount=line.base_amount,
                        discount_amount=line.discount_amount,
                        commercial_amount=line.commercial_amount,
                        component_tax_classification_codes=component_classifications,
                    ),
                )
                fiscal_product_evidence = (
                    await fiscal_product_service.resolve_fiscal_product_evidence(
                        db,
                        FiscalProductClassificationCandidate(
                            tenant_id=tenant_id,
                            organization_id=diner.organization_id,
                            product_id=line.product_id,
                            fiscal_jurisdiction_code=location.country_code,
                            effective_at=accepted_at,
                        ),
                    )
                )
                resolved_lines.append(
                    (line, draft_item, graph, evidence, fiscal_product_evidence)
                )
        except RestaurantTaxError as exc:
            raise errors.TaxEvidenceUnavailableError(
                'Authoritative tax evidence is unavailable for order acceptance'
            ) from exc
        except FiscalProductEvidenceError as exc:
            raise errors.FiscalProductEvidenceUnavailableError(
                'Authoritative fiscal product evidence is unavailable for order acceptance'
            ) from exc

        accepted_fingerprint = _accepted_fingerprint(
            preview.commercial_fingerprint,
            tuple(
                (line.draft_item_id, evidence.evidence_fingerprint)
                for line, _, _, evidence, _ in resolved_lines
            ),
            tuple(
                (line.draft_item_id, evidence.evidence_fingerprint)
                for line, _, _, _, evidence in resolved_lines
            ),
        )
        order = RestaurantOrder(
            tenant_id=tenant_id,
            organization_id=diner.organization_id,
            location_id=diner.location_id,
            resource_id=diner.resource_id,
            service_session_id=session.id,
            diner_session_id=diner.id,
            customer_id=diner.customer_id,
            conversation_id=conversation.id,
            source_order_draft_id=draft.id,
            source_channel=conversation.channel,
            status='ACCEPTED',
            accepted_draft_version=draft.version,
            confirmation_idempotency_key=idempotency_key,
            commercial_fingerprint=accepted_fingerprint,
            fingerprint_schema_version=ACCEPTED_FINGERPRINT_SCHEMA_VERSION,
            currency=preview.currency,
            tax_mode=preview.tax_mode.value,
            rounding_policy=preview.rounding_policy,
            subtotal=preview.subtotal,
            total_discount=preview.total_discount,
            pre_round_total=preview.pre_round_total,
            rounding_adjustment=preview.rounding_adjustment,
            payable_total=preview.payable_total,
            accepted_at=accepted_at,
        )
        db.add(order)
        await db.flush()
        for line, draft_item, graph, tax_evidence, fiscal_product_evidence in resolved_lines:
            order_item = RestaurantOrderItem(
                tenant_id=tenant_id,
                organization_id=diner.organization_id,
                order_id=order.id,
                source_order_draft_item_id=line.draft_item_id,
                product_id=line.product_id,
                product_name=line.product_name,
                composition_id=line.composition_id,
                quantity=line.quantity,
                position=draft_item.position,
                source_product_price_id=line.price_id,
                price_source=line.price_source,
                unit_price=line.unit_price,
                base_amount=line.base_amount,
                discount_amount=line.discount_amount,
                commercial_amount=line.commercial_amount,
            )
            db.add(order_item)
            await db.flush()
            component_position = 0
            if graph is not None:
                for component in graph.components:
                    db.add(RestaurantOrderItemComponent(
                        tenant_id=tenant_id, organization_id=diner.organization_id,
                        order_id=order.id, order_item_id=order_item.id, kind='FIXED',
                        position=component_position, source_component_id=component.component.id,
                        source_choice_group_id=None, source_choice_option_id=None,
                        choice_group_name=None, product_id=component.product.id,
                        product_name=component.product.name, quantity=component.component.quantity,
                    ))
                    component_position += 1
                selections = {value.choice_option_id for value in draft_item.selections}
                for group in graph.groups:
                    for option in group.options:
                        if option.option.id not in selections:
                            continue
                        db.add(RestaurantOrderItemComponent(
                            tenant_id=tenant_id, organization_id=diner.organization_id,
                            order_id=order.id, order_item_id=order_item.id, kind='CHOICE',
                            position=component_position, source_component_id=None,
                            source_choice_group_id=group.group.id,
                            source_choice_option_id=option.option.id,
                            choice_group_name=group.group.name,
                            product_id=option.product.id, product_name=option.product.name,
                            quantity=option.option.quantity,
                        ))
                        component_position += 1
            for application_order, promotion in enumerate(line.applied_promotions):
                db.add(RestaurantOrderPromotion(
                    tenant_id=tenant_id, organization_id=diner.organization_id,
                    order_id=order.id, order_item_id=order_item.id,
                    promotion_id=promotion.promotion_id,
                    application_order=application_order,
                    promotion_name=promotion.name,
                    promotion_type=promotion.promotion_type,
                    promotion_value=promotion.promotion_value,
                    promotion_currency=promotion.currency,
                    priority=promotion.priority,
                    is_combinable=promotion.is_combinable,
                    calculated_discount=promotion.calculated_discount,
                ))
            db.add(
                RestaurantOrderItemTaxSnapshot(
                    tenant_id=tenant_id,
                    organization_id=diner.organization_id,
                    location_id=diner.location_id,
                    restaurant_order_id=order.id,
                    restaurant_order_item_id=order_item.id,
                    source_tax_rule_id=tax_evidence.source_tax_rule_id,
                    tax_category=tax_evidence.tax_category,
                    tax_treatment=tax_evidence.tax_treatment.value,
                    tax_effect=tax_evidence.tax_effect.value,
                    tax_rate=tax_evidence.tax_rate,
                    fiscal_unit_value=tax_evidence.fiscal_unit_value,
                    fiscal_line_amount=tax_evidence.fiscal_line_amount,
                    fiscal_discount_amount=tax_evidence.fiscal_discount_amount,
                    taxable_base=tax_evidence.taxable_base,
                    tax_amount=tax_evidence.tax_amount,
                    jurisdiction_code=tax_evidence.jurisdiction_code,
                    calculation_policy=tax_evidence.calculation_policy,
                    rounding_policy=tax_evidence.rounding_policy,
                    schema_version=tax_evidence.schema_version,
                    evidence_fingerprint=tax_evidence.evidence_fingerprint,
                    created_at=accepted_at,
                )
            )
            db.add(
                RestaurantOrderItemFiscalSnapshot(
                    tenant_id=tenant_id,
                    organization_id=diner.organization_id,
                    location_id=diner.location_id,
                    restaurant_order_id=order.id,
                    restaurant_order_item_id=order_item.id,
                    source_product_fiscal_classification_id=(
                        fiscal_product_evidence.source_product_fiscal_classification_id
                    ),
                    fiscal_jurisdiction_code=(
                        fiscal_product_evidence.fiscal_jurisdiction_code
                    ),
                    product_classification_scheme=(
                        fiscal_product_evidence.product_classification_scheme
                    ),
                    product_classification_code=(
                        fiscal_product_evidence.product_classification_code
                    ),
                    unit_classification_scheme=(
                        fiscal_product_evidence.unit_classification_scheme
                    ),
                    unit_classification_code=(
                        fiscal_product_evidence.unit_classification_code
                    ),
                    schema_version=fiscal_product_evidence.schema_version,
                    evidence_fingerprint=fiscal_product_evidence.evidence_fingerprint,
                    created_at=accepted_at,
                )
            )
        draft.status = 'ACCEPTED'
        draft.current_slot = None
        draft.terminal_at = accepted_at
        await db.flush()
        await order_consumption.materialize_accepted_order(db, order=order)
        await db.commit()
        await db.refresh(order)
    except Exception as exc:
        await db.rollback()
        if isinstance(exc, errors.ConfirmationStaleError):
            _event('order_confirmation_stale', correlation_id=correlation_id, tenant_id=tenant_id, diner_session_id=diner_session_id, conversation_id=conversation_id, outcome='rejected')
        else:
            _event('order_confirmation_rejected', correlation_id=correlation_id, tenant_id=tenant_id, diner_session_id=diner_session_id, conversation_id=conversation_id, outcome='rejected')
        raise
    _event('order_confirmed', correlation_id=correlation_id, tenant_id=tenant_id, organization_id=order.organization_id, location_id=order.location_id, resource_id=order.resource_id, service_session_id=order.service_session_id, diner_session_id=order.diner_session_id, conversation_id=order.conversation_id, order_draft_id=order.source_order_draft_id, restaurant_order_id=order.id, draft_version=order.accepted_draft_version, outcome='accepted')
    return ConfirmationResult(await _projection(db, order), False)


async def list_diner_orders(
    db: AsyncSession, *, tenant_id: int, diner_session_id: int
) -> tuple[RestaurantOrderProjection, ...]:
    orders = tuple(
        (
            await db.execute(
                select(RestaurantOrder)
                .where(
                    RestaurantOrder.tenant_id == tenant_id,
                    RestaurantOrder.diner_session_id == diner_session_id,
                )
                .order_by(RestaurantOrder.accepted_at, RestaurantOrder.id)
            )
        )
        .scalars()
        .all()
    )
    return tuple([await _projection(db, value) for value in orders])


async def get_diner_order(
    db: AsyncSession, *, tenant_id: int, diner_session_id: int, order_id: int
) -> RestaurantOrderProjection:
    order = await db.scalar(
        select(RestaurantOrder).where(
            RestaurantOrder.id == order_id,
            RestaurantOrder.tenant_id == tenant_id,
            RestaurantOrder.diner_session_id == diner_session_id,
        )
    )
    if order is None:
        raise errors.RestaurantOrderNotFoundError('Restaurant Order not found')
    return await _projection(db, order)


async def list_staff_orders(
    db: AsyncSession, *, tenant_id: int
) -> tuple[RestaurantOrderProjection, ...]:
    orders = tuple(
        (
            await db.execute(
                select(RestaurantOrder)
                .where(RestaurantOrder.tenant_id == tenant_id)
                .order_by(RestaurantOrder.accepted_at, RestaurantOrder.id)
            )
        )
        .scalars()
        .all()
    )
    return tuple([await _projection(db, value) for value in orders])


async def get_staff_order(
    db: AsyncSession, *, tenant_id: int, order_id: int
) -> RestaurantOrderProjection:
    order = await db.scalar(
        select(RestaurantOrder).where(
            RestaurantOrder.id == order_id, RestaurantOrder.tenant_id == tenant_id
        )
    )
    if order is None:
        raise errors.RestaurantOrderNotFoundError('Restaurant Order not found')
    return await _projection(db, order)
