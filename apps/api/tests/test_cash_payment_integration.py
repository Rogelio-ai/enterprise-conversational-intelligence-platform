from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from app.restaurant.payments import service as payment_service
from test_canonical_order_commercial_acceptance import (
    _execute,
    _open_and_join,
    _scope,
    _staff_headers,
)
from test_restaurant_payment_settlement_foundation import (
    _check,
    _electronic_payload,
    _grant,
    _order,
)


def _grant_cash_permissions(connection, tenant_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1',
            (tenant_id,),
        )
        role_id = cursor.fetchone()['id']
        for code in (
            'resource.manage', 'cash_session.manage', 'cash_management.read',
        ):
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = cursor.fetchone()['id']
            cursor.execute(
                'INSERT IGNORE INTO role_permissions (role_id,permission_id) '
                'VALUES (%s,%s)',
                (role_id, permission_id),
            )


def _register_and_session(
    client: TestClient, scope, headers: dict[str, str], *, code: str,
    currency: str = 'MXN', location_id: int | None = None,
) -> tuple[dict, dict]:
    register = client.post('/resources', headers=headers, json={
        'location_id': location_id or scope.location_id,
        'code': code,
        'name': code,
        'resource_type': 'CASH_REGISTER',
    })
    assert register.status_code == 201, register.text
    session = client.post(
        f"/resources/{register.json()['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': f'open-{code}'},
        json={'currency': currency},
    )
    assert session.status_code == 201, session.text
    return register.json(), session.json()


def _payment_payload(
    check: dict, *, amount: str, tendered: str,
    cash_session_id: int | None = None,
) -> dict:
    value = {
        'expected_check_version': check['version'],
        'expected_check_fingerprint': check['fingerprint'],
        'amount': amount,
        'currency': check['currency'],
        'method_category': 'CASH',
        'payer_type': 'OTHER',
        'payer_reference': 'cash customer',
        'cash_tendered_amount': tendered,
    }
    if cash_session_id is not None:
        value['cash_session_id'] = cash_session_id
    return value


def _prepared_check(client: TestClient, connection, scope, *, amount: str = '100'):
    _, diner_headers = _open_and_join(client, scope)
    _order(client, connection, scope, diner_headers, amount=amount)
    return _check(client, diner_headers, f'check-{uuid4().hex}')


def _location(connection, scope, *, other_organization: bool = False) -> int:
    organization_id = scope.organization_id
    if other_organization:
        organization_id = _execute(
            connection,
            "INSERT INTO organizations (tenant_id,code,name,status) "
            "VALUES (%s,%s,'Other Organization','ACTIVE')",
            (scope.tenant_id, f'ORG-{uuid4().hex[:12]}'),
        )
    return _execute(
        connection,
        "INSERT INTO locations "
        "(tenant_id,organization_id,code,name,timezone,country_code,status) "
        "VALUES (%s,%s,%s,'Other Location','America/Mexico_City','MX','ACTIVE')",
        (scope.tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'),
    )


def _close_empty_session(
    client: TestClient, headers: dict[str, str], session_id: int, key: str,
) -> None:
    count = client.post(
        f'/cash-sessions/{session_id}/counts',
        headers={**headers, 'Idempotency-Key': f'count-{key}'},
        json={'counted_amount': '0', 'currency': 'MXN'},
    )
    assert count.status_code == 201, count.text
    closed = client.post(
        f'/cash-sessions/{session_id}/close',
        headers={**headers, 'Idempotency-Key': f'close-{key}'},
        json={'cash_count_id': count.json()['id']},
    )
    assert closed.status_code == 200, closed.text


def test_activated_cash_requires_valid_open_scoped_session_and_allows_inactive_register(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _staff_headers(client, scope)
        register, valid = _register_and_session(
            client, scope, headers, code='VALID'
        )
        _, usd = _register_and_session(
            client, scope, headers, code='USD', currency='USD'
        )
        wrong_location_id = _location(connection, scope)
        _, wrong_location = _register_and_session(
            client, scope, headers, code='WRONG-LOCATION',
            location_id=wrong_location_id,
        )
        wrong_organization_id = _location(
            connection, scope, other_organization=True
        )
        _, wrong_organization = _register_and_session(
            client, scope, headers, code='WRONG-ORGANIZATION',
            location_id=wrong_organization_id,
        )
        _, closed = _register_and_session(
            client, scope, headers, code='CLOSED'
        )
        _close_empty_session(client, headers, closed['id'], 'closed')

        other = _scope(connection, f'{prefix}-other')
        _grant(connection, other.tenant_id, configure_executor=False)
        _grant_cash_permissions(connection, other.tenant_id)
        other_headers = _staff_headers(client, other)
        _, foreign = _register_and_session(
            client, other, other_headers, code='FOREIGN'
        )

        check = _prepared_check(client, connection, scope)
        url = f"/restaurant-checks/{check['id']}/payments"
        cases = (
            ('missing', None, 409, 'CASH_SESSION_REQUIRED'),
            ('unknown', 999999999, 404, 'CASH_SESSION_NOT_FOUND'),
            ('foreign', foreign['id'], 404, 'CASH_SESSION_NOT_FOUND'),
            ('location', wrong_location['id'], 409, 'INVALID_CASH_SESSION'),
            ('organization', wrong_organization['id'], 409, 'INVALID_CASH_SESSION'),
            ('currency', usd['id'], 409, 'INVALID_CASH_SESSION'),
            ('closed', closed['id'], 409, 'INVALID_CASH_SESSION'),
        )
        for key, session_id, expected_status, expected_code in cases:
            response = client.post(
                url,
                headers={**headers, 'Idempotency-Key': key},
                json=_payment_payload(
                    check, amount='40', tendered='40',
                    cash_session_id=session_id,
                ),
            )
            assert response.status_code == expected_status, response.text
            assert response.json()['error']['code'] == expected_code

        inactive = client.patch(
            f"/resources/{register['id']}", headers=headers,
            json={'status': 'INACTIVE'},
        )
        assert inactive.status_code == 200, inactive.text
        accepted = client.post(
            url,
            headers={**headers, 'Idempotency-Key': 'valid-inactive-register'},
            json=_payment_payload(
                check, amount='40', tendered='40',
                cash_session_id=valid['id'],
            ),
        )
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()['state'] == 'SUCCEEDED'

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 1


def test_tender_change_relationship_versions_replay_and_close_fencing(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _staff_headers(client, scope)
        _, session = _register_and_session(client, scope, headers, code='DRAWER')
        _, alternate = _register_and_session(client, scope, headers, code='ALTERNATE')
        check = _prepared_check(client, connection, scope)
        prior_count = client.post(
            f"/cash-sessions/{session['id']}/counts",
            headers={**headers, 'Idempotency-Key': 'prior-count'},
            json={'counted_amount': '0', 'currency': 'MXN'},
        )
        assert prior_count.status_code == 201, prior_count.text
        url = f"/restaurant-checks/{check['id']}/payments"
        payload = _payment_payload(
            check, amount='85', tendered='100',
            cash_session_id=session['id'],
        )
        created = client.post(
            url, headers={**headers, 'Idempotency-Key': 'cash-85'}, json=payload
        )
        replay = client.post(
            url, headers={**headers, 'Idempotency-Key': 'cash-85'}, json=payload
        )
        assert created.status_code == 201, created.text
        assert replay.status_code == 200, replay.text
        assert replay.json()['id'] == created.json()['id']
        payment_id = created.json()['id']

        changed_session = client.post(
            url,
            headers={**headers, 'Idempotency-Key': 'cash-85'},
            json={**payload, 'cash_session_id': alternate['id']},
        )
        assert changed_session.status_code == 409
        assert changed_session.json()['error']['code'] == 'PAYMENT_IDEMPOTENCY_CONFLICT'

        stale = client.post(
            f"/cash-sessions/{session['id']}/close",
            headers={**headers, 'Idempotency-Key': 'stale-close'},
            json={'cash_count_id': prior_count.json()['id']},
        )
        assert stale.status_code == 409
        assert stale.json()['error']['code'] == 'STALE_CASH_COUNT'

        final_count = client.post(
            f"/cash-sessions/{session['id']}/counts",
            headers={**headers, 'Idempotency-Key': 'final-count'},
            json={'counted_amount': '85', 'currency': 'MXN'},
        )
        assert final_count.status_code == 201, final_count.text
        closed = client.post(
            f"/cash-sessions/{session['id']}/close",
            headers={**headers, 'Idempotency-Key': 'final-close'},
            json={'cash_count_id': final_count.json()['id']},
        )
        assert closed.status_code == 200, closed.text
        after_close = client.post(
            url,
            headers={**headers, 'Idempotency-Key': 'after-close'},
            json=_payment_payload(
                check, amount='15', tendered='15',
                cash_session_id=session['id'],
            ),
        )
        assert after_close.status_code == 409
        assert after_close.json()['error']['code'] == 'INVALID_CASH_SESSION'

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT movement_type,amount,restaurant_payment_id '
            'FROM cash_movements WHERE cash_session_id=%s ORDER BY id',
            (session['id'],),
        )
        assert cursor.fetchall() == [
            {
                'movement_type': 'CUSTOMER_TENDER',
                'amount': 100,
                'restaurant_payment_id': payment_id,
            },
            {
                'movement_type': 'CUSTOMER_CHANGE',
                'amount': -15,
                'restaurant_payment_id': payment_id,
            },
        ]
        cursor.execute(
            'SELECT movement_version,status FROM cash_sessions WHERE id=%s',
            (session['id'],),
        )
        assert cursor.fetchone() == {'movement_version': 2, 'status': 'CLOSED'}
        cursor.execute(
            'SELECT amount FROM restaurant_check_settlements WHERE payment_id=%s',
            (payment_id,),
        )
        assert cursor.fetchone()['amount'] == 85
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE payment_id=%s',
            (payment_id,),
        )
        assert cursor.fetchone()['count'] == 1


def test_exact_tender_creates_only_tender_and_atomic_failure_rolls_back(
    integration_settings, sql_connection, monkeypatch,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _staff_headers(client, scope)
        _, session = _register_and_session(client, scope, headers, code='EXACT')
        check = _prepared_check(client, connection, scope, amount='100')
        exact = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**headers, 'Idempotency-Key': 'exact'},
            json=_payment_payload(
                check, amount='40', tendered='40',
                cash_session_id=session['id'],
            ),
        )
        assert exact.status_code == 201, exact.text

        async def fail_settlement(*args, **kwargs):
            raise RuntimeError('forced settlement failure')

        monkeypatch.setattr(payment_service, '_apply_success', fail_settlement)
        failed = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**headers, 'Idempotency-Key': 'forced-failure'},
            json=_payment_payload(
                check, amount='10', tendered='10',
                cash_session_id=session['id'],
            ),
        )
        assert failed.status_code == 500

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT movement_type,amount FROM cash_movements '
            'WHERE restaurant_payment_id=%s',
            (exact.json()['id'],),
        )
        assert cursor.fetchall() == [
            {'movement_type': 'CUSTOMER_TENDER', 'amount': 40},
        ]
        cursor.execute(
            'SELECT movement_version FROM cash_sessions WHERE id=%s',
            (session['id'],),
        )
        assert cursor.fetchone()['movement_version'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 1


def test_legacy_cash_and_non_cash_remain_without_cash_movements(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={'deterministic': executor},
    )) as client:
        headers = _staff_headers(client, scope)
        check = _prepared_check(client, connection, scope, amount='100')
        legacy = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**headers, 'Idempotency-Key': 'legacy-cash'},
            json=_payment_payload(check, amount='40', tendered='40'),
        )
        assert legacy.status_code == 201, legacy.text
        assert legacy.json()['state'] == 'SUCCEEDED'

        electronic = {
            **_electronic_payload(check, '60', 1),
            'payer_type': 'OTHER',
            'payer_diner_session_id': None,
            'payer_reference': 'card customer',
        }
        card = client.post(
            f"/restaurant-checks/{check['id']}/payments",
            headers={**headers, 'Idempotency-Key': 'card'},
            json=electronic,
        )
        assert card.status_code == 201, card.text
        assert card.json()['state'] == 'SUCCEEDED'

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT cash_management_activated_at FROM locations WHERE id=%s',
            (scope.location_id,),
        )
        assert cursor.fetchone()['cash_management_activated_at'] is None
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_movements WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 2
