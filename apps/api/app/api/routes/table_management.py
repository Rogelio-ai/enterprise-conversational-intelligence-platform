from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_location_permission
from app.core.middleware import get_correlation_id
from app.restaurant import table_management as service


router = APIRouter(
    prefix='/locations/{location_id}/table-management', tags=['table-management'],
)


class DiningSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    location_id: int
    code: str
    name: str
    movable: bool
    status: str


class DiningSectionListResponse(BaseModel):
    items: list[DiningSectionResponse]


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resource_id: int
    code: str
    name: str
    physical_capacity: int | None
    dining_section_id: int | None
    dining_section_code: str | None
    dining_section_name: str | None
    administrative_status: str | None
    individually_movable: bool
    section_movable: bool
    effective_movable: bool
    metadata_version: int | None
    operational_status: str
    active_group_id: int | None
    is_group_representative: bool


class TableListResponse(BaseModel):
    items: list[TableResponse]


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    representative_resource_id: int
    representative_code: str
    status: str
    version: int
    member_resource_ids: tuple[int, ...]
    member_codes: tuple[str, ...]
    responsible_membership_ids: tuple[int, ...]
    derived_capacity: int
    created_by_membership_id: int
    created_at: datetime
    closed_by_membership_id: int | None
    closed_at: datetime | None


class GroupProposalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    representative_resource_id: int = Field(gt=0)
    joined_resource_ids: list[int] = Field(min_length=1, max_length=100)

    @field_validator('joined_resource_ids')
    @classmethod
    def unique_positive(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values) or len(values) != len(set(values)):
            raise ValueError('Identifiers must be distinct positive integers')
        return values


class CreateGroupRequest(GroupProposalRequest):
    responsible_membership_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator('responsible_membership_ids')
    @classmethod
    def unique_responsible(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values) or len(values) != len(set(values)):
            raise ValueError('Identifiers must be distinct positive integers')
        return values


class ProposedTableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resource_id: int
    code: str
    name: str
    physical_capacity: int
    is_representative: bool


class GroupPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    eligible: Literal[True] = True
    representative: ProposedTableResponse
    members: tuple[ProposedTableResponse, ...]
    derived_capacity: int
    assigned_membership_ids: tuple[int, ...]
    automatic_responsible_membership_ids: tuple[int, ...]
    responsibility_selection_required: bool


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class AddTableRequest(VersionRequest):
    table_resource_id: int = Field(gt=0)


class MoveSectionRequest(VersionRequest):
    destination_section_id: int = Field(gt=0)


class AdminStatusRequest(VersionRequest):
    target_status: Literal['ACTIVE', 'SUSPENDED', 'OUT_OF_SERVICE', 'RETIRED']


class HistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    table_group_id: int | None
    table_resource_id: int | None
    event_type: str
    actor_membership_id: int
    result_version: int
    before_state: dict | list | None
    after_state: dict | list | None
    correlation_id: str | None
    recorded_at: datetime


class HistoryListResponse(BaseModel):
    items: list[HistoryResponse]


def _error(exc: service.TableManagementError) -> HTTPException:
    if isinstance(exc, service.TableManagementNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get('/sections', response_model=DiningSectionListResponse)
async def sections(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DiningSectionListResponse:
    values = await service.list_dining_sections(db, tenant_id=context.tenant_id, location_id=location_id)
    return DiningSectionListResponse(items=list(values))


@router.get('/tables', response_model=TableListResponse)
async def tables(
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TableListResponse:
    values = await service.list_tables(db, tenant_id=context.tenant_id, location_id=location_id)
    return TableListResponse(items=list(values))


@router.get('/groups/{group_id}', response_model=GroupResponse)
async def group(
    location_id: Annotated[int, Path(gt=0)], group_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_group(db, tenant_id=context.tenant_id, location_id=location_id, group_id=group_id)
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.get('/tables/{representative_resource_id}/active-group', response_model=GroupResponse | None)
async def active_group(
    location_id: Annotated[int, Path(gt=0)],
    representative_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    return await service.get_active_group(
        db, tenant_id=context.tenant_id, location_id=location_id,
        representative_resource_id=representative_resource_id,
    )


@router.get('/groups/{group_id}/history', response_model=HistoryListResponse)
async def history(
    location_id: Annotated[int, Path(gt=0)], group_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HistoryListResponse:
    try:
        values = await service.group_history(db, tenant_id=context.tenant_id, location_id=location_id, group_id=group_id)
    except service.TableManagementError as exc:
        raise _error(exc) from exc
    return HistoryListResponse(items=list(values))


@router.get('/tables/{table_resource_id}/history', response_model=HistoryListResponse)
async def table_history(
    location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('resource.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HistoryListResponse:
    try:
        values = await service.table_history(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id,
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc
    return HistoryListResponse(items=list(values))


@router.post('/groups', response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: CreateGroupRequest, location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.create_group(
            db, tenant_id=context.tenant_id, location_id=location_id,
            representative_resource_id=payload.representative_resource_id,
            joined_resource_ids=set(payload.joined_resource_ids),
            responsible_membership_ids=set(payload.responsible_membership_ids),
            actor_membership_id=context.membership_id,
            correlation_id=get_correlation_id(),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.post('/groups:preview', response_model=GroupPreviewResponse)
async def preview_group(
    payload: GroupProposalRequest,
    location_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.preview_group(
            db, tenant_id=context.tenant_id, location_id=location_id,
            representative_resource_id=payload.representative_resource_id,
            joined_resource_ids=set(payload.joined_resource_ids),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.post('/groups/{group_id}/tables', response_model=GroupResponse)
async def add_table(
    payload: AddTableRequest, location_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.add_table(
            db, tenant_id=context.tenant_id, location_id=location_id, group_id=group_id,
            table_resource_id=payload.table_resource_id, expected_version=payload.expected_version,
            actor_membership_id=context.membership_id, correlation_id=get_correlation_id(),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.post('/groups/{group_id}/tables/{table_resource_id}:remove', response_model=GroupResponse)
async def remove_table(
    payload: VersionRequest, location_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)], table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.remove_table(
            db, tenant_id=context.tenant_id, location_id=location_id, group_id=group_id,
            table_resource_id=table_resource_id, expected_version=payload.expected_version,
            actor_membership_id=context.membership_id, correlation_id=get_correlation_id(),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.post('/groups/{group_id}:dissolve', response_model=GroupResponse)
async def dissolve_group(
    payload: VersionRequest, location_id: Annotated[int, Path(gt=0)],
    group_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.dissolve_group(
            db, tenant_id=context.tenant_id, location_id=location_id, group_id=group_id,
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id, correlation_id=get_correlation_id(),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.post('/tables/{table_resource_id}:move-section', response_model=TableResponse)
async def move_section(
    payload: MoveSectionRequest, location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.move_section(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id,
            destination_section_id=payload.destination_section_id,
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id, correlation_id=get_correlation_id(),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc


@router.post('/tables/{table_resource_id}:administrative-status', response_model=TableResponse)
async def administrative_status(
    payload: AdminStatusRequest, location_id: Annotated[int, Path(gt=0)],
    table_resource_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_location_permission('table_management.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.transition_administrative_status(
            db, tenant_id=context.tenant_id, location_id=location_id,
            table_resource_id=table_resource_id, target_status=payload.target_status,
            expected_version=payload.expected_version,
            actor_membership_id=context.membership_id, correlation_id=get_correlation_id(),
        )
    except service.TableManagementError as exc:
        raise _error(exc) from exc
