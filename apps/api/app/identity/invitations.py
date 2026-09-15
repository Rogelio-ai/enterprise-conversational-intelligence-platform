"""Credential-free, one-time canonical User invitation authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.connector_security import secret_digest, verify_machine_secret
from app.core.security import hash_password
from app.models import (
    IdentityInvitation,
    MembershipRole,
    Permission,
    Role,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
)


_PURPOSE = 'identity-invitation'


class IdentityInvitationError(ValueError):
    pass


class IdentityInvitationAuthorizationError(IdentityInvitationError):
    pass


class IdentityInvitationConflictError(IdentityInvitationError):
    pass


class InvalidIdentityInvitationError(IdentityInvitationError):
    pass


@dataclass(frozen=True, slots=True)
class InvitationCreationResult:
    invitation: IdentityInvitation
    acceptance_token: str


@dataclass(frozen=True, slots=True)
class InvitationAcceptanceResult:
    invitation: IdentityInvitation
    user: User


@dataclass(frozen=True, slots=True)
class InvitationRevocationResult:
    invitation: IdentityInvitation
    operation: str


def normalize_email(email: object) -> str:
    if not isinstance(email, str):
        raise IdentityInvitationError('Invalid email')
    normalized = email.strip().casefold()
    if (
        len(normalized) < 3 or len(normalized) > 320
        or '@' not in normalized
        or normalized.startswith('@') or normalized.endswith('@')
    ):
        raise IdentityInvitationError('A valid email is required')
    return normalized


def _display_name(value: object) -> str:
    if not isinstance(value, str):
        raise IdentityInvitationError('Invalid display name')
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise IdentityInvitationError(
            'Display name must contain between 1 and 200 characters'
        )
    return normalized


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    return current.replace(microsecond=0)


async def _authorize_inviter(
    db: AsyncSession, *, tenant_id: int, membership_id: int,
) -> User:
    if await db.scalar(select(Tenant.id).where(
        Tenant.id == tenant_id, Tenant.status == 'ACTIVE',
    ).with_for_update()) is None:
        raise IdentityInvitationAuthorizationError('Invitation Tenant is not active')
    user = await db.scalar(
        select(User)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .where(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == 'ACTIVE',
            User.status == 'ACTIVE',
        ).with_for_update()
    )
    if user is None:
        raise IdentityInvitationAuthorizationError(
            'Invitation actor is not an active Tenant member'
        )
    permission = await db.scalar(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .where(
            MembershipRole.membership_id == membership_id,
            MembershipRole.tenant_id == tenant_id,
            Role.tenant_id == tenant_id,
            Role.status == 'ACTIVE',
            Permission.code == 'user.manage',
        )
        .limit(1)
    )
    if permission is None:
        raise IdentityInvitationAuthorizationError(
            'user.manage permission is required'
        )
    return user


async def resolve_existing_user(
    db: AsyncSession, *, email: str,
) -> User | None:
    return await db.scalar(select(User).where(User.email == normalize_email(email)))


async def invite_identity(
    db: AsyncSession, *, settings: Settings, tenant_id: int,
    actor_membership_id: int, email: str, display_name: str,
    now: datetime | None = None,
) -> InvitationCreationResult:
    normalized_email = normalize_email(email)
    normalized_name = _display_name(display_name)
    current_time = _now(now)
    actor = await _authorize_inviter(
        db, tenant_id=tenant_id, membership_id=actor_membership_id,
    )
    existing_user = await db.scalar(select(User).where(
        User.email == normalized_email,
    ).with_for_update())
    if existing_user is not None:
        raise IdentityInvitationConflictError(
            'Canonical User identity already exists'
        )
    existing_invitation = await db.scalar(select(IdentityInvitation).where(
        IdentityInvitation.email == normalized_email,
        IdentityInvitation.active_slot == 1,
    ).with_for_update())
    if existing_invitation is not None:
        if (
            existing_invitation.revoked_at is None
            and existing_invitation.consumed_at is None
            and existing_invitation.expires_at > current_time
        ):
            raise IdentityInvitationConflictError(
                'Canonical identity already has an active Invitation'
            )
        existing_invitation.active_slot = None

    invitation_id = str(uuid4())
    secret = secrets.token_urlsafe(32)
    invitation = IdentityInvitation(
        invitation_id=invitation_id, inviter_tenant_id=tenant_id,
        created_by_user_id=actor.id, email=normalized_email,
        display_name=normalized_name,
        secret_digest=secret_digest(
            secret, settings=settings, purpose=_PURPOSE,
        ),
        expires_at=current_time + timedelta(
            hours=settings.identity_invitation_ttl_hours
        ),
        active_slot=1,
    )
    db.add(invitation)
    try:
        await db.commit()
        await db.refresh(invitation)
    except IntegrityError as exc:
        await db.rollback()
        raise IdentityInvitationConflictError(
            'Canonical identity Invitation conflicted'
        ) from exc
    return InvitationCreationResult(
        invitation=invitation,
        acceptance_token=f'{invitation_id}.{secret}',
    )


def _token(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 256:
        raise InvalidIdentityInvitationError('Invalid Identity Invitation')
    invitation_id, separator, secret = value.partition('.')
    try:
        UUID(invitation_id)
    except (TypeError, ValueError) as exc:
        raise InvalidIdentityInvitationError('Invalid Identity Invitation') from exc
    if not separator or len(secret) < 32:
        raise InvalidIdentityInvitationError('Invalid Identity Invitation')
    return invitation_id, secret


async def accept_invitation(
    db: AsyncSession, *, settings: Settings, acceptance_token: str,
    user_selected_password: str, now: datetime | None = None,
) -> InvitationAcceptanceResult:
    invitation_id, secret = _token(acceptance_token)
    current_time = _now(now)
    invitation = await db.scalar(select(IdentityInvitation).where(
        IdentityInvitation.invitation_id == invitation_id,
    ).with_for_update())
    if (
        invitation is None
        or invitation.active_slot != 1
        or invitation.consumed_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= current_time
        or not verify_machine_secret(
            secret, invitation.secret_digest,
            settings=settings, purpose=_PURPOSE,
        )
    ):
        raise InvalidIdentityInvitationError('Invalid Identity Invitation')
    if await db.scalar(select(User).where(
        User.email == invitation.email,
    ).with_for_update()) is not None:
        raise IdentityInvitationConflictError(
            'Canonical User identity already exists'
        )

    try:
        password_hash = hash_password(
            user_selected_password, minimum_length=settings.password_min_length,
        )
    except ValueError as exc:
        raise IdentityInvitationError(str(exc)) from exc
    user = User(
        email=invitation.email, password_hash=password_hash,
        display_name=invitation.display_name, status='ACTIVE',
    )
    db.add(user)
    try:
        await db.flush()
        invitation.accepted_user_id = user.id
        invitation.consumed_at = current_time
        invitation.active_slot = None
        await db.commit()
        await db.refresh(user)
        await db.refresh(invitation)
    except IntegrityError as exc:
        await db.rollback()
        raise IdentityInvitationConflictError(
            'Canonical User activation conflicted'
        ) from exc
    return InvitationAcceptanceResult(invitation=invitation, user=user)


async def revoke_invitation(
    db: AsyncSession, *, tenant_id: int, actor_membership_id: int,
    invitation_id: str, now: datetime | None = None,
) -> InvitationRevocationResult:
    await _authorize_inviter(
        db, tenant_id=tenant_id, membership_id=actor_membership_id,
    )
    invitation = await db.scalar(select(IdentityInvitation).where(
        IdentityInvitation.invitation_id == invitation_id,
        IdentityInvitation.inviter_tenant_id == tenant_id,
    ).with_for_update())
    if invitation is None:
        raise IdentityInvitationConflictError('Identity Invitation not found')
    if invitation.consumed_at is not None:
        raise IdentityInvitationConflictError(
            'Consumed Identity Invitation cannot be revoked'
        )
    if invitation.revoked_at is not None:
        return InvitationRevocationResult(invitation, 'UNCHANGED')
    invitation.revoked_at = _now(now)
    invitation.active_slot = None
    await db.commit()
    await db.refresh(invitation)
    return InvitationRevocationResult(invitation, 'UPDATE')
