from __future__ import annotations

from uuid import uuid4

import pymysql
import pytest

from test_canonical_order_commercial_acceptance import _scope


DATABASE_CONSTRAINT_ERRORS = (pymysql.err.IntegrityError, pymysql.err.OperationalError)


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _configuration(connection, scope, *, key: str, location_id: int | None = None) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO location_payment_executor_configurations (
            tenant_id, organization_id, location_id, executor_key, display_name,
            adapter_kind, topology, status, credential_binding, selection_priority
        ) VALUES (%s,%s,%s,%s,'Test executor','deterministic','EXTERNAL','ACTIVE',NULL,100)
        ''',
        (
            scope.tenant_id,
            scope.organization_id,
            scope.location_id if location_id is None else location_id,
            key,
        ),
    )


def _check(connection, scope) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO restaurant_checks (
            tenant_id, organization_id, location_id, currency, status, version,
            current_fingerprint, fingerprint_schema_version, consumption_total,
            gratuity_total, liability_total, controller_actor_type, created_actor_type
        ) VALUES (%s,%s,%s,'MXN','OPEN',1,%s,1,100,0,100,'SYSTEM','SYSTEM')
        ''',
        (scope.tenant_id, scope.organization_id, scope.location_id, uuid4().hex * 2),
    )


def _payment(
    connection,
    scope,
    *,
    check_id: int,
    executor_configuration_id: int | None,
    external_reference: str | None,
) -> int:
    identity = uuid4().hex
    return _execute(
        connection,
        '''
        INSERT INTO restaurant_payments (
            tenant_id, organization_id, location_id, check_id, check_version,
            check_fingerprint, amount, currency, method_category, payer_type,
            payer_reference, initiated_actor_type, actor_scope, idempotency_key,
            request_schema_version, request_fingerprint, state, executor_key,
            executor_configuration_id, provider_idempotency_key, external_reference,
            attempt_count
        ) VALUES (
            %s,%s,%s,%s,1,%s,1,'MXN','CARD','OTHER','test payer','SYSTEM',%s,%s,
            1,%s,'FAILED','deterministic',%s,%s,%s,0
        )
        ''',
        (
            scope.tenant_id,
            scope.organization_id,
            scope.location_id,
            check_id,
            uuid4().hex * 2,
            f'SYSTEM:{identity}',
            identity,
            uuid4().hex * 2,
            executor_configuration_id,
            f'provider-{identity}',
            external_reference,
        ),
    )


def test_executor_configuration_enforces_scope_key_and_enums(sql_connection) -> None:
    connection, prefix = sql_connection
    first = _scope(connection, f'{prefix}-first')
    second = _scope(connection, f'{prefix}-second')
    second_location = _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status)
        VALUES (%s,%s,%s,'Second location','America/Mexico_City','ACTIVE')
        ''',
        (first.tenant_id, first.organization_id, f'LOC-{uuid4().hex[:12]}'),
    )
    other_organization = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Other','ACTIVE')",
        (first.tenant_id, f'ORG-{uuid4().hex[:12]}'),
    )
    other_organization_location = _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status)
        VALUES (%s,%s,%s,'Other organization location','America/Mexico_City','ACTIVE')
        ''',
        (first.tenant_id, other_organization, f'LOC-{uuid4().hex[:12]}'),
    )

    _configuration(connection, first, key='shared-key')
    _configuration(connection, first, key='shared-key', location_id=second_location)

    for statement, parameters in (
        (
            '''INSERT INTO location_payment_executor_configurations
               (tenant_id,organization_id,location_id,executor_key,display_name,adapter_kind,topology,status,selection_priority)
               VALUES (%s,%s,%s,'shared-key','Duplicate','deterministic','EXTERNAL','ACTIVE',100)''',
            (first.tenant_id, first.organization_id, first.location_id),
        ),
        (
            '''INSERT INTO location_payment_executor_configurations
               (tenant_id,organization_id,location_id,executor_key,display_name,adapter_kind,topology,status,selection_priority)
               VALUES (%s,%s,%s,'cross-scope','Cross','deterministic','EXTERNAL','ACTIVE',100)''',
            (first.tenant_id, first.organization_id, second.location_id),
        ),
        (
            '''INSERT INTO location_payment_executor_configurations
               (tenant_id,organization_id,location_id,executor_key,display_name,adapter_kind,topology,status,selection_priority)
               VALUES (%s,%s,%s,'cross-organization','Cross','deterministic','EXTERNAL','ACTIVE',100)''',
            (first.tenant_id, first.organization_id, other_organization_location),
        ),
        (
            '''INSERT INTO location_payment_executor_configurations
               (tenant_id,organization_id,location_id,executor_key,display_name,adapter_kind,topology,status,selection_priority)
               VALUES (%s,%s,%s,'bad-topology','Bad','deterministic','REMOTE','ACTIVE',100)''',
            (first.tenant_id, first.organization_id, first.location_id),
        ),
        (
            '''INSERT INTO location_payment_executor_configurations
               (tenant_id,organization_id,location_id,executor_key,display_name,adapter_kind,topology,status,selection_priority)
               VALUES (%s,%s,%s,'bad-status','Bad','deterministic','EXTERNAL','DISABLED',100)''',
            (first.tenant_id, first.organization_id, first.location_id),
        ),
    ):
        with pytest.raises(DATABASE_CONSTRAINT_ERRORS):
            _execute(connection, statement, parameters)


def test_executor_capability_enforces_scope_uniqueness_method_and_currency(sql_connection) -> None:
    connection, prefix = sql_connection
    first = _scope(connection, f'{prefix}-first')
    second = _scope(connection, f'{prefix}-second')
    configuration_id = _configuration(connection, first, key='capabilities')
    statement = '''
        INSERT INTO location_payment_executor_capabilities (
            executor_configuration_id,tenant_id,organization_id,location_id,method_category,currency
        ) VALUES (%s,%s,%s,%s,%s,%s)
    '''
    _execute(
        connection, statement,
        (configuration_id, first.tenant_id, first.organization_id, first.location_id, 'CARD', 'MXN'),
    )
    invalid_rows = (
        (configuration_id, first.tenant_id, first.organization_id, first.location_id, 'CARD', 'MXN'),
        (configuration_id, second.tenant_id, second.organization_id, second.location_id, 'CARD', 'USD'),
        (configuration_id, first.tenant_id, first.organization_id, first.location_id, 'CRYPTO', 'MXN'),
        (configuration_id, first.tenant_id, first.organization_id, first.location_id, 'TRANSFER', 'mxn'),
    )
    for row in invalid_rows:
        with pytest.raises(DATABASE_CONSTRAINT_ERRORS):
            _execute(connection, statement, row)


def test_restaurant_payment_executor_configuration_linkage_is_scoped_and_nullable(
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    first = _scope(connection, f'{prefix}-first')
    second = _scope(connection, f'{prefix}-second')
    first_configuration = _configuration(connection, first, key='first')
    second_configuration = _configuration(connection, second, key='second')
    second_location = _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status)
        VALUES (%s,%s,%s,'Second location','America/Mexico_City','ACTIVE')
        ''',
        (first.tenant_id, first.organization_id, f'LOC-{uuid4().hex[:12]}'),
    )
    other_location_configuration = _configuration(
        connection, first, key='other-location', location_id=second_location
    )
    check_id = _check(connection, first)

    _payment(
        connection, first, check_id=check_id,
        executor_configuration_id=first_configuration, external_reference='linked',
    )
    _payment(
        connection, first, check_id=check_id,
        executor_configuration_id=None, external_reference='historical',
    )
    with pytest.raises(pymysql.err.IntegrityError):
        _payment(
            connection, first, check_id=check_id,
            executor_configuration_id=second_configuration, external_reference='cross-tenant',
        )
    with pytest.raises(pymysql.err.IntegrityError):
        _payment(
            connection, first, check_id=check_id,
            executor_configuration_id=other_location_configuration,
            external_reference='cross-location',
        )


def test_external_reference_identity_is_configuration_scoped_and_nullable(sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    check_id = _check(connection, scope)
    first = _configuration(connection, scope, key='first')
    second = _configuration(connection, scope, key='second')

    _payment(
        connection, scope, check_id=check_id,
        executor_configuration_id=first, external_reference='provider-reference',
    )
    _payment(
        connection, scope, check_id=check_id,
        executor_configuration_id=first, external_reference='different-reference',
    )
    _payment(
        connection, scope, check_id=check_id,
        executor_configuration_id=second, external_reference='provider-reference',
    )
    _payment(
        connection, scope, check_id=check_id,
        executor_configuration_id=first, external_reference=None,
    )
    _payment(
        connection, scope, check_id=check_id,
        executor_configuration_id=first, external_reference=None,
    )
    with pytest.raises(pymysql.err.IntegrityError):
        _payment(
            connection, scope, check_id=check_id,
            executor_configuration_id=first, external_reference='provider-reference',
        )
