from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.restaurant.commercial import errors as commercial_errors
from app.restaurant.commercial import service as commercial_service
from app.restaurant.orders import errors, service


router = APIRouter(tags=['order-drafts'])


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact quantities')
    return value


ExactPositiveQuantity = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(gt=0, allow_inf_nan=False),
]


def _quantity(value: Decimal) -> Decimal:
    try:
        return service.validate_quantity(value)
    except errors.InvalidDraftQuantityError as exc:
        raise ValueError(str(exc)) from exc


class AddItemRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    product_id: int = Field(gt=0)
    quantity: ExactPositiveQuantity
    expected_version: int = Field(ge=1)

    _validate_quantity = field_validator('quantity')(_quantity)


class SetItemQuantityRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    quantity: ExactPositiveQuantity
    expected_version: int = Field(ge=1)

    _validate_quantity = field_validator('quantity')(_quantity)


class ReplaceGroupSelectionsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    option_ids: list[int] = Field(default_factory=list)
    expected_version: int = Field(ge=1)

    @field_validator('option_ids')
    @classmethod
    def validate_option_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError('Choice option IDs must be positive')
        if len(values) != len(set(values)):
            raise ValueError('Choice option IDs must be distinct')
        return values


class DraftIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    group_id: int | None
    option_id: int | None
    product_id: int | None


class FixedComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    quantity: Decimal


class SelectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: int
    group_name: str
    choice_option_id: int
    selected_product_id: int
    selected_product_name: str


class MissingChoiceGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: int
    group_name: str
    min_selections: int
    max_selections: int
    selected_option_ids: tuple[int, ...]


class DraftItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    product_id: int
    product_name: str
    composition_id: int | None
    quantity: Decimal
    position: int
    readiness: str
    issues: tuple[DraftIssueResponse, ...]
    selections: tuple[SelectionResponse, ...]
    missing_choice_groups: tuple[MissingChoiceGroupResponse, ...]
    fixed_components: tuple[FixedComponentResponse, ...]


class DraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_id: int
    tenant_id: int
    organization_id: int
    location_id: int
    conversation_id: int
    version: int
    readiness: str
    items: tuple[DraftItemResponse, ...]


class AppliedPromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    promotion_id: int
    name: str
    promotion_type: str
    promotion_value: Decimal
    currency: str | None
    priority: int
    is_combinable: bool
    calculated_discount: Decimal


class CheckoutPreviewLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_item_id: int
    product_id: int
    product_name: str
    composition_id: int | None
    quantity: Decimal
    price_id: int
    price_source: str
    unit_price: Decimal
    base_amount: Decimal
    applied_promotions: tuple[AppliedPromotionResponse, ...]
    discount_amount: Decimal
    commercial_amount: Decimal


class CheckoutPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    draft_id: int
    draft_version: int
    tenant_id: int
    organization_id: int
    location_id: int
    resolved_at: datetime
    currency: str
    tax_mode: str
    lines: tuple[CheckoutPreviewLineResponse, ...]
    subtotal: Decimal
    total_discount: Decimal
    pre_round_total: Decimal
    rounding_adjustment: Decimal
    payable_total: Decimal
    commercial_fingerprint: str


def _response(value) -> DraftResponse:
    return DraftResponse.model_validate(value)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (errors.DraftNotFoundError, errors.DraftItemNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, (errors.InvalidDraftQuantityError, errors.InvalidDraftSelectionError)):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    if isinstance(
        exc,
        (
            errors.DraftContextError,
            errors.DraftNotMutableError,
            errors.ProductNotOrderableError,
            errors.InvalidDraftCompositionError,
            errors.DraftConcurrencyConflictError,
        ),
    ):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


def _translate_commercial_error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.DraftNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, commercial_errors.CommercialResolutionError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _translate_error(exc)


@router.post(
    '/conversations/{conversation_id}/order-draft',
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_order_draft(
    conversation_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        value = await service.get_or_create_draft(
            db,
            tenant_id=context.tenant_id,
            conversation_id=conversation_id,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)


@router.get('/conversations/{conversation_id}/order-draft', response_model=DraftResponse)
async def get_conversation_order_draft(
    conversation_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        value = await service.get_draft_for_conversation(
            db,
            tenant_id=context.tenant_id,
            conversation_id=conversation_id,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)


@router.get('/order-drafts/{draft_id}', response_model=DraftResponse)
async def get_order_draft(
    draft_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        value = await service.get_draft(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft_id,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)


@router.get(
    '/order-drafts/{draft_id}/checkout-preview',
    response_model=CheckoutPreviewResponse,
)
async def get_order_draft_checkout_preview(
    draft_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutPreviewResponse:
    try:
        value = await commercial_service.resolve_checkout_preview(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft_id,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_commercial_error(exc) from exc
    return CheckoutPreviewResponse.model_validate(value)


@router.post(
    '/order-drafts/{draft_id}/items',
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_order_draft_item(
    draft_id: Annotated[int, Path(gt=0)],
    payload: AddItemRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        value = await service.add_item(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            expected_version=payload.expected_version,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)


@router.patch('/order-drafts/{draft_id}/items/{item_id}', response_model=DraftResponse)
async def patch_order_draft_item(
    draft_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
    payload: SetItemQuantityRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        value = await service.set_item_quantity(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft_id,
            item_id=item_id,
            quantity=payload.quantity,
            expected_version=payload.expected_version,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)


@router.delete('/order-drafts/{draft_id}/items/{item_id}', response_model=DraftResponse)
async def delete_order_draft_item(
    draft_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    expected_version: int = Query(ge=1),
) -> DraftResponse:
    try:
        value = await service.remove_item(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft_id,
            item_id=item_id,
            expected_version=expected_version,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)


@router.put(
    '/order-drafts/{draft_id}/items/{item_id}/choice-groups/{group_id}',
    response_model=DraftResponse,
)
async def put_order_draft_group_selections(
    draft_id: Annotated[int, Path(gt=0)],
    item_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    payload: ReplaceGroupSelectionsRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('order_draft.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        value = await service.replace_group_selections(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft_id,
            item_id=item_id,
            group_id=group_id,
            option_ids=tuple(payload.option_ids),
            expected_version=payload.expected_version,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    return _response(value)
