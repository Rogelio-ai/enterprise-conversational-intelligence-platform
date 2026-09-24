from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenValidationError, decode_access_token
from app.models import (
    MembershipLocationRole,
    MembershipRole,
    Permission,
    Role,
    RolePermission,
    StaffAuthSession,
    Tenant,
    TenantMembership,
    User,
)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')


@dataclass(frozen=True)
class LocationAuthority:
    location_id: int
    roles: tuple[str, ...]
    permissions: frozenset[str]


@dataclass(frozen=True)
class AuthenticatedContext:
    user_id: int
    username: str
    email: str | None
    display_name: str
    tenant_id: int
    tenant_name: str
    tenant_slug: str
    membership_id: int
    authorized_location_ids: tuple[int, ...]
    roles: tuple[str, ...]
    permissions: frozenset[str]
    location_authorities: tuple[LocationAuthority, ...]

    def authority_for_location(self, location_id: int) -> LocationAuthority | None:
        return next(
            (value for value in self.location_authorities if value.location_id == location_id),
            None,
        )


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async for session in request.app.state.database.session():
        session.info['payment_executor_registry'] = request.app.state.payment_executor_registry
        session.info['merchant_credential_resolver'] = (
            request.app.state.merchant_credential_resolver
        )
        session.info['fiscal_provider_registry'] = (
            request.app.state.fiscal_provider_registry
        )
        session.info['fiscal_credential_resolver'] = (
            request.app.state.fiscal_credential_resolver
        )
        session.info['fiscal_artifact_storage'] = (
            request.app.state.fiscal_artifact_storage
        )
        yield session


def _unauthorized(message: str = 'Invalid authentication credentials') -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={'WWW-Authenticate': 'Bearer'},
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


async def get_authenticated_context(
    request: Request,
    token: str = Depends(oauth2_scheme),
    requested_tenant_id: str | None = Header(default=None, alias='X-Tenant-ID'),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedContext:
    try:
        payload = decode_access_token(token, settings=request.app.state.settings)
        user_id = int(payload['sub'])
        token_tenant_id = int(payload['tenant_id'])
        membership_id = int(payload['membership_id'])
        session_id = payload['session_id']
    except (TokenValidationError, TypeError, ValueError, KeyError) as exc:
        raise _unauthorized() from exc

    if requested_tenant_id is not None:
        try:
            selected_tenant_id = int(requested_tenant_id)
        except ValueError as exc:
            raise _forbidden('Requested Tenant context is not authorized') from exc
        if selected_tenant_id != token_tenant_id:
            raise _forbidden('Requested Tenant context is not authorized')

    result = await db.execute(
        select(User, TenantMembership, Tenant, StaffAuthSession)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .join(
            StaffAuthSession,
            (StaffAuthSession.user_id == User.id)
            & (StaffAuthSession.membership_id == TenantMembership.id)
            & (StaffAuthSession.tenant_id == Tenant.id),
        )
        .where(
            User.id == user_id,
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == token_tenant_id,
            StaffAuthSession.session_id == session_id,
            StaffAuthSession.status == 'ACTIVE',
            StaffAuthSession.active_slot == 1,
        )
    )
    authority = result.first()
    if authority is None:
        raise _unauthorized()
    user, membership, tenant, auth_session = authority
    if user.status != 'ACTIVE':
        raise _unauthorized()
    if membership.status != 'ACTIVE':
        raise _forbidden('Tenant membership is not active')
    if tenant.status != 'ACTIVE':
        raise _forbidden('Tenant is not active')

    assignment_result = await db.execute(
        select(MembershipLocationRole.location_id, Role.id, Role.name)
        .join(Role, Role.id == MembershipLocationRole.role_id)
        .where(
            MembershipLocationRole.membership_id == membership.id,
            MembershipLocationRole.tenant_id == tenant.id,
            Role.tenant_id == tenant.id,
            Role.status == 'ACTIVE',
        )
        .order_by(MembershipLocationRole.location_id, Role.name)
    )
    assignments = list(assignment_result.all())
    role_ids = tuple(sorted({row.id for row in assignments}))
    scoped_permission_result = await db.execute(
        select(RolePermission.role_id, Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id.in_(role_ids))
        .order_by(RolePermission.role_id, Permission.code)
    )
    permissions_by_role: dict[int, set[str]] = {}
    for role_id, code in scoped_permission_result.all():
        permissions_by_role.setdefault(role_id, set()).add(code)
    roles_by_location: dict[int, list[str]] = {}
    permissions_by_location: dict[int, set[str]] = {}
    for location_id, role_id, role_name in assignments:
        roles_by_location.setdefault(location_id, []).append(role_name)
        permissions_by_location.setdefault(location_id, set()).update(
            permissions_by_role.get(role_id, set())
        )
    location_authorities = tuple(
        LocationAuthority(
            location_id=location_id,
            roles=tuple(roles_by_location[location_id]),
            permissions=frozenset(permissions_by_location.get(location_id, set())),
        )
        for location_id in sorted(roles_by_location)
    )
    role_result = await db.execute(
        select(distinct(Role.name))
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .where(
            MembershipRole.membership_id == membership.id,
            MembershipRole.tenant_id == tenant.id,
            Role.tenant_id == tenant.id,
            Role.status == 'ACTIVE',
        )
        .order_by(Role.name)
    )
    roles = tuple(role_result.scalars().all())
    permission_result = await db.execute(
        select(distinct(Permission.code))
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .where(
            MembershipRole.membership_id == membership.id,
            MembershipRole.tenant_id == tenant.id,
            Role.tenant_id == tenant.id,
            Role.status == 'ACTIVE',
        )
        .order_by(Permission.code)
    )
    permissions = frozenset(permission_result.scalars().all())
    authorized_location_ids = tuple(value.location_id for value in location_authorities)
    request.state.user_id = user.id
    request.state.tenant_id = tenant.id
    request.state.auth_session_id = auth_session.session_id
    return AuthenticatedContext(
        user_id=user.id,
        username=user.username or '',
        email=user.email,
        display_name=user.display_name,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        membership_id=membership.id,
        authorized_location_ids=authorized_location_ids,
        roles=roles,
        permissions=permissions,
        location_authorities=location_authorities,
    )


def require_permission(permission_code: str) -> Callable[..., AuthenticatedContext]:
    async def permission_checker(
        context: AuthenticatedContext = Depends(get_authenticated_context),
    ) -> AuthenticatedContext:
        if permission_code not in context.permissions:
            raise _forbidden('Insufficient permission')
        return context

    return permission_checker


async def require_staff_location_access(
    location_id: int,
    context: AuthenticatedContext = Depends(get_authenticated_context),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedContext:
    if context.authority_for_location(location_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')
    return context


def require_location_permission(permission_code: str) -> Callable[..., AuthenticatedContext]:
    async def location_permission_checker(
        location_id: int,
        context: AuthenticatedContext = Depends(require_staff_location_access),
    ) -> AuthenticatedContext:
        authority = context.authority_for_location(location_id)
        if authority is None or permission_code not in authority.permissions:
            raise _forbidden('Insufficient permission')
        return context

    return location_permission_checker
