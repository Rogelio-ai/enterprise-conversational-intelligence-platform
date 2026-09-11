from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap_admin import BootstrapInput, bootstrap_admin
from app.core.config import get_settings
from app.core.security import hash_password, validate_password
from app.db.session import DatabaseManager
from app.models import (
    Location,
    LocationPaymentExecutorCapability,
    LocationPaymentExecutorConfiguration,
    LocationPreparationConfiguration,
    MembershipLocationGrant,
    MembershipRole,
    Menu,
    MenuItem,
    MenuLocation,
    MenuSection,
    Organization,
    Permission,
    PreparationArea,
    PreparationDeliveryConnector,
    PreparationDeliveryDestination,
    Product,
    ProductCategory,
    ProductPreparationRoute,
    ProductPrice,
    Resource,
    Role,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
)


TENANT_NAME = 'Carnitas Muñoz y Cortes'
TENANT_SLUG = 'carnitas-munoz-y-cortes'
ORGANIZATION_CODE = 'CMC'
LOCATION_CODE = 'SLP-CARNITAS-MUNOZ'
LOCATION_NAME = 'Carnitas Muñoz'
LOCATION_TIMEZONE = 'America/Mexico_City'
ADMIN_EMAIL = 'usopublico001@gmail.com'
ADMIN_DISPLAY_NAME = 'Rogelio'
LOCAL_TARGET_KEY = 'workstation_hp_p1005'
CONEKTA_CREDENTIAL_BINDING = 'pilot-location-conekta-test'


STAFF = (
    (
        'WAITER', 'waiter.prepilot@carnitas-munoz.invalid', 'Mesero Pre-Pilot',
        ('order_draft.read', 'order_draft.manage', 'restaurant_service.read',
         'restaurant_service.manage', 'restaurant_order.read', 'restaurant_check.read'),
    ),
    (
        'KITCHEN', 'kitchen.prepilot@carnitas-munoz.invalid', 'Cocina Pre-Pilot',
        ('preparation.read', 'preparation.execute', 'preparation.dispatch',
         'restaurant_order.read'),
    ),
    (
        'CASHIER', 'cashier.prepilot@carnitas-munoz.invalid', 'Caja Pre-Pilot',
        ('restaurant_check.read', 'restaurant_check.manage',
         'restaurant_payment.read', 'restaurant_payment.manage',
         'restaurant_payment.recover', 'cash_management.read',
         'cash_session.manage', 'cash_movement.manage'),
    ),
)


T = TypeVar('T')


@dataclass(frozen=True)
class PilotResult:
    tenant_id: int
    administrator_user_id: int
    administrator_membership_id: int
    organization_id: int
    location_id: int
    table_resource_id: int
    cash_register_resource_id: int
    preparation_configuration_id: int
    preparation_area_id: int
    category_id: int
    menu_id: int
    product_ids: dict[str, int]
    price_ids: dict[str, int]
    staff_membership_ids: dict[str, int]
    connector_id: int
    destination_id: int
    payment_executor_configuration_id: int
    payment_executor_capability_id: int
    objects_created: tuple[str, ...]


def _secret(path_variable: str) -> str:
    raw_path = os.environ.get(path_variable, '').strip()
    if not raw_path:
        raise ValueError(f'{path_variable} is required')
    path = Path(raw_path)
    if not path.is_file():
        raise ValueError(f'{path_variable} must reference a regular file')
    if not path.is_relative_to('/run/secrets') and path.stat().st_mode & 0o077:
        raise PermissionError(f'{path_variable} must reference an owner-only file')
    value = path.read_text(encoding='utf-8').strip()
    if not value:
        raise ValueError(f'{path_variable} references an empty file')
    return value


async def _one(session: AsyncSession, statement: Select[tuple[T]], label: str) -> T | None:
    values = tuple((await session.scalars(statement.limit(2))).all())
    if len(values) > 1:
        raise RuntimeError(f'duplicate authoritative {label} records exist')
    return values[0] if values else None


def _match(value: object, label: str, **expected: Any) -> None:
    mismatches = {
        key: {'actual': getattr(value, key), 'expected': item}
        for key, item in expected.items() if getattr(value, key) != item
    }
    if mismatches:
        raise RuntimeError(f'existing {label} conflicts with pilot contract: {mismatches}')


async def _grant(
    session: AsyncSession, tenant_id: int, membership_id: int, location_id: int,
    created: list[str], label: str,
) -> MembershipLocationGrant:
    value = await _one(session, select(MembershipLocationGrant).where(
        MembershipLocationGrant.tenant_id == tenant_id,
        MembershipLocationGrant.membership_id == membership_id,
        MembershipLocationGrant.location_id == location_id,
    ), f'{label} location grant')
    if value is None:
        value = MembershipLocationGrant(
            tenant_id=tenant_id, membership_id=membership_id, location_id=location_id,
        )
        session.add(value)
        await session.flush()
        created.append(f'{label}:location_grant')
    return value


async def _staff(
    session: AsyncSession, tenant_id: int, location_id: int, password: str,
    created: list[str], role_code: str, email: str, display_name: str,
    permission_codes: tuple[str, ...],
) -> TenantMembership:
    user = await _one(session, select(User).where(User.email == email), f'{role_code} user')
    if user is None:
        user = User(
            email=email, display_name=display_name, status='ACTIVE',
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
        created.append(f'{role_code}:user')
    else:
        _match(user, f'{role_code} user', display_name=display_name, status='ACTIVE')

    membership = await _one(session, select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == user.id,
    ), f'{role_code} membership')
    if membership is None:
        membership = TenantMembership(tenant_id=tenant_id, user_id=user.id, status='ACTIVE')
        session.add(membership)
        await session.flush()
        created.append(f'{role_code}:membership')
    else:
        _match(membership, f'{role_code} membership', status='ACTIVE')

    role_name = f'PREPILOT_{role_code}'
    role = await _one(session, select(Role).where(
        Role.tenant_id == tenant_id, Role.name == role_name,
    ), f'{role_code} role')
    if role is None:
        role = Role(
            tenant_id=tenant_id, name=role_name,
            description=f'Synthetic local pre-pilot {role_code.lower()} role.', status='ACTIVE',
        )
        session.add(role)
        await session.flush()
        created.append(f'{role_code}:role')
    else:
        _match(role, f'{role_code} role', status='ACTIVE')

    permissions = tuple((await session.scalars(select(Permission).where(
        Permission.code.in_(permission_codes)
    ))).all())
    found = {value.code for value in permissions}
    missing = set(permission_codes) - found
    if missing:
        raise RuntimeError(f'bootstrap_admin did not establish permissions: {sorted(missing)}')
    for permission in permissions:
        assignment = await _one(session, select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        ), f'{role_code} role permission')
        if assignment is None:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            created.append(f'{role_code}:role_permission')

    membership_role = await _one(session, select(MembershipRole).where(
        MembershipRole.tenant_id == tenant_id,
        MembershipRole.membership_id == membership.id,
        MembershipRole.role_id == role.id,
    ), f'{role_code} membership role')
    if membership_role is None:
        session.add(MembershipRole(
            tenant_id=tenant_id, membership_id=membership.id, role_id=role.id,
        ))
        created.append(f'{role_code}:membership_role')
    await _grant(session, tenant_id, membership.id, location_id, created, role_code)
    return membership


async def bootstrap_pilot_minimum() -> PilotResult:
    settings = get_settings()
    admin_password = _secret('PILOT_ADMIN_PASSWORD_FILE')
    staff_password = _secret('PILOT_STAFF_PASSWORD_FILE')
    validate_password(staff_password, minimum_length=settings.password_min_length)
    database = DatabaseManager(settings)
    try:
        core = await bootstrap_admin(
            settings=settings,
            values=BootstrapInput(
                tenant_name=TENANT_NAME, tenant_slug=TENANT_SLUG,
                admin_email=ADMIN_EMAIL, admin_password=admin_password,
                admin_display_name=ADMIN_DISPLAY_NAME,
            ),
            database=database,
        )
        created = list(core.created)
        async with database.session_factory() as session:
            async with session.begin():
                tenant = await _one(session, select(Tenant).where(
                    Tenant.id == core.tenant_id,
                ), 'Tenant')
                if tenant is None:
                    raise RuntimeError('bootstrap_admin did not return an existing Tenant')
                _match(
                    tenant, 'Tenant', name=TENANT_NAME, slug=TENANT_SLUG,
                    status='ACTIVE',
                )

                administrator = await _one(session, select(User).where(
                    User.id == core.user_id,
                ), 'Administrator')
                if administrator is None:
                    raise RuntimeError('bootstrap_admin did not return an existing Administrator')
                _match(
                    administrator, 'Administrator', email=ADMIN_EMAIL,
                    display_name=ADMIN_DISPLAY_NAME, status='ACTIVE',
                )

                organization = await _one(session, select(Organization).where(
                    Organization.tenant_id == core.tenant_id,
                    Organization.code == ORGANIZATION_CODE,
                ), 'Organization')
                if organization is None:
                    organization = Organization(
                        tenant_id=core.tenant_id, code=ORGANIZATION_CODE,
                        name=TENANT_NAME, status='ACTIVE',
                    )
                    session.add(organization)
                    await session.flush()
                    created.append('organization')
                else:
                    _match(organization, 'Organization', name=TENANT_NAME, status='ACTIVE')

                location = await _one(session, select(Location).where(
                    Location.tenant_id == core.tenant_id,
                    Location.organization_id == organization.id,
                    Location.code == LOCATION_CODE,
                ), 'Location')
                if location is None:
                    location = Location(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        code=LOCATION_CODE, name=LOCATION_NAME,
                        timezone=LOCATION_TIMEZONE, status='ACTIVE',
                    )
                    session.add(location)
                    await session.flush()
                    created.append('location')
                else:
                    _match(
                        location, 'Location', name=LOCATION_NAME,
                        timezone=LOCATION_TIMEZONE, status='ACTIVE',
                    )

                await _grant(
                    session, core.tenant_id, core.membership_id, location.id,
                    created, 'ADMIN',
                )
                staff_memberships: dict[str, int] = {}
                for role_code, email, name, permissions in STAFF:
                    membership = await _staff(
                        session, core.tenant_id, location.id, staff_password,
                        created, role_code, email, name, permissions,
                    )
                    staff_memberships[role_code] = membership.id

                resources: dict[str, Resource] = {}
                for code, name, kind in (
                    ('MESA-01', 'Mesa 01 Pre-Pilot', 'TABLE'),
                    ('CAJA-01', 'Caja 01 Pre-Pilot', 'CASH_REGISTER'),
                ):
                    resource = await _one(session, select(Resource).where(
                        Resource.tenant_id == core.tenant_id,
                        Resource.location_id == location.id,
                        Resource.code == code,
                    ), f'Resource {code}')
                    if resource is None:
                        resource = Resource(
                            tenant_id=core.tenant_id, location_id=location.id,
                            code=code, name=name, resource_type=kind, status='ACTIVE',
                        )
                        session.add(resource)
                        await session.flush()
                        created.append(f'resource:{code}')
                    else:
                        _match(
                            resource, f'Resource {code}', name=name,
                            resource_type=kind, status='ACTIVE',
                        )
                    resources[code] = resource
                if location.cash_management_activated_at is None:
                    location.cash_management_activated_at = datetime.now(UTC).replace(tzinfo=None)
                    created.append('cash_management_activation')

                prep_config = await _one(session, select(LocationPreparationConfiguration).where(
                    LocationPreparationConfiguration.tenant_id == core.tenant_id,
                    LocationPreparationConfiguration.location_id == location.id,
                ), 'Preparation configuration')
                if prep_config is None:
                    prep_config = LocationPreparationConfiguration(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        location_id=location.id, preparation_owner='PLATFORM',
                    )
                    session.add(prep_config)
                    await session.flush()
                    created.append('preparation_configuration')
                else:
                    _match(prep_config, 'Preparation configuration', preparation_owner='PLATFORM')

                area = await _one(session, select(PreparationArea).where(
                    PreparationArea.tenant_id == core.tenant_id,
                    PreparationArea.location_id == location.id,
                    PreparationArea.code == 'COCINA',
                ), 'Preparation Area')
                if area is None:
                    area = PreparationArea(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        location_id=location.id, resource_id=None, code='COCINA',
                        name='Cocina', status='ACTIVE',
                    )
                    session.add(area)
                    await session.flush()
                    created.append('preparation_area')
                else:
                    _match(area, 'Preparation Area', name='Cocina', status='ACTIVE')

                category = await _one(session, select(ProductCategory).where(
                    ProductCategory.tenant_id == core.tenant_id,
                    ProductCategory.organization_id == organization.id,
                    ProductCategory.name == 'Menú Pre-Pilot',
                ), 'Product Category')
                if category is None:
                    category = ProductCategory(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        parent_id=None, name='Menú Pre-Pilot', display_order=0,
                        status='ACTIVE',
                    )
                    session.add(category)
                    await session.flush()
                    created.append('product_category')
                else:
                    _match(category, 'Product Category', status='ACTIVE')

                products: dict[str, Product] = {}
                prices: dict[str, ProductPrice] = {}
                product_specs = (
                    ('TACO-CARNITAS', 'Taco de carnitas', Decimal('25.0000'), 'AREA'),
                    ('QUESADILLA', 'Quesadilla', Decimal('45.0000'), 'AREA'),
                    ('REFRESCO', 'Refresco', Decimal('30.0000'), 'NO_PREPARATION'),
                )
                for stable_key, name, amount, policy in product_specs:
                    product = await _one(session, select(Product).where(
                        Product.tenant_id == core.tenant_id,
                        Product.organization_id == organization.id,
                        Product.name == name,
                    ), f'Product {stable_key}')
                    if product is None:
                        product = Product(
                            tenant_id=core.tenant_id, organization_id=organization.id,
                            category_id=category.id, name=name,
                            description='Producto sintético para certificación local pre-pilot.',
                            status='ACTIVE', source='PLATFORM',
                        )
                        session.add(product)
                        await session.flush()
                        created.append(f'product:{stable_key}')
                    else:
                        _match(
                            product, f'Product {stable_key}', category_id=category.id,
                            status='ACTIVE', source='PLATFORM',
                        )
                    products[stable_key] = product

                    price = await _one(session, select(ProductPrice).where(
                        ProductPrice.tenant_id == core.tenant_id,
                        ProductPrice.product_id == product.id,
                        ProductPrice.location_id == location.id,
                    ), f'Price {stable_key}')
                    if price is None:
                        price = ProductPrice(
                            tenant_id=core.tenant_id, organization_id=organization.id,
                            product_id=product.id, location_id=location.id,
                            amount=amount, currency='MXN', status='ACTIVE', source='PLATFORM',
                        )
                        session.add(price)
                        await session.flush()
                        created.append(f'price:{stable_key}')
                    else:
                        _match(
                            price, f'Price {stable_key}', amount=amount,
                            currency='MXN', status='ACTIVE', source='PLATFORM',
                        )
                    prices[stable_key] = price

                    route = await _one(session, select(ProductPreparationRoute).where(
                        ProductPreparationRoute.tenant_id == core.tenant_id,
                        ProductPreparationRoute.location_id == location.id,
                        ProductPreparationRoute.product_id == product.id,
                        ProductPreparationRoute.status == 'ACTIVE',
                        ProductPreparationRoute.active_slot == 1,
                    ), f'Preparation Route {stable_key}')
                    expected_area = area.id if policy == 'AREA' else None
                    if route is None:
                        route = ProductPreparationRoute(
                            tenant_id=core.tenant_id, organization_id=organization.id,
                            location_id=location.id, product_id=product.id,
                            policy=policy, preparation_area_id=expected_area,
                            status='ACTIVE', active_slot=1,
                        )
                        session.add(route)
                        await session.flush()
                        created.append(f'preparation_route:{stable_key}')
                    else:
                        _match(
                            route, f'Preparation Route {stable_key}', policy=policy,
                            preparation_area_id=expected_area,
                        )

                menu = await _one(session, select(Menu).where(
                    Menu.tenant_id == core.tenant_id,
                    Menu.organization_id == organization.id,
                    Menu.name == 'Menú Local Pre-Pilot',
                ), 'Menu')
                if menu is None:
                    menu = Menu(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        name='Menú Local Pre-Pilot', status='ACTIVE',
                    )
                    session.add(menu)
                    await session.flush()
                    created.append('menu')
                else:
                    _match(menu, 'Menu', status='ACTIVE')

                menu_location = await _one(session, select(MenuLocation).where(
                    MenuLocation.tenant_id == core.tenant_id,
                    MenuLocation.menu_id == menu.id,
                    MenuLocation.location_id == location.id,
                ), 'Menu Location')
                if menu_location is None:
                    session.add(MenuLocation(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        menu_id=menu.id, location_id=location.id, status='ACTIVE',
                    ))
                    created.append('menu_location')
                else:
                    _match(menu_location, 'Menu Location', status='ACTIVE')

                section = await _one(session, select(MenuSection).where(
                    MenuSection.tenant_id == core.tenant_id,
                    MenuSection.menu_id == menu.id,
                    MenuSection.name == 'Platillos Pre-Pilot',
                ), 'Menu Section')
                if section is None:
                    section = MenuSection(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        menu_id=menu.id, name='Platillos Pre-Pilot',
                        display_order=0, status='ACTIVE',
                    )
                    session.add(section)
                    await session.flush()
                    created.append('menu_section')
                else:
                    _match(section, 'Menu Section', status='ACTIVE')

                for order, (stable_key, product) in enumerate(products.items()):
                    item = await _one(session, select(MenuItem).where(
                        MenuItem.tenant_id == core.tenant_id,
                        MenuItem.menu_id == menu.id,
                        MenuItem.product_id == product.id,
                    ), f'Menu Item {stable_key}')
                    if item is None:
                        session.add(MenuItem(
                            tenant_id=core.tenant_id, organization_id=organization.id,
                            menu_id=menu.id, section_id=section.id,
                            product_id=product.id, display_order=order, status='ACTIVE',
                        ))
                        created.append(f'menu_item:{stable_key}')
                    else:
                        _match(
                            item, f'Menu Item {stable_key}', section_id=section.id,
                            status='ACTIVE',
                        )

                connector = await _one(session, select(PreparationDeliveryConnector).where(
                    PreparationDeliveryConnector.tenant_id == core.tenant_id,
                    PreparationDeliveryConnector.location_id == location.id,
                    PreparationDeliveryConnector.code == 'WS-HP-P1005',
                ), 'Connector')
                if connector is None:
                    connector = PreparationDeliveryConnector(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        location_id=location.id, code='WS-HP-P1005',
                        name='HP P1005 Local Pre-Pilot',
                        auth_subject='preparation-connector:prepilot-workstation-hp-p1005',
                        status='ACTIVE',
                    )
                    session.add(connector)
                    await session.flush()
                    created.append('connector')
                else:
                    _match(connector, 'Connector', status='ACTIVE')

                destination = await _one(session, select(PreparationDeliveryDestination).where(
                    PreparationDeliveryDestination.tenant_id == core.tenant_id,
                    PreparationDeliveryDestination.connector_id == connector.id,
                    PreparationDeliveryDestination.local_target_key == LOCAL_TARGET_KEY,
                    PreparationDeliveryDestination.status == 'ACTIVE',
                ), 'Preparation Destination')
                if destination is None:
                    destination = PreparationDeliveryDestination(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        location_id=location.id, preparation_area_id=area.id,
                        connector_id=connector.id, code='COCINA-HP-P1005',
                        name='Cocina HP P1005 Local Pre-Pilot', channel='PRINTER',
                        local_target_key=LOCAL_TARGET_KEY, status='ACTIVE', active_slot=1,
                    )
                    session.add(destination)
                    await session.flush()
                    created.append('preparation_destination')
                else:
                    _match(
                        destination, 'Preparation Destination',
                        preparation_area_id=area.id, channel='PRINTER', active_slot=1,
                    )

                executor = await _one(session, select(LocationPaymentExecutorConfiguration).where(
                    LocationPaymentExecutorConfiguration.tenant_id == core.tenant_id,
                    LocationPaymentExecutorConfiguration.location_id == location.id,
                    LocationPaymentExecutorConfiguration.executor_key == 'conekta-test-card',
                ), 'Conekta TEST executor')
                if executor is None:
                    executor = LocationPaymentExecutorConfiguration(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        location_id=location.id, executor_key='conekta-test-card',
                        display_name='Conekta TEST card', adapter_kind='CONEKTA',
                        topology='EXTERNAL', status='INACTIVE',
                        credential_binding=CONEKTA_CREDENTIAL_BINDING,
                        client_public_key=None, selection_priority=10,
                    )
                    session.add(executor)
                    await session.flush()
                    created.append('conekta_test_executor_inactive')
                else:
                    _match(
                        executor, 'Conekta TEST executor', adapter_kind='CONEKTA',
                        topology='EXTERNAL', status='INACTIVE',
                        credential_binding=CONEKTA_CREDENTIAL_BINDING,
                    )

                capability = await _one(session, select(LocationPaymentExecutorCapability).where(
                    LocationPaymentExecutorCapability.executor_configuration_id == executor.id,
                    LocationPaymentExecutorCapability.method_category == 'CARD',
                    LocationPaymentExecutorCapability.currency == 'MXN',
                ), 'Conekta TEST capability')
                if capability is None:
                    capability = LocationPaymentExecutorCapability(
                        executor_configuration_id=executor.id, tenant_id=core.tenant_id,
                        organization_id=organization.id, location_id=location.id,
                        method_category='CARD', currency='MXN',
                    )
                    session.add(capability)
                    await session.flush()
                    created.append('conekta_test_capability')

                result = PilotResult(
                    tenant_id=core.tenant_id,
                    administrator_user_id=core.user_id,
                    administrator_membership_id=core.membership_id,
                    organization_id=organization.id,
                    location_id=location.id,
                    table_resource_id=resources['MESA-01'].id,
                    cash_register_resource_id=resources['CAJA-01'].id,
                    preparation_configuration_id=prep_config.id,
                    preparation_area_id=area.id,
                    category_id=category.id,
                    menu_id=menu.id,
                    product_ids={key: value.id for key, value in products.items()},
                    price_ids={key: value.id for key, value in prices.items()},
                    staff_membership_ids=staff_memberships,
                    connector_id=connector.id,
                    destination_id=destination.id,
                    payment_executor_configuration_id=executor.id,
                    payment_executor_capability_id=capability.id,
                    objects_created=tuple(created),
                )
            return result
    finally:
        await database.dispose()


async def _main() -> None:
    result = await bootstrap_pilot_minimum()
    output = asdict(result)
    output['status'] = 'created' if result.objects_created else 'already_configured'
    output['objects_created_count'] = len(result.objects_created)
    output.pop('objects_created')
    output['connector_credential_created'] = False
    output['conekta_executor_status'] = 'INACTIVE'
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    asyncio.run(_main())
