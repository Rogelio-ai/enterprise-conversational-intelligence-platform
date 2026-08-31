from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.connector_security import generate_machine_secret, secret_digest
from app.models import (
    PreparationDeliveryConnector,
    PreparationDeliveryConnectorCredential,
    PreparationDeliveryConnectorEnrollment,
)


router = APIRouter(tags=['preparation-delivery-connectors'])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


async def _connector(db: AsyncSession, tenant_id: int, connector_id: int) -> PreparationDeliveryConnector:
    value = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == connector_id,
        PreparationDeliveryConnector.tenant_id == tenant_id,
    ))
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Preparation Delivery Connector not found')
    return value


class EnrollmentOnceResponse(BaseModel):
    enrollment_id: str
    enrollment_secret: str
    connector_id: int
    expires_at: datetime


class CredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: str
    connector_id: int
    status: str
    expires_at: datetime
    revoked_at: datetime | None
    last_authenticated_at: datetime | None
    replaces_credential_id: int | None
    created_at: datetime


class RotatedCredentialOnceResponse(BaseModel):
    id: int
    client_id: str
    client_secret: str
    connector_id: int
    expires_at: datetime
    replaces_credential_id: int | None


@router.post('/preparation-delivery-connectors/{connector_id}/enrollments', response_model=EnrollmentOnceResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    connector_id: Annotated[int, Path(gt=0)], request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.connector.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnrollmentOnceResponse:
    connector = await _connector(db, context.tenant_id, connector_id)
    now = _now()
    credential_exists = await db.scalar(select(PreparationDeliveryConnectorCredential.id).where(
        PreparationDeliveryConnectorCredential.connector_id == connector.id,
    ).limit(1))
    if credential_exists is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            'Connector is already enrolled; use credential rotation',
        )
    existing = await db.scalar(select(PreparationDeliveryConnectorEnrollment).where(
        PreparationDeliveryConnectorEnrollment.connector_id == connector.id,
        PreparationDeliveryConnectorEnrollment.active_slot == 1,
    ).with_for_update())
    if existing is not None and existing.expires_at > now and existing.revoked_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Connector already has an active enrollment')
    if existing is not None:
        existing.active_slot = None
    enrollment_secret = generate_machine_secret()
    enrollment_id = str(uuid4())
    expires_at = now + timedelta(minutes=request.app.state.settings.connector_enrollment_ttl_minutes)
    value = PreparationDeliveryConnectorEnrollment(
        tenant_id=connector.tenant_id, organization_id=connector.organization_id,
        location_id=connector.location_id, connector_id=connector.id,
        enrollment_id=enrollment_id,
        secret_digest=secret_digest(
            enrollment_secret, settings=request.app.state.settings,
            purpose='connector-enrollment',
        ),
        expires_at=expires_at, created_by_membership_id=context.membership_id,
        active_slot=1,
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, 'Connector enrollment conflicted') from exc
    return EnrollmentOnceResponse(
        enrollment_id=enrollment_id, enrollment_secret=enrollment_secret,
        connector_id=connector.id, expires_at=expires_at,
    )


@router.get('/preparation-delivery-connectors/{connector_id}/credentials', response_model=tuple[CredentialResponse, ...])
async def list_credentials(
    connector_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.connector.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    await _connector(db, context.tenant_id, connector_id)
    return tuple((await db.execute(select(PreparationDeliveryConnectorCredential).where(
        PreparationDeliveryConnectorCredential.tenant_id == context.tenant_id,
        PreparationDeliveryConnectorCredential.connector_id == connector_id,
    ).order_by(PreparationDeliveryConnectorCredential.id))).scalars().all())


@router.post('/preparation-delivery-connectors/{connector_id}/credentials/rotate', response_model=RotatedCredentialOnceResponse, status_code=status.HTTP_201_CREATED)
async def rotate_credential(
    connector_id: Annotated[int, Path(gt=0)], request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.connector.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RotatedCredentialOnceResponse:
    connector = await _connector(db, context.tenant_id, connector_id)
    previous = await db.scalar(select(PreparationDeliveryConnectorCredential).where(
        PreparationDeliveryConnectorCredential.connector_id == connector.id,
    ).order_by(PreparationDeliveryConnectorCredential.id.desc()).limit(1))
    if previous is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            'Connector must complete first enrollment before credential rotation',
        )
    secret = generate_machine_secret()
    client_id = str(uuid4())
    expires_at = _now() + timedelta(days=request.app.state.settings.connector_credential_ttl_days)
    value = PreparationDeliveryConnectorCredential(
        tenant_id=connector.tenant_id, organization_id=connector.organization_id,
        location_id=connector.location_id, connector_id=connector.id,
        client_id=client_id,
        secret_digest=secret_digest(secret, settings=request.app.state.settings, purpose='connector-credential'),
        status='ACTIVE', expires_at=expires_at,
        replaces_credential_id=previous.id if previous is not None else None,
    )
    db.add(value)
    await db.commit()
    await db.refresh(value)
    return RotatedCredentialOnceResponse(
        id=value.id, client_id=client_id, client_secret=secret,
        connector_id=connector.id, expires_at=expires_at,
        replaces_credential_id=value.replaces_credential_id,
    )


@router.post('/preparation-delivery-connectors/{connector_id}/credentials/{credential_id}/revoke', response_model=CredentialResponse)
async def revoke_credential(
    connector_id: Annotated[int, Path(gt=0)], credential_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.connector.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    value = await db.scalar(select(PreparationDeliveryConnectorCredential).where(
        PreparationDeliveryConnectorCredential.id == credential_id,
        PreparationDeliveryConnectorCredential.connector_id == connector_id,
        PreparationDeliveryConnectorCredential.tenant_id == context.tenant_id,
    ).with_for_update())
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Connector credential not found')
    if value.status == 'ACTIVE':
        value.status = 'REVOKED'
        value.revoked_at = _now()
        await db.commit()
        await db.refresh(value)
    return value


@router.post('/preparation-delivery-connectors/{connector_id}/enrollments/{enrollment_id}/revoke', status_code=status.HTTP_200_OK)
async def revoke_enrollment(
    connector_id: Annotated[int, Path(gt=0)], enrollment_id: str,
    context: Annotated[AuthenticatedContext, Depends(require_permission('preparation.connector.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    value = await db.scalar(select(PreparationDeliveryConnectorEnrollment).where(
        PreparationDeliveryConnectorEnrollment.enrollment_id == enrollment_id,
        PreparationDeliveryConnectorEnrollment.connector_id == connector_id,
        PreparationDeliveryConnectorEnrollment.tenant_id == context.tenant_id,
    ).with_for_update())
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Connector enrollment not found')
    if value.consumed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Consumed enrollment cannot be revoked')
    if value.revoked_at is None:
        value.revoked_at = _now()
        value.active_slot = None
        await db.commit()
