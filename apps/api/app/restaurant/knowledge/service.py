from __future__ import annotations

from datetime import UTC, datetime
from functools import wraps

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Menu, Organization, Product
from app.restaurant.catalog.queries import (
    load_menu_graph,
    menu_statement,
    product_statement,
)
from app.restaurant.catalog.structure import load_composition_graph
from app.restaurant.intelligence.errors import KnowledgeNotFoundError, KnowledgeUnavailableError
from app.restaurant.knowledge.contracts import (
    ChoiceGroupKnowledge,
    ChoiceOptionKnowledge,
    CurrentPriceKnowledge,
    FixedComponentKnowledge,
    LocationMenuKnowledge,
    MenuItemKnowledge,
    MenuSectionKnowledge,
    ProductKnowledge,
    ProductCompositionKnowledge,
    PromotionCandidateKnowledge,
)
from app.restaurant.pricing import service as pricing_service


def _stable_knowledge_errors(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except (KnowledgeNotFoundError, ValueError):
            raise
        except SQLAlchemyError as exc:
            raise KnowledgeUnavailableError('Restaurant knowledge is unavailable') from exc

    return wrapped


def _product(value: Product) -> ProductKnowledge:
    return ProductKnowledge(
        id=value.id,
        organization_id=value.organization_id,
        category_id=value.category_id,
        name=value.name,
        description=value.description,
    )


async def _require_organization(
    db: AsyncSession, *, tenant_id: int, organization_id: int
) -> Organization:
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == tenant_id,
        )
    )
    if organization is None:
        raise KnowledgeNotFoundError('Organization not found')
    return organization


async def _require_location(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
) -> Location:
    location = await db.scalar(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
            Location.organization_id == organization_id,
        )
    )
    if location is None:
        raise KnowledgeNotFoundError('Location not found')
    return location


@_stable_knowledge_errors
async def get_location_menu(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
) -> tuple[LocationMenuKnowledge, ...]:
    await _require_organization(db, tenant_id=tenant_id, organization_id=organization_id)
    await _require_location(
        db,
        tenant_id=tenant_id,
        organization_id=organization_id,
        location_id=location_id,
    )
    menu_result = await db.execute(
        menu_statement(
            tenant_id=tenant_id,
            organization_id=organization_id,
            location_id=location_id,
            status='ACTIVE',
            active_location_assignment_only=True,
        ).order_by(Menu.id)
    )
    output: list[LocationMenuKnowledge] = []
    for menu in menu_result.scalars().all():
        graph = await load_menu_graph(
            db, tenant_id=tenant_id, menu_id=menu.id, active_only=True
        )
        if graph is None:
            continue
        output.append(
            LocationMenuKnowledge(
                id=graph.menu.id,
                organization_id=graph.menu.organization_id,
                name=graph.menu.name,
                location_ids=tuple(location.location_id for location in graph.locations),
                sections=tuple(
                    MenuSectionKnowledge(
                        id=section.section.id,
                        name=section.section.name,
                        display_order=section.section.display_order,
                        items=tuple(
                            MenuItemKnowledge(
                                id=item.id,
                                display_order=item.display_order,
                                product=_product(product),
                            )
                            for item, product in section.items
                        ),
                    )
                    for section in graph.sections
                ),
            )
        )
    return tuple(output)


@_stable_knowledge_errors
async def find_products(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    query_text: str | None = None,
    menu_id: int | None = None,
    limit: int = 50,
) -> tuple[ProductKnowledge, ...]:
    if not 1 <= limit <= 100:
        raise ValueError('Product knowledge limit must be between 1 and 100')
    await _require_organization(db, tenant_id=tenant_id, organization_id=organization_id)
    normalized_query = query_text.strip() if query_text is not None else None
    if query_text is not None and not normalized_query:
        raise ValueError('Product search text cannot be blank')
    if menu_id is not None:
        menu = await db.scalar(
            select(Menu).where(
                Menu.id == menu_id,
                Menu.tenant_id == tenant_id,
                Menu.organization_id == organization_id,
                Menu.status == 'ACTIVE',
            )
        )
        if menu is None:
            raise KnowledgeNotFoundError('Menu not found')
    result = await db.execute(
        product_statement(
            tenant_id=tenant_id,
            organization_id=organization_id,
            status='ACTIVE',
            menu_id=menu_id,
            query_text=normalized_query,
            active_menu_items_only=True,
        )
        .distinct()
        .order_by(Product.id)
        .limit(limit)
    )
    return tuple(_product(product) for product in result.scalars().all())


@_stable_knowledge_errors
async def get_product(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    product_id: int,
) -> ProductKnowledge:
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.organization_id == organization_id,
            Product.status == 'ACTIVE',
        )
    )
    if product is None:
        raise KnowledgeNotFoundError('Product not found')
    return _product(product)


@_stable_knowledge_errors
async def get_product_composition(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    product_id: int,
) -> ProductCompositionKnowledge:
    await _require_organization(db, tenant_id=tenant_id, organization_id=organization_id)
    graph = await load_composition_graph(
        db,
        tenant_id=tenant_id,
        product_id=product_id,
        active_only=True,
    )
    if graph is None or graph.composition.organization_id != organization_id:
        raise KnowledgeNotFoundError('Active Product Composition not found')
    return ProductCompositionKnowledge(
        composition_id=graph.composition.id,
        product=_product(graph.product),
        fixed_components=tuple(
            FixedComponentKnowledge(
                component_id=record.component.id,
                product=_product(record.product),
                quantity=record.component.quantity,
                display_order=record.component.display_order,
            )
            for record in graph.components
        ),
        choice_groups=tuple(
            ChoiceGroupKnowledge(
                group_id=record.group.id,
                name=record.group.name,
                min_selections=record.group.min_selections,
                max_selections=record.group.max_selections,
                display_order=record.group.display_order,
                options=tuple(
                    ChoiceOptionKnowledge(
                        option_id=option.option.id,
                        product=_product(option.product),
                        quantity=option.option.quantity,
                        display_order=option.option.display_order,
                    )
                    for option in record.options
                ),
            )
            for record in graph.groups
        ),
    )


@_stable_knowledge_errors
async def get_current_price(
    db: AsyncSession,
    *,
    tenant_id: int,
    product_id: int,
    location_id: int,
) -> CurrentPriceKnowledge:
    try:
        price = await pricing_service.get_canonical_current_price(
            db,
            tenant_id=tenant_id,
            product_id=product_id,
            location_id=location_id,
        )
    except pricing_service.PricingReadContextError as exc:
        raise KnowledgeNotFoundError(str(exc)) from exc
    if price is None:
        raise KnowledgeNotFoundError('Current Price not found')
    return CurrentPriceKnowledge(
        price_id=price.id,
        product_id=price.product_id,
        location_id=price.location_id,
        amount=price.amount,
        currency=price.currency,
        source=price.source,
        updated_at=price.updated_at,
    )


@_stable_knowledge_errors
async def find_applicable_promotions(
    db: AsyncSession,
    *,
    tenant_id: int,
    product_id: int,
    location_id: int,
    effective_at: datetime,
) -> tuple[PromotionCandidateKnowledge, ...]:
    if effective_at.tzinfo is None or effective_at.utcoffset() is None:
        raise ValueError('effective_at must be timezone-aware')
    canonical_time = effective_at.astimezone(UTC).replace(tzinfo=None)
    try:
        promotions = await pricing_service.find_canonical_applicable_promotions(
            db,
            tenant_id=tenant_id,
            product_id=product_id,
            location_id=location_id,
            effective_at=canonical_time,
        )
    except pricing_service.PricingReadContextError as exc:
        raise KnowledgeNotFoundError(str(exc)) from exc
    return tuple(
        PromotionCandidateKnowledge(
            promotion_id=promotion.id,
            name=promotion.name,
            description=promotion.description,
            promotion_type=promotion.promotion_type,
            benefit_value=promotion.benefit_value,
            currency=promotion.currency,
            starts_at=promotion.starts_at,
            ends_at=promotion.ends_at,
            applies_to_all_locations=promotion.applies_to_all_locations,
        )
        for promotion in promotions
    )
