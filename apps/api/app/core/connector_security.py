from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any

import jwt

from app.core.config import Settings
from app.core.security import TokenValidationError


TOKEN_TYPE = 'connector_access'
TOKEN_AUDIENCE = 'restaurant-local-connector'
PROTOCOL_VERSION = 'restaurant-local-connector-v1'


def generate_machine_secret() -> str:
    """Return at least 256 bits of cryptographically random URL-safe material."""
    return secrets.token_urlsafe(32)


def secret_digest(secret: str, *, settings: Settings, purpose: str) -> str:
    key = settings.auth_jwt_secret.get_secret_value().encode('utf-8')
    return hmac.new(key, f'{purpose}\0{secret}'.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_machine_secret(secret: str, digest: str, *, settings: Settings, purpose: str) -> bool:
    expected = secret_digest(secret, settings=settings, purpose=purpose)
    return hmac.compare_digest(expected, digest)


def create_connector_access_token(
    *, settings: Settings, credential_id: int, client_id: str, connector_id: int,
    auth_subject: str, tenant_id: int, organization_id: int, location_id: int,
    issued_at: datetime | None = None,
) -> tuple[str, datetime]:
    now = issued_at or datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.connector_access_token_ttl_minutes)
    payload: dict[str, Any] = {
        'sub': auth_subject,
        'credential_id': credential_id,
        'client_id': client_id,
        'connector_id': connector_id,
        'tenant_id': tenant_id,
        'organization_id': organization_id,
        'location_id': location_id,
        'type': TOKEN_TYPE,
        'aud': TOKEN_AUDIENCE,
        'protocol': PROTOCOL_VERSION,
        'iat': now,
        'exp': expires_at,
    }
    return jwt.encode(
        payload, settings.auth_jwt_secret.get_secret_value(),
        algorithm=settings.auth_jwt_algorithm,
    ), expires_at


def decode_connector_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    required = [
        'sub', 'credential_id', 'client_id', 'connector_id', 'tenant_id',
        'organization_id', 'location_id', 'type', 'aud', 'protocol', 'iat', 'exp',
    ]
    try:
        payload = jwt.decode(
            token, settings.auth_jwt_secret.get_secret_value(),
            algorithms=[settings.auth_jwt_algorithm], audience=TOKEN_AUDIENCE,
            options={'require': required},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError('Invalid connector token') from exc
    if payload.get('type') != TOKEN_TYPE or payload.get('protocol') != PROTOCOL_VERSION:
        raise TokenValidationError('Invalid connector token')
    try:
        for name in ('credential_id', 'connector_id', 'tenant_id', 'organization_id', 'location_id'):
            int(payload[name])
    except (TypeError, ValueError, KeyError) as exc:
        raise TokenValidationError('Invalid connector token') from exc
    return payload
