from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_location_permission
from app.models import InternalOperationalMessage
from app.restaurant import internal_messages as service


router = APIRouter(
    prefix='/locations/{location_id}/internal-messages', tags=['internal-messages'],
)
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key', min_length=1, max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


class CreateMessageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    recipient_membership_id: int = Field(gt=0)
    type: Literal['TABLE_PREPARATION_REQUEST']
    text: str = Field(min_length=1, max_length=2000)
    party_size: int = Field(gt=0, le=999)


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    content: str = Field(min_length=1, max_length=4000)


class ReadyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    prepared_table_resource_id: int | None = Field(default=None, gt=0)


class PersonResponse(BaseModel):
    membership_id: int
    display_name: str
    email: str | None


class MessageSummaryResponse(BaseModel):
    id: int
    organization_id: int
    location_id: int
    creator: PersonResponse
    recipient: PersonResponse
    type: str
    text: str
    party_size: int
    status: str
    entered_at: datetime | None
    ready_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class MessageListResponse(BaseModel):
    items: list[MessageSummaryResponse]
    limit: int
    offset: int


class ResponseResponse(BaseModel):
    id: int
    sequence: int
    author: PersonResponse
    content: str
    created_at: datetime


class HistoryResponse(BaseModel):
    sequence: int
    event_type: str
    actor: PersonResponse
    response_id: int | None
    occurred_at: datetime


class PreparedTableMemberResponse(BaseModel):
    resource_id: int
    code: str
    name: str
    physical_capacity: int


class PreparedTableResponse(PreparedTableMemberResponse):
    is_group_representative: bool
    group_id: int | None
    members: list[PreparedTableMemberResponse]
    derived_group_capacity: int | None


class MessageDetailResponse(MessageSummaryResponse):
    enterado: dict[str, object] | None
    ready: dict[str, object] | None
    responses: list[ResponseResponse]
    history: list[HistoryResponse]
    prepared_table: PreparedTableResponse | None
    allowed_actions: list[str]


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.InternalMessageNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, service.InternalMessageForbiddenError):
        return HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    if isinstance(exc, service.InternalMessageIdempotencyConflictError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': 'INTERNAL_MESSAGE_IDEMPOTENCY_CONFLICT', 'message': str(exc)},
        )
    if isinstance(exc, service.InternalMessageConflictError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': 'INTERNAL_MESSAGE_CONFLICT', 'message': str(exc)},
        )
    if isinstance(exc, ValueError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    raise exc


async def _summary(
    db: AsyncSession, value: InternalOperationalMessage,
) -> MessageSummaryResponse:
    people = await service.people_for(
        db, tenant_id=value.tenant_id,
        membership_ids={value.creator_membership_id, value.recipient_membership_id},
    )
    return MessageSummaryResponse(
        id=value.id,
        organization_id=value.organization_id,
        location_id=value.location_id,
        creator=PersonResponse(**people[value.creator_membership_id]),
        recipient=PersonResponse(**people[value.recipient_membership_id]),
        type=value.message_type,
        text=value.text,
        party_size=value.party_size,
        status=value.status,
        entered_at=value.entered_at,
        ready_at=value.ready_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
        version=value.version,
    )


async def _detail(
    db: AsyncSession, value: InternalOperationalMessage, membership_id: int,
) -> MessageDetailResponse:
    summary = await _summary(db, value)
    responses = await service.responses_for(db, message_id=value.id)
    history = await service.history_for(db, message_id=value.id)
    member_ids = {
        value.creator_membership_id, value.recipient_membership_id,
        *(item.author_membership_id for item in responses),
        *(item.actor_membership_id for item in history),
    }
    people = await service.people_for(
        db, tenant_id=value.tenant_id, membership_ids=member_ids,
    )
    actions: list[str] = []
    if membership_id == value.creator_membership_id:
        actions.append('RESPOND')
    if membership_id == value.recipient_membership_id and value.status != 'READY':
        if value.entered_at is None:
            actions.append('ENTERADO')
        else:
            actions.extend(('RESPOND', 'READY'))
    actions = list(dict.fromkeys(actions))
    return MessageDetailResponse(
        **summary.model_dump(),
        enterado=(
            None if value.entered_at is None else {
                'membership_id': value.entered_by_membership_id,
                'entered_at': value.entered_at,
            }
        ),
        ready=(
            None if value.ready_at is None else {
                'membership_id': value.ready_by_membership_id,
                'ready_at': value.ready_at,
            }
        ),
        responses=[ResponseResponse(
            id=item.id,
            sequence=item.sequence,
            author=PersonResponse(**people[item.author_membership_id]),
            content=item.content,
            created_at=item.created_at,
        ) for item in responses],
        history=[HistoryResponse(
            sequence=item.event_sequence,
            event_type=item.event_type,
            actor=PersonResponse(**people[item.actor_membership_id]),
            response_id=item.response_id,
            occurred_at=item.occurred_at,
        ) for item in history],
        prepared_table=await service.prepared_table_projection(db, message=value),
        allowed_actions=actions,
    )


@router.post('', response_model=MessageDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: CreateMessageRequest,
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.send')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> MessageDetailResponse:
    try:
        value = await service.create_message(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            creator_membership_id=context.membership_id,
            recipient_membership_id=payload.recipient_membership_id,
            message_type=payload.type,
            text=payload.text,
            party_size=payload.party_size,
            idempotency_key=idempotency_key,
        )
        return await _detail(db, value, context.membership_id)
    except Exception as exc:
        raise _error(exc) from exc


async def _list_box(
    *, box: Literal['sent', 'inbox'], location_id: int,
    context: AuthenticatedContext, db: AsyncSession, limit: int, offset: int,
) -> MessageListResponse:
    values = await service.list_messages(
        db, tenant_id=context.tenant_id, location_id=location_id,
        membership_id=context.membership_id, box=box, limit=limit, offset=offset,
    )
    return MessageListResponse(
        items=[await _summary(db, value) for value in values],
        limit=limit, offset=offset,
    )


@router.get('/sent', response_model=MessageListResponse)
async def list_sent(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessageListResponse:
    return await _list_box(
        box='sent', location_id=location_id, context=context,
        db=db, limit=limit, offset=offset,
    )


@router.get('/inbox', response_model=MessageListResponse)
async def list_inbox(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessageListResponse:
    return await _list_box(
        box='inbox', location_id=location_id, context=context,
        db=db, limit=limit, offset=offset,
    )


@router.get('/{message_id}', response_model=MessageDetailResponse)
async def read_message(
    location_id: Annotated[int, Path(gt=0)],
    message_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageDetailResponse:
    try:
        value = await service.get_message(
            db, tenant_id=context.tenant_id, location_id=location_id,
            message_id=message_id, membership_id=context.membership_id,
        )
        return await _detail(db, value, context.membership_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/{message_id}/enterado', response_model=MessageDetailResponse)
async def enter_message(
    location_id: Annotated[int, Path(gt=0)],
    message_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.respond')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageDetailResponse:
    try:
        value = await service.enter_message(
            db, tenant_id=context.tenant_id, location_id=location_id,
            message_id=message_id, membership_id=context.membership_id,
        )
        return await _detail(db, value, context.membership_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/{message_id}/responses', response_model=MessageDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def respond(
    payload: RespondRequest,
    location_id: Annotated[int, Path(gt=0)],
    message_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.respond')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> MessageDetailResponse:
    try:
        await service.add_response(
            db, tenant_id=context.tenant_id, location_id=location_id,
            message_id=message_id, membership_id=context.membership_id,
            content=payload.content, idempotency_key=idempotency_key,
        )
        value = await service.get_message(
            db, tenant_id=context.tenant_id, location_id=location_id,
            message_id=message_id, membership_id=context.membership_id,
        )
        return await _detail(db, value, context.membership_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/{message_id}/ready', response_model=MessageDetailResponse)
async def mark_ready(
    payload: ReadyRequest,
    location_id: Annotated[int, Path(gt=0)],
    message_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('internal_message.respond')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageDetailResponse:
    try:
        value = await service.mark_ready(
            db, tenant_id=context.tenant_id, location_id=location_id,
            message_id=message_id, membership_id=context.membership_id,
            prepared_table_resource_id=payload.prepared_table_resource_id,
        )
        return await _detail(db, value, context.membership_id)
    except Exception as exc:
        raise _error(exc) from exc
