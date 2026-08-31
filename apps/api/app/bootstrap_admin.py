from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import normalize_email
from app.core.config import Settings, get_settings
from app.core.security import hash_password, validate_password
from app.db.session import DatabaseManager
from app.models import MembershipRole, Permission, Role, RolePermission, Tenant, TenantMembership, User


ADMIN_ROLE_NAME = 'TENANT_ADMIN'
CORE_PERMISSIONS = {
    'tenant.read': 'Read the current Tenant context.',
    'tenant.manage': 'Manage Tenant core settings.',
    'user.read': 'Read Tenant user information.',
    'user.manage': 'Manage Tenant users.',
    'role.read': 'Read Tenant roles and permissions.',
    'role.manage': 'Manage Tenant roles and permission assignments.',
    'organization.read': 'Read Tenant organizations.',
    'organization.manage': 'Manage Tenant organizations.',
    'location.read': 'Read Tenant locations.',
    'location.manage': 'Manage Tenant locations.',
    'resource.read': 'Read Tenant resources.',
    'resource.manage': 'Manage Tenant resources.',
    'customer.read': 'Read Tenant customers.',
    'customer.manage': 'Manage Tenant customers.',
    'product.read': 'Read Organization products and categories.',
    'product.manage': 'Manage Organization products and categories.',
    'menu.read': 'Read Organization menus.',
    'menu.manage': 'Manage Organization menus.',
    'pricing.read': 'Read Organization product prices.',
    'pricing.manage': 'Manage Organization product prices.',
    'promotion.read': 'Read Organization promotions.',
    'promotion.manage': 'Manage Organization promotions.',
    'conversation.read': 'Read Tenant conversations, participants, and messages.',
    'conversation.manage': 'Manage Tenant conversations, participants, and messages.',
    'order_draft.read': 'Read canonical Restaurant Order Drafts.',
    'order_draft.manage': 'Manage canonical Restaurant Order Drafts.',
    'restaurant_service.read': 'Read Restaurant service sessions.',
    'restaurant_service.manage': 'Manage Restaurant service sessions.',
    'restaurant_order.read': 'Read immutable accepted Restaurant Orders.',
    'pos_submission.read': 'Read POS order submission state and history.',
    'pos_submission.submit': 'Submit accepted Restaurant Orders to a POS.',
    'pos_submission.retry': 'Retry safely retryable POS order submissions.',
    'pos_submission.recover': 'Recover uncertain POS order submissions.',
    'preparation.read': 'Read preparation configuration, routing, and work.',
    'preparation.route': 'Route accepted Restaurant Orders to preparation.',
    'preparation.configure': 'Configure preparation ownership, areas, and product routes.',
    'preparation.execute': 'Execute native Preparation Work Items.',
    'preparation.dispatch': 'Perform human preparation dispatch interventions.',
    'preparation.connector.manage': 'Manage Restaurant Local Connector machine credentials.',
}
_SLUG_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


@dataclass(frozen=True)
class BootstrapInput:
    tenant_name: str
    tenant_slug: str
    admin_email: str
    admin_password: str
    admin_display_name: str

    @classmethod
    def from_environment(cls) -> 'BootstrapInput':
        required = {
            'tenant_name': 'BOOTSTRAP_TENANT_NAME',
            'tenant_slug': 'BOOTSTRAP_TENANT_SLUG',
            'admin_email': 'BOOTSTRAP_ADMIN_EMAIL',
            'admin_password': 'BOOTSTRAP_ADMIN_PASSWORD',
        }
        values: dict[str, str] = {}
        missing: list[str] = []
        for field_name, variable_name in required.items():
            value = os.getenv(variable_name, '').strip()
            if not value:
                missing.append(variable_name)
            values[field_name] = value
        if missing:
            raise ValueError(f"Missing required bootstrap variables: {', '.join(missing)}")
        values['admin_display_name'] = os.getenv(
            'BOOTSTRAP_ADMIN_DISPLAY_NAME', values['admin_email']
        ).strip()
        return cls(**values)


@dataclass(frozen=True)
class BootstrapResult:
    tenant_id: int
    user_id: int
    membership_id: int
    role_id: int
    created: tuple[str, ...]


def _validate_input(values: BootstrapInput, settings: Settings) -> BootstrapInput:
    slug = values.tenant_slug.strip().casefold()
    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError('BOOTSTRAP_TENANT_SLUG must be a lowercase URL-safe slug')
    email = normalize_email(values.admin_email)
    if '@' not in email or email.startswith('@') or email.endswith('@'):
        raise ValueError('BOOTSTRAP_ADMIN_EMAIL must be a valid email')
    if not values.tenant_name.strip() or not values.admin_display_name.strip():
        raise ValueError('Bootstrap names must not be empty')
    validate_password(values.admin_password, minimum_length=settings.password_min_length)
    return BootstrapInput(
        tenant_name=values.tenant_name.strip(),
        tenant_slug=slug,
        admin_email=email,
        admin_password=values.admin_password,
        admin_display_name=values.admin_display_name.strip(),
    )


async def _bootstrap_in_session(
    session: AsyncSession,
    *,
    settings: Settings,
    values: BootstrapInput,
) -> BootstrapResult:
    values = _validate_input(values, settings)
    created: list[str] = []

    tenant = await session.scalar(select(Tenant).where(Tenant.slug == values.tenant_slug))
    if tenant is None:
        tenant = Tenant(name=values.tenant_name, slug=values.tenant_slug, status='ACTIVE')
        session.add(tenant)
        await session.flush()
        created.append('tenant')
    elif tenant.status != 'ACTIVE':
        raise RuntimeError('Existing bootstrap Tenant is not active')

    user = await session.scalar(select(User).where(User.email == values.admin_email))
    if user is None:
        user = User(
            email=values.admin_email,
            password_hash=hash_password(
                values.admin_password, minimum_length=settings.password_min_length
            ),
            display_name=values.admin_display_name,
            status='ACTIVE',
        )
        session.add(user)
        await session.flush()
        created.append('user')
    elif user.status != 'ACTIVE':
        raise RuntimeError('Existing bootstrap User is not active')

    membership = await session.scalar(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == user.id,
        )
    )
    if membership is None:
        membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, status='ACTIVE')
        session.add(membership)
        await session.flush()
        created.append('membership')
    elif membership.status != 'ACTIVE':
        raise RuntimeError('Existing bootstrap Membership is not active')

    role = await session.scalar(
        select(Role).where(Role.tenant_id == tenant.id, Role.name == ADMIN_ROLE_NAME)
    )
    if role is None:
        role = Role(
            tenant_id=tenant.id,
            name=ADMIN_ROLE_NAME,
            description='Tenant administrator for ECIP Core capabilities.',
            status='ACTIVE',
        )
        session.add(role)
        await session.flush()
        created.append('role')
    elif role.status != 'ACTIVE':
        raise RuntimeError('Existing bootstrap Role is not active')

    permission_ids: list[int] = []
    for code, description in CORE_PERMISSIONS.items():
        permission = await session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=description)
            session.add(permission)
            await session.flush()
            created.append(f'permission:{code}')
        permission_ids.append(permission.id)

    for permission_id in permission_ids:
        assignment = await session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission_id,
            )
        )
        if assignment is None:
            session.add(RolePermission(role_id=role.id, permission_id=permission_id))
            created.append('role_permission')

    membership_role = await session.scalar(
        select(MembershipRole).where(
            MembershipRole.membership_id == membership.id,
            MembershipRole.role_id == role.id,
        )
    )
    if membership_role is None:
        session.add(
            MembershipRole(
                tenant_id=tenant.id,
                membership_id=membership.id,
                role_id=role.id,
            )
        )
        created.append('membership_role')

    return BootstrapResult(
        tenant_id=tenant.id,
        user_id=user.id,
        membership_id=membership.id,
        role_id=role.id,
        created=tuple(created),
    )


async def bootstrap_admin(
    *,
    settings: Settings,
    values: BootstrapInput,
    database: DatabaseManager | None = None,
) -> BootstrapResult:
    manager = database or DatabaseManager(settings)
    owns_manager = database is None
    try:
        async with manager.session_factory() as session:
            async with session.begin():
                return await _bootstrap_in_session(session, settings=settings, values=values)
    finally:
        if owns_manager:
            await manager.dispose()


async def _main() -> None:
    result = await bootstrap_admin(
        settings=get_settings(),
        values=BootstrapInput.from_environment(),
    )
    print(
        json.dumps(
            {
                'status': 'created' if result.created else 'already_configured',
                'tenant_id': result.tenant_id,
                'user_id': result.user_id,
                'membership_id': result.membership_id,
                'role_id': result.role_id,
                'objects_created': len(result.created),
            }
        )
    )


if __name__ == '__main__':
    asyncio.run(_main())
