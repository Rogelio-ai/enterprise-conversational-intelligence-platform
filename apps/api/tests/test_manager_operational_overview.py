from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from test_cash_payment_integration import (
    _grant_cash_permissions, _prepared_check, _register_and_session,
)
from test_canonical_order_commercial_acceptance import _scope, _staff_headers
from test_restaurant_payment_settlement_foundation import _grant
from test_staff_check_query import _login, _membership


MANAGER_READS = (
    'location.read', 'resource.read', 'restaurant_service.read',
    'restaurant_order.read', 'operational_request.read', 'preparation.read',
    'restaurant_check.read', 'restaurant_payment.read', 'cash_management.read',
)


def _grant_manager_reads(connection, tenant_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1', (tenant_id,))
        role_id = int(cursor.fetchone()['id'])
        for code in MANAGER_READS:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
            cursor.execute(
                'INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
                (role_id, permission_id),
            )


def test_manager_overview_is_bounded_authorized_and_location_safe(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)
    _grant_manager_reads(connection, scope.tenant_id)
    _grant_cash_permissions(connection, scope.tenant_id)

    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _staff_headers(client, scope)
        check = _prepared_check(client, connection, scope, amount='75')
        _, cash_session = _register_and_session(
            client, scope, headers, code='MANAGER-REGISTER'
        )

        response = client.get(
            '/staff/manager/operational-overview',
            headers=headers,
            params={'location_id': scope.location_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['location_id'] == scope.location_id
        assert body['active_table_count'] == 1
        assert body['available_table_count'] == 0
        assert body['active_service_session_count'] == 1
        assert body['service_sessions'][0]['resource_id'] == scope.resource_id
        assert body['active_diner_count'] == 1
        assert body['checks_with_outstanding_count'] == 1
        assert body['check_exceptions'][0]['id'] == check['id']
        assert body['check_exceptions'][0]['outstanding'] == '75.0000'
        assert body['cash_session_counts']['OPEN'] == 1
        assert body['cash_session_exceptions'][0]['id'] == cash_session['id']
        assert body['cash_session_exceptions'][0]['expected_cash'] == '0.0000'
        assert body['request_counts_by_status'] == {
            'PENDING': 0, 'ACKNOWLEDGED': 0, 'COMPLETED': 0, 'CANCELLED': 0,
        }
        assert body['uncertain_payments'] == []
        assert body['fiscal_exceptions'] == []
        assert body['paid_print_exceptions'] == []
        assert 'credential_binding' not in response.text
        assert 'payer_reference' not in response.text

        ungranted_email, _ = _membership(
            connection, tenant_id=scope.tenant_id,
            slug=f'manager-ungranted-{scope.location_id}',
            permissions=MANAGER_READS,
        )
        undisclosed = client.get(
            '/staff/manager/operational-overview',
            headers=_login(client, ungranted_email),
            params={'location_id': scope.location_id},
        )
        assert undisclosed.status_code == 404

        incomplete_email, _ = _membership(
            connection, tenant_id=scope.tenant_id,
            slug=f'manager-incomplete-{scope.location_id}',
            permissions=MANAGER_READS[:-1],
        )
        forbidden = client.get(
            '/staff/manager/operational-overview',
            headers=_login(client, incomplete_email),
            params={'location_id': scope.location_id},
        )
        assert forbidden.status_code == 403
