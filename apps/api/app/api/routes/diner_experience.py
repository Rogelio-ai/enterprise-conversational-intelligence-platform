from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.diner_deps import DinerAuthenticatedContext, get_diner_authenticated_context
from app.core.middleware import get_correlation_id
from app.restaurant.checks import errors as check_errors
from app.restaurant.diner_experience import service, states
from app.restaurant.diner_experience.contracts import (
    OperationalRequestIdempotencyConflictError,
    OperationalRequestInvalidError,
    OperationalRequestNotFoundError,
    ProductUnavailableError,
)
from app.restaurant.intelligence.errors import KnowledgeNotFoundError, KnowledgeUnavailableError
from app.restaurant.orders.errors import ProductNotOrderableError


router = APIRouter(prefix='/diner', tags=['diner-experience'])
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key',
        min_length=1,
        max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


class ExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    state: str
    code: str
    required_input: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    next_action: str | None


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    amount: Decimal
    currency: str


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ProductSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    category_path: tuple[CategoryResponse, ...]
    price: PriceResponse | None
    orderable: bool
    configuration_available: bool
    configuration_required: bool


class MenuSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    products: tuple[ProductSummaryResponse, ...]


class MenuResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sections: tuple[MenuSectionResponse, ...]


class DinerMenuResponse(BaseModel):
    menus: tuple[MenuResponse, ...]
    experience: ExperienceResponse


class FixedComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    name: str
    quantity: Decimal


class ChoiceOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    name: str
    description: str | None
    quantity: Decimal


class ChoiceGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    min_selections: int
    max_selections: int
    required: bool
    options: tuple[ChoiceOptionResponse, ...]


class ProductDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product: ProductSummaryResponse
    fixed_components: tuple[FixedComponentResponse, ...]
    choice_groups: tuple[ChoiceGroupResponse, ...]
    experience: ExperienceResponse


class AccountLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: int
    order_item_id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    commercial_amount: Decimal


class AccountPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    diner_session_id: int
    display_name: str
    currency: str | None
    eligible_order_ids: tuple[int, ...]
    lines: tuple[AccountLineResponse, ...]
    eligible_total: Decimal
    active_check_id: int | None
    has_active_nonempty_draft: bool
    experience: ExperienceResponse


class OperationalRequestCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_type: Literal[
        'HUMAN_ASSISTANCE',
        'CASH_PAYMENT_ASSISTANCE',
        'INVOICE_ASSISTANCE',
        'PAID_CHECK_PRINT',
    ]
    related_restaurant_check_id: int | None = Field(default=None, gt=0)


class OperationalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_type: str
    status: str
    related_restaurant_check_id: int | None
    created_at: datetime
    resolved_at: datetime | None
    experience: ExperienceResponse


def _operational_experience(request_status: str) -> ExperienceResponse:
    guidance = (
        states.staff_assistance_required()
        if request_status in {'PENDING', 'ACKNOWLEDGED'}
        else states.ok('VIEW_OPERATIONAL_REQUEST')
    )
    return ExperienceResponse.model_validate(guidance, from_attributes=True)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProductUnavailableError):
        guidance = states.from_domain_condition(ProductNotOrderableError())
        return HTTPException(status.HTTP_404_NOT_FOUND, ExperienceResponse.model_validate(guidance).model_dump())
    if isinstance(exc, (OperationalRequestNotFoundError, check_errors.CheckNotFoundError)):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            {'state': 'ACTION_BLOCKED', 'code': 'RESOURCE_NOT_FOUND'},
        )
    if isinstance(exc, OperationalRequestInvalidError):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {'state': 'ACTION_BLOCKED', 'code': 'OPERATIONAL_REQUEST_INVALID'},
        )
    if isinstance(exc, OperationalRequestIdempotencyConflictError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'state': 'ACTION_BLOCKED', 'code': 'IDEMPOTENCY_CONFLICT'},
        )
    if isinstance(exc, KnowledgeNotFoundError):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            {'state': 'PRODUCT_UNAVAILABLE', 'code': 'PRODUCT_UNAVAILABLE'},
        )
    if isinstance(exc, KnowledgeUnavailableError):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {'state': 'ACTION_BLOCKED', 'code': 'RESTAURANT_KNOWLEDGE_UNAVAILABLE'},
        )
    raise exc


@router.get('/menu', response_model=DinerMenuResponse)
async def read_diner_menu(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DinerMenuResponse:
    try:
        menus = await service.get_menu(
            db,
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            location_id=context.location_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
    return DinerMenuResponse(
        menus=tuple(MenuResponse.model_validate(value) for value in menus),
        experience=ExperienceResponse.model_validate(
            states.ok('SHOW_PRODUCT', 'ADD_ITEM'), from_attributes=True
        ),
    )


@router.get('/products/{product_id}', response_model=ProductDetailResponse)
async def read_diner_product(
    product_id: Annotated[int, Path(gt=0)],
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductDetailResponse:
    try:
        detail = await service.get_product_detail(
            db,
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            location_id=context.location_id,
            product_id=product_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
    next_action = 'CONFIGURE_PRODUCT' if detail.product.configuration_required else 'ADD_ITEM'
    return ProductDetailResponse(
        product=ProductSummaryResponse.model_validate(detail.product),
        fixed_components=tuple(
            FixedComponentResponse.model_validate(value) for value in detail.fixed_components
        ),
        choice_groups=tuple(
            ChoiceGroupResponse.model_validate(value) for value in detail.choice_groups
        ),
        experience=ExperienceResponse.model_validate(
            states.ok('ADD_ITEM', 'BROWSE_MENU', next_action=next_action),
            from_attributes=True,
        ),
    )


@router.get('/account-preview', response_model=AccountPreviewResponse)
async def read_account_preview(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccountPreviewResponse:
    try:
        preview = await service.get_account_preview(
            db,
            tenant_id=context.tenant_id,
            location_id=context.location_id,
            diner_session_id=context.diner_session_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
    return AccountPreviewResponse(
        **asdict(preview),
        experience=ExperienceResponse.model_validate(
            states.ok('CREATE_CHECK', 'VIEW_ORDER'), from_attributes=True
        ),
    )


@router.post(
    '/operational-requests',
    response_model=OperationalRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_operational_request(
    payload: OperationalRequestCreate,
    response: Response,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> OperationalRequestResponse:
    try:
        value, replayed = await service.create_operational_request(
            db,
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            location_id=context.location_id,
            resource_id=context.resource_id,
            service_session_id=context.service_session_id,
            diner_session_id=context.diner_session_id,
            request_type=payload.request_type,
            related_restaurant_check_id=payload.related_restaurant_check_id,
            idempotency_key=idempotency_key,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return OperationalRequestResponse(
        **asdict(value),
        experience=_operational_experience(value.status),
    )


@router.get('/operational-requests/{request_id}', response_model=OperationalRequestResponse)
async def read_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperationalRequestResponse:
    try:
        value = await service.get_operational_request(
            db,
            tenant_id=context.tenant_id,
            diner_session_id=context.diner_session_id,
            request_id=request_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
    return OperationalRequestResponse(
        **asdict(value),
        experience=_operational_experience(value.status),
    )
