from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_resource_foundation import (
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
from test_table_management import _profile, _section
from test_table_waiter_assignments import _membership_id, _waiter


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _authority_for_membership(connection, tenant_id, membership_id, email):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT role_id FROM membership_roles WHERE membership_id=%s ORDER BY id LIMIT 1',
            (membership_id,),
        )
        role_id = int(cursor.fetchone()['role_id'])
    return Authority(tenant_id=tenant_id, role_id=role_id, email=email)


def _prepare(connection, prefix):
    creator = _seed_authority(
        connection, prefix,
        ('internal_message.read', 'internal_message.send', 'internal_message.respond'),
    )
    organization_id = _organization(connection, creator.tenant_id, 'ORG')
    location_id = _location(connection, creator.tenant_id, organization_id, 'LOC')
    _grant_location(connection, creator, location_id)
    recipient_id = _waiter(
        connection, tenant_id=creator.tenant_id, location_id=location_id,
        prefix=prefix, label='recipient',
    )
    recipient = _authority_for_membership(
        connection, creator.tenant_id, recipient_id,
        f'{prefix}-recipient@example.test',
    )
    for permission in ('internal_message.read', 'internal_message.respond'):
        _assign_permission(connection, recipient.role_id, permission)
    stranger_id = _waiter(
        connection, tenant_id=creator.tenant_id, location_id=location_id,
        prefix=prefix, label='stranger',
    )
    stranger = _authority_for_membership(
        connection, creator.tenant_id, stranger_id,
        f'{prefix}-stranger@example.test',
    )
    for permission in ('internal_message.read', 'internal_message.respond'):
        _assign_permission(connection, stranger.role_id, permission)
    return creator, organization_id, location_id, recipient_id, recipient, stranger


def _create(client, headers, location_id, recipient_id, key='message-1', party_size=4):
    return client.post(
        f'/locations/{location_id}/internal-messages',
        headers={**headers, 'Idempotency-Key': key},
        json={
            'recipient_membership_id': recipient_id,
            'type': 'TABLE_PREPARATION_REQUEST',
            'text': 'Preparar mesa para familia',
            'party_size': party_size,
        },
    )


def test_pre_service_message_participant_visibility_enterado_responses_and_ready(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    creator, _, location_id, recipient_id, recipient, stranger = _prepare(
        connection, prefix,
    )
    creator_headers = _login(client, creator)
    recipient_headers = _login(client, recipient)
    stranger_headers = _login(client, stranger)

    created = _create(client, creator_headers, location_id, recipient_id)
    assert created.status_code == 201, created.text
    message_id = created.json()['id']
    assert created.json()['status'] == 'REQUESTED'
    assert created.json()['enterado'] is None
    assert created.json()['allowed_actions'] == ['RESPOND']
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM restaurant_service_sessions '
            'WHERE tenant_id=%s AND location_id=%s',
            (creator.tenant_id, location_id),
        )
        assert cursor.fetchone()['amount'] == 0

    sent = client.get(
        f'/locations/{location_id}/internal-messages/sent', headers=creator_headers,
    )
    inbox = client.get(
        f'/locations/{location_id}/internal-messages/inbox', headers=recipient_headers,
    )
    assert [item['id'] for item in sent.json()['items']] == [message_id]
    assert [item['id'] for item in inbox.json()['items']] == [message_id]
    assert client.get(
        f'/locations/{location_id}/internal-messages/{message_id}',
        headers=stranger_headers,
    ).status_code == 404
    assert client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/enterado',
        headers=creator_headers,
    ).status_code == 403
    assert client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/ready',
        headers=recipient_headers, json={},
    ).status_code == 409

    entered = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/enterado',
        headers=recipient_headers,
    )
    replayed_entered = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/enterado',
        headers=recipient_headers,
    )
    assert entered.status_code == replayed_entered.status_code == 200
    assert entered.json()['enterado'] == replayed_entered.json()['enterado']
    assert entered.json()['allowed_actions'] == ['RESPOND', 'READY']

    first = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/responses',
        headers={**recipient_headers, 'Idempotency-Key': 'recipient-response'},
        json={'content': 'La preparo ahora'},
    )
    replay = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/responses',
        headers={**recipient_headers, 'Idempotency-Key': 'recipient-response'},
        json={'content': 'La preparo ahora'},
    )
    second = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/responses',
        headers={**creator_headers, 'Idempotency-Key': 'creator-response'},
        json={'content': 'Gracias'},
    )
    assert first.status_code == replay.status_code == second.status_code == 201
    assert [item['sequence'] for item in second.json()['responses']] == [1, 2]
    assert client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/responses',
        headers={**recipient_headers, 'Idempotency-Key': 'recipient-response'},
        json={'content': 'Contenido distinto'},
    ).status_code == 409

    ready = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/ready',
        headers=recipient_headers, json={},
    )
    ready_replay = client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/ready',
        headers=recipient_headers, json={},
    )
    assert ready.status_code == ready_replay.status_code == 200
    assert ready.json()['status'] == 'READY'
    assert ready.json()['allowed_actions'] == []
    sender_detail = client.get(
        f'/locations/{location_id}/internal-messages/{message_id}',
        headers=creator_headers,
    ).json()
    assert sender_detail['enterado'] is not None
    assert sender_detail['ready'] is not None
    assert sender_detail['allowed_actions'] == ['RESPOND']
    assert [item['event_type'] for item in sender_detail['history']] == [
        'MESSAGE_CREATED', 'ENTERADO', 'RESPONSE_ADDED', 'RESPONSE_ADDED', 'READY',
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM restaurant_service_sessions '
            'WHERE tenant_id=%s AND location_id=%s',
            (creator.tenant_id, location_id),
        )
        assert cursor.fetchone()['amount'] == 0


def test_scope_waiter_eligibility_stale_recipient_and_create_replay(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    creator, organization_id, location_id, recipient_id, recipient, _ = _prepare(
        connection, prefix,
    )
    creator_headers = _login(client, creator)
    recipient_headers = _login(client, recipient)
    other_location = _location(
        connection, creator.tenant_id, organization_id, 'OTHER',
    )
    other_waiter = _waiter(
        connection, tenant_id=creator.tenant_id, location_id=other_location,
        prefix=prefix, label='other-location',
    )
    rejected = _create(
        client, creator_headers, location_id, other_waiter, key='wrong-scope',
    )
    assert rejected.status_code == 409
    assert _create(
        client, creator_headers, location_id, recipient_id,
        key='bad-party', party_size=0,
    ).status_code == 422

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: _create(
                client, creator_headers, location_id, recipient_id,
                key='concurrent-create',
            ),
            range(2),
        ))
    assert [item.status_code for item in results] == [201, 201]
    message_id = results[0].json()['id']
    assert results[1].json()['id'] == message_id
    assert _create(
        client, creator_headers, location_id, recipient_id,
        key='concurrent-create', party_size=5,
    ).status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM internal_operational_messages '
            'WHERE tenant_id=%s AND idempotency_key=%s',
            (creator.tenant_id, 'concurrent-create'),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            "UPDATE tenant_memberships SET status='INACTIVE' WHERE id=%s",
            (recipient_id,),
        )
    assert client.post(
        f'/locations/{location_id}/internal-messages/{message_id}/enterado',
        headers=recipient_headers,
    ).status_code == 403


def test_prepared_individual_and_active_group_representative_projection(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    creator, organization_id, location_id, recipient_id, recipient, _ = _prepare(
        connection, prefix,
    )
    creator_headers = _login(client, creator)
    recipient_headers = _login(client, recipient)
    first_table = _resource(
        connection, creator.tenant_id, location_id, 'TABLE-ONE', 'TABLE',
    )
    second_table = _resource(
        connection, creator.tenant_id, location_id, 'TABLE-TWO', 'TABLE',
    )
    section_id = _section(
        connection,
        type('Scope', (), {
            'actor': creator, 'organization_id': organization_id,
            'location_id': location_id,
        })(),
    )
    _profile(connection, type('Scope', (), {
        'actor': creator, 'organization_id': organization_id,
        'location_id': location_id,
    })(), first_table, section_id, 4)
    _profile(connection, type('Scope', (), {
        'actor': creator, 'organization_id': organization_id,
        'location_id': location_id,
    })(), second_table, section_id, 6)

    individual = _create(
        client, creator_headers, location_id, recipient_id, key='individual',
    ).json()['id']
    client.post(
        f'/locations/{location_id}/internal-messages/{individual}/enterado',
        headers=recipient_headers,
    )
    prepared = client.post(
        f'/locations/{location_id}/internal-messages/{individual}/ready',
        headers=recipient_headers,
        json={'prepared_table_resource_id': first_table},
    )
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()['prepared_table']['physical_capacity'] == 4
    assert prepared.json()['prepared_table']['is_group_representative'] is False

    group_id = _execute(
        connection,
        'INSERT INTO table_groups '
        '(tenant_id,organization_id,location_id,representative_resource_id,status,'
        'active_slot,version,created_by_membership_id) '
        "VALUES (%s,%s,%s,%s,'ACTIVE',1,1,%s)",
        (
            creator.tenant_id, organization_id, location_id, first_table,
            _membership_id(connection, creator),
        ),
    )
    for table_id, representative in ((first_table, True), (second_table, False)):
        _execute(
            connection,
            'INSERT INTO table_group_memberships '
            '(tenant_id,organization_id,location_id,table_group_id,table_resource_id,'
            'is_representative,active_slot) VALUES (%s,%s,%s,%s,%s,%s,1)',
            (
                creator.tenant_id, organization_id, location_id, group_id,
                table_id, representative,
            ),
        )
    grouped = _create(
        client, creator_headers, location_id, recipient_id, key='grouped',
    ).json()['id']
    client.post(
        f'/locations/{location_id}/internal-messages/{grouped}/enterado',
        headers=recipient_headers,
    )
    assert client.post(
        f'/locations/{location_id}/internal-messages/{grouped}/ready',
        headers=recipient_headers,
        json={'prepared_table_resource_id': second_table},
    ).status_code == 409
    grouped_ready = client.post(
        f'/locations/{location_id}/internal-messages/{grouped}/ready',
        headers=recipient_headers,
        json={'prepared_table_resource_id': first_table},
    )
    assert grouped_ready.status_code == 200, grouped_ready.text
    projection = grouped_ready.json()['prepared_table']
    assert projection['is_group_representative'] is True
    assert projection['group_id'] == group_id
    assert [item['resource_id'] for item in projection['members']] == [
        first_table, second_table,
    ]
    assert projection['derived_group_capacity'] == 10
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS amount FROM restaurant_service_sessions "
            "WHERE tenant_id=%s AND location_id=%s AND status='OPEN'",
            (creator.tenant_id, location_id),
        )
        assert cursor.fetchone()['amount'] == 0
