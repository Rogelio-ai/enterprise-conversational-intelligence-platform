from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedContext,
    get_db,
    require_location_permission,
    require_permission,
)
from app.core.middleware import get_correlation_id
from app.models import RestaurantServiceSession, TenantMembership, User
from app.restaurant.service_sessions import errors, service
from app.restaurant.service_sessions import responsibility as responsibility_service


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


class ServiceResponsibleWaiterResponse(BaseModel):
    membership_id: int
    display_name: str
    email: str | None


class CurrentServiceResponsibilityResponse(BaseModel):
    service_session_id: int
    status: str
    initialized: bool
    version: int | None
    responsible_membership_ids: list[int]
    responsible_waiters: list[ServiceResponsibleWaiterResponse]
    replayed: bool = False


class ReplaceServiceResponsibilityRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    responsible_membership_ids: list[int] = Field(max_length=100)
    expected_version: int


class ServiceResponsibilityTransitionResponse(BaseModel):
    operation: str
    version: int
    before_responsible_membership_ids: list[int]
    after_responsible_membership_ids: list[int]
    actor_membership_id: int
    recorded_at: datetime
    correlation_id: str | None


class ServiceResponsibilityHistoryResponse(BaseModel):
    service_session_id: int
    items: list[ServiceResponsibilityTransitionResponse]


def _error(exc: Exception) -> HTTPException:
    from app.restaurant.checks.errors import RestaurantCheckError
    if isinstance(exc, RestaurantCheckError):
        return HTTPException(status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, (errors.ServiceContextError, errors.ServiceSessionNotFoundError)):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(
        exc,
        (
            errors.ResourceAlreadyOccupiedError,
            errors.ServiceStaffingConflictError,
            errors.ServiceSessionClosedError,
            errors.PartySizeConflictError,
        ),
    ):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise exc


def _responsibility_error(
    exc: responsibility_service.ServiceResponsibilityError,
) -> HTTPException:
    if isinstance(exc, responsibility_service.ServiceResponsibilityNotFoundError):
        return HTTPException(
            status.HTTP_404_NOT_FOUND,
            {'code': 'SERVICE_RESPONSIBILITY_NOT_FOUND', 'message': str(exc)},
        )
    code = 'SERVICE_RESPONSIBILITY_CONFLICT'
    if isinstance(exc, responsibility_service.ServiceResponsibilityNotInitializedError):
        code = exc.code
    elif isinstance(exc, responsibility_service.ServiceResponsibilityVersionConflictError):
        code = 'SERVICE_RESPONSIBILITY_VERSION_CONFLICT'
    elif isinstance(exc, responsibility_service.ServiceResponsibilityIdempotencyConflictError):
        code = 'SERVICE_RESPONSIBILITY_IDEMPOTENCY_CONFLICT'
    elif isinstance(exc, responsibility_service.ServiceResponsibilityValidationError):
        code = 'SERVICE_RESPONSIBILITY_VALIDATION_FAILED'
    return HTTPException(
        status.HTTP_409_CONFLICT, {'code': code, 'message': str(exc)},
    )


async def _scoped_service_session(
    db: AsyncSession, *, tenant_id: int, location_id: int, session_id: int,
) -> RestaurantServiceSession:
    value = await db.scalar(select(RestaurantServiceSession).where(
        RestaurantServiceSession.id == session_id,
        RestaurantServiceSession.tenant_id == tenant_id,
        RestaurantServiceSession.location_id == location_id,
    ))
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Restaurant Service Session not found')
    return value


async def _waiter_projection(
    db: AsyncSession, *, tenant_id: int, membership_ids: tuple[int, ...],
) -> list[ServiceResponsibleWaiterResponse]:
    if not membership_ids:
        return []
    rows = (await db.execute(
        select(TenantMembership.id, User.display_name, User.email)
        .join(User, User.id == TenantMembership.user_id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.id.in_(membership_ids),
        )
    )).all()
    by_id = {int(row.id): row for row in rows}
    return [ServiceResponsibleWaiterResponse(
        membership_id=membership_id,
        display_name=by_id[membership_id].display_name,
        email=by_id[membership_id].email,
    ) for membership_id in membership_ids if membership_id in by_id]


async def _responsibility_response(
    db: AsyncSession, *, session: RestaurantServiceSession,
    value: responsibility_service.ServiceResponsibilityValue,
) -> CurrentServiceResponsibilityResponse:
    return CurrentServiceResponsibilityResponse(
        service_session_id=session.id,
        status=session.status,
        initialized=True,
        version=value.version,
        responsible_membership_ids=list(value.responsible_membership_ids),
        responsible_waiters=await _waiter_projection(
            db, tenant_id=session.tenant_id,
            membership_ids=value.responsible_membership_ids,
        ),
        replayed=value.replayed,
    )


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


@router.get(
    '/locations/{location_id}/restaurant-service-sessions/{session_id}/responsibility',
    response_model=CurrentServiceResponsibilityResponse,
)
async def get_current_service_responsibility(
    location_id: Annotated[int, Path(gt=0)],
    session_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('restaurant_service.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentServiceResponsibilityResponse:
    session = await _scoped_service_session(
        db, tenant_id=context.tenant_id, location_id=location_id,
        session_id=session_id,
    )
    try:
        value = await responsibility_service.get_current_service_responsibility(
            db, tenant_id=context.tenant_id, service_session_id=session.id,
        )
    except responsibility_service.ServiceResponsibilityNotInitializedError:
        return CurrentServiceResponsibilityResponse(
            service_session_id=session.id,
            status=session.status,
            initialized=False,
            version=None,
            responsible_membership_ids=[],
            responsible_waiters=[],
        )
    except responsibility_service.ServiceResponsibilityError as exc:
        raise _responsibility_error(exc) from exc
    return await _responsibility_response(db, session=session, value=value)


@router.put(
    '/locations/{location_id}/restaurant-service-sessions/{session_id}/responsibility',
    response_model=CurrentServiceResponsibilityResponse,
)
async def replace_service_responsibility(
    payload: ReplaceServiceResponsibilityRequest,
    location_id: Annotated[int, Path(gt=0)],
    session_id: Annotated[int, Path(gt=0)],
    idempotency_key: Annotated[
        str,
        Header(
            alias='Idempotency-Key', min_length=1, max_length=128,
            pattern=r'^[\x21-\x7e]+$',
        ),
    ],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('restaurant_service.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentServiceResponsibilityResponse:
    session = await _scoped_service_session(
        db, tenant_id=context.tenant_id, location_id=location_id,
        session_id=session_id,
    )
    try:
        value = await responsibility_service.replace_service_responsibility(
            db,
            tenant_id=context.tenant_id,
            service_session_id=session.id,
            responsible_membership_ids=payload.responsible_membership_ids,
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id,
            idempotency_key=idempotency_key,
            correlation_id=get_correlation_id(),
        )
    except responsibility_service.ServiceResponsibilityError as exc:
        raise _responsibility_error(exc) from exc
    return await _responsibility_response(db, session=session, value=value)


@router.get(
    '/locations/{location_id}/restaurant-service-sessions/{session_id}/responsibility/history',
    response_model=ServiceResponsibilityHistoryResponse,
)
async def get_service_responsibility_history(
    location_id: Annotated[int, Path(gt=0)],
    session_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('restaurant_service.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceResponsibilityHistoryResponse:
    session = await _scoped_service_session(
        db, tenant_id=context.tenant_id, location_id=location_id,
        session_id=session_id,
    )
    try:
        values = await responsibility_service.get_service_responsibility_history(
            db, tenant_id=context.tenant_id, service_session_id=session.id,
        )
    except responsibility_service.ServiceResponsibilityError as exc:
        raise _responsibility_error(exc) from exc
    return ServiceResponsibilityHistoryResponse(
        service_session_id=session.id,
        items=[ServiceResponsibilityTransitionResponse(
            operation=value.operation,
            version=value.result_version,
            before_responsible_membership_ids=list(
                value.before_responsible_membership_ids
            ),
            after_responsible_membership_ids=list(
                value.after_responsible_membership_ids
            ),
            actor_membership_id=value.actor_membership_id,
            recorded_at=value.recorded_at,
            correlation_id=value.correlation_id,
        ) for value in values],
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
