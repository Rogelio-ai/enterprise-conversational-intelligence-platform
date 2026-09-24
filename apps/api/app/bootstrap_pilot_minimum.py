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
    MembershipLocationRole,
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
    ProductFiscalClassification,
    Product,
    ProductCategory,
    ProductPreparationRoute,
    ProductPrice,
    RestaurantTaxRule,
    Resource,
    Role,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
)


DEMO_MODE = os.environ.get('DEMO_ENV') == 'demo'
TENANT_NAME = 'Restaurant Intelligence Demo' if DEMO_MODE else 'Carnitas Muñoz y Cortes'
TENANT_SLUG = 'restaurant-intelligence-demo' if DEMO_MODE else 'carnitas-munoz-y-cortes'
ORGANIZATION_CODE = 'DEMO-GROUP' if DEMO_MODE else 'CMC'
LOCATION_CODE = 'CENTRO-DEMO' if DEMO_MODE else 'SLP-CARNITAS-MUNOZ'
LOCATION_NAME = 'Centro Demo' if DEMO_MODE else 'Carnitas Muñoz'
LOCATION_TIMEZONE = 'America/Mexico_City'
ADMIN_EMAIL = 'manager@restaurant.demo' if DEMO_MODE else 'usopublico001@gmail.com'
ADMIN_DISPLAY_NAME = 'Gerente Demo' if DEMO_MODE else 'Rogelio'
LOCAL_TARGET_KEY = 'demo-disabled-printer' if DEMO_MODE else 'workstation_hp_p1005'
CONEKTA_CREDENTIAL_BINDING = 'demo-disabled-conekta' if DEMO_MODE else 'pilot-location-conekta-test'
FISCAL_JURISDICTION_CODE = 'MX'
TAX_CLASSIFICATION_CODE = 'DEMO-IVA-16' if DEMO_MODE else 'PREPILOT-IVA-16'

MENU_LABEL = 'Menú Demo' if DEMO_MODE else 'Menú Pre-Pilot'
MENU_NAME = 'Menú Restaurant Intelligence Demo' if DEMO_MODE else 'Menú Local Pre-Pilot'
MENU_SECTION = 'Especialidades Demo' if DEMO_MODE else 'Platillos Pre-Pilot'
DATA_DESCRIPTION = ('Producto ficticio para recorrido local DEMO.' if DEMO_MODE
                    else 'Producto sintético para certificación local pre-pilot.')
FISCAL_PREFIX = 'DEMO' if DEMO_MODE else 'PREPILOT'


OPERATIONAL_PROFILE_PERMISSIONS = {
    'HOST': ('location.read', 'resource.read', 'restaurant_service.read'),
    'WAITER': (
        'location.read', 'order_draft.read', 'order_draft.manage',
        'restaurant_service.read', 'restaurant_service.manage',
        'restaurant_order.read', 'restaurant_check.read',
        'operational_request.read',
    ),
    'KITCHEN': (
        'location.read', 'preparation.read', 'preparation.execute',
        'preparation.dispatch', 'restaurant_order.read',
    ),
    'CASHIER': (
        'location.read', 'resource.read', 'restaurant_check.read',
        'restaurant_check.manage', 'restaurant_payment.read',
        'restaurant_payment.manage', 'restaurant_payment.recover',
        'cash_management.read', 'cash_session.manage', 'cash_movement.manage',
    ),
    'INVENTORY_MANAGER': (
        'location.read', 'inventory.read', 'inventory.count.read',
        'inventory.count.approve', 'inventory.count.post',
    ),
}

OPERATIONAL_ROLE_PREFIX = 'DEMO' if DEMO_MODE else 'PREPILOT'


def operational_role_name(profile: str) -> str:
    if profile not in OPERATIONAL_PROFILE_PERMISSIONS:
        raise ValueError(f'unsupported operational profile: {profile}')
    return f'{OPERATIONAL_ROLE_PREFIX}_{profile}'


def operational_role_description(profile: str) -> str:
    if profile not in OPERATIONAL_PROFILE_PERMISSIONS:
        raise ValueError(f'unsupported operational profile: {profile}')
    return f'Synthetic local pre-pilot {profile.lower()} role.'


STAFF = (
    (
        'HOST', ('host@restaurant.demo' if DEMO_MODE else 'host.prepilot@carnitas-munoz.invalid'), ('Host Demo' if DEMO_MODE else 'Host Pre-Pilot'),
        OPERATIONAL_PROFILE_PERMISSIONS['HOST'],
    ),
    (
        'WAITER', ('waiter@restaurant.demo' if DEMO_MODE else 'waiter.prepilot@carnitas-munoz.invalid'), ('Mesero Demo' if DEMO_MODE else 'Mesero Pre-Pilot'),
        OPERATIONAL_PROFILE_PERMISSIONS['WAITER'],
    ),
    (
        'KITCHEN', ('kitchen@restaurant.demo' if DEMO_MODE else 'kitchen.prepilot@carnitas-munoz.invalid'), ('Cocina Demo' if DEMO_MODE else 'Cocina Pre-Pilot'),
        OPERATIONAL_PROFILE_PERMISSIONS['KITCHEN'],
    ),
    (
        'CASHIER', ('cashier@restaurant.demo' if DEMO_MODE else 'cashier.prepilot@carnitas-munoz.invalid'), ('Caja Demo' if DEMO_MODE else 'Caja Pre-Pilot'),
        OPERATIONAL_PROFILE_PERMISSIONS['CASHIER'],
    ),
)
if DEMO_MODE:
    STAFF += (
        (
            'INVENTORY_MANAGER', 'inventory@restaurant.demo',
            'Responsable de Inventario Demo',
            OPERATIONAL_PROFILE_PERMISSIONS['INVENTORY_MANAGER'],
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
    if DEMO_MODE:
        variable = (
            'DEMO_ADMIN_PASSWORD'
            if path_variable == 'PILOT_ADMIN_PASSWORD_FILE'
            else 'DEMO_STAFF_PASSWORD'
        )
        value = os.environ.get(variable, '').strip()
        if not value:
            raise ValueError(f'{variable} is required in DEMO mode')
        return value
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
    role_id: int, created: list[str], label: str,
) -> MembershipLocationRole:
    value = await _one(session, select(MembershipLocationGrant).where(
        MembershipLocationGrant.tenant_id == tenant_id,
        MembershipLocationGrant.membership_id == membership_id,
        MembershipLocationGrant.location_id == location_id,
    ), f'{label} location grant')
    if value is None:
        value = MembershipLocationGrant(
            tenant_id=tenant_id, membership_id=membership_id,
            location_id=location_id,
        )
        session.add(value)
        await session.flush()
        created.append(f'{label}:location_grant')
    assignment = await _one(session, select(MembershipLocationRole).where(
        MembershipLocationRole.tenant_id == tenant_id,
        MembershipLocationRole.membership_id == membership_id,
        MembershipLocationRole.location_id == location_id,
        MembershipLocationRole.role_id == role_id,
    ), f'{label} location role')
    if assignment is None:
        assignment = MembershipLocationRole(
            tenant_id=tenant_id, membership_id=membership_id,
            location_id=location_id, role_id=role_id,
        )
        session.add(assignment)
        await session.flush()
        created.append(f'{label}:location_role')
    return assignment


async def _staff(
    session: AsyncSession, tenant_id: int, location_id: int, password: str,
    created: list[str], role_code: str, email: str, display_name: str,
    permission_codes: tuple[str, ...],
) -> TenantMembership:
    username = role_code.casefold()
    user = await _one(session, select(User).where(User.email == email), f'{role_code} user')
    if user is None:
        user = User(
            username=username, email=email, display_name=display_name, status='ACTIVE',
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
        created.append(f'{role_code}:user')
    else:
        _match(user, f'{role_code} user', display_name=display_name, status='ACTIVE')
        if user.username != username:
            conflict = await session.scalar(select(User.id).where(
                User.username == username, User.id != user.id,
            ))
            if conflict is not None:
                raise RuntimeError(f'{role_code} username conflicts with an existing User')
            user.username = username
            created.append(f'{role_code}:username')

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

    role_name = operational_role_name(role_code)
    role = await _one(session, select(Role).where(
        Role.tenant_id == tenant_id, Role.name == role_name,
    ), f'{role_code} role')
    if role is None:
        role = Role(
            tenant_id=tenant_id, name=role_name,
            description=operational_role_description(role_code), status='ACTIVE',
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
    await _grant(
        session, tenant_id, membership.id, location_id, role.id, created, role_code,
    )
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
                        timezone=LOCATION_TIMEZONE,
                        country_code=FISCAL_JURISDICTION_CODE, status='ACTIVE',
                    )
                    session.add(location)
                    await session.flush()
                    created.append('location')
                else:
                    _match(
                        location, 'Location', name=LOCATION_NAME,
                        timezone=LOCATION_TIMEZONE, status='ACTIVE',
                    )
                    if location.country_code is None:
                        location.country_code = FISCAL_JURISDICTION_CODE
                        created.append('location_country_code')
                    elif location.country_code != FISCAL_JURISDICTION_CODE:
                        raise RuntimeError(
                            'existing Location conflicts with pilot fiscal jurisdiction'
                        )

                await _grant(
                    session, core.tenant_id, core.membership_id, location.id,
                    core.role_id, created, 'ADMIN',
                )
                staff_memberships: dict[str, int] = {}
                for role_code, email, name, permissions in STAFF:
                    membership = await _staff(
                        session, core.tenant_id, location.id, staff_password,
                        created, role_code, email, name, permissions,
                    )
                    staff_memberships[role_code] = membership.id

                resources: dict[str, Resource] = {}
                resource_specs = (
                    ('MESA-01', 'Mesa 01 Demo' if DEMO_MODE else 'Mesa 01 Pre-Pilot', 'TABLE'),
                    ('CAJA-01', 'Caja 01 Demo' if DEMO_MODE else 'Caja 01 Pre-Pilot', 'CASH_REGISTER'),
                )
                if DEMO_MODE:
                    resource_specs += tuple(
                        (f'MESA-{number:02d}', f'Mesa {number:02d} Demo', 'TABLE')
                        for number in range(2, 9)
                    )
                for code, name, kind in resource_specs:
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
                    ProductCategory.name == MENU_LABEL,
                ), 'Product Category')
                if category is None:
                    category = ProductCategory(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        parent_id=None, name=MENU_LABEL, display_order=0,
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
                if DEMO_MODE:
                    product_specs = (
                        ('TACO-DEMO', 'Taco de la casa', Decimal('32.0000'), 'AREA'),
                        ('QUESADILLA-DEMO', 'Quesadilla de temporada', Decimal('58.0000'), 'AREA'),
                        ('TORTA-DEMO', 'Torta Centro', Decimal('92.0000'), 'AREA'),
                        ('ORDEN-DEMO', 'Orden familiar', Decimal('185.0000'), 'AREA'),
                        ('SALSA-DEMO', 'Salsa preparada', Decimal('18.0000'), 'NO_PREPARATION'),
                        ('AGUA-DEMO', 'Agua mineral', Decimal('28.0000'), 'NO_PREPARATION'),
                        ('REFRESCO-DEMO', 'Refresco artesanal', Decimal('42.0000'), 'NO_PREPARATION'),
                        ('POSTRE-DEMO', 'Flan de vainilla', Decimal('55.0000'), 'NO_PREPARATION'),
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
                            description=DATA_DESCRIPTION,
                            tax_classification_code=TAX_CLASSIFICATION_CODE,
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
                        if product.tax_classification_code is None:
                            product.tax_classification_code = TAX_CLASSIFICATION_CODE
                            created.append(f'product_tax_classification:{stable_key}')
                        elif product.tax_classification_code != TAX_CLASSIFICATION_CODE:
                            raise RuntimeError(
                                f'existing Product {stable_key} conflicts with pilot tax classification'
                            )
                    products[stable_key] = product

                    fiscal_classification = await _one(
                        session,
                        select(ProductFiscalClassification).where(
                            ProductFiscalClassification.tenant_id == core.tenant_id,
                            ProductFiscalClassification.organization_id == organization.id,
                            ProductFiscalClassification.product_id == product.id,
                            ProductFiscalClassification.fiscal_jurisdiction_code
                            == FISCAL_JURISDICTION_CODE,
                            ProductFiscalClassification.status == 'ACTIVE',
                            ProductFiscalClassification.effective_to.is_(None),
                        ),
                        f'Fiscal Product Classification {stable_key}',
                    )
                    fiscal_values = {
                        'product_classification_scheme': f'{FISCAL_PREFIX}-PRODUCT-SCHEME',
                        'product_classification_code': f'{FISCAL_PREFIX}-{stable_key}',
                        'unit_classification_scheme': f'{FISCAL_PREFIX}-UNIT-SCHEME',
                        'unit_classification_code': 'EACH',
                    }
                    if fiscal_classification is None:
                        fiscal_classification = ProductFiscalClassification(
                            tenant_id=core.tenant_id,
                            organization_id=organization.id,
                            product_id=product.id,
                            fiscal_jurisdiction_code=FISCAL_JURISDICTION_CODE,
                            effective_from=datetime(2026, 1, 1),
                            effective_to=None,
                            status='ACTIVE',
                            **fiscal_values,
                        )
                        session.add(fiscal_classification)
                        created.append(f'product_fiscal_classification:{stable_key}')
                    else:
                        _match(
                            fiscal_classification,
                            f'Fiscal Product Classification {stable_key}',
                            **fiscal_values,
                        )

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

                tax_rule = await _one(session, select(RestaurantTaxRule).where(
                    RestaurantTaxRule.tenant_id == core.tenant_id,
                    RestaurantTaxRule.organization_id == organization.id,
                    RestaurantTaxRule.location_id.is_(None),
                    RestaurantTaxRule.tax_classification_code == TAX_CLASSIFICATION_CODE,
                    RestaurantTaxRule.status == 'ACTIVE',
                    RestaurantTaxRule.effective_to.is_(None),
                ), 'Restaurant Tax Rule')
                tax_values = {
                    'jurisdiction_code': f'MX-{FISCAL_PREFIX}',
                    'tax_category': 'IVA',
                    'tax_treatment': 'TAXABLE',
                    'tax_effect': 'TRANSFERRED',
                    'tax_rate': Decimal('0.160000'),
                    'calculation_policy': 'INCLUDED_PRICE_SINGLE_TAX',
                    'rounding_policy': 'DECIMAL_4_HALF_UP',
                }
                if tax_rule is None:
                    tax_rule = RestaurantTaxRule(
                        tenant_id=core.tenant_id,
                        organization_id=organization.id,
                        location_id=None,
                        tax_classification_code=TAX_CLASSIFICATION_CODE,
                        effective_from=datetime(2026, 1, 1),
                        effective_to=None,
                        status='ACTIVE',
                        **tax_values,
                    )
                    session.add(tax_rule)
                    created.append('restaurant_tax_rule')
                else:
                    _match(tax_rule, 'Restaurant Tax Rule', **tax_values)

                menu = await _one(session, select(Menu).where(
                    Menu.tenant_id == core.tenant_id,
                    Menu.organization_id == organization.id,
                    Menu.name == MENU_NAME,
                ), 'Menu')
                if menu is None:
                    menu = Menu(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        name=MENU_NAME, status='ACTIVE',
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
                    MenuSection.name == MENU_SECTION,
                ), 'Menu Section')
                if section is None:
                    section = MenuSection(
                        tenant_id=core.tenant_id, organization_id=organization.id,
                        menu_id=menu.id, name=MENU_SECTION,
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
                        name='Impresora no conectada DEMO' if DEMO_MODE else 'HP P1005 Local Pre-Pilot',
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
                        name=('Destino no conectado DEMO' if DEMO_MODE else 'Cocina HP P1005 Local Pre-Pilot'), channel='PRINTER',
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
