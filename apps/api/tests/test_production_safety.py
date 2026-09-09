from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.restaurant.integrations.fiscal.errors import FiscalProviderNotRegisteredError
from app.restaurant.payments.errors import PaymentExecutorAdapterNotRegisteredError


def _production(settings, **updates):
    return settings.model_copy(
        update={
            'app_env': 'production',
            'public_origin': 'https://pilot.example.invalid',
            'trusted_hosts': 'pilot.example.invalid,testserver',
            'docs_enabled': False,
            'electronic_payments_enabled': False,
            'cfdi_issuance_enabled': False,
            'connector_delivery_enabled': False,
            'external_pos_enabled': False,
            **updates,
        }
    )


def test_production_configuration_refuses_enabled_external_capability(settings) -> None:
    values = settings.model_dump(by_alias=True)
    values.update(APP_ENV='production', ELECTRONIC_PAYMENTS_ENABLED=True)
    with pytest.raises(ValidationError, match='explicitly disabled'):
        type(settings)(_env_file=None, **values)


def test_production_disables_docs_and_external_capabilities(settings, database) -> None:
    app = create_app(settings=_production(settings), database=database)

    with TestClient(app) as client:
        assert client.get('/docs').status_code == 404
        connector = client.get('/connector/v1/dispatches/eligible')
        pos = client.get('/restaurant-orders/1/pos-submission')

    assert connector.status_code == 503
    assert connector.json()['error']['code'] == 'capability_disabled'
    assert pos.status_code == 503
    with pytest.raises(PaymentExecutorAdapterNotRegisteredError):
        app.state.payment_executor_registry.resolve('CONEKTA')
    with pytest.raises(FiscalProviderNotRegisteredError):
        app.state.fiscal_provider_registry.resolve('FINKOK')


def test_security_headers_and_trusted_host(settings, database) -> None:
    app = create_app(settings=_production(settings), database=database)

    with TestClient(app) as client:
        response = client.get('/health')
        rejected = client.get('/health', headers={'host': 'untrusted.example'})

    assert response.status_code == 200
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert rejected.status_code == 400


def test_staff_login_rate_limit_is_bounded(settings, database) -> None:
    app = create_app(
        settings=_production(settings, staff_login_rate_limit_per_minute=1),
        database=database,
    )

    with TestClient(app) as client:
        first = client.post('/auth/login', json={'email': 'nobody@example.invalid', 'password': 'bad'})
        second = client.post('/auth/login', json={'email': 'nobody@example.invalid', 'password': 'bad'})

    assert first.status_code != 429
    assert second.status_code == 429
    assert second.headers['retry-after'] == '60'
