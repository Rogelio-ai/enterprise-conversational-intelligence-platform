from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.db.session import DatabaseManager
from app.models import BillingFiscalArtifact, BillingFiscalResult
from app.restaurant.fiscal_issuance import errors, service
from app.restaurant.fiscal_issuance.contracts import (
    RecoverFiscalIssuanceCommand,
)
from app.restaurant.integrations.fiscal.artifact_storage import (
    FiscalArtifactStorageReceipt,
)
from app.restaurant.integrations.fiscal.contracts import (
    AuthoritativeFiscalResult,
    FiscalArtifactEvidence,
    FiscalIssuanceOutcome,
    FiscalIssuanceResult,
    FiscalRecoveryOutcome,
    FiscalRecoveryResult,
)
from app.restaurant.integrations.fiscal.fake import DeterministicFiscalProvider
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry
from test_billing_tax_evidence_consumption import _bill, _source, client  # noqa: F401
from test_fiscal_issuance_service import _command, _execution


ISSUED_AT = datetime(2026, 9, 5, 18, 30, tzinfo=UTC)
CONTENT = b'<fiscal-document id="immutable" />'


def _authoritative_result(
    *,
    identifier: str = 'FISCAL-ID-001',
    content: bytes | None = None,
    content_hash: str | None = None,
) -> AuthoritativeFiscalResult:
    if content is not None:
        artifact = FiscalArtifactEvidence(
            artifact_kind='STAMPED_FISCAL_DOCUMENT',
            media_type='application/xml',
            content=content,
            provider_artifact_reference='provider-artifact-1',
        )
    else:
        payload_hash = content_hash or hashlib.sha256(CONTENT).hexdigest()
        artifact = FiscalArtifactEvidence(
            artifact_kind='STAMPED_FISCAL_DOCUMENT',
            media_type='application/xml',
            storage_strategy='PROVIDER_REFERENCE',
            storage_reference='provider://fiscal/artifact-1',
            content_hash=payload_hash,
            byte_size=len(CONTENT),
            provider_artifact_reference='provider-artifact-1',
        )
    return AuthoritativeFiscalResult(
        external_fiscal_identifier=identifier,
        fiscal_document_type='INVOICE',
        fiscal_document_version='4.0',
        issued_at=ISSUED_AT,
        artifacts=(artifact,),
    )


class ResultProvider:
    def __init__(
        self,
        *,
        issue_result: AuthoritativeFiscalResult,
        recovery_result: AuthoritativeFiscalResult | None = None,
    ) -> None:
        self.issue_result = issue_result
        self.recovery_result = recovery_result or issue_result
        self.issue_calls = 0
        self.recovery_calls = 0

    async def issue(self, *, request, credential):
        self.issue_calls += 1
        return FiscalIssuanceResult(
            outcome=FiscalIssuanceOutcome.SUCCEEDED,
            external_reference='provider-operation-1',
            external_status='STAMPED',
            fiscal_result=self.issue_result,
        )

    async def recover(self, *, request, credential):
        self.recovery_calls += 1
        return FiscalRecoveryResult(
            outcome=FiscalRecoveryOutcome.RECOVERED_SUCCESS,
            external_reference='provider-operation-1',
            external_status='RECOVERED',
            fiscal_result=self.recovery_result,
        )


class TestStorage:
    __test__ = False

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []
        self.bytes_by_reference = {}

    async def store(self, *, request):
        self.calls.append(request)
        if self.fail:
            raise OSError('simulated storage outage')
        reference = (
            f'test-storage://{request.billing_issuance_id}/'
            f'{request.artifact_kind}/{request.content_hash}'
        )
        self.bytes_by_reference[reference] = request.content
        return FiscalArtifactStorageReceipt(
            storage_strategy='TEST_ONLY_MEMORY',
            storage_reference=reference,
            content_hash=request.content_hash,
            byte_size=request.byte_size,
        )


def _invoke(settings, operation):
    async def run():
        database = DatabaseManager(settings)
        session_generator = database.session()
        try:
            db = await anext(session_generator)
            return await operation(db)
        finally:
            await session_generator.aclose()
            await database.dispose()

    return asyncio.run(run())


def _create_source(client, connection, prefix):
    source = _source(client, connection, prefix)
    billed = _bill(client, source, key='e6-billing-document')
    assert billed.status_code == 201, billed.text
    return source, billed.json()['id']


def _initiate(
    settings, execution, source, document_id, provider, *, storage=None, key='e6-issue'
):
    return _invoke(settings, lambda db: service.initiate_fiscal_issuance(
        db,
        execution=execution,
        command=_command(source, document_id, key=key),
        provider_registry=FiscalProviderRegistry({'FAKE': provider}),
        artifact_storage=storage,
    ))


def _recover(settings, execution, source, issuance_id, provider, *, storage=None):
    return _invoke(settings, lambda db: service.recover_fiscal_issuance(
        db,
        execution=execution,
        command=RecoverFiscalIssuanceCommand(
            organization_id=source.scope.organization_id,
            location_id=source.scope.location_id,
            billing_issuance_id=issuance_id,
        ),
        provider_registry=FiscalProviderRegistry({'FAKE': provider}),
        artifact_storage=storage,
    ))


def test_success_persists_one_immutable_result_and_artifact_metadata(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    source, document_id = _create_source(client, connection, prefix)
    execution = _execution(connection, source)
    provider = ResultProvider(issue_result=_authoritative_result())

    created, replayed = _initiate(
        integration_settings, execution, source, document_id, provider
    )
    replay, was_replayed = _initiate(
        integration_settings, execution, source, document_id, provider
    )

    assert created.state == replay.state == 'SUCCEEDED'
    assert replayed is False and was_replayed is True and provider.issue_calls == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT * FROM billing_fiscal_results WHERE billing_issuance_id=%s',
            (created.id,),
        )
        result = cursor.fetchone()
        cursor.execute(
            'SELECT * FROM billing_fiscal_artifacts WHERE fiscal_result_id=%s',
            (result['id'],),
        )
        artifact = cursor.fetchone()
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_fiscal_results '
            'WHERE billing_issuance_id=%s', (created.id,),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_fiscal_artifacts '
            'WHERE fiscal_result_id=%s', (result['id'],),
        )
        assert cursor.fetchone()['count'] == 1
    assert result['external_fiscal_identifier'] == 'FISCAL-ID-001'
    assert result['provider_external_reference'] == 'provider-operation-1'
    assert result['issued_at'] == ISSUED_AT.replace(tzinfo=None)
    assert (result['fiscal_document_type'], result['fiscal_document_version']) == (
        'INVOICE', '4.0'
    )
    assert len(result['result_fingerprint']) == 64
    assert result['successful_attempt_sequence'] == 1
    assert artifact['artifact_kind'] == 'STAMPED_FISCAL_DOCUMENT'
    assert artifact['media_type'] == 'application/xml'
    assert artifact['content_hash'] == hashlib.sha256(CONTENT).hexdigest()
    assert artifact['byte_size'] == len(CONTENT)
    assert (
        result['tenant_id'], result['organization_id'], result['location_id']
    ) == (
        source.scope.tenant_id, source.scope.organization_id, source.scope.location_id
    )
    assert (
        artifact['tenant_id'], artifact['organization_id'], artifact['location_id']
    ) == (
        source.scope.tenant_id, source.scope.organization_id, source.scope.location_id
    )


def test_inline_artifact_hashes_exact_bytes_and_recovery_converges_after_storage_failure(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    source, document_id = _create_source(client, connection, prefix)
    execution = _execution(connection, source)
    provider = ResultProvider(issue_result=_authoritative_result(content=CONTENT))

    uncertain, _ = _initiate(
        integration_settings,
        execution,
        source,
        document_id,
        provider,
        storage=TestStorage(fail=True),
    )
    assert uncertain.state == 'UNCERTAIN'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id,external_fiscal_identifier FROM billing_fiscal_results '
            'WHERE billing_issuance_id=%s', (uncertain.id,),
        )
        before = cursor.fetchone()
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_fiscal_artifacts '
            'WHERE fiscal_result_id=%s', (before['id'],),
        )
        assert cursor.fetchone()['count'] == 0

    storage = TestStorage()
    recovered = _recover(
        integration_settings, execution, source, uncertain.id, provider, storage=storage
    )
    assert recovered.state == 'SUCCEEDED'
    assert provider.issue_calls == 1 and provider.recovery_calls == 1
    assert len(storage.calls) == 1
    assert storage.calls[0].content_hash == hashlib.sha256(CONTENT).hexdigest()
    assert storage.calls[0].byte_size == len(CONTENT)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_fiscal_results '
            'WHERE billing_issuance_id=%s', (uncertain.id,),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT content_hash,byte_size FROM billing_fiscal_artifacts '
            'WHERE fiscal_result_id=%s', (before['id'],),
        )
        artifact = cursor.fetchone()
    assert artifact == {
        'content_hash': hashlib.sha256(CONTENT).hexdigest(),
        'byte_size': len(CONTENT),
    }


def test_conflicting_recovered_fiscal_identifier_fails_closed(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    source, document_id = _create_source(client, connection, prefix)
    execution = _execution(connection, source)
    provider = ResultProvider(
        issue_result=_authoritative_result(content=CONTENT),
        recovery_result=_authoritative_result(identifier='DIFFERENT-ID'),
    )
    uncertain, _ = _initiate(
        integration_settings, execution, source, document_id, provider,
        storage=TestStorage(fail=True),
    )
    with pytest.raises(errors.FiscalResultConflictError):
        _recover(integration_settings, execution, source, uncertain.id, provider)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT state FROM billing_issuances WHERE id=%s', (uncertain.id,),
        )
        assert cursor.fetchone()['state'] == 'UNCERTAIN'
        cursor.execute(
            'SELECT external_fiscal_identifier FROM billing_fiscal_results '
            'WHERE billing_issuance_id=%s', (uncertain.id,),
        )
        assert cursor.fetchone()['external_fiscal_identifier'] == 'FISCAL-ID-001'


def test_conflicting_artifact_content_fails_closed(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    source, document_id = _create_source(client, connection, prefix)
    execution = _execution(connection, source)
    provider = ResultProvider(issue_result=_authoritative_result(content=CONTENT))
    uncertain, _ = _initiate(
        integration_settings, execution, source, document_id, provider,
        storage=TestStorage(fail=True),
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM billing_fiscal_results WHERE billing_issuance_id=%s',
            (uncertain.id,),
        )
        result_id = cursor.fetchone()['id']
        cursor.execute(
            'INSERT INTO billing_fiscal_artifacts '
            '(tenant_id,organization_id,location_id,fiscal_result_id,artifact_kind,'
            'media_type,storage_strategy,storage_reference,content_hash,byte_size) '
            "VALUES (%s,%s,%s,%s,'STAMPED_FISCAL_DOCUMENT','application/xml',"
            "'TEST_ONLY','test://conflict',%s,1)",
            (
                source.scope.tenant_id, source.scope.organization_id,
                source.scope.location_id, result_id, '0' * 64,
            ),
        )
    with pytest.raises(errors.FiscalArtifactConflictError):
        _recover(
            integration_settings, execution, source, uncertain.id, provider,
            storage=TestStorage(),
        )


def test_cross_scope_result_attachment_is_rejected_by_scoped_foreign_key(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    source, document_id = _create_source(client, connection, prefix)
    execution = _execution(connection, source)
    created, _ = _initiate(
        integration_settings, execution, source, document_id,
        DeterministicFiscalProvider(
            issuance_outcomes=(FiscalIssuanceOutcome.UNCERTAIN,)
        ),
    )
    assert created.state == 'UNCERTAIN'
    with pytest.raises(IntegrityError):
        _invoke(integration_settings, lambda db: _insert_cross_scope(db, created, source))


async def _insert_cross_scope(db, issuance, source):
    db.add(BillingFiscalResult(
        tenant_id=source.scope.tenant_id,
        organization_id=source.scope.organization_id + 999,
        location_id=source.scope.location_id,
        billing_document_id=issuance.billing_document_id,
        billing_issuance_id=issuance.id,
        successful_attempt_sequence=1,
        provider_key='FAKE',
        external_fiscal_identifier='CROSS-SCOPE',
        provider_external_reference='cross-scope-reference',
        fiscal_document_type='INVOICE',
        fiscal_document_version='4.0',
        issued_at=ISSUED_AT.replace(tzinfo=None),
        result_fingerprint='f' * 64,
    ))
    await db.flush()


def test_models_enforce_cardinality_restrict_semantics_and_no_secret_columns() -> None:
    result_table = BillingFiscalResult.__table__
    artifact_table = BillingFiscalArtifact.__table__
    assert any(
        set(constraint.columns.keys()) == {'billing_issuance_id'}
        for constraint in result_table.constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    )
    assert all(
        fk.ondelete == 'RESTRICT'
        for table in (result_table, artifact_table)
        for fk in table.foreign_key_constraints
    )
    columns = set(result_table.c.keys()) | set(artifact_table.c.keys())
    assert not columns & {'credential', 'credential_binding', 'secret', 'access_token'}


def test_provider_success_contract_requires_authoritative_result_and_artifact() -> None:
    with pytest.raises(ValidationError):
        FiscalIssuanceResult(
            outcome=FiscalIssuanceOutcome.SUCCEEDED,
            external_reference='provider-operation-1',
        )
    with pytest.raises(ValidationError):
        AuthoritativeFiscalResult(
            external_fiscal_identifier='FISCAL-ID-001',
            fiscal_document_type='INVOICE',
            fiscal_document_version='4.0',
            issued_at=ISSUED_AT,
            artifacts=(),
        )


def test_result_fingerprint_is_deterministic() -> None:
    class Issuance:
        tenant_id = 1
        organization_id = 2
        location_id = 3
        billing_document_id = 4
        id = 5
        provider_key = 'FAKE'

    result = _authoritative_result()
    first = service._result_fingerprint(
        Issuance(), external_reference='provider-operation-1', result=result
    )
    second = service._result_fingerprint(
        Issuance(), external_reference='provider-operation-1', result=result
    )
    assert first == second and len(first) == 64
