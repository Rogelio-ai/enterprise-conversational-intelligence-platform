from __future__ import annotations

from decimal import Decimal

from app.main import create_app
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from fastapi.testclient import TestClient
from test_canonical_order_commercial_acceptance import (
    _open_and_join,
    _product,
    _scope,
)
from test_diner_experience_contracts import _configured_product
from test_restaurant_payment_settlement_foundation import (
    _electronic_payload,
    _grant,
)


def _action(client, headers, key: str, intent: str, **values):
    return client.post(
        '/diner/conversation/actions',
        headers={**headers, 'Idempotency-Key': key},
        json={
            'modality': 'TEXT',
            'content_text': values.pop('content_text', intent),
            'intent_code': intent,
            **values,
        },
    )


def test_menu_and_ambiguous_product_use_b1_and_do_not_mutate_draft(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        _product(connection, scope, name='Coca', amount='40')
        _product(connection, scope, name='Coca', amount='45')

        menu = _action(client, headers, 'menu-1', 'MENU_QUERY', content_text='Muéstrame el menú')
        assert menu.status_code == 200, menu.text
        assert menu.json()['experience']['state'] == 'OK'
        assert len(menu.json()['authoritative_data']) == 2

        ambiguous = _action(
            client,
            headers,
            'ambiguous-1',
            'PRODUCT_QUERY',
            content_text='Quiero una Coca',
            reference_text='Coca',
        )
        assert ambiguous.status_code == 200, ambiguous.text
        assert ambiguous.json()['experience']['state'] == 'CLARIFICATION_REQUIRED'
        assert len(ambiguous.json()['authoritative_data']['candidates']) == 2
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM order_drafts WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0
            cursor.execute(
                'SELECT participant_type FROM conversation_participants p '
                'JOIN conversation_messages m ON m.participant_id=p.id '
                'WHERE m.conversation_id=(SELECT conversation_id FROM diner_sessions '
                'WHERE tenant_id=%s LIMIT 1) ORDER BY m.sequence_number',
                (scope.tenant_id,),
            )
            assert [row['participant_type'] for row in cursor.fetchall()] == [
                'CUSTOMER', 'DIGITAL_WAITER', 'CUSTOMER', 'DIGITAL_WAITER'
            ]


def test_add_configure_review_confirm_account_and_replay_use_authoritative_domains(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        product_id, group_id, _ = _configured_product(connection, scope)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT tax_classification_code FROM products WHERE id=%s',
                (product_id,),
            )
            tax_classification_code = cursor.fetchone()['tax_classification_code']
            cursor.execute(
                'UPDATE products SET tax_classification_code=%s '
                'WHERE tenant_id=%s AND tax_classification_code IS NULL',
                (tax_classification_code, scope.tenant_id),
            )

        added = _action(
            client,
            headers,
            'add-breakfast',
            'ORDER_EXPRESSION',
            operation='ADD',
            product_id=product_id,
            quantity='1',
            expected_draft_version=1,
        )
        assert added.status_code == 200, added.text
        body = added.json()
        assert body['experience']['state'] == 'CONFIGURATION_REQUIRED'
        assert body['authoritative_data']['readiness'] == 'INCOMPLETE'
        item_id = body['authoritative_data']['items'][0]['item_id']

        replay = _action(
            client,
            headers,
            'add-breakfast',
            'ORDER_EXPRESSION',
            operation='ADD',
            product_id=product_id,
            quantity='1',
            expected_draft_version=1,
        )
        assert replay.status_code == 200
        assert replay.json()['experience']['state'] == 'ACTION_BLOCKED'
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM order_draft_items WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 1

        configured = _action(
            client,
            headers,
            'configure-breakfast',
            'ORDER_EXPRESSION',
            operation='CONFIGURE',
            draft_item_id=item_id,
            choice_group_id=group_id,
            choice_reference_text='Coffee',
            expected_draft_version=2,
        )
        assert configured.status_code == 200, configured.text
        assert configured.json()['authoritative_data']['readiness'] == 'READY'

        reviewed = _action(client, headers, 'review-1', 'DRAFT_REVIEW')
        assert reviewed.status_code == 200, reviewed.text
        preview = reviewed.json()['authoritative_data']
        assert preview['payable_total'] == '125.00'

        confirmed = _action(
            client,
            headers,
            'confirm-1',
            'ORDER_CONFIRMATION',
            expected_draft_version=preview['draft_version'],
            expected_commercial_fingerprint=preview['commercial_fingerprint'],
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()['experience']['state'] == 'OK', confirmed.text
        assert confirmed.json()['authoritative_data']['status'] == 'ACCEPTED'
        confirm_replay = _action(
            client,
            headers,
            'confirm-1',
            'ORDER_CONFIRMATION',
            expected_draft_version=preview['draft_version'],
            expected_commercial_fingerprint=preview['commercial_fingerprint'],
        )
        assert confirm_replay.status_code == 200
        assert confirm_replay.json()['replayed'] is True

        orders = _action(client, headers, 'orders-1', 'ORDER_STATUS_QUERY')
        assert len(orders.json()['authoritative_data']) == 1
        account = _action(client, headers, 'account-1', 'ACCOUNT_QUERY')
        assert Decimal(account.json()['authoritative_data']['eligible_total']) == Decimal('125')
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0


def test_payment_scope_cash_assistance_human_unknown_and_paid_print_boundaries(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor()
    with TestClient(
        create_app(settings=integration_settings, payment_executors={'deterministic': executor})
    ) as client:
        _, headers = _open_and_join(client, scope)
        diner_id = client.get('/diner-session', headers=headers).json()['id']
        product_id = _product(connection, scope, amount='100')
        added = _action(
            client,
            headers,
            'add-payment-item',
            'ORDER_EXPRESSION',
            operation='ADD',
            product_id=product_id,
            quantity='1',
            expected_draft_version=1,
        ).json()['authoritative_data']
        preview = _action(client, headers, 'review-payment', 'DRAFT_REVIEW').json()[
            'authoritative_data'
        ]
        _action(
            client,
            headers,
            'confirm-payment-order',
            'ORDER_CONFIRMATION',
            expected_draft_version=added['version'],
            expected_commercial_fingerprint=preview['commercial_fingerprint'],
        )

        unclear = _action(client, headers, 'payment-unclear', 'PAYMENT_REQUEST')
        assert unclear.json()['experience']['state'] == 'CLARIFICATION_REQUIRED'
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0

        created = _action(
            client,
            headers,
            'payment-individual',
            'PAYMENT_REQUEST',
            check_scope='INDIVIDUAL',
        )
        assert created.status_code == 200, created.text
        check = created.json()['authoritative_data']
        cash = _action(
            client,
            headers,
            'cash-assistance',
            'PAYMENT_REQUEST',
            check_id=check['id'],
            payment_method='CASH',
        )
        assert cash.json()['experience']['state'] == 'STAFF_ASSISTANCE_REQUIRED'
        assert cash.json()['authoritative_data']['request_type'] == 'CASH_PAYMENT_ASSISTANCE'

        assistance = _action(
            client, headers, 'human-assistance', 'HUMAN_ASSISTANCE_REQUEST'
        )
        assert assistance.json()['authoritative_data']['request_type'] == 'HUMAN_ASSISTANCE'
        assistance_replay = _action(
            client, headers, 'human-assistance', 'HUMAN_ASSISTANCE_REQUEST'
        )
        assert assistance_replay.json()['replayed'] is True

        payment = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**headers, 'Idempotency-Key': 'settle-for-print'},
            json=_electronic_payload(check, '100', diner_id),
        )
        assert payment.status_code == 201, payment.text
        status = _action(
            client,
            headers,
            'payment-status',
            'PAYMENT_STATUS_QUERY',
            check_id=check['id'],
        )
        assert status.json()['authoritative_data']['check_status'] == 'SETTLED'

        printed = _action(
            client,
            headers,
            'print-request',
            'PAID_PRINT_REQUEST',
            check_id=check['id'],
        )
        assert printed.status_code == 200, printed.text
        assert printed.json()['authoritative_data']['request_type'] == 'PAID_CHECK_PRINT'
        continued_required = _action(
            client,
            headers,
            'continuation-state',
            'SERVICE_CONTINUATION',
            check_id=check['id'],
        )
        assert continued_required.json()['experience']['state'] == 'CONTINUATION_REQUIRED'
        continued = _action(
            client,
            headers,
            'continuation-yes',
            'SERVICE_CONTINUATION',
            check_id=check['id'],
            continuation_decision='YES',
            expected_check_version=check['version'],
        )
        assert continued.status_code == 200, continued.text
        assert continued.json()['authoritative_data']['continuation_decision'] == 'YES'

        unknown = _action(client, headers, 'unknown-1', 'UNKNOWN')
        assert unknown.json()['experience']['state'] == 'CLARIFICATION_REQUIRED'
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM diner_operational_requests '
                'WHERE tenant_id=%s AND request_type=%s',
                (scope.tenant_id, 'HUMAN_ASSISTANCE'),
            )
            assert cursor.fetchone()['count'] == 1
            cursor.execute(
                'SELECT COUNT(*) AS count FROM paid_check_dispatches WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0
            cursor.execute(
                'SELECT COUNT(*) AS count FROM cash_sessions WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0
