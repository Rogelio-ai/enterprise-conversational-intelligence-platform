from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.identity import access_provisioning
from app.main import create_app
from test_inventory_recipe_stock_foundation import (
    PASSWORD,
    _execute,
    _headers,
    _permission,
    _scope,
)


def _user(connection, prefix: str, label: str, *, status: str = 'ACTIVE') -> tuple[int, str]:
    email = f'{prefix}-{label}@example.test'
    password_hash = hash_password(PASSWORD)
    user_id = _execute(
        connection,
        'INSERT INTO users (username,email,password_hash,display_name,status) '
        'VALUES (%s,%s,%s,%s,%s)',
        (f'{prefix}-{label}'.casefold(), email, password_hash, f'Target {label}', status),
    )
    return user_id, password_hash


def _role(connection, tenant_id: int, name: str, permissions: tuple[str, ...]) -> int:
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, name, 'Access provisioning test role', 'ACTIVE'),
    )
    for permission in permissions:
        _permission(connection, role_id, permission)
    return role_id


def _payload(user_id: int, role_name: str, organization_id: int, location_id: int):
    return {
        'user_id': user_id,
        'role_name': role_name,
        'locations': [{
            'organization_id': organization_id,
            'location_id': location_id,
        }],
    }


def _membership_count(connection, tenant_id: int, user_ids: tuple[int, ...]) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM tenant_memberships '
            'WHERE tenant_id=%s AND user_id IN ('
            + ','.join(['%s'] * len(user_ids)) + ')',
            (tenant_id, *user_ids),
        )
        return int(cursor.fetchone()['amount'])


def test_access_plan_creates_replays_and_preserves_credentials_and_rbac(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, f'{prefix}-access')
    for code in ('user.manage', 'role.manage', 'location.manage', 'product.read'):
        _permission(connection, scope.role_id, code)
    target_user_id, original_hash = _user(connection, prefix, 'safe')
    role_name = f'{prefix}-SAFE_STAFF'
    role_id = _role(connection, scope.tenant_id, role_name, ('product.read',))
    payload = _payload(
        target_user_id, role_name, scope.organization_id, scope.location_id,
    )

    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _headers(client, scope)
        caller_capabilities = client.post(
            '/identity/access-provisioning', headers=headers,
            json={**payload, 'permissions': ['tenant.manage']},
        )
        assert caller_capabilities.status_code == 422

        first = client.post(
            '/identity/access-provisioning', headers=headers, json=payload,
        )
        assert first.status_code == 200, first.text
        assert first.json()['membership_operation'] == 'CREATE'
        assert first.json()['role_operation'] == 'CREATE'
        assert first.json()['location_grants'] == [{
            'organization_id': scope.organization_id,
            'location_id': scope.location_id,
            'operation': 'CREATE',
        }]

        replay = client.post(
            '/identity/access-provisioning', headers=headers, json=payload,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()['membership_operation'] == 'UNCHANGED'
        assert replay.json()['role_operation'] == 'UNCHANGED'
        assert replay.json()['location_grants'][0]['operation'] == 'UNCHANGED'

        login = client.post('/auth/login', json={
            'username': f'{prefix}-safe', 'password': PASSWORD,
        })
        assert login.status_code == 200, login.text
        me = client.get('/auth/me', headers={
            'Authorization': f"Bearer {login.json()['access_token']}",
        })
        assert me.status_code == 200
        assert me.json()['roles'] == [role_name]
        assert me.json()['permissions'] == ['product.read']
        assert me.json()['authorized_location_ids'] == [scope.location_id]

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id,password_hash FROM users WHERE id=%s', (target_user_id,),
        )
        target = cursor.fetchone()
        assert target['password_hash'] == original_hash
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM tenant_memberships '
            'WHERE tenant_id=%s AND user_id=%s',
            (scope.tenant_id, target_user_id),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM membership_roles '
            'WHERE membership_id=%s AND role_id=%s',
            (replay.json()['membership_id'], role_id),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM membership_location_grants '
            'WHERE membership_id=%s AND location_id=%s',
            (replay.json()['membership_id'], scope.location_id),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM role_permissions WHERE role_id=%s',
            (role_id,),
        )
        assert cursor.fetchone()['amount'] == 1


def test_staff_account_provisioning_creates_username_login_without_email(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, f'{prefix}-staff-account')
    for code in ('user.manage', 'role.manage', 'location.manage', 'product.read'):
        _permission(connection, scope.role_id, code)
    role_name = f'{prefix}-STAFF'
    _role(connection, scope.tenant_id, role_name, ('product.read',))
    payload = {
        'username': f'{prefix}.Operator',
        'password': PASSWORD,
        'display_name': 'Operator Without Email',
        'role_name': role_name,
        'locations': [{
            'organization_id': scope.organization_id,
            'location_id': scope.location_id,
        }],
    }

    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _headers(client, scope)
        created = client.post(
            '/identity/access-provisioning/staff', headers=headers, json=payload,
        )
        assert created.status_code == 200, created.text
        login = client.post('/auth/login', json={
            'username': f'{prefix}.operator', 'password': PASSWORD,
        })
        assert login.status_code == 200, login.text
        assert login.json()['user']['email'] is None
        duplicate = client.post(
            '/identity/access-provisioning/staff', headers=headers,
            json={**payload, 'username': f'  {prefix}.OPERATOR  '},
        )
        assert duplicate.status_code == 409
        no_location = client.post(
            '/identity/access-provisioning/staff', headers=headers,
            json={
                **payload,
                'username': f'{prefix}.no-location',
                'locations': [],
            },
        )
        assert no_location.status_code == 422

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM users WHERE username=%s AND email IS NULL',
            (f'{prefix}.operator',),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT role_id FROM membership_location_roles '
            'WHERE membership_id=%s AND location_id=%s',
            (created.json()['membership_id'], scope.location_id),
        )
        assert cursor.fetchone()['role_id'] is not None


def test_access_plan_fails_closed_for_authority_privilege_and_scope_conflicts(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, f'{prefix}-guard')
    for code in ('user.manage', 'role.manage', 'location.manage'):
        _permission(connection, scope.role_id, code)
    safe_role = f'{prefix}-SAFE'
    _role(connection, scope.tenant_id, safe_role, ())
    elevated_permission = f'{prefix}.elevated'
    elevated_role = f'{prefix}-ELEVATED'
    _role(connection, scope.tenant_id, elevated_role, (elevated_permission,))
    unknown_user, _ = _user(connection, prefix, 'unknown-role')
    elevated_user, _ = _user(connection, prefix, 'elevated-role')
    ungranted_user, _ = _user(connection, prefix, 'ungranted-location')
    foreign_user, _ = _user(connection, prefix, 'foreign-location')
    disabled_user, _ = _user(connection, prefix, 'disabled', status='DISABLED')

    other_organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'OTHER','Other','ACTIVE')",
        (scope.tenant_id,),
    )
    ungranted_location_id = _execute(
        connection,
        'INSERT INTO locations '
        '(tenant_id,organization_id,code,name,timezone,status) '
        "VALUES (%s,%s,'NO-GRANT','No Grant','America/Mexico_City','ACTIVE')",
        (scope.tenant_id, other_organization_id),
    )
    foreign_scope = _scope(connection, f'{prefix}-foreign')

    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _headers(client, scope)
        unknown = client.post('/identity/access-provisioning', headers=headers, json=_payload(
            unknown_user, f'{prefix}-DOES-NOT-EXIST',
            scope.organization_id, scope.location_id,
        ))
        assert unknown.status_code == 409
        elevated = client.post('/identity/access-provisioning', headers=headers, json=_payload(
            elevated_user, elevated_role, scope.organization_id, scope.location_id,
        ))
        assert elevated.status_code == 403
        ungranted = client.post('/identity/access-provisioning', headers=headers, json=_payload(
            ungranted_user, safe_role, other_organization_id, ungranted_location_id,
        ))
        assert ungranted.status_code == 403
        foreign = client.post('/identity/access-provisioning', headers=headers, json=_payload(
            foreign_user, safe_role,
            foreign_scope.organization_id, foreign_scope.location_id,
        ))
        assert foreign.status_code == 409
        disabled = client.post('/identity/access-provisioning', headers=headers, json=_payload(
            disabled_user, safe_role, scope.organization_id, scope.location_id,
        ))
        assert disabled.status_code == 409

        unauthorized_scope = _scope(connection, f'{prefix}-unauthorized')
        unauthorized_target, _ = _user(connection, prefix, 'unauthorized-actor')
        unauthorized_role = f'{prefix}-UNAUTHORIZED-SAFE'
        _role(connection, unauthorized_scope.tenant_id, unauthorized_role, ())
        unauthorized_headers = _headers(client, unauthorized_scope)
        unauthorized = client.post(
            '/identity/access-provisioning', headers=unauthorized_headers,
            json=_payload(
                unauthorized_target, unauthorized_role,
                unauthorized_scope.organization_id, unauthorized_scope.location_id,
            ),
        )
        assert unauthorized.status_code == 403

    assert _membership_count(
        connection, scope.tenant_id,
        (unknown_user, elevated_user, ungranted_user, foreign_user, disabled_user),
    ) == 0
    assert _membership_count(
        connection, unauthorized_scope.tenant_id, (unauthorized_target,),
    ) == 0


def test_concurrent_equivalent_access_plans_converge_once(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, f'{prefix}-race')
    for code in ('user.manage', 'role.manage', 'location.manage', 'product.read'):
        _permission(connection, scope.role_id, code)
    target_user_id, _ = _user(connection, prefix, 'target-race')
    role_name = f'{prefix}-RACE-SAFE'
    role_id = _role(connection, scope.tenant_id, role_name, ('product.read',))
    candidate = access_provisioning.LocationGrantCandidate(
        organization_id=scope.organization_id,
        location_id=scope.location_id,
    )

    async def exercise():
        from app.db.session import DatabaseManager

        database = DatabaseManager(integration_settings)
        try:
            async with (
                database.session_factory() as first_db,
                database.session_factory() as second_db,
            ):
                return await asyncio.gather(
                    access_provisioning.provision_access(
                        first_db, tenant_id=scope.tenant_id,
                        actor_membership_id=scope.membership_id,
                        user_id=target_user_id, role_name=role_name,
                        locations=(candidate,),
                    ),
                    access_provisioning.provision_access(
                        second_db, tenant_id=scope.tenant_id,
                        actor_membership_id=scope.membership_id,
                        user_id=target_user_id, role_name=role_name,
                        locations=(candidate,),
                    ),
                )
        finally:
            await database.dispose()

    results = asyncio.run(exercise())
    assert {value.membership_operation for value in results} == {'CREATE', 'UNCHANGED'}
    assert {value.role_operation for value in results} == {'CREATE', 'UNCHANGED'}
    assert {
        value.location_grants[0].operation for value in results
    } == {'CREATE', 'UNCHANGED'}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s',
            (scope.tenant_id, target_user_id),
        )
        membership_id = cursor.fetchone()['id']
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM membership_roles '
            'WHERE membership_id=%s AND role_id=%s',
            (membership_id, role_id),
        )
        assert cursor.fetchone()['amount'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM membership_location_grants '
            'WHERE membership_id=%s AND location_id=%s',
            (membership_id, scope.location_id),
        )
        assert cursor.fetchone()['amount'] == 1
