"""Shared waiter eligibility query used by staffing and service responsibility."""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MembershipLocationGrant,
    MembershipRole,
    Permission,
    Role,
    RolePermission,
    TenantMembership,
    User,
)


WAITER_CAPABILITIES = frozenset({'order_draft.manage', 'restaurant_service.manage'})


def eligible_waiter_statement(
    *, tenant_id: int, location_id: int, membership_id: int | None = None,
):
    statement = (
        select(TenantMembership.id, User.display_name, User.email)
        .join(User, User.id == TenantMembership.user_id)
        .join(
            MembershipLocationGrant,
            (MembershipLocationGrant.membership_id == TenantMembership.id)
            & (MembershipLocationGrant.tenant_id == TenantMembership.tenant_id),
        )
        .join(
            MembershipRole,
            (MembershipRole.membership_id == TenantMembership.id)
            & (MembershipRole.tenant_id == TenantMembership.tenant_id),
        )
        .join(
            Role,
            (Role.id == MembershipRole.role_id)
            & (Role.tenant_id == MembershipRole.tenant_id),
        )
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == 'ACTIVE',
            User.status == 'ACTIVE',
            MembershipLocationGrant.location_id == location_id,
            Role.status == 'ACTIVE',
            Permission.code.in_(WAITER_CAPABILITIES),
        )
        .group_by(TenantMembership.id, User.display_name, User.email)
        .having(func.count(distinct(Permission.code)) == len(WAITER_CAPABILITIES))
    )
    if membership_id is not None:
        statement = statement.where(TenantMembership.id == membership_id)
    return statement


async def eligible_waiter_ids(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    membership_ids: Collection[int],
) -> set[int]:
    requested = set(membership_ids)
    if not requested:
        return set()
    statement = eligible_waiter_statement(
        tenant_id=tenant_id, location_id=location_id,
    ).where(TenantMembership.id.in_(requested))
    return {int(row.id) for row in (await db.execute(statement)).all()}
