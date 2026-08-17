from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_NAME='ECIP Test API',
        APP_ENV='test',
        API_HOST='127.0.0.1',
        API_PORT=8000,
        LOG_LEVEL='INFO',
        MYSQL_HOST='mysql.test',
        MYSQL_PORT=3306,
        MYSQL_DATABASE='ecip_test',
        MYSQL_USER='ecip_test',
        MYSQL_PASSWORD='test-only-password',
        MYSQL_POOL_SIZE=1,
        MYSQL_MAX_OVERFLOW=0,
    )


@dataclass
class FakeDatabase:
    available: bool = True
    checks: int = 0
    disposed: bool = False

    async def check_connection(self) -> None:
        self.checks += 1
        if not self.available:
            raise ConnectionError('simulated unavailable database')

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def database() -> FakeDatabase:
    return FakeDatabase()
