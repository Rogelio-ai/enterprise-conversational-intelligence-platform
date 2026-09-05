from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import DatabaseManager
from app.restaurant.fiscal_issuance import errors, service
from app.restaurant.fiscal_issuance.contracts import (
    RecoverFiscalIssuanceCommand,
    RetryFiscalIssuanceCommand,
)
from app.restaurant.integrations.fiscal.contracts import (
    EphemeralFiscalProviderCredential,
    FiscalIssuanceOutcome,
    FiscalRecoveryOutcome,
)
from app.restaurant.integrations.fiscal.fake import DeterministicFiscalProvider
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry
from test_billing_tax_evidence_consumption import _bill, _source, client  # noqa: F401
from test_fiscal_issuance_service import _command, _execution


SECRET = 'd4-ephemeral-secret-never-persist'


def _existing_command(source, issuance_id: int, *, retry: bool = False):
    command_type = RetryFiscalIssuanceCommand if retry else RecoverFiscalIssuanceCommand
    return command_type(
        organization_id=source.scope.organization_id,
        location_id=source.scope.location_id,
        billing_issuance_id=issuance_id,
    )


def _invoke(settings, operation, **kwargs):
    async def invoke():
        database = DatabaseManager(settings)
        try:
            async with database.session_factory() as db:
                return await operation(db, **kwargs)
        finally:
            await database.dispose()

    return asyncio.run(invoke())


def _initiate(settings, *, execution, command, registry, resolver=None):
    return _invoke(
        settings,
        service.initiate_fiscal_issuance,
        execution=execution,
        command=command,
        provider_registry=registry,
        credential_resolver=resolver,
    )[0]


def _recover(settings, *, execution, command, registry, resolver=None):
    return _invoke(
        settings,
        service.recover_fiscal_issuance,
        execution=execution,
        command=command,
        provider_registry=registry,
        credential_resolver=resolver,
    )


def _retry(settings, *, execution, command, registry, resolver=None):
    return _invoke(
        settings,
        service.retry_fiscal_issuance,
        execution=execution,
        command=command,
        provider_registry=registry,
        credential_resolver=resolver,
    )


@pytest.mark.parametrize(
    ('recovery_outcome', 'expected_state'),
    [
        (FiscalRecoveryOutcome.RECOVERED_SUCCESS, 'SUCCEEDED'),
        (FiscalRecoveryOutcome.STILL_UNCERTAIN, 'UNCERTAIN'),
    ],
)
def test_recovery_maps_outcomes_without_reissuing(
    client,
    sql_connection,
    integration_settings,
    recovery_outcome,
    expected_state,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    document = _bill(client, source, key=f'd4-recovery-{expected_state}-document')
    execution = _execution(connection, source)
    provider = DeterministicFiscalProvider(
        issuance_outcomes=(FiscalIssuanceOutcome.UNCERTAIN,),
        recovery_outcomes=(recovery_outcome,),
    )
    registry = FiscalProviderRegistry({'FAKE': provider})
    issued = _initiate(
        integration_settings,
        execution=execution,
        command=_command(
            source,
            document.json()['id'],
            key=f'd4-recovery-{expected_state}',
        ),
        registry=registry,
    )

    recovered = _recover(
        integration_settings,
        execution=execution,
        command=_existing_command(source, issued.id),
        registry=registry,
    )

    assert issued.state == 'UNCERTAIN'
    assert recovered.state == expected_state
    assert provider.issue_calls == 1
    assert provider.recovery_calls == 1
    assert [attempt.attempt_type for attempt in recovered.attempts] == [
        'ISSUE',
        'RECOVER',
    ]
    assert [attempt.sequence for attempt in recovered.attempts] == [1, 2]


def test_definite_absence_authorizes_only_explicit_retry_and_reuses_binding(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    document = _bill(client, source, key='d4-safe-retry-document')
    execution = _execution(connection, source)
    class CapturingProvider(DeterministicFiscalProvider):
        def __init__(self):
            super().__init__(
                issuance_outcomes=(FiscalIssuanceOutcome.UNCERTAIN,),
                recovery_outcomes=(FiscalRecoveryOutcome.DEFINITE_ABSENCE,),
            )
            self.issue_requests = []
            self.recovery_requests = []
            self.retry_claim_committed = False

        async def issue(self, *, request, credential):
            self.issue_requests.append(request)
            if len(self.issue_requests) == 2:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'SELECT state,attempt_count FROM billing_issuances '
                        'WHERE billing_document_id=%s',
                        (request.billing_document_id,),
                    )
                    issuance_row = cursor.fetchone()
                    cursor.execute(
                        'SELECT attempt_type,result FROM billing_issuance_attempts '
                        'WHERE billing_issuance_id=(SELECT id FROM billing_issuances '
                        'WHERE billing_document_id=%s) ORDER BY attempt_sequence DESC LIMIT 1',
                        (request.billing_document_id,),
                    )
                    attempt_row = cursor.fetchone()
                self.retry_claim_committed = (
                    issuance_row['state'] == 'IN_PROGRESS'
                    and issuance_row['attempt_count'] == 3
                    and attempt_row == {'attempt_type': 'RETRY', 'result': None}
                )
            return await super().issue(request=request, credential=credential)

        async def recover(self, *, request, credential):
            self.recovery_requests.append(request)
            return await super().recover(request=request, credential=credential)

    provider = CapturingProvider()
    registry = FiscalProviderRegistry({'ORIGINAL': provider})
    issued = _initiate(
        integration_settings,
        execution=execution,
        command=_command(
            source,
            document.json()['id'],
            key='d4-safe-retry',
            provider_key='ORIGINAL',
        ),
        registry=registry,
    )
    original = (
        issued.id,
        issued.provider_key,
        issued.request_fingerprint,
        issued.provider_idempotency_key,
    )

    recovered = _recover(
        integration_settings,
        execution=execution,
        command=_existing_command(source, issued.id),
        registry=registry,
    )
    assert recovered.state == 'FAILED'
    assert recovered.attempts[-1].external_status == 'DEFINITE_ABSENCE'
    assert provider.issue_calls == 1

    retried = _retry(
        integration_settings,
        execution=execution,
        command=_existing_command(source, issued.id, retry=True),
        registry=registry,
    )
    assert retried.state == 'SUCCEEDED'
    assert (
        retried.id,
        retried.provider_key,
        retried.request_fingerprint,
        retried.provider_idempotency_key,
    ) == original
    assert provider.issue_calls == 2
    assert provider.retry_claim_committed
    assert provider.recovery_requests[0].provider_idempotency_key == original[3]
    assert provider.recovery_requests[0].request_fingerprint == original[2]
    assert provider.issue_requests[1].provider_idempotency_key == original[3]
    assert provider.issue_requests[1].request_fingerprint == original[2]
    assert [attempt.attempt_type for attempt in retried.attempts] == [
        'ISSUE',
        'RECOVER',
        'RETRY',
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_issuances '
            'WHERE billing_document_id=%s',
            (document.json()['id'],),
        )
        assert cursor.fetchone()['count'] == 1


def test_retry_eligibility_and_terminal_recovery_rules(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    execution = _execution(connection, source)

    scenarios = (
        ('uncertain', FiscalIssuanceOutcome.UNCERTAIN),
        ('rejected', FiscalIssuanceOutcome.REJECTED),
        ('failed', FiscalIssuanceOutcome.DEFINITE_FAILURE),
        ('succeeded', FiscalIssuanceOutcome.SUCCEEDED),
    )
    issuances = {}
    providers = {}
    for name, outcome in scenarios:
        document = _bill(client, source, key=f'd4-rules-{name}-document')
        provider = DeterministicFiscalProvider(
            issuance_outcomes=(outcome, FiscalIssuanceOutcome.SUCCEEDED),
        )
        issuances[name] = _initiate(
            integration_settings,
            execution=execution,
            command=_command(
                source,
                document.json()['id'],
                key=f'd4-rules-{name}',
                provider_key=name.upper(),
            ),
            registry=FiscalProviderRegistry({name.upper(): provider}),
        )
        providers[name] = provider

    with pytest.raises(errors.FiscalIssuanceRetryNotAllowedError):
        _retry(
            integration_settings,
            execution=execution,
            command=_existing_command(source, issuances['uncertain'].id, retry=True),
            registry=FiscalProviderRegistry({'UNCERTAIN': providers['uncertain']}),
        )
    with pytest.raises(errors.FiscalIssuanceRetryNotAllowedError):
        _retry(
            integration_settings,
            execution=execution,
            command=_existing_command(source, issuances['rejected'].id, retry=True),
            registry=FiscalProviderRegistry({'REJECTED': providers['rejected']}),
        )
    retried = _retry(
        integration_settings,
        execution=execution,
        command=_existing_command(source, issuances['failed'].id, retry=True),
        registry=FiscalProviderRegistry({'FAILED': providers['failed']}),
    )
    assert retried.state == 'SUCCEEDED'
    assert providers['failed'].issue_calls == 2

    succeeded_provider = providers['succeeded']
    recovered = _recover(
        integration_settings,
        execution=execution,
        command=_existing_command(source, issuances['succeeded'].id),
        registry=FiscalProviderRegistry({'SUCCEEDED': succeeded_provider}),
    )
    assert recovered.state == 'SUCCEEDED'
    assert succeeded_provider.recovery_calls == 0
    with pytest.raises(errors.FiscalIssuanceRetryNotAllowedError):
        _retry(
            integration_settings,
            execution=execution,
            command=_existing_command(source, issuances['succeeded'].id, retry=True),
            registry=FiscalProviderRegistry({'SUCCEEDED': succeeded_provider}),
        )


def test_active_claim_expiry_recovery_and_stale_fence_are_safe(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    document = _bill(client, source, key='d4-fencing-document')
    execution = _execution(connection, source)
    initial_provider = DeterministicFiscalProvider(
        issuance_outcomes=(FiscalIssuanceOutcome.UNCERTAIN,),
    )
    issued = _initiate(
        integration_settings,
        execution=execution,
        command=_command(source, document.json()['id'], key='d4-fencing'),
        registry=FiscalProviderRegistry({'FAKE': initial_provider}),
    )

    async def exercise():
        entered = asyncio.Event()
        release = asyncio.Event()

        class BarrierRecoveryProvider(DeterministicFiscalProvider):
            async def recover(self, *, request, credential):
                entered.set()
                await release.wait()
                return await super().recover(request=request, credential=credential)

        first_provider = BarrierRecoveryProvider()
        winner_provider = DeterministicFiscalProvider()
        database = DatabaseManager(integration_settings)
        try:
            async with (
                database.session_factory() as first_db,
                database.session_factory() as conflict_db,
                database.session_factory() as winner_db,
            ):
                first_task = asyncio.create_task(service.recover_fiscal_issuance(
                    first_db,
                    execution=execution,
                    command=_existing_command(source, issued.id),
                    provider_registry=FiscalProviderRegistry({'FAKE': first_provider}),
                ))
                await asyncio.wait_for(entered.wait(), timeout=10)
                with pytest.raises(errors.FiscalIssuanceConcurrencyConflictError):
                    await service.recover_fiscal_issuance(
                        conflict_db,
                        execution=execution,
                        command=_existing_command(source, issued.id),
                        provider_registry=FiscalProviderRegistry({'FAKE': first_provider}),
                    )

                with connection.cursor() as cursor:
                    cursor.execute(
                        'UPDATE billing_issuances SET claim_expires_at=%s WHERE id=%s',
                        (datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1), issued.id),
                    )
                winner = await service.recover_fiscal_issuance(
                    winner_db,
                    execution=execution,
                    command=_existing_command(source, issued.id),
                    provider_registry=FiscalProviderRegistry({'FAKE': winner_provider}),
                )
                release.set()
                with pytest.raises(errors.FiscalIssuanceStaleFenceError):
                    await asyncio.wait_for(first_task, timeout=10)
                return winner, first_provider, winner_provider
        finally:
            await database.dispose()

    winner, first_provider, winner_provider = asyncio.run(exercise())
    assert winner.state == 'SUCCEEDED'
    assert first_provider.recovery_calls == 1
    assert winner_provider.recovery_calls == 1
    assert [attempt.sequence for attempt in winner.attempts] == [1, 2, 3]
    assert winner.attempts[1].result == 'UNCERTAIN'
    assert winner.attempts[1].external_status == 'CLAIM_EXPIRED'


def test_recovery_credentials_are_ephemeral_and_boundary_failures_stay_uncertain(
    client,
    sql_connection,
    integration_settings,
    caplog,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    document = _bill(client, source, key='d4-credential-document')
    execution = _execution(connection, source)

    class Resolver:
        def __init__(self):
            self.bindings = []

        async def resolve(self, *, binding):
            self.bindings.append(binding)
            return EphemeralFiscalProviderCredential(value=SECRET)

    class ExplodingRecoveryProvider(DeterministicFiscalProvider):
        async def recover(self, *, request, credential):
            assert credential.value.get_secret_value() == SECRET
            raise RuntimeError(SECRET)

    resolver = Resolver()
    initial_provider = DeterministicFiscalProvider(
        issuance_outcomes=(FiscalIssuanceOutcome.UNCERTAIN,),
    )
    issued = _initiate(
        integration_settings,
        execution=execution,
        command=_command(
            source,
            document.json()['id'],
            key='d4-credential',
            credential_binding='original-safe-binding',
        ),
        registry=FiscalProviderRegistry({'FAKE': initial_provider}),
        resolver=resolver,
    )
    failed_recovery = _recover(
        integration_settings,
        execution=execution,
        command=_existing_command(source, issued.id),
        registry=FiscalProviderRegistry({'FAKE': ExplodingRecoveryProvider()}),
        resolver=resolver,
    )

    assert failed_recovery.state == 'UNCERTAIN'
    assert failed_recovery.attempts[-1].result == 'UNCERTAIN'
    assert all(binding.provider_key == 'FAKE' for binding in resolver.bindings)
    assert all(
        binding.credential_binding == 'original-safe-binding'
        for binding in resolver.bindings
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT credential_binding,last_error_message FROM billing_issuances '
            'WHERE id=%s',
            (issued.id,),
        )
        issuance_row = cursor.fetchone()
        cursor.execute(
            'SELECT error_message,result_fingerprint FROM billing_issuance_attempts '
            'WHERE billing_issuance_id=%s',
            (issued.id,),
        )
        attempts = tuple(cursor.fetchall())
    assert SECRET not in repr((issuance_row, attempts))
    assert SECRET not in caplog.text


def test_duplicate_concurrent_retry_calls_provider_at_most_once(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    document = _bill(client, source, key='d4-concurrent-retry-document')
    execution = _execution(connection, source)
    failed = _initiate(
        integration_settings,
        execution=execution,
        command=_command(source, document.json()['id'], key='d4-concurrent-retry'),
        registry=FiscalProviderRegistry({'FAKE': DeterministicFiscalProvider(
            issuance_outcomes=(FiscalIssuanceOutcome.DEFINITE_FAILURE,),
        )}),
    )

    async def exercise():
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
                database.session_factory() as first_db,
                database.session_factory() as second_db,
            ):
                first_task = asyncio.create_task(service.retry_fiscal_issuance(
                    first_db,
                    execution=execution,
                    command=_existing_command(source, failed.id, retry=True),
                    provider_registry=registry,
                ))
                await asyncio.wait_for(entered.wait(), timeout=10)
                with pytest.raises(errors.FiscalIssuanceConcurrencyConflictError):
                    await service.retry_fiscal_issuance(
                        second_db,
                        execution=execution,
                        command=_existing_command(source, failed.id, retry=True),
                        provider_registry=registry,
                    )
                release.set()
                result = await asyncio.wait_for(first_task, timeout=10)
                return result, provider.issue_calls
        finally:
            await database.dispose()

    result, calls = asyncio.run(exercise())
    assert result.state == 'SUCCEEDED'
    assert calls == 1
    assert [attempt.sequence for attempt in result.attempts] == [1, 2]


def test_retry_boundary_exception_and_binding_mismatch_are_controlled(
    client,
    sql_connection,
    integration_settings,
) -> None:
    connection, prefix = sql_connection
    source = _source(client, connection, prefix)
    execution = _execution(connection, source)

    def prepare(name):
        document = _bill(client, source, key=f'd4-{name}-document')
        failed = _initiate(
            integration_settings,
            execution=execution,
            command=_command(source, document.json()['id'], key=f'd4-{name}'),
            registry=FiscalProviderRegistry({'FAKE': DeterministicFiscalProvider(
                issuance_outcomes=(FiscalIssuanceOutcome.DEFINITE_FAILURE,),
            )}),
        )
        return document.json()['id'], failed

    boundary_document_id, boundary_failed = prepare('retry-boundary')

    class ExplodingIssueProvider(DeterministicFiscalProvider):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def issue(self, *, request, credential):
            self.calls += 1
            raise RuntimeError(SECRET)

    exploding = ExplodingIssueProvider()
    uncertain = _retry(
        integration_settings,
        execution=execution,
        command=_existing_command(source, boundary_failed.id, retry=True),
        registry=FiscalProviderRegistry({'FAKE': exploding}),
    )
    assert uncertain.state == 'UNCERTAIN'
    assert exploding.calls == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_issuances '
            'WHERE billing_document_id=%s',
            (boundary_document_id,),
        )
        assert cursor.fetchone()['count'] == 1

    mismatch_document_id, mismatch_failed = prepare('binding-mismatch')
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE billing_issuances SET request_fingerprint=%s WHERE id=%s',
            ('0' * 64, mismatch_failed.id),
        )
    unused_provider = DeterministicFiscalProvider()
    with pytest.raises(errors.FiscalProviderBindingMismatchError):
        _retry(
            integration_settings,
            execution=execution,
            command=_existing_command(source, mismatch_failed.id, retry=True),
            registry=FiscalProviderRegistry({'FAKE': unused_provider}),
        )
    assert unused_provider.issue_calls == 0
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM billing_issuances '
            'WHERE billing_document_id=%s',
            (mismatch_document_id,),
        )
        assert cursor.fetchone()['count'] == 1
