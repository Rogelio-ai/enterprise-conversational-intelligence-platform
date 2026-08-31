from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.restaurant.preparation_delivery.service import result_fingerprint
from test_pos_order_submission_recovery import _headers, _scope
from test_preparation_dispatch_operational_delivery import _native_dispatch


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _provision(client, headers, connector_id):
    enrollment = client.post(
        f'/preparation-delivery-connectors/{connector_id}/enrollments', headers=headers,
    )
    assert enrollment.status_code == 201, enrollment.text
    once = enrollment.json()
    credential = client.post('/connector-auth/v1/enroll', json={
        'enrollment_id': once['enrollment_id'],
        'enrollment_secret': once['enrollment_secret'],
    })
    assert credential.status_code == 201, credential.text
    machine = credential.json()
    token = client.post('/connector-auth/v1/token', json={
        'client_id': machine['client_id'], 'client_secret': machine['client_secret'],
    })
    assert token.status_code == 200, token.text
    return once, machine, {'Authorization': f"Bearer {token.json()['access_token']}"}


def test_enrollment_machine_auth_assigned_claim_result_and_revocation(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    staff, _, _, _, connector, _, dispatch = _native_dispatch(client, connection, scope)
    once, machine, machine_headers = _provision(client, staff, connector['id'])

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT secret_digest,consumed_at,active_slot FROM preparation_delivery_connector_enrollments WHERE enrollment_id=%s',
            (once['enrollment_id'],),
        )
        stored = cursor.fetchone()
        assert stored['secret_digest'] != once['enrollment_secret']
        assert len(stored['secret_digest']) == 64
        assert stored['consumed_at'] is not None
        assert stored['active_slot'] is None
        cursor.execute(
            'SELECT id,secret_digest FROM preparation_delivery_connector_credentials WHERE client_id=%s',
            (machine['client_id'],),
        )
        credential = cursor.fetchone()
        assert credential['secret_digest'] != machine['client_secret']

    assert client.post('/connector-auth/v1/enroll', json={
        'enrollment_id': once['enrollment_id'],
        'enrollment_secret': once['enrollment_secret'],
    }).status_code == 401
    assert client.get('/connector/v1/dispatches/eligible', headers=staff).status_code == 401

    eligible = client.get('/connector/v1/dispatches/eligible', headers=machine_headers)
    assert eligible.status_code == 200, eligible.text
    assert [item['dispatch_id'] for item in eligible.json()['items']] == [dispatch['id']]
    heartbeat = client.post('/connector/v1/heartbeat', headers=machine_headers, json={
        'connector_version': '0.1.0',
        'protocol_version': 'restaurant-local-connector-v1',
        'runtime_status': 'RUNNING', 'capabilities': ['cups'],
    })
    assert heartbeat.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT last_seen_at,connector_version,protocol_version FROM preparation_delivery_connectors WHERE id=%s',
            (connector['id'],),
        )
        observed = cursor.fetchone()
        assert observed['last_seen_at'] is not None
        assert observed['connector_version'] == '0.1.0'

    request_id = 'CaseSensitive-Claim-1'
    first = client.post(
        f"/connector/v1/dispatches/{dispatch['id']}/claims", headers=machine_headers,
        json={'claim_request_id': request_id},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body['payload_text'] == dispatch['payload_text']
    assert body['payload_fingerprint'] == dispatch['payload_fingerprint']
    replay = client.post(
        f"/connector/v1/dispatches/{dispatch['id']}/claims", headers=machine_headers,
        json={'claim_request_id': request_id},
    )
    assert replay.status_code == 200
    assert replay.json()['claim_token'] == body['claim_token']
    assert replay.json()['attempt']['id'] == body['attempt']['id']
    conflict = client.post(
        f"/connector/v1/dispatches/{dispatch['id'] + 999999}/claims", headers=machine_headers,
        json={'claim_request_id': request_id},
    )
    assert conflict.status_code == 409

    fingerprint = result_fingerprint(
        result='DESTINATION_SUBMISSION_ACCEPTED',
        local_job_reference='cups:KITCHEN:42', error_kind=None, error_message=None,
    )
    result = {
        'claim_token': body['claim_token'],
        'result': 'DESTINATION_SUBMISSION_ACCEPTED',
        'result_fingerprint': fingerprint,
        'local_job_reference': 'cups:KITCHEN:42',
        'error_kind': None, 'error_message': None,
    }
    recorded = client.post(
        f"/connector/v1/dispatches/{dispatch['id']}/results",
        headers=machine_headers, json=result,
    )
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()['dispatch']['state'] == 'DESTINATION_SUBMISSION_ACCEPTED'
    replayed = client.post(
        f"/connector/v1/dispatches/{dispatch['id']}/results",
        headers=machine_headers, json=result,
    )
    assert replayed.status_code == 200
    assert replayed.json()['replayed'] is True

    listed = client.get(
        f"/preparation-delivery-connectors/{connector['id']}/credentials", headers=staff,
    )
    assert listed.status_code == 200
    assert 'secret_digest' not in listed.text and 'client_secret' not in listed.text
    revoked = client.post(
        f"/preparation-delivery-connectors/{connector['id']}/credentials/{credential['id']}/revoke",
        headers=staff,
    )
    assert revoked.status_code == 200
    assert client.get('/connector/v1/dispatches/eligible', headers=machine_headers).status_code == 401


def test_rotation_is_separate_and_enrollment_revocation(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    staff, _, _, _, connector, _, _ = _native_dispatch(client, connection, scope)
    once, machine, _ = _provision(client, staff, connector['id'])
    rotated = client.post(
        f"/preparation-delivery-connectors/{connector['id']}/credentials/rotate",
        headers=staff,
    )
    assert rotated.status_code == 201, rotated.text
    assert rotated.json()['client_id'] != machine['client_id']
    assert rotated.json()['replaces_credential_id'] is not None
    assert client.post(
        f"/preparation-delivery-connectors/{connector['id']}/enrollments", headers=staff,
    ).status_code == 409
    second_connector = client.post('/preparation-delivery-connectors', headers=staff, json={
        'location_id': scope.location_id, 'code': 'LOCAL_REVOKE', 'name': 'Revoke Test',
    }).json()
    second_enrollment = client.post(
        f"/preparation-delivery-connectors/{second_connector['id']}/enrollments", headers=staff,
    )
    assert second_enrollment.status_code == 201
    revoked = client.post(
        f"/preparation-delivery-connectors/{second_connector['id']}/enrollments/{second_enrollment.json()['enrollment_id']}/revoke",
        headers=staff,
    )
    assert revoked.status_code == 200
    assert client.post('/connector-auth/v1/enroll', json={
        'enrollment_id': second_enrollment.json()['enrollment_id'],
        'enrollment_secret': second_enrollment.json()['enrollment_secret'],
    }).status_code == 401
