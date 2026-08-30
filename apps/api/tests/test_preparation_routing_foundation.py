from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.main import create_app
from app.restaurant.integrations.pos.mock import MockPosAdapter, build_mock_pos_dataset
from fastapi.testclient import TestClient
import pytest

from test_pos_order_submission_recovery import (
    CONNECTOR,
    _accepted_complex_order,
    _accepted_order,
    _configure,
    _execute,
    _headers,
    _scope,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _owner(client, headers, location_id: int, value: str = 'PLATFORM'):
    response = client.put(
        f'/locations/{location_id}/preparation-configuration',
        headers=headers,
        json={'preparation_owner': value},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _area(client, headers, location_id: int, code: str = 'COCINA'):
    response = client.post(
        '/preparation-areas', headers=headers,
        json={'location_id': location_id, 'code': code, 'name': code.title()},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _route(client, headers, location_id: int, product_id: int, policy: str, area_id=None):
    response = client.put(
        f'/locations/{location_id}/products/{product_id}/preparation-route',
        headers=headers,
        json={'policy': policy, 'preparation_area_id': area_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_native_platform_routing_needs_no_external_pos_and_is_idempotent(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    route = _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda _: client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers),
            range(2),
        ))
    assert {response.status_code for response in responses} == {200}
    bodies = [response.json() for response in responses]
    assert {body['id'] for body in bodies}.__len__() == 1
    result = bodies[0]
    assert result['state'] == 'ROUTED'
    assert result['preparation_owner'] == 'PLATFORM'
    assert len(result['works']) == 1
    assert result['works'][0]['area_code'] == 'COCINA'
    assert result['works'][0]['items'][0]['route_id'] == route['id']
    assert result['works'][0]['items'][0]['source_restaurant_order_item_id'] is not None
    replay = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert replay.status_code == 200 and replay.json() == result


def test_missing_route_is_atomic_action_required_and_retry_uses_repaired_configuration(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    failed = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert failed.status_code == 200
    assert failed.json()['state'] == 'ACTION_REQUIRED'
    assert failed.json()['error_code'] == 'MISSING_PRODUCT_ROUTE'
    assert failed.json()['works'] == []

    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    repaired = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert repaired.status_code == 200
    assert repaired.json()['state'] == 'ROUTED'
    assert len(repaired.json()['works']) == 1


def test_no_preparation_is_successful_with_zero_work_and_suppresses_children(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, parent, _, _, _ = _accepted_complex_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, parent, 'NO_PREPARATION')
    result = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert result.status_code == 200
    assert result.json()['state'] == 'ROUTED'
    assert result.json()['works'] == []


def test_components_policy_routes_accepted_components_and_suppresses_parent(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, parent, fixed, option, _ = _accepted_complex_order(
        client, connection, scope, parent_quantity='2', fixed_quantity='3'
    )
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    kitchen = _area(client, headers, scope.location_id)
    bar = _area(client, headers, scope.location_id, 'BAR')
    _route(client, headers, scope.location_id, parent, 'COMPONENTS')
    _route(client, headers, scope.location_id, fixed, 'AREA', kitchen['id'])
    _route(client, headers, scope.location_id, option, 'AREA', bar['id'])
    result = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['state'] == 'ROUTED'
    assert {work['area_code'] for work in body['works']} == {'COCINA', 'BAR'}
    items = [item for work in body['works'] for item in work['items']]
    assert len(items) == 2
    assert all(item['source_restaurant_order_item_id'] is None for item in items)
    assert all(item['source_restaurant_order_item_component_id'] is not None for item in items)
    assert sorted(item['required_quantity'] for item in items) == ['2.0000', '6.0000']


def test_platform_owner_rejects_unsafe_pos_but_accepts_certified_no_output(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    first_order, first_product, _ = _accepted_order(client, connection, scope, name='First')
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, first_product, 'AREA', area['id'])
    connection_id = _execute(connection, "INSERT INTO location_pos_connections (tenant_id,organization_id,location_id,connector_key,external_location_id,status,active_slot,stable_replay_supported,recovery_supported,external_preparation_behavior) VALUES (%s,%s,%s,%s,'location-001','ACTIVE',1,1,0,'MAY_PRODUCE_PREPARATION_OUTPUT')", (scope.tenant_id, scope.organization_id, scope.location_id, CONNECTOR))
    blocked = client.post(f'/restaurant-orders/{first_order}/preparation-routing', headers=headers)
    assert blocked.status_code == 200
    assert blocked.json()['error_code'] == 'EXTERNAL_PREPARATION_OUTPUT_CONFLICT'
    assert blocked.json()['works'] == []

    connection.cursor().execute("UPDATE location_pos_connections SET external_preparation_behavior='NO_PREPARATION_OUTPUT' WHERE id=%s", (connection_id,))
    routed = client.post(f'/restaurant-orders/{first_order}/preparation-routing', headers=headers)
    assert routed.status_code == 200 and routed.json()['state'] == 'ROUTED'
    _execute(connection, 'INSERT INTO product_external_mappings (tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)', (scope.tenant_id, first_product, CONNECTOR, 'product-001'))
    client.app.state.pos_adapters[CONNECTOR] = MockPosAdapter(build_mock_pos_dataset(
        tenant_id=scope.tenant_id, connector_key=CONNECTOR,
        location_ids=(scope.location_id, scope.location_id + 1_000_000),
    ))
    submitted = client.post(f'/restaurant-orders/{first_order}/pos-submission', headers=headers)
    assert submitted.status_code == 200 and submitted.json()['state'] == 'SUCCEEDED'


def test_external_pos_owner_requires_connection_and_never_creates_native_work(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, _, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id, 'EXTERNAL_POS')
    missing = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert missing.status_code == 200
    assert missing.json()['error_code'] == 'EXTERNAL_POS_CONNECTION_REQUIRED'
    _execute(connection, "INSERT INTO location_pos_connections (tenant_id,organization_id,location_id,connector_key,external_location_id,status,active_slot,stable_replay_supported,recovery_supported) VALUES (%s,%s,%s,%s,'location-001','ACTIVE',1,1,0)", (scope.tenant_id, scope.organization_id, scope.location_id, CONNECTOR))
    result = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert result.status_code == 200
    assert result.json()['state'] == 'EXTERNAL_POS_OWNED'
    assert result.json()['works'] == []


def test_frozen_owner_and_area_snapshots_survive_live_configuration_changes(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    original = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers).json()
    _owner(client, headers, scope.location_id, 'EXTERNAL_POS')
    changed = client.patch(f"/preparation-areas/{area['id']}", headers=headers, json={'name': 'Renamed'})
    assert changed.status_code == 200
    replay = client.get(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert replay.status_code == 200
    assert replay.json()['preparation_owner'] == 'PLATFORM'
    assert replay.json()['works'][0]['area_name'] == original['works'][0]['area_name']


def test_legacy_pos_submission_does_not_invent_preparation_ownership(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    connection_id = _execute(connection, "INSERT INTO location_pos_connections (tenant_id,organization_id,location_id,connector_key,external_location_id,status,active_slot,stable_replay_supported,recovery_supported) VALUES (%s,%s,%s,%s,'location-001','ACTIVE',1,1,0)", (scope.tenant_id, scope.organization_id, scope.location_id, CONNECTOR))
    _execute(connection, "INSERT INTO pos_order_submissions (tenant_id,organization_id,location_id,restaurant_order_id,connection_id,connector_key,external_location_id,stable_replay_supported,recovery_supported,idempotency_key,request_schema_version,request_fingerprint,state,attempt_count,last_error_kind,last_error_message,initiated_actor_type,initiated_principal_reference) VALUES (%s,%s,%s,%s,%s,%s,'location-001',1,0,%s,1,%s,'ACTION_REQUIRED',1,'MAPPING','legacy','SYSTEM','legacy-import')", (scope.tenant_id, scope.organization_id, scope.location_id, order_id, connection_id, CONNECTOR, f'legacy:{order_id}', '0' * 64))
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    result = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert result.status_code == 200
    assert result.json()['preparation_owner'] is None
    assert result.json()['error_code'] == 'LEGACY_PREPARATION_OWNERSHIP_UNRESOLVED'
    assert result.json()['works'] == []


def test_pos_and_preparation_initialization_share_one_frozen_owner(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pos_future = pool.submit(
            client.post, f'/restaurant-orders/{order_id}/pos-submission', headers=headers
        )
        route_future = pool.submit(
            client.post, f'/restaurant-orders/{order_id}/preparation-routing', headers=headers
        )
        pos_response = pos_future.result()
        route_response = route_future.result()
    assert pos_response.status_code == 200
    assert route_response.status_code == 200
    assert route_response.json()['preparation_owner'] == 'EXTERNAL_POS'
    assert route_response.json()['state'] == 'EXTERNAL_POS_OWNED'
    assert route_response.json()['works'] == []
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count,MIN(preparation_owner) AS owner,MAX(preparation_owner) AS owner2 FROM preparation_routings WHERE tenant_id=%s AND restaurant_order_id=%s', (scope.tenant_id, order_id))
        row = cursor.fetchone()
    assert row == {'count': 1, 'owner': 'EXTERNAL_POS', 'owner2': 'EXTERNAL_POS'}
