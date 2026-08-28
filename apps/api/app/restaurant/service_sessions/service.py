from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    Conversation,
    ConversationParticipant,
    Customer,
    DinerSession,
    Location,
    Organization,
    Resource,
    RestaurantServiceSession,
)
from app.restaurant.customers.service import normalize_email
from app.restaurant.service_sessions import errors


logger = logging.getLogger('ecip.restaurant_service')
_FAILURE_WINDOW = timedelta(minutes=5)
_LOCKOUT = timedelta(minutes=5)


@dataclass(frozen=True)
class OpenedServiceSession:
    session: RestaurantServiceSession
    access_code: str


@dataclass(frozen=True)
class RegeneratedAccessCode:
    session: RestaurantServiceSession
    access_code: str


@dataclass(frozen=True)
class JoinedDiner:
    diner: DinerSession


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def generate_access_code() -> str:
    return f'{secrets.randbelow(10000):04d}'


def generate_join_context_key() -> str:
    return secrets.token_urlsafe(32)


def _digest(*, settings: Settings, join_context_key: str, access_code: str, version: int) -> str:
    message = f'ecip.restaurant.join-code.v1\x00{join_context_key}\x00{version}\x00{access_code}'
    return hmac.new(
        settings.restaurant_access_code_secret.get_secret_value().encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_access_code(
    *, settings: Settings, session: RestaurantServiceSession, access_code: str
) -> bool:
    if session.access_code_digest is None:
        return False
    candidate = _digest(
        settings=settings,
        join_context_key=session.join_context_key,
        access_code=access_code,
        version=session.access_code_version,
    )
    return hmac.compare_digest(candidate, session.access_code_digest)


def _event(name: str, *, session: RestaurantServiceSession, correlation_id: str | None, **values: object) -> None:
    logger.info(
        name.replace('_', ' ').capitalize(),
        extra={
            'event': name,
            'tenant_id': session.tenant_id,
            'organization_id': session.organization_id,
            'location_id': session.location_id,
            'resource_id': session.resource_id,
            'service_session_id': session.id,
            'correlation_id': correlation_id,
            **values,
        },
    )


async def open_service_session(
    db: AsyncSession,
    *,
    settings: Settings,
    tenant_id: int,
    membership_id: int,
    resource_id: int,
    party_size: int,
    correlation_id: str | None = None,
) -> OpenedServiceSession:
    if not 1 <= party_size <= 999:
        raise ValueError('party_size must be between 1 and 999')
    try:
        resource = await db.scalar(
            select(Resource)
            .where(Resource.id == resource_id, Resource.tenant_id == tenant_id)
            .with_for_update()
        )
        if resource is None:
            raise errors.ServiceContextError('Serviceable Resource not found')
        location = await db.scalar(
            select(Location).where(
                Location.id == resource.location_id,
                Location.tenant_id == tenant_id,
                Location.status == 'ACTIVE',
            )
        )
        organization = None if location is None else await db.scalar(
            select(Organization).where(
                Organization.id == location.organization_id,
                Organization.tenant_id == tenant_id,
                Organization.status == 'ACTIVE',
            )
        )
        if (
            location is None
            or organization is None
            or resource.resource_type != 'TABLE'
            or resource.status != 'ACTIVE'
        ):
            raise errors.ServiceContextError('Resource is not an active serviceable TABLE')
        current = await db.scalar(
            select(RestaurantServiceSession).where(
                RestaurantServiceSession.resource_id == resource.id,
                RestaurantServiceSession.open_slot == 1,
            )
        )
        if current is not None:
            raise errors.ResourceAlreadyOccupiedError('Resource already has an open Service Session')
        code = generate_access_code()
        now = _now()
        session = RestaurantServiceSession(
            tenant_id=tenant_id,
            organization_id=organization.id,
            location_id=location.id,
            resource_id=resource.id,
            party_size=party_size,
            status='OPEN',
            open_slot=1,
            join_context_key=generate_join_context_key(),
            access_code_version=1,
            failed_join_attempts=0,
            opened_by_membership_id=membership_id,
            opened_at=now,
        )
        session.access_code_digest = _digest(
            settings=settings,
            join_context_key=session.join_context_key,
            access_code=code,
            version=1,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.ResourceAlreadyOccupiedError(
            'Resource already has an open Service Session'
        ) from exc
    except Exception:
        await db.rollback()
        raise
    _event('restaurant_service_session_opened', session=session, correlation_id=correlation_id, party_size=party_size)
    return OpenedServiceSession(session=session, access_code=code)


async def current_service_session(
    db: AsyncSession, *, tenant_id: int, resource_id: int
) -> tuple[RestaurantServiceSession, int]:
    session = await db.scalar(
        select(RestaurantServiceSession).where(
            RestaurantServiceSession.tenant_id == tenant_id,
            RestaurantServiceSession.resource_id == resource_id,
            RestaurantServiceSession.open_slot == 1,
        )
    )
    if session is None:
        raise errors.ServiceSessionNotFoundError('Current Service Session not found')
    active_count = int(
        await db.scalar(
            select(func.count(DinerSession.id)).where(
                DinerSession.service_session_id == session.id,
                DinerSession.active_slot == 1,
            )
        )
    )
    return session, active_count


async def update_party_size(
    db: AsyncSession,
    *,
    tenant_id: int,
    session_id: int,
    party_size: int,
    correlation_id: str | None = None,
) -> tuple[RestaurantServiceSession, int]:
    if not 1 <= party_size <= 999:
        raise ValueError('party_size must be between 1 and 999')
    try:
        session = await db.scalar(
            select(RestaurantServiceSession)
            .where(RestaurantServiceSession.id == session_id, RestaurantServiceSession.tenant_id == tenant_id)
            .with_for_update()
        )
        if session is None:
            raise errors.ServiceSessionNotFoundError('Service Session not found')
        if session.status != 'OPEN':
            raise errors.ServiceSessionClosedError('Service Session is closed')
        active_count = int(await db.scalar(select(func.count(DinerSession.id)).where(DinerSession.service_session_id == session.id, DinerSession.active_slot == 1)))
        if party_size < active_count:
            raise errors.PartySizeConflictError('party_size cannot be below active diner count')
        previous = session.party_size
        session.party_size = party_size
        await db.commit()
        await db.refresh(session)
    except Exception:
        await db.rollback()
        raise
    _event('restaurant_service_party_size_changed', session=session, correlation_id=correlation_id, previous_party_size=previous, party_size=party_size)
    return session, active_count


async def regenerate_access_code(
    db: AsyncSession,
    *,
    settings: Settings,
    tenant_id: int,
    session_id: int,
    correlation_id: str | None = None,
) -> RegeneratedAccessCode:
    try:
        session = await db.scalar(
            select(RestaurantServiceSession)
            .where(RestaurantServiceSession.id == session_id, RestaurantServiceSession.tenant_id == tenant_id)
            .with_for_update()
        )
        if session is None:
            raise errors.ServiceSessionNotFoundError('Service Session not found')
        if session.status != 'OPEN':
            raise errors.ServiceSessionClosedError('Service Session is closed')
        code = generate_access_code()
        session.access_code_version += 1
        session.access_code_digest = _digest(settings=settings, join_context_key=session.join_context_key, access_code=code, version=session.access_code_version)
        _reset_failures(session)
        await db.commit()
        await db.refresh(session)
    except Exception:
        await db.rollback()
        raise
    _event('restaurant_service_access_code_regenerated', session=session, correlation_id=correlation_id, access_code_version=session.access_code_version)
    return RegeneratedAccessCode(session=session, access_code=code)


def _reset_failures(session: RestaurantServiceSession) -> None:
    session.failed_join_attempts = 0
    session.failed_window_started_at = None
    session.join_locked_until = None


def _record_failure(session: RestaurantServiceSession, now: datetime) -> None:
    if session.failed_window_started_at is None or now - session.failed_window_started_at >= _FAILURE_WINDOW:
        session.failed_window_started_at = now
        session.failed_join_attempts = 1
    else:
        session.failed_join_attempts += 1
    if session.failed_join_attempts >= 5:
        session.join_locked_until = now + _LOCKOUT


async def join_diner(
    db: AsyncSession,
    *,
    settings: Settings,
    join_context_key: str,
    access_code: str,
    display_name: str,
    email: str | None,
    correlation_id: str | None = None,
) -> JoinedDiner:
    name = display_name.strip()
    if not name or len(name) > 200:
        raise ValueError('display_name must contain between 1 and 200 characters')
    normalized_email = normalize_email(email)
    session = await db.scalar(
        select(RestaurantServiceSession)
        .where(RestaurantServiceSession.join_context_key == join_context_key)
        .with_for_update()
    )
    if session is None:
        logger.info('Diner join rejected', extra={'event': 'diner_session_join_rejected', 'outcome': 'invalid', 'correlation_id': correlation_id})
        raise errors.InvalidJoinError('Invalid diner join credentials')
    now = _now()
    if session.status != 'OPEN':
        _event('diner_session_join_rejected', session=session, correlation_id=correlation_id, outcome='invalid')
        await db.rollback()
        raise errors.InvalidJoinError('Invalid diner join credentials')
    if session.join_locked_until is not None and session.join_locked_until > now:
        retry = max(1, min(300, int((session.join_locked_until - now).total_seconds()) + 1))
        _event('diner_session_join_rejected', session=session, correlation_id=correlation_id, outcome='locked')
        await db.rollback()
        raise errors.JoinLockedError(retry)
    if not verify_access_code(settings=settings, session=session, access_code=access_code):
        _record_failure(session, now)
        locked = session.join_locked_until is not None and session.join_locked_until > now
        await db.commit()
        _event('diner_session_join_rejected', session=session, correlation_id=correlation_id, outcome='invalid')
        if locked:
            raise errors.JoinLockedError(300)
        raise errors.InvalidJoinError('Invalid diner join credentials')

    _reset_failures(session)
    active_count = int(await db.scalar(select(func.count(DinerSession.id)).where(DinerSession.service_session_id == session.id, DinerSession.active_slot == 1)))
    if active_count >= session.party_size:
        await db.commit()
        _event('diner_session_capacity_conflict', session=session, correlation_id=correlation_id, outcome='rejected')
        raise errors.CapacityConflictError('Service Session capacity has been reached')
    if normalized_email is not None:
        duplicate = await db.scalar(
            select(DinerSession.id).where(
                DinerSession.service_session_id == session.id,
                DinerSession.normalized_email == normalized_email,
                DinerSession.active_slot == 1,
            )
        )
        if duplicate is not None:
            await db.commit()
            _event('diner_session_duplicate_identity', session=session, correlation_id=correlation_id, outcome='rejected')
            raise errors.DuplicateDinerIdentityError('Diner identity is already active')

    customer_id = None
    if normalized_email is not None:
        matches = tuple((await db.execute(select(Customer.id).where(Customer.tenant_id == session.tenant_id, Customer.email == normalized_email, Customer.status == 'ACTIVE').order_by(Customer.id).limit(2))).scalars().all())
        if len(matches) == 1:
            customer_id = matches[0]
    conversation = Conversation(
        tenant_id=session.tenant_id,
        organization_id=session.organization_id,
        location_id=session.location_id,
        resource_id=session.resource_id,
        channel='IN_PERSON_DIGITAL',
        status='ACTIVE',
        next_message_sequence=1,
        closed_at=None,
    )
    db.add(conversation)
    await db.flush()
    customer_participant = ConversationParticipant(
        tenant_id=session.tenant_id,
        conversation_id=conversation.id,
        participant_type='CUSTOMER',
        customer_id=customer_id,
        tenant_membership_id=None,
    )
    digital_waiter = ConversationParticipant(
        tenant_id=session.tenant_id,
        conversation_id=conversation.id,
        participant_type='DIGITAL_WAITER',
        customer_id=None,
        tenant_membership_id=None,
    )
    db.add_all([customer_participant, digital_waiter])
    await db.flush()
    diner = DinerSession(
        tenant_id=session.tenant_id,
        organization_id=session.organization_id,
        location_id=session.location_id,
        resource_id=session.resource_id,
        service_session_id=session.id,
        customer_id=customer_id,
        conversation_id=conversation.id,
        conversation_participant_id=customer_participant.id,
        display_name=name,
        normalized_email=normalized_email,
        status='ACTIVE',
        active_slot=1,
        joined_at=now,
    )
    db.add(diner)
    try:
        await db.commit()
        await db.refresh(diner)
    except IntegrityError as exc:
        await db.rollback()
        raise errors.DuplicateDinerIdentityError('Diner identity is already active') from exc
    _event('diner_session_joined', session=session, correlation_id=correlation_id, diner_session_id=diner.id, conversation_id=diner.conversation_id)
    return JoinedDiner(diner=diner)


async def validate_diner_authority(
    db: AsyncSession,
    *,
    tenant_id: int,
    diner_session_id: int,
    conversation_id: int,
) -> DinerSession:
    diner = await db.scalar(
        select(DinerSession)
        .join(RestaurantServiceSession, RestaurantServiceSession.id == DinerSession.service_session_id)
        .where(
            DinerSession.id == diner_session_id,
            DinerSession.tenant_id == tenant_id,
            DinerSession.conversation_id == conversation_id,
            DinerSession.status == 'ACTIVE',
            DinerSession.active_slot == 1,
            RestaurantServiceSession.status == 'OPEN',
            RestaurantServiceSession.open_slot == 1,
        )
    )
    if diner is None:
        raise errors.DinerAuthorizationError('Diner is not authorized for this Conversation')
    return diner


async def end_diner_session(
    db: AsyncSession,
    *,
    tenant_id: int,
    service_session_id: int,
    diner_session_id: int,
    correlation_id: str | None = None,
) -> DinerSession:
    try:
        session = await db.scalar(select(RestaurantServiceSession).where(RestaurantServiceSession.id == service_session_id, RestaurantServiceSession.tenant_id == tenant_id).with_for_update())
        if session is None or session.status != 'OPEN':
            raise errors.DinerAuthorizationError('Diner session is not active')
        diner = await db.scalar(select(DinerSession).where(DinerSession.id == diner_session_id, DinerSession.service_session_id == session.id, DinerSession.tenant_id == tenant_id).with_for_update())
        if diner is None or diner.status != 'ACTIVE':
            raise errors.DinerAuthorizationError('Diner session is not active')
        conversation = await db.scalar(select(Conversation).where(Conversation.id == diner.conversation_id, Conversation.tenant_id == tenant_id).with_for_update())
        now = _now()
        diner.status = 'ENDED'
        diner.active_slot = None
        diner.ended_at = now
        if conversation is not None and conversation.status == 'ACTIVE':
            conversation.status = 'CLOSED'
            conversation.closed_at = now
        await db.commit()
        await db.refresh(diner)
    except Exception:
        await db.rollback()
        raise
    _event('diner_session_ended', session=session, correlation_id=correlation_id, diner_session_id=diner.id, conversation_id=diner.conversation_id)
    return diner


async def close_service_session(
    db: AsyncSession,
    *,
    tenant_id: int,
    membership_id: int,
    session_id: int,
    correlation_id: str | None = None,
) -> RestaurantServiceSession:
    try:
        identity = await db.scalar(select(RestaurantServiceSession.resource_id).where(RestaurantServiceSession.id == session_id, RestaurantServiceSession.tenant_id == tenant_id))
        if identity is None:
            raise errors.ServiceSessionNotFoundError('Service Session not found')
        resource = await db.scalar(select(Resource).where(Resource.id == identity, Resource.tenant_id == tenant_id).with_for_update())
        session = await db.scalar(select(RestaurantServiceSession).where(RestaurantServiceSession.id == session_id, RestaurantServiceSession.tenant_id == tenant_id, RestaurantServiceSession.resource_id == resource.id).with_for_update())
        if session is None:
            raise errors.ServiceSessionNotFoundError('Service Session not found')
        if session.status != 'OPEN':
            raise errors.ServiceSessionClosedError('Service Session is closed')
        diners = tuple((await db.execute(select(DinerSession).where(DinerSession.service_session_id == session.id, DinerSession.active_slot == 1).order_by(DinerSession.id).with_for_update())).scalars().all())
        conversation_ids = tuple(sorted(diner.conversation_id for diner in diners))
        conversations = tuple((await db.execute(select(Conversation).where(Conversation.id.in_(conversation_ids or (-1,)), Conversation.tenant_id == tenant_id).order_by(Conversation.id).with_for_update())).scalars().all())
        now = _now()
        for diner in diners:
            diner.status = 'ENDED'
            diner.active_slot = None
            diner.ended_at = now
        for conversation in conversations:
            if conversation.status == 'ACTIVE':
                conversation.status = 'CLOSED'
                conversation.closed_at = now
        session.status = 'CLOSED'
        session.open_slot = None
        session.access_code_digest = None
        _reset_failures(session)
        session.closed_by_membership_id = membership_id
        session.closed_at = now
        await db.commit()
        await db.refresh(session)
    except Exception:
        await db.rollback()
        raise
    _event('restaurant_service_session_closed', session=session, correlation_id=correlation_id, ended_diner_count=len(diners))
    return session
