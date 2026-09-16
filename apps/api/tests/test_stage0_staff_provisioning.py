from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from io import BytesIO
import json

from openpyxl import load_workbook
from fastapi.testclient import TestClient
import pytest

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.models import OnboardingImport
from app.onboarding import staff_provisioning
from test_inventory_recipe_stock_foundation import (
    PASSWORD,
    _execute,
    _headers,
    _permission,
)
from test_stage0_onboarding_confirmed_import import (
    _analyze,
    _confirm,
    _prepare,
    _set_row,
    _workbook,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _role(connection, tenant_id: int, name: str) -> int:
    return _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) '
        "VALUES (%s,%s,'Stage 0 Staff Role','ACTIVE')",
        (tenant_id, name),
    )


def _staff_authority(connection, scope) -> str:
    for code in (
        'user.manage', 'role.manage', 'location.manage',
        'product.read', 'menu.read',
    ):
        _permission(connection, scope.role_id, code)
    role_name = f'STAFF-{scope.tenant_id}'
    role_id = _role(connection, scope.tenant_id, role_name)
    _permission(connection, role_id, 'product.read')
    return role_name


def _staff_workbook(
    tenant_slug: str, *, staff_key: str, display_name: str,
    email: str, role_name: str, status: str = 'ACTIVE',
) -> bytes:
    workbook = load_workbook(
        BytesIO(_workbook(tenant_slug, inventory=False)), data_only=False,
    )
    _set_row(workbook, '02_Staff', (
        staff_key, tenant_slug, display_name, email,
        role_name, 'LOC', status,
    ))
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _access_counts(connection, tenant_id: int, email: str) -> tuple[int, int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM users WHERE email=%s', (email,),
        )
        user = cursor.fetchone()
        if user is None:
            return 0, 0, 0
        cursor.execute(
            'SELECT id FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s',
            (tenant_id, user['id']),
        )
        membership = cursor.fetchone()
        if membership is None:
            return 0, 0, 0
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM membership_roles '
            'WHERE tenant_id=%s AND membership_id=%s',
            (tenant_id, membership['id']),
        )
        roles = int(cursor.fetchone()['amount'])
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM membership_location_grants '
            'WHERE tenant_id=%s AND membership_id=%s',
            (tenant_id, membership['id']),
        )
        grants = int(cursor.fetchone()['amount'])
        return 1, roles, grants


def test_existing_active_user_completes_through_p2_and_disabled_fails_closed(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    role_name = _staff_authority(connection, scope)
    headers = _headers(client, scope)
    email = f'{prefix}-existing@example.test'
    original_hash = hash_password(PASSWORD)
    _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) '
        "VALUES (%s,%s,'Existing Staff','ACTIVE')",
        (email, original_hash),
    )
    content = _staff_workbook(
        f'{prefix}-onboarding', staff_key='EXISTING',
        display_name='Existing Staff', email=email.upper(), role_name=role_name,
    )
    analyzed = _analyze(client, headers, content)
    assert analyzed.status_code == 200, analyzed.text
    confirmed = _confirm(
        client, headers, content, scope.location_id,
        analyzed.json()['dataset_fingerprint'],
    )
    assert confirmed.status_code == 201, confirmed.text
    result = confirmed.json()
    assert result['status'] == 'SUCCESS'
    assert result['groups']['staff']['created'] == 1
    assert result['groups']['staff']['pending'] == 0
    assert result['required_deferred_groups'] == []
    assert _access_counts(connection, scope.tenant_id, email) == (1, 1, 1)
    with connection.cursor() as cursor:
        cursor.execute('SELECT password_hash FROM users WHERE email=%s', (email,))
        assert cursor.fetchone()['password_hash'] == original_hash

    replay = _confirm(
        client, headers, content, scope.location_id,
        analyzed.json()['dataset_fingerprint'],
    )
    assert replay.status_code == 200 and replay.json()['replay'] is True
    assert _access_counts(connection, scope.tenant_id, email) == (1, 1, 1)

    disabled_email = f'{prefix}-disabled@example.test'
    _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) '
        "VALUES (%s,%s,'Disabled Staff','DISABLED')",
        (disabled_email, hash_password(PASSWORD)),
    )
    disabled_content = _staff_workbook(
        f'{prefix}-onboarding', staff_key='DISABLED',
        display_name='Disabled Staff', email=disabled_email,
        role_name=role_name,
    )
    disabled_analysis = _analyze(client, headers, disabled_content)
    disabled = _confirm(
        client, headers, disabled_content, scope.location_id,
        disabled_analysis.json()['dataset_fingerprint'],
    )
    assert disabled.status_code == 201
    assert disabled.json()['status'] == 'FAILED'
    assert disabled.json()['groups']['staff']['failed'] == 1
    assert _access_counts(connection, scope.tenant_id, disabled_email) == (0, 0, 0)


def test_new_identity_is_secret_free_pending_then_resumes_after_acceptance(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    role_name = _staff_authority(connection, scope)
    headers = _headers(client, scope)
    email = f'{prefix}-invited@example.test'
    content = _staff_workbook(
        f'{prefix}-onboarding', staff_key='INVITED',
        display_name='Invited Staff', email=f'  {email.upper()}  ',
        role_name=role_name,
    )
    analyzed = _analyze(client, headers, content)
    assert analyzed.status_code == 200, analyzed.text
    fingerprint = analyzed.json()['dataset_fingerprint']

    first = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['status'] == 'PARTIAL'
    assert result['groups']['staff']['pending'] == 1
    assert result['groups']['staff']['created'] == 0
    assert len(result['invitation_deliveries']) == 1
    token = result['invitation_deliveries'][0]['acceptance_token']
    assert _access_counts(connection, scope.tenant_id, email) == (0, 0, 0)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT status,requested_permission_codes FROM '
            'onboarding_staff_continuations WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        continuation = cursor.fetchone()
        assert continuation['status'] == 'PENDING_ACCEPTANCE'
        assert json.loads(continuation['requested_permission_codes']) == ['product.read']
        cursor.execute(
            'SELECT result_json FROM onboarding_imports WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        persisted = cursor.fetchone()['result_json']
        assert token not in str(persisted)
        assert token.partition('.')[2] not in str(persisted)
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM identity_invitations WHERE email=%s',
            (email,),
        )
        assert cursor.fetchone()['amount'] == 1

    pending_replay = _confirm(
        client, headers, content, scope.location_id, fingerprint,
    )
    assert pending_replay.status_code == 200
    assert pending_replay.json()['status'] == 'PARTIAL'
    assert pending_replay.json()['groups']['staff']['pending'] == 1
    assert 'invitation_deliveries' not in pending_replay.json()

    password = 'Accepted Staff Password 123!'
    accepted = client.post('/identity/invitations/accept', json={
        'acceptance_token': token, 'password': password,
    })
    assert accepted.status_code == 200, accepted.text
    resumed = _confirm(client, headers, content, scope.location_id, fingerprint)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['status'] == 'SUCCESS'
    assert resumed.json()['groups']['staff']['created'] == 1
    assert resumed.json()['groups']['staff']['pending'] == 0
    assert _access_counts(connection, scope.tenant_id, email) == (1, 1, 1)
    login = client.post('/auth/login', json={
        'email': email, 'password': password, 'tenant_id': scope.tenant_id,
    })
    assert login.status_code == 200, login.text


def test_pending_staff_rejects_role_drift_and_concurrent_requests_converge(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    role_name = _staff_authority(connection, scope)
    headers = _headers(client, scope)
    email = f'{prefix}-drift@example.test'
    content = _staff_workbook(
        f'{prefix}-onboarding', staff_key='DRIFT', display_name='Drift Staff',
        email=email, role_name=role_name,
    )
    analyzed = _analyze(client, headers, content).json()
    first = _confirm(
        client, headers, content, scope.location_id,
        analyzed['dataset_fingerprint'],
    )
    token = first.json()['invitation_deliveries'][0]['acceptance_token']
    accepted = client.post('/identity/invitations/accept', json={
        'acceptance_token': token, 'password': 'Drift Staff Password 123!',
    })
    assert accepted.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM roles WHERE tenant_id=%s AND name=%s',
            (scope.tenant_id, role_name),
        )
        target_role_id = cursor.fetchone()['id']
    _permission(connection, target_role_id, 'menu.read')
    rejected = _confirm(
        client, headers, content, scope.location_id,
        analyzed['dataset_fingerprint'],
    )
    assert rejected.status_code == 200
    assert rejected.json()['status'] == 'PARTIAL'
    assert rejected.json()['groups']['staff']['failed'] == 1
    assert rejected.json()['staff_continuations'][0]['status'] == 'SECURITY_CONFLICT'
    assert _access_counts(connection, scope.tenant_id, email) == (0, 0, 0)

    race_email = f'{prefix}-race@example.test'
    values = {
        'staff_key': 'RACE', 'tenant_slug': f'{prefix}-onboarding',
        'display_name': 'Race Staff', 'email': race_email,
        'role_name': role_name, 'location_code': 'LOC', 'status': 'ACTIVE',
        'requested_permission_codes': ['menu.read', 'product.read'],
    }
    first_import_id = _execute(
        connection,
        'INSERT INTO onboarding_imports '
        '(import_id,tenant_id,organization_id,location_id,contract_version,'
        'dataset_fingerprint,actor_membership_id,status) '
        "VALUES (UUID(),%s,%s,%s,'restaurant-onboarding/v1',%s,%s,'IN_PROGRESS')",
        (scope.tenant_id, scope.organization_id, scope.location_id, 'a' * 64,
         scope.membership_id),
    )
    second_import_id = _execute(
        connection,
        'INSERT INTO onboarding_imports '
        '(import_id,tenant_id,organization_id,location_id,contract_version,'
        'dataset_fingerprint,actor_membership_id,status) '
        "VALUES (UUID(),%s,%s,%s,'restaurant-onboarding/v1',%s,%s,'IN_PROGRESS')",
        (scope.tenant_id, scope.organization_id, scope.location_id, 'b' * 64,
         scope.membership_id),
    )

    async def exercise():
        database = DatabaseManager(integration_settings)
        try:
            async with (
                database.session_factory() as first_db,
                database.session_factory() as second_db,
            ):
                first_evidence = await first_db.get(OnboardingImport, first_import_id)
                second_evidence = await second_db.get(OnboardingImport, second_import_id)
                return await asyncio.gather(
                    staff_provisioning.provision_staff_request(
                        first_db, settings=integration_settings,
                        evidence=first_evidence,
                        actor_membership_id=scope.membership_id, values=values,
                    ),
                    staff_provisioning.provision_staff_request(
                        second_db, settings=integration_settings,
                        evidence=second_evidence,
                        actor_membership_id=scope.membership_id, values=values,
                    ),
                )
        finally:
            await database.dispose()

    outcomes = asyncio.run(exercise())
    assert len({value.continuation.continuation_id for value in outcomes}) == 1
    assert sum(value.delivery is not None for value in outcomes) == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM identity_invitations WHERE email=%s',
            (race_email,),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM onboarding_staff_continuations '
            'WHERE tenant_id=%s AND normalized_email=%s',
            (scope.tenant_id, race_email),
        )
        assert cursor.fetchone()['amount'] == 1


def test_expired_pending_invitation_becomes_terminal_once_on_replay(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _prepare(connection, prefix)
    role_name = _staff_authority(connection, scope)
    headers = _headers(client, scope)
    email = f'{prefix}-expired@example.test'
    content = _staff_workbook(
        f'{prefix}-onboarding', staff_key='EXPIRED',
        display_name='Expired Staff', email=email, role_name=role_name,
    )
    analyzed = _analyze(client, headers, content).json()
    first = _confirm(
        client, headers, content, scope.location_id,
        analyzed['dataset_fingerprint'],
    )
    assert first.status_code == 201
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE identity_invitations SET expires_at=%s WHERE email=%s',
            (datetime.now() - timedelta(seconds=1), email),
        )

    terminal = _confirm(
        client, headers, content, scope.location_id,
        analyzed['dataset_fingerprint'],
    )
    assert terminal.status_code == 200
    result = terminal.json()
    assert result['groups']['staff']['failed'] == 1
    assert result['groups']['staff']['pending'] == 0
    assert result['staff_continuations'][0]['status'] == 'TERMINAL_FAILURE'
    assert [
        value['code'] for value in result['errors']
        if value['group'] == 'staff'
    ] == ['STAFF_CONTINUATION_TERMINAL_FAILURE']

    replay = _confirm(
        client, headers, content, scope.location_id,
        analyzed['dataset_fingerprint'],
    )
    assert replay.status_code == 200
    assert [
        value['code'] for value in replay.json()['errors']
        if value['group'] == 'staff'
    ] == ['STAFF_CONTINUATION_TERMINAL_FAILURE']
