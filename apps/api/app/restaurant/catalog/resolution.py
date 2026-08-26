from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Location,
    Menu,
    MenuItem,
    MenuLocation,
    MenuSection,
    Organization,
    Product,
    ProductAlias,
)
from app.restaurant.catalog import structure
from app.restaurant.catalog.resolution_contracts import (
    ChoiceResolutionCandidate,
    ChoiceResolutionRequest,
    ChoiceResolutionResult,
    MatchSource,
    ProductResolutionCandidate,
    ProductResolutionRequest,
    ProductResolutionResult,
    ResolutionStatus,
)


logger = logging.getLogger('ecip.product_resolution')
_LANGUAGE_TAG = re.compile(r'^[A-Za-z0-9]{1,8}(?:-[A-Za-z0-9]{1,8})*$')


def normalize_reference(value: str) -> str:
    """Return the one canonical exact-match representation used by WS-13."""
    return ' '.join(unicodedata.normalize('NFKC', value).split()).casefold()


def validate_language_tag(value: str | None) -> bool:
    return value is None or (
        len(value) <= 63
        and value.isascii()
        and _LANGUAGE_TAG.fullmatch(value) is not None
    )


def normalize_alias(value: str) -> str:
    normalized = normalize_reference(value)
    if not normalized:
        raise ValueError('Alias cannot be empty after normalization')
    if len(normalized) > 400:
        raise ValueError('Normalized alias cannot exceed 400 characters')
    return normalized


async def _scope_is_valid(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int | None = None,
) -> bool:
    if tenant_id <= 0 or organization_id <= 0:
        return False
    organization = await db.scalar(
        select(Organization.id).where(
            Organization.id == organization_id,
            Organization.tenant_id == tenant_id,
            Organization.status == 'ACTIVE',
        )
    )
    if organization is None:
        return False
    if location_id is None or location_id <= 0:
        return location_id is None
    location = await db.scalar(
        select(Location.id).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
            Location.organization_id == organization_id,
            Location.status == 'ACTIVE',
        )
    )
    return location is not None


async def _match_products(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    normalized_reference: str,
    language: str | None,
    products: Iterable[Product] | None = None,
) -> dict[int, tuple[Product, MatchSource]]:
    if products is None:
        product_rows = tuple(
            (
                await db.execute(
                    select(Product)
                    .where(
                        Product.tenant_id == tenant_id,
                        Product.organization_id == organization_id,
                    )
                    .order_by(Product.id)
                )
            )
            .scalars()
            .all()
        )
    else:
        product_rows = tuple(products)
    by_id = {product.id: product for product in product_rows}
    matched: dict[int, tuple[Product, MatchSource]] = {
        product.id: (product, MatchSource.CANONICAL_NAME)
        for product in product_rows
        if normalize_reference(product.name) == normalized_reference
    }
    if not by_id:
        return matched
    alias_query = select(ProductAlias).where(
        ProductAlias.tenant_id == tenant_id,
        ProductAlias.organization_id == organization_id,
        ProductAlias.product_id.in_(tuple(by_id)),
        ProductAlias.normalized_alias == normalized_reference,
        ProductAlias.status == 'ACTIVE',
    )
    if language is None:
        alias_query = alias_query.where(ProductAlias.language == '')
    else:
        alias_query = alias_query.where(ProductAlias.language.in_(('', language)))
    aliases = tuple((await db.execute(alias_query.order_by(ProductAlias.id))).scalars().all())
    for alias in aliases:
        if alias.product_id not in matched:
            matched[alias.product_id] = (by_id[alias.product_id], MatchSource.ALIAS)
    return matched


async def _orderable_product_ids(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int,
    product_ids: tuple[int, ...],
) -> set[int]:
    if not product_ids:
        return set()
    result = await db.execute(
        select(Product.id)
        .join(
            MenuItem,
            (MenuItem.product_id == Product.id)
            & (MenuItem.tenant_id == Product.tenant_id)
            & (MenuItem.organization_id == Product.organization_id),
        )
        .join(
            MenuSection,
            (MenuSection.id == MenuItem.section_id)
            & (MenuSection.menu_id == MenuItem.menu_id)
            & (MenuSection.tenant_id == MenuItem.tenant_id)
            & (MenuSection.organization_id == MenuItem.organization_id),
        )
        .join(
            Menu,
            (Menu.id == MenuItem.menu_id)
            & (Menu.tenant_id == MenuItem.tenant_id)
            & (Menu.organization_id == MenuItem.organization_id),
        )
        .join(
            MenuLocation,
            (MenuLocation.menu_id == Menu.id)
            & (MenuLocation.tenant_id == Menu.tenant_id)
            & (MenuLocation.organization_id == Menu.organization_id),
        )
        .where(
            Product.tenant_id == tenant_id,
            Product.organization_id == organization_id,
            Product.id.in_(product_ids),
            Product.status == 'ACTIVE',
            MenuItem.status == 'ACTIVE',
            MenuSection.status == 'ACTIVE',
            Menu.status == 'ACTIVE',
            MenuLocation.status == 'ACTIVE',
            MenuLocation.location_id == location_id,
        )
        .distinct()
    )
    return set(result.scalars().all())


def _log_product_outcome(
    request: ProductResolutionRequest, result: ProductResolutionResult
) -> None:
    logger.info(
        'Product resolution completed',
        extra={
            'event': f'product_resolution_{result.status.value.lower()}',
            'tenant_id': request.tenant_id,
            'organization_id': request.organization_id,
            'location_id': request.location_id,
            'product_id': result.candidate.product_id if result.candidate else None,
            'candidate_count': len(result.candidates) or (1 if result.candidate else 0),
            'language': request.language,
            'outcome': result.status.value,
        },
    )


async def resolve_product(
    db: AsyncSession, request: ProductResolutionRequest
) -> ProductResolutionResult:
    normalized = normalize_reference(request.reference_text)
    if (
        request.location_id is None
        or not normalized
        or not validate_language_tag(request.language)
        or not await _scope_is_valid(
            db,
            tenant_id=request.tenant_id,
            organization_id=request.organization_id,
            location_id=request.location_id,
        )
    ):
        result = ProductResolutionResult(ResolutionStatus.INVALID_CONTEXT)
        _log_product_outcome(request, result)
        return result

    matched = await _match_products(
        db,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        normalized_reference=normalized,
        language=request.language,
    )
    if not matched:
        result = ProductResolutionResult(ResolutionStatus.NOT_FOUND)
        _log_product_outcome(request, result)
        return result
    orderable_ids = await _orderable_product_ids(
        db,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        location_id=request.location_id,
        product_ids=tuple(sorted(matched)),
    )
    candidates = tuple(
        ProductResolutionCandidate(product.id, product.name, source)
        for product, source in (matched[product_id] for product_id in sorted(orderable_ids))
    )
    if not candidates:
        result = ProductResolutionResult(ResolutionStatus.NOT_ORDERABLE)
    elif len(candidates) == 1:
        result = ProductResolutionResult(ResolutionStatus.RESOLVED, candidate=candidates[0])
    else:
        result = ProductResolutionResult(
            ResolutionStatus.AMBIGUOUS, candidates=candidates
        )
    _log_product_outcome(request, result)
    return result


def _log_choice_outcome(
    request: ChoiceResolutionRequest, result: ChoiceResolutionResult
) -> None:
    logger.info(
        'Choice resolution completed',
        extra={
            'event': f'choice_resolution_{result.status.value.lower()}',
            'tenant_id': request.tenant_id,
            'organization_id': request.organization_id,
            'product_id': request.parent_product_id,
            'candidate_count': len(result.candidates) or (1 if result.candidate else 0),
            'language': request.language,
            'outcome': result.status.value,
        },
    )


async def resolve_choice(
    db: AsyncSession, request: ChoiceResolutionRequest
) -> ChoiceResolutionResult:
    normalized = normalize_reference(request.choice_reference_text)
    if (
        request.parent_product_id <= 0
        or not normalized
        or not validate_language_tag(request.language)
        or not await _scope_is_valid(
            db,
            tenant_id=request.tenant_id,
            organization_id=request.organization_id,
        )
    ):
        result = ChoiceResolutionResult(ResolutionStatus.INVALID_CONTEXT)
        _log_choice_outcome(request, result)
        return result
    graph = await structure.load_composition_graph(
        db,
        tenant_id=request.tenant_id,
        product_id=request.parent_product_id,
        active_only=True,
    )
    if graph is None or graph.composition.organization_id != request.organization_id:
        result = ChoiceResolutionResult(ResolutionStatus.INVALID_CONTEXT)
        _log_choice_outcome(request, result)
        return result

    groups = graph.groups
    if request.choice_group_id is not None:
        groups = tuple(group for group in groups if group.group.id == request.choice_group_id)
        if not groups:
            result = ChoiceResolutionResult(ResolutionStatus.INVALID_CONTEXT)
            _log_choice_outcome(request, result)
            return result
    option_records = tuple(
        (group.group.id, option.option.id, option.product)
        for group in groups
        for option in group.options
    )
    matches = await _match_products(
        db,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        normalized_reference=normalized,
        language=request.language,
        products=(record[2] for record in option_records),
    )
    candidates = tuple(
        sorted(
            (
                ChoiceResolutionCandidate(
                    group_id,
                    option_id,
                    product.id,
                    product.name,
                    matches[product.id][1],
                )
                for group_id, option_id, product in option_records
                if product.id in matches
            ),
            key=lambda candidate: (
                candidate.choice_group_id,
                candidate.choice_option_id,
                candidate.option_product_id,
            ),
        )
    )
    if not candidates:
        result = ChoiceResolutionResult(ResolutionStatus.NOT_FOUND)
    elif len(candidates) == 1:
        result = ChoiceResolutionResult(ResolutionStatus.RESOLVED, candidate=candidates[0])
    else:
        result = ChoiceResolutionResult(ResolutionStatus.AMBIGUOUS, candidates=candidates)
    _log_choice_outcome(request, result)
    return result
