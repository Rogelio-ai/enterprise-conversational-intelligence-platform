from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
import pymysql
import pytest

from app.main import create_app
from test_operational_message_center_persistence import (
    _insert_request,
    _membership,
    _prepared_scope,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _conversation_for_diner(connection, diner_session_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT conversation_id FROM diner_sessions WHERE id=%s',
            (diner_session_id,),
        )
        return int(cursor.fetchone()['conversation_id'])


def _participant(
    connection,
    *,
    tenant_id: int,
    conversation_id: int,
    participant_type: str,
    membership_id: int | None = None,
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO conversation_participants '
            '(tenant_id,conversation_id,participant_type,tenant_membership_id) '
            'VALUES (%s,%s,%s,%s)',
            (tenant_id, conversation_id, participant_type, membership_id),
        )
        return int(cursor.lastrowid)


def _next_sequence(connection, conversation_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COALESCE(MAX(sequence_number),0)+1 AS next_sequence '
            'FROM conversation_messages WHERE conversation_id=%s',
            (conversation_id,),
        )
        return int(cursor.fetchone()['next_sequence'])


def _message(
    connection,
    *,
    tenant_id: int,
    conversation_id: int,
    participant_id: int,
    operational_request_id: int | None = None,
    idempotency_key: str | None = None,
    fingerprint: str | None = None,
    content: str = 'Canonical response content',
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO conversation_messages (
                tenant_id,conversation_id,participant_id,sequence_number,
                modality,content_text,language,language_source,
                operational_request_id,response_idempotency_key,
                response_request_fingerprint
            ) VALUES (%s,%s,%s,%s,'TEXT',%s,'es-MX','DECLARED',%s,%s,%s)
            ''',
            (
                tenant_id,
                conversation_id,
                participant_id,
                _next_sequence(connection, conversation_id),
                content,
                operational_request_id,
                idempotency_key,
                fingerprint,
            ),
        )
        return int(cursor.lastrowid)


def _request_context(client, connection, prefix):
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
    return scope, _conversation_for_diner(connection, diner_session_id), request_id


def test_legacy_and_responder_messages_preserve_replay_identity_and_request_state(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, conversation_id, request_id = _request_context(client, connection, prefix)
    first_membership = _membership(connection, scope.tenant_id)
    second_membership = _membership(connection, scope.tenant_id)
    first_participant = _participant(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_type='HUMAN_STAFF',
        membership_id=first_membership,
    )
    second_participant = _participant(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_type='HUMAN_STAFF',
        membership_id=second_membership,
    )

    legacy_id = _message(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_id=first_participant,
        content='Legacy uncorrelated message',
    )
    fingerprint = uuid4().hex + uuid4().hex
    response_id = _message(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_id=first_participant,
        operational_request_id=request_id,
        idempotency_key='waiter-response-1',
        fingerprint=fingerprint,
    )

    with pytest.raises(pymysql.MySQLError):
        _message(
            connection,
            tenant_id=scope.tenant_id,
            conversation_id=conversation_id,
            participant_id=first_participant,
            operational_request_id=request_id,
            idempotency_key='waiter-response-1',
            fingerprint=fingerprint,
        )
    _message(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_id=first_participant,
        operational_request_id=request_id,
        idempotency_key='waiter-response-2',
        fingerprint=fingerprint,
    )
    _message(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_id=second_participant,
        operational_request_id=request_id,
        idempotency_key='waiter-response-1',
        fingerprint=fingerprint,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT operational_request_id,response_idempotency_key,'
            'response_request_fingerprint FROM conversation_messages WHERE id IN (%s,%s) '
            'ORDER BY id',
            (legacy_id, response_id),
        )
        assert cursor.fetchall() == [
            {
                'operational_request_id': None,
                'response_idempotency_key': None,
                'response_request_fingerprint': None,
            },
            {
                'operational_request_id': request_id,
                'response_idempotency_key': 'waiter-response-1',
                'response_request_fingerprint': fingerprint,
            },
        ]
        cursor.execute(
            'SELECT status,acknowledged_by_membership_id,acknowledged_at,'
            'resolved_by_membership_id,resolved_at '
            'FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        assert cursor.fetchone() == {
            'status': 'PENDING',
            'acknowledged_by_membership_id': None,
            'acknowledged_at': None,
            'resolved_by_membership_id': None,
            'resolved_at': None,
        }


@pytest.mark.parametrize(
    ('request_present', 'idempotency_key', 'fingerprint'),
    (
        (True, None, None),
        (False, 'partial-key', None),
        (False, None, 'f' * 64),
        (True, 'partial-key', None),
        (True, None, 'f' * 64),
    ),
)
def test_partial_responder_evidence_is_rejected(
    client,
    sql_connection,
    request_present,
    idempotency_key,
    fingerprint,
):
    connection, prefix = sql_connection
    scope, conversation_id, request_id = _request_context(client, connection, prefix)
    participant_id = _participant(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_type='HUMAN_STAFF',
        membership_id=_membership(connection, scope.tenant_id),
    )
    with pytest.raises(pymysql.MySQLError):
        _message(
            connection,
            tenant_id=scope.tenant_id,
            conversation_id=conversation_id,
            participant_id=participant_id,
            operational_request_id=request_id if request_present else None,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )


def test_cross_tenant_operational_request_correlation_is_rejected(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, conversation_id, _ = _request_context(client, connection, prefix)
    foreign_scope, _, foreign_request_id = _request_context(
        client, connection, f'{prefix}-foreign',
    )
    assert foreign_scope.tenant_id != scope.tenant_id
    participant_id = _participant(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_type='HUMAN_STAFF',
        membership_id=_membership(connection, scope.tenant_id),
    )
    with pytest.raises(pymysql.MySQLError):
        _message(
            connection,
            tenant_id=scope.tenant_id,
            conversation_id=conversation_id,
            participant_id=participant_id,
            operational_request_id=foreign_request_id,
            idempotency_key='cross-tenant-response',
            fingerprint='f' * 64,
        )


def test_staff_participant_identity_is_stable_without_collapsing_null_memberships(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, conversation_id, _ = _request_context(client, connection, prefix)
    membership_id = _membership(connection, scope.tenant_id)
    _participant(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=conversation_id,
        participant_type='HUMAN_STAFF',
        membership_id=membership_id,
    )
    with pytest.raises(pymysql.MySQLError):
        _participant(
            connection,
            tenant_id=scope.tenant_id,
            conversation_id=conversation_id,
            participant_type='HUMAN_STAFF',
            membership_id=membership_id,
        )

    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO conversations '
            '(tenant_id,organization_id,location_id,resource_id,channel,status,'
            'next_message_sequence) VALUES (%s,%s,%s,%s,%s,%s,1)',
            (
                scope.tenant_id,
                scope.organization_id,
                scope.location_id,
                scope.resource_id,
                'IN_PERSON_DIGITAL',
                'ACTIVE',
            ),
        )
        other_conversation_id = int(cursor.lastrowid)
    _participant(
        connection,
        tenant_id=scope.tenant_id,
        conversation_id=other_conversation_id,
        participant_type='HUMAN_STAFF',
        membership_id=membership_id,
    )
    for participant_type in ('SYSTEM', 'SYSTEM', 'DIGITAL_WAITER', 'DIGITAL_WAITER'):
        _participant(
            connection,
            tenant_id=scope.tenant_id,
            conversation_id=conversation_id,
            participant_type=participant_type,
        )
