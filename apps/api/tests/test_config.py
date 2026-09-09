from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


_MYSQL_ENVIRONMENT_KEYS = (
    'MYSQL_HOST',
    'MYSQL_PORT',
    'MYSQL_DATABASE',
    'MYSQL_USER',
    'MYSQL_PASSWORD',
)


def test_database_configuration_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _MYSQL_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_database_url_safely_encodes_credentials() -> None:
    settings = Settings(
        _env_file=None,
        MYSQL_HOST='mysql',
        MYSQL_PORT=3306,
        MYSQL_DATABASE='ecip',
        MYSQL_USER='user@name',
        MYSQL_PASSWORD='p@ss:/word',
        RESTAURANT_ACCESS_CODE_SECRET='test-only-independent-access-code-secret-32-chars',
    )

    rendered = settings.async_database_url.render_as_string(hide_password=False)
    sync_rendered = settings.sync_database_url.render_as_string(hide_password=False)

    assert 'user%40name' in rendered
    assert 'p%40ss%3A%2Fword' in rendered
    assert 'p@ss:/word' not in rendered
    assert 'p%40ss%3A%2Fword' in sync_rendered
    assert '***' not in sync_rendered


def test_password_is_not_exposed_by_settings_repr(settings: Settings) -> None:
    assert settings.mysql_password.get_secret_value() not in repr(settings)


def test_conekta_test_configuration_requires_complete_runtime_boundary(
    settings: Settings,
) -> None:
    values = settings.model_dump(by_alias=True)
    values.update(CONEKTA_ENVIRONMENT='test')
    with pytest.raises(ValidationError, match='credential binding and private key'):
        Settings(_env_file=None, **values)

    values.update(
        CONEKTA_CREDENTIAL_BINDING='pilot-location-conekta-test',
        CONEKTA_PRIVATE_KEY='test-private-key-never-persist',
    )
    configured = Settings(_env_file=None, **values)

    assert configured.conekta_environment == 'test'
    assert configured.conekta_credential_binding == 'pilot-location-conekta-test'
    assert 'test-private-key-never-persist' not in repr(configured)


def test_conekta_runtime_secret_is_rejected_when_disabled(settings: Settings) -> None:
    values = settings.model_dump(by_alias=True)
    values.update(CONEKTA_PRIVATE_KEY='unused-private-key')
    with pytest.raises(ValidationError, match='CONEKTA_ENVIRONMENT=test'):
        Settings(_env_file=None, **values)


def test_conekta_test_configuration_is_forbidden_in_production(
    settings: Settings,
) -> None:
    values = settings.model_dump(by_alias=True)
    values.update(
        APP_ENV='production',
        ELECTRONIC_PAYMENTS_ENABLED=False,
        CFDI_ISSUANCE_ENABLED=False,
        CONNECTOR_DELIVERY_ENABLED=False,
        EXTERNAL_POS_ENABLED=False,
        CONEKTA_ENVIRONMENT='test',
        CONEKTA_CREDENTIAL_BINDING='pilot-location-conekta-test',
        CONEKTA_PRIVATE_KEY='test-private-key-never-persist',
    )
    with pytest.raises(ValidationError, match='forbidden in production'):
        Settings(_env_file=None, **values)
