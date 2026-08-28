from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.restaurant.service_sessions import errors, service


router = APIRouter(tags=['restaurant-service'])


class OpenServiceSessionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    party_size: int = Field(ge=1, le=999)


class PartySizeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    party_size: int = Field(ge=1, le=999)


class OpenServiceSessionResponse(BaseModel):
    id: int
    resource_id: int
    party_size: int
    status: str
    join_context_key: str
    access_code: str
    access_code_version: int
    opened_at: datetime


class CurrentServiceSessionResponse(BaseModel):
    id: int
    resource_id: int
    party_size: int
    active_diner_count: int
    status: str
    join_context_key: str
    access_code_version: int
    opened_at: datetime


class RegeneratedCodeResponse(BaseModel):
    id: int
    access_code: str
    access_code_version: int


class ClosedServiceSessionResponse(BaseModel):
    id: int
    resource_id: int
    status: str
    closed_at: datetime


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (errors.ServiceContextError, errors.ServiceSessionNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(
        exc,
        (
            errors.ResourceAlreadyOccupiedError,
            errors.ServiceSessionClosedError,
            errors.PartySizeConflictError,
        ),
    ):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


@router.post(
    '/resources/{resource_id}/service-sessions',
    response_model=OpenServiceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def open_service_session(
    resource_id: Annotated[int, Path(gt=0)],
    payload: OpenServiceSessionRequest,
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_service.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OpenServiceSessionResponse:
    try:
        opened = await service.open_service_session(
            db,
            settings=request.app.state.settings,
            tenant_id=context.tenant_id,
            membership_id=context.membership_id,
            resource_id=resource_id,
            party_size=payload.party_size,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _error(exc) from exc
    value = opened.session
    return OpenServiceSessionResponse(
        id=value.id,
        resource_id=value.resource_id,
        party_size=value.party_size,
        status=value.status,
        join_context_key=value.join_context_key,
        access_code=opened.access_code,
        access_code_version=value.access_code_version,
        opened_at=value.opened_at,
    )


@router.get(
    '/resources/{resource_id}/service-sessions/current',
    response_model=CurrentServiceSessionResponse,
)
async def get_current_service_session(
    resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_service.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentServiceSessionResponse:
    try:
        value, active_count = await service.current_service_session(
            db, tenant_id=context.tenant_id, resource_id=resource_id
        )
    except Exception as exc:
        raise _error(exc) from exc
    return CurrentServiceSessionResponse(
        id=value.id,
        resource_id=value.resource_id,
        party_size=value.party_size,
        active_diner_count=active_count,
        status=value.status,
        join_context_key=value.join_context_key,
        access_code_version=value.access_code_version,
        opened_at=value.opened_at,
    )


@router.put('/restaurant-service-sessions/{session_id}/party-size', response_model=CurrentServiceSessionResponse)
async def put_party_size(
    session_id: Annotated[int, Path(gt=0)],
    payload: PartySizeRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_service.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentServiceSessionResponse:
    try:
        value, active_count = await service.update_party_size(
            db,
            tenant_id=context.tenant_id,
            session_id=session_id,
            party_size=payload.party_size,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return CurrentServiceSessionResponse(
        id=value.id,
        resource_id=value.resource_id,
        party_size=value.party_size,
        active_diner_count=active_count,
        status=value.status,
        join_context_key=value.join_context_key,
        access_code_version=value.access_code_version,
        opened_at=value.opened_at,
    )


@router.post('/restaurant-service-sessions/{session_id}/access-code/regenerate', response_model=RegeneratedCodeResponse)
async def regenerate_code(
    session_id: Annotated[int, Path(gt=0)],
    request: Request,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_service.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegeneratedCodeResponse:
    try:
        regenerated = await service.regenerate_access_code(
            db,
            settings=request.app.state.settings,
            tenant_id=context.tenant_id,
            session_id=session_id,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return RegeneratedCodeResponse(
        id=regenerated.session.id,
        access_code=regenerated.access_code,
        access_code_version=regenerated.session.access_code_version,
    )


@router.post('/restaurant-service-sessions/{session_id}/close', response_model=ClosedServiceSessionResponse)
async def close_service_session(
    session_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_service.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClosedServiceSessionResponse:
    try:
        value = await service.close_service_session(
            db,
            tenant_id=context.tenant_id,
            membership_id=context.membership_id,
            session_id=session_id,
            correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return ClosedServiceSessionResponse(
        id=value.id,
        resource_id=value.resource_id,
        status=value.status,
        closed_at=value.closed_at,
    )
