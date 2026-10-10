"""Tenant-scoped administration of existing Staff credentials."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    MembershipRole,
    Permission,
    Role,
    RolePermission,
    StaffAuthSession,
    TenantMembership,
    User,
)


PERMISSION = 'staff_credentials.manage'
logger = logging.getLogger('ecip.identity')


class StaffCredentialAdministrationError(ValueError):
    pass


class StaffCredentialAuthorizationError(StaffCredentialAdministrationError):
    pass


class StaffCredentialTargetNotFoundError(StaffCredentialAdministrationError):
    pass


class StaffCredentialTargetInvalidError(StaffCredentialAdministrationError):
    pass


class StaffCredentialPasswordPolicyError(StaffCredentialAdministrationError):
    pass


@dataclass(frozen=True, slots=True)
class StaffPasswordChangeResult:
    target_user_id: int
    target_membership_id: int
    sessions_revoked: int


async def _authorize_actor(
    db: AsyncSession, *, tenant_id: int, actor_membership_id: int,
) -> None:
    actor = await db.execute(
        select(TenantMembership, User)
        .join(User, User.id == TenantMembership.user_id)
        .where(
            TenantMembership.id == actor_membership_id,
            TenantMembership.tenant_id == tenant_id,
        )
    )
    row = actor.one_or_none()
    if row is None or row.TenantMembership.status != 'ACTIVE' or row.User.status != 'ACTIVE':
        raise StaffCredentialAuthorizationError(
            'Staff credential administration actor is not active'
        )
    permission = await db.scalar(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .where(
            MembershipRole.membership_id == actor_membership_id,
            MembershipRole.tenant_id == tenant_id,
            Role.tenant_id == tenant_id,
            Role.status == 'ACTIVE',
            Permission.code == PERMISSION,
        )
        .limit(1)
    )
    if permission is None:
        raise StaffCredentialAuthorizationError(
            'Staff credential administration is not authorized'
        )


async def change_staff_password(
    db: AsyncSession,
    *,
    tenant_id: int,
    actor_membership_id: int,
    target_membership_id: int,
    new_password: str,
    password_minimum_length: int,
    correlation_id: str | None = None,
) -> StaffPasswordChangeResult:
    """Change one existing Staff password and revoke all target sessions atomically."""
    try:
        password_hash = hash_password(
            new_password, minimum_length=password_minimum_length,
        )
    except ValueError as exc:
        raise StaffCredentialPasswordPolicyError(str(exc)) from exc

    try:
        await _authorize_actor(
            db, tenant_id=tenant_id, actor_membership_id=actor_membership_id,
        )
        target_identity = await db.execute(
            select(TenantMembership.user_id)
            .where(
                TenantMembership.id == target_membership_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        target_user_id = target_identity.scalar_one_or_none()
        if target_user_id is None:
            raise StaffCredentialTargetNotFoundError('Staff identity not found')

        target_user = await db.scalar(
            select(User).where(User.id == target_user_id).with_for_update()
        )
        target_membership = await db.scalar(
            select(TenantMembership)
            .where(
                TenantMembership.id == target_membership_id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == target_user_id,
            )
            .with_for_update()
        )
        if target_user is None or target_membership is None:
            raise StaffCredentialTargetNotFoundError('Staff identity not found')
        if target_user.status != 'ACTIVE' or target_membership.status != 'ACTIVE':
            raise StaffCredentialTargetInvalidError('Staff identity is not active')

        active_sessions = tuple((await db.scalars(
            select(StaffAuthSession)
            .where(
                StaffAuthSession.user_id == target_user.id,
                StaffAuthSession.status == 'ACTIVE',
                StaffAuthSession.active_slot == 1,
            )
            .order_by(StaffAuthSession.id)
            .with_for_update()
        )).all())
        target_user.password_hash = password_hash
        closed_at = datetime.now(UTC).replace(tzinfo=None)
        for auth_session in active_sessions:
            auth_session.status = 'REPLACED'
            auth_session.active_slot = None
            auth_session.closed_at = closed_at
        await db.commit()
    except StaffCredentialAdministrationError:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    logger.info(
        'Staff credential changed administratively',
        extra={
            'event': 'staff_credential_changed',
            'tenant_id': tenant_id,
            'actor_membership_id': actor_membership_id,
            'target_user_id': target_user.id,
            'target_membership_id': target_membership.id,
            'sessions_revoked': len(active_sessions),
            'correlation_id': correlation_id,
        },
    )
    return StaffPasswordChangeResult(
        target_user_id=target_user.id,
        target_membership_id=target_membership.id,
        sessions_revoked=len(active_sessions),
    )
