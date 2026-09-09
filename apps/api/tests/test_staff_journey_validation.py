from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.integrations.fiscal.contracts import FiscalIssuanceOutcome
from app.restaurant.integrations.fiscal.fake import DeterministicFiscalProvider
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry
from app.restaurant.integrations.payments.contracts import (
    PaymentExecutionOutcome,
    PaymentRecoveryOutcome,
)
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from test_billing_tax_evidence_consumption import _bill, _source
from test_canonical_order_commercial_acceptance import (
    _execute,
    _open_and_join,
    _scope,
    _staff_headers,
)
from test_cash_payment_integration import _grant_cash_permissions
from test_fiscal_issuance_service import _command, _execution, _run
from test_manager_operational_overview import _grant_manager_reads
from test_paid_check_printing_bridge import (
    _cashier,
    _grant_connector_permissions,
    _request as _print_request,
)
from test_preparation_dispatch_operational_delivery import _connector
from test_preparation_execution_foundation import _native_item, _transition
from test_restaurant_payment_settlement_foundation import (
    _check,
    _electronic_payload,
    _grant,
    _grant_staff_location,
    _order,
)
from test_staff_check_query import _login, _membership
from test_staff_operational_requests import _enable_staff


def _overview(client: TestClient, headers: dict[str, str], location_id: int) -> dict:
    response = client.get(
        '/staff/manager/operational-overview',
        headers=headers,
        params={'location_id': location_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _grant_permissions(connection, tenant_id: int, *codes: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1',
            (tenant_id,),
        )
        role_id = int(cursor.fetchone()['id'])
        for code in codes:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
            cursor.execute(
                'INSERT IGNORE INTO role_permissions (role_id,permission_id) '
                'VALUES (%s,%s)',
                (role_id, permission_id),
            )


def test_waiter_and_kitchen_mutations_reconstruct_in_manager(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _enable_staff(connection, scope)
    _grant_manager_reads(connection, scope.tenant_id)
    _grant_permissions(
        connection, scope.tenant_id,
        'preparation.route', 'preparation.configure', 'preparation.execute',
    )
    _execute(
        connection,
        "INSERT INTO restaurant_tax_rules (tenant_id,organization_id,location_id,"
        "tax_classification_code,jurisdiction_code,tax_category,tax_treatment,tax_rate,"
        "calculation_policy,rounding_policy,effective_from,effective_to,status) "
        "VALUES (%s,%s,NULL,'TEST-FOOD','TEST-JURISDICTION','SALES_TAX','TAXABLE',"
        "0.160000,'INCLUDED_PRICE_SINGLE_TAX','DECIMAL_4_HALF_UP',"
        "CURRENT_TIMESTAMP - INTERVAL 1 DAY,NULL,'ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )

    with TestClient(create_app(settings=integration_settings)) as client:
        staff_headers = _staff_headers(client, scope)
        _, diner_headers = _open_and_join(client, scope, name='Journey Diner')
        created = client.post(
            '/diner/operational-requests',
            headers={**diner_headers, 'Idempotency-Key': 'journey-assistance'},
            json={'request_type': 'HUMAN_ASSISTANCE'},
        )
        assert created.status_code == 201, created.text
        request_id = created.json()['id']

        pending = _overview(client, staff_headers, scope.location_id)
        assert pending['request_counts_by_status']['PENDING'] == 1
        waiter_read = client.get(
            f'/staff/operational-requests/{request_id}',
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert waiter_read.status_code == 200, waiter_read.text
        assert waiter_read.json()['id'] == request_id

        acknowledged = client.post(
            f'/staff/operational-requests/{request_id}/acknowledge',
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert acknowledged.status_code == 200, acknowledged.text
        in_attention = _overview(client, staff_headers, scope.location_id)
        assert in_attention['request_counts_by_status']['PENDING'] == 0
        assert in_attention['request_counts_by_status']['ACKNOWLEDGED'] == 1

        completed = client.post(
            f'/staff/operational-requests/{request_id}/complete',
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert completed.status_code == 200, completed.text
        resolved = _overview(client, staff_headers, scope.location_id)
        assert resolved['request_counts_by_status']['ACKNOWLEDGED'] == 0
        assert resolved['request_counts_by_status']['COMPLETED'] == 1

        kitchen_resource_id = _execute(
            connection,
            "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) "
            "VALUES (%s,%s,'JOURNEY-KITCHEN','Journey Kitchen Table','TABLE','ACTIVE')",
            (scope.tenant_id, scope.location_id),
        )
        kitchen_scope = replace(scope, resource_id=kitchen_resource_id)
        kitchen_headers, _, _, work_id, item_id = _native_item(
            client, connection, kitchen_scope, name='Journey Kitchen Item'
        )
        waiting = _overview(client, staff_headers, scope.location_id)
        assert waiting['preparation_item_counts']['NEW'] == 1
        started = _transition(
            client, kitchen_headers, item_id, 'journey-start', 'NEW', 0,
            'IN_PROGRESS',
        )
        assert started.status_code == 201, started.text
        kitchen_read = client.get(
            f'/preparation-works/{work_id}', headers=kitchen_headers
        )
        assert kitchen_read.status_code == 200, kitchen_read.text
        assert kitchen_read.json()['items'][0]['id'] == item_id
        assert kitchen_read.json()['items'][0]['execution_state'] == 'IN_PROGRESS'
        preparing = _overview(client, staff_headers, scope.location_id)
        assert preparing['preparation_item_counts']['NEW'] == 0
        assert preparing['preparation_item_counts']['IN_PROGRESS'] == 1

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count,status FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        assert cursor.fetchone() == {'count': 1, 'status': 'COMPLETED'}


def test_uncertain_payment_recovery_reconstructs_in_cashier_and_manager(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant(connection, scope.tenant_id)
    _grant_staff_location(connection, scope)
    _grant_manager_reads(connection, scope.tenant_id)
    executor = DeterministicPaymentExecutor(
        execution_outcomes=(PaymentExecutionOutcome.UNCERTAIN,),
        recovery_outcomes=(PaymentRecoveryOutcome.CONFIRMED_SUCCESS,),
    )

    with TestClient(create_app(
        settings=integration_settings,
        payment_executors={'deterministic': executor},
    )) as client:
        staff_headers = _staff_headers(client, scope)
        _, diner_headers = _open_and_join(client, scope)
        _order(client, connection, scope, diner_headers, amount='100')
        check = _check(client, diner_headers, 'journey-uncertain-check')
        diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
        created = client.post(
            f"/diner/restaurant-checks/{check['id']}/payments",
            headers={**diner_headers, 'Idempotency-Key': 'journey-uncertain-payment'},
            json=_electronic_payload(check, '100', diner_id),
        )
        assert created.status_code == 201, created.text
        payment_id = created.json()['id']
        assert created.json()['state'] == 'UNCERTAIN'

        cashier_projection = client.get(
            f"/restaurant-checks/{check['id']}/settlement",
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert cashier_projection.status_code == 200, cashier_projection.text
        assert cashier_projection.json()['uncertain_exposure'] == '100.0000'
        uncertain = _overview(client, staff_headers, scope.location_id)
        assert [item['id'] for item in uncertain['uncertain_payments']] == [payment_id]

        recovered = client.post(
            f'/restaurant-payments/{payment_id}/recover',
            headers=staff_headers,
            params={'location_id': scope.location_id},
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['id'] == payment_id
        assert recovered.json()['state'] == 'SUCCEEDED'
        final = _overview(client, staff_headers, scope.location_id)
        assert final['uncertain_payments'] == []
        assert final['check_counts_by_status']['SETTLED'] == 1

    with connection.cursor() as cursor:
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
    assert executor.execution_calls == 1
    assert executor.recovery_calls == 1


def test_settled_check_billing_and_paid_print_reconstruct_in_manager_and_isolate_location(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    provider = DeterministicFiscalProvider(
        issuance_outcomes=(FiscalIssuanceOutcome.UNCERTAIN,)
    )

    with TestClient(create_app(settings=integration_settings)) as client:
        source = _source(client, connection, prefix)
        scope = source.scope
        _grant_manager_reads(connection, scope.tenant_id)
        _grant_cash_permissions(connection, scope.tenant_id)
        _grant_connector_permissions(connection, scope.tenant_id)
        staff_headers = _staff_headers(client, scope)

        invoice_request = client.post(
            '/diner/operational-requests',
            headers={
                **source.diner_headers,
                'Idempotency-Key': 'journey-invoice-assistance',
            },
            json={
                'request_type': 'INVOICE_ASSISTANCE',
                'related_restaurant_check_id': source.check_id,
            },
        )
        assert invoice_request.status_code == 201, invoice_request.text
        billed = _bill(client, source, key='journey-billing-document')
        assert billed.status_code == 201, billed.text
        document_id = billed.json()['id']
        assert billed.json()['restaurant_check_id'] == source.check_id

        issuance, replayed = _run(
            integration_settings,
            execution=_execution(connection, source),
            command=_command(
                source, document_id, key='journey-fiscal-issuance'
            ),
            registry=FiscalProviderRegistry({'FAKE': provider}),
        )
        assert replayed is False
        assert issuance.state == 'UNCERTAIN'

        connector = _connector(client, staff_headers, scope.location_id)
        cashier = _cashier(
            client, staff_headers, scope.location_id, 'JOURNEY-REGISTER'
        )
        printed = _print_request(
            client, staff_headers, source.check_id, cashier['id'], connector['id'],
            key='journey-paid-print',
        )
        assert printed.status_code == 201, printed.text
        dispatch_id = printed.json()['id']

        overview = _overview(client, staff_headers, scope.location_id)
        assert overview['request_counts_by_type']['INVOICE_ASSISTANCE'] == 1
        assert [item['id'] for item in overview['fiscal_exceptions']] == [issuance.id]
        assert overview['fiscal_exceptions'][0]['billing_document_id'] == document_id
        assert [item['id'] for item in overview['paid_print_exceptions']] == [dispatch_id]
        assert overview['paid_print_exceptions'][0]['reference_id'] == source.check_id

        ungranted_email, _ = _membership(
            connection,
            tenant_id=scope.tenant_id,
            slug=f'{prefix}-journey-ungranted',
            permissions=(
                'location.read', 'resource.read', 'restaurant_service.read',
                'restaurant_order.read', 'operational_request.read',
                'preparation.read', 'restaurant_check.read',
                'restaurant_payment.read', 'cash_management.read',
            ),
        )
        denied = client.get(
            '/staff/manager/operational-overview',
            headers=_login(client, ungranted_email),
            params={'location_id': scope.location_id},
        )
        assert denied.status_code == 404
        assert str(document_id) not in denied.text
        assert str(dispatch_id) not in denied.text
        assert 'credential_binding' not in denied.text
