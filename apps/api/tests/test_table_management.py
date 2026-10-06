from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_resource_foundation import (
    _assign_permission,
    _execute,
    _location,
    _login,
    _resource,
)
from test_service_responsibility_integration import _scope
from test_table_waiter_assignments import _assign


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _section(connection, scope, code='SALON', *, movable=True):
    return _execute(
        connection,
        'INSERT INTO dining_sections '
        '(tenant_id,organization_id,location_id,code,name,movable,status) '
        "VALUES (%s,%s,%s,%s,%s,%s,'ACTIVE')",
        (scope.actor.tenant_id, scope.organization_id, scope.location_id,
         code, code.title(), movable),
    )


def _profile(connection, scope, table_id, section_id, capacity, *, movable=True):
    return _execute(
        connection,
        'INSERT INTO restaurant_table_profiles '
        '(tenant_id,organization_id,location_id,resource_id,dining_section_id,'
        'physical_capacity,movable,administrative_status,version) '
        "VALUES (%s,%s,%s,%s,%s,%s,%s,'ACTIVE',1)",
        (scope.actor.tenant_id, scope.organization_id, scope.location_id,
         table_id, section_id, capacity, movable),
    )


def _prepare(connection, prefix, *, capacities=(4, 4, 6, 2)):
    scope = _scope(connection, prefix)
    _assign_permission(connection, scope.actor.role_id, 'table_management.manage')
    table_ids = [scope.table_id]
    for index in range(2, len(capacities) + 1):
        table_ids.append(_resource(
            connection, scope.actor.tenant_id, scope.location_id,
            f'TABLE-{index}', 'TABLE',
        ))
    section_id = _section(connection, scope)
    for table_id, capacity in zip(table_ids, capacities, strict=True):
        _profile(connection, scope, table_id, section_id, capacity)
    return scope, tuple(table_ids), section_id


def _group(client, headers, scope, representative, joined, responsible=()):
    return client.post(
        f'/locations/{scope.location_id}/table-management/groups',
        headers=headers,
        json={
            'representative_resource_id': representative,
            'joined_resource_ids': list(joined),
            'responsible_membership_ids': list(responsible),
        },
    )


def _preview(client, headers, scope, representative, joined):
    return client.post(
        f'/locations/{scope.location_id}/table-management/groups:preview',
        headers=headers,
        json={
            'representative_resource_id': representative,
            'joined_resource_ids': list(joined),
        },
    )


def _table_group_business_counts(connection, scope):
    tables = (
        'table_groups', 'table_group_memberships',
        'table_management_history', 'table_group_responsible_waiters',
    )
    result = {}
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                f'SELECT COUNT(*) AS amount FROM {table} '
                'WHERE tenant_id=%s AND location_id=%s',
                (scope.actor.tenant_id, scope.location_id),
            )
            result[table] = int(cursor.fetchone()['amount'])
    return result


def test_group_preview_canonical_formula_is_read_only_and_shared_with_create(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, _ = _prepare(connection, prefix, capacities=(4, 4, 6))
    headers = _login(client, scope.actor)
    for table_id in tables:
        assert _assign(
            client, headers, scope.location_id, table_id, scope.waiter_ids[0], 0,
        ).status_code == 201

    before = _table_group_business_counts(connection, scope)
    response = _preview(client, headers, scope, tables[0], tables[1:])
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['eligible'] is True
    assert preview['representative']['resource_id'] == tables[0]
    assert preview['representative']['physical_capacity'] == 4
    assert [member['physical_capacity'] for member in preview['members']] == [4, 4, 6]
    assert preview['derived_capacity'] == 4 + 4 + 6 - (2 * 2) == 10
    assert preview['assigned_membership_ids'] == [scope.waiter_ids[0]]
    assert preview['automatic_responsible_membership_ids'] == [scope.waiter_ids[0]]
    assert preview['responsibility_selection_required'] is False
    assert _table_group_business_counts(connection, scope) == before

    created = _group(client, headers, scope, tables[0], tables[1:])
    assert created.status_code == 201, created.text
    assert created.json()['derived_capacity'] == preview['derived_capacity']


def test_group_preview_rejects_invalid_shape_and_scope(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, _ = _prepare(connection, prefix)
    headers = _login(client, scope.actor)
    assert _preview(client, headers, scope, tables[0], ()).status_code == 422
    assert _preview(client, headers, scope, tables[0], (tables[1], tables[1])).status_code == 422
    assert _preview(client, headers, scope, tables[0], (tables[0],)).status_code == 409

    other_location_id = _location(
        connection, scope.actor.tenant_id, scope.organization_id, 'OTHER',
    )
    other_location_table = _resource(
        connection, scope.actor.tenant_id, other_location_id, 'OTHER-TABLE', 'TABLE',
    )
    assert _preview(
        client, headers, scope, tables[0], (other_location_table,),
    ).status_code == 404

    other_scope = _scope(connection, f'{prefix}-other')
    other_tenant_table = other_scope.table_id
    assert _preview(
        client, headers, scope, tables[0], (other_tenant_table,),
    ).status_code == 404
    equipment = _resource(
        connection, scope.actor.tenant_id, scope.location_id, 'EQUIPMENT', 'EQUIPMENT',
    )
    assert _preview(client, headers, scope, tables[0], (equipment,)).status_code == 404


def test_group_preview_eligibility_and_create_revalidation(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, section_id = _prepare(connection, prefix)
    headers = _login(client, scope.actor)
    for table_id in tables:
        assert _assign(
            client, headers, scope.location_id, table_id, scope.waiter_ids[0], 0,
        ).status_code == 201

    with connection.cursor() as cursor:
        cursor.execute("UPDATE resources SET status='INACTIVE' WHERE id=%s", (tables[1],))
    assert _preview(client, headers, scope, tables[0], (tables[1],)).status_code == 409
    with connection.cursor() as cursor:
        cursor.execute("UPDATE resources SET status='ACTIVE' WHERE id=%s", (tables[1],))
        cursor.execute(
            "UPDATE restaurant_table_profiles SET administrative_status='SUSPENDED' "
            'WHERE resource_id=%s', (tables[1],),
        )
    assert _preview(client, headers, scope, tables[0], (tables[1],)).status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE restaurant_table_profiles SET administrative_status='ACTIVE',movable=0 "
            'WHERE resource_id=%s', (tables[1],),
        )
    assert _preview(client, headers, scope, tables[0], (tables[1],)).status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE restaurant_table_profiles SET movable=1 WHERE resource_id=%s',
            (tables[1],),
        )
        cursor.execute('UPDATE dining_sections SET movable=0 WHERE id=%s', (section_id,))
    assert _preview(client, headers, scope, tables[0], (tables[1],)).status_code == 409
    with connection.cursor() as cursor:
        cursor.execute('UPDATE dining_sections SET movable=1 WHERE id=%s', (section_id,))

    group = _group(client, headers, scope, tables[0], (tables[1],))
    assert group.status_code == 201, group.text
    assert _preview(client, headers, scope, tables[0], (tables[2],)).status_code == 409

    advisory = _preview(client, headers, scope, tables[2], (tables[3],))
    assert advisory.status_code == 200, advisory.text
    opened = client.post(
        f'/resources/{tables[2]}/service-sessions', headers=headers,
        json={'party_size': 2},
    )
    assert opened.status_code == 201, opened.text
    assert _preview(client, headers, scope, tables[2], (tables[3],)).status_code == 409
    assert _group(client, headers, scope, tables[2], (tables[3],)).status_code == 409


def test_table_projection_movement_and_terminal_administrative_lifecycle(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, section_id = _prepare(connection, prefix)
    headers = _login(client, scope.actor)
    patio_id = _section(connection, scope, 'PATIO', movable=False)

    listed = client.get(
        f'/locations/{scope.location_id}/table-management/tables', headers=headers,
    )
    assert listed.status_code == 200, listed.text
    first = next(item for item in listed.json()['items'] if item['resource_id'] == tables[0])
    assert first['physical_capacity'] == 4
    assert first['dining_section_id'] == section_id
    assert first['effective_movable'] is True
    assert first['operational_status'] == 'AVAILABLE'

    moved = client.post(
        f'/locations/{scope.location_id}/table-management/tables/{tables[0]}:move-section',
        headers=headers,
        json={'destination_section_id': patio_id, 'expected_version': 1},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()['dining_section_id'] == patio_id
    assert moved.json()['effective_movable'] is False
    move_back = client.post(
        f'/locations/{scope.location_id}/table-management/tables/{tables[0]}:move-section',
        headers=headers,
        json={'destination_section_id': section_id, 'expected_version': 2},
    )
    assert move_back.status_code == 409

    suspended = client.post(
        f'/locations/{scope.location_id}/table-management/tables/{tables[1]}:administrative-status',
        headers=headers,
        json={'target_status': 'SUSPENDED', 'expected_version': 1},
    )
    assert suspended.status_code == 200, suspended.text
    active = client.post(
        f'/locations/{scope.location_id}/table-management/tables/{tables[1]}:administrative-status',
        headers=headers,
        json={'target_status': 'ACTIVE', 'expected_version': 2},
    )
    assert active.status_code == 200
    retired = client.post(
        f'/locations/{scope.location_id}/table-management/tables/{tables[1]}:administrative-status',
        headers=headers,
        json={'target_status': 'RETIRED', 'expected_version': 3},
    )
    assert retired.status_code == 200
    terminal = client.post(
        f'/locations/{scope.location_id}/table-management/tables/{tables[1]}:administrative-status',
        headers=headers,
        json={'target_status': 'ACTIVE', 'expected_version': 4},
    )
    assert terminal.status_code == 409
    table_history = client.get(
        f'/locations/{scope.location_id}/table-management/tables/{tables[0]}/history',
        headers=headers,
    )
    assert table_history.status_code == 200, table_history.text
    assert [item['event_type'] for item in table_history.json()['items']] == [
        'MOVE_SECTION',
    ]
    lifecycle_history = client.get(
        f'/locations/{scope.location_id}/table-management/tables/{tables[1]}/history',
        headers=headers,
    )
    assert lifecycle_history.status_code == 200, lifecycle_history.text
    assert [item['event_type'] for item in lifecycle_history.json()['items']] == [
        'ADMIN_STATUS_CHANGE', 'ADMIN_STATUS_CHANGE', 'ADMIN_STATUS_CHANGE',
    ]


def test_group_capacity_mutations_history_and_assignment_preservation(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, _ = _prepare(connection, prefix)
    headers = _login(client, scope.actor)
    for version, table_id in enumerate(tables):
        assert _assign(
            client, headers, scope.location_id, table_id, scope.waiter_ids[0], 0,
        ).status_code == 201

    created = _group(client, headers, scope, tables[0], (tables[1],))
    assert created.status_code == 201, created.text
    group = created.json()
    assert group['representative_resource_id'] == tables[0]
    assert group['member_resource_ids'] == [tables[0], tables[1]]
    assert group['derived_capacity'] == 6
    assert group['responsible_membership_ids'] == [scope.waiter_ids[0]]

    added = client.post(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}/tables",
        headers=headers,
        json={'table_resource_id': tables[2], 'expected_version': 1},
    )
    assert added.status_code == 200, added.text
    assert added.json()['derived_capacity'] == 10
    representative_remove = client.post(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}/tables/{tables[0]}:remove",
        headers=headers, json={'expected_version': 2},
    )
    assert representative_remove.status_code == 409
    removed = client.post(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}/tables/{tables[2]}:remove",
        headers=headers, json={'expected_version': 2},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()['derived_capacity'] == 6
    last = client.post(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}/tables/{tables[1]}:remove",
        headers=headers, json={'expected_version': 3},
    )
    assert last.status_code == 409
    dissolved = client.post(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}:dissolve",
        headers=headers, json={'expected_version': 3},
    )
    assert dissolved.status_code == 200, dissolved.text
    assert dissolved.json()['status'] == 'CLOSED'
    history = client.get(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}/history",
        headers=headers,
    ).json()['items']
    assert [item['event_type'] for item in history] == [
        'CREATE_GROUP', 'ADD_TABLE', 'REMOVE_TABLE', 'DISSOLVE_GROUP',
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT table_resource_id,waiter_membership_id FROM table_waiter_assignments '
            'WHERE table_resource_id IN (%s,%s,%s,%s) ORDER BY table_resource_id',
            tables,
        )
        assert len(cursor.fetchall()) == 4


def test_multi_waiter_selection_service_guards_and_close_group(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, _ = _prepare(connection, prefix)
    headers = _login(client, scope.actor)
    assert _assign(client, headers, scope.location_id, tables[0], scope.waiter_ids[0], 0).status_code == 201
    assert _assign(client, headers, scope.location_id, tables[1], scope.waiter_ids[1], 0).status_code == 201

    missing = _group(client, headers, scope, tables[0], (tables[1],))
    assert missing.status_code == 409
    created = _group(
        client, headers, scope, tables[0], (tables[1],), (scope.waiter_ids[0],),
    )
    assert created.status_code == 201, created.text
    group = created.json()
    opened = client.post(
        f'/resources/{tables[0]}/service-sessions', headers=headers,
        json={'party_size': 2},
    )
    assert opened.status_code == 201, opened.text
    non_representative = client.post(
        f'/resources/{tables[1]}/service-sessions', headers=headers,
        json={'party_size': 2},
    )
    assert non_representative.status_code == 409
    blocked = client.post(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}:dissolve",
        headers=headers, json={'expected_version': 1},
    )
    assert blocked.status_code == 409

    current = client.get(
        f'/resources/{tables[0]}/service-sessions/current', headers=headers,
    )
    session_id = current.json()['id']
    closed = client.post(
        f'/restaurant-service-sessions/{session_id}/close', headers=headers,
    )
    assert closed.status_code == 200, closed.text
    detail = client.get(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}",
        headers=headers,
    )
    assert detail.json()['status'] == 'CLOSED'
    assert client.get(
        f"/locations/{scope.location_id}/table-management/groups/{group['id']}/history",
        headers=headers,
    ).json()['items'][-1]['event_type'] == 'CLOSE_GROUP'


def test_authorization_location_isolation_and_concurrent_single_membership(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, tables, _ = _prepare(connection, prefix)
    headers = _login(client, scope.actor)
    for table_id in tables:
        assert _assign(client, headers, scope.location_id, table_id, scope.waiter_ids[0], 0).status_code == 201
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.id FROM permissions p WHERE p.code='table_management.manage'"
        )
        permission_id = int(cursor.fetchone()['id'])
        cursor.execute(
            'DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s',
            (scope.actor.role_id, permission_id),
        )
    assert client.get(
        f'/locations/{scope.location_id}/table-management/tables', headers=headers,
    ).status_code == 200
    assert _group(client, headers, scope, tables[0], (tables[2],)).status_code == 403
    _assign_permission(connection, scope.actor.role_id, 'table_management.manage')

    def create(representative):
        return _group(client, headers, scope, representative, (tables[2],))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, (tables[0], tables[1])))
    assert sorted(response.status_code for response in responses) == [201, 409]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM table_group_memberships '
            'WHERE table_resource_id=%s AND active_slot=1', (tables[2],),
        )
        assert cursor.fetchone()['count'] == 1
