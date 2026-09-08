from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DinerOperationalRequest, DinerSession, Resource


class OperationalRequestNotFoundError(LookupError):
    pass


class OperationalRequestStateConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StaffOperationalRequest:
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


def _projection(
    value: DinerOperationalRequest,
    diner_display_name: str,
    resource_code: str,
    resource_name: str,
) -> StaffOperationalRequest:
    return StaffOperationalRequest(
        id=value.id,
        organization_id=value.organization_id,
        location_id=value.location_id,
        resource_id=value.resource_id,
        resource_code=resource_code,
        resource_name=resource_name,
        service_session_id=value.service_session_id,
        diner_session_id=value.diner_session_id,
        diner_display_name=diner_display_name,
        request_type=value.request_type,
        status=value.status,
        related_restaurant_check_id=value.related_restaurant_check_id,
        resolved_by_membership_id=value.resolved_by_membership_id,
        resolved_at=value.resolved_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _read_statement():
    return (
        select(
            DinerOperationalRequest,
            DinerSession.display_name,
            Resource.code,
            Resource.name,
        )
        .join(
            DinerSession,
            and_(
                DinerSession.id == DinerOperationalRequest.diner_session_id,
                DinerSession.tenant_id == DinerOperationalRequest.tenant_id,
            ),
        )
        .join(
            Resource,
            and_(
                Resource.id == DinerOperationalRequest.resource_id,
                Resource.tenant_id == DinerOperationalRequest.tenant_id,
            ),
        )
    )


async def list_operational_requests(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    request_status: str | None,
    request_type: str | None,
    limit: int,
    offset: int,
) -> tuple[StaffOperationalRequest, ...]:
    statement = _read_statement().where(
        DinerOperationalRequest.tenant_id == tenant_id,
        DinerOperationalRequest.location_id == location_id,
    )
    if request_status is not None:
        statement = statement.where(DinerOperationalRequest.status == request_status)
    if request_type is not None:
        statement = statement.where(DinerOperationalRequest.request_type == request_type)
    result = await db.execute(
        statement.order_by(
            DinerOperationalRequest.created_at,
            DinerOperationalRequest.id,
        ).limit(limit).offset(offset)
    )
    return tuple(_projection(*row) for row in result.all())


async def get_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    request_id: int,
) -> StaffOperationalRequest:
    row = (
        await db.execute(
            _read_statement().where(
                DinerOperationalRequest.id == request_id,
                DinerOperationalRequest.tenant_id == tenant_id,
                DinerOperationalRequest.location_id == location_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    return _projection(*row)


async def _transition(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    request_id: int,
    membership_id: int,
    target_status: str,
) -> StaffOperationalRequest:
    value = await db.scalar(
        select(DinerOperationalRequest)
        .where(
            DinerOperationalRequest.id == request_id,
            DinerOperationalRequest.tenant_id == tenant_id,
            DinerOperationalRequest.location_id == location_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if value is None:
        raise OperationalRequestNotFoundError('Operational request not found')

    if value.status == target_status:
        return await get_operational_request(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            request_id=request_id,
        )
    expected_status = 'PENDING' if target_status == 'ACKNOWLEDGED' else 'ACKNOWLEDGED'
    if value.status != expected_status:
        raise OperationalRequestStateConflictError(
            f'Operational request cannot transition from {value.status} to {target_status}'
        )

    value.status = target_status
    if target_status == 'COMPLETED':
        value.resolved_by_membership_id = membership_id
        value.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return await get_operational_request(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        request_id=request_id,
    )


async def acknowledge_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    request_id: int,
    membership_id: int,
) -> StaffOperationalRequest:
    return await _transition(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        request_id=request_id,
        membership_id=membership_id,
        target_status='ACKNOWLEDGED',
    )


async def complete_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    request_id: int,
    membership_id: int,
) -> StaffOperationalRequest:
    return await _transition(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        request_id=request_id,
        membership_id=membership_id,
        target_status='COMPLETED',
    )
