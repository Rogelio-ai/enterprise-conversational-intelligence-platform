from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.api.diner_deps import DinerAuthenticatedContext, get_diner_authenticated_context
from app.core.middleware import get_correlation_id
from app.restaurant.orders import acceptance, acceptance_errors
from app.restaurant.commercial.errors import CommercialResolutionError
from app.restaurant.orders.errors import DraftNotFoundError


router = APIRouter(tags=['restaurant-orders'])


class ConfirmOrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_draft_version: int = Field(ge=1)
    expected_commercial_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')


class OrderComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    position: int
    source_component_id: int | None
    source_choice_group_id: int | None
    source_choice_option_id: int | None
    choice_group_name: str | None
    product_id: int
    product_name: str
    quantity: Decimal


class OrderPromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    promotion_id: int
    application_order: int
    promotion_name: str
    promotion_type: str
    promotion_value: Decimal
    promotion_currency: str | None
    priority: int
    is_combinable: bool
    calculated_discount: Decimal


class RestaurantOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_order_draft_item_id: int
    product_id: int
    product_name: str
    composition_id: int | None
    quantity: Decimal
    position: int
    source_product_price_id: int
    price_source: str
    unit_price: Decimal
    base_amount: Decimal
    discount_amount: Decimal
    commercial_amount: Decimal
    components: tuple[OrderComponentResponse, ...]
    promotions: tuple[OrderPromotionResponse, ...]


class RestaurantOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    accepted_at: datetime
    source_order_draft_id: int
    accepted_draft_version: int
    currency: str
    tax_mode: str
    rounding_policy: str
    subtotal: Decimal
    total_discount: Decimal
    pre_round_total: Decimal
    rounding_adjustment: Decimal
    payable_total: Decimal
    items: tuple[RestaurantOrderItemResponse, ...]


def _error(exc: Exception, *, diner: bool) -> HTTPException:
    from app.restaurant.checks.errors import OrderingBlockedError
    if isinstance(exc, OrderingBlockedError):
        return HTTPException(status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, acceptance_errors.RestaurantOrderNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'Restaurant Order not found')
    if isinstance(
        exc,
        (
            acceptance_errors.DraftNotConfirmableError,
            acceptance_errors.ConfirmationStaleError,
            acceptance_errors.OrderAlreadyConfirmedError,
            acceptance_errors.ConfirmationConflictError,
            CommercialResolutionError,
        ),
    ):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    # Diner ownership and lifecycle failures are non-disclosing.
    if diner:
        from app.restaurant.service_sessions.errors import DinerAuthorizationError

        if isinstance(exc, DinerAuthorizationError):
            return HTTPException(status.HTTP_404_NOT_FOUND, 'Restaurant Order not found')
        if isinstance(exc, DraftNotFoundError):
            return HTTPException(status.HTTP_404_NOT_FOUND, 'Order Draft not found')
    raise exc


@router.post('/diner/order/confirm', response_model=RestaurantOrderResponse, status_code=status.HTTP_201_CREATED)
async def confirm_diner_order(
    payload: ConfirmOrderRequest,
    response: Response,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[
        str,
        Header(alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[\x21-\x7e]+$'),
    ],
) -> RestaurantOrderResponse:
    try:
        result = await acceptance.confirm_current_order(
            db,
            tenant_id=context.tenant_id,
            diner_session_id=context.diner_session_id,
            conversation_id=context.conversation_id,
            expected_draft_version=payload.expected_draft_version,
            expected_commercial_fingerprint=payload.expected_commercial_fingerprint,
            idempotency_key=idempotency_key,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _error(exc, diner=True) from exc
    response.status_code = status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED
    return RestaurantOrderResponse.model_validate(result.order)


@router.get('/diner/orders', response_model=tuple[RestaurantOrderResponse, ...])
async def list_diner_orders(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> tuple[RestaurantOrderResponse, ...]:
    values = await acceptance.list_diner_orders(
        db, tenant_id=context.tenant_id, diner_session_id=context.diner_session_id
    )
    return tuple(RestaurantOrderResponse.model_validate(value) for value in values)


@router.get('/diner/orders/{order_id}', response_model=RestaurantOrderResponse)
async def get_diner_order(
    order_id: Annotated[int, Path(gt=0)],
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RestaurantOrderResponse:
    try:
        value = await acceptance.get_diner_order(
            db,
            tenant_id=context.tenant_id,
            diner_session_id=context.diner_session_id,
            order_id=order_id,
        )
    except Exception as exc:
        raise _error(exc, diner=True) from exc
    return RestaurantOrderResponse.model_validate(value)


@router.get('/restaurant-orders', response_model=tuple[RestaurantOrderResponse, ...])
async def list_staff_orders(
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_order.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> tuple[RestaurantOrderResponse, ...]:
    values = await acceptance.list_staff_orders(db, tenant_id=context.tenant_id)
    return tuple(RestaurantOrderResponse.model_validate(value) for value in values)


@router.get('/restaurant-orders/{order_id}', response_model=RestaurantOrderResponse)
async def get_staff_order(
    order_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_order.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RestaurantOrderResponse:
    try:
        value = await acceptance.get_staff_order(
            db, tenant_id=context.tenant_id, order_id=order_id
        )
    except Exception as exc:
        raise _error(exc, diner=False) from exc
    return RestaurantOrderResponse.model_validate(value)
