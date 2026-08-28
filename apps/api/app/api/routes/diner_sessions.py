from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diner_deps import DinerAuthenticatedContext, get_diner_authenticated_context
from app.api.deps import get_db
from app.api.routes.conversations import ConversationResponse, MessageResponse, validate_language
from app.api.routes.order_drafts import (
    AddItemRequest,
    CheckoutPreviewResponse,
    DraftResponse,
    ReplaceGroupSelectionsRequest,
    SetItemQuantityRequest,
)
from app.core.middleware import get_correlation_id
from app.core.security import create_diner_access_token
from app.models import DinerSession
from app.restaurant.commercial import errors as commercial_errors
from app.restaurant.commercial import service as commercial_service
from app.restaurant.conversations import service as conversation_service
from app.restaurant.orders import errors as draft_errors
from app.restaurant.orders import service as draft_service
from app.restaurant.service_sessions import errors, service


router = APIRouter(tags=['diner'])


class DinerJoinRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    join_context_key: str = Field(min_length=32, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    access_code: str = Field(pattern=r'^\d{4}$')

    @field_validator('display_name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('display_name cannot be blank')
        return normalized


class DinerJoinResponse(BaseModel):
    diner_session_id: int
    service_session_id: int
    conversation_id: int
    display_name: str
    customer_id: int | None
    access_token: str
    token_type: str = 'bearer'
    expires_at: datetime
    expires_in: int


class DinerSessionResponse(BaseModel):
    id: int
    service_session_id: int
    resource_id: int
    conversation_id: int
    display_name: str
    customer_id: int | None
    status: str
    joined_at: datetime
    ended_at: datetime | None


class DinerMessageCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    modality: Literal['TEXT', 'VOICE', 'TOUCH']
    content_text: str = Field(min_length=1, max_length=10_000)
    language: str | None = Field(default=None, max_length=63)
    language_source: Literal['DECLARED', 'DETECTED', 'INHERITED'] | None = None

    _language = field_validator('language')(validate_language)

    @field_validator('content_text')
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Message content cannot be blank')
        return value

    @model_validator(mode='after')
    def validate_language_pair(self):
        if (self.language is None) != (self.language_source is None):
            raise ValueError('language and language_source must be supplied together')
        return self


def _diner_response(value: DinerSession) -> DinerSessionResponse:
    return DinerSessionResponse(
        id=value.id,
        service_session_id=value.service_session_id,
        resource_id=value.resource_id,
        conversation_id=value.conversation_id,
        display_name=value.display_name,
        customer_id=value.customer_id,
        status=value.status,
        joined_at=value.joined_at,
        ended_at=value.ended_at,
    )


def _join_error(exc: Exception) -> HTTPException:
    if isinstance(exc, errors.JoinLockedError):
        return HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            'Diner join is temporarily unavailable',
            headers={'Retry-After': str(exc.retry_after)},
        )
    if isinstance(exc, errors.InvalidJoinError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid diner join credentials')
    if isinstance(exc, errors.CapacityConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, errors.DuplicateDinerIdentityError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


def _conversation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (conversation_service.ConversationNotFoundError, conversation_service.ConversationContextError, errors.DinerAuthorizationError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'Conversation not found')
    if isinstance(exc, conversation_service.ConversationClosedError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


def _draft_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (draft_errors.DraftNotFoundError, draft_errors.DraftItemNotFoundError, errors.DinerAuthorizationError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'Order Draft not found')
    if isinstance(exc, (draft_errors.InvalidDraftQuantityError, draft_errors.InvalidDraftSelectionError)):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    if isinstance(exc, (draft_errors.DraftContextError, draft_errors.DraftNotMutableError, draft_errors.ProductNotOrderableError, draft_errors.InvalidDraftCompositionError, draft_errors.DraftConcurrencyConflictError, commercial_errors.CommercialResolutionError)):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


@router.post('/diner-sessions/join', response_model=DinerJoinResponse, status_code=status.HTTP_201_CREATED)
async def join_diner(
    payload: DinerJoinRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DinerJoinResponse:
    try:
        joined = await service.join_diner(
            db,
            settings=request.app.state.settings,
            join_context_key=payload.join_context_key,
            access_code=payload.access_code,
            display_name=payload.display_name,
            email=payload.email,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _join_error(exc) from exc
    diner = joined.diner
    token, expires_at = create_diner_access_token(
        settings=request.app.state.settings,
        diner_session_id=diner.id,
        tenant_id=diner.tenant_id,
        service_session_id=diner.service_session_id,
    )
    return DinerJoinResponse(
        diner_session_id=diner.id,
        service_session_id=diner.service_session_id,
        conversation_id=diner.conversation_id,
        display_name=diner.display_name,
        customer_id=diner.customer_id,
        access_token=token,
        expires_at=expires_at,
        expires_in=request.app.state.settings.diner_access_token_ttl_minutes * 60,
    )


@router.get('/diner-session', response_model=DinerSessionResponse)
async def get_diner_session(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DinerSessionResponse:
    diner = await service.validate_diner_authority(
        db,
        tenant_id=context.tenant_id,
        diner_session_id=context.diner_session_id,
        conversation_id=context.conversation_id,
    )
    return _diner_response(diner)


@router.post('/diner-session/end', response_model=DinerSessionResponse)
async def end_diner_session(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DinerSessionResponse:
    value = await service.end_diner_session(
        db,
        tenant_id=context.tenant_id,
        service_session_id=context.service_session_id,
        diner_session_id=context.diner_session_id,
        correlation_id=get_correlation_id(),
    )
    return _diner_response(value)


@router.get('/diner/conversation', response_model=ConversationResponse)
async def get_diner_conversation(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        return await conversation_service.get_conversation(
            db,
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            owner_diner_session_id=context.diner_session_id,
        )
    except Exception as exc:
        raise _conversation_error(exc) from exc


@router.post('/diner/conversation/messages', response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def append_diner_message(
    payload: DinerMessageCreate,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        return await conversation_service.append_message(
            db,
            tenant_id=context.tenant_id,
            conversation_id=context.conversation_id,
            participant_id=context.conversation_participant_id,
            owner_diner_session_id=context.diner_session_id,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _conversation_error(exc) from exc


def _owner(context: DinerAuthenticatedContext) -> dict[str, int]:
    return {
        'owner_diner_session_id': context.diner_session_id,
        'owned_conversation_id': context.conversation_id,
    }


@router.post('/diner/order-draft', response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_diner_draft(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        return DraftResponse.model_validate(await draft_service.get_or_create_draft(db, tenant_id=context.tenant_id, conversation_id=context.conversation_id, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc


@router.get('/diner/order-draft', response_model=DraftResponse)
async def get_diner_draft(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        return DraftResponse.model_validate(await draft_service.get_draft_for_conversation(db, tenant_id=context.tenant_id, conversation_id=context.conversation_id, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc


async def _owned_draft(db: AsyncSession, context: DinerAuthenticatedContext):
    return await draft_service.get_draft_for_conversation(
        db,
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
        correlation_id=get_correlation_id(),
        **_owner(context),
    )


@router.post('/diner/order-draft/items', response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def add_diner_draft_item(
    payload: AddItemRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        draft = await _owned_draft(db, context)
        return DraftResponse.model_validate(await draft_service.add_item(db, tenant_id=context.tenant_id, draft_id=draft.draft_id, product_id=payload.product_id, quantity=payload.quantity, expected_version=payload.expected_version, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc


@router.put('/diner/order-draft/items/{item_id}/quantity', response_model=DraftResponse)
async def set_diner_item_quantity(
    item_id: Annotated[int, Path(gt=0)],
    payload: SetItemQuantityRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        draft = await _owned_draft(db, context)
        return DraftResponse.model_validate(await draft_service.set_item_quantity(db, tenant_id=context.tenant_id, draft_id=draft.draft_id, item_id=item_id, quantity=payload.quantity, expected_version=payload.expected_version, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc


@router.delete('/diner/order-draft/items/{item_id}', response_model=DraftResponse)
async def remove_diner_item(
    item_id: Annotated[int, Path(gt=0)],
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    expected_version: int = Query(ge=1),
) -> DraftResponse:
    try:
        draft = await _owned_draft(db, context)
        return DraftResponse.model_validate(await draft_service.remove_item(db, tenant_id=context.tenant_id, draft_id=draft.draft_id, item_id=item_id, expected_version=expected_version, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc


@router.put('/diner/order-draft/items/{item_id}/choice-groups/{group_id}', response_model=DraftResponse)
async def replace_diner_selections(
    item_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    payload: ReplaceGroupSelectionsRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftResponse:
    try:
        draft = await _owned_draft(db, context)
        return DraftResponse.model_validate(await draft_service.replace_group_selections(db, tenant_id=context.tenant_id, draft_id=draft.draft_id, item_id=item_id, group_id=group_id, option_ids=tuple(payload.option_ids), expected_version=payload.expected_version, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc


@router.get('/diner/checkout-preview', response_model=CheckoutPreviewResponse)
async def get_diner_checkout_preview(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutPreviewResponse:
    try:
        draft = await _owned_draft(db, context)
        return CheckoutPreviewResponse.model_validate(await commercial_service.resolve_checkout_preview(db, tenant_id=context.tenant_id, draft_id=draft.draft_id, correlation_id=get_correlation_id(), **_owner(context)))
    except Exception as exc:
        raise _draft_error(exc) from exc
