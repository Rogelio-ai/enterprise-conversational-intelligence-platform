from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.models import (
    ProductChoiceGroup,
    ProductChoiceOption,
    ProductComponent,
    ProductComposition,
)
from app.restaurant.catalog import structure


router = APIRouter(tags=['product-composition'])
Lifecycle = Literal['ACTIVE', 'INACTIVE']
MAX_QUANTITY = Decimal('999999999999999.9999')


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact numbers')
    return value


ExactPositiveQuantity = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(gt=0, allow_inf_nan=False),
]


def _quantity(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if value.as_tuple().exponent < -4:
        raise ValueError('At most four fractional digits are allowed')
    if value > MAX_QUANTITY:
        raise ValueError('Quantity exceeds DECIMAL(19,4)')
    return value


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str


class CompositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    product_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class CompositionPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: Lifecycle


class ComponentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    component_product_id: int = Field(gt=0)
    quantity: ExactPositiveQuantity
    display_order: int = Field(default=0, ge=0)

    _validate_quantity = field_validator('quantity')(_quantity)


class ComponentPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')

    quantity: ExactPositiveQuantity | None = None
    display_order: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    _validate_quantity = field_validator('quantity')(_quantity)

    @model_validator(mode='after')
    def validate_patch(self) -> 'ComponentPatch':
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError('At least one non-null field is required')
        return self


class ComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    composition_id: int
    component_product_id: int
    quantity: Decimal
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class ComponentDetail(ComponentResponse):
    product: ProductSummary


class ChoiceGroupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str = Field(min_length=1, max_length=200)
    min_selections: int = Field(ge=0)
    max_selections: int = Field(gt=0)
    display_order: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def validate_range(self) -> 'ChoiceGroupCreate':
        if self.min_selections > self.max_selections:
            raise ValueError('min_selections cannot exceed max_selections')
        return self


class ChoiceGroupPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=200)
    min_selections: int | None = Field(default=None, ge=0)
    max_selections: int | None = Field(default=None, gt=0)
    display_order: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    @model_validator(mode='after')
    def validate_patch(self) -> 'ChoiceGroupPatch':
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError('At least one non-null field is required')
        return self


class ChoiceGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    composition_id: int
    name: str
    min_selections: int
    max_selections: int
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class ChoiceOptionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    option_product_id: int = Field(gt=0)
    quantity: ExactPositiveQuantity
    display_order: int = Field(default=0, ge=0)

    _validate_quantity = field_validator('quantity')(_quantity)


class ChoiceOptionPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')

    quantity: ExactPositiveQuantity | None = None
    display_order: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    _validate_quantity = field_validator('quantity')(_quantity)

    @model_validator(mode='after')
    def validate_patch(self) -> 'ChoiceOptionPatch':
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError('At least one non-null field is required')
        return self


class ChoiceOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    group_id: int
    option_product_id: int
    quantity: Decimal
    display_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class ChoiceOptionDetail(ChoiceOptionResponse):
    product: ProductSummary


class ChoiceGroupDetail(ChoiceGroupResponse):
    options: list[ChoiceOptionDetail]


class CompositionDetail(CompositionResponse):
    product: ProductSummary
    components: list[ComponentDetail]
    choice_groups: list[ChoiceGroupDetail]


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def _map_structure_error(exc: Exception) -> HTTPException:
    if isinstance(exc, structure.StructureNotFoundError):
        return _not_found(str(exc))
    return _conflict(str(exc))


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict('Product composition relationship already exists') from exc


def _detail(graph: structure.CompositionGraph) -> CompositionDetail:
    return CompositionDetail(
        **CompositionResponse.model_validate(graph.composition).model_dump(),
        product=ProductSummary.model_validate(graph.product),
        components=[
            ComponentDetail(
                **ComponentResponse.model_validate(record.component).model_dump(),
                product=ProductSummary.model_validate(record.product),
            )
            for record in graph.components
        ],
        choice_groups=[
            ChoiceGroupDetail(
                **ChoiceGroupResponse.model_validate(record.group).model_dump(),
                options=[
                    ChoiceOptionDetail(
                        **ChoiceOptionResponse.model_validate(option.option).model_dump(),
                        product=ProductSummary.model_validate(option.product),
                    )
                    for option in record.options
                ],
            )
            for record in graph.groups
        ],
    )


@router.get('/products/{product_id}/composition', response_model=CompositionDetail)
async def get_composition(
    product_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompositionDetail:
    graph = await structure.load_composition_graph(
        db, tenant_id=context.tenant_id, product_id=product_id, active_only=False
    )
    if graph is None:
        raise _not_found('Product Composition not found')
    return _detail(graph)


@router.post(
    '/products/{product_id}/composition',
    response_model=CompositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_composition(
    product_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductComposition:
    try:
        composition = await structure.create_composition(
            db, tenant_id=context.tenant_id, product_id=product_id
        )
        await _commit(db)
    except (structure.StructureNotFoundError, structure.StructureConflictError) as exc:
        await db.rollback()
        raise _map_structure_error(exc) from exc
    await db.refresh(composition)
    return composition


@router.patch('/products/{product_id}/composition', response_model=CompositionResponse)
async def patch_composition(
    product_id: Annotated[int, Path(gt=0)],
    payload: CompositionPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductComposition:
    try:
        if payload.status == 'ACTIVE':
            composition = await structure.activate_composition(
                db, tenant_id=context.tenant_id, product_id=product_id
            )
        else:
            composition = await structure.require_composition(
                db, tenant_id=context.tenant_id, product_id=product_id, for_update=True
            )
            composition.status = 'INACTIVE'
        await _commit(db)
    except (structure.StructureNotFoundError, structure.StructureConflictError) as exc:
        await db.rollback()
        raise _map_structure_error(exc) from exc
    await db.refresh(composition)
    return composition


@router.post(
    '/products/{product_id}/composition/components',
    response_model=ComponentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_component(
    product_id: Annotated[int, Path(gt=0)],
    payload: ComponentCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductComponent:
    try:
        composition = await structure.require_composition(
            db, tenant_id=context.tenant_id, product_id=product_id
        )
        await structure.validate_child_product(
            db, composition=composition, child_product_id=payload.component_product_id
        )
        component = ProductComponent(
            tenant_id=context.tenant_id,
            organization_id=composition.organization_id,
            composition_id=composition.id,
            component_product_id=payload.component_product_id,
            quantity=payload.quantity,
            display_order=payload.display_order,
            status='ACTIVE',
        )
        db.add(component)
        await _commit(db)
    except (structure.StructureNotFoundError, structure.StructureConflictError) as exc:
        await db.rollback()
        raise _map_structure_error(exc) from exc
    await db.refresh(component)
    return component


async def _component(
    db: AsyncSession, *, composition: ProductComposition, component_id: int
) -> ProductComponent:
    value = await db.scalar(
        select(ProductComponent)
        .where(
            ProductComponent.id == component_id,
            ProductComponent.tenant_id == composition.tenant_id,
            ProductComponent.organization_id == composition.organization_id,
            ProductComponent.composition_id == composition.id,
        )
        .with_for_update()
    )
    if value is None:
        raise _not_found('Product Component not found')
    return value


@router.patch(
    '/products/{product_id}/composition/components/{component_id}',
    response_model=ComponentResponse,
)
async def patch_component(
    product_id: Annotated[int, Path(gt=0)],
    component_id: Annotated[int, Path(gt=0)],
    payload: ComponentPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductComponent:
    try:
        composition = await structure.require_composition(
            db, tenant_id=context.tenant_id, product_id=product_id
        )
    except structure.StructureNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    component = await _component(db, composition=composition, component_id=component_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(component, field, value)
    await _commit(db)
    await db.refresh(component)
    return component


@router.post(
    '/products/{product_id}/composition/choice-groups',
    response_model=ChoiceGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_choice_group(
    product_id: Annotated[int, Path(gt=0)],
    payload: ChoiceGroupCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductChoiceGroup:
    try:
        composition = await structure.require_composition(
            db, tenant_id=context.tenant_id, product_id=product_id, for_update=True
        )
    except structure.StructureNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    group = ProductChoiceGroup(
        tenant_id=context.tenant_id,
        organization_id=composition.organization_id,
        composition_id=composition.id,
        name=payload.name,
        min_selections=payload.min_selections,
        max_selections=payload.max_selections,
        display_order=payload.display_order,
        status='ACTIVE',
    )
    db.add(group)
    await _commit(db)
    await db.refresh(group)
    return group


async def _group(
    db: AsyncSession, *, composition: ProductComposition, group_id: int
) -> ProductChoiceGroup:
    value = await db.scalar(
        select(ProductChoiceGroup)
        .where(
            ProductChoiceGroup.id == group_id,
            ProductChoiceGroup.tenant_id == composition.tenant_id,
            ProductChoiceGroup.organization_id == composition.organization_id,
            ProductChoiceGroup.composition_id == composition.id,
        )
        .with_for_update()
    )
    if value is None:
        raise _not_found('Product Choice Group not found')
    return value


@router.patch(
    '/products/{product_id}/composition/choice-groups/{group_id}',
    response_model=ChoiceGroupResponse,
)
async def patch_choice_group(
    product_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    payload: ChoiceGroupPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductChoiceGroup:
    try:
        composition = await structure.require_composition(
            db, tenant_id=context.tenant_id, product_id=product_id, for_update=True
        )
    except structure.StructureNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    group = await _group(db, composition=composition, group_id=group_id)
    values = {
        'min_selections': group.min_selections,
        'max_selections': group.max_selections,
    }
    values.update(payload.model_dump(exclude_unset=True))
    if values['min_selections'] > values['max_selections']:
        raise HTTPException(422, 'min_selections cannot exceed max_selections')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    await _commit(db)
    await db.refresh(group)
    return group


@router.post(
    '/products/{product_id}/composition/choice-groups/{group_id}/options',
    response_model=ChoiceOptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_choice_option(
    product_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    payload: ChoiceOptionCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductChoiceOption:
    try:
        composition = await structure.require_composition(
            db, tenant_id=context.tenant_id, product_id=product_id
        )
        await _group(db, composition=composition, group_id=group_id)
        await structure.validate_child_product(
            db, composition=composition, child_product_id=payload.option_product_id
        )
        option = ProductChoiceOption(
            tenant_id=context.tenant_id,
            organization_id=composition.organization_id,
            group_id=group_id,
            option_product_id=payload.option_product_id,
            quantity=payload.quantity,
            display_order=payload.display_order,
            status='ACTIVE',
        )
        db.add(option)
        await _commit(db)
    except (structure.StructureNotFoundError, structure.StructureConflictError) as exc:
        await db.rollback()
        raise _map_structure_error(exc) from exc
    await db.refresh(option)
    return option


async def _option(
    db: AsyncSession, *, group: ProductChoiceGroup, option_id: int
) -> ProductChoiceOption:
    value = await db.scalar(
        select(ProductChoiceOption)
        .where(
            ProductChoiceOption.id == option_id,
            ProductChoiceOption.tenant_id == group.tenant_id,
            ProductChoiceOption.organization_id == group.organization_id,
            ProductChoiceOption.group_id == group.id,
        )
        .with_for_update()
    )
    if value is None:
        raise _not_found('Product Choice Option not found')
    return value


@router.patch(
    '/products/{product_id}/composition/choice-groups/{group_id}/options/{option_id}',
    response_model=ChoiceOptionResponse,
)
async def patch_choice_option(
    product_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    option_id: Annotated[int, Path(gt=0)],
    payload: ChoiceOptionPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('product.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductChoiceOption:
    try:
        composition = await structure.require_composition(
            db, tenant_id=context.tenant_id, product_id=product_id, for_update=True
        )
    except structure.StructureNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    group = await _group(db, composition=composition, group_id=group_id)
    option = await _option(db, group=group, option_id=option_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(option, field, value)
    await _commit(db)
    await db.refresh(option)
    return option
