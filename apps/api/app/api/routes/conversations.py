from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.models import Conversation, ConversationMessage, ConversationParticipant
from app.restaurant.conversations import service

router = APIRouter(prefix='/conversations', tags=['conversations'])
logger = logging.getLogger('ecip.conversations')

Channel = Literal['IN_PERSON_DIGITAL', 'PHONE', 'WHATSAPP', 'WEB_CHAT', 'MOBILE_APP']
Modality = Literal['TEXT', 'VOICE', 'TOUCH']
ParticipantType = Literal['CUSTOMER', 'DIGITAL_WAITER', 'HUMAN_STAFF', 'SYSTEM']
LanguageSource = Literal['DECLARED', 'DETECTED', 'INHERITED']
_LANGUAGE_TAG = re.compile(r'^[A-Za-z0-9]{1,8}(?:-[A-Za-z0-9]{1,8})*$')


def validate_language(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > 63 or not value.isascii() or _LANGUAGE_TAG.fullmatch(value) is None:
        raise ValueError('Language must be a valid BCP-47-style tag')
    return value


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organization_id: int = Field(gt=0)
    location_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    channel: Channel
    default_language: str | None = Field(default=None, max_length=63)

    _language = field_validator('default_language')(validate_language)


class ConversationPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    location_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    default_language: str | None = Field(default=None, max_length=63)
    status: Literal['CLOSED'] | None = None

    _language = field_validator('default_language')(validate_language)

    @model_validator(mode='after')
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        for name in self.model_fields_set - {'default_language'}:
            if getattr(self, name) is None:
                raise ValueError(f'{name} cannot be null')
        return self


class ParticipantCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    participant_type: ParticipantType
    customer_id: int | None = Field(default=None, gt=0)
    tenant_membership_id: int | None = Field(default=None, gt=0)
    preferred_language: str | None = Field(default=None, max_length=63)

    _language = field_validator('preferred_language')(validate_language)

    @model_validator(mode='after')
    def validate_references(self):
        if self.participant_type == 'CUSTOMER':
            valid = self.tenant_membership_id is None
        elif self.participant_type == 'HUMAN_STAFF':
            valid = self.customer_id is None and self.tenant_membership_id is not None
        else:
            valid = self.customer_id is None and self.tenant_membership_id is None
        if not valid:
            raise ValueError('Participant references do not match participant_type')
        return self


class ParticipantPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer_id: int | None = Field(default=None, gt=0)
    preferred_language: str | None = Field(default=None, max_length=63)

    _language = field_validator('preferred_language')(validate_language)

    @model_validator(mode='after')
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if 'customer_id' in self.model_fields_set and self.customer_id is None:
            raise ValueError('customer_id cannot be null')
        return self


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    participant_id: int = Field(gt=0)
    modality: Modality
    content_text: str = Field(min_length=1, max_length=10_000)
    language: str | None = Field(default=None, max_length=63)
    language_source: LanguageSource | None = None

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


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    conversation_id: int
    participant_type: str
    customer_id: int | None
    tenant_membership_id: int | None
    preferred_language: str | None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    conversation_id: int
    participant_id: int
    sequence_number: int
    modality: str
    content_text: str
    language: str | None
    language_source: str | None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int | None
    resource_id: int | None
    channel: str
    status: str
    default_language: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationResponse):
    participants: list[ParticipantResponse]


class ConversationList(BaseModel):
    items: list[ConversationResponse]
    limit: int
    offset: int


class MessageList(BaseModel):
    items: list[MessageResponse]
    limit: int
    offset: int


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.ConversationNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'Conversation not found')
    if isinstance(exc, service.ConversationContextError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, service.ConversationClosedError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, service.ConversationConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


@router.get('', response_model=ConversationList)
async def list_conversations(
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    channel: Channel | None = Query(default=None),
    status_filter: Literal['ACTIVE', 'CLOSED'] | None = Query(default=None, alias='status'),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConversationList:
    query = select(Conversation).where(Conversation.tenant_id == context.tenant_id)
    for column, value in (
        (Conversation.organization_id, organization_id),
        (Conversation.location_id, location_id),
        (Conversation.channel, channel),
        (Conversation.status, status_filter),
    ):
        if value is not None:
            query = query.where(column == value)
    result = await db.execute(query.order_by(Conversation.id).limit(limit).offset(offset))
    return ConversationList(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('', response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Conversation:
    try:
        conversation = await service.create_conversation(
            db, tenant_id=context.tenant_id, **payload.model_dump()
        )
    except Exception as exc:
        raise _translate_error(exc) from exc
    logger.info('Conversation created', extra={'event': 'conversation_created', 'operation': 'create', 'tenant_id': context.tenant_id, 'organization_id': conversation.organization_id, 'conversation_id': conversation.id, 'location_id': conversation.location_id, 'resource_id': conversation.resource_id, 'channel': conversation.channel, 'correlation_id': get_correlation_id()})
    return conversation


@router.get('/{conversation_id}', response_model=ConversationDetail)
async def get_conversation(
    conversation_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationDetail:
    try:
        conversation = await service.get_conversation(db, tenant_id=context.tenant_id, conversation_id=conversation_id)
    except Exception as exc:
        raise _translate_error(exc) from exc
    result = await db.execute(select(ConversationParticipant).where(ConversationParticipant.tenant_id == context.tenant_id, ConversationParticipant.conversation_id == conversation_id).order_by(ConversationParticipant.id))
    return ConversationDetail(**ConversationResponse.model_validate(conversation).model_dump(), participants=list(result.scalars().all()))


@router.patch('/{conversation_id}', response_model=ConversationResponse)
async def patch_conversation(
    conversation_id: Annotated[int, Path(gt=0)],
    payload: ConversationPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Conversation:
    try:
        conversation = await service.update_conversation(db, tenant_id=context.tenant_id, conversation_id=conversation_id, updates=payload.model_dump(exclude_unset=True))
    except Exception as exc:
        raise _translate_error(exc) from exc
    logger.info('Conversation updated', extra={'event': 'conversation_updated', 'operation': 'update', 'tenant_id': context.tenant_id, 'conversation_id': conversation.id, 'location_id': conversation.location_id, 'resource_id': conversation.resource_id, 'outcome': conversation.status, 'correlation_id': get_correlation_id()})
    return conversation


@router.post('/{conversation_id}/participants', response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED)
async def create_participant(
    conversation_id: Annotated[int, Path(gt=0)],
    payload: ParticipantCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationParticipant:
    try:
        participant = await service.add_participant(db, tenant_id=context.tenant_id, conversation_id=conversation_id, **payload.model_dump())
    except Exception as exc:
        raise _translate_error(exc) from exc
    logger.info('Conversation participant added', extra={'event': 'conversation_participant_added', 'operation': 'create', 'tenant_id': context.tenant_id, 'conversation_id': conversation_id, 'participant_id': participant.id, 'correlation_id': get_correlation_id()})
    return participant


@router.patch('/{conversation_id}/participants/{participant_id}', response_model=ParticipantResponse)
async def patch_participant(
    conversation_id: Annotated[int, Path(gt=0)],
    participant_id: Annotated[int, Path(gt=0)],
    payload: ParticipantPatch,
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationParticipant:
    try:
        return await service.update_participant(db, tenant_id=context.tenant_id, conversation_id=conversation_id, participant_id=participant_id, updates=payload.model_dump(exclude_unset=True))
    except Exception as exc:
        raise _translate_error(exc) from exc


@router.post('/{conversation_id}/messages', response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: Annotated[int, Path(gt=0)],
    payload: MessageCreate,
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationMessage:
    try:
        message = await service.append_message(db, tenant_id=context.tenant_id, conversation_id=conversation_id, **payload.model_dump())
    except Exception as exc:
        raise _translate_error(exc) from exc
    logger.info('Conversation message appended', extra={'event': 'conversation_message_appended', 'operation': 'create', 'tenant_id': context.tenant_id, 'conversation_id': conversation_id, 'participant_id': message.participant_id, 'message_id': message.id, 'modality': message.modality, 'language': message.language, 'sequence_number': message.sequence_number, 'correlation_id': get_correlation_id()})
    return message


@router.get('/{conversation_id}/messages', response_model=MessageList)
async def list_messages(
    conversation_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('conversation.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MessageList:
    try:
        await service.get_conversation(db, tenant_id=context.tenant_id, conversation_id=conversation_id)
    except Exception as exc:
        raise _translate_error(exc) from exc
    result = await db.execute(select(ConversationMessage).where(ConversationMessage.tenant_id == context.tenant_id, ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.sequence_number).limit(limit).offset(offset))
    return MessageList(items=list(result.scalars().all()), limit=limit, offset=offset)
