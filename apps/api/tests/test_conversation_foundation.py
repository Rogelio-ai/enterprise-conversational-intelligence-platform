from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.models import ConversationMessage
from app.restaurant.conversations.service import append_message

PASSWORD = 'Test Password 123!'
PERMISSIONS = ('conversation.read', 'conversation.manage')


def _execute(connection, sql, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters)
        return int(cursor.lastrowid)


def _permission(connection, role_id, code):
    _execute(connection, 'INSERT IGNORE INTO permissions (code, description) VALUES (%s, %s)', (code, code))
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
        permission_id = int(cursor.fetchone()['id'])
    _execute(connection, 'INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s,%s)', (role_id, permission_id))


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    user_id: int
    membership_id: int
    role_id: int
    email: str
    organization_id: int
    location_id: int
    resource_id: int
    customer_ids: tuple[int, int]


def _scope(connection, prefix, permissions=PERMISSIONS):
    tenant_id = _execute(connection, "INSERT INTO tenants (name,slug,status) VALUES (%s,%s,'ACTIVE')", ('Conversation Tenant', prefix))
    email = f'{prefix}@example.test'
    user_id = _execute(connection, "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Conversation User','ACTIVE')", (email, hash_password(PASSWORD)))
    membership_id = _execute(connection, "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')", (tenant_id, user_id))
    role_id = _execute(connection, "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,'WS10_TEST','test','ACTIVE')", (tenant_id,))
    _execute(connection, 'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)', (tenant_id, membership_id, role_id))
    for permission in permissions:
        _permission(connection, role_id, permission)
    organization_id = _execute(connection, "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'ORG','Org','ACTIVE')", (tenant_id,))
    location_id = _execute(connection, "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC','Location','UTC','ACTIVE')", (tenant_id, organization_id))
    resource_id = _execute(connection, "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) VALUES (%s,%s,'TABLE-1','Table 1','TABLE','ACTIVE')", (tenant_id, location_id))
    customers = tuple(
        _execute(connection, "INSERT INTO customers (tenant_id,display_name,status,source) VALUES (%s,%s,'ACTIVE','PLATFORM')", (tenant_id, name))
        for name in ('Customer A', 'Customer B')
    )
    return Scope(tenant_id, user_id, membership_id, role_id, email, organization_id, location_id, resource_id, customers)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _headers(client, scope):
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _conversation(client, scope, headers, **updates):
    payload = {'organization_id': scope.organization_id, 'channel': 'IN_PERSON_DIGITAL'}
    payload.update(updates)
    response = client.post('/conversations', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _participant(client, conversation_id, headers, participant_type='CUSTOMER', **updates):
    payload = {'participant_type': participant_type}
    payload.update(updates)
    response = client.post(f'/conversations/{conversation_id}/participants', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_conversation_permissions_and_immutable_contract(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, permissions=())
    headers = _headers(client, scope)
    assert client.get('/conversations').status_code == 401
    assert client.get('/conversations', headers=headers).status_code == 403
    _permission(connection, scope.role_id, 'conversation.read')
    assert client.get('/conversations', headers=headers).status_code == 200
    assert client.post('/conversations', headers=headers, json={}).status_code == 403
    _permission(connection, scope.role_id, 'conversation.manage')
    conversation = _conversation(client, scope, headers)
    assert conversation['tenant_id'] == scope.tenant_id
    assert conversation['status'] == 'ACTIVE'
    assert client.patch(f"/conversations/{conversation['id']}", headers=headers, json={'channel': 'PHONE'}).status_code == 422
    assert client.delete(f"/conversations/{conversation['id']}", headers=headers).status_code == 405


def test_digital_waiter_voice_scenario_and_multilingual_preservation(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers, location_id=scope.location_id, resource_id=scope.resource_id, default_language='es-MX')
    customer = _participant(client, conversation['id'], headers, preferred_language='fr-FR')
    waiter = _participant(client, conversation['id'], headers, 'DIGITAL_WAITER')
    contents = (
        ('VOICE', 'Souhaitez-vous autre chose ?', 'fr-FR', 'DETECTED', customer['id']),
        ('TEXT', '¿Desea agregar algo más?', 'es-MX', 'DECLARED', waiter['id']),
        ('TOUCH', '您还需要别的吗？ 🍽️☕🥐', 'zh-CN', 'INHERITED', customer['id']),
        ('TEXT', 'Would you like anything else?', 'en-US', 'DECLARED', waiter['id']),
    )
    for expected_sequence, (modality, content, language, source, participant_id) in enumerate(contents, 1):
        response = client.post(f"/conversations/{conversation['id']}/messages", headers=headers, json={'participant_id': participant_id, 'modality': modality, 'content_text': content, 'language': language, 'language_source': source})
        assert response.status_code == 201, response.text
        assert response.json()['content_text'] == content
        assert response.json()['sequence_number'] == expected_sequence
    listed = client.get(f"/conversations/{conversation['id']}/messages", headers=headers).json()['items']
    assert [item['content_text'] for item in listed] == [item[1] for item in contents]
    assert [item['language'] for item in listed] == [item[2] for item in contents]
    detail = client.get(f"/conversations/{conversation['id']}", headers=headers).json()
    assert [item['participant_type'] for item in detail['participants']] == ['CUSTOMER', 'DIGITAL_WAITER']


@pytest.mark.parametrize(('channel', 'modality'), [('PHONE', 'VOICE'), ('WHATSAPP', 'TEXT')])
def test_remote_channels_share_canonical_schema_without_location(client, sql_connection, channel, modality):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers, channel=channel)
    customer = _participant(client, conversation['id'], headers)
    response = client.post(f"/conversations/{conversation['id']}/messages", headers=headers, json={'participant_id': customer['id'], 'modality': modality, 'content_text': 'Original semantic content'})
    assert response.status_code == 201, response.text
    assert conversation['location_id'] is None and conversation['resource_id'] is None


def test_multiple_customers_explicit_linking_and_human_staff(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers)
    anonymous = _participant(client, conversation['id'], headers, preferred_language='es-MX')
    linked = _participant(client, conversation['id'], headers, customer_id=scope.customer_ids[1], preferred_language='en-US')
    response = client.patch(f"/conversations/{conversation['id']}/participants/{anonymous['id']}", headers=headers, json={'customer_id': scope.customer_ids[0], 'preferred_language': 'fr-FR'})
    assert response.status_code == 200 and response.json()['customer_id'] == scope.customer_ids[0]
    assert client.patch(f"/conversations/{conversation['id']}/participants/{anonymous['id']}", headers=headers, json={'customer_id': scope.customer_ids[1]}).status_code == 409
    assert client.post(f"/conversations/{conversation['id']}/participants", headers=headers, json={'participant_type': 'CUSTOMER', 'customer_id': linked['customer_id']}).status_code == 409
    staff = _participant(client, conversation['id'], headers, 'HUMAN_STAFF', tenant_membership_id=scope.membership_id)
    system = _participant(client, conversation['id'], headers, 'SYSTEM')
    assert staff['tenant_membership_id'] == scope.membership_id and system['participant_type'] == 'SYSTEM'
    other = _scope(connection, f'{prefix}-other')
    assert client.post(f"/conversations/{conversation['id']}/participants", headers=headers, json={'participant_type': 'CUSTOMER', 'customer_id': other.customer_ids[0]}).status_code == 404
    assert client.post(f"/conversations/{conversation['id']}/participants", headers=headers, json={'participant_type': 'HUMAN_STAFF', 'tenant_membership_id': other.membership_id}).status_code == 404


@pytest.mark.parametrize('payload', [
    {'participant_type': 'CUSTOMER', 'tenant_membership_id': 1},
    {'participant_type': 'HUMAN_STAFF'},
    {'participant_type': 'DIGITAL_WAITER', 'customer_id': 1},
    {'participant_type': 'SYSTEM', 'tenant_membership_id': 1},
])
def test_invalid_participant_reference_combinations(client, sql_connection, payload):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers)
    assert client.post(f"/conversations/{conversation['id']}/participants", headers=headers, json=payload).status_code == 422


@pytest.mark.parametrize('tag', ['es', 'es-MX', 'en-US', 'fr-FR', 'zh-CN'])
def test_valid_language_tags_are_preserved(client, sql_connection, tag):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers, default_language=tag)
    assert conversation['default_language'] == tag


@pytest.mark.parametrize('tag', ['', '-es', 'es-', 'es--MX', 'abcdefghi', 'és-MX', 'a-' + ('b' * 62)])
def test_invalid_language_tags_are_rejected(client, sql_connection, tag):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    response = client.post('/conversations', headers=headers, json={'organization_id': scope.organization_id, 'channel': 'PHONE', 'default_language': tag})
    assert response.status_code == 422


def test_message_validation_language_pair_and_append_only_routes(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers)
    participant = _participant(client, conversation['id'], headers)
    endpoint = f"/conversations/{conversation['id']}/messages"
    base = {'participant_id': participant['id'], 'modality': 'TEXT'}
    for payload in ({**base, 'content_text': '   '}, {**base, 'content_text': 'x' * 10_001}, {**base, 'content_text': 'hi', 'language': 'en'}, {**base, 'content_text': 'hi', 'language_source': 'DETECTED'}):
        assert client.post(endpoint, headers=headers, json=payload).status_code == 422
    message = client.post(endpoint, headers=headers, json={**base, 'content_text': '  preserved  '})
    assert message.status_code == 201 and message.json()['content_text'] == '  preserved  '
    assert client.patch(f"{endpoint}/{message.json()['id']}", headers=headers, json={'content_text': 'changed'}).status_code in {404, 405}
    assert client.delete(f"{endpoint}/{message.json()['id']}", headers=headers).status_code in {404, 405}


def test_lifecycle_closure_blocks_new_evidence_and_reopening(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers)
    participant = _participant(client, conversation['id'], headers)
    closed = client.patch(f"/conversations/{conversation['id']}", headers=headers, json={'status': 'CLOSED'})
    assert closed.status_code == 200 and closed.json()['closed_at'] is not None
    assert client.post(f"/conversations/{conversation['id']}/messages", headers=headers, json={'participant_id': participant['id'], 'modality': 'TEXT', 'content_text': 'late'}).status_code == 409
    assert client.post(f"/conversations/{conversation['id']}/participants", headers=headers, json={'participant_type': 'SYSTEM'}).status_code == 409
    assert client.patch(f"/conversations/{conversation['id']}", headers=headers, json={'status': 'ACTIVE'}).status_code == 422


def test_context_mutation_is_set_once_and_compatible(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers)
    assigned = client.patch(f"/conversations/{conversation['id']}", headers=headers, json={'location_id': scope.location_id, 'resource_id': scope.resource_id})
    assert assigned.status_code == 200, assigned.text
    other_location = _execute(connection, "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC-2','Location 2','UTC','ACTIVE')", (scope.tenant_id, scope.organization_id))
    assert client.patch(f"/conversations/{conversation['id']}", headers=headers, json={'location_id': other_location}).status_code == 409
    no_location = _conversation(client, scope, headers, channel='PHONE')
    assert client.patch(f"/conversations/{no_location['id']}", headers=headers, json={'resource_id': scope.resource_id}).status_code == 404
    wrong_context = _conversation(client, scope, headers, channel='WEB_CHAT', location_id=other_location)
    assert client.patch(f"/conversations/{wrong_context['id']}", headers=headers, json={'resource_id': scope.resource_id}).status_code == 404


def test_raw_database_rejects_cross_context_and_invalid_evidence(sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    other = _scope(connection, f'{prefix}-other')
    conversation_id = _execute(connection, "INSERT INTO conversations (tenant_id,organization_id,channel,status,next_message_sequence) VALUES (%s,%s,'PHONE','ACTIVE',1)", (scope.tenant_id, scope.organization_id))
    participant_id = _execute(connection, "INSERT INTO conversation_participants (tenant_id,conversation_id,participant_type) VALUES (%s,%s,'CUSTOMER')", (scope.tenant_id, conversation_id))
    other_conversation_id = _execute(connection, "INSERT INTO conversations (tenant_id,organization_id,channel,status,next_message_sequence) VALUES (%s,%s,'PHONE','ACTIVE',1)", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text) VALUES (%s,%s,%s,1,'TEXT','valid')", (scope.tenant_id, conversation_id, participant_id))
    invalid = (
        ("INSERT INTO conversations (tenant_id,organization_id,location_id,channel,status,next_message_sequence) VALUES (%s,%s,%s,'PHONE','ACTIVE',1)", (scope.tenant_id, scope.organization_id, other.location_id)),
        ("INSERT INTO conversations (tenant_id,organization_id,resource_id,channel,status,next_message_sequence) VALUES (%s,%s,%s,'PHONE','ACTIVE',1)", (scope.tenant_id, scope.organization_id, scope.resource_id)),
        ("INSERT INTO conversation_participants (tenant_id,conversation_id,participant_type,customer_id) VALUES (%s,%s,'CUSTOMER',%s)", (scope.tenant_id, conversation_id, other.customer_ids[0])),
        ("INSERT INTO conversation_participants (tenant_id,conversation_id,participant_type) VALUES (%s,%s,'HUMAN_STAFF')", (scope.tenant_id, conversation_id)),
        ("INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text) VALUES (%s,%s,%s,1,'TEXT','wrong')", (other.tenant_id, conversation_id, participant_id)),
        ("INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text) VALUES (%s,%s,%s,1,'IMAGE','wrong')", (scope.tenant_id, conversation_id, participant_id)),
        ("INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text) VALUES (%s,%s,%s,1,'TEXT','duplicate sequence')", (scope.tenant_id, conversation_id, participant_id)),
        ("INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text) VALUES (%s,%s,%s,1,'TEXT','wrong conversation')", (scope.tenant_id, other_conversation_id, participant_id)),
    )
    for statement, parameters in invalid:
        with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
            _execute(connection, statement, parameters)


def test_concurrent_message_sequence_allocation(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    conversation_id = _execute(connection, "INSERT INTO conversations (tenant_id,organization_id,channel,status,next_message_sequence) VALUES (%s,%s,'PHONE','ACTIVE',1)", (scope.tenant_id, scope.organization_id))
    participant_id = _execute(connection, "INSERT INTO conversation_participants (tenant_id,conversation_id,participant_type) VALUES (%s,%s,'CUSTOMER')", (scope.tenant_id, conversation_id))

    async def scenario():
        manager = DatabaseManager(integration_settings)
        try:
            async def create(content):
                async with manager.session_factory() as session:
                    return await append_message(session, tenant_id=scope.tenant_id, conversation_id=conversation_id, participant_id=participant_id, modality='TEXT', content_text=content, language='en', language_source='DECLARED')
            first, second = await asyncio.gather(create('first'), create('second'))
            assert {first.sequence_number, second.sequence_number} == {1, 2}
            async with manager.session_factory() as session:
                result = await session.execute(select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.sequence_number))
                assert [item.sequence_number for item in result.scalars()] == [1, 2]
        finally:
            await manager.dispose()
    asyncio.run(scenario())


def test_logs_exclude_message_content(client, sql_connection, caplog):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    conversation = _conversation(client, scope, headers)
    participant = _participant(client, conversation['id'], headers)
    secret = 'private transcript must never be logged'
    with caplog.at_level(logging.INFO):
        response = client.post(f"/conversations/{conversation['id']}/messages", headers=headers, json={'participant_id': participant['id'], 'modality': 'VOICE', 'content_text': secret, 'language': 'en', 'language_source': 'DECLARED'})
    assert response.status_code == 201
    assert secret not in caplog.text
