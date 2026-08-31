from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import pytest

from app.core.execution import ActorType, ExecutionContext
from app.db.session import DatabaseManager
from app.main import create_app
from app.restaurant.preparation_delivery import errors
from app.restaurant.preparation_delivery import service as delivery_service
from app.restaurant.preparation_delivery.contracts import DeliveryResult
from test_pos_order_submission_recovery import (
    _accepted_complex_order,
    _accepted_order,
    _execute,
    _headers,
    _scope,
)
from test_preparation_routing_foundation import _area, _owner, _route


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _connector(client, headers, location_id, *, code='LOCAL_01', name='Local Connector'):
    response = client.post('/preparation-delivery-connectors', headers=headers, json={
        'location_id': location_id, 'code': code, 'name': name,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _destination(
    client, headers, location_id, area_id, connector_id, *,
    code='PRINTER_01', name='Kitchen Printer', target='kitchen_printer_01',
):
    response = client.post('/preparation-delivery-destinations', headers=headers, json={
        'location_id': location_id, 'preparation_area_id': area_id,
        'connector_id': connector_id, 'code': code, 'name': name,
        'channel': 'PRINTER', 'local_target_key': target,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _native_dispatch(client, connection, scope, *, name='Burger'):
    order_id, product_id, _ = _accepted_order(client, connection, scope, name=name)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    connector = _connector(client, headers, scope.location_id)
    destination = _destination(
        client, headers, scope.location_id, area['id'], connector['id'],
    )
    routed = client.post(
        f'/restaurant-orders/{order_id}/preparation-routing', headers=headers,
    )
    assert routed.status_code == 200, routed.text
    work_id = routed.json()['works'][0]['id']
    dispatches = client.get(
        f'/preparation-works/{work_id}/dispatches', headers=headers,
    )
    assert dispatches.status_code == 200, dispatches.text
    return headers, order_id, area, work_id, connector, destination, dispatches.json()[0]


def _machine(scope, connector, correlation='connector-test') -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EXTERNAL_SYSTEM,
        tenant_id=scope.tenant_id,
        principal_id=None,
        principal_reference=connector['auth_subject'],
        correlation_id=correlation,
    )


def _delivery_result(result, *, job=None, error_kind=None, error_message=None):
    fingerprint = delivery_service.result_fingerprint(
        result=result, local_job_reference=job,
        error_kind=error_kind, error_message=error_message,
    )
    return DeliveryResult(
        result=result, result_fingerprint=fingerprint,
        local_job_reference=job, error_kind=error_kind,
        error_message=error_message,
    )


def test_connector_destination_configuration_scope_and_active_target(client, sql_connection):
    connection, prefix = sql_connection
    scope_a = _scope(connection, f'{prefix}-a')
    scope_b = _scope(connection, f'{prefix}-b')
    headers_a = _headers(client, scope_a)
    headers_b = _headers(client, scope_b)
    area_a = _area(client, headers_a, scope_a.location_id)
    area_b = _area(client, headers_b, scope_b.location_id)
    connector_a = _connector(client, headers_a, scope_a.location_id)
    connector_b = _connector(client, headers_b, scope_b.location_id)

    assert client.get(
        '/preparation-delivery-connectors', headers=headers_b,
        params={'location_id': scope_a.location_id},
    ).status_code == 404

    assert connector_a['auth_subject'].startswith('preparation-connector:')
    renamed = client.patch(
        f"/preparation-delivery-connectors/{connector_a['id']}",
        headers=headers_a, json={'name': 'Renamed'},
    )
    assert renamed.status_code == 200
    assert renamed.json()['auth_subject'] == connector_a['auth_subject']
    assert client.patch(
        f"/preparation-delivery-connectors/{connector_a['id']}",
        headers=headers_a, json={'auth_subject': 'forged'},
    ).status_code == 422

    assert client.post('/preparation-delivery-destinations', headers=headers_a, json={
        'location_id': scope_a.location_id, 'preparation_area_id': area_a['id'],
        'connector_id': connector_b['id'], 'code': 'CROSS', 'name': 'Cross',
        'channel': 'PRINTER', 'local_target_key': 'cross_target',
    }).status_code == 404
    assert client.post('/preparation-delivery-destinations', headers=headers_a, json={
        'location_id': scope_a.location_id, 'preparation_area_id': area_b['id'],
        'connector_id': connector_a['id'], 'code': 'CROSS_AREA', 'name': 'Cross',
        'channel': 'PRINTER', 'local_target_key': 'cross_area',
    }).status_code == 404
    destination = _destination(
        client, headers_a, scope_a.location_id, area_a['id'], connector_a['id'],
    )
    assert client.get(
        '/preparation-delivery-destinations', headers=headers_b,
        params={'location_id': scope_a.location_id},
    ).status_code == 404
    duplicate = client.post('/preparation-delivery-destinations', headers=headers_a, json={
        'location_id': scope_a.location_id, 'preparation_area_id': area_a['id'],
        'connector_id': connector_a['id'], 'code': 'ANOTHER', 'name': 'Another',
        'channel': 'PRINTER', 'local_target_key': destination['local_target_key'],
    })
    assert duplicate.status_code == 409
    assert client.post('/preparation-delivery-destinations', headers=headers_a, json={
        'location_id': scope_a.location_id, 'preparation_area_id': area_a['id'],
        'connector_id': connector_a['id'], 'code': 'URL', 'name': 'URL',
        'channel': 'PRINTER', 'local_target_key': 'http://printer',
    }).status_code == 422


def test_multiple_materialization_payload_snapshots_and_independence(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, parent, fixed, option, _ = _accepted_complex_order(
        client, connection, scope, parent_quantity='2', fixed_quantity='3',
    )
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, parent, 'AREA', area['id'])
    connector = _connector(client, headers, scope.location_id)
    first = _destination(
        client, headers, scope.location_id, area['id'], connector['id'],
        code='PRINTER_A', name='Printer A', target='printer_a',
    )
    second = _destination(
        client, headers, scope.location_id, area['id'], connector['id'],
        code='PRINTER_B', name='Printer B', target='printer_b',
    )
    routed = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert routed.status_code == 200, routed.text
    work = routed.json()['works'][0]
    dispatches = client.get(
        f"/preparation-works/{work['id']}/dispatches", headers=headers,
    ).json()
    assert len(dispatches) == 2
    assert {value['destination_id'] for value in dispatches} == {first['id'], second['id']}
    assert len({value['operation_id'] for value in dispatches}) == 2
    assert {value['state'] for value in dispatches} == {'PENDING'}
    assert {value['initiating_actor_type'] for value in dispatches} == {'SYSTEM'}
    assert {value['initiating_principal_reference'] for value in dispatches} == {
        'preparation-dispatch-materializer'
    }
    payload = json.loads(dispatches[0]['payload_text'])
    assert payload['schema'] == 'preparation-delivery-v1'
    assert payload['restaurant_order']['resource_code_at_dispatch'] is not None
    assert payload['items'][0]['product_name'] == 'Combo'
    assert {value['product_name'] for value in payload['items'][0]['accepted_components']} == {
        'Fries', 'Cola'
    }
    assert 'price' not in dispatches[0]['payload_text'].lower()
    assert 'email' not in dispatches[0]['payload_text'].lower()
    assert delivery_service.fingerprint_text(dispatches[0]['payload_text']) == dispatches[0]['payload_fingerprint']
    assert dispatches[0]['payload_fingerprint'] == dispatches[1]['payload_fingerprint']

    old_payload = dispatches[0]['payload_text']
    old_destination_name = dispatches[0]['destination_name']
    old_connector_code = dispatches[0]['connector_code']
    old_connector_name = dispatches[0]['connector_name']
    connection.cursor().execute("UPDATE products SET name='Mutable catalog name' WHERE id IN (%s,%s,%s)", (parent, fixed, option))
    connection.cursor().execute("UPDATE resources SET code='MUTATED',name='Mutated Table' WHERE id=%s", (scope.resource_id,))
    assert client.patch(
        f"/preparation-delivery-destinations/{first['id']}", headers=headers,
        json={'name': 'Renamed Printer'},
    ).status_code == 200
    assert client.patch(
        f"/preparation-delivery-connectors/{connector['id']}", headers=headers,
        json={'name': 'Renamed Connector'},
    ).status_code == 200
    historical = client.get(
        f"/preparation-dispatches/{dispatches[0]['id']}", headers=headers,
    ).json()
    assert historical['payload_text'] == old_payload
    assert historical['destination_name'] == old_destination_name
    assert historical['connector_code'] == old_connector_code
    assert historical['connector_name'] == old_connector_name
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM restaurant_orders WHERE id=%s', (order_id,))
        assert cursor.fetchone()['status'] == 'ACCEPTED'
        cursor.execute('SELECT DISTINCT execution_state FROM preparation_work_items WHERE preparation_work_id=%s', (work['id'],))
        assert {row['execution_state'] for row in cursor.fetchall()} == {'NEW'}
        cursor.execute('SELECT COUNT(*) AS count FROM preparation_item_transitions WHERE preparation_work_id=%s', (work['id'],))
        assert cursor.fetchone()['count'] == 0


def test_no_destination_and_inactive_destination_are_valid(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    first_order, first_product, _ = _accepted_order(client, connection, scope, name='No destination')
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, first_product, 'AREA', area['id'])
    first_routing = client.post(f'/restaurant-orders/{first_order}/preparation-routing', headers=headers).json()
    assert len(first_routing['works']) == 1
    assert client.get(
        f"/preparation-works/{first_routing['works'][0]['id']}/dispatches", headers=headers,
    ).json() == []

    second_resource = _execute(
        connection,
        "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) "
        "VALUES (%s,%s,'T-SECOND','Second Table','TABLE','ACTIVE')",
        (scope.tenant_id, scope.location_id),
    )
    second_scope = replace(scope, resource_id=second_resource)
    second_order, second_product, _ = _accepted_order(
        client, connection, second_scope, name='Inactive',
    )
    _route(client, headers, scope.location_id, second_product, 'AREA', area['id'])
    connector = _connector(client, headers, scope.location_id)
    destination = _destination(
        client, headers, scope.location_id, area['id'], connector['id'],
    )
    assert client.patch(
        f"/preparation-delivery-destinations/{destination['id']}",
        headers=headers, json={'status': 'INACTIVE'},
    ).status_code == 200
    second_routing = client.post(f'/restaurant-orders/{second_order}/preparation-routing', headers=headers).json()
    assert client.get(
        f"/preparation-works/{second_routing['works'][0]['id']}/dispatches", headers=headers,
    ).json() == []

    assert client.patch(
        f"/preparation-delivery-destinations/{destination['id']}",
        headers=headers, json={'status': 'ACTIVE'},
    ).status_code == 200
    assert client.patch(
        f"/preparation-delivery-connectors/{connector['id']}",
        headers=headers, json={'status': 'INACTIVE'},
    ).status_code == 200
    third_resource = _execute(
        connection,
        "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) "
        "VALUES (%s,%s,'T-THIRD','Third Table','TABLE','ACTIVE')",
        (scope.tenant_id, scope.location_id),
    )
    third_order, third_product, _ = _accepted_order(
        client, connection, replace(scope, resource_id=third_resource), name='Inactive connector',
    )
    _route(client, headers, scope.location_id, third_product, 'AREA', area['id'])
    third_routing = client.post(
        f'/restaurant-orders/{third_order}/preparation-routing', headers=headers,
    ).json()
    third_dispatches = client.get(
        f"/preparation-works/{third_routing['works'][0]['id']}/dispatches", headers=headers,
    ).json()
    assert len(third_dispatches) == 1
    assert third_dispatches[0]['state'] == 'ACTION_REQUIRED'
    assert third_dispatches[0]['last_error_kind'] == 'CONNECTOR_INACTIVE'


def test_concurrent_routing_materializes_one_initial_dispatch(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    connector = _connector(client, headers, scope.location_id)
    _destination(client, headers, scope.location_id, area['id'], connector['id'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda _: client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers),
            range(2),
        ))
    assert {response.status_code for response in responses} == {200}
    work_id = responses[0].json()['works'][0]['id']
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM preparation_dispatches WHERE preparation_work_id=%s', (work_id,))
        assert cursor.fetchone()['count'] == 1


def test_claim_result_retry_uncertain_replay_and_fencing(
    client, sql_connection, integration_settings,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, _, _, _, connector, _, dispatch = _native_dispatch(client, connection, scope)

    async def spoofed_claim():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await delivery_service.claim_dispatch(
                    db, dispatch_id=dispatch['id'], connector_id=connector['id'],
                    execution=ExecutionContext(
                        actor_type=ActorType.EXTERNAL_SYSTEM,
                        tenant_id=scope.tenant_id,
                        principal_id=None,
                        principal_reference='preparation-connector:forged',
                        correlation_id='forged-connector',
                    ),
                )
        finally:
            await manager.dispose()

    with pytest.raises(errors.PreparationDeliveryNotFoundError):
        asyncio.run(spoofed_claim())

    def claim(*, recovery=False):
        async def run():
            manager = DatabaseManager(integration_settings)
            try:
                async with manager.session_factory() as db:
                    return await delivery_service.claim_dispatch(
                        db, dispatch_id=dispatch['id'], connector_id=connector['id'],
                        execution=_machine(scope, connector), recovery=recovery,
                    )
            finally:
                await manager.dispose()
        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        outcomes = []
        failures = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except Exception as exc:  # noqa: BLE001 - assert domain concurrency result
                failures.append(exc)
    assert len(outcomes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], errors.PreparationDeliveryConflictError)
    first_claim = outcomes[0]
    assert first_claim.attempt.attempt_type == 'DELIVER'

    async def record(claim_token, result):
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await delivery_service.record_result(
                    db, dispatch_id=dispatch['id'], connector_id=connector['id'],
                    claim_token=claim_token, delivery_result=result,
                    execution=_machine(scope, connector),
                )
        finally:
            await manager.dispose()

    retryable = _delivery_result(
        'RETRYABLE_FAILURE', error_kind='DEVICE_UNAVAILABLE',
        error_message='Definite failure before submission',
    )
    first_result = asyncio.run(record(first_claim.claim_token, retryable))
    assert first_result.dispatch.state == 'RETRYABLE_FAILURE'
    replay = asyncio.run(record(first_claim.claim_token, retryable))
    assert replay.replayed is True
    conflicting = _delivery_result('UNCERTAIN', error_kind='TIMEOUT', error_message='Unknown')
    with pytest.raises(errors.PreparationDeliveryConflictError):
        asyncio.run(record(first_claim.claim_token, conflicting))

    second_claim = claim()
    assert second_claim.dispatch.operation_id == first_claim.dispatch.operation_id
    assert second_claim.dispatch.generation == first_claim.dispatch.generation == 1
    assert second_claim.attempt.attempt_sequence == 2
    assert second_claim.attempt.attempt_type == 'RETRY'
    uncertain = asyncio.run(record(
        second_claim.claim_token,
        _delivery_result('UNCERTAIN', error_kind='CONNECTION_LOST', error_message='Boundary may have been crossed'),
    ))
    assert uncertain.dispatch.state == 'UNCERTAIN'
    with pytest.raises(errors.PreparationDeliveryConflictError):
        claim()

    recovery_claim = claim(recovery=True)
    assert recovery_claim.attempt.attempt_type == 'RECOVERY'
    assert recovery_claim.dispatch.operation_id == dispatch['operation_id']
    accepted = asyncio.run(record(
        recovery_claim.claim_token,
        _delivery_result('DESTINATION_SUBMISSION_ACCEPTED', job='local-job-1'),
    ))
    assert accepted.dispatch.state == 'DESTINATION_SUBMISSION_ACCEPTED'
    assert accepted.dispatch.terminal_at is not None
    with pytest.raises(errors.PreparationDeliveryConflictError):
        asyncio.run(record(
            second_claim.claim_token,
            _delivery_result('DESTINATION_SUBMISSION_ACCEPTED', job='late-job'),
        ))
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM preparation_dispatch_attempts WHERE dispatch_id=%s', (dispatch['id'],))
        assert cursor.fetchone()['count'] == 3


def test_expired_claim_recovery_fences_stale_claim(client, sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, _, _, _, connector, _, dispatch = _native_dispatch(client, connection, scope)

    async def claim(recovery=False):
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await delivery_service.claim_dispatch(
                    db, dispatch_id=dispatch['id'], connector_id=connector['id'],
                    execution=_machine(scope, connector), recovery=recovery,
                )
        finally:
            await manager.dispose()

    first = asyncio.run(claim())
    connection.cursor().execute(
        'UPDATE preparation_dispatches SET claim_expires_at=%s WHERE id=%s',
        (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1), dispatch['id']),
    )
    with pytest.raises(errors.PreparationDeliveryConflictError):
        asyncio.run(claim())
    recovered = asyncio.run(claim(recovery=True))
    assert recovered.attempt.attempt_type == 'RECOVERY'
    assert recovered.claim_token != first.claim_token

    async def stale_result():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await delivery_service.record_result(
                    db, dispatch_id=dispatch['id'], connector_id=connector['id'],
                    claim_token=first.claim_token,
                    delivery_result=_delivery_result('DESTINATION_SUBMISSION_ACCEPTED', job='stale'),
                    execution=_machine(scope, connector),
                )
        finally:
            await manager.dispose()

    with pytest.raises(errors.PreparationDeliveryConflictError):
        asyncio.run(stale_result())


def test_reprint_is_new_employee_operation_and_requires_dispatch_permission(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, _, _, _, dispatch = _native_dispatch(client, connection, scope)
    response = client.post(
        f"/preparation-dispatches/{dispatch['id']}/reprints", headers=headers,
    )
    assert response.status_code == 201, response.text
    reprint = response.json()
    assert reprint['id'] != dispatch['id']
    assert reprint['operation_kind'] == 'REPRINT'
    assert reprint['generation'] == 2
    assert reprint['operation_id'] != dispatch['operation_id']
    assert reprint['payload_text'] == dispatch['payload_text']
    assert reprint['payload_fingerprint'] == dispatch['payload_fingerprint']
    assert reprint['reprint_of_dispatch_id'] == dispatch['id']
    assert reprint['initiating_actor_type'] == 'EMPLOYEE'
    assert reprint['initiating_membership_id'] is not None
    assert client.get(f"/preparation-dispatches/{reprint['id']}", headers=headers).status_code == 200

    forbidden_scope = _scope(
        connection, f'{prefix}-forbidden', include_dispatch_permission=False,
    )
    forbidden_headers, _, _, _, _, _, forbidden_dispatch = _native_dispatch(
        client, connection, forbidden_scope,
    )
    assert client.post(
        f"/preparation-dispatches/{forbidden_dispatch['id']}/reprints",
        headers=forbidden_headers,
    ).status_code == 403


def test_dispatch_reads_are_tenant_safe_and_diner_forbidden(client, sql_connection):
    connection, prefix = sql_connection
    scope_a = _scope(connection, f'{prefix}-a')
    headers_a, _, _, _, _, _, dispatch = _native_dispatch(client, connection, scope_a)
    scope_b = _scope(connection, f'{prefix}-b')
    headers_b = _headers(client, scope_b)
    assert client.get(
        f"/preparation-dispatches/{dispatch['id']}", headers=headers_b,
    ).status_code == 404
    listed = client.get('/preparation-dispatches', headers=headers_a, params={
        'location_id': scope_a.location_id, 'limit': 1,
    })
    assert listed.status_code == 200
    assert [value['id'] for value in listed.json()] == [dispatch['id']]
    # A diner credential cannot pass the employee OAuth/JWT audience boundary.
    opened = client.post(
        f'/resources/{scope_b.resource_id}/service-sessions', headers=headers_b,
        json={'party_size': 1},
    ).json()
    joined = client.post('/diner-sessions/join', json={
        'join_context_key': opened['join_context_key'],
        'access_code': opened['access_code'], 'display_name': 'Diner',
    }).json()
    diner = {'Authorization': f"Bearer {joined['access_token']}"}
    assert client.get(
        '/preparation-dispatches', headers=diner,
        params={'location_id': scope_a.location_id},
    ).status_code == 401
