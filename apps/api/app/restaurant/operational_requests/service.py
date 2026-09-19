from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DinerOperationalRequest,
    DinerSession,
    Conversation,
    OperationalRequestWaiterState,
    PreparationWork,
    Resource,
    RestaurantOrder,
    RestaurantServiceSession,
    ServiceResponsibleWaiter,
    ServiceResponsibilityTransition,
)
from app.restaurant.conversations import service as conversation_service


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
    diner_session_id: int | None
    diner_display_name: str | None
    request_type: str
    status: str
    related_restaurant_check_id: int | None
    preparation_work_id: int | None
    restaurant_order_id: int | None
    preparation_area_id: int | None
    preparation_area_code: str | None
    preparation_area_name: str | None
    picked_up_by_membership_id: int | None
    picked_up_at: datetime | None
    delivered_by_membership_id: int | None
    delivered_at: datetime | None
    acknowledged_by_membership_id: int | None
    acknowledged_at: datetime | None
    resolved_by_membership_id: int | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    current_waiter_entered_at: datetime | None = None
    current_waiter_hidden_at: datetime | None = None


def _projection(
    value: DinerOperationalRequest,
    diner_display_name: str | None,
    resource_code: str,
    resource_name: str,
    restaurant_order_id: int | None,
    preparation_area_id: int | None,
    preparation_area_code: str | None,
    preparation_area_name: str | None,
    picked_up_by_membership_id: int | None,
    picked_up_at: datetime | None,
    delivered_by_membership_id: int | None,
    delivered_at: datetime | None,
    current_waiter_entered_at: datetime | None = None,
    current_waiter_hidden_at: datetime | None = None,
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
        preparation_work_id=value.preparation_work_id,
        restaurant_order_id=restaurant_order_id,
        preparation_area_id=preparation_area_id,
        preparation_area_code=preparation_area_code,
        preparation_area_name=preparation_area_name,
        picked_up_by_membership_id=picked_up_by_membership_id,
        picked_up_at=picked_up_at,
        delivered_by_membership_id=delivered_by_membership_id,
        delivered_at=delivered_at,
        acknowledged_by_membership_id=value.acknowledged_by_membership_id,
        acknowledged_at=value.acknowledged_at,
        resolved_by_membership_id=value.resolved_by_membership_id,
        resolved_at=value.resolved_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
        current_waiter_entered_at=current_waiter_entered_at,
        current_waiter_hidden_at=current_waiter_hidden_at,
    )


def _read_statement():
    return (
        select(
            DinerOperationalRequest,
            DinerSession.display_name,
            Resource.code,
            Resource.name,
            PreparationWork.restaurant_order_id,
            PreparationWork.preparation_area_id,
            PreparationWork.area_code_snapshot,
            PreparationWork.area_name_snapshot,
            PreparationWork.picked_up_by_membership_id,
            PreparationWork.picked_up_at,
            PreparationWork.delivered_by_membership_id,
            PreparationWork.delivered_at,
        )
        .outerjoin(
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
        .outerjoin(
            PreparationWork,
            and_(
                PreparationWork.id == DinerOperationalRequest.preparation_work_id,
                PreparationWork.tenant_id == DinerOperationalRequest.tenant_id,
            ),
        )
    )


def _waiter_read_statement(membership_id: int):
    return (
        select(
            DinerOperationalRequest,
            DinerSession.display_name,
            Resource.code,
            Resource.name,
            PreparationWork.restaurant_order_id,
            PreparationWork.preparation_area_id,
            PreparationWork.area_code_snapshot,
            PreparationWork.area_name_snapshot,
            PreparationWork.picked_up_by_membership_id,
            PreparationWork.picked_up_at,
            PreparationWork.delivered_by_membership_id,
            PreparationWork.delivered_at,
            OperationalRequestWaiterState.entered_at,
            OperationalRequestWaiterState.hidden_at,
        )
        .outerjoin(
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
        .outerjoin(
            PreparationWork,
            and_(
                PreparationWork.id == DinerOperationalRequest.preparation_work_id,
                PreparationWork.tenant_id == DinerOperationalRequest.tenant_id,
            ),
        )
        .outerjoin(
            OperationalRequestWaiterState,
            and_(
                OperationalRequestWaiterState.operational_request_id
                == DinerOperationalRequest.id,
                OperationalRequestWaiterState.tenant_id
                == DinerOperationalRequest.tenant_id,
                OperationalRequestWaiterState.waiter_membership_id == membership_id,
            ),
        )
    )


def _preparation_ready_identity(work_id: int) -> tuple[str, str]:
    idempotency_key = f'PREPARATION_READY:{work_id}'
    payload = json.dumps(
        {'preparation_work_id': work_id, 'request_type': 'PREPARATION_READY'},
        sort_keys=True,
        separators=(',', ':'),
    )
    return idempotency_key, hashlib.sha256(payload.encode()).hexdigest()


async def ensure_preparation_ready_request(
    db: AsyncSession,
    *,
    work: PreparationWork,
    correlation_id: str | None,
) -> DinerOperationalRequest:
    """Persist the one readiness request without committing the caller's transaction."""
    existing = await db.scalar(select(DinerOperationalRequest).where(
        DinerOperationalRequest.preparation_work_id == work.id,
    ))
    idempotency_key, fingerprint = _preparation_ready_identity(work.id)
    if existing is not None:
        if (
            existing.tenant_id != work.tenant_id
            or existing.request_type != 'PREPARATION_READY'
            or existing.diner_session_id is not None
            or existing.related_restaurant_check_id is not None
            or existing.idempotency_key != idempotency_key
            or existing.request_fingerprint != fingerprint
        ):
            raise OperationalRequestStateConflictError(
                'Preparation readiness is associated with conflicting request evidence'
            )
        return existing

    order = await db.scalar(select(RestaurantOrder).where(
        RestaurantOrder.id == work.restaurant_order_id,
        RestaurantOrder.tenant_id == work.tenant_id,
        RestaurantOrder.organization_id == work.organization_id,
        RestaurantOrder.location_id == work.location_id,
    ))
    if order is None:
        raise OperationalRequestStateConflictError(
            'Preparation Work has no canonical Restaurant Order scope'
        )
    value = DinerOperationalRequest(
        tenant_id=work.tenant_id,
        organization_id=work.organization_id,
        location_id=work.location_id,
        resource_id=order.resource_id,
        service_session_id=order.service_session_id,
        diner_session_id=None,
        request_type='PREPARATION_READY',
        status='PENDING',
        related_restaurant_check_id=None,
        preparation_work_id=work.id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        correlation_id=correlation_id,
    )
    db.add(value)
    await db.flush()
    return value


def _waiter_visibility(membership_id: int):
    initialized = exists(select(ServiceResponsibilityTransition.id).where(
        ServiceResponsibilityTransition.tenant_id == DinerOperationalRequest.tenant_id,
        ServiceResponsibilityTransition.service_session_id
        == DinerOperationalRequest.service_session_id,
    ))
    any_current = exists(select(ServiceResponsibleWaiter.id).where(
        ServiceResponsibleWaiter.tenant_id == DinerOperationalRequest.tenant_id,
        ServiceResponsibleWaiter.service_session_id
        == DinerOperationalRequest.service_session_id,
    ))
    current_for_waiter = exists(select(ServiceResponsibleWaiter.id).where(
        ServiceResponsibleWaiter.tenant_id == DinerOperationalRequest.tenant_id,
        ServiceResponsibleWaiter.service_session_id
        == DinerOperationalRequest.service_session_id,
        ServiceResponsibleWaiter.waiter_membership_id == membership_id,
    ))
    genuine_legacy_open = exists(select(RestaurantServiceSession.id).where(
        RestaurantServiceSession.id == DinerOperationalRequest.service_session_id,
        RestaurantServiceSession.tenant_id == DinerOperationalRequest.tenant_id,
        RestaurantServiceSession.status == 'OPEN',
    ))
    return or_(
        and_(initialized, current_for_waiter),
        and_(~initialized, ~any_current, genuine_legacy_open),
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


async def list_waiter_operational_requests(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_status: str | None,
    request_type: str | None,
    view: str,
    limit: int,
    offset: int,
) -> tuple[StaffOperationalRequest, ...]:
    statement = _waiter_read_statement(membership_id).where(
        DinerOperationalRequest.tenant_id == tenant_id,
        DinerOperationalRequest.location_id == location_id,
        _waiter_visibility(membership_id),
    )
    if view == 'hidden':
        statement = statement.where(
            OperationalRequestWaiterState.hidden_at.is_not(None),
            DinerOperationalRequest.status.not_in(('COMPLETED', 'CANCELLED')),
        )
    else:
        statement = statement.where(OperationalRequestWaiterState.hidden_at.is_(None))
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


async def get_waiter_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
) -> StaffOperationalRequest:
    row = (
        await db.execute(
            _waiter_read_statement(membership_id).where(
                DinerOperationalRequest.id == request_id,
                DinerOperationalRequest.tenant_id == tenant_id,
                DinerOperationalRequest.location_id == location_id,
                _waiter_visibility(membership_id),
            )
        )
    ).one_or_none()
    if row is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    return _projection(*row)


async def _get_waiter_operational_request_projection(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
) -> StaffOperationalRequest:
    row = (
        await db.execute(
            _waiter_read_statement(membership_id)
            .where(
                DinerOperationalRequest.id == request_id,
                DinerOperationalRequest.tenant_id == tenant_id,
                DinerOperationalRequest.location_id == location_id,
            )
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    return _projection(*row)


async def _locked_waiter_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
) -> DinerOperationalRequest:
    identity = (
        await db.execute(select(
            DinerOperationalRequest.service_session_id,
            DinerOperationalRequest.resource_id,
        ).where(
            DinerOperationalRequest.id == request_id,
            DinerOperationalRequest.tenant_id == tenant_id,
            DinerOperationalRequest.location_id == location_id,
        ))
    ).one_or_none()
    if identity is None:
        raise OperationalRequestNotFoundError('Operational request not found')

    # Keep the certified responsibility lock order: Resource, then Service Session.
    resource = await db.scalar(select(Resource).where(
        Resource.id == identity.resource_id,
        Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
    ).with_for_update())
    if resource is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    session = await db.scalar(select(RestaurantServiceSession).where(
        RestaurantServiceSession.id == identity.service_session_id,
        RestaurantServiceSession.tenant_id == tenant_id,
        RestaurantServiceSession.location_id == location_id,
        RestaurantServiceSession.resource_id == resource.id,
    ).with_for_update())
    if session is None:
        raise OperationalRequestNotFoundError('Operational request not found')

    initialized = await db.scalar(select(ServiceResponsibilityTransition.id).where(
        ServiceResponsibilityTransition.tenant_id == tenant_id,
        ServiceResponsibilityTransition.service_session_id == session.id,
    ).limit(1).with_for_update())
    any_current = await db.scalar(select(ServiceResponsibleWaiter.id).where(
        ServiceResponsibleWaiter.tenant_id == tenant_id,
        ServiceResponsibleWaiter.service_session_id == session.id,
    ).limit(1).with_for_update())
    if initialized is None:
        if any_current is not None or session.status != 'OPEN':
            raise OperationalRequestNotFoundError('Operational request not found')
    else:
        responsible = await db.scalar(select(ServiceResponsibleWaiter.id).where(
            ServiceResponsibleWaiter.tenant_id == tenant_id,
            ServiceResponsibleWaiter.service_session_id == session.id,
            ServiceResponsibleWaiter.waiter_membership_id == membership_id,
        ).limit(1).with_for_update())
        if responsible is None:
            raise OperationalRequestNotFoundError('Operational request not found')

    value = await db.scalar(
        select(DinerOperationalRequest)
        .where(
            DinerOperationalRequest.id == request_id,
            DinerOperationalRequest.tenant_id == tenant_id,
            DinerOperationalRequest.location_id == location_id,
            DinerOperationalRequest.service_session_id == session.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if value is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    return value


async def _apply_transition(
    db: AsyncSession,
    *,
    value: DinerOperationalRequest,
    membership_id: int,
    target_status: str,
    record_acknowledgement: bool = False,
) -> None:
    if target_status == 'COMPLETED' and value.request_type == 'PREPARATION_READY':
        raise OperationalRequestStateConflictError(
            'PREPARATION_READY can only be completed by canonical delivery'
        )
    if value.status == target_status:
        return
    expected_status = 'PENDING' if target_status == 'ACKNOWLEDGED' else 'ACKNOWLEDGED'
    if value.status != expected_status:
        raise OperationalRequestStateConflictError(
            f'Operational request cannot transition from {value.status} to {target_status}'
        )
    value.status = target_status
    effective_at = datetime.now(UTC).replace(tzinfo=None)
    if target_status == 'ACKNOWLEDGED' and record_acknowledgement:
        value.acknowledged_by_membership_id = membership_id
        value.acknowledged_at = effective_at
    elif target_status == 'COMPLETED':
        value.resolved_by_membership_id = membership_id
        value.resolved_at = effective_at


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

    await _apply_transition(
        db, value=value, membership_id=membership_id, target_status=target_status,
    )
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


async def transition_waiter_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
    target_status: str,
) -> StaffOperationalRequest:
    try:
        value = await _locked_waiter_request(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            membership_id=membership_id,
            request_id=request_id,
        )
        await _apply_transition(
            db,
            value=value,
            membership_id=membership_id,
            target_status=target_status,
            record_acknowledgement=True,
        )
        await db.commit()
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise
    return await _get_waiter_operational_request_projection(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        membership_id=membership_id,
        request_id=request_id,
    )


async def _locked_waiter_preparation_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
) -> tuple[DinerOperationalRequest, PreparationWork]:
    identity = (await db.execute(select(
        DinerOperationalRequest.service_session_id,
        DinerOperationalRequest.resource_id,
        DinerOperationalRequest.request_type,
        DinerOperationalRequest.preparation_work_id,
    ).where(
        DinerOperationalRequest.id == request_id,
        DinerOperationalRequest.tenant_id == tenant_id,
        DinerOperationalRequest.location_id == location_id,
    ))).one_or_none()
    if identity is None:
        raise OperationalRequestNotFoundError('Operational request not found')

    resource = await db.scalar(select(Resource).where(
        Resource.id == identity.resource_id,
        Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
    ).with_for_update())
    if resource is None:
        raise OperationalRequestNotFoundError('Operational request not found')
    session = await db.scalar(select(RestaurantServiceSession).where(
        RestaurantServiceSession.id == identity.service_session_id,
        RestaurantServiceSession.tenant_id == tenant_id,
        RestaurantServiceSession.location_id == location_id,
        RestaurantServiceSession.resource_id == resource.id,
    ).with_for_update())
    if session is None:
        raise OperationalRequestNotFoundError('Operational request not found')

    initialized = await db.scalar(select(ServiceResponsibilityTransition.id).where(
        ServiceResponsibilityTransition.tenant_id == tenant_id,
        ServiceResponsibilityTransition.service_session_id == session.id,
    ).limit(1))
    responsible = await db.scalar(select(ServiceResponsibleWaiter.id).where(
        ServiceResponsibleWaiter.tenant_id == tenant_id,
        ServiceResponsibleWaiter.service_session_id == session.id,
        ServiceResponsibleWaiter.waiter_membership_id == membership_id,
    ).limit(1))
    if initialized is None or responsible is None or session.status != 'OPEN':
        raise OperationalRequestNotFoundError('Operational request not found')
    if identity.request_type != 'PREPARATION_READY' or identity.preparation_work_id is None:
        raise OperationalRequestStateConflictError(
            'Physical handoff requires a PREPARATION_READY request'
        )

    # MP5 owns Work-first serialization, so keep Work before request here too.
    work = await db.scalar(select(PreparationWork).where(
        PreparationWork.id == identity.preparation_work_id,
        PreparationWork.tenant_id == tenant_id,
        PreparationWork.location_id == location_id,
    ).with_for_update().execution_options(populate_existing=True))
    if work is None:
        raise OperationalRequestStateConflictError(
            'PREPARATION_READY has no canonical Preparation Work'
        )
    value = await db.scalar(select(DinerOperationalRequest).where(
        DinerOperationalRequest.id == request_id,
        DinerOperationalRequest.tenant_id == tenant_id,
        DinerOperationalRequest.location_id == location_id,
        DinerOperationalRequest.service_session_id == session.id,
        DinerOperationalRequest.preparation_work_id == work.id,
    ).with_for_update().execution_options(populate_existing=True))
    if value is None or value.request_type != 'PREPARATION_READY':
        raise OperationalRequestStateConflictError(
            'Physical handoff requires a PREPARATION_READY request'
        )
    return value, work


async def handoff_waiter_preparation_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
    action: str,
) -> StaffOperationalRequest:
    from app.restaurant.preparation import errors as preparation_errors
    from app.restaurant.preparation import service as preparation_service

    try:
        value, work = await _locked_waiter_preparation_request(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            membership_id=membership_id,
            request_id=request_id,
        )
        if action == 'pick-up':
            if value.status not in {'PENDING', 'ACKNOWLEDGED'}:
                raise OperationalRequestStateConflictError(
                    'PREPARATION_READY is not available for pickup'
                )
            await preparation_service.pickup_preparation_work(
                db,
                work=work,
                membership_id=membership_id,
                effective_at=datetime.now(UTC).replace(tzinfo=None, microsecond=0),
            )
        elif action == 'deliver':
            if value.status == 'COMPLETED':
                if (
                    work.delivered_by_membership_id is None
                    or work.delivered_at is None
                    or value.resolved_by_membership_id != work.delivered_by_membership_id
                    or value.resolved_at != work.delivered_at
                ):
                    raise OperationalRequestStateConflictError(
                        'Completed PREPARATION_READY has inconsistent delivery evidence'
                    )
            elif value.status in {'PENDING', 'ACKNOWLEDGED'}:
                if work.delivered_by_membership_id is not None or work.delivered_at is not None:
                    raise OperationalRequestStateConflictError(
                        'Preparation delivery evidence conflicts with request lifecycle'
                    )
                effective_at = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
                await preparation_service.deliver_preparation_work(
                    db,
                    work=work,
                    membership_id=membership_id,
                    effective_at=effective_at,
                )
                value.status = 'COMPLETED'
                value.resolved_by_membership_id = membership_id
                value.resolved_at = effective_at
            else:
                raise OperationalRequestStateConflictError(
                    'PREPARATION_READY is not available for delivery'
                )
        else:
            raise ValueError('Unsupported preparation handoff action')
        await db.commit()
    except preparation_errors.PreparationConflictError as exc:
        if db.in_transaction():
            await db.rollback()
        raise OperationalRequestStateConflictError(str(exc)) from exc
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise
    return await _get_waiter_operational_request_projection(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        membership_id=membership_id,
        request_id=request_id,
    )


def _responder_fingerprint(
    *,
    request_id: int,
    modality: str,
    content_text: str,
    language: str | None,
    language_source: str | None,
) -> str:
    payload = json.dumps({
        'operational_request_id': request_id,
        'modality': modality,
        'content_text': content_text,
        'language': language,
        'language_source': language_source,
    }, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


async def respond_to_operational_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
    idempotency_key: str,
    modality: str,
    content_text: str,
    language: str | None,
    language_source: str | None,
) -> conversation_service.ResponderMessage:
    normalized_content = content_text.strip()
    fingerprint = _responder_fingerprint(
        request_id=request_id,
        modality=modality,
        content_text=normalized_content,
        language=language,
        language_source=language_source,
    )
    try:
        value = await _locked_waiter_request(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            membership_id=membership_id,
            request_id=request_id,
        )
        service_status = await db.scalar(select(RestaurantServiceSession.status).where(
            RestaurantServiceSession.id == value.service_session_id,
            RestaurantServiceSession.tenant_id == tenant_id,
            RestaurantServiceSession.location_id == location_id,
            RestaurantServiceSession.resource_id == value.resource_id,
        ).with_for_update())
        if service_status != 'OPEN':
            raise OperationalRequestStateConflictError(
                'RESPONDER requires an OPEN Restaurant Service Session'
            )
        if value.status == 'CANCELLED':
            raise OperationalRequestStateConflictError(
                'RESPONDER is not allowed for a CANCELLED operational request'
            )
        if value.status not in {'PENDING', 'ACKNOWLEDGED', 'COMPLETED'}:
            raise OperationalRequestStateConflictError(
                'Operational request lifecycle does not allow RESPONDER'
            )
        if value.diner_session_id is None:
            raise OperationalRequestStateConflictError(
                'Operational request has no canonical diner Conversation'
            )
        diner = await db.scalar(select(DinerSession).where(
            DinerSession.id == value.diner_session_id,
            DinerSession.tenant_id == tenant_id,
            DinerSession.organization_id == value.organization_id,
            DinerSession.location_id == value.location_id,
            DinerSession.resource_id == value.resource_id,
            DinerSession.service_session_id == value.service_session_id,
        ))
        if diner is None:
            raise OperationalRequestStateConflictError(
                'Operational request has no canonical diner Conversation'
            )
        conversation = await db.scalar(select(Conversation).where(
            Conversation.id == diner.conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.organization_id == value.organization_id,
            Conversation.location_id == value.location_id,
            Conversation.resource_id == value.resource_id,
        ).with_for_update())
        if conversation is None or conversation.status != 'ACTIVE':
            raise OperationalRequestStateConflictError(
                'Canonical diner Conversation is not active'
            )
        result = await conversation_service.stage_staff_response(
            db,
            conversation=conversation,
            operational_request_id=value.id,
            membership_id=membership_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            modality=modality,
            content_text=normalized_content,
            language=language,
            language_source=language_source,
        )
        await db.commit()
        return result
    except conversation_service.ConversationConflictError as exc:
        if db.in_transaction():
            await db.rollback()
        raise OperationalRequestStateConflictError(str(exc)) from exc
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise


async def mutate_waiter_operational_request_state(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
    membership_id: int,
    request_id: int,
    action: str,
) -> StaffOperationalRequest:
    try:
        value = await _locked_waiter_request(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            membership_id=membership_id,
            request_id=request_id,
        )
        state = await db.scalar(
            select(OperationalRequestWaiterState)
            .where(
                OperationalRequestWaiterState.tenant_id == tenant_id,
                OperationalRequestWaiterState.operational_request_id == request_id,
                OperationalRequestWaiterState.waiter_membership_id == membership_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if action in {'hide', 'show'} and value.status in {'COMPLETED', 'CANCELLED'}:
            raise OperationalRequestStateConflictError(
                f'Operational request cannot {action} from {value.status}'
            )

        effective_at = datetime.now(UTC).replace(tzinfo=None)
        if action == 'show':
            if state is not None:
                state.hidden_at = None
        else:
            if state is None:
                state = OperationalRequestWaiterState(
                    tenant_id=tenant_id,
                    operational_request_id=request_id,
                    waiter_membership_id=membership_id,
                )
                db.add(state)
            if action == 'entered' and state.entered_at is None:
                state.entered_at = effective_at
            elif action == 'hide' and state.hidden_at is None:
                state.hidden_at = effective_at
        await db.commit()
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise
    return await _get_waiter_operational_request_projection(
        db,
        tenant_id=tenant_id,
        location_id=location_id,
        membership_id=membership_id,
        request_id=request_id,
    )
