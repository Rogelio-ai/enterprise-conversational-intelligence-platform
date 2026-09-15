from __future__ import annotations

import asyncio
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
import pytest

from app.main import create_app
from app.onboarding.importer import coverage
from app.onboarding.contract import CONTRACT_VERSION
from app.onboarding.xlsx import deterministic_bytes
from app.restaurant.catalog import provisioning as product_provisioning
from app.restaurant.inventory import service as inventory_service
from test_inventory_recipe_stock_foundation import _headers, _permission, _scope


MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def test_all_contract_groups_have_one_explicit_import_classification() -> None:
    values = coverage()
    assert len(values) == 32
    by_group = {value['group']: value for value in values}
    assert len(by_group) == 32
    assert by_group['inventory_items']['classification'] == 'IMPORTABLE_NOW'
    assert by_group['products']['classification'] == 'IMPORTABLE_NOW'
    assert by_group['staff']['classification'] == 'DEFERRED_PROVISIONING'
    assert by_group['tax_rules']['classification'] == 'DEFERRED_PROVISIONING'
    assert by_group['warehouses']['classification'] == 'DEFERRED_PROVISIONING'
    assert by_group['payment_methods']['classification'] == 'OPERATIONAL_NOT_CATALOG_IMPORT'
    assert all(value['authority'] and value['business_key'] for value in values)


def _set_row(workbook, sheet: str, values: tuple[object, ...], row: int = 2) -> None:
    for column, value in enumerate(values, start=1):
        workbook[sheet].cell(row, column, value)


def _workbook(
    tenant_slug: str, *, item_code: str = 'FLOUR', product: bool = False,
    deferred_resource: bool = False,
) -> bytes:
    workbook = load_workbook(BytesIO(deterministic_bytes()), data_only=False)
    _set_row(workbook, '01_Restaurant', (
        tenant_slug, 'Inventory Tenant', 'ORG', 'Inventory Organization', 'LOC',
        'Inventory Location', 'America/Mexico_City', None, None, None, None,
        None, 'MX', None, None, 'ACTIVE',
    ))
    _set_row(workbook, '19_Inventory_Items', (
        'LOC', item_code, f'Item {item_code}', 'G', '0.010000', 'MXN',
        'OPTIONAL', 'NONE', 'ACTIVE',
    ))
    _set_row(workbook, '20_UOM_Conversions', (
        'LOC', item_code, 'BAG', '1000', None, 'approved capture',
    ))
    _set_row(workbook, '21_Suppliers', (
        'ORG', f'SUP-{item_code}', f'Supplier {item_code}', None, 'LOC', 'ACTIVE',
    ))
    _set_row(workbook, '22_Supplier_Offers', (
        f'SUP-{item_code}', 'LOC', item_code, None, 'G', 'ACTIVE',
    ))
    if product:
        _set_row(workbook, '07_Products', (
            f'PROD-{item_code}', 'ORG', None, f'Product {item_code}', None, 'ACTIVE',
        ))
    if deferred_resource:
        _set_row(workbook, '03_Resources', (
            'LOC', f'RESOURCE-{item_code}', f'Resource {item_code}', 'TABLE', 'ACTIVE',
        ))
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _prepare(connection, prefix: str):
    scope = _scope(connection, f'{prefix}-onboarding')
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE locations SET country_code='MX' WHERE id=%s", (scope.location_id,)
        )
    for permission in (
        'location.manage', 'inventory.manage', 'inventory.supplier.manage', 'product.manage',
    ):
        _permission(connection, scope.role_id, permission)
    return scope


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _analyze(client, headers, content):
    return client.post(
        '/onboarding/stage0/analyze', headers={**headers, 'Content-Type': MEDIA_TYPE},
        content=content,
    )


def _confirm(client, headers, content, location_id, fingerprint, *, explicit=True):
    values = {
        **headers, 'Content-Type': MEDIA_TYPE,
        'X-Dataset-Fingerprint': fingerprint,
    }
    if explicit:
        values['X-Confirm-Import'] = 'true'
    return client.post(
        f'/onboarding/stage0/confirm?location_id={location_id}',
        headers=values, content=content,
    )


def _count(connection, table: str, tenant_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT COUNT(*) AS amount FROM {table} WHERE tenant_id=%s', (tenant_id,))
        return int(cursor.fetchone()['amount'])


def test_confirmation_binding_authorities_replay_and_no_inventory_history(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    content = _workbook(f'{prefix}-onboarding')

    analysis = _analyze(client, headers, content)
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()['analysis']['status'] == 'VALID'
    fingerprint = analysis.json()['dataset_fingerprint']
    assert _count(connection, 'inventory_items', scope.tenant_id) == 0
    assert _count(connection, 'onboarding_imports', scope.tenant_id) == 0

    missing_confirmation = _confirm(
        client, headers, content, scope.location_id, fingerprint, explicit=False,
    )
    assert missing_confirmation.status_code == 422
    changed_content = _workbook(f'{prefix}-onboarding', item_code='CHANGED')
    mismatch = _confirm(client, headers, changed_content, scope.location_id, fingerprint)
    assert mismatch.status_code == 409
    assert _count(connection, 'inventory_items', scope.tenant_id) == 0

    first = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['status'] == 'PARTIAL' and result['replay'] is False, result
    assert 'products' not in result['required_deferred_groups']
    assert (result['total_planned_rows'], result['created'], result['unchanged']) == (5, 4, 1)
    assert [result['groups'][key]['created'] for key in (
        'inventory_items', 'uom_conversions', 'suppliers', 'supplier_offerings'
    )] == [1, 1, 1, 1]
    assert _count(connection, 'inventory_items', scope.tenant_id) == 1
    assert _count(connection, 'stock_movements', scope.tenant_id) == 0
    assert _count(connection, 'inventory_lots', scope.tenant_id) == 0
    assert _count(connection, 'inventory_cost_layers', scope.tenant_id) == 0

    replay = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert replay.status_code == 200, replay.text
    assert replay.json()['import_id'] == result['import_id']
    assert replay.json()['replay'] is True
    assert _count(connection, 'inventory_items', scope.tenant_id) == 1
    assert _count(connection, 'onboarding_imports', scope.tenant_id) == 1


def test_existing_records_use_deterministic_authority_updates(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    content = _workbook(f'{prefix}-onboarding', item_code='BEANS')
    fingerprint = _analyze(client, headers, content).json()['dataset_fingerprint']
    first = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert first.status_code == 201 and first.json()['status'] == 'PARTIAL'

    workbook = load_workbook(BytesIO(content), data_only=False)
    workbook['19_Inventory_Items']['C2'] = 'Updated Beans'
    workbook['19_Inventory_Items']['E2'] = '0.020000'
    workbook['21_Suppliers']['C2'] = 'Updated Supplier'
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    changed = output.getvalue()
    changed_fingerprint = _analyze(client, headers, changed).json()['dataset_fingerprint']

    updated = _confirm(client, headers, changed, scope.location_id, changed_fingerprint)
    assert updated.status_code == 201, updated.text
    result = updated.json()
    assert result['status'] == 'PARTIAL'
    assert result['updated'] == 2
    assert result['unchanged'] == 3
    assert _count(connection, 'inventory_items', scope.tenant_id) == 1
    assert _count(connection, 'inventory_cost_revisions', scope.tenant_id) == 2


def test_product_import_binding_update_replay_and_distinct_keys(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    content = _workbook(f'{prefix}-onboarding', item_code='CATALOG', product=True)
    workbook = load_workbook(BytesIO(content), data_only=False)
    _set_row(workbook, '07_Products', (
        'PROD-SECOND', 'ORG', None, 'Product CATALOG', None, 'ACTIVE',
    ), row=3)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    content = output.getvalue()
    fingerprint = _analyze(client, headers, content).json()['dataset_fingerprint']

    first = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['groups']['products']['classification'] == 'IMPORTABLE_NOW'
    assert result['groups']['products']['created'] == 2
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id,organization_id,name,status,source FROM products '
            'WHERE tenant_id=%s ORDER BY id',
            (scope.tenant_id,),
        )
        products = cursor.fetchall()
        cursor.execute(
            'SELECT product_id,connector_key,external_product_id '
            'FROM product_external_mappings '
            'WHERE tenant_id=%s ORDER BY external_product_id',
            (scope.tenant_id,),
        )
        bindings = cursor.fetchall()
    assert len(products) == len(bindings) == 2
    assert products[0]['id'] != products[1]['id']
    assert all(row['organization_id'] == scope.organization_id for row in products)
    assert all((row['status'], row['source']) == ('ACTIVE', 'PLATFORM') for row in products)
    expected_namespace = product_provisioning.onboarding_binding_namespace(
        contract_version=CONTRACT_VERSION, organization_id=scope.organization_id,
    )
    assert all(row['connector_key'] == expected_namespace for row in bindings)
    assert {row['external_product_id'] for row in bindings} == {'PROD-CATALOG', 'PROD-SECOND'}

    async def resolve() -> tuple[int, int]:
        from app.db.session import DatabaseManager

        database = DatabaseManager(integration_settings)
        try:
            async with database.session_factory() as db:
                namespace = product_provisioning.onboarding_binding_namespace(
                    contract_version=CONTRACT_VERSION,
                    organization_id=scope.organization_id,
                )
                first_product = await product_provisioning.resolve_product_binding(
                    db, tenant_id=scope.tenant_id, organization_id=scope.organization_id,
                    binding_namespace=namespace, product_key='PROD-CATALOG',
                )
                second_product = await product_provisioning.resolve_product_binding(
                    db, tenant_id=scope.tenant_id, organization_id=scope.organization_id,
                    binding_namespace=namespace, product_key='PROD-SECOND',
                )
                return first_product.id, second_product.id
        finally:
            await database.dispose()

    resolved = asyncio.run(resolve())
    assert set(resolved) == {row['id'] for row in products}

    replay = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert replay.status_code == 200 and replay.json()['replay'] is True
    assert _count(connection, 'products', scope.tenant_id) == 2

    workbook = load_workbook(BytesIO(content), data_only=False)
    workbook['07_Products']['D2'] = 'Updated canonical Product'
    changed_output = BytesIO()
    workbook.save(changed_output)
    workbook.close()
    changed = changed_output.getvalue()
    changed_fingerprint = _analyze(client, headers, changed).json()['dataset_fingerprint']
    updated = _confirm(client, headers, changed, scope.location_id, changed_fingerprint)
    assert updated.status_code == 201, updated.text
    assert updated.json()['groups']['products']['updated'] == 1
    assert updated.json()['groups']['products']['unchanged'] == 1
    assert _count(connection, 'products', scope.tenant_id) == 2


def test_product_binding_conflict_across_organization_blocks_before_product_write(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'OTHER','Other','ACTIVE')",
            (scope.tenant_id,),
        )
        other_organization_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO products (tenant_id,organization_id,name,status,source) "
            "VALUES (%s,%s,'Foreign','ACTIVE','PLATFORM')",
            (scope.tenant_id, other_organization_id),
        )
        foreign_product_id = cursor.lastrowid
        namespace = product_provisioning.onboarding_binding_namespace(
            contract_version=CONTRACT_VERSION, organization_id=scope.organization_id,
        )
        cursor.execute(
            'INSERT INTO product_external_mappings '
            '(tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)',
            (scope.tenant_id, foreign_product_id, namespace, 'PROD-CONFLICT'),
        )

    content = _workbook(f'{prefix}-onboarding', item_code='CONFLICT', product=True)
    fingerprint = _analyze(client, headers, content).json()['dataset_fingerprint']
    response = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['status'] == 'FAILED'
    assert result['groups']['products']['failed'] == 1
    assert result['errors'][0]['code'] == 'PLAN_BLOCKED'
    assert _count(connection, 'products', scope.tenant_id) == 1


def test_partial_authority_failure_is_durable_and_not_blindly_replayed(
    client, sql_connection, monkeypatch,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    content = _workbook(f'{prefix}-onboarding', item_code='FAILSAFE')
    fingerprint = _analyze(client, headers, content).json()['dataset_fingerprint']

    async def reject_conversion(*args, **kwargs):
        raise RuntimeError('simulated authority failure')

    monkeypatch.setattr(inventory_service, 'append_item_uom_conversion', reject_conversion)
    first = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['status'] == 'PARTIAL'
    assert result['created'] == 1 and result['failed'] == 1
    assert result['groups']['suppliers']['created'] == 0
    assert result['errors'][0]['message'] == 'An existing write authority rejected the planned operation'

    replay = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert replay.status_code == 200
    assert replay.json()['import_id'] == result['import_id']
    assert replay.json()['status'] == 'PARTIAL' and replay.json()['replay'] is True
    assert _count(connection, 'inventory_items', scope.tenant_id) == 1
    assert _count(connection, 'onboarding_imports', scope.tenant_id) == 1


def test_invalid_and_cross_scope_confirmation_cannot_persist(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    invalid = bytearray(_workbook(f'{prefix}-onboarding', item_code='INVALID'))
    invalid[-8:] = b'not-xlsx'
    invalid_analysis = _analyze(client, headers, bytes(invalid)).json()
    response = _confirm(
        client, headers, bytes(invalid), scope.location_id,
        invalid_analysis['dataset_fingerprint'],
    )
    assert response.status_code == 422

    content = _workbook(f'{prefix}-onboarding', item_code='CROSS')
    fingerprint = _analyze(client, headers, content).json()['dataset_fingerprint']
    response = _confirm(client, headers, content, scope.location_id + 999999, fingerprint)
    assert response.status_code == 403
    assert _count(connection, 'inventory_items', scope.tenant_id) == 0
    assert _count(connection, 'onboarding_imports', scope.tenant_id) == 0


def test_deferred_group_is_visible_and_prevents_false_success(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    headers = _headers(client, scope)
    content = _workbook(f'{prefix}-onboarding', item_code='RICE', deferred_resource=True)
    fingerprint = _analyze(client, headers, content).json()['dataset_fingerprint']

    response = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['status'] == 'PARTIAL', result
    assert result['deferred'] == 1
    assert result['groups']['resources'] == {
        'classification': 'DEFERRED_PROVISIONING',
        'authority': 'models.resource.Resource',
        'required_for_stage0': True,
        'planned': 1, 'created': 0, 'updated': 0, 'unchanged': 0,
        'deferred': 1, 'failed': 0,
    }
    assert _count(connection, 'resources', scope.tenant_id) == 0
