from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_location_permission
from app.api.routes.staff_operational_requests import (
    RequestStatus,
    RequestType,
    StaffOperationalRequestResponse,
)
from app.api.routes.conversations import validate_language
from app.restaurant.operational_requests import service


router = APIRouter(
    prefix='/waiter/operational-requests',
    tags=['waiter-operational-requests'],
)
WaiterView = Literal['active', 'hidden']


class WaiterOperationalRequestResponse(StaffOperationalRequestResponse):
    current_waiter_entered_at: datetime | None
    current_waiter_hidden_at: datetime | None


class WaiterOperationalRequestListResponse(BaseModel):
    items: list[WaiterOperationalRequestResponse]
    limit: int
    offset: int


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content_text: str = Field(min_length=1, max_length=10_000)
    modality: Literal['TEXT', 'VOICE', 'TOUCH'] = 'TEXT'
    language: str | None = Field(default=None, max_length=63)
    language_source: Literal['DECLARED', 'DETECTED', 'INHERITED'] | None = None

    _language = field_validator('language')(validate_language)

    @field_validator('content_text')
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Message content cannot be blank')
        return normalized

    @model_validator(mode='after')
    def validate_language_pair(self):
        if (self.language is None) != (self.language_source is None):
            raise ValueError('language and language_source must be supplied together')
        return self


class RespondResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    message_id: int
    conversation_id: int
    operational_request_id: int
    participant_id: int
    author_type: str
    sequence_number: int
    modality: str
    content_text: str
    language: str | None
    language_source: str | None
    created_at: datetime


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.OperationalRequestNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'Operational request not found')
    if isinstance(exc, service.OperationalRequestStateConflictError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': 'OPERATIONAL_REQUEST_STATE_CONFLICT', 'message': str(exc)},
        )
    raise exc


@router.get('', response_model=WaiterOperationalRequestListResponse)
async def list_waiter_operational_requests(
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    request_status: Annotated[RequestStatus | None, Query(alias='status')] = None,
    request_type: RequestType | None = None,
    view: WaiterView = 'active',
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WaiterOperationalRequestListResponse:
    values = await service.list_waiter_operational_requests(
        db,
        tenant_id=context.tenant_id,
        location_id=location_id,
        membership_id=context.membership_id,
        request_status=request_status,
        request_type=request_type,
        view=view,
        limit=limit,
        offset=offset,
    )
    return WaiterOperationalRequestListResponse(
        items=list(values), limit=limit, offset=offset,
    )


@router.get('/{request_id}', response_model=WaiterOperationalRequestResponse)
async def read_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_waiter_operational_request(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            membership_id=context.membership_id,
            request_id=request_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


async def _transition(
    *,
    action: Literal['acknowledge', 'complete'],
    request_id: int,
    location_id: int,
    context: AuthenticatedContext,
    db: AsyncSession,
) -> object:
    try:
        return await service.transition_waiter_operational_request(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            membership_id=context.membership_id,
            request_id=request_id,
            target_status='ACKNOWLEDGED' if action == 'acknowledge' else 'COMPLETED',
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/{request_id}/acknowledge', response_model=WaiterOperationalRequestResponse)
async def acknowledge_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _transition(
        action='acknowledge',
        request_id=request_id,
        location_id=location_id,
        context=context,
        db=db,
    )


@router.post('/{request_id}/complete', response_model=WaiterOperationalRequestResponse)
async def complete_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _transition(
        action='complete',
        request_id=request_id,
        location_id=location_id,
        context=context,
        db=db,
    )


async def _handoff(
    *,
    action: Literal['pick-up', 'deliver'],
    request_id: int,
    location_id: int,
    context: AuthenticatedContext,
    db: AsyncSession,
) -> object:
    try:
        return await service.handoff_waiter_preparation_request(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            membership_id=context.membership_id,
            request_id=request_id,
            action=action,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/{request_id}/pick-up', response_model=WaiterOperationalRequestResponse)
async def pick_up_waiter_preparation_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _handoff(
        action='pick-up', request_id=request_id, location_id=location_id,
        context=context, db=db,
    )


@router.post('/{request_id}/deliver', response_model=WaiterOperationalRequestResponse)
async def deliver_waiter_preparation_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _handoff(
        action='deliver', request_id=request_id, location_id=location_id,
        context=context, db=db,
    )


@router.post('/{request_id}/respond', response_model=RespondResponse)
async def respond_to_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    payload: RespondRequest,
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[
        str,
        Header(
            alias='Idempotency-Key',
            min_length=1,
            max_length=128,
            pattern=r'^[\x21-\x7e]+$',
        ),
    ],
) -> object:
    try:
        return await service.respond_to_operational_request(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            membership_id=context.membership_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _error(exc) from exc


async def _personal_state_mutation(
    *,
    action: Literal['entered', 'hide', 'show'],
    request_id: int,
    location_id: int,
    context: AuthenticatedContext,
    db: AsyncSession,
) -> object:
    try:
        return await service.mutate_waiter_operational_request_state(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            membership_id=context.membership_id,
            request_id=request_id,
            action=action,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/{request_id}/entered', response_model=WaiterOperationalRequestResponse)
async def enter_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _personal_state_mutation(
        action='entered', request_id=request_id, location_id=location_id,
        context=context, db=db,
    )


@router.post('/{request_id}/hide', response_model=WaiterOperationalRequestResponse)
async def hide_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _personal_state_mutation(
        action='hide', request_id=request_id, location_id=location_id,
        context=context, db=db,
    )


@router.post('/{request_id}/show', response_model=WaiterOperationalRequestResponse)
async def show_waiter_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await _personal_state_mutation(
        action='show', request_id=request_id, location_id=location_id,
        context=context, db=db,
    )
