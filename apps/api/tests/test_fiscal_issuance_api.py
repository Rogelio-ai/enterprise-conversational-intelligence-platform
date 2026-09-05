from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db
from app.main import create_app
from app.restaurant.fiscal_issuance import errors, service
from app.restaurant.fiscal_issuance.contracts import (
    BillingIssuanceProjection,
)
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry


SECRET = 'd5-secret-must-never-be-public'


class EmptySession:
    def __init__(self) -> None:
        self.info = {
            'fiscal_provider_registry': FiscalProviderRegistry(),
            'fiscal_credential_resolver': object(),
        }


def _auth(
    *,
    tenant_id: int = 11,
    permissions: frozenset[str] | None = None,
) -> AuthenticatedContext:
    return AuthenticatedContext(
        user_id=1,
        email='fiscal@example.test',
        display_name='Fiscal User',
        tenant_id=tenant_id,
        tenant_name='Fiscal Tenant',
        tenant_slug='fiscal-tenant',
        membership_id=22,
        roles=('TENANT_ADMIN',),
        permissions=permissions if permissions is not None else frozenset({
            'restaurant_check.read',
            'restaurant_check.manage',
        }),
    )


@contextmanager
def _client(
    settings,
    database,
    *,
    auth: AuthenticatedContext | None = _auth(),
):
    app = create_app(settings=settings, database=database)
    session = EmptySession()

    async def database_session():
        yield session

    app.dependency_overrides[get_db] = database_session
    if auth is not None:
        async def authenticated_context():
            return auth

        app.dependency_overrides[get_authenticated_context] = authenticated_context
    with TestClient(app) as client:
        yield client, session


def _projection(*, state: str = 'SUCCEEDED') -> BillingIssuanceProjection:
    now = datetime(2026, 9, 4, 12, 0, 0)
    return BillingIssuanceProjection(
        id=1001,
        tenant_id=11,
        organization_id=201,
        location_id=301,
        billing_document_id=401,
        provider_key='FAKE',
        state=state,
        idempotency_key='private-command-key',
        request_schema_version=1,
        request_fingerprint='a' * 64,
        provider_idempotency_key='private-provider-operation',
        external_reference='external-safe-reference' if state == 'SUCCEEDED' else None,
        external_status=state,
        attempt_count=2,
        last_error_kind=None,
        last_error_message=SECRET,
        requested_at=now,
        completed_at=now if state in ('SUCCEEDED', 'REJECTED') else None,
        attempts=(),
    )


def _scope() -> dict[str, int]:
    return {'organization_id': 201, 'location_id': 301}


def test_create_and_identical_replay_delegate_with_idempotency(
    settings,
    database,
    monkeypatch,
) -> None:
    calls = []

    async def initiate(_db, **kwargs):
        calls.append(kwargs)
        return _projection(), len(calls) > 1

    monkeypatch.setattr(service, 'initiate_fiscal_issuance', initiate)
    with _client(settings, database) as (client, session):
        first = client.post(
            '/billing-documents/401/issuances',
            params=_scope(),
            headers={'Idempotency-Key': 'd5-create'},
            json={
                'provider_key': 'FAKE',
                'credential_binding': 'non-secret-binding',
            },
        )
        replay = client.post(
            '/billing-documents/401/issuances',
            params=_scope(),
            headers={'Idempotency-Key': 'd5-create'},
            json={
                'provider_key': 'FAKE',
                'credential_binding': 'non-secret-binding',
            },
        )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json() == replay.json()
    assert calls[0]['execution'].tenant_id == 11
    assert calls[0]['execution'].principal_id == 22
    assert calls[0]['command'].billing_document_id == 401
    assert calls[0]['command'].organization_id == 201
    assert calls[0]['command'].location_id == 301
    assert calls[0]['command'].idempotency_key == 'd5-create'
    assert calls[0]['command'].provider_key == 'FAKE'
    assert calls[0]['command'].credential_binding == 'non-secret-binding'
    assert calls[0]['provider_registry'] is session.info['fiscal_provider_registry']


def test_conflict_unknown_provider_and_invalid_shape_are_controlled(
    settings,
    database,
    monkeypatch,
) -> None:
    calls = 0

    async def initiate(_db, **kwargs):
        nonlocal calls
        calls += 1
        command = kwargs['command']
        if command.provider_key == 'UNKNOWN':
            raise errors.FiscalProviderUnavailableError(SECRET)
        raise errors.FiscalIssuanceIdempotencyConflictError()

    monkeypatch.setattr(service, 'initiate_fiscal_issuance', initiate)
    with _client(settings, database) as (client, _):
        conflict = client.post(
            '/billing-documents/401/issuances',
            params=_scope(),
            headers={'Idempotency-Key': 'd5-conflict'},
            json={'provider_key': 'FAKE'},
        )
        unavailable = client.post(
            '/billing-documents/401/issuances',
            params=_scope(),
            headers={'Idempotency-Key': 'd5-unknown'},
            json={'provider_key': 'UNKNOWN'},
        )
        override = client.post(
            '/billing-documents/401/issuances',
            params=_scope(),
            headers={'Idempotency-Key': 'd5-invalid'},
            json={
                'provider_key': 'FAKE',
                'total': '999.00',
                'lines': [],
                'tax_total': '0.00',
            },
        )

    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'FISCAL_ISSUANCE_IDEMPOTENCY_CONFLICT'
    assert unavailable.status_code == 409
    assert unavailable.json()['error']['code'] == 'FISCAL_PROVIDER_UNAVAILABLE'
    assert SECRET not in unavailable.text
    assert override.status_code == 422
    assert calls == 2


def test_get_returns_only_public_projection_and_enforces_scope(
    settings,
    database,
    monkeypatch,
) -> None:
    calls = []

    async def get_issuance(_db, **kwargs):
        calls.append(kwargs)
        if kwargs['tenant_id'] != 11 or kwargs['organization_id'] != 201:
            raise errors.FiscalIssuanceNotFoundError()
        return _projection()

    monkeypatch.setattr(service, 'get_fiscal_issuance', get_issuance)
    with _client(settings, database) as (client, _):
        response = client.get(
            '/billing-issuances/1001',
            params=_scope(),
        )
        wrong_organization = client.get(
            '/billing-issuances/1001',
            params={'organization_id': 999, 'location_id': 301},
        )

    assert response.status_code == 200
    assert set(response.json()) == {
        'id',
        'tenant_id',
        'organization_id',
        'location_id',
        'billing_document_id',
        'provider_key',
        'state',
        'external_reference',
        'external_status',
        'attempt_count',
        'requested_at',
        'completed_at',
    }
    assert SECRET not in response.text
    for private_name in (
        'credential',
        'claim_token',
        'claim_expires_at',
        'request_fingerprint',
        'provider_idempotency_key',
        'last_error',
        'attempts',
    ):
        assert private_name not in response.text
    assert wrong_organization.status_code == 404
    assert wrong_organization.json()['error']['code'] == 'FISCAL_ISSUANCE_NOT_FOUND'
    assert calls[0] == {
        'tenant_id': 11,
        'organization_id': 201,
        'location_id': 301,
        'issuance_id': 1001,
    }


def test_recover_and_retry_are_thin_d4_delegations(
    settings,
    database,
    monkeypatch,
) -> None:
    captured = {}

    async def recover(_db, **kwargs):
        captured['recover'] = kwargs
        return _projection(state='SUCCEEDED')

    async def retry(_db, **kwargs):
        captured['retry'] = kwargs
        raise errors.FiscalIssuanceRetryNotAllowedError()

    monkeypatch.setattr(service, 'recover_fiscal_issuance', recover)
    monkeypatch.setattr(service, 'retry_fiscal_issuance', retry)
    with _client(settings, database) as (client, session):
        recovered = client.post(
            '/billing-issuances/1001/recover',
            params=_scope(),
        )
        rejected_retry = client.post(
            '/billing-issuances/1001/retry',
            params=_scope(),
        )

    assert recovered.status_code == 200
    assert recovered.json()['state'] == 'SUCCEEDED'
    assert rejected_retry.status_code == 409
    assert rejected_retry.json()['error']['code'] == 'FISCAL_ISSUANCE_RETRY_NOT_ALLOWED'
    assert captured['recover']['command'].billing_issuance_id == 1001
    assert captured['recover']['command'].organization_id == 201
    assert captured['recover']['command'].location_id == 301
    assert captured['recover']['provider_registry'] is session.info[
        'fiscal_provider_registry'
    ]
    assert captured['retry']['command'].billing_issuance_id == 1001


def test_active_claim_and_foreign_tenant_map_to_public_conflicts(
    settings,
    database,
    monkeypatch,
) -> None:
    async def recover(_db, **kwargs):
        if kwargs['execution'].tenant_id != 11:
            raise errors.FiscalIssuanceNotFoundError()
        raise errors.FiscalIssuanceConcurrencyConflictError()

    monkeypatch.setattr(service, 'recover_fiscal_issuance', recover)
    with _client(settings, database) as (client, _):
        conflict = client.post(
            '/billing-issuances/1001/recover',
            params=_scope(),
        )
    with _client(settings, database, auth=_auth(tenant_id=12)) as (client, _):
        foreign = client.post(
            '/billing-issuances/1001/recover',
            params=_scope(),
        )

    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'FISCAL_ISSUANCE_CONCURRENCY_CONFLICT'
    assert foreign.status_code == 404
    assert foreign.json()['error']['code'] == 'FISCAL_ISSUANCE_NOT_FOUND'


def test_authentication_and_permissions_use_existing_dependencies(
    settings,
    database,
) -> None:
    with _client(settings, database, auth=None) as (client, _):
        missing_auth = client.get(
            '/billing-issuances/1001',
            params=_scope(),
        )
    with _client(
        settings,
        database,
        auth=_auth(permissions=frozenset()),
    ) as (client, _):
        denied_read = client.get(
            '/billing-issuances/1001',
            params=_scope(),
        )
        denied_write = client.post(
            '/billing-issuances/1001/retry',
            params=_scope(),
        )

    assert missing_auth.status_code == 401
    assert denied_read.status_code == 403
    assert denied_write.status_code == 403
