from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DiningSection,
    InternalOperationalMessage,
    InternalOperationalMessageHistory,
    InternalOperationalMessageResponse,
    Location,
    Resource,
    RestaurantTableProfile,
    TableGroup,
    TableGroupMembership,
    TenantMembership,
    User,
)
from app.restaurant.waiter_eligibility import eligible_waiter_ids


class InternalMessageError(RuntimeError):
    pass


class InternalMessageNotFoundError(InternalMessageError):
    pass


class InternalMessageForbiddenError(InternalMessageError):
    pass


class InternalMessageConflictError(InternalMessageError):
    pass


class InternalMessageIdempotencyConflictError(InternalMessageConflictError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _content(value: str, *, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f'{field} must contain between 1 and {maximum} characters')
    return normalized


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _participant_message(
    db: AsyncSession, *, tenant_id: int, location_id: int, message_id: int,
    membership_id: int, lock: bool = False,
) -> InternalOperationalMessage:
    statement = select(InternalOperationalMessage).where(
        InternalOperationalMessage.id == message_id,
        InternalOperationalMessage.tenant_id == tenant_id,
        InternalOperationalMessage.location_id == location_id,
        (
            (InternalOperationalMessage.creator_membership_id == membership_id)
            | (InternalOperationalMessage.recipient_membership_id == membership_id)
        ),
    )
    if lock:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise InternalMessageNotFoundError('Internal operational message not found')
    return value


async def _require_current_recipient(
    db: AsyncSession, *, message: InternalOperationalMessage, membership_id: int,
) -> None:
    if membership_id != message.recipient_membership_id:
        raise InternalMessageForbiddenError('Only the explicit recipient may perform this action')
    eligible = await eligible_waiter_ids(
        db, tenant_id=message.tenant_id, location_id=message.location_id,
        membership_ids=(membership_id,),
    )
    if membership_id not in eligible:
        raise InternalMessageForbiddenError(
            'The explicit recipient is no longer active and eligible for this Location'
        )


async def _append_history(
    db: AsyncSession, *, message: InternalOperationalMessage, event_type: str,
    actor_membership_id: int, response_id: int | None = None,
) -> InternalOperationalMessageHistory:
    last_sequence = await db.scalar(select(func.max(
        InternalOperationalMessageHistory.event_sequence,
    )).where(InternalOperationalMessageHistory.message_id == message.id))
    value = InternalOperationalMessageHistory(
        tenant_id=message.tenant_id,
        organization_id=message.organization_id,
        location_id=message.location_id,
        message_id=message.id,
        event_sequence=int(last_sequence or 0) + 1,
        event_type=event_type,
        actor_membership_id=actor_membership_id,
        response_id=response_id,
        occurred_at=_now(),
    )
    db.add(value)
    await db.flush()
    return value


async def create_message(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    creator_membership_id: int, recipient_membership_id: int,
    message_type: str, text: str, party_size: int, idempotency_key: str,
) -> InternalOperationalMessage:
    if message_type != 'TABLE_PREPARATION_REQUEST':
        raise ValueError('Unsupported internal operational message type')
    if not 1 <= party_size <= 999:
        raise ValueError('party_size must be between 1 and 999')
    normalized_text = _content(text, field='text', maximum=2000)
    fingerprint = _fingerprint({
        'location_id': location_id,
        'recipient_membership_id': recipient_membership_id,
        'message_type': message_type,
        'text': normalized_text,
        'party_size': party_size,
    })
    replay = await db.scalar(select(InternalOperationalMessage).where(
        InternalOperationalMessage.tenant_id == tenant_id,
        InternalOperationalMessage.location_id == location_id,
        InternalOperationalMessage.creator_membership_id == creator_membership_id,
        InternalOperationalMessage.idempotency_key == idempotency_key,
    ))
    if replay is not None:
        if replay.request_fingerprint != fingerprint:
            raise InternalMessageIdempotencyConflictError(
                'Idempotency-Key was already used with a different request'
            )
        return replay
    location = await db.scalar(select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.status == 'ACTIVE',
    ))
    if location is None:
        raise InternalMessageNotFoundError('Location not found')
    eligible = await eligible_waiter_ids(
        db, tenant_id=tenant_id, location_id=location_id,
        membership_ids=(recipient_membership_id,),
    )
    if recipient_membership_id not in eligible:
        raise InternalMessageConflictError(
            'Recipient must be an active eligible Waiter for this Location'
        )
    value = InternalOperationalMessage(
        tenant_id=tenant_id,
        organization_id=location.organization_id,
        location_id=location_id,
        creator_membership_id=creator_membership_id,
        recipient_membership_id=recipient_membership_id,
        message_type=message_type,
        text=normalized_text,
        party_size=party_size,
        status='REQUESTED',
        version=1,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    db.add(value)
    try:
        await db.flush()
        await _append_history(
            db, message=value, event_type='MESSAGE_CREATED',
            actor_membership_id=creator_membership_id,
        )
        await db.commit()
        await db.refresh(value)
    except IntegrityError:
        await db.rollback()
        replay = await db.scalar(select(InternalOperationalMessage).where(
            InternalOperationalMessage.tenant_id == tenant_id,
            InternalOperationalMessage.location_id == location_id,
            InternalOperationalMessage.creator_membership_id == creator_membership_id,
            InternalOperationalMessage.idempotency_key == idempotency_key,
        ))
        if replay is None:
            raise
        if replay.request_fingerprint != fingerprint:
            raise InternalMessageIdempotencyConflictError(
                'Idempotency-Key was already used with a different request'
            )
        return replay
    return value


async def list_messages(
    db: AsyncSession, *, tenant_id: int, location_id: int, membership_id: int,
    box: str, limit: int, offset: int,
) -> tuple[InternalOperationalMessage, ...]:
    participant = (
        InternalOperationalMessage.creator_membership_id
        if box == 'sent' else InternalOperationalMessage.recipient_membership_id
    )
    return tuple((await db.scalars(select(InternalOperationalMessage).where(
        InternalOperationalMessage.tenant_id == tenant_id,
        InternalOperationalMessage.location_id == location_id,
        participant == membership_id,
    ).order_by(
        InternalOperationalMessage.created_at.desc(),
        InternalOperationalMessage.id.desc(),
    ).limit(limit).offset(offset))).all())


async def get_message(
    db: AsyncSession, *, tenant_id: int, location_id: int, message_id: int,
    membership_id: int,
) -> InternalOperationalMessage:
    return await _participant_message(
        db, tenant_id=tenant_id, location_id=location_id,
        message_id=message_id, membership_id=membership_id,
    )


async def enter_message(
    db: AsyncSession, *, tenant_id: int, location_id: int, message_id: int,
    membership_id: int,
) -> InternalOperationalMessage:
    value = await _participant_message(
        db, tenant_id=tenant_id, location_id=location_id,
        message_id=message_id, membership_id=membership_id, lock=True,
    )
    await _require_current_recipient(db, message=value, membership_id=membership_id)
    if value.entered_at is None:
        value.entered_at = _now()
        value.entered_by_membership_id = membership_id
        value.version += 1
        await _append_history(
            db, message=value, event_type='ENTERADO',
            actor_membership_id=membership_id,
        )
        await db.commit()
        await db.refresh(value)
    return value


async def add_response(
    db: AsyncSession, *, tenant_id: int, location_id: int, message_id: int,
    membership_id: int, content: str, idempotency_key: str,
) -> InternalOperationalMessageResponse:
    normalized = _content(content, field='content', maximum=4000)
    fingerprint = _fingerprint({'content': normalized})
    message = await _participant_message(
        db, tenant_id=tenant_id, location_id=location_id,
        message_id=message_id, membership_id=membership_id, lock=True,
    )
    replay = await db.scalar(select(InternalOperationalMessageResponse).where(
        InternalOperationalMessageResponse.message_id == message.id,
        InternalOperationalMessageResponse.author_membership_id == membership_id,
        InternalOperationalMessageResponse.idempotency_key == idempotency_key,
    ))
    if replay is not None:
        if replay.request_fingerprint != fingerprint:
            raise InternalMessageIdempotencyConflictError(
                'Idempotency-Key was already used with different response content'
            )
        return replay
    if membership_id == message.recipient_membership_id:
        await _require_current_recipient(db, message=message, membership_id=membership_id)
        if message.status == 'READY':
            raise InternalMessageConflictError('READY is terminal for the recipient')
        if message.entered_at is None:
            raise InternalMessageConflictError('Recipient must mark Enterado before responding')
    last_sequence = await db.scalar(select(func.max(
        InternalOperationalMessageResponse.sequence,
    )).where(InternalOperationalMessageResponse.message_id == message.id))
    value = InternalOperationalMessageResponse(
        tenant_id=message.tenant_id,
        organization_id=message.organization_id,
        location_id=message.location_id,
        message_id=message.id,
        author_membership_id=membership_id,
        sequence=int(last_sequence or 0) + 1,
        content=normalized,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        created_at=_now(),
    )
    db.add(value)
    await db.flush()
    await _append_history(
        db, message=message, event_type='RESPONSE_ADDED',
        actor_membership_id=membership_id, response_id=value.id,
    )
    await db.commit()
    await db.refresh(value)
    return value


async def _validate_prepared_table(
    db: AsyncSession, *, message: InternalOperationalMessage, resource_id: int,
) -> None:
    row = (await db.execute(select(
        Resource, RestaurantTableProfile, DiningSection,
    ).join(
        RestaurantTableProfile,
        (RestaurantTableProfile.resource_id == Resource.id)
        & (RestaurantTableProfile.tenant_id == Resource.tenant_id),
    ).join(
        DiningSection, DiningSection.id == RestaurantTableProfile.dining_section_id,
    ).where(
        Resource.id == resource_id,
        Resource.tenant_id == message.tenant_id,
        Resource.location_id == message.location_id,
        Resource.resource_type == 'TABLE',
        Resource.status == 'ACTIVE',
        RestaurantTableProfile.organization_id == message.organization_id,
        RestaurantTableProfile.location_id == message.location_id,
        RestaurantTableProfile.administrative_status == 'ACTIVE',
        DiningSection.status == 'ACTIVE',
    ))).first()
    if row is None:
        raise InternalMessageConflictError(
            'Prepared Table is not valid under current Table Management authority'
        )
    group_membership = await db.scalar(select(TableGroupMembership).where(
        TableGroupMembership.tenant_id == message.tenant_id,
        TableGroupMembership.location_id == message.location_id,
        TableGroupMembership.table_resource_id == resource_id,
        TableGroupMembership.active_slot == 1,
    ))
    if group_membership is not None and not group_membership.is_representative:
        raise InternalMessageConflictError(
            'An ACTIVE TableGroup must be referenced by its representative Table'
        )


async def mark_ready(
    db: AsyncSession, *, tenant_id: int, location_id: int, message_id: int,
    membership_id: int, prepared_table_resource_id: int | None,
) -> InternalOperationalMessage:
    value = await _participant_message(
        db, tenant_id=tenant_id, location_id=location_id,
        message_id=message_id, membership_id=membership_id, lock=True,
    )
    await _require_current_recipient(db, message=value, membership_id=membership_id)
    if value.status == 'READY':
        if value.prepared_table_resource_id != prepared_table_resource_id:
            raise InternalMessageConflictError(
                'Message is already READY with different prepared Table evidence'
            )
        return value
    if value.entered_at is None:
        raise InternalMessageConflictError('Enterado is required before READY')
    if prepared_table_resource_id is not None:
        await _validate_prepared_table(
            db, message=value, resource_id=prepared_table_resource_id,
        )
    value.status = 'READY'
    value.ready_at = _now()
    value.ready_by_membership_id = membership_id
    value.prepared_table_resource_id = prepared_table_resource_id
    value.version += 1
    await _append_history(
        db, message=value, event_type='READY', actor_membership_id=membership_id,
    )
    await db.commit()
    await db.refresh(value)
    return value


async def responses_for(
    db: AsyncSession, *, message_id: int,
) -> tuple[InternalOperationalMessageResponse, ...]:
    return tuple((await db.scalars(select(InternalOperationalMessageResponse).where(
        InternalOperationalMessageResponse.message_id == message_id,
    ).order_by(InternalOperationalMessageResponse.sequence))).all())


async def history_for(
    db: AsyncSession, *, message_id: int,
) -> tuple[InternalOperationalMessageHistory, ...]:
    return tuple((await db.scalars(select(InternalOperationalMessageHistory).where(
        InternalOperationalMessageHistory.message_id == message_id,
    ).order_by(InternalOperationalMessageHistory.event_sequence))).all())


async def people_for(
    db: AsyncSession, *, tenant_id: int, membership_ids: set[int],
) -> dict[int, dict[str, object]]:
    rows = (await db.execute(select(
        TenantMembership.id, User.display_name, User.email,
    ).join(User, User.id == TenantMembership.user_id).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.id.in_(membership_ids),
    ))).all()
    return {
        int(row.id): {
            'membership_id': int(row.id),
            'display_name': row.display_name,
            'email': row.email,
        }
        for row in rows
    }


async def prepared_table_projection(
    db: AsyncSession, *, message: InternalOperationalMessage,
) -> dict[str, object] | None:
    resource_id = message.prepared_table_resource_id
    if resource_id is None:
        return None
    row = (await db.execute(select(Resource, RestaurantTableProfile).join(
        RestaurantTableProfile,
        (RestaurantTableProfile.resource_id == Resource.id)
        & (RestaurantTableProfile.tenant_id == Resource.tenant_id),
    ).where(
        Resource.id == resource_id,
        Resource.tenant_id == message.tenant_id,
        Resource.location_id == message.location_id,
    ))).first()
    if row is None:
        return None
    resource, profile = row
    projection: dict[str, object] = {
        'resource_id': resource.id,
        'code': resource.code,
        'name': resource.name,
        'physical_capacity': profile.physical_capacity,
        'is_group_representative': False,
        'group_id': None,
        'members': [],
        'derived_group_capacity': None,
    }
    membership = await db.scalar(select(TableGroupMembership).where(
        TableGroupMembership.tenant_id == message.tenant_id,
        TableGroupMembership.location_id == message.location_id,
        TableGroupMembership.table_resource_id == resource_id,
        TableGroupMembership.active_slot == 1,
        TableGroupMembership.is_representative.is_(True),
    ))
    if membership is None:
        return projection
    group = await db.scalar(select(TableGroup).where(
        TableGroup.id == membership.table_group_id,
        TableGroup.status == 'ACTIVE',
        TableGroup.active_slot == 1,
    ))
    if group is None:
        return projection
    member_rows = (await db.execute(select(
        Resource.id, Resource.code, Resource.name,
        RestaurantTableProfile.physical_capacity,
    ).join(
        TableGroupMembership,
        (TableGroupMembership.table_resource_id == Resource.id)
        & (TableGroupMembership.tenant_id == Resource.tenant_id),
    ).join(
        RestaurantTableProfile,
        (RestaurantTableProfile.resource_id == Resource.id)
        & (RestaurantTableProfile.tenant_id == Resource.tenant_id),
    ).where(
        TableGroupMembership.table_group_id == group.id,
        TableGroupMembership.active_slot == 1,
    ).order_by(
        TableGroupMembership.is_representative.desc(),
        TableGroupMembership.id,
    ))).all()
    members = [{
        'resource_id': int(item.id), 'code': item.code, 'name': item.name,
        'physical_capacity': int(item.physical_capacity),
    } for item in member_rows]
    projection.update({
        'is_group_representative': True,
        'group_id': group.id,
        'members': members,
        'derived_group_capacity': sum(item['physical_capacity'] for item in members),
    })
    return projection
