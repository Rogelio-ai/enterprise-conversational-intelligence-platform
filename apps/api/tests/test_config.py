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
