from __future__ import annotations

from pathlib import Path

import pymysql
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app import models
from app.db.base import Base
from app.models import BillingIssuance, BillingIssuanceAttempt
from test_billing_tax_evidence_consumption import _bill, _source, client  # noqa: F401
from test_canonical_order_commercial_acceptance import _execute, _scope


API_ROOT = Path(__file__).resolve().parents[1]


def _constraint_names(table, kind) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, kind)
    }


def test_fiscal_issuance_models_register_and_0027_is_single_head() -> None:
    assert models.BillingIssuance is BillingIssuance
    assert models.BillingIssuanceAttempt is BillingIssuanceAttempt
    issuance = Base.metadata.tables['billing_issuances']
    attempts = Base.metadata.tables['billing_issuance_attempts']

    assert set(issuance.c.keys()) == {
        'id', 'tenant_id', 'organization_id', 'location_id',
        'billing_document_id', 'provider_key', 'credential_binding', 'state',
        'actor_scope', 'idempotency_key', 'request_schema_version',
        'request_fingerprint', 'provider_idempotency_key', 'external_reference',
        'external_status', 'claim_token', 'claim_expires_at', 'attempt_count',
        'last_error_kind', 'last_error_message', 'requested_at', 'completed_at',
        'created_at', 'updated_at',
    }
    assert set(attempts.c.keys()) == {
        'id', 'tenant_id', 'organization_id', 'location_id',
        'billing_issuance_id', 'attempt_sequence', 'attempt_type', 'claim_token',
        'started_at', 'completed_at', 'result', 'external_reference',
        'external_status', 'error_kind', 'error_message', 'result_fingerprint',
        'actor_type', 'actor_id', 'actor_reference', 'correlation_id',
    }
    assert not any('secret' in column.name for table in (issuance, attempts) for column in table.c)
    assert _constraint_names(issuance, UniqueConstraint) >= {
        'uq_billing_issuances_document',
        'uq_billing_issuances_idempotency',
        'uq_billing_issuances_provider_operation',
    }
    assert _constraint_names(issuance, CheckConstraint) >= {
        'ck_billing_issuances_state',
        'ck_billing_issuances_claim',
        'ck_billing_issuances_lifecycle',
    }
    assert _constraint_names(attempts, UniqueConstraint) >= {
        'uq_billing_issuance_attempts_sequence',
        'uq_billing_issuance_attempts_claim',
    }
    assert _constraint_names(attempts, CheckConstraint) >= {
        'ck_billing_issuance_attempts_type',
        'ck_billing_issuance_attempts_result',
        'ck_billing_issuance_attempts_lifecycle',
    }
    assert {
        index.name: tuple(column.name for column in index.columns)
        for index in issuance.indexes
    } == {
        'ix_billing_issuances_state': ('tenant_id', 'state', 'requested_at', 'id'),
        'ix_billing_issuances_claim': ('tenant_id', 'state', 'claim_expires_at', 'id'),
        'ix_billing_issuances_external': (
            'tenant_id', 'provider_key', 'external_reference', 'id',
        ),
    }
    assert {
        index.name: tuple(column.name for column in index.columns)
        for index in attempts.indexes
    } == {
        'ix_billing_issuance_attempts_ordered': (
            'tenant_id', 'billing_issuance_id', 'attempt_sequence', 'id',
        ),
    }
    assert all(
        constraint.ondelete == 'RESTRICT'
        for table in (issuance, attempts)
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )

    config = Config(str(API_ROOT / 'alembic.ini'))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ['0027_fiscal_issuance_foundation']
    assert scripts.get_revision('0027_fiscal_issuance_foundation').down_revision == (
        '0026_authoritative_tax_evidence'
    )


def _insert_issuance(
    connection,
    source,
    document_id: int,
    *,
    actor_key: str,
    provider_operation: str,
) -> int:
    return _execute(
        connection,
        "INSERT INTO billing_issuances (tenant_id,organization_id,location_id,"
        "billing_document_id,provider_key,credential_binding,state,actor_scope,"
        "idempotency_key,request_schema_version,request_fingerprint,"
        "provider_idempotency_key,attempt_count,requested_at) "
        "VALUES (%s,%s,%s,%s,'TEST_PROVIDER','test-account','PENDING',"
        "'EMPLOYEE:1',%s,1,%s,%s,0,CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            document_id,
            actor_key,
            'a' * 64,
            provider_operation,
        ),
    )


def _assert_integrity(connection, statement: str, parameters: tuple) -> None:
    with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)


def test_fiscal_issuance_database_constraints(client, sql_connection) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    first_document = _bill(client, source, key='d1-document-1')
    second_document = _bill(client, source, key='d1-document-2')
    assert first_document.status_code == second_document.status_code == 201
    first_document_id = first_document.json()['id']
    second_document_id = second_document.json()['id']
    issuance_id = _insert_issuance(
        connection,
        source,
        first_document_id,
        actor_key='d1-issue-1',
        provider_operation='d1-provider-operation-1',
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_issuances SET state='IN_PROGRESS',claim_token=%s,"
            "claim_expires_at=CURRENT_TIMESTAMP + INTERVAL 1 HOUR WHERE id=%s",
            ('00000000-0000-0000-0000-000000000001', issuance_id),
        )
        for state in ('FAILED', 'PENDING', 'UNCERTAIN'):
            cursor.execute(
                'UPDATE billing_issuances SET state=%s,claim_token=NULL,'
                'claim_expires_at=NULL WHERE id=%s',
                (state, issuance_id),
            )
        cursor.execute(
            "UPDATE billing_issuances SET state='REJECTED',completed_at=CURRENT_TIMESTAMP "
            'WHERE id=%s',
            (issuance_id,),
        )
        cursor.execute(
            "UPDATE billing_issuances SET state='SUCCEEDED',external_reference='fiscal-1' "
            'WHERE id=%s',
            (issuance_id,),
        )
    _assert_integrity(
        connection,
        "UPDATE billing_issuances SET state='INVALID' WHERE id=%s",
        (issuance_id,),
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_issuances SET state='PENDING',completed_at=NULL,"
            "external_reference=NULL WHERE id=%s",
            (issuance_id,),
        )
        for sequence, attempt_type in enumerate(('ISSUE', 'RETRY', 'RECOVER'), 1):
            cursor.execute(
                'INSERT INTO billing_issuance_attempts '
                '(tenant_id,organization_id,location_id,billing_issuance_id,'
                'attempt_sequence,attempt_type,started_at) '
                'VALUES (%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)',
                (
                    source.scope.tenant_id,
                    source.scope.organization_id,
                    source.scope.location_id,
                    issuance_id,
                    sequence,
                    attempt_type,
                ),
            )
    _assert_integrity(
        connection,
        'INSERT INTO billing_issuance_attempts '
        '(tenant_id,organization_id,location_id,billing_issuance_id,'
        'attempt_sequence,attempt_type,started_at) '
        "VALUES (%s,%s,%s,%s,4,'INVALID',CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            issuance_id,
        ),
    )
    _assert_integrity(
        connection,
        'INSERT INTO billing_issuance_attempts '
        '(tenant_id,organization_id,location_id,billing_issuance_id,'
        'attempt_sequence,attempt_type,started_at) '
        "VALUES (%s,%s,%s,%s,1,'ISSUE',CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            issuance_id,
        ),
    )

    _assert_integrity(
        connection,
        "INSERT INTO billing_issuances (tenant_id,organization_id,location_id,"
        "billing_document_id,provider_key,state,actor_scope,idempotency_key,"
        "request_schema_version,request_fingerprint,provider_idempotency_key,"
        "attempt_count,requested_at) VALUES (%s,%s,%s,%s,'TEST_PROVIDER','PENDING',"
        "'EMPLOYEE:1','different-command',1,%s,'different-operation',0,CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            first_document_id,
            'b' * 64,
        ),
    )
    _assert_integrity(
        connection,
        "INSERT INTO billing_issuances (tenant_id,organization_id,location_id,"
        "billing_document_id,provider_key,state,actor_scope,idempotency_key,"
        "request_schema_version,request_fingerprint,provider_idempotency_key,"
        "attempt_count,requested_at) VALUES (%s,%s,%s,%s,'TEST_PROVIDER','PENDING',"
        "'EMPLOYEE:1','d1-issue-1',1,%s,'different-operation',0,CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            second_document_id,
            'b' * 64,
        ),
    )
    _assert_integrity(
        connection,
        "INSERT INTO billing_issuances (tenant_id,organization_id,location_id,"
        "billing_document_id,provider_key,state,actor_scope,idempotency_key,"
        "request_schema_version,request_fingerprint,provider_idempotency_key,"
        "attempt_count,requested_at) VALUES (%s,%s,%s,%s,'TEST_PROVIDER','PENDING',"
        "'EMPLOYEE:1','different-command',1,%s,'d1-provider-operation-1',0,CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            source.scope.location_id,
            second_document_id,
            'b' * 64,
        ),
    )

    other = _scope(connection, f'{prefix}-other')
    _assert_integrity(
        connection,
        "INSERT INTO billing_issuances (tenant_id,organization_id,location_id,"
        "billing_document_id,provider_key,state,actor_scope,idempotency_key,"
        "request_schema_version,request_fingerprint,provider_idempotency_key,"
        "attempt_count,requested_at) VALUES (%s,%s,%s,%s,'TEST_PROVIDER','PENDING',"
        "'EMPLOYEE:2','cross-tenant',1,%s,'cross-tenant',0,CURRENT_TIMESTAMP)",
        (
            other.tenant_id,
            other.organization_id,
            other.location_id,
            second_document_id,
            'c' * 64,
        ),
    )
    other_location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,%s,'Other Location','America/Mexico_City','ACTIVE')",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            f'D1-{prefix[-8:]}',
        ),
    )
    _assert_integrity(
        connection,
        "INSERT INTO billing_issuances (tenant_id,organization_id,location_id,"
        "billing_document_id,provider_key,state,actor_scope,idempotency_key,"
        "request_schema_version,request_fingerprint,provider_idempotency_key,"
        "attempt_count,requested_at) VALUES (%s,%s,%s,%s,'TEST_PROVIDER','PENDING',"
        "'EMPLOYEE:1','cross-location',1,%s,'cross-location',0,CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            other_location_id,
            second_document_id,
            'd' * 64,
        ),
    )
    _assert_integrity(
        connection,
        'INSERT INTO billing_issuance_attempts '
        '(tenant_id,organization_id,location_id,billing_issuance_id,'
        'attempt_sequence,attempt_type,started_at) '
        "VALUES (%s,%s,%s,%s,4,'RECOVER',CURRENT_TIMESTAMP)",
        (
            other.tenant_id,
            other.organization_id,
            other.location_id,
            issuance_id,
        ),
    )
    _assert_integrity(
        connection,
        'INSERT INTO billing_issuance_attempts '
        '(tenant_id,organization_id,location_id,billing_issuance_id,'
        'attempt_sequence,attempt_type,started_at) '
        "VALUES (%s,%s,%s,%s,4,'RECOVER',CURRENT_TIMESTAMP)",
        (
            source.scope.tenant_id,
            source.scope.organization_id,
            other_location_id,
            issuance_id,
        ),
    )

    _assert_integrity(
        connection,
        'DELETE FROM billing_issuances WHERE id=%s',
        (issuance_id,),
    )
    second_issuance_id = _insert_issuance(
        connection,
        source,
        second_document_id,
        actor_key='d1-issue-2',
        provider_operation='d1-provider-operation-2',
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'DELETE FROM billing_document_line_taxes WHERE billing_document_line_id IN '
            '(SELECT id FROM billing_document_lines WHERE billing_document_id=%s)',
            (second_document_id,),
        )
        cursor.execute(
            'DELETE FROM billing_document_lines WHERE billing_document_id=%s',
            (second_document_id,),
        )
    _assert_integrity(
        connection,
        'DELETE FROM billing_documents WHERE id=%s',
        (second_document_id,),
    )
    assert second_issuance_id > 0
