from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import create_app
from test_canonical_order_commercial_acceptance import (
    PASSWORD,
    _execute,
    _open_and_join,
    _scope,
    _staff_headers,
)


def _enable_staff(
    connection,
    scope,
    *,
    permissions: tuple[str, ...] = (
        'operational_request.read',
        'operational_request.manage',
    ),
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT TM.id AS membership_id, MR.role_id '
            'FROM tenant_memberships AS TM '
            'JOIN membership_roles AS MR ON MR.membership_id=TM.id '
            'WHERE TM.tenant_id=%s',
            (scope.tenant_id,),
        )
        authority = cursor.fetchone()
    membership_id = int(authority['membership_id'])
    _execute(
        connection,
        'INSERT INTO membership_location_grants (tenant_id,membership_id,location_id) '
        'VALUES (%s,%s,%s)',
        (scope.tenant_id, membership_id, scope.location_id),
    )
    for code in permissions:
        _execute(
            connection,
            'INSERT IGNORE INTO permissions (code,description) VALUES (%s,%s)',
            (code, f'Permission {code}'),
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
            (authority['role_id'], permission_id),
        )
    return membership_id


def _session_scope(connection, scope) -> tuple[int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT RSS.id AS service_session_id, DS.id AS diner_session_id '
            'FROM restaurant_service_sessions AS RSS '
            'JOIN diner_sessions AS DS ON DS.service_session_id=RSS.id '
            'WHERE RSS.tenant_id=%s AND RSS.location_id=%s ORDER BY DS.id DESC LIMIT 1',
            (scope.tenant_id, scope.location_id),
        )
        row = cursor.fetchone()
    return int(row['service_session_id']), int(row['diner_session_id'])


def _settled_check(connection, scope, diner_session_id: int) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO restaurant_checks (
            tenant_id,organization_id,location_id,currency,status,version,
            current_fingerprint,fingerprint_schema_version,consumption_total,
            gratuity_total,liability_total,controller_actor_type,controller_actor_id,
            controller_diner_session_id,created_actor_type,created_actor_id,
            frozen_at,settled_at,continuation_decision
        ) VALUES (
            %s,%s,%s,'MXN','SETTLED',1,%s,1,0,0,0,'DINER',%s,%s,'DINER',%s,
            CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'PENDING'
        )
        ''',
        (
            scope.tenant_id,
            scope.organization_id,
            scope.location_id,
            uuid4().hex + uuid4().hex,
            diner_session_id,
            diner_session_id,
            diner_session_id,
        ),
    )


def _request(
    connection,
    scope,
    *,
    request_type: str,
    service_session_id: int,
    diner_session_id: int,
    check_id: int | None = None,
    status: str = 'PENDING',
    resolver_membership_id: int | None = None,
) -> int:
    terminal = status in {'COMPLETED', 'CANCELLED'}
    return _execute(
        connection,
        '''
        INSERT INTO diner_operational_requests (
            tenant_id,organization_id,location_id,resource_id,service_session_id,
            diner_session_id,request_type,status,related_restaurant_check_id,
            idempotency_key,request_fingerprint,resolved_by_membership_id,resolved_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                  CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END)
        ''',
        (
            scope.tenant_id,
            scope.organization_id,
            scope.location_id,
            scope.resource_id,
            service_session_id,
            diner_session_id,
            request_type,
            status,
            check_id,
            f'staff-test-{uuid4().hex}',
            uuid4().hex + uuid4().hex,
            resolver_membership_id if terminal else None,
            terminal,
        ),
    )


def _second_staff(
    connection,
    scope,
    prefix: str,
    *,
    label: str,
    permissions: tuple[str, ...] = (),
) -> dict[str, str]:
    email = f'{prefix}-{label}@example.test'
    user_id = _execute(
        connection,
        "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Staff','ACTIVE')",
        (email, hash_password(PASSWORD)),
    )
    membership_id = _execute(
        connection,
        "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')",
        (scope.tenant_id, user_id),
    )
    role_id = _execute(
        connection,
        "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Role','ACTIVE')",
        (scope.tenant_id, f'NO_PERMISSION_{uuid4().hex}'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (scope.tenant_id, membership_id, role_id),
    )
    _execute(
        connection,
        'INSERT INTO membership_location_grants (tenant_id,membership_id,location_id) '
        'VALUES (%s,%s,%s)',
        (scope.tenant_id, membership_id, scope.location_id),
    )
    for code in permissions:
        _execute(
            connection,
            'INSERT IGNORE INTO permissions (code,description) VALUES (%s,%s)',
            (code, f'Permission {code}'),
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
            (role_id, permission_id),
        )
    return {'email': email, 'membership_id': membership_id}


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': email, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def test_diner_request_is_the_same_staff_listed_read_and_completed_object(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    membership_id = _enable_staff(connection, scope)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, diner_headers = _open_and_join(client, scope, name='Safe Diner Name')
        created = client.post(
            '/diner/operational-requests',
            headers={**diner_headers, 'Idempotency-Key': 'staff-interoperability'},
            json={'request_type': 'HUMAN_ASSISTANCE'},
        )
        assert created.status_code == 201, created.text
        request_id = created.json()['id']
        staff_headers = _staff_headers(client, scope)
        path = f'/staff/operational-requests?location_id={scope.location_id}'

        listing = client.get(path, headers=staff_headers)
        detail = client.get(
            f'/staff/operational-requests/{request_id}?location_id={scope.location_id}',
            headers=staff_headers,
        )
        acknowledged = client.post(
            f'/staff/operational-requests/{request_id}/acknowledge?location_id={scope.location_id}',
            headers=staff_headers,
        )
        completed = client.post(
            f'/staff/operational-requests/{request_id}/complete?location_id={scope.location_id}',
            headers=staff_headers,
        )

    assert listing.status_code == 200
    assert [item['id'] for item in listing.json()['items']] == [request_id]
    assert detail.status_code == 200
    assert detail.json()['diner_display_name'] == 'Safe Diner Name'
    assert 'idempotency_key' not in detail.json()
    assert 'request_fingerprint' not in detail.json()
    assert acknowledged.json()['status'] == 'ACKNOWLEDGED'
    assert acknowledged.json()['resolved_at'] is None
    assert completed.json()['status'] == 'COMPLETED'
    assert completed.json()['resolved_by_membership_id'] == membership_id
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count,status FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        row = cursor.fetchone()
    assert row == {'count': 1, 'status': 'COMPLETED'}


def test_staff_filters_permissions_and_location_authority_are_enforced(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _enable_staff(connection, scope)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, diner_headers = _open_and_join(client, scope)
        service_session_id, diner_session_id = _session_scope(connection, scope)
        check_id = _settled_check(connection, scope, diner_session_id)
        pending_id = _request(
            connection,
            scope,
            request_type='HUMAN_ASSISTANCE',
            service_session_id=service_session_id,
            diner_session_id=diner_session_id,
        )
        cash_id = _request(
            connection,
            scope,
            request_type='CASH_PAYMENT_ASSISTANCE',
            service_session_id=service_session_id,
            diner_session_id=diner_session_id,
            check_id=check_id,
        )
        staff_headers = _staff_headers(client, scope)
        base = f'/staff/operational-requests?location_id={scope.location_id}'

        assert client.get(base).status_code == 401
        assert client.post(
            f'/staff/operational-requests/{pending_id}/acknowledge'
            f'?location_id={scope.location_id}',
            headers=staff_headers,
        ).status_code == 200
        status_filtered = client.get(f'{base}&status=PENDING', headers=staff_headers)
        type_filtered = client.get(
            f'{base}&request_type=CASH_PAYMENT_ASSISTANCE', headers=staff_headers
        )
        assert [item['id'] for item in status_filtered.json()['items']] == [cash_id]
        assert [item['id'] for item in type_filtered.json()['items']] == [cash_id]

        read_only = _second_staff(
            connection,
            scope,
            prefix,
            label='read-only',
            permissions=('operational_request.read',),
        )
        read_only_headers = _login(client, read_only['email'])
        assert client.get(base, headers=read_only_headers).status_code == 200
        assert client.post(
            f'/staff/operational-requests/{cash_id}/acknowledge'
            f'?location_id={scope.location_id}',
            headers=read_only_headers,
        ).status_code == 403

        no_permission = _second_staff(
            connection, scope, prefix, label='no-permission'
        )
        no_permission_headers = _login(client, no_permission['email'])
        assert client.get(base, headers=no_permission_headers).status_code == 403
        assert client.post(
            f'/staff/operational-requests/{pending_id}/acknowledge'
            f'?location_id={scope.location_id}',
            headers=no_permission_headers,
        ).status_code == 403

        ungranted_location_id = _execute(
            connection,
            "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
            "VALUES (%s,%s,%s,'Ungrant','America/Mexico_City','ACTIVE')",
            (scope.tenant_id, scope.organization_id, f'UNGRANT-{uuid4().hex[:8]}'),
        )
        assert client.get(
            f'/staff/operational-requests?location_id={ungranted_location_id}',
            headers={**staff_headers, 'X-Location-ID': str(ungranted_location_id)},
        ).status_code == 404
        assert client.post(
            f'/staff/operational-requests/{pending_id}/acknowledge'
            f'?location_id={ungranted_location_id}',
            headers=staff_headers,
        ).status_code == 404

        foreign = _scope(connection, f'{prefix}-foreign')
        _enable_staff(connection, foreign)
        _, foreign_diner_headers = _open_and_join(client, foreign)
        foreign_created = client.post(
            '/diner/operational-requests',
            headers={**foreign_diner_headers, 'Idempotency-Key': 'foreign-request'},
            json={'request_type': 'HUMAN_ASSISTANCE'},
        )
        assert foreign_created.status_code == 201
        foreign_id = foreign_created.json()['id']
        foreign_staff_headers = _staff_headers(client, foreign)
        assert client.get(
            f'/staff/operational-requests?location_id={foreign.location_id}',
            headers=staff_headers,
        ).status_code == 404
        assert client.get(
            f'/staff/operational-requests/{foreign_id}?location_id={scope.location_id}',
            headers=staff_headers,
        ).status_code == 404
        assert client.post(
            f'/staff/operational-requests/{pending_id}/complete'
            f'?location_id={foreign.location_id}',
            headers=foreign_staff_headers,
        ).status_code == 404


def test_staff_transitions_are_locked_idempotent_and_terminal(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    membership_id = _enable_staff(connection, scope)
    with TestClient(create_app(settings=integration_settings)) as client:
        _open_and_join(client, scope)
        service_session_id, diner_session_id = _session_scope(connection, scope)
        request_id = _request(
            connection,
            scope,
            request_type='HUMAN_ASSISTANCE',
            service_session_id=service_session_id,
            diner_session_id=diner_session_id,
        )
        headers = _staff_headers(client, scope)
        acknowledge_url = (
            f'/staff/operational-requests/{request_id}/acknowledge'
            f'?location_id={scope.location_id}'
        )
        complete_url = (
            f'/staff/operational-requests/{request_id}/complete'
            f'?location_id={scope.location_id}'
        )

        assert client.post(complete_url, headers=headers).status_code == 409
        with ThreadPoolExecutor(max_workers=2) as pool:
            acknowledgements = list(pool.map(lambda _: client.post(
                acknowledge_url, headers=headers
            ), range(2)))
        assert [response.status_code for response in acknowledgements] == [200, 200]
        assert {response.json()['status'] for response in acknowledgements} == {'ACKNOWLEDGED'}

        with ThreadPoolExecutor(max_workers=2) as pool:
            completions = list(pool.map(lambda _: client.post(
                complete_url, headers=headers
            ), range(2)))
        assert [response.status_code for response in completions] == [200, 200]
        assert {response.json()['status'] for response in completions} == {'COMPLETED'}
        assert client.post(acknowledge_url, headers=headers).status_code == 409
        assert client.post(complete_url, headers=headers).status_code == 200

        cancelled_id = _request(
            connection,
            scope,
            request_type='HUMAN_ASSISTANCE',
            service_session_id=service_session_id,
            diner_session_id=diner_session_id,
            status='CANCELLED',
            resolver_membership_id=membership_id,
        )
        assert client.post(
            f'/staff/operational-requests/{cancelled_id}/acknowledge'
            f'?location_id={scope.location_id}',
            headers=headers,
        ).status_code == 409
        assert client.post(
            f'/staff/operational-requests/{cancelled_id}/complete'
            f'?location_id={scope.location_id}',
            headers=headers,
        ).status_code == 409


def test_all_request_types_transition_without_fabricating_domain_results(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _enable_staff(connection, scope)
    with TestClient(create_app(settings=integration_settings)) as client:
        _open_and_join(client, scope)
        service_session_id, diner_session_id = _session_scope(connection, scope)
        check_id = _settled_check(connection, scope, diner_session_id)
        headers = _staff_headers(client, scope)
        request_ids = [
            _request(
                connection,
                scope,
                request_type=request_type,
                service_session_id=service_session_id,
                diner_session_id=diner_session_id,
                check_id=None if request_type == 'HUMAN_ASSISTANCE' else check_id,
            )
            for request_type in (
                'HUMAN_ASSISTANCE',
                'CASH_PAYMENT_ASSISTANCE',
                'INVOICE_ASSISTANCE',
                'PAID_CHECK_PRINT',
            )
        ]
        for request_id in request_ids:
            base = f'/staff/operational-requests/{request_id}'
            assert client.post(
                f'{base}/acknowledge?location_id={scope.location_id}', headers=headers
            ).status_code == 200
            assert client.post(
                f'{base}/complete?location_id={scope.location_id}', headers=headers
            ).status_code == 200

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_sessions WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_issuances WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_fiscal_results WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM paid_check_dispatches WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT request_type,status FROM diner_operational_requests '
            'WHERE id IN (%s,%s,%s,%s) ORDER BY id',
            tuple(request_ids),
        )
        rows = cursor.fetchall()
        assert {row['request_type'] for row in rows} == {
            'HUMAN_ASSISTANCE',
            'CASH_PAYMENT_ASSISTANCE',
            'INVOICE_ASSISTANCE',
            'PAID_CHECK_PRINT',
        }
        assert {row['status'] for row in rows} == {'COMPLETED'}
