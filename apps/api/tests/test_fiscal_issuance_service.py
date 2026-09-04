from __future__ import annotations

import asyncio
import json

import pytest

from app.core.execution import ActorType, ExecutionContext
from app.db.session import DatabaseManager
from app.restaurant.fiscal_issuance import errors, service
from app.restaurant.fiscal_issuance.contracts import InitiateFiscalIssuanceCommand
from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceOutcome,
    FiscalIssuanceRequest,
    FiscalIssuanceResult,
)
from app.restaurant.integrations.fiscal.fake import DeterministicFiscalProvider
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry
from test_billing_tax_evidence_consumption import _bill, _source, client  # noqa: F401


SECRET = 'd3-ephemeral-fiscal-secret-never-persist'


def _execution(connection, source) -> ExecutionContext:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM tenant_memberships WHERE tenant_id=%s ORDER BY id LIMIT 1',
            (source.scope.tenant_id,),
        )
        membership_id = int(cursor.fetchone()['id'])
    return ExecutionContext(
        actor_type=ActorType.EMPLOYEE,
        tenant_id=source.scope.tenant_id,
        principal_id=membership_id,
        principal_reference=None,
        correlation_id='d3-correlation',
    )


def _command(
    source,
    document_id: int,
    *,
    key: str,
    provider_key: str = 'FAKE',
    credential_binding: str | None = None,
) -> InitiateFiscalIssuanceCommand:
    return InitiateFiscalIssuanceCommand(
        organization_id=source.scope.organization_id,
        location_id=source.scope.location_id,
        billing_document_id=document_id,
        provider_key=provider_key,
        credential_binding=credential_binding,
        idempotency_key=key,
    )


def _run(
    settings,
    *,
    execution: ExecutionContext,
    command: InitiateFiscalIssuanceCommand,
    registry: FiscalProviderRegistry,
    resolver=None,
):
    async def invoke():
        database = DatabaseManager(settings)
        session_generator = database.session()
        try:
            db = await anext(session_generator)
            return await service.initiate_fiscal_issuance(
                db,
                execution=execution,
                command=command,
                provider_registry=registry,
                credential_resolver=resolver,
            )
        finally:
            await session_generator.aclose()
            await database.dispose()

    return asyncio.run(invoke())


class InspectingProvider(DeterministicFiscalProvider):
    def __init__(self, connection, **kwargs) -> None:
        super().__init__(**kwargs)
        self._connection = connection
        self.requests: list[FiscalIssuanceRequest] = []
        self.reservation_committed: list[bool] = []
        self.credential_matches: list[bool] = []

    async def issue(
        self,
        *,
        request: FiscalIssuanceRequest,
        credential: EphemeralFiscalProviderCredential | None,
    ) -> FiscalIssuanceResult:
        with self._connection.cursor() as cursor:
            cursor.execute(
                'SELECT id,state,attempt_count FROM billing_issuances '
                'WHERE billing_document_id=%s',
                (request.billing_document_id,),
            )
            issuance = cursor.fetchone()
            cursor.execute(
                'SELECT attempt_type,result FROM billing_issuance_attempts '
                'WHERE billing_issuance_id=%s',
                (issuance['id'],),
            )
            attempt = cursor.fetchone()
        self.reservation_committed.append(
            issuance['state'] == 'IN_PROGRESS'
            and issuance['attempt_count'] == 1
            and attempt == {'attempt_type': 'ISSUE', 'result': None}
        )
        self.requests.append(request)
        self.credential_matches.append(
            credential is not None
            and credential.value.get_secret_value() == SECRET
        )
        return await super().issue(request=request, credential=credential)


class InspectingCredentialResolver:
    def __init__(self, connection) -> None:
        self._connection = connection
        self.reservation_committed: list[bool] = []
        self.bindings = []

    async def resolve(self, *, binding):
        with self._connection.cursor() as cursor:
            cursor.execute(
                'SELECT state,credential_binding FROM billing_issuances '
                'WHERE billing_document_id=%s',
                (int(binding.operation_reference.rsplit(':', 1)[1]),),
            )
            issuance = cursor.fetchone()
        self.reservation_committed.append(
            issuance == {
                'state': 'IN_PROGRESS',
                'credential_binding': binding.credential_binding,
            }
        )
        self.bindings.append(binding)
        return EphemeralFiscalProviderCredential(value=SECRET)


def test_success_uses_frozen_evidence_after_durable_reservation_and_replays(
    client,
    sql_connection,
    integration_settings,
    caplog,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    billed = _bill(client, source, key='d3-success-document')
    assert billed.status_code == 201, billed.text
    document_id = billed.json()['id']
    execution = _execution(connection, source)
    command = _command(
        source,
        document_id,
        key='d3-success-issuance',
        credential_binding='safe-account-binding',
    )

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT issuer_snapshot,recipient_snapshot,request_fingerprint,updated_at '
            'FROM billing_documents WHERE id=%s',
            (document_id,),
        )
        frozen_document = cursor.fetchone()
        cursor.execute(
            'SELECT id,description,quantity,unit_price,base_amount,discount_amount,'
            'commercial_total FROM billing_document_lines '
            'WHERE billing_document_id=%s ORDER BY id',
            (document_id,),
        )
        frozen_lines = tuple(cursor.fetchall())
        cursor.execute(
            'SELECT id,billing_document_line_id,tax_category,tax_treatment,tax_rate,'
            'taxable_base,tax_amount FROM billing_document_line_taxes '
            'WHERE billing_document_line_id IN '
            '(SELECT id FROM billing_document_lines WHERE billing_document_id=%s) '
            'ORDER BY billing_document_line_id,id',
            (document_id,),
        )
        frozen_taxes = tuple(cursor.fetchall())
        cursor.execute(
            "UPDATE products SET name='MUTATED PRODUCT' WHERE id=%s",
            (source.product_id,),
        )
        cursor.execute(
            'UPDATE restaurant_tax_rules SET tax_rate=0.080000 WHERE id=%s',
            (source.tax_rule_id,),
        )
        cursor.execute(
            "UPDATE issuer_fiscal_profiles SET legal_name='MUTATED ISSUER' WHERE id=%s",
            (source.issuer_profile_id,),
        )
        cursor.execute(
            "UPDATE customer_fiscal_profiles SET legal_name='MUTATED RECIPIENT' WHERE id=%s",
            (source.recipient_profile_id,),
        )

    provider = InspectingProvider(connection)
    resolver = InspectingCredentialResolver(connection)
    registry = FiscalProviderRegistry({'FAKE': provider})
    created, replayed = _run(
        integration_settings,
        execution=execution,
        command=command,
        registry=registry,
        resolver=resolver,
    )
    replay, was_replay = _run(
        integration_settings,
        execution=execution,
        command=command,
        registry=registry,
        resolver=resolver,
    )

    assert not replayed
    assert was_replay
    assert created.id == replay.id
    assert created.state == replay.state == 'SUCCEEDED'
    assert created.external_reference == replay.external_reference
    assert created.external_status == 'SUCCEEDED'
    assert created.request_fingerprint == replay.request_fingerprint
    assert created.provider_idempotency_key == replay.provider_idempotency_key
    assert provider.issue_calls == 1
    assert provider.reservation_committed == [True]
    assert resolver.reservation_committed == [True]
    assert provider.credential_matches == [True]
    assert len(created.attempts) == 1
    assert created.attempts[0].attempt_type == 'ISSUE'
    assert created.attempts[0].result == 'SUCCEEDED'
    assert created.attempts[0].result_fingerprint is not None

    request = provider.requests[0]
    frozen_issuer = json.loads(frozen_document['issuer_snapshot'])
    frozen_recipient = json.loads(frozen_document['recipient_snapshot'])
    assert request.issuer.legal_name == frozen_issuer['legal_name']
    assert request.recipient.legal_name == frozen_recipient['legal_name']
    assert tuple(line.billing_document_line_id for line in request.lines) == tuple(
        line['id'] for line in frozen_lines
    )
    assert tuple(
        tax.billing_document_line_tax_id
        for line in request.lines
        for tax in line.taxes
    ) == tuple(tax['id'] for tax in frozen_taxes)
    assert request.lines[0].description == frozen_lines[0]['description']
    assert request.lines[0].taxes[0].rate == frozen_taxes[0]['tax_rate']

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT issuer_snapshot,recipient_snapshot,request_fingerprint,updated_at '
            'FROM billing_documents WHERE id=%s',
            (document_id,),
        )
        assert cursor.fetchone() == frozen_document
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_issuances '
            'WHERE billing_document_id=%s',
            (document_id,),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            'SELECT credential_binding,request_fingerprint,provider_idempotency_key,'
            'last_error_message FROM billing_issuances WHERE id=%s',
            (created.id,),
        )
        persisted = cursor.fetchone()
        cursor.execute(
            'SELECT error_message,result_fingerprint FROM billing_issuance_attempts '
            'WHERE billing_issuance_id=%s',
            (created.id,),
        )
        persisted_attempt = cursor.fetchone()
    assert SECRET not in repr((persisted, persisted_attempt))
    assert SECRET not in created.request_fingerprint
    assert SECRET not in created.provider_idempotency_key
    assert SECRET not in caplog.text


@pytest.mark.parametrize(
    ('outcome', 'expected_state'),
    [
        (FiscalIssuanceOutcome.DEFINITE_FAILURE, 'FAILED'),
        (FiscalIssuanceOutcome.REJECTED, 'REJECTED'),
        (FiscalIssuanceOutcome.UNCERTAIN, 'UNCERTAIN'),
    ],
)
def test_provider_outcomes_persist_and_replay_without_reissuing(
    client,
    sql_connection,
    integration_settings,
    outcome,
    expected_state,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    billed = _bill(client, source, key=f'd3-{expected_state}-document')
    assert billed.status_code == 201, billed.text
    command = _command(
        source,
        billed.json()['id'],
        key=f'd3-{expected_state}-issuance',
    )
    provider = DeterministicFiscalProvider(issuance_outcomes=(outcome,))
    registry = FiscalProviderRegistry({'FAKE': provider})
    execution = _execution(connection, source)

    result, replayed = _run(
        integration_settings,
        execution=execution,
        command=command,
        registry=registry,
    )
    replay, was_replay = _run(
        integration_settings,
        execution=execution,
        command=command,
        registry=registry,
    )

    assert not replayed
    assert was_replay
    assert result.id == replay.id
    assert result.state == replay.state == expected_state
    assert result.attempts[0].result == expected_state
    assert result.last_error_kind is not None
    assert result.last_error_message is not None
    assert provider.issue_calls == 1


def test_idempotency_conflict_and_one_issuance_per_document(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    first = _bill(client, source, key='d3-idempotency-document-1')
    second = _bill(client, source, key='d3-idempotency-document-2')
    assert first.status_code == second.status_code == 201
    execution = _execution(connection, source)
    provider = DeterministicFiscalProvider()
    registry = FiscalProviderRegistry({'FAKE': provider})
    original = _command(
        source,
        first.json()['id'],
        key='d3-shared-command',
    )
    created, _ = _run(
        integration_settings,
        execution=execution,
        command=original,
        registry=registry,
    )

    with pytest.raises(errors.FiscalIssuanceIdempotencyConflictError):
        _run(
            integration_settings,
            execution=execution,
            command=_command(
                source,
                second.json()['id'],
                key='d3-shared-command',
            ),
            registry=registry,
        )
    same_document, replayed = _run(
        integration_settings,
        execution=execution,
        command=_command(
            source,
            first.json()['id'],
            key='d3-another-command',
        ),
        registry=registry,
    )
    assert replayed
    assert same_document.id == created.id
    with pytest.raises(errors.FiscalIssuanceStateConflictError):
        _run(
            integration_settings,
            execution=execution,
            command=_command(
                source,
                first.json()['id'],
                key='d3-other-provider-command',
                provider_key='OTHER',
            ),
            registry=registry,
        )
    assert provider.issue_calls == 1


def test_unknown_provider_and_credential_failure_are_controlled_and_durable(
    client,
    sql_connection,
    integration_settings,
    caplog,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    unknown_document = _bill(client, source, key='d3-unknown-document')
    credential_document = _bill(client, source, key='d3-credential-document')
    assert unknown_document.status_code == credential_document.status_code == 201
    execution = _execution(connection, source)

    with pytest.raises(errors.FiscalProviderUnavailableError) as unknown:
        _run(
            integration_settings,
            execution=execution,
            command=_command(
                source,
                unknown_document.json()['id'],
                key='d3-unknown-provider',
                provider_key='UNKNOWN',
            ),
            registry=FiscalProviderRegistry(),
        )

    class FailingResolver:
        async def resolve(self, *, binding):
            del binding
            raise RuntimeError(SECRET)

    provider = DeterministicFiscalProvider()
    with pytest.raises(errors.FiscalCredentialResolutionError) as credential:
        _run(
            integration_settings,
            execution=execution,
            command=_command(
                source,
                credential_document.json()['id'],
                key='d3-credential-failure',
                credential_binding='safe-binding',
            ),
            registry=FiscalProviderRegistry({'FAKE': provider}),
            resolver=FailingResolver(),
        )

    assert provider.issue_calls == 0
    assert SECRET not in str(unknown.value)
    assert SECRET not in str(credential.value)
    assert SECRET not in caplog.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT state,last_error_kind,last_error_message '
            'FROM billing_issuances WHERE billing_document_id IN (%s,%s) '
            'ORDER BY billing_document_id',
            (unknown_document.json()['id'], credential_document.json()['id']),
        )
        rows = tuple(cursor.fetchall())
        cursor.execute(
            'SELECT result,error_kind,error_message FROM billing_issuance_attempts '
            'WHERE billing_issuance_id IN '
            '(SELECT id FROM billing_issuances WHERE billing_document_id IN (%s,%s))',
            (unknown_document.json()['id'], credential_document.json()['id']),
        )
        attempts = tuple(cursor.fetchall())
    assert {row['state'] for row in rows} == {'FAILED'}
    assert {attempt['result'] for attempt in attempts} == {'FAILED'}
    assert SECRET not in repr((rows, attempts))


def test_concurrent_replay_cannot_duplicate_initial_provider_call(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    billed = _bill(client, source, key='d3-concurrent-document')
    assert billed.status_code == 201, billed.text
    execution = _execution(connection, source)
    command = _command(
        source,
        billed.json()['id'],
        key='d3-concurrent-issuance',
    )

    async def invoke_concurrently():
        entered = asyncio.Event()
        release = asyncio.Event()

        class BarrierProvider(DeterministicFiscalProvider):
            async def issue(self, *, request, credential):
                entered.set()
                await release.wait()
                return await super().issue(request=request, credential=credential)

        provider = BarrierProvider()
        registry = FiscalProviderRegistry({'FAKE': provider})
        database = DatabaseManager(integration_settings)
        try:
            async with (
                database.session_factory() as first_session,
                database.session_factory() as second_session,
            ):
                first_task = asyncio.create_task(service.initiate_fiscal_issuance(
                    first_session,
                    execution=execution,
                    command=command,
                    provider_registry=registry,
                ))
                await asyncio.wait_for(entered.wait(), timeout=10)
                second = await service.initiate_fiscal_issuance(
                    second_session,
                    execution=execution,
                    command=command,
                    provider_registry=registry,
                )
                release.set()
                first = await asyncio.wait_for(first_task, timeout=10)
                return first, second, provider.issue_calls
        finally:
            await database.dispose()

    first, second, calls = asyncio.run(invoke_concurrently())
    assert first[0].id == second[0].id
    assert first[0].state == 'SUCCEEDED'
    assert second[0].state == 'IN_PROGRESS'
    assert not first[1]
    assert second[1]
    assert calls == 1


def test_wrong_scope_and_incomplete_canonical_evidence_never_reserve_or_call(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    billed = _bill(client, source, key='d3-malformed-document')
    assert billed.status_code == 201, billed.text
    document_id = billed.json()['id']
    execution = _execution(connection, source)
    provider = DeterministicFiscalProvider()
    registry = FiscalProviderRegistry({'FAKE': provider})

    with pytest.raises(errors.FiscalBillingDocumentNotFoundError):
        _run(
            integration_settings,
            execution=execution,
            command=InitiateFiscalIssuanceCommand(
                organization_id=source.scope.organization_id,
                location_id=source.scope.location_id + 999_999,
                billing_document_id=document_id,
                provider_key='FAKE',
                credential_binding=None,
                idempotency_key='d3-wrong-scope',
            ),
            registry=registry,
        )
    with connection.cursor() as cursor:
        cursor.execute(
            'DELETE FROM billing_document_line_taxes WHERE billing_document_line_id IN '
            '(SELECT id FROM billing_document_lines WHERE billing_document_id=%s)',
            (document_id,),
        )
    with pytest.raises(errors.FiscalCanonicalEvidenceInvalidError):
        _run(
            integration_settings,
            execution=execution,
            command=_command(
                source,
                document_id,
                key='d3-incomplete-evidence',
            ),
            registry=registry,
        )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_issuances '
            'WHERE billing_document_id=%s',
            (document_id,),
        )
        assert cursor.fetchone()['count'] == 0
    assert provider.issue_calls == 0
