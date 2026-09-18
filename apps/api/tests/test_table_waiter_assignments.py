from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient
import pytest

from app.core.security import hash_password
from app.main import create_app
from test_resource_foundation import (
    PASSWORD,
    Authority,
    _assign_permission,
    _execute,
    _grant_location,
    _location,
    _login,
    _organization,
    _resource,
    _seed_authority,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _membership_id(connection, authority: Authority) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tm.id FROM tenant_memberships tm JOIN users u ON u.id=tm.user_id '
            'WHERE tm.tenant_id=%s AND u.email=%s',
            (authority.tenant_id, authority.email),
        )
        return int(cursor.fetchone()['id'])


def _waiter(
    connection, *, tenant_id: int, location_id: int, prefix: str, label: str,
    grant: bool = True, active_user: bool = True, active_membership: bool = True,
    capabilities: tuple[str, ...] = ('order_draft.manage', 'restaurant_service.manage'),
) -> int:
    email = f'{prefix}-{label}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,%s,%s)',
        (email, hash_password(PASSWORD), f'Waiter {label}', 'ACTIVE' if active_user else 'DISABLED'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (tenant_id, user_id, 'ACTIVE' if active_membership else 'INACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, f'WAITER-{label}', 'Waiter capability role', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for capability in capabilities:
        _assign_permission(connection, role_id, capability)
    if grant:
        _execute(
            connection,
            'INSERT INTO membership_location_grants (tenant_id,membership_id,location_id) VALUES (%s,%s,%s)',
            (tenant_id, membership_id, location_id),
        )
    return membership_id


def _setup(connection, prefix: str):
    actor = _seed_authority(connection, prefix, ('resource.read', 'resource.manage'))
    organization_id = _organization(connection, actor.tenant_id, 'ORG')
    location_id = _location(connection, actor.tenant_id, organization_id, 'LOC')
    _grant_location(connection, actor, location_id)
    first_table = _resource(connection, actor.tenant_id, location_id, 'TABLE-1', 'TABLE')
    second_table = _resource(connection, actor.tenant_id, location_id, 'TABLE-2', 'TABLE')
    return actor, location_id, first_table, second_table


def _base(location_id: int, table_id: int) -> str:
    return f'/locations/{location_id}/tables/{table_id}'


def _assign(client, headers, location_id: int, table_id: int, waiter_id: int, version: int):
    return client.post(
        f'{_base(location_id, table_id)}/waiter-assignments', headers=headers,
        json={'waiter_membership_id': waiter_id, 'expected_version': version},
    )


def _responsible(client, headers, location_id: int, table_id: int, ids: list[int], version: int):
    return client.put(
        f'{_base(location_id, table_id)}/responsible-waiters', headers=headers,
        json={'responsible_membership_ids': ids, 'expected_version': version},
    )


def _unassign(
    client, headers, location_id: int, table_id: int, waiter_id: int, version: int,
    replacements: list[int] | None = None,
):
    return client.post(
        f'{_base(location_id, table_id)}/waiter-assignments/{waiter_id}:unassign',
        headers=headers,
        json={
            'expected_version': version,
            'replacement_responsible_membership_ids': replacements or [],
        },
    )


def test_assignment_cardinality_automatic_responsibility_and_audit(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    actor, location_id, first_table, second_table = _setup(connection, prefix)
    waiter = _waiter(
        connection, tenant_id=actor.tenant_id, location_id=location_id,
        prefix=prefix, label='one',
    )
    headers = _login(client, actor)

    empty = client.get(
        f'{_base(location_id, first_table)}/waiter-assignments', headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json() == {
        'table_resource_id': first_table, 'location_id': location_id,
        'configured': False, 'version': 0, 'assignments': [],
    }
    first = _assign(client, headers, location_id, first_table, waiter, 0)
    assert first.status_code == 201, first.text
    assert first.json()['assignments'] == [{
        'membership_id': waiter, 'display_name': 'Waiter one',
        'email': f'{prefix}-one@example.test', 'is_responsible': True,
    }]
    assert _assign(client, headers, location_id, first_table, waiter, 1).status_code == 409

    second = _assign(client, headers, location_id, second_table, waiter, 0)
    assert second.status_code == 201, second.text
    assert second.json()['assignments'][0]['is_responsible'] is True
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT operation,actor_membership_id,assigned_membership_ids,'
            'responsible_membership_ids,correlation_id FROM table_waiter_assignment_audits '
            'WHERE table_resource_id=%s', (first_table,),
        )
        audit = cursor.fetchone()
    assert audit['operation'] == 'ASSIGN'
    assert audit['actor_membership_id'] == _membership_id(connection, actor)
    assert json.loads(audit['assigned_membership_ids']) == [waiter]
    assert json.loads(audit['responsible_membership_ids']) == [waiter]
    assert audit['correlation_id']


def test_multiple_and_shared_responsibility_change_preserves_assignments(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    actor, location_id, table_id, _ = _setup(connection, prefix)
    waiters = [
        _waiter(
            connection, tenant_id=actor.tenant_id, location_id=location_id,
            prefix=prefix, label=str(index),
        )
        for index in range(1, 4)
    ]
    headers = _login(client, actor)
    for version, waiter in enumerate(waiters):
        response = _assign(client, headers, location_id, table_id, waiter, version)
        assert response.status_code == 201, response.text
    assert [
        item['membership_id'] for item in response.json()['assignments'] if item['is_responsible']
    ] == [waiters[0]]

    changed = _responsible(client, headers, location_id, table_id, waiters[:2], 3)
    assert changed.status_code == 200, changed.text
    assert {item['membership_id'] for item in changed.json()['assignments']} == set(waiters)
    assert {
        item['membership_id'] for item in changed.json()['assignments'] if item['is_responsible']
    } == set(waiters[:2])
    rejected = _responsible(client, headers, location_id, table_id, [999999999], 4)
    assert rejected.status_code == 409
    unchanged = client.get(
        f'{_base(location_id, table_id)}/waiter-assignments', headers=headers,
    ).json()
    assert unchanged['version'] == 4
    assert {item['membership_id'] for item in unchanged['assignments']} == set(waiters)


def test_unassignment_rules_preserve_invariants_atomically(client, sql_connection) -> None:
    connection, prefix = sql_connection
    actor, location_id, table_id, second_table = _setup(connection, prefix)
    waiters = [
        _waiter(
            connection, tenant_id=actor.tenant_id, location_id=location_id,
            prefix=prefix, label=str(index),
        )
        for index in range(1, 5)
    ]
    headers = _login(client, actor)
    for version, waiter in enumerate(waiters):
        assert _assign(client, headers, location_id, table_id, waiter, version).status_code == 201

    assert _unassign(client, headers, location_id, table_id, waiters[3], 4).status_code == 200
    assert _responsible(client, headers, location_id, table_id, waiters[:2], 5).status_code == 200
    removed_responsible = _unassign(client, headers, location_id, table_id, waiters[0], 6)
    assert removed_responsible.status_code == 200
    assert [
        item['membership_id'] for item in removed_responsible.json()['assignments']
        if item['is_responsible']
    ] == [waiters[1]]

    # Exactly two assigned: removing the sole responsible promotes the survivor.
    promoted = _unassign(client, headers, location_id, table_id, waiters[1], 7)
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()['assignments'] == [{
        'membership_id': waiters[2], 'display_name': 'Waiter 3',
        'email': f'{prefix}-3@example.test', 'is_responsible': True,
    }]
    assert _unassign(client, headers, location_id, table_id, waiters[2], 8).status_code == 409

    # Rebuild four assignments and prove manual one-or-many replacement is atomic.
    for waiter in (waiters[0], waiters[1], waiters[3]):
        current = client.get(
            f'{_base(location_id, table_id)}/waiter-assignments', headers=headers,
        ).json()
        assert _assign(
            client, headers, location_id, table_id, waiter, current['version'],
        ).status_code == 201
    current = client.get(
        f'{_base(location_id, table_id)}/waiter-assignments', headers=headers,
    ).json()
    rejected = _unassign(
        client, headers, location_id, table_id, waiters[2], current['version'],
    )
    assert rejected.status_code == 409
    after_rejection = client.get(
        f'{_base(location_id, table_id)}/waiter-assignments', headers=headers,
    ).json()
    assert after_rejection == current
    replaced = _unassign(
        client, headers, location_id, table_id, waiters[2], current['version'],
        [waiters[0]],
    )
    assert replaced.status_code == 200, replaced.text
    assert {
        item['membership_id'] for item in replaced.json()['assignments']
        if item['is_responsible']
    } == {waiters[0]}

    for version, waiter in enumerate(waiters):
        assert _assign(
            client, headers, location_id, second_table, waiter, version,
        ).status_code == 201
    multiple = _unassign(
        client, headers, location_id, second_table, waiters[0], 4,
        [waiters[1], waiters[2]],
    )
    assert multiple.status_code == 200, multiple.text
    assert {
        item['membership_id'] for item in multiple.json()['assignments']
        if item['is_responsible']
    } == {waiters[1], waiters[2]}


def test_eligibility_tenant_location_and_actor_authorization(client, sql_connection) -> None:
    connection, prefix = sql_connection
    actor, location_id, table_id, _ = _setup(connection, prefix)
    eligible = _waiter(
        connection, tenant_id=actor.tenant_id, location_id=location_id,
        prefix=prefix, label='eligible',
    )
    invalid = [
        _waiter(connection, tenant_id=actor.tenant_id, location_id=location_id, prefix=prefix, label='no-grant', grant=False),
        _waiter(connection, tenant_id=actor.tenant_id, location_id=location_id, prefix=prefix, label='inactive-user', active_user=False),
        _waiter(connection, tenant_id=actor.tenant_id, location_id=location_id, prefix=prefix, label='inactive-member', active_membership=False),
        _waiter(connection, tenant_id=actor.tenant_id, location_id=location_id, prefix=prefix, label='no-capability', capabilities=('restaurant_service.manage',)),
    ]
    foreign = _seed_authority(connection, f'{prefix}-foreign', ())
    foreign_org = _organization(connection, foreign.tenant_id, 'FOREIGN')
    foreign_location = _location(connection, foreign.tenant_id, foreign_org, 'FOREIGN')
    foreign_waiter = _waiter(
        connection, tenant_id=foreign.tenant_id, location_id=foreign_location,
        prefix=f'{prefix}-foreign', label='waiter',
    )
    headers = _login(client, actor)
    listed = client.get(
        f'/locations/{location_id}/tables/eligible-waiters', headers=headers,
    )
    assert listed.status_code == 200
    assert [item['membership_id'] for item in listed.json()['items']] == [eligible]
    for waiter in [*invalid, foreign_waiter]:
        assert _assign(client, headers, location_id, table_id, waiter, 0).status_code == 409

    unauthorized_membership = _waiter(
        connection, tenant_id=actor.tenant_id, location_id=location_id,
        prefix=prefix, label='unauthorized', grant=False,
        capabilities=('resource.read',),
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT r.id,u.email FROM roles r JOIN membership_roles mr ON mr.role_id=r.id '
            'JOIN tenant_memberships tm ON tm.id=mr.membership_id '
            'JOIN users u ON u.id=tm.user_id WHERE tm.id=%s',
            (unauthorized_membership,),
        )
        unauthorized_row = cursor.fetchone()
    unauthorized = Authority(
        tenant_id=actor.tenant_id,
        role_id=int(unauthorized_row['id']),
        email=unauthorized_row['email'],
    )
    _grant_location(connection, unauthorized, location_id)
    unauthorized_headers = _login(client, unauthorized)
    assert _assign(
        client, unauthorized_headers, location_id, table_id, eligible, 0,
    ).status_code == 403
    no_grant_actor = _seed_authority(connection, f'{prefix}-no-location', ('resource.manage',))
    assert _assign(
        client, _login(client, no_grant_actor), location_id, table_id, eligible, 0,
    ).status_code == 404


def test_stale_concurrent_unassign_and_responsibility_change_preserves_invariants(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    actor, location_id, table_id, _ = _setup(connection, prefix)
    waiters = [
        _waiter(
            connection, tenant_id=actor.tenant_id, location_id=location_id,
            prefix=prefix, label=str(index),
        )
        for index in range(1, 4)
    ]
    headers = _login(client, actor)
    for version, waiter in enumerate(waiters):
        assert _assign(client, headers, location_id, table_id, waiter, version).status_code == 201

    with ThreadPoolExecutor(max_workers=2) as executor:
        unassign = executor.submit(
            _unassign, client, headers, location_id, table_id, waiters[0], 3,
            [waiters[1]],
        )
        responsibility = executor.submit(
            _responsible, client, headers, location_id, table_id, [waiters[2]], 3,
        )
        statuses = sorted([unassign.result().status_code, responsibility.result().status_code])
    assert statuses == [200, 409]
    final = client.get(
        f'{_base(location_id, table_id)}/waiter-assignments', headers=headers,
    ).json()
    assigned = {item['membership_id'] for item in final['assignments']}
    responsible = {
        item['membership_id'] for item in final['assignments'] if item['is_responsible']
    }
    assert assigned
    assert responsible
    assert responsible <= assigned
