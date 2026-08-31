from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.connector_security import decode_connector_access_token
from app.core.security import TokenValidationError
from app.models import PreparationDeliveryConnector, PreparationDeliveryConnectorCredential, Tenant


bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class ConnectorContext:
    credential_id: int
    client_id: str
    connector_id: int
    auth_subject: str
    tenant_id: int
    organization_id: int
    location_id: int


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, 'Invalid connector authentication credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )


async def get_connector_context(
    request: Request,
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> ConnectorContext:
    if authorization is None or authorization.scheme.casefold() != 'bearer':
        raise _unauthorized()
    try:
        payload = decode_connector_access_token(
            authorization.credentials, settings=request.app.state.settings,
        )
        credential_id = int(payload['credential_id'])
        connector_id = int(payload['connector_id'])
        tenant_id = int(payload['tenant_id'])
        organization_id = int(payload['organization_id'])
        location_id = int(payload['location_id'])
    except (TokenValidationError, KeyError, TypeError, ValueError) as exc:
        raise _unauthorized() from exc
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = (await db.execute(
        select(PreparationDeliveryConnectorCredential, PreparationDeliveryConnector, Tenant)
        .join(PreparationDeliveryConnector, PreparationDeliveryConnector.id == PreparationDeliveryConnectorCredential.connector_id)
        .join(Tenant, Tenant.id == PreparationDeliveryConnectorCredential.tenant_id)
        .where(
            PreparationDeliveryConnectorCredential.id == credential_id,
            PreparationDeliveryConnectorCredential.client_id == payload['client_id'],
            PreparationDeliveryConnectorCredential.connector_id == connector_id,
            PreparationDeliveryConnectorCredential.tenant_id == tenant_id,
            PreparationDeliveryConnectorCredential.organization_id == organization_id,
            PreparationDeliveryConnectorCredential.location_id == location_id,
        )
    )).first()
    if row is None:
        raise _unauthorized()
    credential, connector, tenant = row
    if (
        credential.status != 'ACTIVE' or credential.revoked_at is not None
        or credential.expires_at <= now or connector.status != 'ACTIVE'
        or tenant.status != 'ACTIVE' or connector.auth_subject != payload['sub']
    ):
        raise _unauthorized()
    request.state.tenant_id = tenant_id
    request.state.connector_id = connector_id
    return ConnectorContext(
        credential_id=credential.id, client_id=credential.client_id,
        connector_id=connector.id, auth_subject=connector.auth_subject,
        tenant_id=tenant_id, organization_id=organization_id, location_id=location_id,
    )
