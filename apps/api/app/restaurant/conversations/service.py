from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    ConversationMessage,
    ConversationParticipant,
    Customer,
    Location,
    Organization,
    OrderDraft,
    Resource,
    TenantMembership,
)
from app.restaurant.service_sessions import service as diner_authority_service


class ConversationNotFoundError(LookupError):
    pass


class ConversationContextError(ValueError):
    pass


class ConversationClosedError(RuntimeError):
    pass


class ConversationConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResponderMessage:
    message_id: int
    conversation_id: int
    operational_request_id: int
    participant_id: int
    author_type: str
    sequence_number: int
    modality: str
    content_text: str
    language: str | None
    language_source: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DinerTranscriptMessage:
    message_id: int
    author_type: str
    sequence_number: int
    modality: str
    content_text: str
    language: str | None
    language_source: str | None
    created_at: datetime


async def get_conversation(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    lock: bool = False,
    owner_diner_session_id: int | None = None,
) -> Conversation:
    query = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == tenant_id,
    )
    if lock:
        query = query.with_for_update()
    conversation = await db.scalar(query)
    if conversation is None:
        raise ConversationNotFoundError
    if owner_diner_session_id is not None:
        await diner_authority_service.validate_diner_authority(
            db,
            tenant_id=tenant_id,
            diner_session_id=owner_diner_session_id,
            conversation_id=conversation.id,
        )
    return conversation


async def _organization(db: AsyncSession, tenant_id: int, organization_id: int) -> Organization:
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == tenant_id,
        )
    )
    if organization is None:
        raise ConversationContextError('Organization not found')
    return organization


async def _location(
    db: AsyncSession,
    tenant_id: int,
    organization_id: int,
    location_id: int,
) -> Location:
    location = await db.scalar(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
            Location.organization_id == organization_id,
        )
    )
    if location is None:
        raise ConversationContextError('Location not found in Conversation context')
    return location


async def _resource(
    db: AsyncSession,
    tenant_id: int,
    location_id: int,
    resource_id: int,
) -> Resource:
    resource = await db.scalar(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.tenant_id == tenant_id,
            Resource.location_id == location_id,
        )
    )
    if resource is None:
        raise ConversationContextError('Resource not found in Conversation context')
    return resource


async def create_conversation(
    db: AsyncSession,
    *,
    tenant_id: int,
    organization_id: int,
    location_id: int | None,
    resource_id: int | None,
    channel: str,
    default_language: str | None,
) -> Conversation:
    await _organization(db, tenant_id, organization_id)
    if resource_id is not None and location_id is None:
        raise ConversationContextError('Resource requires a Location')
    if location_id is not None:
        await _location(db, tenant_id, organization_id, location_id)
    if resource_id is not None:
        await _resource(db, tenant_id, location_id, resource_id)
    conversation = Conversation(
        tenant_id=tenant_id,
        organization_id=organization_id,
        location_id=location_id,
        resource_id=resource_id,
        channel=channel,
        status='ACTIVE',
        default_language=default_language,
        next_message_sequence=1,
        closed_at=None,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def update_conversation(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    updates: dict[str, object],
) -> Conversation:
    conversation = await get_conversation(
        db, tenant_id=tenant_id, conversation_id=conversation_id, lock=True
    )
    if conversation.status == 'CLOSED':
        raise ConversationClosedError('Conversation is closed')

    if 'location_id' in updates:
        location_id = int(updates['location_id'])
        if conversation.location_id is not None and conversation.location_id != location_id:
            raise ConversationConflictError('Conversation Location cannot be reassigned')
        await _location(db, tenant_id, conversation.organization_id, location_id)
        conversation.location_id = location_id

    if 'resource_id' in updates:
        resource_id = int(updates['resource_id'])
        if conversation.resource_id is not None and conversation.resource_id != resource_id:
            raise ConversationConflictError('Conversation Resource cannot be reassigned')
        if conversation.location_id is None:
            raise ConversationContextError('Resource requires a Location')
        await _resource(db, tenant_id, conversation.location_id, resource_id)
        conversation.resource_id = resource_id

    if 'default_language' in updates:
        conversation.default_language = updates['default_language']

    if updates.get('status') == 'CLOSED':
        now = datetime.now(UTC).replace(tzinfo=None)
        draft = await db.scalar(
            select(OrderDraft)
            .where(
                OrderDraft.tenant_id == tenant_id,
                OrderDraft.conversation_id == conversation.id,
                OrderDraft.status == 'OPEN',
                OrderDraft.current_slot == 1,
            )
            .with_for_update()
        )
        if draft is not None:
            draft.status = 'ABANDONED'
            draft.current_slot = None
            draft.terminal_at = now
        conversation.status = 'CLOSED'
        conversation.closed_at = now

    await db.commit()
    await db.refresh(conversation)
    return conversation


async def add_participant(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    participant_type: str,
    customer_id: int | None,
    tenant_membership_id: int | None,
    preferred_language: str | None,
) -> ConversationParticipant:
    conversation = await get_conversation(
        db, tenant_id=tenant_id, conversation_id=conversation_id, lock=True
    )
    if conversation.status == 'CLOSED':
        raise ConversationClosedError('Conversation is closed')
    if customer_id is not None:
        customer = await db.scalar(
            select(Customer.id).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )
        if customer is None:
            raise ConversationContextError('Customer not found')
    if tenant_membership_id is not None:
        membership = await db.scalar(
            select(TenantMembership.id).where(
                TenantMembership.id == tenant_membership_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        if membership is None:
            raise ConversationContextError('Tenant membership not found')

    participant = ConversationParticipant(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        participant_type=participant_type,
        customer_id=customer_id,
        tenant_membership_id=tenant_membership_id,
        preferred_language=preferred_language,
    )
    db.add(participant)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConversationConflictError('Participant conflicts with existing Conversation identity') from exc
    await db.refresh(participant)
    return participant


async def update_participant(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    participant_id: int,
    updates: dict[str, object],
) -> ConversationParticipant:
    conversation = await get_conversation(
        db, tenant_id=tenant_id, conversation_id=conversation_id, lock=True
    )
    if conversation.status == 'CLOSED':
        raise ConversationClosedError('Conversation is closed')
    participant = await db.scalar(
        select(ConversationParticipant)
        .where(
            ConversationParticipant.id == participant_id,
            ConversationParticipant.tenant_id == tenant_id,
            ConversationParticipant.conversation_id == conversation_id,
        )
        .with_for_update()
    )
    if participant is None:
        raise ConversationContextError('Participant not found')

    if 'customer_id' in updates:
        customer_id = int(updates['customer_id'])
        if participant.participant_type != 'CUSTOMER':
            raise ConversationConflictError('Only a CUSTOMER participant may link a Customer')
        if participant.customer_id is not None:
            raise ConversationConflictError('Customer identity is already linked')
        customer = await db.scalar(
            select(Customer.id).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )
        if customer is None:
            raise ConversationContextError('Customer not found')
        participant.customer_id = customer_id
    if 'preferred_language' in updates:
        participant.preferred_language = updates['preferred_language']

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConversationConflictError('Participant conflicts with existing Conversation identity') from exc
    await db.refresh(participant)
    return participant


async def append_message(
    db: AsyncSession,
    *,
    tenant_id: int,
    conversation_id: int,
    participant_id: int,
    modality: str,
    content_text: str,
    language: str | None,
    language_source: str | None,
    owner_diner_session_id: int | None = None,
) -> ConversationMessage:
    conversation = await get_conversation(
        db, tenant_id=tenant_id, conversation_id=conversation_id, lock=True
        , owner_diner_session_id=owner_diner_session_id
    )
    if owner_diner_session_id is not None:
        diner = await diner_authority_service.validate_diner_authority(
            db,
            tenant_id=tenant_id,
            diner_session_id=owner_diner_session_id,
            conversation_id=conversation_id,
        )
        if diner.conversation_participant_id != participant_id:
            raise ConversationContextError('Participant not found in Conversation')
    if conversation.status == 'CLOSED':
        raise ConversationClosedError('Conversation is closed')
    participant = await db.scalar(
        select(ConversationParticipant.id).where(
            ConversationParticipant.id == participant_id,
            ConversationParticipant.tenant_id == tenant_id,
            ConversationParticipant.conversation_id == conversation_id,
        )
    )
    if participant is None:
        raise ConversationContextError('Participant not found in Conversation')

    sequence_number = conversation.next_message_sequence
    conversation.next_message_sequence += 1
    message = ConversationMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        participant_id=participant_id,
        sequence_number=sequence_number,
        modality=modality,
        content_text=content_text,
        language=language,
        language_source=language_source,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


def _responder_projection(message: ConversationMessage) -> ResponderMessage:
    return ResponderMessage(
        message_id=message.id,
        conversation_id=message.conversation_id,
        operational_request_id=message.operational_request_id,
        participant_id=message.participant_id,
        author_type='HUMAN_STAFF',
        sequence_number=message.sequence_number,
        modality=message.modality,
        content_text=message.content_text,
        language=message.language,
        language_source=message.language_source,
        created_at=message.created_at,
    )


async def stage_staff_response(
    db: AsyncSession,
    *,
    conversation: Conversation,
    operational_request_id: int,
    membership_id: int,
    idempotency_key: str,
    request_fingerprint: str,
    modality: str,
    content_text: str,
    language: str | None,
    language_source: str | None,
) -> ResponderMessage:
    participant = await db.scalar(select(ConversationParticipant).where(
        ConversationParticipant.tenant_id == conversation.tenant_id,
        ConversationParticipant.conversation_id == conversation.id,
        ConversationParticipant.tenant_membership_id == membership_id,
    ).with_for_update())
    if participant is None:
        participant = ConversationParticipant(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            participant_type='HUMAN_STAFF',
            customer_id=None,
            tenant_membership_id=membership_id,
            preferred_language=None,
        )
        db.add(participant)
        await db.flush()

    existing = await db.scalar(select(ConversationMessage).where(
        ConversationMessage.tenant_id == conversation.tenant_id,
        ConversationMessage.operational_request_id == operational_request_id,
        ConversationMessage.participant_id == participant.id,
        ConversationMessage.response_idempotency_key == idempotency_key,
    ).with_for_update())
    if existing is not None:
        if existing.response_request_fingerprint != request_fingerprint:
            raise ConversationConflictError(
                'Idempotency key was used for a different responder command'
            )
        return _responder_projection(existing)

    message = ConversationMessage(
        tenant_id=conversation.tenant_id,
        conversation_id=conversation.id,
        participant_id=participant.id,
        sequence_number=conversation.next_message_sequence,
        modality=modality,
        content_text=content_text,
        language=language,
        language_source=language_source,
        operational_request_id=operational_request_id,
        response_idempotency_key=idempotency_key,
        response_request_fingerprint=request_fingerprint,
    )
    conversation.next_message_sequence += 1
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return _responder_projection(message)


async def list_diner_transcript(
    db: AsyncSession,
    *,
    tenant_id: int,
    diner_session_id: int,
    conversation_id: int,
    limit: int,
    offset: int,
) -> tuple[DinerTranscriptMessage, ...]:
    await get_conversation(
        db,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        owner_diner_session_id=diner_session_id,
    )
    rows = (await db.execute(
        select(ConversationMessage, ConversationParticipant.participant_type)
        .join(
            ConversationParticipant,
            (ConversationParticipant.id == ConversationMessage.participant_id)
            & (ConversationParticipant.tenant_id == ConversationMessage.tenant_id)
            & (ConversationParticipant.conversation_id == ConversationMessage.conversation_id),
        )
        .where(
            ConversationMessage.tenant_id == tenant_id,
            ConversationMessage.conversation_id == conversation_id,
        )
        .order_by(ConversationMessage.sequence_number, ConversationMessage.id)
        .limit(limit)
        .offset(offset)
    )).all()
    return tuple(DinerTranscriptMessage(
        message_id=message.id,
        author_type=participant_type,
        sequence_number=message.sequence_number,
        modality=message.modality,
        content_text=message.content_text,
        language=message.language,
        language_source=message.language_source,
        created_at=message.created_at,
    ) for message, participant_type in rows)
