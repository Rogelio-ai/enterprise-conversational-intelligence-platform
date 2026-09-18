from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
import pymysql
import pytest

from app.core.security import hash_password
from app.main import create_app
from test_pos_order_submission_recovery import PASSWORD, _execute, _headers, _scope
from test_preparation_execution_foundation import _native_item
from test_staff_operational_requests import _enable_staff, _session_scope, _settled_check


DINER_TYPES = (
    'HUMAN_ASSISTANCE',
    'CASH_PAYMENT_ASSISTANCE',
    'INVOICE_ASSISTANCE',
    'PAID_CHECK_PRINT',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _membership(connection, tenant_id: int) -> int:
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) '
        "VALUES (%s,%s,'Message Center waiter','ACTIVE')",
        (f'{uuid4().hex}@example.test', hash_password(PASSWORD)),
    )
    return _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) '
        "VALUES (%s,%s,'ACTIVE')",
        (tenant_id, user_id),
    )


def _insert_request(
    connection,
    scope,
    *,
    service_session_id: int,
    request_type: str,
    diner_session_id: int | None,
    check_id: int | None = None,
    preparation_work_id: int | None = None,
    status: str = 'PENDING',
    acknowledged_by_membership_id: int | None = None,
    acknowledged_at: datetime | None = None,
) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO diner_operational_requests (
            tenant_id,organization_id,location_id,resource_id,service_session_id,
            diner_session_id,request_type,status,related_restaurant_check_id,
            preparation_work_id,acknowledged_by_membership_id,acknowledged_at,
            idempotency_key,request_fingerprint
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            preparation_work_id,
            acknowledged_by_membership_id,
            acknowledged_at,
            f'message-center-{uuid4().hex}',
            uuid4().hex + uuid4().hex,
        ),
    )


def _prepared_scope(client, connection, prefix):
    scope = _scope(connection, prefix)
    _, _, _, work_id, _ = _native_item(client, connection, scope)
    service_session_id, diner_session_id = _session_scope(connection, scope)
    return scope, service_session_id, diner_session_id, work_id


def test_existing_diner_shapes_and_unknown_acknowledgement_evidence_remain_valid(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, service_session_id, diner_session_id, _ = _prepared_scope(
        client, connection, prefix,
    )
    check_id = _settled_check(connection, scope, diner_session_id)
    request_ids = [
        _insert_request(
            connection,
            scope,
            service_session_id=service_session_id,
            request_type=request_type,
            diner_session_id=diner_session_id,
            check_id=None if request_type == 'HUMAN_ASSISTANCE' else check_id,
            status='ACKNOWLEDGED',
        )
        for request_type in DINER_TYPES
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT request_type,acknowledged_by_membership_id,acknowledged_at '
            'FROM diner_operational_requests WHERE id IN (%s,%s,%s,%s)',
            tuple(request_ids),
        )
        rows = cursor.fetchall()
    assert {row['request_type'] for row in rows} == set(DINER_TYPES)
    assert all(row['acknowledged_by_membership_id'] is None for row in rows)
    assert all(row['acknowledged_at'] is None for row in rows)


@pytest.mark.parametrize('request_type', DINER_TYPES)
def test_diner_request_types_require_diner_and_exclude_preparation_work(
    client, sql_connection, request_type,
):
    connection, prefix = sql_connection
    scope, service_session_id, diner_session_id, work_id = _prepared_scope(
        client, connection, prefix,
    )
    check_id = _settled_check(connection, scope, diner_session_id)
    related_check = None if request_type == 'HUMAN_ASSISTANCE' else check_id
    with pytest.raises(pymysql.MySQLError):
        _insert_request(
            connection,
            scope,
            service_session_id=service_session_id,
            request_type=request_type,
            diner_session_id=None,
            check_id=related_check,
        )
    with pytest.raises(pymysql.MySQLError):
        _insert_request(
            connection,
            scope,
            service_session_id=service_session_id,
            request_type=request_type,
            diner_session_id=diner_session_id,
            check_id=related_check,
            preparation_work_id=work_id,
        )


def test_preparation_ready_shape_uniqueness_and_staff_projection(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, service_session_id, diner_session_id, work_id = _prepared_scope(
        client, connection, prefix,
    )
    request_id = _insert_request(
        connection,
        scope,
        service_session_id=service_session_id,
        request_type='PREPARATION_READY',
        diner_session_id=None,
        preparation_work_id=work_id,
    )
    with pytest.raises(pymysql.MySQLError):
        _insert_request(
            connection,
            scope,
            service_session_id=service_session_id,
            request_type='PREPARATION_READY',
            diner_session_id=None,
            preparation_work_id=work_id,
        )

    _enable_staff(connection, scope, permissions=('operational_request.read',))
    response = client.get(
        f'/staff/operational-requests/{request_id}?location_id={scope.location_id}',
        headers=_headers(client, scope),
    )
    assert response.status_code == 200, response.text
    assert response.json()['diner_session_id'] is None
    assert response.json()['diner_display_name'] is None
    assert response.json()['preparation_work_id'] == work_id
    assert response.json()['acknowledged_by_membership_id'] is None
    assert response.json()['acknowledged_at'] is None

    check_id = _settled_check(connection, scope, diner_session_id)
    for diner_value, work_value, check_value in (
        (diner_session_id, work_id, None),
        (None, None, None),
        (None, work_id, check_id),
    ):
        with pytest.raises(pymysql.MySQLError):
            _insert_request(
                connection,
                scope,
                service_session_id=service_session_id,
                request_type='PREPARATION_READY',
                diner_session_id=diner_value,
                preparation_work_id=work_value,
                check_id=check_value,
            )


def test_cross_tenant_preparation_work_is_rejected(client, sql_connection):
    connection, prefix = sql_connection
    scope, service_session_id, _, _ = _prepared_scope(client, connection, prefix)
    foreign_scope, _, _, foreign_work_id = _prepared_scope(
        client, connection, f'{prefix}-foreign',
    )
    assert foreign_scope.tenant_id != scope.tenant_id
    with pytest.raises(pymysql.MySQLError):
        _insert_request(
            connection,
            scope,
            service_session_id=service_session_id,
            request_type='PREPARATION_READY',
            diner_session_id=None,
            preparation_work_id=foreign_work_id,
        )


def test_acknowledgement_pair_and_tenant_scope_are_enforced(client, sql_connection):
    connection, prefix = sql_connection
    scope, service_session_id, diner_session_id, _ = _prepared_scope(
        client, connection, prefix,
    )
    actor = _membership(connection, scope.tenant_id)
    acknowledged_at = datetime(2026, 9, 18, 14, 0, 0)
    request_id = _insert_request(
        connection,
        scope,
        service_session_id=service_session_id,
        request_type='HUMAN_ASSISTANCE',
        diner_session_id=diner_session_id,
        status='ACKNOWLEDGED',
        acknowledged_by_membership_id=actor,
        acknowledged_at=acknowledged_at,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT acknowledged_by_membership_id,acknowledged_at '
            'FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        assert cursor.fetchone() == {
            'acknowledged_by_membership_id': actor,
            'acknowledged_at': acknowledged_at,
        }

    for actor_value, time_value in ((actor, None), (None, acknowledged_at)):
        with pytest.raises(pymysql.MySQLError):
            _insert_request(
                connection,
                scope,
                service_session_id=service_session_id,
                request_type='HUMAN_ASSISTANCE',
                diner_session_id=diner_session_id,
                status='ACKNOWLEDGED',
                acknowledged_by_membership_id=actor_value,
                acknowledged_at=time_value,
            )

    foreign_scope = _scope(connection, f'{prefix}-actor-foreign')
    foreign_actor = _membership(connection, foreign_scope.tenant_id)
    with pytest.raises(pymysql.MySQLError):
        _insert_request(
            connection,
            scope,
            service_session_id=service_session_id,
            request_type='HUMAN_ASSISTANCE',
            diner_session_id=diner_session_id,
            status='ACKNOWLEDGED',
            acknowledged_by_membership_id=foreign_actor,
            acknowledged_at=acknowledged_at,
        )


def test_per_waiter_entered_and_hidden_shapes_are_independent_and_tenant_scoped(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, service_session_id, diner_session_id, _ = _prepared_scope(
        client, connection, prefix,
    )
    request_id = _insert_request(
        connection,
        scope,
        service_session_id=service_session_id,
        request_type='HUMAN_ASSISTANCE',
        diner_session_id=diner_session_id,
    )
    entered_at = datetime(2026, 9, 18, 14, 0, 0)
    hidden_at = datetime(2026, 9, 18, 14, 5, 0)
    waiters = tuple(_membership(connection, scope.tenant_id) for _ in range(4))
    shapes = (
        (None, None),
        (entered_at, None),
        (None, hidden_at),
        (entered_at, hidden_at),
    )
    for waiter_id, (entered_value, hidden_value) in zip(waiters, shapes, strict=True):
        _execute(
            connection,
            'INSERT INTO operational_request_waiter_states '
            '(tenant_id,operational_request_id,waiter_membership_id,entered_at,hidden_at) '
            'VALUES (%s,%s,%s,%s,%s)',
            (scope.tenant_id, request_id, waiter_id, entered_value, hidden_value),
        )

    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            'INSERT INTO operational_request_waiter_states '
            '(tenant_id,operational_request_id,waiter_membership_id) '
            'VALUES (%s,%s,%s)',
            (scope.tenant_id, request_id, waiters[0]),
        )

    foreign_scope = _scope(connection, f'{prefix}-waiter-foreign')
    foreign_waiter = _membership(connection, foreign_scope.tenant_id)
    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            'INSERT INTO operational_request_waiter_states '
            '(tenant_id,operational_request_id,waiter_membership_id) '
            'VALUES (%s,%s,%s)',
            (scope.tenant_id, request_id, foreign_waiter),
        )

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT waiter_membership_id,entered_at,hidden_at '
            'FROM operational_request_waiter_states WHERE operational_request_id=%s '
            'ORDER BY id',
            (request_id,),
        )
        assert cursor.fetchall() == [
            {
                'waiter_membership_id': waiter_id,
                'entered_at': entered_value,
                'hidden_at': hidden_value,
            }
            for waiter_id, (entered_value, hidden_value) in zip(
                waiters, shapes, strict=True,
            )
        ]
