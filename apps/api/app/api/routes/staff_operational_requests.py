from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_location_permission
from app.restaurant.operational_requests import service


router = APIRouter(prefix='/staff/operational-requests', tags=['staff-operational-requests'])
RequestStatus = Literal['PENDING', 'ACKNOWLEDGED', 'COMPLETED', 'CANCELLED']
RequestType = Literal[
    'HUMAN_ASSISTANCE',
    'CASH_PAYMENT_ASSISTANCE',
    'INVOICE_ASSISTANCE',
    'PAID_CHECK_PRINT',
]


class StaffOperationalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    location_id: int
    resource_id: int
    resource_code: str
    resource_name: str
    service_session_id: int
    diner_session_id: int
    diner_display_name: str
    request_type: str
    status: str
    related_restaurant_check_id: int | None
    resolved_by_membership_id: int | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StaffOperationalRequestListResponse(BaseModel):
    items: list[StaffOperationalRequestResponse]
    limit: int
    offset: int


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.OperationalRequestNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'Operational request not found')
    if isinstance(exc, service.OperationalRequestStateConflictError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': 'OPERATIONAL_REQUEST_STATE_CONFLICT', 'message': str(exc)},
        )
    raise exc


@router.get('', response_model=StaffOperationalRequestListResponse)
async def list_operational_requests(
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    request_status: Annotated[RequestStatus | None, Query(alias='status')] = None,
    request_type: RequestType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StaffOperationalRequestListResponse:
    values = await service.list_operational_requests(
        db,
        tenant_id=context.tenant_id,
        location_id=location_id,
        request_status=request_status,
        request_type=request_type,
        limit=limit,
        offset=offset,
    )
    return StaffOperationalRequestListResponse(items=list(values), limit=limit, offset=offset)


@router.get('/{request_id}', response_model=StaffOperationalRequestResponse)
async def read_operational_request(
    request_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext,
        Depends(require_location_permission('operational_request.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_operational_request(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
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
    transition = (
        service.acknowledge_operational_request
        if action == 'acknowledge'
        else service.complete_operational_request
    )
    try:
        return await transition(
            db,
            tenant_id=context.tenant_id,
            location_id=location_id,
            request_id=request_id,
            membership_id=context.membership_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/{request_id}/acknowledge', response_model=StaffOperationalRequestResponse)
async def acknowledge_operational_request(
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


@router.post('/{request_id}/complete', response_model=StaffOperationalRequestResponse)
async def complete_operational_request(
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
