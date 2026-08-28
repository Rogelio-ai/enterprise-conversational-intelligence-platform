from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings


_password_hasher = PasswordHasher()


class TokenValidationError(Exception):
    pass


def validate_password(password: str, *, minimum_length: int) -> None:
    if len(password) < minimum_length:
        raise ValueError(f'Password must contain at least {minimum_length} characters')
    if len(password) > 128:
        raise ValueError('Password must contain at most 128 characters')


def hash_password(password: str, *, minimum_length: int = 12) -> str:
    validate_password(password, minimum_length=minimum_length)
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_access_token(
    *,
    settings: Settings,
    user_id: int,
    tenant_id: int,
    membership_id: int,
    issued_at: datetime | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    now = issued_at or datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.auth_access_token_ttl_minutes)
    )
    payload: dict[str, Any] = {
        'sub': str(user_id),
        'tenant_id': tenant_id,
        'membership_id': membership_id,
        'iat': now,
        'exp': expires_at,
        'type': 'access',
    }
    return jwt.encode(
        payload,
        settings.auth_jwt_secret.get_secret_value(),
        algorithm=settings.auth_jwt_algorithm,
    )


def decode_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret.get_secret_value(),
            algorithms=[settings.auth_jwt_algorithm],
            options={'require': ['sub', 'tenant_id', 'membership_id', 'iat', 'exp', 'type']},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError('Invalid token') from exc
    if payload.get('type') != 'access':
        raise TokenValidationError('Invalid token')
    try:
        int(payload['sub'])
        int(payload['tenant_id'])
        int(payload['membership_id'])
    except (TypeError, ValueError) as exc:
        raise TokenValidationError('Invalid token') from exc
    return payload


def create_diner_access_token(
    *,
    settings: Settings,
    diner_session_id: int,
    tenant_id: int,
    service_session_id: int,
    issued_at: datetime | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    now = issued_at or datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta or timedelta(minutes=settings.diner_access_token_ttl_minutes)
    )
    payload: dict[str, Any] = {
        'sub': str(diner_session_id),
        'tenant_id': tenant_id,
        'service_session_id': service_session_id,
        'type': 'diner_access',
        'aud': 'restaurant-diner',
        'iat': now,
        'exp': expires_at,
    }
    return (
        jwt.encode(
            payload,
            settings.auth_jwt_secret.get_secret_value(),
            algorithm=settings.auth_jwt_algorithm,
        ),
        expires_at,
    )


def decode_diner_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret.get_secret_value(),
            algorithms=[settings.auth_jwt_algorithm],
            audience='restaurant-diner',
            options={
                'require': [
                    'sub', 'tenant_id', 'service_session_id', 'type', 'aud', 'iat', 'exp'
                ]
            },
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError('Invalid token') from exc
    if payload.get('type') != 'diner_access' or payload.get('aud') != 'restaurant-diner':
        raise TokenValidationError('Invalid token')
    try:
        int(payload['sub'])
        int(payload['tenant_id'])
        int(payload['service_session_id'])
    except (TypeError, ValueError) as exc:
        raise TokenValidationError('Invalid token') from exc
    return payload
