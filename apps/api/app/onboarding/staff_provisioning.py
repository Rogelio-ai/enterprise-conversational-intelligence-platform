"""Restaurant onboarding orchestration over certified P1 and P2 authorities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.identity import access_provisioning, invitations
from app.models import (
    IdentityInvitation,
    Location,
    OnboardingImport,
    OnboardingStaffContinuation,
    Permission,
    Role,
    RolePermission,
    User,
)


class StaffProvisioningError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StaffPlan:
    values: dict[str, object]
    operation: str


@dataclass(frozen=True, slots=True)
class InvitationDelivery:
    staff_key: str
    email: str
    invitation_id: str
    acceptance_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class StaffOutcome:
    continuation: OnboardingStaffContinuation
    status: str
    operation: str | None
    delivery: InvitationDelivery | None = None


def _exact_text(value: object, *, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise StaffProvisioningError(f'Invalid Staff {label}')
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise StaffProvisioningError(f'Invalid Staff {label}')
    return normalized


async def plan_staff_request(
    db: AsyncSession, *, values: dict[str, object], tenant_id: int,
    organization_id: int, location_id: int,
    actor_permissions: frozenset[str],
) -> StaffPlan:
    normalized = dict(values)
    normalized['staff_key'] = _exact_text(
        values.get('staff_key'), label='key', maximum=100,
    )
    normalized['display_name'] = _exact_text(
        values.get('display_name'), label='display name', maximum=200,
    )
    normalized['email'] = invitations.normalize_email(values.get('email'))
    normalized['role_name'] = _exact_text(
        values.get('role_name'), label='Role', maximum=100,
    )
    if values.get('status') != 'ACTIVE':
        raise StaffProvisioningError(
            'Only ACTIVE Staff access can be provisioned by the certified authority'
        )
    if not access_provisioning.can_provision_access(actor_permissions):
        raise StaffProvisioningError(
            'Staff provisioning requires user, Role, and Location management authority'
        )

    role = await db.scalar(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.name == normalized['role_name'],
    ))
    if (
        role is None or role.status != 'ACTIVE'
        or role.name != normalized['role_name']
    ):
        raise StaffProvisioningError(
            'Staff Role is not an existing active Tenant Role'
        )
    target_permissions = frozenset((await db.scalars(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
    )).all())
    if not access_provisioning.can_assign_role(
        actor_permissions, target_permissions,
    ):
        raise StaffProvisioningError(
            'Staff Role exceeds the importing actor delegation authority'
        )
    normalized['requested_permission_codes'] = sorted(target_permissions)
    location = await db.scalar(select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
        Location.status == 'ACTIVE',
    ))
    if location is None:
        raise StaffProvisioningError(
            'Staff Location is not active in the authorized scope'
        )

    user = await invitations.resolve_existing_user(
        db, email=str(normalized['email']),
    )
    if user is not None and user.status != 'ACTIVE':
        raise StaffProvisioningError(
            'Existing canonical Staff User is not active'
        )
    return StaffPlan(
        values=normalized,
        operation='PROVISION' if user is not None else 'INVITE',
    )


async def _logical_continuation(
    db: AsyncSession, *, tenant_id: int, email: str,
    role_name: str, location_id: int, for_update: bool = False,
) -> OnboardingStaffContinuation | None:
    statement = select(OnboardingStaffContinuation).where(
        OnboardingStaffContinuation.tenant_id == tenant_id,
        OnboardingStaffContinuation.normalized_email == email,
        OnboardingStaffContinuation.role_name == role_name,
        OnboardingStaffContinuation.location_id == location_id,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _assert_equivalent(
    continuation: OnboardingStaffContinuation, *, organization_id: int,
    staff_key: str, display_name: str,
    requested_permission_codes: list[str],
) -> None:
    if (
        continuation.organization_id != organization_id
        or continuation.staff_key != staff_key
        or continuation.display_name != display_name
        or continuation.requested_permission_codes != requested_permission_codes
    ):
        raise StaffProvisioningError(
            'Existing Staff continuation conflicts with the requested identity scope'
        )


def _completion_operation(
    result: access_provisioning.AccessProvisioningResult,
) -> str:
    operations = {
        result.membership_operation,
        result.role_operation,
        *(value.operation for value in result.location_grants),
    }
    return 'CREATE' if 'CREATE' in operations else 'UNCHANGED'


async def _save_new_continuation(
    db: AsyncSession, continuation: OnboardingStaffContinuation,
) -> OnboardingStaffContinuation:
    db.add(continuation)
    try:
        await db.commit()
        await db.refresh(continuation)
        return continuation
    except IntegrityError:
        await db.rollback()
        existing = await _logical_continuation(
            db, tenant_id=continuation.tenant_id,
            email=continuation.normalized_email,
            role_name=continuation.role_name,
            location_id=continuation.location_id,
            for_update=True,
        )
        if existing is None:
            raise
        _assert_equivalent(
            existing, organization_id=continuation.organization_id,
            staff_key=continuation.staff_key,
            display_name=continuation.display_name,
            requested_permission_codes=continuation.requested_permission_codes,
        )
        return existing


def _new_continuation(
    *, evidence: OnboardingImport, actor_membership_id: int,
    values: dict[str, object], invitation: IdentityInvitation | None,
    user: User | None, status: str, operation: str | None,
    error_code: str | None,
) -> OnboardingStaffContinuation:
    return OnboardingStaffContinuation(
        continuation_id=str(uuid4()), onboarding_import_id=evidence.id,
        tenant_id=evidence.tenant_id, organization_id=evidence.organization_id,
        location_id=evidence.location_id,
        actor_membership_id=actor_membership_id,
        identity_invitation_id=None if invitation is None else invitation.id,
        user_id=None if user is None else user.id,
        staff_key=str(values['staff_key']),
        normalized_email=str(values['email']),
        display_name=str(values['display_name']),
        role_name=str(values['role_name']), status=status,
        requested_permission_codes=list(values['requested_permission_codes']),
        completion_operation=operation, error_code=error_code,
        completed_at=(
            datetime.now(UTC).replace(tzinfo=None)
            if status == 'COMPLETE' else None
        ),
    )


async def _mark_security_conflict(
    db: AsyncSession, *, continuation: OnboardingStaffContinuation,
    user: User | None,
) -> StaffOutcome:
    current = await _logical_continuation(
        db, tenant_id=continuation.tenant_id,
        email=continuation.normalized_email,
        role_name=continuation.role_name,
        location_id=continuation.location_id,
        for_update=True,
    )
    if current is None:
        raise StaffProvisioningError('Staff continuation disappeared')
    if current.status == 'COMPLETE':
        return StaffOutcome(current, 'COMPLETE', current.completion_operation)
    current.user_id = None if user is None else user.id
    current.status = 'SECURITY_CONFLICT'
    current.completion_operation = None
    current.error_code = 'ACCESS_REVALIDATION_FAILED'
    current.completed_at = None
    await db.commit()
    await db.refresh(current)
    return StaffOutcome(current, current.status, None)


async def _mark_terminal_failure(
    db: AsyncSession, *, continuation: OnboardingStaffContinuation,
    error_code: str,
) -> StaffOutcome:
    current = await _logical_continuation(
        db, tenant_id=continuation.tenant_id,
        email=continuation.normalized_email,
        role_name=continuation.role_name,
        location_id=continuation.location_id,
        for_update=True,
    )
    if current is None:
        raise StaffProvisioningError('Staff continuation disappeared')
    if current.status == 'COMPLETE':
        return StaffOutcome(current, 'COMPLETE', current.completion_operation)
    current.status = 'TERMINAL_FAILURE'
    current.completion_operation = None
    current.error_code = error_code
    current.completed_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(current)
    return StaffOutcome(current, current.status, None)


async def resume_continuation(
    db: AsyncSession, *, continuation: OnboardingStaffContinuation,
) -> StaffOutcome:
    if continuation.status == 'COMPLETE':
        return StaffOutcome(
            continuation, 'COMPLETE', continuation.completion_operation,
        )
    if continuation.status in {'SECURITY_CONFLICT', 'TERMINAL_FAILURE'}:
        return StaffOutcome(continuation, continuation.status, None)
    user = await invitations.resolve_existing_user(
        db, email=continuation.normalized_email,
    )
    if user is None:
        if continuation.identity_invitation_id is None:
            return await _mark_security_conflict(
                db, continuation=continuation, user=None,
            )
        invitation = await db.scalar(select(IdentityInvitation).where(
            IdentityInvitation.id == continuation.identity_invitation_id,
        ))
        if (
            invitation is None or invitation.revoked_at is not None
            or invitation.expires_at <= datetime.now(UTC).replace(tzinfo=None)
        ):
            return await _mark_terminal_failure(
                db, continuation=continuation,
                error_code='INVITATION_UNAVAILABLE',
            )
        return StaffOutcome(continuation, 'PENDING_ACCEPTANCE', None)
    if user.status != 'ACTIVE':
        return await _mark_security_conflict(
            db, continuation=continuation, user=user,
        )
    current_permissions = frozenset((await db.scalars(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(
            Role.tenant_id == continuation.tenant_id,
            Role.name == continuation.role_name,
            Role.status == 'ACTIVE',
        )
    )).all())
    if current_permissions != frozenset(continuation.requested_permission_codes):
        return await _mark_security_conflict(
            db, continuation=continuation, user=user,
        )
    try:
        result = await access_provisioning.provision_access(
            db, tenant_id=continuation.tenant_id,
            actor_membership_id=continuation.actor_membership_id,
            user_id=user.id, role_name=continuation.role_name,
            locations=(access_provisioning.LocationGrantCandidate(
                organization_id=continuation.organization_id,
                location_id=continuation.location_id,
            ),),
        )
    except access_provisioning.AccessProvisioningError:
        return await _mark_security_conflict(
            db, continuation=continuation, user=user,
        )
    current = await _logical_continuation(
        db, tenant_id=continuation.tenant_id,
        email=continuation.normalized_email,
        role_name=continuation.role_name,
        location_id=continuation.location_id,
        for_update=True,
    )
    if current is None:
        raise StaffProvisioningError('Staff continuation disappeared')
    if current.status != 'COMPLETE':
        current.user_id = user.id
        current.status = 'COMPLETE'
        current.completion_operation = _completion_operation(result)
        current.error_code = None
        current.completed_at = datetime.now(UTC).replace(tzinfo=None)
        await db.commit()
        await db.refresh(current)
    return StaffOutcome(current, 'COMPLETE', current.completion_operation)


async def provision_staff_request(
    db: AsyncSession, *, settings: Settings, evidence: OnboardingImport,
    actor_membership_id: int, values: dict[str, object],
) -> StaffOutcome:
    email = str(values['email'])
    role_name = str(values['role_name'])
    existing = await _logical_continuation(
        db, tenant_id=evidence.tenant_id, email=email,
        role_name=role_name, location_id=evidence.location_id,
        for_update=True,
    )
    if existing is not None:
        _assert_equivalent(
            existing, organization_id=evidence.organization_id,
            staff_key=str(values['staff_key']),
            display_name=str(values['display_name']),
            requested_permission_codes=list(values['requested_permission_codes']),
        )
        return await resume_continuation(db, continuation=existing)

    user = await invitations.resolve_existing_user(db, email=email)
    if user is not None:
        if user.status != 'ACTIVE':
            continuation = await _save_new_continuation(db, _new_continuation(
                evidence=evidence, actor_membership_id=actor_membership_id,
                values=values, invitation=None, user=user,
                status='SECURITY_CONFLICT', operation=None,
                error_code='IDENTITY_NOT_ACTIVE',
            ))
            return StaffOutcome(continuation, continuation.status, None)
        try:
            result = await access_provisioning.provision_access(
                db, tenant_id=evidence.tenant_id,
                actor_membership_id=actor_membership_id,
                user_id=user.id, role_name=role_name,
                locations=(access_provisioning.LocationGrantCandidate(
                    organization_id=evidence.organization_id,
                    location_id=evidence.location_id,
                ),),
            )
        except access_provisioning.AccessProvisioningError:
            continuation = await _save_new_continuation(db, _new_continuation(
                evidence=evidence, actor_membership_id=actor_membership_id,
                values=values, invitation=None, user=user,
                status='SECURITY_CONFLICT', operation=None,
                error_code='ACCESS_REVALIDATION_FAILED',
            ))
            return StaffOutcome(continuation, continuation.status, None)
        operation = _completion_operation(result)
        continuation = await _save_new_continuation(db, _new_continuation(
            evidence=evidence, actor_membership_id=actor_membership_id,
            values=values, invitation=None, user=user,
            status='COMPLETE', operation=operation, error_code=None,
        ))
        return StaffOutcome(
            continuation, continuation.status,
            continuation.completion_operation,
        )

    delivery: InvitationDelivery | None = None
    try:
        invited = await invitations.invite_identity(
            db, settings=settings, tenant_id=evidence.tenant_id,
            actor_membership_id=actor_membership_id,
            email=email, display_name=str(values['display_name']),
        )
        invitation = invited.invitation
        delivery = InvitationDelivery(
            staff_key=str(values['staff_key']), email=email,
            invitation_id=invitation.invitation_id,
            acceptance_token=invited.acceptance_token,
            expires_at=invitation.expires_at,
        )
    except invitations.IdentityInvitationConflictError:
        user = await invitations.resolve_existing_user(db, email=email)
        if user is not None:
            return await provision_staff_request(
                db, settings=settings, evidence=evidence,
                actor_membership_id=actor_membership_id, values=values,
            )
        invitation = await db.scalar(select(IdentityInvitation).where(
            IdentityInvitation.email == email,
            IdentityInvitation.active_slot == 1,
        ).with_for_update())
        if invitation is None:
            raise StaffProvisioningError(
                'Identity invitation conflicted without reusable state'
            )

    invitation_database_id = invitation.id
    continuation = await _save_new_continuation(db, _new_continuation(
        evidence=evidence, actor_membership_id=actor_membership_id,
        values=values, invitation=invitation, user=None,
        status='PENDING_ACCEPTANCE', operation=None, error_code=None,
    ))
    if continuation.identity_invitation_id != invitation_database_id:
        delivery = None
    return StaffOutcome(
        continuation, continuation.status,
        continuation.completion_operation, delivery,
    )
