from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenValidationError, decode_access_token
from app.models import MembershipRole, Permission, Role, RolePermission, Tenant, TenantMembership, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')


@dataclass(frozen=True)
class AuthenticatedContext:
    user_id: int
    email: str
    display_name: str
    tenant_id: int
    tenant_name: str
    tenant_slug: str
    membership_id: int
    roles: tuple[str, ...]
    permissions: frozenset[str]


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
        select(User, TenantMembership, Tenant)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(
            User.id == user_id,
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == token_tenant_id,
        )
    )
    authority = result.first()
    if authority is None:
        raise _unauthorized()
    user, membership, tenant = authority
    if user.status != 'ACTIVE':
        raise _unauthorized()
    if membership.status != 'ACTIVE':
        raise _forbidden('Tenant membership is not active')
    if tenant.status != 'ACTIVE':
        raise _forbidden('Tenant is not active')

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
    request.state.user_id = user.id
    request.state.tenant_id = tenant.id
    return AuthenticatedContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        membership_id=membership.id,
        roles=roles,
        permissions=permissions,
    )


def require_permission(permission_code: str) -> Callable[..., AuthenticatedContext]:
    async def permission_checker(
        context: AuthenticatedContext = Depends(get_authenticated_context),
    ) -> AuthenticatedContext:
        if permission_code not in context.permissions:
            raise _forbidden('Insufficient permission')
        return context

    return permission_checker
