"""Confirmed Stage 0 import orchestration over existing write authorities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InventoryItem,
    ItemUomConversion,
    Location,
    OnboardingImport,
    Organization,
    Supplier,
    SupplierLocation,
    SupplierOffering,
    Tenant,
)
from app.onboarding.analyzer import AnalysisResult, AnalyzedRow
from app.onboarding.contract import CONTRACT_VERSION, ONBOARDING_CONTRACT
from app.restaurant.catalog import category_provisioning
from app.restaurant.catalog import provisioning as product_provisioning
from app.restaurant import resource_provisioning
from app.restaurant.inventory import receiving
from app.restaurant.inventory import service as inventory_service
from app.restaurant.preparation import (
    area_provisioning,
    configuration_provisioning,
    route_provisioning,
)


IMPORTABLE_NOW = frozenset({
    'restaurant_profile', 'inventory_items', 'uom_conversions', 'suppliers',
    'supplier_offerings', 'resources', 'preparation_configuration',
    'preparation_areas', 'categories', 'products', 'preparation_routes',
})
OPERATIONAL_NOT_CATALOG_IMPORT = frozenset({'payment_methods'})
DEFERRED_PROVISIONING = frozenset(
    group.key for group in ONBOARDING_CONTRACT
    if group.key not in IMPORTABLE_NOW | OPERATIONAL_NOT_CATALOG_IMPORT
)
REQUIRED_DEFERRED_GROUPS = tuple(
    group.key for group in ONBOARDING_CONTRACT
    if group.required_for_stage0 and group.key in DEFERRED_PROVISIONING
)

AUTHORITY_BY_GROUP = {
    'restaurant_profile': 'authorized Tenant/Organization/Location scope verification',
    'inventory_items': 'restaurant.inventory.service.create/update_inventory_item',
    'uom_conversions': 'restaurant.inventory.service.append_item_uom_conversion',
    'suppliers': 'restaurant.inventory.receiving.create/update_supplier',
    'supplier_offerings': 'restaurant.inventory.receiving.create/update_offering',
    'resources': 'restaurant.resource_provisioning.provision_resource',
    'preparation_configuration': (
        'restaurant.preparation.configuration_provisioning.provision_configuration'
    ),
    'preparation_areas': (
        'restaurant.preparation.area_provisioning.provision_area'
    ),
    'preparation_routes': (
        'restaurant.preparation.route_provisioning.provision_route_binding'
    ),
    'categories': 'restaurant.catalog.category_provisioning.provision_category',
    'products': 'restaurant.catalog.provisioning.provision_product',
}


class ImportRejectedError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ImportScope:
    tenant_id: int
    organization_id: int
    location_id: int


@dataclass(frozen=True, slots=True)
class PlanItem:
    group: str
    row: int
    business_key: dict[str, Any]
    operation: str
    authority: str
    values: dict[str, Any]
    existing_id: int | None = None
    existing_version: int | None = None
    blocking_error: str | None = None


@dataclass(frozen=True, slots=True)
class ImportPlan:
    scope: ImportScope
    items: tuple[PlanItem, ...]

    @property
    def blocking_errors(self) -> tuple[str, ...]:
        return tuple(item.blocking_error for item in self.items if item.blocking_error)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _dependency_ordered_rows(rows: tuple[AnalyzedRow, ...]) -> tuple[AnalyzedRow, ...]:
    categories = [row for row in rows if row.group == 'categories']
    ordered_categories: list[AnalyzedRow] = []
    remaining = list(categories)
    while remaining:
        remaining_keys = {row.values['category_key'] for row in remaining}
        ready = [
            row for row in remaining
            if row.values['parent_category_key'] not in remaining_keys
        ]
        if not ready:
            ready = remaining
        ordered_categories.extend(ready)
        remaining = [row for row in remaining if row not in ready]
    iterator = iter(ordered_categories)
    return tuple(next(iterator) if row.group == 'categories' else row for row in rows)


def dataset_fingerprint(analysis: AnalysisResult) -> str:
    """Identify the normalized dataset, independent of filename or XLSX metadata."""

    payload = {
        'contract_version': analysis.contract_version,
        'rows': [
            {
                'group': row.group,
                'business_key': _json_value(row.business_key),
                'values': _json_value(row.values),
            }
            for row in analysis.rows
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return sha256(canonical.encode('utf-8')).hexdigest()


def coverage() -> tuple[dict[str, Any], ...]:
    values = []
    for group in ONBOARDING_CONTRACT:
        if group.key in IMPORTABLE_NOW:
            classification = 'IMPORTABLE_NOW'
            authority = AUTHORITY_BY_GROUP[group.key]
        elif group.key in OPERATIONAL_NOT_CATALOG_IMPORT:
            classification = 'OPERATIONAL_NOT_CATALOG_IMPORT'
            authority = 'authorized payment capability/credential workflow'
        else:
            classification = 'DEFERRED_PROVISIONING'
            authority = group.authority
        values.append({
            'group': group.key,
            'classification': classification,
            'authority': authority,
            'business_key': list(group.business_key),
            'required_for_stage0': group.required_for_stage0,
        })
    return tuple(values)


def _same(value: Any, expected: Any) -> bool:
    return value == expected


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _utc_naive(value: Any) -> datetime | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _item_values(row: AnalyzedRow) -> tuple[Any, ...]:
    value = row.values
    return (
        value['name'], value['base_uom'], _decimal(value['standard_unit_cost']), value['currency'],
        value['lot_tracking_policy'], value['date_tracking_policy'], value['status'],
    )


async def build_import_plan(
    db: AsyncSession, *, analysis: AnalysisResult, tenant_id: int,
    tenant_slug: str, location_id: int, authorized_location_ids: tuple[int, ...],
    permissions: frozenset[str],
) -> ImportPlan:
    """Build the complete, non-mutating plan before any import evidence or writes."""

    if analysis.status != 'VALID' or analysis.contract_version != CONTRACT_VERSION:
        raise ImportRejectedError('INVALID_ANALYSIS', 'Only a valid current-contract analysis can be confirmed')
    if location_id not in authorized_location_ids:
        raise ImportRejectedError('UNAUTHORIZED_SCOPE', 'Location is not authorized')
    if 'location.manage' not in permissions:
        raise ImportRejectedError('INSUFFICIENT_PERMISSION', 'location.manage permission is required')

    result = await db.execute(
        select(Tenant, Organization, Location)
        .join(Organization, Organization.tenant_id == Tenant.id)
        .join(
            Location,
            (Location.organization_id == Organization.id)
            & (Location.tenant_id == Tenant.id),
        )
        .where(Tenant.id == tenant_id, Location.id == location_id)
    )
    authority = result.first()
    if authority is None:
        raise ImportRejectedError('UNAUTHORIZED_SCOPE', 'Authorized location scope was not found')
    tenant, organization, location = authority

    profiles = [row for row in analysis.rows if row.group == 'restaurant_profile']
    if len(profiles) != 1:
        raise ImportRejectedError('SCOPE_MISMATCH', 'Exactly one restaurant profile is required for confirmation')
    profile = profiles[0]
    expected_scope = profile.values
    if (
        expected_scope['tenant_slug'] != tenant_slug
        or expected_scope['tenant_slug'] != tenant.slug
        or expected_scope['organization_code'] != organization.code
        or expected_scope['location_code'] != location.code
    ):
        raise ImportRejectedError('SCOPE_MISMATCH', 'Workbook scope does not match the authorized server scope')

    for row in analysis.rows:
        value = row.values
        if value.get('tenant_slug', tenant.slug) != tenant.slug:
            raise ImportRejectedError('SCOPE_MISMATCH', f'Row {row.group}:{row.row} crosses tenant scope')
        if value.get('organization_code', organization.code) != organization.code:
            raise ImportRejectedError('SCOPE_MISMATCH', f'Row {row.group}:{row.row} crosses organization scope')
        if value.get('location_code', location.code) != location.code:
            raise ImportRejectedError('SCOPE_MISMATCH', f'Row {row.group}:{row.row} crosses location scope')

    profile_fields = (
        (tenant.name, expected_scope['tenant_name']),
        (organization.name, expected_scope['organization_name']),
        (location.name, expected_scope['location_name']),
        (location.timezone, expected_scope['timezone']),
        (location.address_line1, expected_scope['address_line1']),
        (location.address_line2, expected_scope['address_line2']),
        (location.locality, expected_scope['locality']),
        (location.administrative_area, expected_scope['administrative_area']),
        (location.postal_code, expected_scope['postal_code']),
        (location.country_code, expected_scope['country_code']),
        (location.phone, expected_scope['phone']),
        (location.email, expected_scope['email']),
        (location.status, expected_scope['status']),
    )
    profile_error = None if all(_same(*pair) for pair in profile_fields) else (
        'Restaurant profile differs from the authorized existing scope; explicit profile update authority is required'
    )
    items: list[PlanItem] = [PlanItem(
        group=profile.group, row=profile.row, business_key=profile.business_key,
        operation='UNCHANGED', authority=AUTHORITY_BY_GROUP[profile.group],
        values=profile.values, existing_id=location.id, blocking_error=profile_error,
    )]

    ordered_rows = _dependency_ordered_rows(analysis.rows)
    populated = {row.group for row in ordered_rows}
    if populated & {'inventory_items', 'uom_conversions'} and 'inventory.manage' not in permissions:
        raise ImportRejectedError('INSUFFICIENT_PERMISSION', 'inventory.manage permission is required')
    if populated & {'suppliers', 'supplier_offerings'} and 'inventory.supplier.manage' not in permissions:
        raise ImportRejectedError('INSUFFICIENT_PERMISSION', 'inventory.supplier.manage permission is required')
    if 'resources' in populated and 'resource.manage' not in permissions:
        raise ImportRejectedError('INSUFFICIENT_PERMISSION', 'resource.manage permission is required')
    if (
        populated & {
            'preparation_configuration', 'preparation_areas', 'preparation_routes',
        }
        and 'preparation.configure' not in permissions
    ):
        raise ImportRejectedError(
            'INSUFFICIENT_PERMISSION',
            'preparation.configure permission is required',
        )
    if populated & {'categories', 'products'} and 'product.manage' not in permissions:
        raise ImportRejectedError('INSUFFICIENT_PERMISSION', 'product.manage permission is required')

    product_namespace = product_provisioning.onboarding_binding_namespace(
        contract_version=CONTRACT_VERSION, organization_id=organization.id,
    )

    existing_items = {
        value.code: value for value in (
            await db.scalars(select(InventoryItem).where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.location_id == location.id,
            ))
        ).all()
    }
    existing_suppliers = {
        value.code: value for value in (
            await db.scalars(select(Supplier).where(
                Supplier.tenant_id == tenant_id,
                Supplier.organization_id == organization.id,
            ))
        ).all()
    }

    category_keys = {
        row.values['category_key'] for row in ordered_rows if row.group == 'categories'
    }
    resource_keys = {
        row.values['resource_code'] for row in ordered_rows
        if row.group == 'resources'
    }
    product_keys = {
        row.values['product_key'] for row in ordered_rows
        if row.group == 'products'
    }
    area_keys = {
        row.values['preparation_area_code'] for row in ordered_rows
        if row.group == 'preparation_areas'
    }
    for row in ordered_rows:
        if row.group == 'restaurant_profile':
            continue
        if row.group not in IMPORTABLE_NOW:
            classification = (
                'OPERATIONAL_NOT_CATALOG_IMPORT'
                if row.group in OPERATIONAL_NOT_CATALOG_IMPORT else 'DEFERRED_PROVISIONING'
            )
            items.append(PlanItem(
                group=row.group, row=row.row, business_key=row.business_key,
                operation='DEFERRED', authority=classification, values=row.values,
            ))
            continue
        value = row.values
        if row.group == 'resources':
            blocker = None
            try:
                resource_plan = await resource_provisioning.plan_resource(
                    db, tenant_id=tenant_id, location_id=location.id,
                    resource_code=value['resource_code'], name=value['name'],
                    resource_type=value['resource_type'], status=value['status'],
                )
                operation, current_id = resource_plan.operation, resource_plan.resource_id
            except resource_provisioning.ResourceProvisioningError as exc:
                operation, current_id, blocker = 'CREATE', None, str(exc)
            items.append(PlanItem(
                row.group, row.row, row.business_key, operation,
                AUTHORITY_BY_GROUP[row.group], value, current_id,
                blocking_error=blocker,
            ))
        elif row.group == 'preparation_configuration':
            blocker = None
            try:
                configuration_plan = await configuration_provisioning.plan_configuration(
                    db, tenant_id=tenant_id,
                    organization_id=organization.id,
                    location_id=location.id,
                    preparation_owner=value['preparation_owner'],
                )
                operation = configuration_plan.operation
                current_id = configuration_plan.configuration_id
            except (
                configuration_provisioning.PreparationConfigurationProvisioningError
            ) as exc:
                operation, current_id, blocker = 'CREATE', None, str(exc)
            items.append(PlanItem(
                row.group, row.row, row.business_key, operation,
                AUTHORITY_BY_GROUP[row.group], value, current_id,
                blocking_error=blocker,
            ))
        elif row.group == 'preparation_areas':
            blocker = None
            try:
                area_plan = await area_provisioning.plan_area(
                    db, tenant_id=tenant_id,
                    organization_id=organization.id,
                    location_id=location.id,
                    area_code=value['preparation_area_code'],
                    resource_code=value['resource_code'],
                    name=value['name'], status=value['status'],
                    allow_unresolved_resource=(
                        value['resource_code'] in resource_keys
                    ),
                )
                operation, current_id = area_plan.operation, area_plan.area_id
            except area_provisioning.PreparationAreaProvisioningError as exc:
                operation, current_id, blocker = 'CREATE', None, str(exc)
            items.append(PlanItem(
                row.group, row.row, row.business_key, operation,
                AUTHORITY_BY_GROUP[row.group], value, current_id,
                blocking_error=blocker,
            ))
        elif row.group == 'preparation_routes':
            blocker = None
            try:
                route_plan = await route_provisioning.plan_route_binding(
                    db, tenant_id=tenant_id,
                    organization_id=organization.id,
                    location_id=location.id,
                    binding_namespace=product_namespace,
                    product_key=value['product_key'], policy=value['policy'],
                    preparation_area_code=value['preparation_area_code'],
                    status=value['status'],
                    allow_unresolved_product=(
                        value['product_key'] in product_keys
                    ),
                    allow_unresolved_area=(
                        value['preparation_area_code'] in area_keys
                    ),
                )
                operation = route_plan.operation
                current_id = route_plan.current_route_id
            except route_provisioning.PreparationRouteProvisioningError as exc:
                operation, current_id, blocker = 'CREATE', None, str(exc)
            items.append(PlanItem(
                row.group, row.row, row.business_key, operation,
                AUTHORITY_BY_GROUP[row.group], value, current_id,
                blocking_error=blocker,
            ))
        elif row.group == 'categories':
            blocker = None
            try:
                category_plan = await category_provisioning.plan_category(
                    db, tenant_id=tenant_id, organization_id=organization.id,
                    binding_namespace=product_namespace,
                    category_key=value['category_key'],
                    parent_category_key=value['parent_category_key'],
                    name=value['name'], display_order=value['display_order'] or 0,
                    status=value['status'],
                    allow_unresolved_parent=value['parent_category_key'] in category_keys,
                )
                operation, current_id = category_plan.operation, category_plan.category_id
            except category_provisioning.CategoryProvisioningError as exc:
                operation, current_id, blocker = 'CREATE', None, str(exc)
            items.append(PlanItem(
                row.group, row.row, row.business_key, operation,
                AUTHORITY_BY_GROUP[row.group], value, current_id,
                blocking_error=blocker,
            ))
        elif row.group == 'products':
            blocker = None
            try:
                product_plan = await product_provisioning.plan_product(
                    db, tenant_id=tenant_id, organization_id=organization.id,
                    binding_namespace=product_namespace,
                    product_key=value['product_key'],
                    category_key=value['category_key'], name=value['name'],
                    description=value['description'], status=value['status'],
                    allow_unresolved_category=value['category_key'] in category_keys,
                )
                operation, current_id = product_plan.operation, product_plan.product_id
            except product_provisioning.ProductProvisioningError as exc:
                operation, current_id, blocker = 'CREATE', None, str(exc)
            items.append(PlanItem(
                row.group, row.row, row.business_key, operation,
                AUTHORITY_BY_GROUP[row.group], value, current_id,
                blocking_error=blocker,
            ))
        elif row.group == 'inventory_items':
            current = existing_items.get(value['inventory_item_code'])
            if current is None:
                operation, current_id, version, blocker = 'CREATE', None, None, (
                    None if value['status'] == 'ACTIVE' else 'New Inventory Items must be ACTIVE'
                )
            else:
                current_tuple = (
                    current.name, current.base_uom, current.standard_unit_cost,
                    current.currency, current.lot_tracking_policy,
                    current.date_tracking_policy, current.status,
                )
                operation = 'UNCHANGED' if current_tuple == _item_values(row) else 'UPDATE'
                current_id, version, blocker = current.id, current.version, None
            items.append(PlanItem(row.group, row.row, row.business_key, operation,
                                  AUTHORITY_BY_GROUP[row.group], value, current_id, version, blocker))
        elif row.group == 'uom_conversions':
            current_item = existing_items.get(value['inventory_item_code'])
            latest = None
            if current_item is not None:
                latest = await db.scalar(select(ItemUomConversion).where(
                    ItemUomConversion.tenant_id == tenant_id,
                    ItemUomConversion.inventory_item_id == current_item.id,
                    ItemUomConversion.operational_uom == value['operational_uom'],
                ).order_by(ItemUomConversion.revision.desc()).limit(1))
            same = latest is not None and latest.factor_to_base == _decimal(value['factor_to_base'])
            if same and value['effective_at'] is not None:
                same = latest.effective_at == _utc_naive(value['effective_at'])
            items.append(PlanItem(
                row.group, row.row, row.business_key, 'UNCHANGED' if same else 'CREATE',
                AUTHORITY_BY_GROUP[row.group], value,
                None if latest is None else latest.id,
            ))
        elif row.group == 'suppliers':
            current = existing_suppliers.get(value['supplier_code'])
            active_location = False
            current_locations: tuple[int, ...] = ()
            if current is not None:
                current_locations = tuple((await db.scalars(select(SupplierLocation.location_id).where(
                    SupplierLocation.tenant_id == tenant_id,
                    SupplierLocation.supplier_id == current.id,
                    SupplierLocation.status == 'ACTIVE',
                ))).all())
                active_location = location.id in current_locations
            same = current is not None and (
                current.name, current.contact_reference, current.status, active_location
            ) == (value['name'], value['contact_reference'], value['status'], True)
            blocker = None if current is not None or value['status'] == 'ACTIVE' else 'New Suppliers must be ACTIVE'
            if current is not None and not set(current_locations) <= set(authorized_location_ids):
                blocker = 'Existing Supplier has availability outside the actor authorized Locations'
            items.append(PlanItem(
                row.group, row.row, row.business_key,
                'CREATE' if current is None else ('UNCHANGED' if same else 'UPDATE'),
                AUTHORITY_BY_GROUP[row.group], value,
                None if current is None else current.id,
                None if current is None else current.version, blocker,
            ))
        elif row.group == 'supplier_offerings':
            supplier = existing_suppliers.get(value['supplier_code'])
            item = existing_items.get(value['inventory_item_code'])
            current = None
            if supplier is not None and item is not None:
                current = await db.scalar(select(SupplierOffering).where(
                    SupplierOffering.tenant_id == tenant_id,
                    SupplierOffering.supplier_id == supplier.id,
                    SupplierOffering.location_id == location.id,
                    SupplierOffering.inventory_item_id == item.id,
                ))
            same = current is not None and (
                current.supplier_item_code, current.purchase_uom, current.status
            ) == (value['supplier_item_code'], value['purchase_uom'], value['status'])
            blocker = None
            if current is None and value['status'] != 'ACTIVE':
                blocker = 'New Supplier Offerings must be ACTIVE'
            elif current is not None and current.purchase_uom != value['purchase_uom']:
                blocker = 'Existing Supplier Offering purchase_uom cannot be overwritten'
            items.append(PlanItem(
                row.group, row.row, row.business_key,
                'CREATE' if current is None else ('UNCHANGED' if same else 'UPDATE'),
                AUTHORITY_BY_GROUP[row.group], value,
                None if current is None else current.id,
                None if current is None else current.version, blocker,
            ))
    return ImportPlan(ImportScope(tenant_id, organization.id, location.id), tuple(items))


def _classification(group_key: str) -> str:
    if group_key in IMPORTABLE_NOW:
        return 'IMPORTABLE_NOW'
    if group_key in OPERATIONAL_NOT_CATALOG_IMPORT:
        return 'OPERATIONAL_NOT_CATALOG_IMPORT'
    return 'DEFERRED_PROVISIONING'


def _empty_summaries(plan: ImportPlan) -> dict[str, dict[str, Any]]:
    return {
        group.key: {
            'classification': _classification(group.key),
            'authority': AUTHORITY_BY_GROUP.get(group.key, group.authority),
            'required_for_stage0': group.required_for_stage0,
            'planned': 0, 'created': 0, 'updated': 0, 'unchanged': 0,
            'deferred': 0, 'failed': 0,
        }
        for group in ONBOARDING_CONTRACT
    }


def _result(
    *, evidence: OnboardingImport, plan: ImportPlan, status: str, replay: bool,
    summaries: dict[str, dict[str, Any]], errors: list[dict[str, Any]],
) -> dict[str, Any]:
    totals = {key: sum(value[key] for value in summaries.values()) for key in (
        'created', 'updated', 'unchanged', 'deferred', 'failed'
    )}
    return {
        'import_id': evidence.import_id,
        'contract_version': evidence.contract_version,
        'dataset_fingerprint': evidence.dataset_fingerprint,
        'scope': asdict(plan.scope),
        'status': status,
        'replay': replay,
        'total_planned_rows': len(plan.items),
        'required_deferred_groups': list(REQUIRED_DEFERRED_GROUPS),
        **totals,
        'groups': summaries,
        'errors': errors,
    }


async def _existing_replay(
    db: AsyncSession, *, scope: ImportScope, fingerprint: str,
) -> OnboardingImport | None:
    return await db.scalar(select(OnboardingImport).where(
        OnboardingImport.tenant_id == scope.tenant_id,
        OnboardingImport.organization_id == scope.organization_id,
        OnboardingImport.location_id == scope.location_id,
        OnboardingImport.contract_version == CONTRACT_VERSION,
        OnboardingImport.dataset_fingerprint == fingerprint,
    ))


async def confirm_import(
    db: AsyncSession, *, analysis: AnalysisResult, expected_fingerprint: str,
    tenant_id: int, tenant_slug: str, membership_id: int, location_id: int,
    authorized_location_ids: tuple[int, ...], permissions: frozenset[str],
) -> dict[str, Any]:
    fingerprint = dataset_fingerprint(analysis)
    if expected_fingerprint != fingerprint:
        raise ImportRejectedError('DATASET_MISMATCH', 'Confirmation fingerprint does not match the analyzed dataset')
    plan = await build_import_plan(
        db, analysis=analysis, tenant_id=tenant_id, tenant_slug=tenant_slug,
        location_id=location_id, authorized_location_ids=authorized_location_ids,
        permissions=permissions,
    )
    previous = await _existing_replay(db, scope=plan.scope, fingerprint=fingerprint)
    if previous is not None:
        if previous.result_json is not None:
            replay = dict(previous.result_json)
            replay['replay'] = True
            return replay
        return {
            'import_id': previous.import_id, 'contract_version': CONTRACT_VERSION,
            'dataset_fingerprint': fingerprint, 'scope': asdict(plan.scope),
            'status': 'PARTIAL', 'replay': True, 'total_planned_rows': len(plan.items),
            'required_deferred_groups': list(REQUIRED_DEFERRED_GROUPS),
            'created': 0, 'updated': 0, 'unchanged': 0, 'deferred': 0, 'failed': 1,
            'groups': _empty_summaries(plan),
            'errors': [{'code': 'RECOVERY_REQUIRED', 'message': 'The prior import has no terminal result; it was not re-executed'}],
        }

    evidence = OnboardingImport(
        import_id=str(uuid4()), tenant_id=plan.scope.tenant_id,
        organization_id=plan.scope.organization_id, location_id=plan.scope.location_id,
        contract_version=CONTRACT_VERSION, dataset_fingerprint=fingerprint,
        actor_membership_id=membership_id, status='IN_PROGRESS', result_json=None,
    )
    db.add(evidence)
    try:
        await db.commit()
        await db.refresh(evidence)
    except IntegrityError:
        await db.rollback()
        previous = await _existing_replay(db, scope=plan.scope, fingerprint=fingerprint)
        if previous is None:
            raise
        if previous.result_json is not None:
            replay = dict(previous.result_json)
            replay['replay'] = True
            return replay
        return {
            'import_id': previous.import_id, 'contract_version': CONTRACT_VERSION,
            'dataset_fingerprint': fingerprint, 'scope': asdict(plan.scope),
            'status': 'PARTIAL', 'replay': True, 'total_planned_rows': len(plan.items),
            'required_deferred_groups': list(REQUIRED_DEFERRED_GROUPS),
            'created': 0, 'updated': 0, 'unchanged': 0, 'deferred': 0, 'failed': 1,
            'groups': _empty_summaries(plan),
            'errors': [{'code': 'RECOVERY_REQUIRED', 'message': 'The import is already in progress and was not re-executed'}],
        }
    evidence_id = evidence.id

    summaries = _empty_summaries(plan)
    for item in plan.items:
        summaries[item.group]['planned'] += 1
    errors: list[dict[str, Any]] = []
    if plan.blocking_errors:
        for item in plan.items:
            if item.blocking_error:
                summaries[item.group]['failed'] += 1
                errors.append({'code': 'PLAN_BLOCKED', 'group': item.group, 'row': item.row, 'message': item.blocking_error})
        result = _result(evidence=evidence, plan=plan, status='FAILED', replay=False, summaries=summaries, errors=errors)
        evidence.status, evidence.result_json = 'FAILED', result
        evidence.completed_at = datetime.now(UTC).replace(tzinfo=None)
        await db.commit()
        return result

    try:
        for item in plan.items:
            summary = summaries[item.group]
            if item.operation == 'DEFERRED':
                summary['deferred'] += 1
                continue
            if item.operation == 'UNCHANGED':
                summary['unchanged'] += 1
                continue
            value = item.values
            actual_operation = item.operation
            if item.group == 'resources':
                result = await resource_provisioning.provision_resource(
                    db, tenant_id=tenant_id, location_id=location_id,
                    resource_code=value['resource_code'], name=value['name'],
                    resource_type=value['resource_type'], status=value['status'],
                )
                actual_operation = result.operation
            elif item.group == 'preparation_configuration':
                result = await configuration_provisioning.provision_configuration(
                    db, tenant_id=tenant_id,
                    organization_id=plan.scope.organization_id,
                    location_id=location_id,
                    preparation_owner=value['preparation_owner'],
                )
                actual_operation = result.operation
            elif item.group == 'preparation_areas':
                result = await area_provisioning.provision_area(
                    db, tenant_id=tenant_id,
                    organization_id=plan.scope.organization_id,
                    location_id=location_id,
                    area_code=value['preparation_area_code'],
                    resource_code=value['resource_code'],
                    name=value['name'], status=value['status'],
                )
                actual_operation = result.operation
            elif item.group == 'preparation_routes':
                result = await route_provisioning.provision_route_binding(
                    db, tenant_id=tenant_id,
                    organization_id=plan.scope.organization_id,
                    location_id=location_id,
                    binding_namespace=product_provisioning.onboarding_binding_namespace(
                        contract_version=CONTRACT_VERSION,
                        organization_id=plan.scope.organization_id,
                    ),
                    product_key=value['product_key'], policy=value['policy'],
                    preparation_area_code=value['preparation_area_code'],
                    status=value['status'],
                )
                actual_operation = result.operation
            elif item.group == 'categories':
                result = await category_provisioning.provision_category(
                    db, tenant_id=tenant_id,
                    organization_id=plan.scope.organization_id,
                    binding_namespace=product_provisioning.onboarding_binding_namespace(
                        contract_version=CONTRACT_VERSION,
                        organization_id=plan.scope.organization_id,
                    ),
                    category_key=value['category_key'],
                    parent_category_key=value['parent_category_key'],
                    name=value['name'], display_order=value['display_order'] or 0,
                    status=value['status'],
                )
                actual_operation = result.operation
            elif item.group == 'products':
                result = await product_provisioning.provision_product(
                    db, tenant_id=tenant_id,
                    organization_id=plan.scope.organization_id,
                    binding_namespace=product_provisioning.onboarding_binding_namespace(
                        contract_version=CONTRACT_VERSION,
                        organization_id=plan.scope.organization_id,
                    ),
                    product_key=value['product_key'],
                    category_key=value['category_key'], name=value['name'],
                    description=value['description'], status=value['status'],
                )
                actual_operation = result.operation
            elif item.group == 'inventory_items':
                if item.operation == 'CREATE':
                    await inventory_service.create_inventory_item(
                        db, tenant_id=tenant_id, location_id=location_id,
                        code=value['inventory_item_code'], name=value['name'],
                        base_uom=value['base_uom'], standard_unit_cost=_decimal(value['standard_unit_cost']),
                        currency=value['currency'], actor_id=membership_id,
                        lot_tracking_policy=value['lot_tracking_policy'],
                        date_tracking_policy=value['date_tracking_policy'],
                    )
                else:
                    await inventory_service.update_inventory_item(
                        db, tenant_id=tenant_id, inventory_item_id=item.existing_id,
                        expected_version=item.existing_version, name=value['name'],
                        standard_unit_cost=_decimal(value['standard_unit_cost']), currency=value['currency'],
                        status=value['status'], actor_id=membership_id,
                        lot_tracking_policy=value['lot_tracking_policy'],
                        date_tracking_policy=value['date_tracking_policy'],
                    )
            elif item.group == 'uom_conversions':
                inventory_item = await db.scalar(select(InventoryItem).where(
                    InventoryItem.tenant_id == tenant_id,
                    InventoryItem.location_id == location_id,
                    InventoryItem.code == value['inventory_item_code'],
                ))
                if inventory_item is None:
                    raise RuntimeError('Planned Inventory Item dependency was not established')
                effective_at = _utc_naive(value['effective_at'])
                await inventory_service.append_item_uom_conversion(
                    db, tenant_id=tenant_id, inventory_item_id=inventory_item.id,
                    operational_uom=value['operational_uom'], factor_to_base=_decimal(value['factor_to_base']),
                    effective_at=effective_at, actor_id=membership_id, reference=value['reference'],
                )
            elif item.group == 'suppliers':
                if item.operation == 'CREATE':
                    await receiving.create_supplier(
                        db, tenant_id=tenant_id, organization_id=plan.scope.organization_id,
                        code=value['supplier_code'], name=value['name'],
                        contact_reference=value['contact_reference'], location_ids=(location_id,),
                    )
                else:
                    current_locations = await receiving.supplier_locations(
                        db, tenant_id=tenant_id, supplier_id=item.existing_id,
                    )
                    await receiving.update_supplier(
                        db, tenant_id=tenant_id, supplier_id=item.existing_id,
                        expected_version=item.existing_version, name=value['name'],
                        status=value['status'], contact_reference=value['contact_reference'],
                        location_ids=tuple(dict.fromkeys((*current_locations, location_id))),
                    )
            elif item.group == 'supplier_offerings':
                supplier = await db.scalar(select(Supplier).where(
                    Supplier.tenant_id == tenant_id,
                    Supplier.organization_id == plan.scope.organization_id,
                    Supplier.code == value['supplier_code'],
                ))
                inventory_item = await db.scalar(select(InventoryItem).where(
                    InventoryItem.tenant_id == tenant_id,
                    InventoryItem.location_id == location_id,
                    InventoryItem.code == value['inventory_item_code'],
                ))
                if supplier is None or inventory_item is None:
                    raise RuntimeError('Planned Supplier Offering dependency was not established')
                if item.operation == 'CREATE':
                    await receiving.create_offering(
                        db, tenant_id=tenant_id, supplier_id=supplier.id,
                        location_id=location_id, inventory_item_id=inventory_item.id,
                        supplier_item_code=value['supplier_item_code'], purchase_uom=value['purchase_uom'],
                    )
                else:
                    await receiving.update_offering(
                        db, tenant_id=tenant_id, offering_id=item.existing_id,
                        expected_version=item.existing_version, status=value['status'],
                        supplier_item_code=value['supplier_item_code'],
                    )
            summary[{
                'CREATE': 'created', 'UPDATE': 'updated', 'UNCHANGED': 'unchanged',
            }[actual_operation]] += 1
    except Exception:
        await db.rollback()
        summaries[item.group]['failed'] += 1
        errors.append({
            'code': 'IMPORT_FAILED', 'group': item.group, 'row': item.row,
            'message': 'An existing write authority rejected the planned operation',
        })
        completed = sum(s['created'] + s['updated'] for s in summaries.values())
        status = 'PARTIAL' if completed else 'FAILED'
    else:
        status = 'PARTIAL' if REQUIRED_DEFERRED_GROUPS or any(
            s['deferred'] for s in summaries.values()
        ) else 'SUCCESS'

    evidence = await db.scalar(
        select(OnboardingImport).where(OnboardingImport.id == evidence_id).with_for_update()
    )
    result = _result(evidence=evidence, plan=plan, status=status, replay=False, summaries=summaries, errors=errors)
    evidence.status, evidence.result_json = status, result
    evidence.completed_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return result
