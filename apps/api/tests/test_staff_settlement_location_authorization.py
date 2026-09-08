from __future__ import annotations

from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from test_canonical_order_commercial_acceptance import (
    _scope,
    _staff_headers,
)
from test_restaurant_payment_settlement_foundation import (
    _client,
    _electronic_payload,
    _grant,
)
from test_staff_check_query import (
    _grant_location,
    _login,
    _membership,
    _membership_id,
    _new_check,
    _other_location,
)


def test_staff_settlement_read_requires_location_authority_and_preserves_truth(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    owner_membership_id = _membership_id(connection, scope.email)
    _grant_location(
        connection, scope.tenant_id, owner_membership_id, scope.location_id
    )
    other_location = _other_location(connection, scope, 'MISMATCH')
    _grant_location(
        connection,
        scope.tenant_id,
        owner_membership_id,
        other_location.location_id,
    )
    permission_email, _ = _membership(
        connection,
        tenant_id=scope.tenant_id,
        slug=f'{prefix}-permission-no-grant',
        permissions=('restaurant_payment.read',),
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
    executor = DeterministicPaymentExecutor()

    with _client(integration_settings, executor) as client:
        check, diner_headers = _new_check(client, connection, scope, 'settlement')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        payment = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'settlement-card-40'},
            json=_electronic_payload(check, '40', diner_id),
        )
        assert payment.status_code == 201, payment.text
        assert payment.json()['state'] == 'SUCCEEDED'
        staff_headers = _staff_headers(client, scope)

        inbox = client.get(
            '/restaurant-checks',
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert inbox.status_code == 200, inbox.text
        assert [item['id'] for item in inbox.json()['items']] == [check['id']]

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
                (check['id'],),
            )
            payment_count = cursor.fetchone()['count']
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
                'WHERE check_id=%s',
                (check['id'],),
            )
            settlement_count = cursor.fetchone()['count']

        url = f"/restaurant-checks/{check['id']}/settlement"
        authorized = client.get(
            url,
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert authorized.status_code == 200, authorized.text
        body = authorized.json()
        assert body['check_id'] == check['id']
        assert body['liability_total'] == '100.0000'
        assert body['confirmed_settlement'] == '40.0000'
        assert body['reserved_financial_exposure'] == '0.0000'
        assert body['uncertain_exposure'] == '0.0000'
        assert body['available_to_initiate'] == '60.0000'
        assert [value['id'] for value in body['payments']] == [payment.json()['id']]
        assert body['payments'][0]['state'] == 'SUCCEEDED'
        assert body['payments'][0]['instrument_brand'] == 'TEST'
        assert body['payments'][0]['instrument_last_four'] == '0000'
        assert body['payments'][0]['instrument_display'] == 'TEST •••• 0000'

        diner = client.get(
            f"/diner/restaurant-checks/{check['id']}/settlement",
            headers=diner_headers,
        )
        assert diner.status_code == 200, diner.text
        assert diner.json() == body

        denied_cases = (
            (_login(client, permission_email), scope.location_id, 404, url),
            (_login(client, no_permission_email), scope.location_id, 403, url),
            (staff_headers, other_location.location_id, 404, url),
            (_staff_headers(client, foreign), scope.location_id, 404, url),
            (
                staff_headers,
                scope.location_id,
                404,
                f"/restaurant-checks/{check['id'] + 999999}/settlement",
            ),
        )
        for headers, location_id, expected_status, denied_url in denied_cases:
            denied = client.get(
                denied_url,
                headers=headers,
                params={'location_id': location_id},
            )
            assert denied.status_code == expected_status, denied.text
            assert 'liability_total' not in denied.text
            assert 'confirmed_settlement' not in denied.text
            assert 'payments' not in denied.text

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_payments WHERE check_id=%s',
                (check['id'],),
            )
            assert cursor.fetchone()['count'] == payment_count
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_check_settlements '
                'WHERE check_id=%s',
                (check['id'],),
            )
            assert cursor.fetchone()['count'] == settlement_count
