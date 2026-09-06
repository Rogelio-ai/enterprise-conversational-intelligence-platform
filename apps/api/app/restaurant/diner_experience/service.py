from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DinerOperationalRequest, ProductCategory
from app.restaurant.catalog.resolution import is_product_orderable
from app.restaurant.checks import service as check_service
from app.restaurant.diner_experience.contracts import (
    AccountPreviewLine,
    DinerAccountPreview,
    DinerCategory,
    DinerChoiceGroup,
    DinerChoiceOption,
    DinerFixedComponent,
    DinerMenu,
    DinerMenuSection,
    DinerPrice,
    DinerProductDetail,
    DinerProductSummary,
    OperationalRequestIdempotencyConflictError,
    OperationalRequestInvalidError,
    OperationalRequestNotFoundError,
    OperationalRequestProjection,
    ProductUnavailableError,
)
from app.restaurant.intelligence.errors import KnowledgeNotFoundError
from app.restaurant.knowledge import service as knowledge
from app.restaurant.orders import acceptance


REQUEST_TYPES = {
    'HUMAN_ASSISTANCE',
    'CASH_PAYMENT_ASSISTANCE',
    'INVOICE_ASSISTANCE',
    'PAID_CHECK_PRINT',
}


async def _category_paths(
    db: AsyncSession, *, tenant_id: int, organization_id: int
) -> dict[int, tuple[DinerCategory, ...]]:
    rows = tuple(
        (
            await db.execute(
                select(ProductCategory)
                .where(
                    ProductCategory.tenant_id == tenant_id,
                    ProductCategory.organization_id == organization_id,
                    ProductCategory.status == 'ACTIVE',
                )
                .order_by(ProductCategory.id)
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}
    output: dict[int, tuple[DinerCategory, ...]] = {}
    for category in rows:
        path: list[DinerCategory] = []
        current = category
        seen: set[int] = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            path.append(DinerCategory(current.id, current.name))
            current = by_id.get(current.parent_id) if current.parent_id is not None else None
        output[category.id] = tuple(reversed(path))
    return output


async def _price(
    db: AsyncSession, *, tenant_id: int, location_id: int, product_id: int
) -> DinerPrice | None:
    try:
        value = await knowledge.get_current_price(
            db, tenant_id=tenant_id, product_id=product_id, location_id=location_id
        )
    except KnowledgeNotFoundError:
        return None
    return DinerPrice(value.amount, value.currency)


async def _composition(
    db: AsyncSession, *, tenant_id: int, organization_id: int, product_id: int
):
    try:
        return await knowledge.get_product_composition(
            db,
            tenant_id=tenant_id,
            organization_id=organization_id,
            product_id=product_id,
        )
    except KnowledgeNotFoundError:
        return None


async def get_menu(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
) -> tuple[DinerMenu, ...]:
    menus = await knowledge.get_location_menu(
        db,
        tenant_id=tenant_id,
        organization_id=organization_id,
        location_id=location_id,
    )
    paths = await _category_paths(
        db, tenant_id=tenant_id, organization_id=organization_id
    )
    product_cache: dict[int, DinerProductSummary] = {}
    for menu in menus:
        for section in menu.sections:
            for item in section.items:
                product = item.product
                if product.id in product_cache:
                    continue
                composition = await _composition(
                    db,
                    tenant_id=tenant_id,
                    organization_id=organization_id,
                    product_id=product.id,
                )
                product_cache[product.id] = DinerProductSummary(
                    id=product.id,
                    name=product.name,
                    description=product.description,
                    category_path=paths.get(product.category_id, ()),
                    price=await _price(
                        db,
                        tenant_id=tenant_id,
                        location_id=location_id,
                        product_id=product.id,
                    ),
                    orderable=True,
                    configuration_available=composition is not None,
                    configuration_required=(
                        composition is not None
                        and any(group.min_selections > 0 for group in composition.choice_groups)
                    ),
                )
    return tuple(
        DinerMenu(
            id=menu.id,
            name=menu.name,
            sections=tuple(
                DinerMenuSection(
                    id=section.id,
                    name=section.name,
                    products=tuple(product_cache[item.product.id] for item in section.items),
                )
                for section in menu.sections
            ),
        )
        for menu in menus
    )


async def get_product_detail(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
    product_id: int,
) -> DinerProductDetail:
    if not await is_product_orderable(
        db,
        tenant_id=tenant_id,
        organization_id=organization_id,
        location_id=location_id,
        product_id=product_id,
    ):
        raise ProductUnavailableError('Product is not available in the current diner location')
    product = await knowledge.get_product(
        db, tenant_id=tenant_id, organization_id=organization_id, product_id=product_id
    )
    composition = await _composition(
        db,
        tenant_id=tenant_id,
        organization_id=organization_id,
        product_id=product_id,
    )
    paths = await _category_paths(
        db, tenant_id=tenant_id, organization_id=organization_id
    )
    summary = DinerProductSummary(
        id=product.id,
        name=product.name,
        description=product.description,
        category_path=paths.get(product.category_id, ()),
        price=await _price(
            db, tenant_id=tenant_id, location_id=location_id, product_id=product.id
        ),
        orderable=True,
        configuration_available=composition is not None,
        configuration_required=(
            composition is not None
            and any(group.min_selections > 0 for group in composition.choice_groups)
        ),
    )
    if composition is None:
        return DinerProductDetail(summary, (), ())
    return DinerProductDetail(
        product=summary,
        fixed_components=tuple(
            DinerFixedComponent(value.product.id, value.product.name, value.quantity)
            for value in composition.fixed_components
        ),
        choice_groups=tuple(
            DinerChoiceGroup(
                id=group.group_id,
                name=group.name,
                min_selections=group.min_selections,
                max_selections=group.max_selections,
                required=group.min_selections > 0,
                options=tuple(
                    DinerChoiceOption(
                        option.option_id,
                        option.product.id,
                        option.product.name,
                        option.product.description,
                        option.quantity,
                    )
                    for option in group.options
                ),
            )
            for group in composition.choice_groups
        ),
    )


async def get_account_preview(
    db: AsyncSession, *, tenant_id: int, location_id: int, diner_session_id: int
) -> DinerAccountPreview:
    eligible = await check_service.eligible_consumption(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        owner_diner_session_id=diner_session_id,
    )
    own = next((value for value in eligible if value.diner_session_id == diner_session_id), None)
    if own is None:
        raise OperationalRequestNotFoundError('Diner account is not available')
    eligible_ids = set(own.eligible_order_ids)
    orders = await acceptance.list_diner_orders(
        db, tenant_id=tenant_id, diner_session_id=diner_session_id
    )
    lines = tuple(
        AccountPreviewLine(
            order_id=order.id,
            order_item_id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            commercial_amount=item.commercial_amount,
        )
        for order in orders
        if order.id in eligible_ids
        for item in order.items
    )
    return DinerAccountPreview(
        diner_session_id=own.diner_session_id,
        display_name=own.display_name,
        currency=own.currency,
        eligible_order_ids=own.eligible_order_ids,
        lines=lines,
        eligible_total=own.eligible_total,
        active_check_id=own.active_check_id,
        has_active_nonempty_draft=own.has_active_nonempty_draft,
    )


def _request_projection(value: DinerOperationalRequest) -> OperationalRequestProjection:
    return OperationalRequestProjection(
        value.id,
        value.request_type,
        value.status,
        value.related_restaurant_check_id,
        value.created_at,
        value.resolved_at,
    )


def _fingerprint(request_type: str, related_check_id: int | None) -> str:
    payload = json.dumps(
        {'request_type': request_type, 'related_restaurant_check_id': related_check_id},
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def create_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
    resource_id: int,
    service_session_id: int,
    diner_session_id: int,
    request_type: str,
    related_restaurant_check_id: int | None,
    idempotency_key: str,
    correlation_id: str | None,
) -> tuple[OperationalRequestProjection, bool]:
    if request_type not in REQUEST_TYPES:
        raise OperationalRequestInvalidError('Unsupported operational request type')
    check_required = request_type != 'HUMAN_ASSISTANCE'
    if check_required != (related_restaurant_check_id is not None):
        raise OperationalRequestInvalidError(
            'This operational request requires a related Restaurant Check'
            if check_required
            else 'Human assistance does not accept a related Restaurant Check'
        )
    if related_restaurant_check_id is not None:
        check = await check_service.get_check(
            db,
            tenant_id=tenant_id,
            check_id=related_restaurant_check_id,
            owner_diner_session_id=diner_session_id,
        )
        if check.organization_id != organization_id or check.location_id != location_id:
            raise OperationalRequestNotFoundError('Restaurant Check not found')
        if request_type in {'INVOICE_ASSISTANCE', 'PAID_CHECK_PRINT'} and check.status != 'SETTLED':
            raise OperationalRequestInvalidError('A settled Restaurant Check is required')
    fingerprint = _fingerprint(request_type, related_restaurant_check_id)
    existing = await db.scalar(
        select(DinerOperationalRequest).where(
            DinerOperationalRequest.tenant_id == tenant_id,
            DinerOperationalRequest.diner_session_id == diner_session_id,
            DinerOperationalRequest.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise OperationalRequestIdempotencyConflictError(
                'Idempotency key was already used for a different operational request'
            )
        return _request_projection(existing), True
    value = DinerOperationalRequest(
        tenant_id=tenant_id,
        organization_id=organization_id,
        location_id=location_id,
        resource_id=resource_id,
        service_session_id=service_session_id,
        diner_session_id=diner_session_id,
        request_type=request_type,
        status='PENDING',
        related_restaurant_check_id=related_restaurant_check_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        correlation_id=correlation_id,
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(DinerOperationalRequest).where(
                DinerOperationalRequest.tenant_id == tenant_id,
                DinerOperationalRequest.diner_session_id == diner_session_id,
                DinerOperationalRequest.idempotency_key == idempotency_key,
            )
        )
        if existing is None or existing.request_fingerprint != fingerprint:
            raise OperationalRequestIdempotencyConflictError(
                'Operational request could not be created idempotently'
            )
        return _request_projection(existing), True
    await db.refresh(value)
    return _request_projection(value), False


async def get_operational_request(
    db: AsyncSession, *, tenant_id: int, diner_session_id: int, request_id: int
) -> OperationalRequestProjection:
    value = await db.scalar(
        select(DinerOperationalRequest).where(
            DinerOperationalRequest.id == request_id,
            DinerOperationalRequest.tenant_id == tenant_id,
            DinerOperationalRequest.diner_session_id == diner_session_id,
        )
    )
    if value is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    return _request_projection(value)
