from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.connector_security import (
    TOKEN_AUDIENCE,
    TOKEN_TYPE,
    create_connector_access_token,
    generate_machine_secret,
    secret_digest,
    verify_machine_secret,
)
from app.models import (
    PreparationDeliveryConnector,
    PreparationDeliveryConnectorCredential,
    PreparationDeliveryConnectorEnrollment,
)


router = APIRouter(prefix='/connector-auth/v1', tags=['connector-auth'])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _invalid() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid connector credentials')


class EnrollRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enrollment_id: str = Field(min_length=36, max_length=36)
    enrollment_secret: SecretStr


class CredentialOnceResponse(BaseModel):
    client_id: str
    client_secret: str
    connector_id: int
    expires_at: datetime
    token_endpoint: str = '/connector-auth/v1/token'


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_id: str = Field(min_length=36, max_length=36)
    client_secret: SecretStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_at: datetime
    audience: str = TOKEN_AUDIENCE
    access_token_type: str = TOKEN_TYPE


@router.post('/enroll', response_model=CredentialOnceResponse, status_code=status.HTTP_201_CREATED)
async def enroll(
    payload: EnrollRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialOnceResponse:
    value = await db.scalar(select(PreparationDeliveryConnectorEnrollment).where(
        PreparationDeliveryConnectorEnrollment.enrollment_id == payload.enrollment_id,
    ).with_for_update())
    now = _now()
    if (
        value is None or value.consumed_at is not None or value.revoked_at is not None
        or value.expires_at <= now or value.active_slot != 1
        or not verify_machine_secret(
            payload.enrollment_secret.get_secret_value(), value.secret_digest,
            settings=request.app.state.settings, purpose='connector-enrollment',
        )
    ):
        raise _invalid()
    connector = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == value.connector_id,
        PreparationDeliveryConnector.tenant_id == value.tenant_id,
        PreparationDeliveryConnector.organization_id == value.organization_id,
        PreparationDeliveryConnector.location_id == value.location_id,
        PreparationDeliveryConnector.status == 'ACTIVE',
    ))
    if connector is None:
        raise _invalid()
    client_secret = generate_machine_secret()
    client_id = str(uuid4())
    expires_at = now + timedelta(days=request.app.state.settings.connector_credential_ttl_days)
    credential = PreparationDeliveryConnectorCredential(
        tenant_id=value.tenant_id, organization_id=value.organization_id,
        location_id=value.location_id, connector_id=value.connector_id,
        client_id=client_id,
        secret_digest=secret_digest(
            client_secret, settings=request.app.state.settings,
            purpose='connector-credential',
        ),
        status='ACTIVE', expires_at=expires_at,
    )
    db.add(credential)
    value.consumed_at = now
    value.active_slot = None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _invalid() from exc
    return CredentialOnceResponse(
        client_id=client_id, client_secret=client_secret,
        connector_id=value.connector_id, expires_at=expires_at,
    )


@router.post('/token', response_model=TokenResponse)
async def token(
    payload: TokenRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    row = (await db.execute(
        select(PreparationDeliveryConnectorCredential, PreparationDeliveryConnector)
        .join(PreparationDeliveryConnector, PreparationDeliveryConnector.id == PreparationDeliveryConnectorCredential.connector_id)
        .where(PreparationDeliveryConnectorCredential.client_id == payload.client_id)
    )).first()
    now = _now()
    if row is None:
        raise _invalid()
    credential, connector = row
    if (
        credential.status != 'ACTIVE' or credential.revoked_at is not None
        or credential.expires_at <= now or connector.status != 'ACTIVE'
        or not verify_machine_secret(
            payload.client_secret.get_secret_value(), credential.secret_digest,
            settings=request.app.state.settings, purpose='connector-credential',
        )
    ):
        raise _invalid()
    access_token, expires_at = create_connector_access_token(
        settings=request.app.state.settings,
        credential_id=credential.id, client_id=credential.client_id,
        connector_id=connector.id, auth_subject=connector.auth_subject,
        tenant_id=credential.tenant_id, organization_id=credential.organization_id,
        location_id=credential.location_id,
    )
    credential.last_authenticated_at = now
    await db.commit()
    return TokenResponse(access_token=access_token, expires_at=expires_at)
