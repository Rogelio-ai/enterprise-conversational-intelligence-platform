"""Canonical Product Preparation Route revision provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, PreparationArea, Product, ProductPreparationRoute
from app.restaurant.catalog import provisioning as product_provisioning
from app.restaurant.preparation import area_provisioning


ROUTE_POLICIES = frozenset({'AREA', 'COMPONENTS', 'NO_PREPARATION'})


class PreparationRouteProvisioningError(ValueError):
    pass


class PreparationRouteScopeNotFoundError(PreparationRouteProvisioningError):
    pass


class PreparationRouteConflictError(PreparationRouteProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class PreparationRouteProvisioningPlan:
    operation: str
    product_id: int | None
    preparation_area_id: int | None
    current_route_id: int | None


@dataclass(frozen=True, slots=True)
class PreparationRouteProvisioningResult:
    route: ProductPreparationRoute
    operation: str


def _policy(value: str) -> str:
    if not isinstance(value, str):
        raise PreparationRouteProvisioningError('Invalid Preparation Route policy')
    normalized = value.strip().upper()
    if normalized not in ROUTE_POLICIES:
        raise PreparationRouteProvisioningError('Unsupported Preparation Route policy')
    return normalized


def _active_status(value: str) -> str:
    if not isinstance(value, str):
        raise PreparationRouteProvisioningError('Invalid Preparation Route status')
    normalized = value.strip().upper()
    if normalized != 'ACTIVE':
        raise PreparationRouteConflictError(
            'Preparation Route workbook rows must describe an ACTIVE route'
        )
    return normalized


def _area_semantics(policy: str, preparation_area_id: int | None) -> None:
    if (policy == 'AREA') != (preparation_area_id is not None):
        raise PreparationRouteProvisioningError(
            'AREA requires a Preparation Area; other policies require none'
        )


async def _location(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, for_update: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    location = await db.scalar(statement)
    if location is None:
        raise PreparationRouteScopeNotFoundError('Location not found')
    return location


async def _product(
    db: AsyncSession, *, tenant_id: int, organization_id: int, product_id: int,
) -> Product:
    product = await db.scalar(select(Product).where(
        Product.id == product_id,
        Product.tenant_id == tenant_id,
        Product.organization_id == organization_id,
    ))
    if product is None:
        raise PreparationRouteScopeNotFoundError(
            'Product not found in this Location Organization'
        )
    return product


async def _area(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, preparation_area_id: int | None,
) -> PreparationArea | None:
    if preparation_area_id is None:
        return None
    area = await db.scalar(select(PreparationArea).where(
        PreparationArea.id == preparation_area_id,
        PreparationArea.tenant_id == tenant_id,
        PreparationArea.organization_id == organization_id,
        PreparationArea.location_id == location_id,
        PreparationArea.status == 'ACTIVE',
    ))
    if area is None:
        raise PreparationRouteScopeNotFoundError(
            'Active Preparation Area not found in this Location'
        )
    return area


async def _current_route(
    db: AsyncSession, *, tenant_id: int, location_id: int, product_id: int,
    for_update: bool = False,
) -> ProductPreparationRoute | None:
    statement = select(ProductPreparationRoute).where(
        ProductPreparationRoute.tenant_id == tenant_id,
        ProductPreparationRoute.location_id == location_id,
        ProductPreparationRoute.product_id == product_id,
        ProductPreparationRoute.status == 'ACTIVE',
        ProductPreparationRoute.active_slot == 1,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _operation(
    route: ProductPreparationRoute | None, *, policy: str,
    preparation_area_id: int | None,
) -> str:
    if route is None:
        return 'CREATE'
    return (
        'UNCHANGED'
        if (route.policy, route.preparation_area_id) == (policy, preparation_area_id)
        else 'UPDATE'
    )


async def plan_route(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, product_id: int, policy: str,
    preparation_area_id: int | None, status: str = 'ACTIVE',
) -> PreparationRouteProvisioningPlan:
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    await _product(
        db, tenant_id=tenant_id, organization_id=organization_id,
        product_id=product_id,
    )
    normalized_policy = _policy(policy)
    _active_status(status)
    _area_semantics(normalized_policy, preparation_area_id)
    await _area(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, preparation_area_id=preparation_area_id,
    )
    current = await _current_route(
        db, tenant_id=tenant_id, location_id=location_id,
        product_id=product_id,
    )
    return PreparationRouteProvisioningPlan(
        _operation(
            current, policy=normalized_policy,
            preparation_area_id=preparation_area_id,
        ),
        product_id, preparation_area_id,
        None if current is None else current.id,
    )


async def _apply_revision(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, product_id: int, policy: str,
    preparation_area_id: int | None, unchanged_if_equivalent: bool,
) -> PreparationRouteProvisioningResult:
    normalized_policy = _policy(policy)
    _area_semantics(normalized_policy, preparation_area_id)
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, for_update=True,
    )
    await _product(
        db, tenant_id=tenant_id, organization_id=organization_id,
        product_id=product_id,
    )
    await _area(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, preparation_area_id=preparation_area_id,
    )
    current = await _current_route(
        db, tenant_id=tenant_id, location_id=location_id,
        product_id=product_id, for_update=True,
    )
    operation = _operation(
        current, policy=normalized_policy,
        preparation_area_id=preparation_area_id,
    )
    if operation == 'UNCHANGED' and unchanged_if_equivalent:
        await db.commit()
        await db.refresh(current)
        return PreparationRouteProvisioningResult(current, operation)
    if current is not None:
        current.status = 'INACTIVE'
        current.active_slot = None
        await db.flush()
    route = ProductPreparationRoute(
        tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, product_id=product_id,
        policy=normalized_policy, preparation_area_id=preparation_area_id,
        status='ACTIVE', active_slot=1,
    )
    db.add(route)
    try:
        await db.commit()
        await db.refresh(route)
    except IntegrityError as exc:
        await db.rollback()
        raise PreparationRouteConflictError(
            'Product Preparation Route update conflicted'
        ) from exc
    return PreparationRouteProvisioningResult(
        route, 'CREATE' if current is None else 'UPDATE'
    )


async def revise_route(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, product_id: int, policy: str,
    preparation_area_id: int | None,
) -> ProductPreparationRoute:
    """Preserve the existing API behavior of always appending a revision."""

    result = await _apply_revision(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, product_id=product_id, policy=policy,
        preparation_area_id=preparation_area_id,
        unchanged_if_equivalent=False,
    )
    return result.route


async def provision_route(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, product_id: int, policy: str,
    preparation_area_id: int | None, status: str = 'ACTIVE',
) -> PreparationRouteProvisioningResult:
    _active_status(status)
    return await _apply_revision(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, product_id=product_id, policy=policy,
        preparation_area_id=preparation_area_id,
        unchanged_if_equivalent=True,
    )


async def _resolve_product_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    binding_namespace: str, product_key: str,
) -> Product:
    try:
        return await product_provisioning.resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except product_provisioning.ProductScopeNotFoundError as exc:
        raise PreparationRouteScopeNotFoundError(
            'Product binding not found'
        ) from exc
    except product_provisioning.ProductProvisioningError as exc:
        raise PreparationRouteProvisioningError(str(exc)) from exc


async def _resolve_area_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, preparation_area_code: str | None,
) -> PreparationArea | None:
    if preparation_area_code is None:
        return None
    try:
        area = await area_provisioning.resolve_area(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, area_code=preparation_area_code,
        )
    except area_provisioning.PreparationAreaScopeNotFoundError as exc:
        raise PreparationRouteScopeNotFoundError(
            'Preparation Area binding not found'
        ) from exc
    except area_provisioning.PreparationAreaProvisioningError as exc:
        raise PreparationRouteProvisioningError(str(exc)) from exc
    if area.status != 'ACTIVE':
        raise PreparationRouteConflictError(
            'Preparation Route requires an ACTIVE Preparation Area'
        )
    return area


async def plan_route_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    policy: str, preparation_area_code: str | None, status: str,
    allow_unresolved_product: bool = False,
    allow_unresolved_area: bool = False,
) -> PreparationRouteProvisioningPlan:
    normalized_policy = _policy(policy)
    _active_status(status)
    await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    if (normalized_policy == 'AREA') != (preparation_area_code is not None):
        raise PreparationRouteProvisioningError(
            'AREA requires a Preparation Area; other policies require none'
        )
    product = None
    area = None
    try:
        product = await _resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except PreparationRouteScopeNotFoundError:
        if not allow_unresolved_product:
            raise
    try:
        area = await _resolve_area_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id,
            preparation_area_code=preparation_area_code,
        )
    except PreparationRouteScopeNotFoundError:
        if not allow_unresolved_area:
            raise
    if product is None:
        return PreparationRouteProvisioningPlan(
            'CREATE', None, None if area is None else area.id, None,
        )
    current = await _current_route(
        db, tenant_id=tenant_id, location_id=location_id,
        product_id=product.id,
    )
    if normalized_policy == 'AREA' and area is None:
        operation = 'CREATE' if current is None else 'UPDATE'
        area_id = None
    else:
        area_id = None if area is None else area.id
        operation = _operation(
            current, policy=normalized_policy, preparation_area_id=area_id,
        )
    return PreparationRouteProvisioningPlan(
        operation, product.id, area_id,
        None if current is None else current.id,
    )


async def provision_route_binding(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    policy: str, preparation_area_code: str | None, status: str,
) -> PreparationRouteProvisioningResult:
    normalized_policy = _policy(policy)
    _active_status(status)
    if (normalized_policy == 'AREA') != (preparation_area_code is not None):
        raise PreparationRouteProvisioningError(
            'AREA requires a Preparation Area; other policies require none'
        )
    product = await _resolve_product_binding(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, product_key=product_key,
    )
    area = await _resolve_area_binding(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
        preparation_area_code=preparation_area_code,
    )
    return await provision_route(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, product_id=product.id,
        policy=normalized_policy,
        preparation_area_id=None if area is None else area.id,
        status=status,
    )
