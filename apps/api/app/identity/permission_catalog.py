"""Canonical permission definitions and permission-only initialization."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Final, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import DatabaseManager
from app.models import Permission


CANONICAL_PERMISSIONS: Final[Mapping[str, str]] = MappingProxyType({
    'cash_management.read': 'Read cash-management sessions.',
    'cash_movement.manage': 'Record authorized manual cash movements.',
    'cash_session.manage': 'Open and manage cash sessions.',
    'conversation.manage': 'Manage Tenant conversations, participants, and messages.',
    'conversation.read': 'Read Tenant conversations, participants, and messages.',
    'customer.manage': 'Manage Tenant customers.',
    'customer.read': 'Read Tenant customers.',
    'internal_message.read': 'Read participant-scoped internal operational messages.',
    'internal_message.respond': (
        'Acknowledge, respond to, and complete addressed internal messages.'
    ),
    'internal_message.send': 'Send internal operational messages in authorized locations.',
    'inventory.cost.read': 'Read inventory standard and receipt cost evidence.',
    'inventory.count.approve': 'Approve submitted physical counts.',
    'inventory.count.manage': 'Open, count, submit and cancel physical counts.',
    'inventory.count.post': 'Post approved physical count adjustments.',
    'inventory.count.read': 'Read physical count evidence.',
    'inventory.fifo.read': 'Read FIFO layers and valuation evidence.',
    'inventory.loss.approve': 'Configure policy, approve and reverse inventory losses.',
    'inventory.loss.manage': 'Create, update, submit and cancel inventory losses.',
    'inventory.loss.read': 'Read typed inventory loss evidence.',
    'inventory.lot.read': 'Read inventory lot traceability.',
    'inventory.manage': 'Manage location inventory, recipes, and stock movements.',
    'inventory.preparation.complete': 'Complete preparation batches.',
    'inventory.preparation.manage': 'Manage preparation recipes and batches.',
    'inventory.preparation.read': 'Read preparation recipes and batches.',
    'inventory.purchase_order.approve': 'Approve purchase orders.',
    'inventory.purchase_order.manage': 'Manage purchase orders.',
    'inventory.purchase_order.read': 'Read purchase orders.',
    'inventory.read': 'Read location inventory, stock, recipes, and current costs.',
    'inventory.receipt.accept': 'Accept direct goods receipts into stock.',
    'inventory.receipt.manage': 'Create and cancel direct goods receipts.',
    'inventory.reconciliation.manage': 'Create and close inventory reconciliations.',
    'inventory.reconciliation.read': 'Read inventory reconciliation evidence.',
    'inventory.replenishment.manage': 'Manage replenishment policy.',
    'inventory.replenishment.read': 'Read replenishment policy and suggestions.',
    'inventory.supplier.manage': 'Manage inventory suppliers and offerings.',
    'inventory.transfer.manage': 'Create and execute inventory transfers.',
    'inventory.transfer.read': 'Read inventory transfers.',
    'inventory.valuation.create': 'Create immutable inventory valuation snapshots.',
    'inventory.valuation.read': 'Read inventory valuation snapshots.',
    'location.manage': 'Manage Tenant locations.',
    'location.read': 'Read Tenant locations.',
    'menu.manage': 'Manage Organization menus.',
    'menu.read': 'Read Organization menus.',
    'operational_request.manage': 'Acknowledge and complete diner operational requests.',
    'operational_request.read': 'Read diner operational requests for authorized locations.',
    'order_draft.manage': 'Manage canonical Restaurant Order Drafts.',
    'order_draft.read': 'Read canonical Restaurant Order Drafts.',
    'organization.manage': 'Manage Tenant organizations.',
    'organization.read': 'Read Tenant organizations.',
    'pos_submission.read': 'Read POS order submission state and history.',
    'pos_submission.recover': 'Recover uncertain POS order submissions.',
    'pos_submission.retry': 'Retry safely retryable POS order submissions.',
    'pos_submission.submit': 'Submit accepted Restaurant Orders to a POS.',
    'preparation.configure': 'Configure preparation ownership, areas, and product routes.',
    'preparation.connector.manage': (
        'Manage Restaurant Local Connector machine credentials.'
    ),
    'preparation.dispatch': 'Perform human preparation dispatch interventions.',
    'preparation.execute': 'Execute native Preparation Work Items.',
    'preparation.read': 'Read preparation configuration, routing, and work.',
    'preparation.route': 'Route accepted Restaurant Orders to preparation.',
    'pricing.manage': 'Manage Organization product prices.',
    'pricing.read': 'Read Organization product prices.',
    'product.manage': 'Manage Organization products and categories.',
    'product.read': 'Read Organization products and categories.',
    'promotion.manage': 'Manage Organization promotions.',
    'promotion.read': 'Read Organization promotions.',
    'resource.manage': 'Manage Tenant resources.',
    'resource.read': 'Read Tenant resources.',
    'restaurant_check.manage': 'Manage canonical Restaurant Checks.',
    'restaurant_check.read': 'Read canonical Restaurant Checks and table balances.',
    'restaurant_order.read': 'Read immutable accepted Restaurant Orders.',
    'restaurant_payment.manage': 'Initiate and confirm canonical Restaurant Payments.',
    'restaurant_payment.read': 'Read canonical Restaurant Payments and settlements.',
    'restaurant_payment.recover': 'Recover uncertain Restaurant Payment execution.',
    'restaurant_service.manage': 'Manage Restaurant service sessions.',
    'restaurant_service.read': 'Read Restaurant service sessions.',
    'role.manage': 'Manage Tenant roles and permission assignments.',
    'role.read': 'Read Tenant roles and permissions.',
    'staff_credentials.manage': (
        'Administratively change existing Staff credentials and revoke their sessions.'
    ),
    'table_management.manage': (
        'Manage dining sections, table lifecycle, movement, and groups.'
    ),
    'tenant.manage': 'Manage Tenant core settings.',
    'tenant.read': 'Read the current Tenant context.',
    'user.manage': 'Manage Tenant users.',
    'user.read': 'Read Tenant user information.',
})

ADMIN_BOOTSTRAP_PERMISSION_CODES: Final[tuple[str, ...]] = (
    'tenant.read',
    'tenant.manage',
    'user.read',
    'user.manage',
    'staff_credentials.manage',
    'role.read',
    'role.manage',
    'organization.read',
    'organization.manage',
    'location.read',
    'location.manage',
    'operational_request.read',
    'operational_request.manage',
    'resource.read',
    'resource.manage',
    'table_management.manage',
    'internal_message.read',
    'internal_message.send',
    'internal_message.respond',
    'customer.read',
    'customer.manage',
    'product.read',
    'product.manage',
    'menu.read',
    'menu.manage',
    'pricing.read',
    'pricing.manage',
    'promotion.read',
    'promotion.manage',
    'conversation.read',
    'conversation.manage',
    'order_draft.read',
    'order_draft.manage',
    'restaurant_service.read',
    'restaurant_service.manage',
    'restaurant_order.read',
    'restaurant_check.read',
    'restaurant_check.manage',
    'restaurant_payment.read',
    'restaurant_payment.manage',
    'restaurant_payment.recover',
    'cash_management.read',
    'cash_session.manage',
    'cash_movement.manage',
    'inventory.read',
    'inventory.manage',
    'inventory.count.read',
    'inventory.count.approve',
    'inventory.count.post',
    'pos_submission.read',
    'pos_submission.submit',
    'pos_submission.retry',
    'pos_submission.recover',
    'preparation.read',
    'preparation.route',
    'preparation.configure',
    'preparation.execute',
    'preparation.dispatch',
    'preparation.connector.manage',
)


class PermissionCatalogConflictError(RuntimeError):
    """The stored permission catalog conflicts with its canonical definition."""


@dataclass(frozen=True, slots=True)
class PermissionInitializationResult:
    created_codes: tuple[str, ...]
    total_permissions: int


def _validate_catalog() -> None:
    if len(CANONICAL_PERMISSIONS) != 83:
        raise PermissionCatalogConflictError(
            'Canonical permission catalog must contain exactly 83 unique codes'
        )
    invalid_codes = tuple(
        code for code, description in CANONICAL_PERMISSIONS.items()
        if not code or not description or len(code) > 100 or len(description) > 255
    )
    if invalid_codes:
        raise PermissionCatalogConflictError(
            f'Canonical permission definitions are invalid: {invalid_codes!r}'
        )
    unknown_admin_codes = tuple(
        code for code in ADMIN_BOOTSTRAP_PERMISSION_CODES
        if code not in CANONICAL_PERMISSIONS
    )
    if len(ADMIN_BOOTSTRAP_PERMISSION_CODES) != 59 or unknown_admin_codes:
        raise PermissionCatalogConflictError(
            'Administrative bootstrap permission selection is invalid'
        )


async def initialize_canonical_permissions(
    session: AsyncSession,
) -> PermissionInitializationResult:
    """Insert only missing canonical permissions in the caller-owned transaction."""
    _validate_catalog()
    codes = tuple(sorted(CANONICAL_PERMISSIONS))
    existing = tuple((await session.scalars(
        select(Permission).where(Permission.code.in_(codes)).order_by(Permission.code)
    )).all())
    existing_by_code = {permission.code: permission for permission in existing}
    conflicts = tuple(
        code for code, permission in existing_by_code.items()
        if permission.description != CANONICAL_PERMISSIONS[code]
    )
    if conflicts:
        raise PermissionCatalogConflictError(
            f'Canonical permission descriptions conflict: {conflicts!r}'
        )

    created_codes = tuple(code for code in codes if code not in existing_by_code)
    session.add_all(
        Permission(code=code, description=CANONICAL_PERMISSIONS[code])
        for code in created_codes
    )
    if created_codes:
        await session.flush()

    stored = tuple((await session.scalars(
        select(Permission).where(Permission.code.in_(codes)).order_by(Permission.code)
    )).all())
    if len(stored) != len(codes) or any(
        permission.description != CANONICAL_PERMISSIONS[permission.code]
        for permission in stored
    ):
        raise PermissionCatalogConflictError(
            'Canonical permission catalog did not converge'
        )
    return PermissionInitializationResult(
        created_codes=created_codes,
        total_permissions=len(stored),
    )


async def initialize_permission_catalog(
    *,
    settings: Settings,
    database: DatabaseManager | None = None,
) -> PermissionInitializationResult:
    """Run canonical initialization as one controlled transaction."""
    manager = database or DatabaseManager(settings)
    owns_manager = database is None
    try:
        async with manager.session_factory() as session:
            async with session.begin():
                return await initialize_canonical_permissions(session)
    finally:
        if owns_manager:
            await manager.dispose()


async def _main() -> None:
    result = await initialize_permission_catalog(settings=get_settings())
    print(json.dumps({
        'status': 'created' if result.created_codes else 'already_configured',
        'permissions_created': len(result.created_codes),
        'permissions_total': result.total_permissions,
    }))


if __name__ == '__main__':
    asyncio.run(_main())
