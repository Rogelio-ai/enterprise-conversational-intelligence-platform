from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.models import (
    Location,
    LocationPosConnection,
    LocationPreparationConfiguration,
    PreparationArea,
    Product,
    ProductPreparationRoute,
    Resource,
)
from app.restaurant.preparation import errors, service


router = APIRouter(tags=['preparation'])
_CODE = re.compile(r'^[A-Z0-9][A-Z0-9_-]{0,63}$')


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


async def _location(db: AsyncSession, tenant_id: int, location_id: int, *, lock: bool = False) -> Location:
    statement = select(Location).where(Location.id == location_id, Location.tenant_id == tenant_id)
    if lock:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise _not_found('Location not found')
    return value


class PreparationConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preparation_owner: Literal['PLATFORM', 'EXTERNAL_POS']


class PreparationConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    preparation_owner: str
    created_at: datetime
    updated_at: datetime


@router.get('/locations/{location_id}/preparation-configuration', response_model=PreparationConfigurationResponse)
async def get_configuration(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LocationPreparationConfiguration:
    value = await db.scalar(select(LocationPreparationConfiguration).where(
        LocationPreparationConfiguration.location_id == location_id,
        LocationPreparationConfiguration.tenant_id == context.tenant_id,
    ))
    if value is None:
        raise _not_found('Location Preparation Configuration not found')
    return value


@router.put('/locations/{location_id}/preparation-configuration', response_model=PreparationConfigurationResponse)
async def put_configuration(
    location_id: Annotated[int, Path(gt=0)], payload: PreparationConfigurationRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LocationPreparationConfiguration:
    location = await _location(db, context.tenant_id, location_id, lock=True)
    value = await db.scalar(select(LocationPreparationConfiguration).where(
        LocationPreparationConfiguration.location_id == location.id,
        LocationPreparationConfiguration.tenant_id == context.tenant_id,
    ).with_for_update())
    if value is None:
        value = LocationPreparationConfiguration(
            tenant_id=context.tenant_id, organization_id=location.organization_id,
            location_id=location.id, preparation_owner=payload.preparation_owner,
        )
        db.add(value)
    else:
        value.preparation_owner = payload.preparation_owner
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Location Preparation Configuration update conflicted') from exc
    await db.refresh(value)
    return value


class PreparationAreaCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    location_id: int = Field(gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)

    @field_validator('code')
    @classmethod
    def code_value(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not _CODE.fullmatch(normalized):
            raise ValueError('Code must contain only letters, numbers, underscores, or hyphens')
        return normalized


class PreparationAreaPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=200)
    resource_id: int | None = Field(default=None, gt=0)
    status: Literal['ACTIVE', 'INACTIVE'] | None = None

    @model_validator(mode='after')
    def nonempty(self) -> 'PreparationAreaPatch':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if any(getattr(self, field) is None for field in self.model_fields_set if field != 'resource_id'):
            raise ValueError('Required fields cannot be null')
        return self


class PreparationAreaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int | None
    code: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class PreparationAreaList(BaseModel):
    items: list[PreparationAreaResponse]


async def _resource(db: AsyncSession, tenant_id: int, location_id: int, resource_id: int | None) -> None:
    if resource_id is None:
        return
    value = await db.scalar(select(Resource.id).where(
        Resource.id == resource_id, Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
    ))
    if value is None:
        raise _not_found('Resource not found in this Location')


@router.get('/preparation-areas', response_model=PreparationAreaList)
async def list_areas(
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
) -> PreparationAreaList:
    await _location(db, context.tenant_id, location_id)
    values = (await db.execute(select(PreparationArea).where(
        PreparationArea.tenant_id == context.tenant_id,
        PreparationArea.location_id == location_id,
    ).order_by(PreparationArea.code, PreparationArea.id))).scalars().all()
    return PreparationAreaList(items=list(values))


@router.post('/preparation-areas', response_model=PreparationAreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    payload: PreparationAreaCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreparationArea:
    location = await _location(db, context.tenant_id, payload.location_id, lock=True)
    await _resource(db, context.tenant_id, location.id, payload.resource_id)
    value = PreparationArea(
        tenant_id=context.tenant_id, organization_id=location.organization_id,
        location_id=location.id, resource_id=payload.resource_id,
        code=payload.code, name=payload.name, status='ACTIVE',
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Preparation Area code already exists in this Location') from exc
    await db.refresh(value)
    return value


@router.get('/preparation-areas/{area_id}', response_model=PreparationAreaResponse)
async def get_area(
    area_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreparationArea:
    value = await db.scalar(select(PreparationArea).where(
        PreparationArea.id == area_id, PreparationArea.tenant_id == context.tenant_id,
    ))
    if value is None:
        raise _not_found('Preparation Area not found')
    return value


@router.patch('/preparation-areas/{area_id}', response_model=PreparationAreaResponse)
async def patch_area(
    area_id: Annotated[int, Path(gt=0)], payload: PreparationAreaPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreparationArea:
    value = await db.scalar(select(PreparationArea).where(
        PreparationArea.id == area_id, PreparationArea.tenant_id == context.tenant_id,
    ).with_for_update())
    if value is None:
        raise _not_found('Preparation Area not found')
    updates = payload.model_dump(exclude_unset=True)
    if 'resource_id' in updates:
        await _resource(db, context.tenant_id, value.location_id, updates['resource_id'])
    for key, item in updates.items():
        setattr(value, key, item)
    await db.commit()
    await db.refresh(value)
    return value


class ProductRouteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    policy: Literal['AREA', 'COMPONENTS', 'NO_PREPARATION']
    preparation_area_id: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def area_semantics(self) -> 'ProductRouteRequest':
        if (self.policy == 'AREA') != (self.preparation_area_id is not None):
            raise ValueError('AREA requires preparation_area_id; other policies require null')
        return self


class ProductRouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    product_id: int
    policy: str
    preparation_area_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProductRouteList(BaseModel):
    items: list[ProductRouteResponse]


@router.get('/locations/{location_id}/product-preparation-routes', response_model=ProductRouteList)
async def list_product_routes(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductRouteList:
    await _location(db, context.tenant_id, location_id)
    values = (await db.execute(select(ProductPreparationRoute).where(
        ProductPreparationRoute.tenant_id == context.tenant_id,
        ProductPreparationRoute.location_id == location_id,
        ProductPreparationRoute.status == 'ACTIVE',
    ).order_by(ProductPreparationRoute.product_id, ProductPreparationRoute.id))).scalars().all()
    return ProductRouteList(items=list(values))


@router.put('/locations/{location_id}/products/{product_id}/preparation-route', response_model=ProductRouteResponse)
async def put_product_route(
    location_id: Annotated[int, Path(gt=0)], product_id: Annotated[int, Path(gt=0)],
    payload: ProductRouteRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductPreparationRoute:
    location = await _location(db, context.tenant_id, location_id, lock=True)
    product = await db.scalar(select(Product).where(
        Product.id == product_id, Product.tenant_id == context.tenant_id,
        Product.organization_id == location.organization_id,
    ))
    if product is None:
        raise _not_found('Product not found in this Location Organization')
    if payload.preparation_area_id is not None:
        area = await db.scalar(select(PreparationArea).where(
            PreparationArea.id == payload.preparation_area_id,
            PreparationArea.tenant_id == context.tenant_id,
            PreparationArea.organization_id == location.organization_id,
            PreparationArea.location_id == location.id,
            PreparationArea.status == 'ACTIVE',
        ))
        if area is None:
            raise _not_found('Active Preparation Area not found in this Location')
    current = await db.scalar(select(ProductPreparationRoute).where(
        ProductPreparationRoute.tenant_id == context.tenant_id,
        ProductPreparationRoute.location_id == location.id,
        ProductPreparationRoute.product_id == product.id,
        ProductPreparationRoute.status == 'ACTIVE',
        ProductPreparationRoute.active_slot == 1,
    ).with_for_update())
    if current is not None:
        current.status = 'INACTIVE'
        current.active_slot = None
        await db.flush()
    value = ProductPreparationRoute(
        tenant_id=context.tenant_id, organization_id=location.organization_id,
        location_id=location.id, product_id=product.id, policy=payload.policy,
        preparation_area_id=payload.preparation_area_id, status='ACTIVE', active_slot=1,
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Product Preparation Route update conflicted') from exc
    await db.refresh(value)
    return value


class PosPreparationBehaviorRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    external_preparation_behavior: Literal['NO_PREPARATION_OUTPUT', 'MAY_PRODUCE_PREPARATION_OUTPUT']


@router.put('/locations/{location_id}/pos-connection/preparation-behavior')
async def put_pos_preparation_behavior(
    location_id: Annotated[int, Path(gt=0)], payload: PosPreparationBehaviorRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.configure'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    value = await db.scalar(select(LocationPosConnection).where(
        LocationPosConnection.tenant_id == context.tenant_id,
        LocationPosConnection.location_id == location_id,
        LocationPosConnection.status == 'ACTIVE',
        LocationPosConnection.active_slot == 1,
    ).with_for_update())
    if value is None:
        raise _not_found('Active Location POS connection not found')
    value.external_preparation_behavior = payload.external_preparation_behavior
    await db.commit()
    return {'location_id': location_id, 'external_preparation_behavior': value.external_preparation_behavior}


class WorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_restaurant_order_item_id: int | None
    source_restaurant_order_item_component_id: int | None
    required_quantity: Decimal
    route_id: int


class WorkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    preparation_area_id: int
    area_code: str
    area_name: str
    items: tuple[WorkItemResponse, ...]


class RoutingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_order_id: int
    preparation_owner: str | None
    state: str
    routing_schema_version: int
    routing_fingerprint: str | None
    error_code: str | None
    error_detail: str | None
    routed_at: datetime | None
    works: tuple[WorkResponse, ...]


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EMPLOYEE, tenant_id=context.tenant_id,
        principal_id=context.membership_id, principal_reference=None,
        correlation_id=get_correlation_id(),
    )


def _routing_error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.PreparationNotFoundError):
        return _not_found(str(exc))
    if isinstance(exc, errors.PreparationConflictError):
        return _conflict(str(exc))
    raise exc


@router.post('/restaurant-orders/{order_id}/preparation-routing', response_model=RoutingResponse)
async def route_restaurant_order(
    order_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.route'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.route_order(db, order_id=order_id, execution=_execution(context))
    except Exception as exc:
        raise _routing_error(exc) from exc


@router.get('/restaurant-orders/{order_id}/preparation-routing', response_model=RoutingResponse)
async def read_restaurant_order_routing(
    order_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_routing(db, tenant_id=context.tenant_id, order_id=order_id)
    except Exception as exc:
        raise _routing_error(exc) from exc


class PreparationOrderContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    restaurant_order_id: int
    accepted_at: datetime
    source_channel: str
    resource_id: int
    service_session_id: int
    diner_session_id: int
    current_resource_code: str | None
    current_resource_name: str | None


class PreparationExecutionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    preparation_work_id: int
    source_type: str
    source_restaurant_order_item_id: int | None
    source_restaurant_order_item_component_id: int | None
    product_name: str
    parent_product_name: str | None
    required_quantity: Decimal
    execution_state: str
    execution_version: int


class PreparationExecutionWorkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    preparation_area_id: int
    area_code: str
    area_name: str
    routed_at: datetime
    execution_state: str
    order: PreparationOrderContextResponse
    items: tuple[PreparationExecutionItemResponse, ...]


class PreparationTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sequence: int
    from_state: str
    to_state: str
    actor_type: str
    actor_membership_id: int | None
    actor_principal_reference: str | None
    correlation_id: str | None
    occurred_at: datetime


class PreparationItemDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item: PreparationExecutionItemResponse
    transitions: tuple[PreparationTransitionResponse, ...]


class PreparationTransitionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_state: Literal['NEW', 'IN_PROGRESS', 'COMPLETED']
    expected_version: int = Field(ge=0)
    to_state: Literal['NEW', 'IN_PROGRESS', 'COMPLETED']


class PreparationTransitionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    transition: PreparationTransitionResponse
    current_execution_state: str
    current_execution_version: int
    replayed: bool


@router.get('/preparation-works', response_model=tuple[PreparationExecutionWorkResponse, ...])
async def list_execution_work(
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: int = Query(gt=0),
    preparation_area_id: int | None = Query(default=None, gt=0),
    execution_state: Literal['NEW', 'IN_PROGRESS', 'COMPLETED'] | None = Query(default=None),
    restaurant_order_id: int | None = Query(default=None, gt=0),
    after_work_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> object:
    await _location(db, context.tenant_id, location_id)
    try:
        return await service.list_preparation_work(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            preparation_area_id=preparation_area_id,
            execution_state=execution_state,
            restaurant_order_id=restaurant_order_id,
            after_work_id=after_work_id,
            limit=limit,
        )
    except Exception as exc:
        raise _routing_error(exc) from exc


@router.get('/preparation-works/{work_id}', response_model=PreparationExecutionWorkResponse)
async def read_execution_work(
    work_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_preparation_work(db, tenant_id=context.tenant_id, work_id=work_id)
    except Exception as exc:
        raise _routing_error(exc) from exc


@router.get('/preparation-work-items/{item_id}', response_model=PreparationItemDetailResponse)
async def read_execution_item(
    item_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_preparation_work_item(
            db, tenant_id=context.tenant_id, item_id=item_id
        )
    except Exception as exc:
        raise _routing_error(exc) from exc


@router.post(
    '/preparation-work-items/{item_id}/transitions',
    response_model=PreparationTransitionResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def transition_execution_item(
    item_id: Annotated[int, Path(gt=0)],
    payload: PreparationTransitionRequest,
    response: Response,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.execute'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[
        str,
        Header(alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[\x21-\x7e]+$'),
    ],
) -> object:
    try:
        result = await service.transition_work_item(
            db,
            item_id=item_id,
            expected_state=payload.expected_state,
            expected_version=payload.expected_version,
            to_state=payload.to_state,
            idempotency_key=idempotency_key,
            execution=_execution(context),
        )
    except Exception as exc:
        raise _routing_error(exc) from exc
    response.status_code = status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED
    return result
