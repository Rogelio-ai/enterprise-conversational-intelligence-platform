from __future__ import annotations

from uuid import uuid4

from app.core.security import hash_password
from app.restaurant.integrations.payments.contracts import PaymentExecutionOutcome
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from test_canonical_order_commercial_acceptance import (
    PASSWORD,
    Scope,
    _confirm,
    _open_and_join,
    _preview,
    _product,
    _scope,
    _staff_headers,
)
from test_restaurant_payment_settlement_foundation import (
    _check,
    _client,
    _electronic_payload,
    _grant,
)


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _membership(
    connection,
    *,
    tenant_id: int,
    slug: str,
    permissions: tuple[str, ...],
) -> tuple[str, int]:
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) '
        'VALUES (%s,%s,%s,%s)',
        (email, hash_password(PASSWORD), slug, 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, f'CHECK_{uuid4().hex}', 'Check query tests', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) '
        'VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for code in permissions:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
            (role_id, permission_id),
        )
    return email, membership_id


def _membership_id(connection, email: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tm.id FROM tenant_memberships tm '
            'JOIN users u ON u.id=tm.user_id WHERE u.email=%s',
            (email,),
        )
        return int(cursor.fetchone()['id'])


def _grant_location(connection, tenant_id: int, membership_id: int, location_id: int):
    _execute(
        connection,
        'INSERT INTO membership_location_grants '
        '(tenant_id,membership_id,location_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, location_id),
    )


def _table_scope(connection, scope: Scope, suffix: str) -> Scope:
    resource_id = _execute(
        connection,
        'INSERT INTO resources '
        '(tenant_id,location_id,code,name,resource_type,status) '
        'VALUES (%s,%s,%s,%s,%s,%s)',
        (
            scope.tenant_id,
            scope.location_id,
            f'T-{suffix}-{uuid4().hex[:8]}',
            f'Table {suffix}',
            'TABLE',
            'ACTIVE',
        ),
    )
    return Scope(
        scope.tenant_id,
        scope.organization_id,
        scope.location_id,
        resource_id,
        scope.email,
    )


def _other_location(connection, scope: Scope, suffix: str) -> Scope:
    location_id = _execute(
        connection,
        'INSERT INTO locations '
        '(tenant_id,organization_id,code,name,timezone,country_code,status) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s)',
        (
            scope.tenant_id,
            scope.organization_id,
            f'LOC-{suffix}-{uuid4().hex[:8]}',
            f'Location {suffix}',
            'America/Mexico_City',
            'MX',
            'ACTIVE',
        ),
    )
    resource_id = _execute(
        connection,
        'INSERT INTO resources '
        '(tenant_id,location_id,code,name,resource_type,status) '
        'VALUES (%s,%s,%s,%s,%s,%s)',
        (
            scope.tenant_id,
            location_id,
            f'T-{suffix}-{uuid4().hex[:8]}',
            f'Table {suffix}',
            'TABLE',
            'ACTIVE',
        ),
    )
    return Scope(
        scope.tenant_id,
        scope.organization_id,
        location_id,
        resource_id,
        scope.email,
    )


def _new_check(client, connection, scope: Scope, key: str, amount: str = '100'):
    _, diner_headers = _open_and_join(client, scope, name=key)
    product_id = _product(connection, scope, name=f'Product {key}', amount=amount)
    preview = _preview(client, diner_headers, product_id)
    confirmed = _confirm(client, diner_headers, preview, f'order-{key}')
    assert confirmed.status_code == 201, confirmed.text
    return _check(client, diner_headers, f'check-{key}'), diner_headers


def _cash_payment(client, staff_headers, check, diner_id: int, amount: str, key: str):
    return client.post(
        f"/restaurant-checks/{check['id']}/payments",
        headers={**staff_headers, 'Idempotency-Key': key},
        json={
            'expected_check_version': check['version'],
            'expected_check_fingerprint': check['fingerprint'],
            'amount': amount,
            'currency': check['currency'],
            'method_category': 'CASH',
            'payer_type': 'DINER',
            'payer_diner_session_id': diner_id,
            'cash_tendered_amount': amount,
        },
    )


def test_staff_check_query_projects_financial_truth_and_is_stable(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    owner_membership_id = _membership_id(connection, scope.email)
    _grant_location(
        connection, scope.tenant_id, owner_membership_id, scope.location_id
    )
    other_location = _other_location(connection, scope, 'OTHER')
    _grant_location(
        connection,
        scope.tenant_id,
        owner_membership_id,
        other_location.location_id,
    )
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,)
    )

    with _client(integration_settings, executor) as client:
        staff_headers = _staff_headers(client, scope)
        empty = client.get(
            '/restaurant-checks',
            headers=staff_headers,
            params={'location_id': other_location.location_id},
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()['items'] == []

        partial, partial_headers = _new_check(
            client, connection, _table_scope(connection, scope, 'PARTIAL'), 'partial'
        )
        partial_diner_id = client.get(
            '/diner-session', headers=partial_headers
        ).json()['id']
        partial_payment = _cash_payment(
            client, staff_headers, partial, partial_diner_id, '40', 'partial-40'
        )
        assert partial_payment.status_code == 201, partial_payment.text

        uncertain, uncertain_headers = _new_check(
            client,
            connection,
            _table_scope(connection, scope, 'UNCERTAIN'),
            'uncertain',
        )
        uncertain_diner_id = client.get(
            '/diner-session', headers=uncertain_headers
        ).json()['id']
        uncertain_payment = client.post(
            f"/diner/restaurant-checks/{uncertain['id']}/payments",
            headers={**uncertain_headers, 'Idempotency-Key': 'uncertain-25'},
            json=_electronic_payload(uncertain, '25', uncertain_diner_id),
        )
        assert uncertain_payment.status_code == 201, uncertain_payment.text
        assert uncertain_payment.json()['state'] == 'UNCERTAIN'

        settled, settled_headers = _new_check(
            client, connection, _table_scope(connection, scope, 'SETTLED'), 'settled'
        )
        settled_diner_id = client.get(
            '/diner-session', headers=settled_headers
        ).json()['id']
        settled_payment = _cash_payment(
            client, staff_headers, settled, settled_diner_id, '100', 'settled-100'
        )
        assert settled_payment.status_code == 201, settled_payment.text

        opened, _ = _new_check(
            client, connection, _table_scope(connection, scope, 'OPEN'), 'open'
        )
        foreign_location_check, _ = _new_check(
            client, connection, other_location, 'other-location'
        )

        url = '/restaurant-checks'
        params = {'location_id': scope.location_id, 'limit': 100, 'offset': 0}
        before_counts = {}
        with connection.cursor() as cursor:
            for table in (
                'restaurant_checks',
                'restaurant_payments',
                'restaurant_check_settlements',
            ):
                cursor.execute(f'SELECT COUNT(*) AS count FROM {table}')
                before_counts[table] = cursor.fetchone()['count']

        first = client.get(url, headers=staff_headers, params=params)
        repeated = client.get(url, headers=staff_headers, params=params)
        assert first.status_code == 200, first.text
        assert repeated.json() == first.json()
        items = first.json()['items']
        assert [item['id'] for item in items] == [
            partial['id'],
            uncertain['id'],
            settled['id'],
            opened['id'],
        ]
        assert foreign_location_check['id'] not in {item['id'] for item in items}

        by_id = {item['id']: item for item in items}
        assert by_id[partial['id']]['status'] == 'FROZEN'
        assert by_id[partial['id']]['liability_total'] == '100.0000'
        assert by_id[partial['id']]['confirmed_settlement'] == '40.0000'
        assert by_id[partial['id']]['outstanding'] == '60.0000'
        assert by_id[partial['id']]['available_to_initiate'] == '60.0000'
        assert by_id[uncertain['id']]['uncertain_exposure'] == '25.0000'
        assert by_id[uncertain['id']]['reserved_financial_exposure'] == '25.0000'
        assert by_id[uncertain['id']]['available_to_initiate'] == '75.0000'
        assert by_id[settled['id']]['status'] == 'SETTLED'
        assert by_id[settled['id']]['confirmed_settlement'] == '100.0000'
        assert by_id[settled['id']]['outstanding'] == '0.0000'
        assert by_id[opened['id']]['status'] == 'OPEN'

        frozen = client.get(
            url,
            headers=staff_headers,
            params={'location_id': scope.location_id, 'status': 'FROZEN'},
        )
        assert [item['id'] for item in frozen.json()['items']] == [
            partial['id'], uncertain['id']
        ]
        page = client.get(
            url,
            headers=staff_headers,
            params={'location_id': scope.location_id, 'limit': 2, 'offset': 1},
        )
        assert [item['id'] for item in page.json()['items']] == [
            uncertain['id'], settled['id']
        ]
        assert client.get(
            url,
            headers=staff_headers,
            params={'location_id': scope.location_id, 'limit': 101},
        ).status_code == 422

        detail = client.get(
            f"/restaurant-checks/{partial['id']}",
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert detail.status_code == 200, detail.text
        for field in (
            'liability_total',
            'confirmed_settlement',
            'outstanding',
            'uncertain_exposure',
        ):
            assert detail.json()[field] == by_id[partial['id']][field]

        with connection.cursor() as cursor:
            for table, expected in before_counts.items():
                cursor.execute(f'SELECT COUNT(*) AS count FROM {table}')
                assert cursor.fetchone()['count'] == expected


def test_staff_check_query_and_detail_enforce_location_and_permission(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    owner_membership_id = _membership_id(connection, scope.email)
    _grant_location(
        connection, scope.tenant_id, owner_membership_id, scope.location_id
    )
    permission_email, permission_membership_id = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-permission-no-grant',
        permissions=('restaurant_check.read',),
    )
    no_permission_email, no_permission_membership_id = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-grant-no-permission',
        permissions=(),
    )
    _grant_location(
        connection,
        scope.tenant_id,
        no_permission_membership_id,
        scope.location_id,
    )
    foreign = _scope(connection, f'{prefix}-foreign')
    _grant(connection, foreign.tenant_id, configure_executor=False)
    foreign_membership_id = _membership_id(connection, foreign.email)
    _grant_location(
        connection, foreign.tenant_id, foreign_membership_id, foreign.location_id
    )

    with _client(integration_settings) as client:
        check, _ = _new_check(client, connection, scope, 'secured')
        owner_headers = _staff_headers(client, scope)
        permission_headers = _login(client, permission_email)
        no_permission_headers = _login(client, no_permission_email)
        foreign_headers = _staff_headers(client, foreign)
        params = {'location_id': scope.location_id}

        allowed = client.get('/restaurant-checks', headers=owner_headers, params=params)
        assert allowed.status_code == 200, allowed.text
        assert [item['id'] for item in allowed.json()['items']] == [check['id']]
        assert client.get(
            f"/restaurant-checks/{check['id']}",
            headers=owner_headers,
            params=params,
        ).status_code == 200

        for headers, expected_status in (
            (permission_headers, 404),
            (no_permission_headers, 403),
            (foreign_headers, 404),
        ):
            denied = client.get('/restaurant-checks', headers=headers, params=params)
            assert denied.status_code == expected_status
            assert 'liability_total' not in denied.text
            detail = client.get(
                f"/restaurant-checks/{check['id']}",
                headers=headers,
                params=params,
            )
            assert detail.status_code == expected_status
            assert 'liability_total' not in detail.text

        assert client.get(
            f"/restaurant-checks/{check['id']}",
            headers=owner_headers,
            params={'location_id': foreign.location_id},
        ).status_code == 404


def _login(client, email: str) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': email, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}
