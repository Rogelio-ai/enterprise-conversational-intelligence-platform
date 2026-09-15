from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core.security import verify_password
from app.identity import invitations
from app.main import create_app
from test_inventory_recipe_stock_foundation import (
    PASSWORD,
    _headers,
    _permission,
    _scope,
)


def _prepare(connection, prefix: str):
    scope = _scope(connection, f'{prefix}-identity-invitation')
    return scope, _headers


def _invite(client, headers, *, email: str, display_name: str = 'Invited User'):
    return client.post(
        '/identity/invitations', headers=headers,
        json={'email': email, 'display_name': display_name},
    )


def test_invitation_is_credential_free_one_time_and_activates_existing_login(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, header_factory = _prepare(connection, prefix)
    with TestClient(create_app(settings=integration_settings)) as client:
        headers = header_factory(client, scope)
        email = f'{prefix}-invited@example.test'

        forbidden = _invite(client, headers, email=email)
        assert forbidden.status_code == 403
        _permission(connection, scope.role_id, 'user.manage')

        password_in_creation = client.post(
            '/identity/invitations', headers=headers,
            json={
                'email': email, 'display_name': 'Invited User',
                'password': 'must-not-be-accepted',
            },
        )
        assert password_in_creation.status_code == 422

        created = _invite(
            client, headers, email=f'  {email.upper()}  ',
        )
        assert created.status_code == 201, created.text
        invitation = created.json()
        assert invitation['email'] == email
        token = invitation['acceptance_token']
        secret = token.partition('.')[2]
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT email,display_name,secret_digest,consumed_at,revoked_at,'
                'active_slot FROM identity_invitations WHERE invitation_id=%s',
                (invitation['invitation_id'],),
            )
            stored = cursor.fetchone()
            cursor.execute('SELECT COUNT(*) AS amount FROM users WHERE email=%s', (email,))
            assert cursor.fetchone()['amount'] == 0
        assert stored['email'] == email
        assert stored['secret_digest'] != secret
        assert token not in stored['secret_digest']
        assert stored['consumed_at'] is None and stored['revoked_at'] is None
        assert stored['active_slot'] == 1

        before_activation = client.post(
            '/auth/login', json={
                'email': email, 'password': 'User Selected Password 123!',
            },
        )
        assert before_activation.status_code == 401

        invalid_token = f"{token[:-1]}{'x' if token[-1] != 'x' else 'y'}"
        invalid = client.post('/identity/invitations/accept', json={
            'acceptance_token': invalid_token,
            'password': 'User Selected Password 123!',
        })
        assert invalid.status_code == 401

        weak = client.post('/identity/invitations/accept', json={
            'acceptance_token': token, 'password': 'short',
        })
        assert weak.status_code == 409
        password = 'User Selected Password 123!'
        accepted = client.post('/identity/invitations/accept', json={
            'acceptance_token': token, 'password': password,
        })
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()['email'] == email
        assert accepted.json()['status'] == 'ACTIVE'
        replay = client.post('/identity/invitations/accept', json={
            'acceptance_token': token, 'password': password,
        })
        assert replay.status_code == 401

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT id,password_hash,status FROM users WHERE email=%s', (email,),
            )
            user = cursor.fetchone()
            assert user['status'] == 'ACTIVE'
            assert user['password_hash'] != password
            assert verify_password(password, user['password_hash'])
            cursor.execute(
                'SELECT COUNT(*) AS amount FROM tenant_memberships WHERE user_id=%s',
                (user['id'],),
            )
            assert cursor.fetchone()['amount'] == 0
            cursor.execute(
                'SELECT consumed_at,active_slot,accepted_user_id '
                'FROM identity_invitations WHERE invitation_id=%s',
                (invitation['invitation_id'],),
            )
            consumed = cursor.fetchone()
            assert consumed['consumed_at'] is not None
            assert consumed['active_slot'] is None
            assert consumed['accepted_user_id'] == user['id']
            cursor.execute(
                "INSERT INTO tenant_memberships (tenant_id,user_id,status) "
                "VALUES (%s,%s,'ACTIVE')", (scope.tenant_id, user['id']),
            )

        login = client.post('/auth/login', json={
            'email': email, 'password': password, 'tenant_id': scope.tenant_id,
        })
        assert login.status_code == 200, login.text
        me = client.get(
            '/auth/me', headers={'Authorization': f"Bearer {login.json()['access_token']}"},
        )
        assert me.status_code == 200 and me.json()['email'] == email


def test_expiry_revocation_reinvite_and_existing_credentials_are_safe(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, header_factory = _prepare(connection, prefix)
    _permission(connection, scope.role_id, 'user.manage')
    with TestClient(create_app(settings=integration_settings)) as client:
        headers = header_factory(client, scope)
        email = f'{prefix}-lifecycle@example.test'
        first = _invite(client, headers, email=email)
        assert first.status_code == 201
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE identity_invitations SET expires_at=%s '
                'WHERE invitation_id=%s',
                (datetime.now() - timedelta(seconds=1), first.json()['invitation_id']),
            )
        expired = client.post('/identity/invitations/accept', json={
            'acceptance_token': first.json()['acceptance_token'],
            'password': 'Expired Password 123!',
        })
        assert expired.status_code == 401

        second = _invite(client, headers, email=email)
        assert second.status_code == 201, second.text
        duplicate = _invite(client, headers, email=email)
        assert duplicate.status_code == 409
        revoked = client.post(
            f"/identity/invitations/{second.json()['invitation_id']}/revoke",
            headers=headers,
        )
        assert revoked.status_code == 200
        rejected = client.post('/identity/invitations/accept', json={
            'acceptance_token': second.json()['acceptance_token'],
            'password': 'Revoked Password 123!',
        })
        assert rejected.status_code == 401
        third = _invite(client, headers, email=email)
        assert third.status_code == 201

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT id,password_hash FROM users WHERE email=%s', (scope.email,),
            )
            actor = cursor.fetchone()
            original_hash = actor['password_hash']
        existing = _invite(client, headers, email=scope.email)
        assert existing.status_code == 409
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT password_hash FROM users WHERE id=%s', (actor['id'],),
            )
            assert cursor.fetchone()['password_hash'] == original_hash
            cursor.execute(
                'SELECT COUNT(*) AS amount FROM identity_invitations '
                'WHERE email=%s AND active_slot=1', (email,),
            )
            assert cursor.fetchone()['amount'] == 1


def test_concurrent_invitation_and_acceptance_have_one_winner(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, _ = _prepare(connection, prefix)
    _permission(connection, scope.role_id, 'user.manage')
    email = f'{prefix}-race@example.test'

    async def exercise():
        from app.db.session import DatabaseManager

        database = DatabaseManager(integration_settings)
        try:
            async with (
                database.session_factory() as first_db,
                database.session_factory() as second_db,
            ):
                created = await asyncio.gather(
                    invitations.invite_identity(
                        first_db, settings=integration_settings,
                        tenant_id=scope.tenant_id,
                        actor_membership_id=scope.membership_id,
                        email=email, display_name='Concurrent Identity',
                    ),
                    invitations.invite_identity(
                        second_db, settings=integration_settings,
                        tenant_id=scope.tenant_id,
                        actor_membership_id=scope.membership_id,
                        email=email, display_name='Concurrent Identity',
                    ),
                    return_exceptions=True,
                )
            successful = [
                value for value in created
                if isinstance(value, invitations.InvitationCreationResult)
            ]
            assert len(successful) == 1
            assert sum(
                isinstance(value, invitations.IdentityInvitationConflictError)
                for value in created
            ) == 1
            token = successful[0].acceptance_token
            async with (
                database.session_factory() as first_db,
                database.session_factory() as second_db,
            ):
                accepted = await asyncio.gather(
                    invitations.accept_invitation(
                        first_db, settings=integration_settings,
                        acceptance_token=token,
                        user_selected_password='Concurrent Password 123!',
                    ),
                    invitations.accept_invitation(
                        second_db, settings=integration_settings,
                        acceptance_token=token,
                        user_selected_password='Concurrent Password 123!',
                    ),
                    return_exceptions=True,
                )
            return created, accepted
        finally:
            await database.dispose()

    _, accepted = asyncio.run(exercise())
    assert sum(
        isinstance(value, invitations.InvitationAcceptanceResult)
        for value in accepted
    ) == 1
    assert sum(
        isinstance(value, invitations.InvalidIdentityInvitationError)
        for value in accepted
    ) == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS amount FROM users WHERE email=%s', (email,))
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM identity_invitations '
            'WHERE email=%s AND consumed_at IS NOT NULL', (email,),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM tenant_memberships m '
            'JOIN users u ON u.id=m.user_id WHERE u.email=%s', (email,),
        )
        assert cursor.fetchone()['amount'] == 0
