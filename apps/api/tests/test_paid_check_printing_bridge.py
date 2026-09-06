from __future__ import annotations

import json
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.restaurant.paid_check_printing.service import result_fingerprint
from test_cash_payment_integration import (
    _grant_cash_permissions,
    _payment_payload,
    _prepared_check,
)
from test_canonical_order_commercial_acceptance import _scope, _staff_headers
from test_preparation_dispatch_operational_delivery import _connector
from test_restaurant_local_connector_machine_delivery import _provision
from test_restaurant_payment_settlement_foundation import _grant


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _cashier(client: TestClient, headers: dict[str, str], location_id: int, code: str):
    response = client.post('/resources', headers=headers, json={
        'location_id': location_id,
        'code': code,
        'name': f'{code} Cashier',
        'resource_type': 'CASH_REGISTER',
    })
    assert response.status_code == 201, response.text
    return response.json()


def _grant_connector_permissions(connection, tenant_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1',
            (tenant_id,),
        )
        role_id = cursor.fetchone()['id']
        for code in (
            'preparation.read', 'preparation.configure',
            'preparation.connector.manage',
        ):
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = cursor.fetchone()['id']
            cursor.execute(
                'INSERT IGNORE INTO role_permissions (role_id,permission_id) '
                'VALUES (%s,%s)',
                (role_id, permission_id),
            )


def _settle(
    client: TestClient, connection, scope, headers: dict[str, str], check: dict,
    *, cash_session_id: int | None = None,
) -> dict:
    response = client.post(
        f"/restaurant-checks/{check['id']}/payments",
        headers={**headers, 'Idempotency-Key': f"settle-{check['id']}"},
        json=_payment_payload(
            check,
            amount=str(check['liability_total']),
            tendered=str(check['liability_total']),
            cash_session_id=cash_session_id,
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()['state'] == 'SUCCEEDED'
    return response.json()


def _request(
    client: TestClient, headers: dict[str, str], check_id: int,
    cashier_id: int, connector_id: int, *, key: str, target: str = 'cashier_printer',
):
    return client.post(
        f'/restaurant-checks/{check_id}/paid-print',
        headers={**headers, 'Idempotency-Key': key},
        json={
            'cashier_resource_id': cashier_id,
            'connector_id': connector_id,
            'local_target_key': target,
        },
    )


def test_explicit_settled_print_is_durable_idempotent_and_intentionally_repeatable(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    _grant_connector_permissions(connection, scope.tenant_id)
    headers = _staff_headers(client, scope)
    check = _prepared_check(client, connection, scope, amount='125.50')

    _settle(client, connection, scope, headers, check)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM paid_check_dispatches '
            'WHERE restaurant_check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 0

    connector = _connector(client, headers, scope.location_id)
    cashier = _cashier(client, headers, scope.location_id, 'REGISTER-PRINT')
    first = _request(
        client, headers, check['id'], cashier['id'], connector['id'], key='print-1',
    )
    assert first.status_code == 201, first.text
    dispatch = first.json()
    assert dispatch['state'] == 'PENDING'
    assert dispatch['attempt_count'] == 0
    assert dispatch['cashier_resource_id'] == cashier['id']
    assert dispatch['connector_id'] == connector['id']

    replay = _request(
        client, headers, check['id'], cashier['id'], connector['id'], key='print-1',
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()['id'] == dispatch['id']
    conflict = _request(
        client, headers, check['id'], cashier['id'], connector['id'],
        key='print-1', target='different_printer',
    )
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'PAID_CHECK_PRINT_IDEMPOTENCY_CONFLICT'

    intentional = _request(
        client, headers, check['id'], cashier['id'], connector['id'], key='print-2',
    )
    assert intentional.status_code == 201, intentional.text
    assert intentional.json()['id'] != dispatch['id']
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM paid_check_dispatches '
            'WHERE restaurant_check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 2

        cursor.execute(
            'SELECT payload_text FROM paid_check_dispatches WHERE id=%s',
            (dispatch['id'],),
        )
        payload_text = cursor.fetchone()['payload_text']
    payload = json.loads(payload_text)
    assert payload['schema'] == 'paid-check-v1'
    assert payload['check']['status'] == 'SETTLED'
    assert Decimal(payload['check']['confirmed_paid_total']) == Decimal(
        str(check['liability_total'])
    )
    assert Decimal(payload['check']['outstanding_total']) == Decimal('0')
    assert payload['check']['orders'][0]['items'][0]['product_name']


def test_unsettled_and_cross_scope_targets_are_rejected_without_dispatch(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    _grant_connector_permissions(connection, scope.tenant_id)
    headers = _staff_headers(client, scope)
    check = _prepared_check(client, connection, scope, amount='80')
    connector = _connector(client, headers, scope.location_id)
    cashier = _cashier(client, headers, scope.location_id, 'REGISTER-SCOPE')

    unsettled = _request(
        client, headers, check['id'], cashier['id'], connector['id'], key='unsettled',
    )
    assert unsettled.status_code == 409
    assert unsettled.json()['error']['code'] == 'PAID_CHECK_NOT_SETTLED'

    cash_session = client.post(
        f"/resources/{cashier['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': 'open-print-register'},
        json={'currency': 'MXN'},
    )
    assert cash_session.status_code == 201, cash_session.text
    _settle(
        client, connection, scope, headers, check,
        cash_session_id=cash_session.json()['id'],
    )
    foreign = _scope(connection, f'{prefix}-foreign')
    _grant_cash_permissions(connection, foreign.tenant_id)
    foreign_headers = _staff_headers(client, foreign)
    foreign_cashier = _cashier(
        client, foreign_headers, foreign.location_id, 'FOREIGN-REGISTER',
    )
    rejected = _request(
        client, headers, check['id'], foreign_cashier['id'], connector['id'],
        key='cross-scope',
    )
    assert rejected.status_code == 404
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM paid_check_dispatches '
            'WHERE restaurant_check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 0


def test_local_connector_failure_preserves_financial_truth_and_dispatch_evidence(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_cash_permissions(connection, scope.tenant_id)
    _grant_connector_permissions(connection, scope.tenant_id)
    headers = _staff_headers(client, scope)
    check = _prepared_check(client, connection, scope, amount='60')
    payment = _settle(client, connection, scope, headers, check)
    connector = _connector(client, headers, scope.location_id)
    cashier = _cashier(client, headers, scope.location_id, 'REGISTER-FAILURE')
    response = _request(
        client, headers, check['id'], cashier['id'], connector['id'], key='failure',
    )
    assert response.status_code == 201, response.text
    dispatch = response.json()

    _, _, machine_headers = _provision(client, headers, connector['id'])
    eligible = client.get(
        '/connector/v1/paid-check-dispatches/eligible', headers=machine_headers,
    )
    assert eligible.status_code == 200, eligible.text
    assert [item['dispatch_id'] for item in eligible.json()['items']] == [dispatch['id']]
    claim = client.post(
        f"/connector/v1/paid-check-dispatches/{dispatch['id']}/claims",
        headers=machine_headers,
        json={'claim_request_id': 'paid-check-claim-1'},
    )
    assert claim.status_code == 200, claim.text
    assert claim.json()['payload_schema'] == 'paid-check-v1'
    assert claim.json()['dispatch_kind'] == 'PAID_CHECK'

    error_message = 'Printer unavailable before submission'
    fingerprint = result_fingerprint(
        result='RETRYABLE_FAILURE',
        local_job_reference=None,
        error_kind='DEVICE_UNAVAILABLE',
        error_message=error_message,
    )
    failed = client.post(
        f"/connector/v1/paid-check-dispatches/{dispatch['id']}/results",
        headers=machine_headers,
        json={
            'claim_token': claim.json()['claim_token'],
            'result': 'RETRYABLE_FAILURE',
            'result_fingerprint': fingerprint,
            'local_job_reference': None,
            'error_kind': 'DEVICE_UNAVAILABLE',
            'error_message': error_message,
        },
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()['dispatch']['state'] == 'RETRYABLE_FAILURE'

    read = client.get(
        f"/paid-check-dispatches/{dispatch['id']}", headers=headers,
    )
    assert read.status_code == 200, read.text
    assert read.json()['state'] == 'RETRYABLE_FAILURE'
    assert read.json()['attempts'][0]['result'] == 'RETRYABLE_FAILURE'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT status,continuation_decision FROM restaurant_checks WHERE id=%s',
            (check['id'],),
        )
        financial = cursor.fetchone()
        assert financial == {
            'status': 'SETTLED', 'continuation_decision': 'PENDING',
        }
        cursor.execute(
            'SELECT state FROM restaurant_payments WHERE id=%s', (payment['id'],),
        )
        assert cursor.fetchone()['state'] == 'SUCCEEDED'
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
            'WHERE check_id=%s',
            (check['id'],),
        )
        assert cursor.fetchone()['count'] == 1
