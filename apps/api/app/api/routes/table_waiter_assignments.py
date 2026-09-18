from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_location_permission
from app.core.middleware import get_correlation_id
from app.restaurant import table_waiter_assignments as service


router = APIRouter(
    prefix='/locations/{location_id}/tables', tags=['table-waiter-assignments'],
)


class WaiterAssignmentResponse(BaseModel):
    membership_id: int
    display_name: str
    email: str
    is_responsible: bool


class AssignmentSetResponse(BaseModel):
    table_resource_id: int
    location_id: int
    configured: bool
    version: int
    assignments: list[WaiterAssignmentResponse]


class EligibleWaiterResponse(BaseModel):
    membership_id: int
    display_name: str
    email: str


class EligibleWaiterListResponse(BaseModel):
    items: list[EligibleWaiterResponse]


class AssignWaiterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    waiter_membership_id: int = Field(gt=0)
    expected_version: int = Field(ge=0)


class ResponsibleWaitersRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    responsible_membership_ids: list[int] = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=1)

    @field_validator('responsible_membership_ids')
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError('Membership identifiers must be positive')
        if len(set(value)) != len(value):
            raise ValueError('Responsible waiter identifiers must be unique')
        return value


class UnassignWaiterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    expected_version: int = Field(ge=1)
    replacement_responsible_membership_ids: list[int] = Field(
        default_factory=list, max_length=100,
    )

    @field_validator('replacement_responsible_membership_ids')
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError('Membership identifiers must be positive')
        if len(set(value)) != len(value):
            raise ValueError('Replacement waiter identifiers must be unique')
        return value


def _response(value: service.AssignmentSetValue) -> AssignmentSetResponse:
    return AssignmentSetResponse(
        table_resource_id=value.table_resource_id,
        location_id=value.location_id,
        configured=bool(value.assignments),
        version=value.version,
        assignments=[
            WaiterAssignmentResponse(
                membership_id=item.membership_id,
                display_name=item.display_name,
                email=item.email,
                is_responsible=item.is_responsible,
            )
            for item in value.assignments
        ],
    )


def _domain_error(exc: service.TableWaiterAssignmentError) -> HTTPException:
    if isinstance(exc, service.TableNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get('/eligible-waiters', response_model=EligibleWaiterListResponse)
async def eligible_waiters(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_location_permission('resource.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EligibleWaiterListResponse:
    values = await service.list_eligible_waiters(
        db, tenant_id=context.tenant_id, location_id=location_id,
    )
    return EligibleWaiterListResponse(items=[EligibleWaiterResponse(
        membership_id=value.membership_id,
        display_name=value.display_name,
        email=value.email,
    ) for value in values])


@router.get('/{table_resource_id}/waiter-assignments', response_model=AssignmentSetResponse)
async def get_table_waiter_assignments(
    location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_location_permission('resource.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssignmentSetResponse:
    try:
        value = await service.get_assignment_set(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id,
        )
    except service.TableWaiterAssignmentError as exc:
        raise _domain_error(exc) from exc
    return _response(value)


@router.post(
    '/{table_resource_id}/waiter-assignments',
    response_model=AssignmentSetResponse, status_code=status.HTTP_201_CREATED,
)
async def assign_waiter(
    payload: AssignWaiterRequest,
    location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_location_permission('resource.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssignmentSetResponse:
    try:
        value = await service.assign_waiter(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id,
            waiter_membership_id=payload.waiter_membership_id,
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id,
            correlation_id=get_correlation_id(),
        )
    except service.TableWaiterAssignmentError as exc:
        await db.rollback()
        raise _domain_error(exc) from exc
    return _response(value)


@router.put(
    '/{table_resource_id}/responsible-waiters', response_model=AssignmentSetResponse,
)
async def update_responsible_waiters(
    payload: ResponsibleWaitersRequest,
    location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_location_permission('resource.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssignmentSetResponse:
    try:
        value = await service.update_responsible_waiters(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id,
            responsible_membership_ids=set(payload.responsible_membership_ids),
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id,
            correlation_id=get_correlation_id(),
        )
    except service.TableWaiterAssignmentError as exc:
        await db.rollback()
        raise _domain_error(exc) from exc
    return _response(value)


@router.post(
    '/{table_resource_id}/waiter-assignments/{waiter_membership_id}:unassign',
    response_model=AssignmentSetResponse,
)
async def unassign_waiter(
    payload: UnassignWaiterRequest,
    location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    waiter_membership_id: Annotated[int, Path(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_location_permission('resource.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssignmentSetResponse:
    try:
        value = await service.unassign_waiter(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id,
            waiter_membership_id=waiter_membership_id,
            replacement_responsible_membership_ids=set(
                payload.replacement_responsible_membership_ids
            ),
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id,
            correlation_id=get_correlation_id(),
        )
    except service.TableWaiterAssignmentError as exc:
        await db.rollback()
        raise _domain_error(exc) from exc
    return _response(value)
