from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.restaurant.integrations.payments.mock import DeterministicPaymentExecutor
from app.restaurant.integrations.payments.registry import PaymentExecutorRegistry
from app.restaurant.integrations.payments.resolver import (
    PaymentExecutorResolver,
    PaymentExecutorSelectionMode,
    ResolvedPaymentExecutor,
)
from app.restaurant.payments import errors
from test_canonical_order_commercial_acceptance import _scope


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _location(connection, scope, name: str) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status)
        VALUES (%s,%s,%s,%s,'America/Mexico_City','ACTIVE')
        ''',
        (scope.tenant_id, scope.organization_id, f'LOC-{uuid4().hex[:12]}', name),
    )


def _organization_location(connection, scope) -> tuple[int, int]:
    organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Other','ACTIVE')",
        (scope.tenant_id, f'ORG-{uuid4().hex[:12]}'),
    )
    location_id = _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status)
        VALUES (%s,%s,%s,'Other location','America/Mexico_City','ACTIVE')
        ''',
        (scope.tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'),
    )
    return organization_id, location_id


def _configuration(
    connection,
    scope,
    *,
    key: str,
    adapter_kind: str = 'DETERMINISTIC',
    status: str = 'ACTIVE',
    priority: int = 100,
    organization_id: int | None = None,
    location_id: int | None = None,
    capabilities: tuple[tuple[str, str], ...] = (('CARD', 'MXN'),),
) -> int:
    owner_organization_id = organization_id or scope.organization_id
    owner_location_id = location_id or scope.location_id
    configuration_id = _execute(
        connection,
        '''
        INSERT INTO location_payment_executor_configurations (
            tenant_id,organization_id,location_id,executor_key,display_name,
            adapter_kind,topology,status,selection_priority
        ) VALUES (%s,%s,%s,%s,%s,%s,'EXTERNAL',%s,%s)
        ''',
        (
            scope.tenant_id,
            owner_organization_id,
            owner_location_id,
            key,
            f'Executor {key}',
            adapter_kind,
            status,
            priority,
        ),
    )
    for method_category, currency in capabilities:
        _execute(
            connection,
            '''
            INSERT INTO location_payment_executor_capabilities (
                executor_configuration_id,tenant_id,organization_id,location_id,
                method_category,currency
            ) VALUES (%s,%s,%s,%s,%s,%s)
            ''',
            (
                configuration_id,
                scope.tenant_id,
                owner_organization_id,
                owner_location_id,
                method_category,
                currency,
            ),
        )
    return configuration_id


def _run_with_resolver(
    settings: Settings,
    registry: PaymentExecutorRegistry,
    operation: Callable[[PaymentExecutorResolver], Awaitable[ResolvedPaymentExecutor]],
) -> ResolvedPaymentExecutor:
    async def run() -> ResolvedPaymentExecutor:
        database = DatabaseManager(settings)
        session_generator = database.session()
        try:
            session: AsyncSession = await anext(session_generator)
            return await operation(PaymentExecutorResolver(session, registry))
        finally:
            await session_generator.aclose()
            await database.dispose()

    return asyncio.run(run())


def _resolve(
    settings: Settings,
    registry: PaymentExecutorRegistry,
    scope,
    *,
    mode: PaymentExecutorSelectionMode | str,
    key: str | None = None,
    method: str = 'CARD',
    currency: str = 'MXN',
    organization_id: int | None = None,
    location_id: int | None = None,
) -> ResolvedPaymentExecutor:
    return _run_with_resolver(
        settings,
        registry,
        lambda resolver: resolver.resolve(
            tenant_id=scope.tenant_id,
            organization_id=organization_id or scope.organization_id,
            location_id=location_id or scope.location_id,
            method_category=method,
            currency=currency,
            selection_mode=mode,
            executor_key=key,
        ),
    )


def test_registry_resolves_adapter_kind_and_rejects_unknown_or_duplicate() -> None:
    executor = DeterministicPaymentExecutor()
    registry = PaymentExecutorRegistry()
    registry.register('DETERMINISTIC', executor)

    assert registry.resolve('DETERMINISTIC') is executor
    with pytest.raises(errors.PaymentExecutorAdapterNotRegisteredError):
        registry.resolve('UNKNOWN')
    with pytest.raises(errors.DuplicatePaymentExecutorRegistrationError):
        registry.register('DETERMINISTIC', DeterministicPaymentExecutor())


def test_explicit_resolution_enforces_scope_status_capability_and_runtime(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, f'{prefix}-local')
    foreign_tenant = _scope(connection, f'{prefix}-foreign')
    other_location_id = _location(connection, local, 'Other location')
    other_organization_id, other_organization_location_id = _organization_location(
        connection, local
    )
    local_id = _configuration(connection, local, key='shared')
    _configuration(connection, foreign_tenant, key='shared')
    _configuration(connection, local, key='shared', location_id=other_location_id)
    _configuration(
        connection,
        local,
        key='shared',
        organization_id=other_organization_id,
        location_id=other_organization_location_id,
    )
    _configuration(connection, foreign_tenant, key='foreign-only')
    _configuration(connection, local, key='other-location-only', location_id=other_location_id)
    _configuration(
        connection,
        local,
        key='other-organization-only',
        organization_id=other_organization_id,
        location_id=other_organization_location_id,
    )
    _configuration(connection, local, key='inactive', status='INACTIVE')
    _configuration(connection, local, key='transfer', capabilities=(('TRANSFER', 'MXN'),))
    _configuration(connection, local, key='usd', capabilities=(('CARD', 'USD'),))
    _configuration(connection, local, key='missing-runtime', adapter_kind='MISSING')
    executor = DeterministicPaymentExecutor()
    registry = PaymentExecutorRegistry({'DETERMINISTIC': executor})

    resolved = _resolve(
        integration_settings,
        registry,
        local,
        mode=PaymentExecutorSelectionMode.EXPLICIT,
        key='shared',
    )
    assert resolved.configuration.id == local_id
    assert resolved.configuration.executor_key == 'shared'
    assert resolved.executor is executor

    for key in (
        'foreign-only',
        'other-location-only',
        'other-organization-only',
        'unknown',
    ):
        with pytest.raises(errors.PaymentExecutorConfigurationNotFoundError):
            _resolve(integration_settings, registry, local, mode='EXPLICIT', key=key)
    with pytest.raises(errors.PaymentExecutorConfigurationInactiveError):
        _resolve(integration_settings, registry, local, mode='EXPLICIT', key='inactive')
    with pytest.raises(errors.UnsupportedPaymentExecutorMethodError):
        _resolve(integration_settings, registry, local, mode='EXPLICIT', key='transfer')
    with pytest.raises(errors.UnsupportedPaymentExecutorCurrencyError):
        _resolve(integration_settings, registry, local, mode='EXPLICIT', key='usd')
    with pytest.raises(errors.PaymentExecutorAdapterNotRegisteredError):
        _resolve(
            integration_settings, registry, local, mode='EXPLICIT', key='missing-runtime'
        )


def test_auto_resolution_is_eligible_priority_ordered_and_stably_tied(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, f'{prefix}-local')
    foreign_tenant = _scope(connection, f'{prefix}-foreign')
    other_location_id = _location(connection, local, 'Other location')
    other_organization_id, other_organization_location_id = _organization_location(
        connection, local
    )
    _configuration(connection, local, key='inactive-first', status='INACTIVE', priority=0)
    _configuration(
        connection, local, key='wrong-method', priority=0,
        capabilities=(('TRANSFER', 'MXN'),),
    )
    _configuration(
        connection, local, key='wrong-currency', priority=0,
        capabilities=(('CARD', 'USD'),),
    )
    _configuration(
        connection, local, key='wrong-location', priority=0, location_id=other_location_id
    )
    _configuration(
        connection,
        local,
        key='wrong-organization',
        priority=0,
        organization_id=other_organization_id,
        location_id=other_organization_location_id,
    )
    _configuration(connection, foreign_tenant, key='wrong-tenant', priority=0)
    first_tied_id = _configuration(connection, local, key='first-tied', priority=10)
    _configuration(connection, local, key='second-tied', priority=10)
    _configuration(connection, local, key='lower-preference', priority=20)
    registry = PaymentExecutorRegistry({'DETERMINISTIC': DeterministicPaymentExecutor()})

    selected = _resolve(integration_settings, registry, local, mode='AUTO')
    assert selected.configuration.id == first_tied_id
    assert selected.configuration.executor_key == 'first-tied'

    single_location_id = _location(connection, local, 'Single eligible location')
    single_id = _configuration(
        connection, local, key='single', location_id=single_location_id
    )
    selected = _resolve(
        integration_settings,
        registry,
        local,
        mode='AUTO',
        location_id=single_location_id,
    )
    assert selected.configuration.id == single_id

    empty_organization_id, empty_location_id = _organization_location(connection, local)
    with pytest.raises(errors.NoEligiblePaymentExecutorError):
        _resolve(
            integration_settings,
            registry,
            local,
            mode='AUTO',
            organization_id=empty_organization_id,
            location_id=empty_location_id,
        )

    missing_runtime_location_id = _location(connection, local, 'Missing runtime location')
    _configuration(
        connection,
        local,
        key='missing-runtime',
        adapter_kind='MISSING',
        location_id=missing_runtime_location_id,
    )
    with pytest.raises(errors.PaymentExecutorAdapterNotRegisteredError):
        _resolve(
            integration_settings,
            registry,
            local,
            mode='AUTO',
            location_id=missing_runtime_location_id,
        )


def test_historical_resolution_preserves_inactive_original_and_scope(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, f'{prefix}-local')
    foreign_tenant = _scope(connection, f'{prefix}-foreign')
    other_location_id = _location(connection, local, 'Other location')
    other_organization_id, other_organization_location_id = _organization_location(
        connection, local
    )
    historical_id = _configuration(
        connection,
        local,
        key='historical',
        adapter_kind='ORIGINAL',
        status='INACTIVE',
        priority=100,
    )
    _configuration(
        connection, local, key='new-auto-preference', adapter_kind='NEW', priority=0
    )
    original = DeterministicPaymentExecutor()
    registry = PaymentExecutorRegistry(
        {'ORIGINAL': original, 'NEW': DeterministicPaymentExecutor()}
    )

    resolved = _run_with_resolver(
        integration_settings,
        registry,
        lambda resolver: resolver.resolve_historical(
            tenant_id=local.tenant_id,
            organization_id=local.organization_id,
            location_id=local.location_id,
            executor_configuration_id=historical_id,
        ),
    )
    assert resolved.configuration.id == historical_id
    assert resolved.configuration.status == 'INACTIVE'
    assert resolved.configuration.adapter_kind == 'ORIGINAL'
    assert resolved.executor is original

    for tenant_id, organization_id, location_id in (
        (
            foreign_tenant.tenant_id,
            foreign_tenant.organization_id,
            foreign_tenant.location_id,
        ),
        (local.tenant_id, local.organization_id, other_location_id),
        (local.tenant_id, other_organization_id, other_organization_location_id),
    ):
        with pytest.raises(errors.PaymentExecutorConfigurationNotFoundError):
            _run_with_resolver(
                integration_settings,
                registry,
                lambda resolver, tenant_id=tenant_id,
                organization_id=organization_id, location_id=location_id:
                    resolver.resolve_historical(
                        tenant_id=tenant_id,
                        organization_id=organization_id,
                        location_id=location_id,
                        executor_configuration_id=historical_id,
                    ),
            )

    with pytest.raises(errors.PaymentExecutorAdapterNotRegisteredError):
        _run_with_resolver(
            integration_settings,
            PaymentExecutorRegistry({'NEW': DeterministicPaymentExecutor()}),
            lambda resolver: resolver.resolve_historical(
                tenant_id=local.tenant_id,
                organization_id=local.organization_id,
                location_id=local.location_id,
                executor_configuration_id=historical_id,
            ),
        )


def test_invalid_selection_and_cash_do_not_enter_provider_resolution(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    local = _scope(connection, prefix)
    registry = PaymentExecutorRegistry()

    with pytest.raises(errors.InvalidPaymentExecutorSelectionError):
        _resolve(integration_settings, registry, local, mode='EXPLICIT')
    with pytest.raises(errors.InvalidPaymentExecutorSelectionError):
        _resolve(integration_settings, registry, local, mode='RANDOM')
    with pytest.raises(errors.InvalidPaymentExecutorSelectionError):
        _resolve(integration_settings, registry, local, mode='AUTO', key='not-allowed')
    with pytest.raises(errors.UnsupportedPaymentExecutorMethodError):
        _resolve(integration_settings, registry, local, mode='AUTO', method='CASH')
