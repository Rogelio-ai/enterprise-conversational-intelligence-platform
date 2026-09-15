"""Actor-aware provisioning of existing identity access within one Tenant."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Location,
    MembershipLocationGrant,
    MembershipRole,
    Organization,
    Permission,
    Role,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
)


_REQUIRED_PERMISSIONS = frozenset({'user.manage', 'role.manage', 'location.manage'})


class AccessProvisioningError(ValueError):
    pass


class AccessProvisioningAuthorizationError(AccessProvisioningError):
    pass


class AccessProvisioningConflictError(AccessProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class LocationGrantCandidate:
    organization_id: int
    location_id: int


@dataclass(frozen=True, slots=True)
class LocationGrantResult:
    organization_id: int
    location_id: int
    operation: str


@dataclass(frozen=True, slots=True)
class AccessProvisioningResult:
    membership: TenantMembership
    role: Role
    membership_operation: str
    role_operation: str
    location_grants: tuple[LocationGrantResult, ...]


def can_assign_role(
    actor_permissions: frozenset[str], target_permissions: frozenset[str],
) -> bool:
    """An actor may delegate no permission they do not currently possess."""
    return target_permissions <= actor_permissions


async def _locked_permissions_for_roles(
    db: AsyncSession, *, role_ids: tuple[int, ...],
) -> frozenset[str]:
    if not role_ids:
        return frozenset()
    assignments = tuple((await db.scalars(
        select(RolePermission)
        .where(RolePermission.role_id.in_(role_ids))
        .order_by(RolePermission.id)
        .with_for_update()
    )).all())
    permission_ids = tuple(sorted({value.permission_id for value in assignments}))
    if not permission_ids:
        return frozenset()
    permissions = tuple((await db.scalars(
        select(Permission)
        .where(Permission.id.in_(permission_ids))
        .order_by(Permission.id)
        .with_for_update()
    )).all())
    return frozenset(value.code for value in permissions)


async def _authorize_actor(
    db: AsyncSession, *, tenant_id: int, actor_membership_id: int,
) -> tuple[frozenset[str], frozenset[int]]:
    actor_membership = await db.scalar(select(TenantMembership).where(
        TenantMembership.id == actor_membership_id,
        TenantMembership.tenant_id == tenant_id,
    ).with_for_update())
    if actor_membership is None or actor_membership.status != 'ACTIVE':
        raise AccessProvisioningAuthorizationError(
            'Access provisioning actor is not an active Tenant member'
        )
    actor = await db.scalar(select(User).where(
        User.id == actor_membership.user_id,
    ).with_for_update())
    if actor is None or actor.status != 'ACTIVE':
        raise AccessProvisioningAuthorizationError(
            'Access provisioning actor is not active'
        )

    assignments = tuple((await db.scalars(
        select(MembershipRole)
        .where(
            MembershipRole.membership_id == actor_membership_id,
            MembershipRole.tenant_id == tenant_id,
        )
        .order_by(MembershipRole.id)
        .with_for_update()
    )).all())
    assigned_role_ids = tuple(sorted({value.role_id for value in assignments}))
    active_roles: tuple[Role, ...] = ()
    if assigned_role_ids:
        active_roles = tuple((await db.scalars(
            select(Role)
            .where(
                Role.id.in_(assigned_role_ids),
                Role.tenant_id == tenant_id,
                Role.status == 'ACTIVE',
            )
            .order_by(Role.id)
            .with_for_update()
        )).all())
    permissions = await _locked_permissions_for_roles(
        db, role_ids=tuple(value.id for value in active_roles),
    )
    missing = _REQUIRED_PERMISSIONS - permissions
    if missing:
        raise AccessProvisioningAuthorizationError(
            'Access provisioning authority is required'
        )

    grants = tuple((await db.scalars(
        select(MembershipLocationGrant)
        .where(
            MembershipLocationGrant.membership_id == actor_membership_id,
            MembershipLocationGrant.tenant_id == tenant_id,
        )
        .order_by(MembershipLocationGrant.id)
        .with_for_update()
    )).all())
    return permissions, frozenset(value.location_id for value in grants)


def _role_name(value: object) -> str:
    if not isinstance(value, str):
        raise AccessProvisioningConflictError('Invalid Role name')
    normalized = value.strip()
    if not normalized or len(normalized) > 100:
        raise AccessProvisioningConflictError('Invalid Role name')
    return normalized


def _location_candidates(
    values: tuple[LocationGrantCandidate, ...],
) -> tuple[LocationGrantCandidate, ...]:
    if not values:
        raise AccessProvisioningConflictError(
            'At least one Location grant is required'
        )
    by_location: dict[int, LocationGrantCandidate] = {}
    for value in values:
        if value.organization_id <= 0 or value.location_id <= 0:
            raise AccessProvisioningConflictError('Invalid Location grant scope')
        if value.location_id in by_location:
            raise AccessProvisioningConflictError(
                'Duplicate Location grant requested'
            )
        by_location[value.location_id] = value
    return tuple(by_location[key] for key in sorted(by_location))


async def provision_access(
    db: AsyncSession, *, tenant_id: int, actor_membership_id: int,
    user_id: int, role_name: str,
    locations: tuple[LocationGrantCandidate, ...],
) -> AccessProvisioningResult:
    """Validate a complete access plan, then atomically converge it."""
    canonical_role_name = _role_name(role_name)
    requested_locations = _location_candidates(locations)

    tenant = await db.scalar(select(Tenant).where(
        Tenant.id == tenant_id,
    ).with_for_update())
    if tenant is None or tenant.status != 'ACTIVE':
        raise AccessProvisioningAuthorizationError(
            'Access provisioning Tenant is not active'
        )
    actor_permissions, actor_location_ids = await _authorize_actor(
        db, tenant_id=tenant_id, actor_membership_id=actor_membership_id,
    )

    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or user.status != 'ACTIVE':
        raise AccessProvisioningConflictError(
            'Target canonical User is not active'
        )

    role = await db.scalar(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.name == canonical_role_name,
    ).with_for_update())
    if (
        role is None or role.status != 'ACTIVE'
        or role.name != canonical_role_name
    ):
        raise AccessProvisioningConflictError(
            'Target Role is not an existing active Tenant Role'
        )
    target_permissions = await _locked_permissions_for_roles(db, role_ids=(role.id,))
    if not can_assign_role(actor_permissions, target_permissions):
        raise AccessProvisioningAuthorizationError(
            'Actor cannot delegate the target Role permissions'
        )

    organization_ids = tuple(sorted({value.organization_id for value in requested_locations}))
    organizations = tuple((await db.scalars(
        select(Organization)
        .where(
            Organization.id.in_(organization_ids),
            Organization.tenant_id == tenant_id,
        )
        .order_by(Organization.id)
        .with_for_update()
    )).all())
    organization_by_id = {value.id: value for value in organizations}
    location_ids = tuple(value.location_id for value in requested_locations)
    location_rows = tuple((await db.scalars(
        select(Location)
        .where(Location.id.in_(location_ids), Location.tenant_id == tenant_id)
        .order_by(Location.id)
        .with_for_update()
    )).all())
    location_by_id = {value.id: value for value in location_rows}
    for candidate in requested_locations:
        organization = organization_by_id.get(candidate.organization_id)
        location = location_by_id.get(candidate.location_id)
        if (
            organization is None or organization.status != 'ACTIVE'
            or location is None or location.status != 'ACTIVE'
            or location.organization_id != candidate.organization_id
        ):
            raise AccessProvisioningConflictError(
                'Target Location is not active in the requested Tenant/Organization scope'
            )
        if candidate.location_id not in actor_location_ids:
            raise AccessProvisioningAuthorizationError(
                'Actor cannot delegate an unauthorized Location'
            )

    membership = await db.scalar(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == user.id,
    ).with_for_update())
    if membership is not None and membership.status != 'ACTIVE':
        raise AccessProvisioningConflictError(
            'Existing Tenant Membership is not active'
        )

    membership_operation = 'UNCHANGED'
    role_operation = 'CREATE'
    existing_grants: dict[int, MembershipLocationGrant] = {}
    assignment: MembershipRole | None = None
    if membership is not None:
        assignment = await db.scalar(select(MembershipRole).where(
            MembershipRole.tenant_id == tenant_id,
            MembershipRole.membership_id == membership.id,
            MembershipRole.role_id == role.id,
        ).with_for_update())
        role_operation = 'UNCHANGED' if assignment is not None else 'CREATE'
        grants = tuple((await db.scalars(select(MembershipLocationGrant).where(
            MembershipLocationGrant.tenant_id == tenant_id,
            MembershipLocationGrant.membership_id == membership.id,
            MembershipLocationGrant.location_id.in_(location_ids),
        ).order_by(MembershipLocationGrant.id).with_for_update())).all())
        existing_grants = {value.location_id: value for value in grants}

    if membership is None:
        membership = TenantMembership(
            tenant_id=tenant_id, user_id=user.id, status='ACTIVE',
        )
        db.add(membership)
        membership_operation = 'CREATE'

    try:
        if membership_operation == 'CREATE':
            await db.flush()
        if assignment is None:
            db.add(MembershipRole(
                tenant_id=tenant_id,
                membership_id=membership.id,
                role_id=role.id,
            ))
        location_results: list[LocationGrantResult] = []
        for candidate in requested_locations:
            operation = 'UNCHANGED'
            if candidate.location_id not in existing_grants:
                db.add(MembershipLocationGrant(
                    tenant_id=tenant_id,
                    membership_id=membership.id,
                    location_id=candidate.location_id,
                ))
                operation = 'CREATE'
            location_results.append(LocationGrantResult(
                organization_id=candidate.organization_id,
                location_id=candidate.location_id,
                operation=operation,
            ))
        await db.commit()
        await db.refresh(membership)
    except IntegrityError as exc:
        await db.rollback()
        raise AccessProvisioningConflictError(
            'Access provisioning conflicted with concurrent state'
        ) from exc
    return AccessProvisioningResult(
        membership=membership,
        role=role,
        membership_operation=membership_operation,
        role_operation=role_operation,
        location_grants=tuple(location_results),
    )
