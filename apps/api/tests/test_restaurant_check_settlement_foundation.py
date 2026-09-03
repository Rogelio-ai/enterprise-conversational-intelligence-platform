from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _open_and_join,
    _preview,
    _product,
    _scope,
    _staff_headers,
)


def _client(integration_settings):
    return TestClient(create_app(settings=integration_settings))


def _grant_check_permissions(connection, tenant_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1', (tenant_id,))
        role_id = cursor.fetchone()['id']
        for code in ('restaurant_check.read', 'restaurant_check.manage'):
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = cursor.fetchone()['id']
            cursor.execute(
                'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
                (role_id, permission_id),
            )


def _accepted_order(client, connection, scope, diner_headers, *, amount='150'):
    product_id = _product(connection, scope, amount=amount)
    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, f'accept-{product_id}')
    assert accepted.status_code == 201, accepted.text
    return accepted.json()


def _join(client, opened: dict, name: str) -> dict[str, str]:
    response = client.post('/diner-sessions/join', json={
        'join_context_key': opened['join_context_key'],
        'access_code': opened['access_code'],
        'display_name': name,
    })
    assert response.status_code == 201, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def test_personal_check_ordering_lock_views_gratuity_freeze_and_close_guard(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, diner_headers = _open_and_join(client, scope)
        order = _accepted_order(client, connection, scope, diner_headers)
        created = client.post(
            '/diner/restaurant-checks', headers={**diner_headers, 'Idempotency-Key': 'personal-check'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert created.status_code == 201, created.text
        check = created.json()
        assert Decimal(check['consumption_total']) == Decimal(order['payable_total'])
        assert check['member_ids']

        replay = client.post(
            '/diner/restaurant-checks', headers={**diner_headers, 'Idempotency-Key': 'personal-check'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert replay.status_code == 200 and replay.json()['id'] == check['id']
        blocked = client.post('/diner/order-draft', headers=diner_headers)
        assert blocked.status_code == 409
        assert blocked.json()['error']['code'] == 'ORDERING_BLOCKED_BY_ACTIVE_CHECK'

        totalized = client.get(f"/diner/restaurant-checks/{check['id']}", headers=diner_headers)
        detailed = client.get(
            f"/diner/restaurant-checks/{check['id']}?view=detailed", headers=diner_headers
        )
        assert totalized.status_code == detailed.status_code == 200
        assert totalized.json()['liability_total'] == detailed.json()['liability_total']
        assert detailed.json()['details'][0]['diners'][0]['orders'][0]['order_id'] == order['id']

        gratuity = client.put(
            f"/diner/restaurant-checks/{check['id']}/gratuity",
            headers={**diner_headers, 'Idempotency-Key': 'tip-1'},
            json={'expected_version': 1, 'input_type': 'PERCENTAGE', 'input_value': '10'},
        )
        assert gratuity.status_code == 200, gratuity.text
        assert Decimal(gratuity.json()['gratuity_total']) == Decimal(order['payable_total']) * Decimal('0.10')
        stale = client.put(
            f"/diner/restaurant-checks/{check['id']}/gratuity",
            headers={**diner_headers, 'Idempotency-Key': 'tip-stale'},
            json={'expected_version': 1, 'input_type': 'FIXED_AMOUNT', 'input_value': '12.345'},
        )
        assert stale.status_code == 409
        assert stale.json()['error']['code'] == 'CHECK_VERSION_CONFLICT'
        fixed = client.put(
            f"/diner/restaurant-checks/{check['id']}/gratuity",
            headers={**diner_headers, 'Idempotency-Key': 'tip-fixed'},
            json={'expected_version': 2, 'input_type': 'FIXED_AMOUNT', 'input_value': '12.345'},
        )
        assert fixed.status_code == 200, fixed.text
        assert Decimal(fixed.json()['gratuity_total']) == Decimal('12.34')
        frozen = client.post(
            f"/diner/restaurant-checks/{check['id']}/confirm-for-settlement",
            headers={**diner_headers, 'Idempotency-Key': 'freeze-1'},
            json={'expected_version': 3},
        )
        assert frozen.status_code == 200, frozen.text
        assert frozen.json()['status'] == 'FROZEN'
        close = client.post(
            f"/restaurant-service-sessions/{opened['id']}/close",
            headers=_staff_headers(client, scope),
        )
        assert close.status_code == 409
        assert close.json()['error']['code'] == 'TABLE_OUTSTANDING_BALANCE_NOT_ZERO'

    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_check_versions WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone()['count'] == 3
        cursor.execute('SELECT state,ownership_slot FROM restaurant_check_allocations WHERE check_id=%s', (check['id'],))
        assert cursor.fetchone() == {'state': 'CLAIMED', 'ownership_slot': 1}
        cursor.execute(
            "UPDATE restaurant_check_allocations SET state='SETTLED',settled_at=CURRENT_TIMESTAMP,"
            "settlement_reference='ws22-test-fixture' WHERE check_id=%s",
            (check['id'],),
        )
        cursor.execute(
            "UPDATE restaurant_check_members SET active_slot=NULL,released_at=CURRENT_TIMESTAMP,"
            "released_actor_type='SYSTEM',released_actor_reference='ws22-test-fixture',"
            "release_reason='SETTLEMENT_COMPLETED',released_version=3 WHERE check_id=%s",
            (check['id'],),
        )
    with _client(integration_settings) as client:
        balance = client.get(
            f"/restaurant-service-sessions/{opened['id']}/outstanding-balance",
            headers=_staff_headers(client, scope),
        )
        assert balance.status_code == 200, balance.text
        assert Decimal(balance.json()['outstanding_confirmed_balance']) == Decimal('0')
        assert Decimal(balance.json()['pending_exposure']) == Decimal('12.34')
        assert balance.json()['closure_eligible'] is False


def test_nonempty_draft_abandon_then_check_and_cancel_releases_lock(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        _, diner_headers = _open_and_join(client, scope)
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        order = _accepted_order(client, connection, scope, diner_headers, amount='90')
        product_id = _product(connection, scope, name='Extra', amount='20')
        preview = _preview(client, diner_headers, product_id)
        rejected = client.post(
            '/diner/restaurant-checks', headers={**diner_headers, 'Idempotency-Key': 'draft-blocked'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert rejected.status_code == 409
        assert rejected.json()['error']['code'] == 'DINER_HAS_ACTIVE_ORDER_DRAFT'
        abandoned = client.post(
            '/diner/order-draft/abandon', headers={**diner_headers, 'Idempotency-Key': 'abandon-1'},
            json={'expected_version': preview['draft_version']},
        )
        assert abandoned.status_code == 204, abandoned.text
        created = client.post(
            '/diner/restaurant-checks', headers={**diner_headers, 'Idempotency-Key': 'after-abandon'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert created.status_code == 201, created.text
        cancelled = client.post(
            f"/diner/restaurant-checks/{created.json()['id']}/cancellation",
            headers={**diner_headers, 'Idempotency-Key': 'cancel-1'},
            json={'expected_version': 1, 'reason': 'customer changed mind'},
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()['status'] == 'CANCELLED'
        reacquired = client.post(
            '/diner/restaurant-checks',
            headers={**diner_headers, 'Idempotency-Key': 'after-cancel-reacquire'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert reacquired.status_code == 201, reacquired.text
        recancelled = client.post(
            f"/diner/restaurant-checks/{reacquired.json()['id']}/cancellation",
            headers={**diner_headers, 'Idempotency-Key': 'cancel-reacquired'},
            json={'expected_version': 1, 'reason': 'nullable-slot certification'},
        )
        assert recancelled.status_code == 200, recancelled.text
        next_draft = client.post('/diner/order-draft', headers=diner_headers)
        assert next_draft.status_code == 201, next_draft.text

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status,abandoned_actor_type,abandon_idempotency_key FROM order_drafts "
            "WHERE tenant_id=%s AND status='ABANDONED' ORDER BY id DESC LIMIT 1",
            (scope.tenant_id,),
        )
        row = cursor.fetchone()
        assert row == {'status': 'ABANDONED', 'abandoned_actor_type': 'DINER', 'abandon_idempotency_key': 'abandon-1'}
        cursor.execute('SELECT active_slot,released_at FROM restaurant_check_members WHERE check_id=%s', (created.json()['id'],))
        released = cursor.fetchone()
        assert released['active_slot'] is None and released['released_at'] is not None
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_members '
            'WHERE tenant_id=%s AND diner_session_id=%s AND active_slot IS NULL',
            (scope.tenant_id, diner_id),
        )
        assert cursor.fetchone()['count'] == 2
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_allocations '
            'WHERE tenant_id=%s AND restaurant_order_id=%s AND ownership_slot IS NULL',
            (scope.tenant_id, order['id']),
        )
        assert cursor.fetchone()['count'] == 2


def test_simultaneous_personal_check_has_one_winner(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        _, diner_headers = _open_and_join(client, scope)
        _accepted_order(client, connection, scope, diner_headers, amount='75')

        def create(key):
            return client.post('/diner/restaurant-checks', headers={**diner_headers, 'Idempotency-Key': key}, json={'mode': 'INDIVIDUAL'})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, ('race-a', 'race-b')))
        assert sorted(value.status_code for value in responses) == [201, 409]
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 1
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_check_members WHERE tenant_id=%s AND active_slot=1', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 1


def test_simultaneous_whole_table_checks_have_one_atomic_winner(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, first_headers = _open_and_join(client, scope, name='First')
        second_headers = _join(client, opened, 'Second')
        _accepted_order(client, connection, scope, first_headers, amount='61')
        _accepted_order(client, connection, scope, second_headers, amount='39')

        def create(key):
            return client.post(
                '/diner/restaurant-checks',
                headers={**first_headers, 'Idempotency-Key': key},
                json={'mode': 'GLOBAL_TABLE'},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, ('global-race-a', 'global-race-b')))
        assert sorted(value.status_code for value in responses) == [201, 409]
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_members '
            'WHERE tenant_id=%s AND active_slot=1',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 2
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_allocations '
            'WHERE tenant_id=%s AND ownership_slot=1',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 2


def test_check_creation_vs_order_confirmation_preserves_complete_liability(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        _, diner_headers = _open_and_join(client, scope)
        _accepted_order(client, connection, scope, diner_headers, amount='55')
        preview = _preview(
            client, diner_headers,
            _product(connection, scope, name='Concurrent dessert', amount='25'),
        )

        def create():
            return client.post(
                '/diner/restaurant-checks',
                headers={**diner_headers, 'Idempotency-Key': 'create-confirm-race-check'},
                json={'mode': 'INDIVIDUAL'},
            )

        def confirm():
            return _confirm(client, diner_headers, preview, 'create-confirm-race-order')

        with ThreadPoolExecutor(max_workers=2) as pool:
            create_future = pool.submit(create)
            confirm_future = pool.submit(confirm)
            create_response = create_future.result()
            confirm_response = confirm_future.result()
        assert confirm_response.status_code == 201, confirm_response.text
        assert create_response.status_code in (201, 409), create_response.text
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 2
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_allocations WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        allocation_count = cursor.fetchone()['count']
        assert allocation_count == (2 if create_response.status_code == 201 else 0)


def test_member_addition_vs_order_confirmation_never_leaves_active_member_incomplete(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, controller_headers = _open_and_join(client, scope, name='Controller')
        candidate_headers = _join(client, opened, 'Candidate')
        _accepted_order(client, connection, scope, controller_headers, amount='80')
        _accepted_order(client, connection, scope, candidate_headers, amount='10')
        candidate_id = client.get('/diner-session', headers=candidate_headers).json()['id']
        check = client.post(
            '/diner/restaurant-checks',
            headers={**controller_headers, 'Idempotency-Key': 'add-confirm-base'},
            json={'mode': 'INDIVIDUAL'},
        ).json()
        preview = _preview(
            client, candidate_headers,
            _product(connection, scope, name='Concurrent beverage', amount='10'),
        )

        def add():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/members",
                headers={**controller_headers, 'Idempotency-Key': 'add-confirm-member'},
                json={'expected_version': 1, 'diner_session_id': candidate_id},
            )

        def confirm():
            return _confirm(client, candidate_headers, preview, 'add-confirm-order')

        with ThreadPoolExecutor(max_workers=2) as pool:
            add_future = pool.submit(add)
            confirm_future = pool.submit(confirm)
            add_response = add_future.result()
            confirm_response = confirm_future.result()
        assert confirm_response.status_code == 201, confirm_response.text
        assert add_response.status_code in (200, 409), add_response.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_members '
            'WHERE check_id=%s AND diner_session_id=%s AND active_slot=1',
            (check['id'], candidate_id),
        )
        active = cursor.fetchone()['count']
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_allocations '
            'WHERE check_id=%s AND source_diner_session_id=%s AND ownership_slot=1',
            (check['id'], candidate_id),
        )
        allocated = cursor.fetchone()['count']
        assert (active, allocated) == ((1, 2) if add_response.status_code == 200 else (0, 0))


def test_global_table_and_staff_ordering_bypass_are_atomic(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, first_headers = _open_and_join(client, scope, name='First')
        second_headers = _join(client, opened, 'Second')
        _accepted_order(client, connection, scope, first_headers, amount='60')
        _accepted_order(client, connection, scope, second_headers, amount='40')
        created = client.post('/diner/restaurant-checks', headers={**first_headers, 'Idempotency-Key': 'global'}, json={'mode': 'GLOBAL_TABLE'})
        assert created.status_code == 201, created.text
        assert len(created.json()['member_ids']) == 2
        second = client.get('/diner-session', headers=second_headers).json()
        staff_headers = _staff_headers(client, scope)
        transferred = client.post(
            f"/restaurant-checks/{created.json()['id']}/controller",
            headers={**staff_headers, 'Idempotency-Key': 'controller-transfer'},
            json={'expected_version': 1, 'diner_session_id': second['id']},
        )
        assert transferred.status_code == 200, transferred.text
        assert transferred.json()['controller_diner_session_id'] == second['id']
        assert transferred.json()['version'] == 2
        staff_bypass = client.post(
            f"/conversations/{second['conversation_id']}/order-draft",
            headers=staff_headers,
        )
        assert staff_bypass.status_code == 409
        assert staff_bypass.json()['error']['code'] == 'ORDERING_BLOCKED_BY_ACTIVE_CHECK'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT diner_session_id,relationship FROM restaurant_check_members '
            'WHERE check_id=%s ORDER BY diner_session_id',
            (created.json()['id'],),
        )
        relationships = {row['diner_session_id']: row['relationship'] for row in cursor.fetchall()}
        assert relationships[second['id']] == 'CONTROLLER'
        assert sorted(relationships.values()) == ['CONTROLLER', 'INCLUDED']


def test_global_table_includes_only_eligible_diners_plus_controller(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, controller_headers = _open_and_join(client, scope, name='Payer')
        consuming_headers = _join(client, opened, 'Consumed')
        draft_only_headers = _join(client, opened, 'Draft only')
        order = _accepted_order(client, connection, scope, consuming_headers, amount='95')
        _preview(
            client, draft_only_headers,
            _product(connection, scope, name='Unaccepted draft item', amount='5'),
        )
        controller_id = client.get('/diner-session', headers=controller_headers).json()['id']
        consuming_id = client.get('/diner-session', headers=consuming_headers).json()['id']
        draft_only_id = client.get('/diner-session', headers=draft_only_headers).json()['id']
        response = client.post(
            '/diner/restaurant-checks',
            headers={**controller_headers, 'Idempotency-Key': 'eligible-global'},
            json={'mode': 'GLOBAL_TABLE'},
        )
        assert response.status_code == 201, response.text
        check = response.json()
        assert set(check['member_ids']) == {controller_id, consuming_id}
        assert draft_only_id not in check['member_ids']
        assert Decimal(check['consumption_total']) == Decimal(order['payable_total'])
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT source_diner_session_id FROM restaurant_check_allocations WHERE check_id=%s',
            (check['id'],),
        )
        assert {row['source_diner_session_id'] for row in cursor.fetchall()} == {consuming_id}


def test_remove_member_vs_freeze_has_one_invariant_preserving_winner(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, first_headers = _open_and_join(client, scope, name='Controller')
        second_headers = _join(client, opened, 'Included')
        _accepted_order(client, connection, scope, first_headers, amount='70')
        _accepted_order(client, connection, scope, second_headers, amount='30')
        second_id = client.get('/diner-session', headers=second_headers).json()['id']
        check = client.post(
            '/diner/restaurant-checks',
            headers={**first_headers, 'Idempotency-Key': 'remove-freeze-check'},
            json={'mode': 'GLOBAL_TABLE'},
        ).json()

        def remove():
            return client.delete(
                f"/diner/restaurant-checks/{check['id']}/members/{second_id}",
                headers={**first_headers, 'Idempotency-Key': 'remove-freeze-remove'},
                params={'expected_version': 1, 'reason': 'separate liability'},
            )

        def freeze():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/confirm-for-settlement",
                headers={**first_headers, 'Idempotency-Key': 'remove-freeze-freeze'},
                json={'expected_version': 1},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            remove_future = pool.submit(remove)
            freeze_future = pool.submit(freeze)
            responses = (remove_future.result(), freeze_future.result())
        assert sorted(value.status_code for value in responses) == [200, 409], [
            {'status': value.status_code, 'body': value.text} for value in responses
        ]
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,version FROM restaurant_checks WHERE id=%s', (check['id'],))
        state = cursor.fetchone()
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_members '
            'WHERE check_id=%s AND active_slot=1',
            (check['id'],),
        )
        active_members = cursor.fetchone()['count']
        cursor.execute(
            "SELECT COUNT(*) AS count FROM restaurant_check_allocations "
            "WHERE check_id=%s AND state='RELEASED' AND ownership_slot IS NULL",
            (check['id'],),
        )
        released = cursor.fetchone()['count']
        assert (state, active_members, released) in (
            ({'status': 'OPEN', 'version': 2}, 1, 1),
            ({'status': 'FROZEN', 'version': 1}, 2, 0),
        )


def test_member_release_vs_order_confirmation_serializes_on_diner_context(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, controller_headers = _open_and_join(client, scope, name='Controller')
        released_headers = _join(client, opened, 'Released')
        _accepted_order(client, connection, scope, controller_headers, amount='65')
        _accepted_order(client, connection, scope, released_headers, amount='35')
        released_id = client.get('/diner-session', headers=released_headers).json()['id']
        check = client.post(
            '/diner/restaurant-checks',
            headers={**controller_headers, 'Idempotency-Key': 'release-confirm-base'},
            json={'mode': 'GLOBAL_TABLE'},
        ).json()

        def release():
            return client.delete(
                f"/diner/restaurant-checks/{check['id']}/members/{released_id}",
                headers={**controller_headers, 'Idempotency-Key': 'release-confirm-release'},
                params={'expected_version': 1, 'reason': 'separate liability'},
            )

        def confirm():
            return client.post(
                '/diner/order/confirm',
                headers={**released_headers, 'Idempotency-Key': 'release-confirm-order'},
                json={
                    'expected_draft_version': 1,
                    'expected_commercial_fingerprint': '0' * 64,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            release_future = pool.submit(release)
            confirm_future = pool.submit(confirm)
            release_response = release_future.result()
            confirm_response = confirm_future.result()
        assert release_response.status_code == 200, release_response.text
        assert confirm_response.status_code in (404, 409), confirm_response.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT active_slot,released_at FROM restaurant_check_members '
            'WHERE check_id=%s AND diner_session_id=%s',
            (check['id'], released_id),
        )
        member = cursor.fetchone()
        assert member['active_slot'] is None and member['released_at'] is not None
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 2


def test_cancel_check_vs_order_confirmation_serializes_without_new_consumption(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        _, diner_headers = _open_and_join(client, scope)
        _accepted_order(client, connection, scope, diner_headers, amount='44')
        check = client.post(
            '/diner/restaurant-checks',
            headers={**diner_headers, 'Idempotency-Key': 'cancel-confirm-base'},
            json={'mode': 'INDIVIDUAL'},
        ).json()

        def cancel():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/cancellation",
                headers={**diner_headers, 'Idempotency-Key': 'cancel-confirm-cancel'},
                json={'expected_version': 1, 'reason': 'customer cancelled'},
            )

        def confirm():
            return client.post(
                '/diner/order/confirm',
                headers={**diner_headers, 'Idempotency-Key': 'cancel-confirm-order'},
                json={
                    'expected_draft_version': 1,
                    'expected_commercial_fingerprint': '0' * 64,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            cancel_future = pool.submit(cancel)
            confirm_future = pool.submit(confirm)
            cancel_response = cancel_future.result()
            confirm_response = confirm_future.result()
        assert cancel_response.status_code == 200, cancel_response.text
        assert confirm_response.status_code in (404, 409), confirm_response.text
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,version FROM restaurant_checks WHERE id=%s', (check['id'],))
        assert cursor.fetchone() == {'status': 'CANCELLED', 'version': 2}
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 1


def test_add_member_vs_remove_member_has_one_consistent_composition(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with _client(integration_settings) as client:
        opened, controller_headers = _open_and_join(client, scope, name='Controller')
        removed_headers = _join(client, opened, 'Potential removal')
        added_headers = _join(client, opened, 'Potential addition')
        _accepted_order(client, connection, scope, controller_headers, amount='50')
        _accepted_order(client, connection, scope, removed_headers, amount='30')
        _accepted_order(client, connection, scope, added_headers, amount='20')
        controller_id = client.get('/diner-session', headers=controller_headers).json()['id']
        removed_id = client.get('/diner-session', headers=removed_headers).json()['id']
        added_id = client.get('/diner-session', headers=added_headers).json()['id']
        check = client.post(
            '/diner/restaurant-checks',
            headers={**controller_headers, 'Idempotency-Key': 'add-remove-base'},
            json={'mode': 'SELECTED', 'diner_session_ids': [controller_id, removed_id]},
        ).json()

        def add():
            return client.post(
                f"/diner/restaurant-checks/{check['id']}/members",
                headers={**controller_headers, 'Idempotency-Key': 'add-remove-add'},
                json={'expected_version': 1, 'diner_session_id': added_id},
            )

        def remove():
            return client.delete(
                f"/diner/restaurant-checks/{check['id']}/members/{removed_id}",
                headers={**controller_headers, 'Idempotency-Key': 'add-remove-remove'},
                params={'expected_version': 1, 'reason': 'separate liability'},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            add_future = pool.submit(add)
            remove_future = pool.submit(remove)
            responses = (add_future.result(), remove_future.result())
        assert sorted(value.status_code for value in responses) == [200, 409], [
            {'status': value.status_code, 'body': value.text} for value in responses
        ]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT diner_session_id FROM restaurant_check_members '
            'WHERE check_id=%s AND active_slot=1 ORDER BY diner_session_id',
            (check['id'],),
        )
        active_ids = {row['diner_session_id'] for row in cursor.fetchall()}
        assert active_ids in (
            {controller_id, removed_id, added_id},
            {controller_id},
        )
        cursor.execute(
            'SELECT source_diner_session_id FROM restaurant_check_allocations '
            'WHERE check_id=%s AND ownership_slot=1 ORDER BY source_diner_session_id',
            (check['id'],),
        )
        owned_ids = {row['source_diner_session_id'] for row in cursor.fetchall()}
        assert owned_ids == active_ids


def test_close_vs_new_order_acceptance_never_leaves_closed_unsettled_table(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    with _client(integration_settings) as client:
        opened, diner_headers = _open_and_join(client, scope)
        preview = _preview(
            client, diner_headers,
            _product(connection, scope, name='Race order', amount='42'),
        )
        staff_headers = _staff_headers(client, scope)

        def close():
            return client.post(
                f"/restaurant-service-sessions/{opened['id']}/close",
                headers=staff_headers,
            )

        def confirm():
            return _confirm(client, diner_headers, preview, 'close-order-race')

        with ThreadPoolExecutor(max_workers=2) as pool:
            close_future = pool.submit(close)
            confirm_future = pool.submit(confirm)
            close_response = close_future.result()
            confirm_response = confirm_future.result()
        assert (close_response.status_code, confirm_response.status_code) in (
            (200, 404),
            (409, 201),
        )
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM restaurant_service_sessions WHERE id=%s', (opened['id'],))
        session_status = cursor.fetchone()['status']
        cursor.execute(
            "SELECT COUNT(*) AS count FROM restaurant_orders "
            "WHERE service_session_id=%s AND status='ACCEPTED'",
            (opened['id'],),
        )
        accepted_count = cursor.fetchone()['count']
        assert not (session_status == 'CLOSED' and accepted_count > 0)


def test_multi_table_check_balance_continuation_and_multiple_cycles(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_check_permissions(connection, scope.tenant_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) "
            "VALUES (%s,%s,%s,'Second Table','TABLE','ACTIVE')",
            (scope.tenant_id, scope.location_id, f'{prefix}-T2'),
        )
        second_resource_id = int(cursor.lastrowid)
    with _client(integration_settings) as client:
        opened1, first_headers = _open_and_join(client, scope, name='Table One')
        opened2_response = client.post(
            f'/resources/{second_resource_id}/service-sessions',
            headers=_staff_headers(client, scope), json={'party_size': 2},
        )
        assert opened2_response.status_code == 201, opened2_response.text
        opened2 = opened2_response.json()
        second_headers = _join(client, opened2, 'Table Two')
        _accepted_order(client, connection, scope, first_headers, amount='80')
        _accepted_order(client, connection, scope, second_headers, amount='120')
        first_id = client.get('/diner-session', headers=first_headers).json()['id']
        second_id = client.get('/diner-session', headers=second_headers).json()['id']
        combined = client.post(
            '/diner/restaurant-checks',
            headers={**first_headers, 'Idempotency-Key': 'multi-table-1'},
            json={'mode': 'SELECTED', 'diner_session_ids': [first_id, second_id]},
        )
        assert combined.status_code == 201, combined.text
        check1 = combined.json()
        detailed = client.get(
            f"/diner/restaurant-checks/{check1['id']}?view=detailed", headers=first_headers
        )
        assert len(detailed.json()['details']) == 2
        frozen = client.post(
            f"/diner/restaurant-checks/{check1['id']}/confirm-for-settlement",
            headers={**first_headers, 'Idempotency-Key': 'freeze-multi-1'},
            json={'expected_version': 1},
        )
        assert frozen.status_code == 200, frozen.text

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE restaurant_check_allocations SET state='SETTLED',settled_at=CURRENT_TIMESTAMP,"
                "settlement_reference='ws22-test-fixture' WHERE check_id=%s",
                (check1['id'],),
            )
            cursor.execute(
                "UPDATE restaurant_check_members SET active_slot=NULL,released_at=CURRENT_TIMESTAMP,"
                "released_actor_type='SYSTEM',released_actor_reference='ws22-test-fixture',"
                "release_reason='SETTLEMENT_COMPLETED',released_version=1 WHERE check_id=%s",
                (check1['id'],),
            )
        balance1 = client.get(
            f"/restaurant-service-sessions/{opened1['id']}/outstanding-balance",
            headers=_staff_headers(client, scope),
        )
        assert balance1.status_code == 200
        assert Decimal(balance1.json()['outstanding_confirmed_balance']) == Decimal('0')
        # WS-23-B supersedes the former derived zero-balance signal: only an
        # actual fully settled Check with a durable PENDING decision emits it.
        # This WS-22 fixture mutates allocations only and therefore must not.
        assert balance1.json()['service_continuation_decision_required'] is False

        _accepted_order(client, connection, scope, first_headers, amount='35')
        positive = client.get(
            f"/restaurant-service-sessions/{opened1['id']}/outstanding-balance",
            headers=_staff_headers(client, scope),
        ).json()
        assert Decimal(positive['outstanding_confirmed_balance']) > 0
        assert positive['closure_eligible'] is False
        check2 = client.post(
            '/diner/restaurant-checks', headers={**first_headers, 'Idempotency-Key': 'cycle-2'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert check2.status_code == 201, check2.text
        assert check2.json()['id'] != check1['id']
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s', (scope.tenant_id,))
            assert cursor.fetchone()['count'] == 2
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_check_allocations '
                "WHERE check_id=%s AND state='SETTLED' AND ownership_slot=1",
                (check1['id'],),
            )
            assert cursor.fetchone()['count'] == 2
