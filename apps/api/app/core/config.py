from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        populate_by_name=True,
    )

    app_name: str = Field(default='ECIP API', alias='APP_NAME', min_length=1)
    app_env: Literal['development', 'test', 'staging', 'production'] = Field(
        default='development', alias='APP_ENV'
    )
    api_host: str = Field(default='0.0.0.0', alias='API_HOST', min_length=1)
    api_port: int = Field(default=8000, alias='API_PORT', ge=1, le=65535)
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field(
        default='INFO', alias='LOG_LEVEL'
    )

    mysql_host: str = Field(alias='MYSQL_HOST', min_length=1)
    mysql_port: int = Field(alias='MYSQL_PORT', ge=1, le=65535)
    mysql_database: str = Field(alias='MYSQL_DATABASE', min_length=1)
    mysql_user: str = Field(alias='MYSQL_USER', min_length=1)
    mysql_password: SecretStr = Field(alias='MYSQL_PASSWORD')
    mysql_pool_size: int = Field(default=5, alias='MYSQL_POOL_SIZE', ge=1, le=50)
    mysql_max_overflow: int = Field(default=10, alias='MYSQL_MAX_OVERFLOW', ge=0, le=100)

    @field_validator('app_env', mode='before')
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator('log_level', mode='before')
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator('mysql_password')
    @classmethod
    def require_database_password(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('MYSQL_PASSWORD must not be empty')
        return value

    @property
    def async_database_url(self) -> URL:
        return URL.create(
            drivername='mysql+aiomysql',
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
        )

    @property
    def sync_database_url(self) -> URL:
        return self.async_database_url.set(drivername='mysql+pymysql')


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
