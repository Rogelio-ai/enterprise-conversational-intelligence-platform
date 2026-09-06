from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import TokenValidationError, decode_diner_access_token
from app.models import DinerSession, RestaurantServiceSession


logger = logging.getLogger('ecip.restaurant_service')
diner_oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/diner-sessions/join')


@dataclass(frozen=True)
class DinerAuthenticatedContext:
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    service_session_id: int
    diner_session_id: int
    conversation_id: int
    conversation_participant_id: int
    customer_id: int | None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid diner authentication credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )


def _session_closed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            'state': 'SESSION_CLOSED',
            'code': 'SESSION_CLOSED',
            'required_input': [],
            'allowed_actions': [],
            'next_action': 'LEAVE_SESSION',
        },
    )


async def get_diner_authenticated_context(
    request: Request,
    token: Annotated[str, Depends(diner_oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DinerAuthenticatedContext:
    try:
        payload = decode_diner_access_token(token, settings=request.app.state.settings)
        diner_id = int(payload['sub'])
        tenant_id = int(payload['tenant_id'])
        service_session_id = int(payload['service_session_id'])
    except (TokenValidationError, TypeError, ValueError, KeyError) as exc:
        logger.info('Diner authorization denied', extra={'event': 'diner_authorization_denied', 'outcome': 'invalid_token'})
        raise _unauthorized() from exc
    row = (
        await db.execute(
            select(DinerSession, RestaurantServiceSession)
            .join(RestaurantServiceSession, RestaurantServiceSession.id == DinerSession.service_session_id)
            .where(
                DinerSession.id == diner_id,
                DinerSession.tenant_id == tenant_id,
                DinerSession.service_session_id == service_session_id,
            )
        )
    ).first()
    if row is None:
        logger.info('Diner authorization denied', extra={'event': 'diner_authorization_denied', 'tenant_id': tenant_id, 'diner_session_id': diner_id, 'outcome': 'not_found'})
        raise _unauthorized()
    diner, service = row
    if (
        diner.status != 'ACTIVE'
        or diner.active_slot != 1
        or service.status != 'OPEN'
        or service.open_slot != 1
        or service.tenant_id != tenant_id
    ):
        logger.info('Diner authorization denied', extra={'event': 'diner_authorization_denied', 'tenant_id': tenant_id, 'service_session_id': service.id, 'diner_session_id': diner.id, 'outcome': 'closed'})
        # The signed token and its exact tenant/diner/service tuple resolved before
        # this distinction is returned; unknown or mismatched identities stay 401.
        raise _session_closed()
    request.state.tenant_id = tenant_id
    request.state.diner_session_id = diner.id
    return DinerAuthenticatedContext(
        tenant_id=tenant_id,
        organization_id=diner.organization_id,
        location_id=diner.location_id,
        resource_id=diner.resource_id,
        service_session_id=diner.service_session_id,
        diner_session_id=diner.id,
        conversation_id=diner.conversation_id,
        conversation_participant_id=diner.conversation_participant_id,
        customer_id=diner.customer_id,
    )
