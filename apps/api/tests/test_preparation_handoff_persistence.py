from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
import pymysql
import pytest

from app.core.security import hash_password
from app.main import create_app
from test_pos_order_submission_recovery import PASSWORD, _execute, _scope
from test_preparation_execution_foundation import _native_item


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _membership(connection, tenant_id: int) -> int:
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) '
        "VALUES (%s,%s,'Handoff actor','ACTIVE')",
        (f'{uuid4().hex}@example.test', hash_password(PASSWORD)),
    )
    return _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) '
        "VALUES (%s,%s,'ACTIVE')",
        (tenant_id, user_id),
    )


def _work(client, connection, prefix):
    scope = _scope(connection, prefix)
    _, _, _, work_id, _ = _native_item(client, connection, scope)
    return scope, work_id


def _evidence(connection, work_id: int) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT picked_up_by_membership_id,picked_up_at,'
            'delivered_by_membership_id,delivered_at '
            'FROM preparation_works WHERE id=%s',
            (work_id,),
        )
        return cursor.fetchone()


def test_legacy_null_evidence_and_same_tenant_handoff_actors_are_persistable(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, work_id = _work(client, connection, prefix)
    assert _evidence(connection, work_id) == {
        'picked_up_by_membership_id': None,
        'picked_up_at': None,
        'delivered_by_membership_id': None,
        'delivered_at': None,
    }

    pickup_actor = _membership(connection, scope.tenant_id)
    delivery_actor = _membership(connection, scope.tenant_id)
    picked_up_at = datetime(2026, 9, 18, 12, 0, 0)
    delivered_at = datetime(2026, 9, 18, 12, 5, 0)
    _execute(
        connection,
        'UPDATE preparation_works SET picked_up_by_membership_id=%s,picked_up_at=%s '
        'WHERE id=%s',
        (pickup_actor, picked_up_at, work_id),
    )
    _execute(
        connection,
        'UPDATE preparation_works SET delivered_by_membership_id=%s,delivered_at=%s '
        'WHERE id=%s',
        (delivery_actor, delivered_at, work_id),
    )

    assert pickup_actor != delivery_actor
    assert _evidence(connection, work_id) == {
        'picked_up_by_membership_id': pickup_actor,
        'picked_up_at': picked_up_at,
        'delivered_by_membership_id': delivery_actor,
        'delivered_at': delivered_at,
    }


@pytest.mark.parametrize(
    ('assignment', 'parameters'),
    [
        ('picked_up_by_membership_id=%s', 'actor'),
        ('picked_up_at=%s', 'time'),
    ],
)
def test_partial_pickup_evidence_is_rejected(
    client, sql_connection, assignment, parameters,
):
    connection, prefix = sql_connection
    scope, work_id = _work(client, connection, prefix)
    value = (
        _membership(connection, scope.tenant_id)
        if parameters == 'actor'
        else datetime(2026, 9, 18, 12, 0, 0)
    )
    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            f'UPDATE preparation_works SET {assignment} WHERE id=%s',
            (value, work_id),
        )
    assert _evidence(connection, work_id)['picked_up_by_membership_id'] is None
    assert _evidence(connection, work_id)['picked_up_at'] is None


@pytest.mark.parametrize(
    ('assignment', 'parameters'),
    [
        ('delivered_by_membership_id=%s', 'actor'),
        ('delivered_at=%s', 'time'),
    ],
)
def test_partial_delivery_evidence_is_rejected(
    client, sql_connection, assignment, parameters,
):
    connection, prefix = sql_connection
    scope, work_id = _work(client, connection, prefix)
    pickup_actor = _membership(connection, scope.tenant_id)
    _execute(
        connection,
        'UPDATE preparation_works SET picked_up_by_membership_id=%s,picked_up_at=%s '
        'WHERE id=%s',
        (pickup_actor, datetime(2026, 9, 18, 12, 0, 0), work_id),
    )
    value = (
        _membership(connection, scope.tenant_id)
        if parameters == 'actor'
        else datetime(2026, 9, 18, 12, 5, 0)
    )
    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            f'UPDATE preparation_works SET {assignment} WHERE id=%s',
            (value, work_id),
        )
    assert _evidence(connection, work_id)['delivered_by_membership_id'] is None
    assert _evidence(connection, work_id)['delivered_at'] is None


def test_delivery_without_pickup_is_rejected(client, sql_connection):
    connection, prefix = sql_connection
    scope, work_id = _work(client, connection, prefix)
    delivery_actor = _membership(connection, scope.tenant_id)
    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            'UPDATE preparation_works SET delivered_by_membership_id=%s,delivered_at=%s '
            'WHERE id=%s',
            (delivery_actor, datetime(2026, 9, 18, 12, 5, 0), work_id),
        )
    assert _evidence(connection, work_id)['delivered_by_membership_id'] is None


def test_cross_tenant_pickup_and_delivery_actors_are_rejected(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, work_id = _work(client, connection, prefix)
    foreign_scope = _scope(connection, f'{prefix}-foreign')
    foreign_actor = _membership(connection, foreign_scope.tenant_id)

    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            'UPDATE preparation_works SET picked_up_by_membership_id=%s,picked_up_at=%s '
            'WHERE id=%s',
            (foreign_actor, datetime(2026, 9, 18, 12, 0, 0), work_id),
        )

    pickup_actor = _membership(connection, scope.tenant_id)
    _execute(
        connection,
        'UPDATE preparation_works SET picked_up_by_membership_id=%s,picked_up_at=%s '
        'WHERE id=%s',
        (pickup_actor, datetime(2026, 9, 18, 12, 0, 0), work_id),
    )
    with pytest.raises(pymysql.MySQLError):
        _execute(
            connection,
            'UPDATE preparation_works SET delivered_by_membership_id=%s,delivered_at=%s '
            'WHERE id=%s',
            (foreign_actor, datetime(2026, 9, 18, 12, 5, 0), work_id),
        )
    evidence = _evidence(connection, work_id)
    assert evidence['picked_up_by_membership_id'] == pickup_actor
    assert evidence['delivered_by_membership_id'] is None
