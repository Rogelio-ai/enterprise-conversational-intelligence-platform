from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.catalog.resolution_contracts import ResolutionStatus
from app.restaurant.checks.errors import OrderingBlockedError
from app.restaurant.diner_experience import states
from app.restaurant.diner_experience.contracts import ExperienceState
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _execute,
    _open_and_join,
    _preview,
    _product,
    _scope,
)


def _configured_product(connection, scope):
    category_id = _execute(
        connection,
        "INSERT INTO product_categories "
        "(tenant_id,organization_id,name,display_order,status) "
        "VALUES (%s,%s,'Food',0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    parent_id = _product(connection, scope, name='Breakfast', amount='125')
    connection.cursor().execute(
        "UPDATE products SET category_id=%s,description='Breakfast plate' WHERE id=%s",
        (category_id, parent_id),
    )
    fixed_id = _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) "
        "VALUES (%s,%s,'Fruit','ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id),
    )
    option_id = _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) "
        "VALUES (%s,%s,'Coffee','ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id),
    )
    composition_id = _execute(
        connection,
        "INSERT INTO product_compositions "
        "(tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, parent_id),
    )
    _execute(
        connection,
        "INSERT INTO product_components "
        "(tenant_id,organization_id,composition_id,component_product_id,quantity,status) "
        "VALUES (%s,%s,%s,%s,1,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id, fixed_id),
    )
    group_id = _execute(
        connection,
        "INSERT INTO product_choice_groups "
        "(tenant_id,organization_id,composition_id,name,min_selections,max_selections,status) "
        "VALUES (%s,%s,%s,'Drink',1,1,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    choice_id = _execute(
        connection,
        "INSERT INTO product_choice_options "
        "(tenant_id,organization_id,group_id,option_product_id,quantity,status) "
        "VALUES (%s,%s,%s,%s,1,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, group_id, option_id),
    )
    return parent_id, group_id, choice_id


def test_diner_menu_and_product_configuration_are_current_location_authoritative(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        product_id, group_id, choice_id = _configured_product(connection, scope)

        menu = client.get('/diner/menu', headers=headers)
        assert menu.status_code == 200, menu.text
        product = next(
            product
            for menu_value in menu.json()['menus']
            for section in menu_value['sections']
            for product in section['products']
            if product['id'] == product_id
        )
        assert product['price'] == {'amount': '125.0000', 'currency': 'MXN'}
        assert product['category_path'] == [{'id': product['category_path'][0]['id'], 'name': 'Food'}]
        assert product['orderable'] is True
        assert product['configuration_required'] is True

        detail = client.get(f'/diner/products/{product_id}', headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()['fixed_components'][0]['name'] == 'Fruit'
        group = detail.json()['choice_groups'][0]
        assert (group['id'], group['min_selections'], group['max_selections'], group['required']) == (
            group_id, 1, 1, True
        )
        assert group['options'][0]['id'] == choice_id

        other = _scope(connection, f'{prefix}-other')
        other_product_id = _product(connection, other, name='Other location item')
        unavailable = client.get(f'/diner/products/{other_product_id}', headers=headers)
        assert unavailable.status_code == 404
        assert unavailable.json()['error']['state'] == 'PRODUCT_UNAVAILABLE'


def test_account_preview_is_coherent_repeatable_and_non_locking(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        product_id = _product(connection, scope, amount='150')
        preview = _preview(client, headers, product_id)
        accepted = _confirm(client, headers, preview, 'b1-account-order')
        assert accepted.status_code == 201, accepted.text

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            checks_before = cursor.fetchone()['count']
        reads = [client.get('/diner/account-preview', headers=headers) for _ in range(3)]
        assert all(value.status_code == 200 for value in reads)
        body = reads[0].json()
        assert body['eligible_order_ids'] == [accepted.json()['id']]
        assert body['lines'][0]['commercial_amount'] == '150.0000'
        assert Decimal(body['eligible_total']) == Decimal('150')
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_checks WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == checks_before
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_payments WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0
        assert client.post('/diner/order-draft', headers=headers).status_code == 201


def test_operational_request_is_scoped_durable_idempotent_and_does_not_execute_staff_actions(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    with TestClient(create_app(settings=integration_settings)) as client:
        _, headers = _open_and_join(client, scope)
        request_headers = {**headers, 'Idempotency-Key': 'b1-assistance'}
        created = client.post(
            '/diner/operational-requests',
            headers=request_headers,
            json={'request_type': 'HUMAN_ASSISTANCE'},
        )
        assert created.status_code == 201, created.text
        replay = client.post(
            '/diner/operational-requests',
            headers=request_headers,
            json={'request_type': 'HUMAN_ASSISTANCE'},
        )
        assert replay.status_code == 200
        assert replay.json()['id'] == created.json()['id']
        assert replay.json()['status'] == 'PENDING'
        assert replay.json()['experience']['state'] == 'STAFF_ASSISTANCE_REQUIRED'
        assert client.get(
            f"/diner/operational-requests/{created.json()['id']}", headers=headers
        ).status_code == 200

        product_id = _product(connection, scope, amount='80')
        accepted = _confirm(
            client, headers, _preview(client, headers, product_id), 'b1-handoff-order'
        )
        assert accepted.status_code == 201, accepted.text
        check = client.post(
            '/diner/restaurant-checks',
            headers={**headers, 'Idempotency-Key': 'b1-handoff-check'},
            json={'mode': 'INDIVIDUAL'},
        )
        assert check.status_code == 201, check.text
        cash_request = client.post(
            '/diner/operational-requests',
            headers={**headers, 'Idempotency-Key': 'b1-cash-assistance'},
            json={
                'request_type': 'CASH_PAYMENT_ASSISTANCE',
                'related_restaurant_check_id': check.json()['id'],
            },
        )
        assert cash_request.status_code == 201, cash_request.text

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS count FROM diner_operational_requests WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 2
            cursor.execute(
                'SELECT COUNT(*) AS count FROM paid_check_dispatches WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0
            cursor.execute(
                'SELECT COUNT(*) AS count FROM restaurant_payments WHERE tenant_id=%s',
                (scope.tenant_id,),
            )
            assert cursor.fetchone()['count'] == 0
        assert client.post(
            '/diner/operational-requests',
            headers={**headers, 'Idempotency-Key': 'b1-print-no-check'},
            json={'request_type': 'PAID_CHECK_PRINT'},
        ).status_code == 422
        assert client.post(
            f"/restaurant-checks/{check.json()['id']}/paid-print",
            headers={**headers, 'Idempotency-Key': 'cannot-dispatch'},
            json={
                'cashier_resource_id': scope.resource_id,
                'connector_id': 1,
                'local_target_key': 'printer',
            },
        ).status_code == 401


def test_experience_state_mapping_is_bounded_and_deterministic():
    assert states.from_resolution(ResolutionStatus.AMBIGUOUS).state is ExperienceState.CLARIFICATION_REQUIRED
    assert states.from_resolution(ResolutionStatus.NOT_ORDERABLE).state is ExperienceState.PRODUCT_UNAVAILABLE
    assert states.from_domain_condition(OrderingBlockedError()).state is ExperienceState.ACTION_BLOCKED
    assert states.from_domain_condition('SERVICE_CONTINUATION_DECISION_REQUIRED').state is ExperienceState.CONTINUATION_REQUIRED
    assert states.from_domain_condition('UNCERTAIN').state is ExperienceState.PAYMENT_UNCERTAIN
    assert states.from_domain_condition('SESSION_CLOSED').state is ExperienceState.SESSION_CLOSED
