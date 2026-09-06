from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.diner_deps import DinerAuthenticatedContext, get_diner_authenticated_context
from app.api.routes.conversations import validate_language
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
from app.restaurant.intelligence.contracts import RestaurantIntentCode
from app.restaurant.intelligence.orchestration import (
    ConversationActionCommand,
    DinerOrchestrationContext,
    orchestrate_action,
)
from app.restaurant.conversations import service as conversation_service
from app.restaurant.orders.errors import ProductNotOrderableError
from app.models import ConversationParticipant


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


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact quantities')
    return value


ExactQuantity = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=0)]


class ConversationActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    modality: Literal['TEXT', 'VOICE', 'TOUCH']
    content_text: str = Field(min_length=1, max_length=10_000)
    intent_code: RestaurantIntentCode
    operation: Literal['ADD', 'CONFIGURE', 'MODIFY', 'REMOVE'] | None = None
    reference_text: str | None = Field(default=None, min_length=1, max_length=200)
    product_id: int | None = Field(default=None, gt=0)
    quantity: ExactQuantity | None = None
    draft_item_id: int | None = Field(default=None, gt=0)
    choice_group_id: int | None = Field(default=None, gt=0)
    choice_reference_text: str | None = Field(default=None, min_length=1, max_length=200)
    option_ids: list[int] = Field(default_factory=list)
    expected_draft_version: int | None = Field(default=None, ge=1)
    expected_commercial_fingerprint: str | None = Field(
        default=None, pattern=r'^[0-9a-f]{64}$'
    )
    check_id: int | None = Field(default=None, gt=0)
    check_scope: Literal['INDIVIDUAL', 'GLOBAL_TABLE', 'SELECTED'] | None = None
    selected_diner_session_ids: list[int] = Field(default_factory=list)
    payment_method: Literal['CASH', 'CARD', 'TRANSFER'] | None = None
    continuation_decision: Literal['YES', 'NO'] | None = None
    expected_check_version: int | None = Field(default=None, ge=1)
    language: str | None = Field(default=None, max_length=63)
    language_source: Literal['DECLARED', 'DETECTED', 'INHERITED'] | None = None

    _language = field_validator('language')(validate_language)

    @field_validator('content_text')
    @classmethod
    def content_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('content_text cannot be blank')
        return value

    @field_validator('option_ids', 'selected_diner_session_ids')
    @classmethod
    def identifiers_are_distinct_positive(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values) or len(values) != len(set(values)):
            raise ValueError('Identifiers must be distinct positive integers')
        return values

    @model_validator(mode='after')
    def language_metadata_is_paired(self):
        if (self.language is None) != (self.language_source is None):
            raise ValueError('language and language_source must be supplied together')
        return self


class ConversationMessageReference(BaseModel):
    id: int
    sequence_number: int
    modality: str
    content_text: str


class ConversationActionResponse(BaseModel):
    source_message: ConversationMessageReference
    response_message: ConversationMessageReference
    intent_code: RestaurantIntentCode
    experience: ExperienceResponse
    authoritative_data: Any = None
    replayed: bool = False


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


@router.post('/conversation/actions', response_model=ConversationActionResponse)
async def execute_conversation_action(
    payload: ConversationActionRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> ConversationActionResponse:
    source = await conversation_service.append_message(
        db,
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
        participant_id=context.conversation_participant_id,
        owner_diner_session_id=context.diner_session_id,
        modality=payload.modality,
        content_text=payload.content_text,
        language=payload.language,
        language_source=payload.language_source,
    )
    source_reference = ConversationMessageReference.model_validate(
        source, from_attributes=True
    )
    result = await orchestrate_action(
        db,
        context=DinerOrchestrationContext(
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            location_id=context.location_id,
            resource_id=context.resource_id,
            service_session_id=context.service_session_id,
            diner_session_id=context.diner_session_id,
            conversation_id=context.conversation_id,
            correlation_id=get_correlation_id(),
        ),
        command=ConversationActionCommand(
            intent_code=payload.intent_code,
            idempotency_key=idempotency_key,
            operation=payload.operation,
            reference_text=payload.reference_text,
            product_id=payload.product_id,
            quantity=payload.quantity,
            draft_item_id=payload.draft_item_id,
            choice_group_id=payload.choice_group_id,
            choice_reference_text=payload.choice_reference_text,
            option_ids=tuple(payload.option_ids),
            expected_draft_version=payload.expected_draft_version,
            expected_commercial_fingerprint=payload.expected_commercial_fingerprint,
            check_id=payload.check_id,
            check_scope=payload.check_scope,
            selected_diner_session_ids=tuple(payload.selected_diner_session_ids),
            payment_method=payload.payment_method,
            continuation_decision=payload.continuation_decision,
            expected_check_version=payload.expected_check_version,
            language=payload.language,
        ),
    )
    waiter_id = await db.scalar(
        select(ConversationParticipant.id).where(
            ConversationParticipant.tenant_id == context.tenant_id,
            ConversationParticipant.conversation_id == context.conversation_id,
            ConversationParticipant.participant_type == 'DIGITAL_WAITER',
        )
    )
    if waiter_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {'state': 'ACTION_BLOCKED', 'code': 'DIGITAL_WAITER_PARTICIPANT_MISSING'},
        )
    response_message = await conversation_service.append_message(
        db,
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
        participant_id=waiter_id,
        modality='TEXT',
        content_text=json.dumps(
            {
                'state': result.experience.state.value,
                'code': result.experience.code,
                'next_action': result.experience.next_action,
            },
            sort_keys=True,
            separators=(',', ':'),
        ),
        language=payload.language,
        language_source='INHERITED' if payload.language is not None else None,
    )
    return ConversationActionResponse(
        source_message=source_reference,
        response_message=ConversationMessageReference.model_validate(
            response_message, from_attributes=True
        ),
        intent_code=payload.intent_code,
        experience=ExperienceResponse.model_validate(result.experience, from_attributes=True),
        authoritative_data=result.authoritative_data,
        replayed=result.replayed,
    )
