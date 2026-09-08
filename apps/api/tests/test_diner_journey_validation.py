from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _open_and_join,
    _preview,
    _product,
    _scope,
)


def test_conversational_and_deterministic_paths_share_the_active_order_draft(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)

    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        product_id = _product(connection, scope, name='Tacos', amount='100')

        conversational_add = client.post(
            '/diner/conversation/actions',
            headers={**headers, 'Idempotency-Key': 'c7-conversational-add'},
            json={
                'modality': 'TEXT',
                'content_text': 'Agrega unos tacos',
                'intent_code': 'ORDER_EXPRESSION',
                'operation': 'ADD',
                'product_id': product_id,
                'quantity': '1',
                'expected_draft_version': 1,
            },
        )
        assert conversational_add.status_code == 200, conversational_add.text
        conversational_draft = conversational_add.json()['authoritative_data']

        deterministic_read = client.get('/diner/order-draft', headers=headers)
        assert deterministic_read.status_code == 200, deterministic_read.text
        assert deterministic_read.json()['draft_id'] == conversational_draft['draft_id']
        assert deterministic_read.json()['items'][0]['item_id'] == conversational_draft['items'][0]['item_id']

        item_id = deterministic_read.json()['items'][0]['item_id']
        deterministic_modify = client.put(
            f'/diner/order-draft/items/{item_id}/quantity',
            headers=headers,
            json={'quantity': '2', 'expected_version': deterministic_read.json()['version']},
        )
        assert deterministic_modify.status_code == 200, deterministic_modify.text

        conversational_read = client.post(
            '/diner/conversation/actions',
            headers={**headers, 'Idempotency-Key': 'c7-conversational-draft-read'},
            json={'modality': 'TEXT', 'content_text': 'Quiero ver mi pedido'},
        )
        assert conversational_read.status_code == 200, conversational_read.text
        assert conversational_read.json()['intent_code'] == 'DRAFT_REVIEW'
        assert conversational_read.json()['authoritative_data']['draft_id'] == conversational_draft['draft_id']
        assert conversational_read.json()['authoritative_data']['lines'][0]['quantity'] == '2.0000'


def test_conversational_check_is_the_deterministic_check_and_account_read_is_non_mutating(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)

    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        preview = _preview(client, headers, _product(connection, scope, amount='100'))
        accepted = _confirm(client, headers, preview, 'c7-check-order')
        assert accepted.status_code == 201, accepted.text

        account = client.get('/diner/account-preview', headers=headers)
        assert account.status_code == 200, account.text
        assert account.json()['eligible_total'] == '100.0000'
        with connection.cursor() as cursor:
            for table in ('restaurant_checks', 'restaurant_payments', 'restaurant_check_settlements'):
                cursor.execute(
                    f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s',
                    (scope.tenant_id,),
                )
                assert cursor.fetchone()['count'] == 0

        conversational_check = client.post(
            '/diner/conversation/actions',
            headers={**headers, 'Idempotency-Key': 'c7-conversational-check'},
            json={
                'modality': 'TEXT',
                'content_text': 'Prepara mi cuenta',
                'intent_code': 'PAYMENT_REQUEST',
                'check_scope': 'INDIVIDUAL',
            },
        )
        assert conversational_check.status_code == 200, conversational_check.text
        check = conversational_check.json()['authoritative_data']

        deterministic_check = client.get(
            f"/diner/restaurant-checks/{check['id']}?view=detailed", headers=headers
        )
        assert deterministic_check.status_code == 200, deterministic_check.text
        assert deterministic_check.json()['id'] == check['id']
        assert deterministic_check.json()['consumption_total'] == check['consumption_total']
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 1

        other_scope = _scope(connection, f'{prefix}-other')
        _, other_headers = _open_and_join(client, other_scope)
        foreign_read = client.get(
            f"/diner/restaurant-checks/{check['id']}?view=detailed", headers=other_headers
        )
        assert foreign_read.status_code == 404
