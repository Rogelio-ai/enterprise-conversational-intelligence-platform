from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from test_cash_payment_integration import _prepared_check
from test_canonical_order_commercial_acceptance import _scope, _staff_headers
from test_restaurant_payment_settlement_foundation import _grant
from test_staff_check_query import _login, _membership


def test_fiscal_context_edit_validation_and_location_isolation(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id, configure_executor=False)

    with TestClient(create_app(settings=integration_settings)) as client:
        headers = _staff_headers(client, scope)
        check = _prepared_check(client, connection, scope, amount='75')
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO customers "
                "(tenant_id,display_name,email,status,source) "
                "VALUES (%s,'Cliente Fiscal','fiscal@example.test','ACTIVE','PLATFORM')",
                (scope.tenant_id,),
            )
            customer_id = int(cursor.lastrowid)
            cursor.execute(
                'SELECT controller_diner_session_id FROM restaurant_checks WHERE id=%s',
                (check['id'],),
            )
            diner_session_id = int(cursor.fetchone()['controller_diner_session_id'])
            cursor.execute(
                'UPDATE diner_sessions SET customer_id=%s WHERE id=%s',
                (customer_id, diner_session_id),
            )

        path = f"/restaurant-checks/{check['id']}"
        empty = client.get(
            f'{path}/fiscal-context', headers=headers,
            params={'location_id': scope.location_id},
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()['customer_id'] == customer_id
        assert empty.json()['issuer_profiles'] == []
        assert empty.json()['recipient_profile'] is None

        invalid = client.put(
            f'{path}/recipient-fiscal-profile', headers=headers,
            params={'location_id': scope.location_id},
            json={
                'legal_name': '', 'tax_identifier': 'XAXX010101000',
                'tax_regime': '616', 'fiscal_postal_code': '01000',
                'invoice_usage': 'S01',
            },
        )
        assert invalid.status_code == 422

        issuer = client.put(
            f'{path}/issuer-fiscal-profile', headers=headers,
            params={'location_id': scope.location_id},
            json={
                'legal_name': 'Restaurante Ejemplo',
                'tax_identifier': 'AAA010101AAA',
                'tax_regime': '601',
                'fiscal_postal_code': '01000',
            },
        )
        assert issuer.status_code == 200, issuer.text
        recipient = client.put(
            f'{path}/recipient-fiscal-profile', headers=headers,
            params={'location_id': scope.location_id},
            json={
                'legal_name': 'Cliente Fiscal',
                'tax_identifier': 'XAXX010101000',
                'tax_regime': '616',
                'fiscal_postal_code': '01000',
                'invoice_usage': 'S01',
            },
        )
        assert recipient.status_code == 200, recipient.text

        context = client.get(
            f'{path}/fiscal-context', headers=headers,
            params={'location_id': scope.location_id},
        )
        assert context.status_code == 200, context.text
        assert context.json()['issuer_profiles'][0]['id'] == issuer.json()['id']
        assert context.json()['recipient_profile']['id'] == recipient.json()['id']

        ungranted_email, _ = _membership(
            connection,
            tenant_id=scope.tenant_id,
            slug=f'fiscal-ungranted-{check["id"]}',
            permissions=('restaurant_check.read', 'restaurant_check.manage'),
        )
        undisclosed = client.get(
            f'{path}/fiscal-context',
            headers=_login(client, ungranted_email),
            params={'location_id': scope.location_id},
        )
        assert undisclosed.status_code == 404
