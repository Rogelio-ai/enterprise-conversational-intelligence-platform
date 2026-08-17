from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    validate_password,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    password_hash = hash_password('Correct Horse Battery Staple')

    assert password_hash.startswith('$argon2id$')
    assert password_hash != 'Correct Horse Battery Staple'
    assert verify_password('Correct Horse Battery Staple', password_hash)
    assert not verify_password('wrong password', password_hash)


def test_password_length_bounds() -> None:
    with pytest.raises(ValueError):
        validate_password('short', minimum_length=12)
    with pytest.raises(ValueError):
        validate_password('x' * 129, minimum_length=12)


def test_access_token_round_trip(settings) -> None:
    token = create_access_token(
        settings=settings,
        user_id=7,
        tenant_id=11,
        membership_id=13,
    )

    payload = decode_access_token(token, settings=settings)

    assert payload['sub'] == '7'
    assert payload['tenant_id'] == 11
    assert payload['membership_id'] == 13
    assert payload['type'] == 'access'
    assert 'iat' in payload
    assert 'exp' in payload


def test_expired_access_token_is_rejected(settings) -> None:
    token = create_access_token(
        settings=settings,
        user_id=7,
        tenant_id=11,
        membership_id=13,
        issued_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        expires_delta=timedelta(minutes=1),
    )

    with pytest.raises(TokenValidationError):
        decode_access_token(token, settings=settings)


def test_token_signed_with_another_secret_is_rejected(settings) -> None:
    other_settings = settings.model_copy(
        update={'auth_jwt_secret': settings.auth_jwt_secret.__class__('another-test-secret-that-is-over-32-characters')}
    )
    token = create_access_token(
        settings=other_settings,
        user_id=7,
        tenant_id=11,
        membership_id=13,
    )

    with pytest.raises(TokenValidationError):
        decode_access_token(token, settings=settings)
