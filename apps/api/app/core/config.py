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

    auth_jwt_secret: SecretStr = Field(alias='AUTH_JWT_SECRET', min_length=32)
    auth_jwt_algorithm: Literal['HS256', 'HS384', 'HS512'] = Field(
        default='HS256', alias='AUTH_JWT_ALGORITHM'
    )
    auth_access_token_ttl_minutes: int = Field(
        default=60, alias='AUTH_ACCESS_TOKEN_TTL_MINUTES', ge=1, le=1440
    )
    restaurant_access_code_secret: SecretStr = Field(
        alias='RESTAURANT_ACCESS_CODE_SECRET', min_length=32
    )
    diner_access_token_ttl_minutes: int = Field(
        default=720, alias='DINER_ACCESS_TOKEN_TTL_MINUTES', ge=1, le=720
    )
    connector_access_token_ttl_minutes: int = Field(
        default=5, alias='CONNECTOR_ACCESS_TOKEN_TTL_MINUTES', ge=1, le=15
    )
    connector_enrollment_ttl_minutes: int = Field(
        default=15, alias='CONNECTOR_ENROLLMENT_TTL_MINUTES', ge=1, le=60
    )
    connector_credential_ttl_days: int = Field(
        default=365, alias='CONNECTOR_CREDENTIAL_TTL_DAYS', ge=1, le=730
    )
    preparation_dispatch_claim_lease_seconds: int = Field(
        default=120, alias='PREPARATION_DISPATCH_CLAIM_LEASE_SECONDS', ge=30, le=600
    )
    password_min_length: int = Field(default=12, alias='PASSWORD_MIN_LENGTH', ge=8, le=128)
    finkok_environment: Literal['demo', 'production'] = Field(
        default='demo', alias='FINKOK_ENVIRONMENT'
    )
    finkok_wsdl_endpoint: str | None = Field(
        default=None, alias='FINKOK_WSDL_ENDPOINT', min_length=1
    )
    finkok_connect_timeout_seconds: float = Field(
        default=5.0, alias='FINKOK_CONNECT_TIMEOUT_SECONDS', gt=0, le=60
    )
    finkok_read_timeout_seconds: float = Field(
        default=20.0, alias='FINKOK_READ_TIMEOUT_SECONDS', gt=0, le=120
    )

    @field_validator('app_env', mode='before')
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator('log_level', mode='before')
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator('finkok_environment', mode='before')
    @classmethod
    def normalize_finkok_environment(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator('mysql_password')
    @classmethod
    def require_database_password(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('MYSQL_PASSWORD must not be empty')
        return value

    @field_validator('auth_jwt_secret')
    @classmethod
    def require_auth_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError('AUTH_JWT_SECRET must not be empty')
        return value

    @field_validator('restaurant_access_code_secret')
    @classmethod
    def require_restaurant_access_code_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError('RESTAURANT_ACCESS_CODE_SECRET must not be empty')
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

    @property
    def resolved_finkok_wsdl_endpoint(self) -> str:
        if self.finkok_wsdl_endpoint is not None:
            return self.finkok_wsdl_endpoint
        host = (
            'demo-facturacion.finkok.com'
            if self.finkok_environment == 'demo'
            else 'facturacion.finkok.com'
        )
        return f'https://{host}/servicios/soap/stamp.wsdl'

    @property
    def finkok_service_endpoint(self) -> str:
        endpoint = self.resolved_finkok_wsdl_endpoint
        return endpoint[:-5] if endpoint.endswith('.wsdl') else endpoint


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
