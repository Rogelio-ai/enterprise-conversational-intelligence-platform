from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_authenticated_context, get_db, require_staff_location_access
from app.models import (
    BillingIssuance, CashSession, DinerOperationalRequest, DinerSession,
    PaidCheckDispatch, PreparationDispatch, PreparationWorkItem, Resource,
    RestaurantCheck, RestaurantCheckSettlement, RestaurantPayment,
    RestaurantServiceSession,
)
from app.restaurant.cash_management import service as cash_service


router = APIRouter(prefix='/staff/manager', tags=['staff-manager'])
REQUIRED_PERMISSIONS = frozenset({
    'location.read', 'resource.read', 'restaurant_service.read',
    'restaurant_order.read', 'operational_request.read', 'preparation.read',
    'restaurant_check.read', 'restaurant_payment.read', 'cash_management.read',
})


class ServiceSessionItem(BaseModel):
    id: int
    resource_id: int
    resource_code: str
    resource_name: str
    party_size: int
    active_diner_count: int
    opened_at: datetime


class CheckExceptionItem(BaseModel):
    id: int
    status: str
    currency: str
    liability_total: Decimal
    confirmed_settlement: Decimal
    outstanding: Decimal
    reserved_exposure: Decimal
    uncertain_exposure: Decimal


class PaymentExceptionItem(BaseModel):
    id: int
    check_id: int
    amount: Decimal
    currency: str
    method_category: str
    state: str
    created_at: datetime


class CashSessionItem(BaseModel):
    id: int
    resource_id: int
    status: str
    currency: str
    expected_cash: Decimal
    frozen_variance: Decimal | None
    opened_at: datetime


class DispatchExceptionItem(BaseModel):
    id: int
    reference_id: int
    state: str
    destination_name: str
    attempt_count: int
    last_error_kind: str | None
    created_at: datetime


class FiscalExceptionItem(BaseModel):
    id: int
    billing_document_id: int
    provider_key: str
    state: str
    attempt_count: int
    requested_at: datetime


class ManagerOperationalOverview(BaseModel):
    location_id: int
    generated_at: datetime
    active_table_count: int
    available_table_count: int
    active_service_session_count: int
    active_diner_count: int
    service_sessions: list[ServiceSessionItem]
    request_counts_by_status: dict[str, int]
    request_counts_by_type: dict[str, int]
    preparation_item_counts: dict[str, int]
    preparation_dispatch_counts: dict[str, int]
    preparation_dispatch_exceptions: list[DispatchExceptionItem]
    check_counts_by_status: dict[str, int]
    checks_with_outstanding_count: int
    check_exceptions: list[CheckExceptionItem]
    uncertain_payments: list[PaymentExceptionItem]
    cash_session_counts: dict[str, int]
    cash_session_exceptions: list[CashSessionItem]
    fiscal_issuance_counts: dict[str, int]
    fiscal_exceptions: list[FiscalExceptionItem]
    paid_print_counts: dict[str, int]
    paid_print_exceptions: list[DispatchExceptionItem]


async def _counts(db: AsyncSession, model, column, *, tenant_id: int, location_id: int, states: tuple[str, ...]) -> dict[str, int]:
    values = {state: 0 for state in states}
    rows = (await db.execute(
        select(column, func.count()).select_from(model).where(
            model.tenant_id == tenant_id, model.location_id == location_id,
        ).group_by(column)
    )).all()
    for state, count in rows:
        if state in values:
            values[state] = int(count)
    return values


@router.get('/operational-overview', response_model=ManagerOperationalOverview)
async def manager_operational_overview(
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    if not REQUIRED_PERMISSIONS.issubset(context.permissions):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Insufficient permission')
    await require_staff_location_access(location_id, context, db)
    tenant_id = context.tenant_id

    active_table_count = int(await db.scalar(select(func.count()).select_from(Resource).where(
        Resource.tenant_id == tenant_id, Resource.location_id == location_id,
        Resource.resource_type == 'TABLE', Resource.status == 'ACTIVE',
    )) or 0)
    service_rows = (await db.execute(
        select(
            RestaurantServiceSession.id, Resource.id.label('resource_id'),
            Resource.code, Resource.name, RestaurantServiceSession.party_size,
            func.count(DinerSession.id).label('active_diner_count'),
            RestaurantServiceSession.opened_at,
        )
        .join(Resource, Resource.id == RestaurantServiceSession.resource_id)
        .outerjoin(DinerSession, (DinerSession.service_session_id == RestaurantServiceSession.id) & (DinerSession.status == 'ACTIVE'))
        .where(
            RestaurantServiceSession.tenant_id == tenant_id,
            RestaurantServiceSession.location_id == location_id,
            RestaurantServiceSession.status == 'OPEN',
        )
        .group_by(RestaurantServiceSession.id, Resource.id, Resource.code, Resource.name, RestaurantServiceSession.party_size, RestaurantServiceSession.opened_at)
        .order_by(RestaurantServiceSession.opened_at, RestaurantServiceSession.id).limit(50)
    )).all()
    service_sessions = [ServiceSessionItem(
        id=row.id, resource_id=row.resource_id, resource_code=row.code,
        resource_name=row.name, party_size=row.party_size,
        active_diner_count=int(row.active_diner_count), opened_at=row.opened_at,
    ) for row in service_rows]
    active_service_session_count = int(await db.scalar(select(func.count()).select_from(RestaurantServiceSession).where(
        RestaurantServiceSession.tenant_id == tenant_id,
        RestaurantServiceSession.location_id == location_id,
        RestaurantServiceSession.status == 'OPEN',
    )) or 0)
    active_diner_count = int(await db.scalar(select(func.count()).select_from(DinerSession).where(
        DinerSession.tenant_id == tenant_id, DinerSession.location_id == location_id,
        DinerSession.status == 'ACTIVE',
    )) or 0)

    request_counts_by_status = await _counts(db, DinerOperationalRequest, DinerOperationalRequest.status, tenant_id=tenant_id, location_id=location_id, states=('PENDING', 'ACKNOWLEDGED', 'COMPLETED', 'CANCELLED'))
    request_counts_by_type = await _counts(db, DinerOperationalRequest, DinerOperationalRequest.request_type, tenant_id=tenant_id, location_id=location_id, states=('HUMAN_ASSISTANCE', 'CASH_PAYMENT_ASSISTANCE', 'INVOICE_ASSISTANCE', 'PAID_CHECK_PRINT'))
    preparation_item_counts = await _counts(db, PreparationWorkItem, PreparationWorkItem.execution_state, tenant_id=tenant_id, location_id=location_id, states=('NEW', 'IN_PROGRESS', 'COMPLETED'))
    dispatch_states = ('PENDING', 'IN_PROGRESS', 'DESTINATION_SUBMISSION_ACCEPTED', 'RETRYABLE_FAILURE', 'UNCERTAIN', 'ACTION_REQUIRED')
    preparation_dispatch_counts = await _counts(db, PreparationDispatch, PreparationDispatch.state, tenant_id=tenant_id, location_id=location_id, states=dispatch_states)
    preparation_dispatch_rows = tuple((await db.scalars(select(PreparationDispatch).where(
        PreparationDispatch.tenant_id == tenant_id, PreparationDispatch.location_id == location_id,
        PreparationDispatch.state.in_(('RETRYABLE_FAILURE', 'UNCERTAIN', 'ACTION_REQUIRED')),
    ).order_by(PreparationDispatch.created_at.desc(), PreparationDispatch.id.desc()).limit(20))).all())
    preparation_dispatch_exceptions = [DispatchExceptionItem(
        id=value.id, reference_id=value.preparation_work_id, state=value.state,
        destination_name=value.destination_name_snapshot, attempt_count=value.attempt_count,
        last_error_kind=value.last_error_kind, created_at=value.created_at,
    ) for value in preparation_dispatch_rows]

    check_counts_by_status = await _counts(db, RestaurantCheck, RestaurantCheck.status, tenant_id=tenant_id, location_id=location_id, states=('OPEN', 'FROZEN', 'SETTLED', 'CANCELLED'))
    zero = Decimal('0')
    confirmed = select(func.coalesce(func.sum(RestaurantCheckSettlement.amount), zero)).where(RestaurantCheckSettlement.check_id == RestaurantCheck.id).correlate(RestaurantCheck).scalar_subquery()
    reserved = select(func.coalesce(func.sum(RestaurantPayment.amount), zero)).where(RestaurantPayment.check_id == RestaurantCheck.id, RestaurantPayment.state.in_(('RESERVED', 'IN_PROGRESS'))).correlate(RestaurantCheck).scalar_subquery()
    uncertain = select(func.coalesce(func.sum(RestaurantPayment.amount), zero)).where(RestaurantPayment.check_id == RestaurantCheck.id, RestaurantPayment.state == 'UNCERTAIN').correlate(RestaurantCheck).scalar_subquery()
    exception_condition = (RestaurantCheck.liability_total > confirmed) | (reserved > zero) | (uncertain > zero)
    checks_with_outstanding_count = int(await db.scalar(select(func.count()).select_from(RestaurantCheck).where(
        RestaurantCheck.tenant_id == tenant_id, RestaurantCheck.location_id == location_id,
        RestaurantCheck.liability_total > confirmed,
    )) or 0)
    check_rows = (await db.execute(select(
        RestaurantCheck.id, RestaurantCheck.status, RestaurantCheck.currency,
        RestaurantCheck.liability_total, confirmed.label('confirmed'),
        reserved.label('reserved'), uncertain.label('uncertain'),
    ).where(
        RestaurantCheck.tenant_id == tenant_id, RestaurantCheck.location_id == location_id,
        exception_condition,
    ).order_by(RestaurantCheck.created_at, RestaurantCheck.id).limit(20))).all()
    check_exceptions = [CheckExceptionItem(
        id=row.id, status=row.status, currency=row.currency,
        liability_total=row.liability_total, confirmed_settlement=row.confirmed,
        outstanding=max(zero, row.liability_total - row.confirmed),
        reserved_exposure=row.reserved, uncertain_exposure=row.uncertain,
    ) for row in check_rows]
    uncertain_payment_rows = tuple((await db.scalars(select(RestaurantPayment).where(
        RestaurantPayment.tenant_id == tenant_id, RestaurantPayment.location_id == location_id,
        RestaurantPayment.state == 'UNCERTAIN',
    ).order_by(RestaurantPayment.created_at, RestaurantPayment.id).limit(20))).all())
    uncertain_payments = [PaymentExceptionItem(
        id=value.id, check_id=value.check_id, amount=value.amount,
        currency=value.currency, method_category=value.method_category,
        state=value.state, created_at=value.created_at,
    ) for value in uncertain_payment_rows]

    cash_session_counts = await _counts(db, CashSession, CashSession.status, tenant_id=tenant_id, location_id=location_id, states=('OPEN', 'CLOSED'))
    cash_rows = tuple((await db.scalars(select(CashSession).where(
        CashSession.tenant_id == tenant_id, CashSession.location_id == location_id,
        (CashSession.status == 'OPEN') | ((CashSession.status == 'CLOSED') & (CashSession.frozen_variance != zero)),
    ).order_by(CashSession.opened_at.desc(), CashSession.id.desc()).limit(20))).all())
    cash_projections = [await cash_service.get_cash_session(
        db, tenant_id=tenant_id, location_id=location_id, cash_session_id=value.id,
    ) for value in cash_rows]
    cash_session_exceptions = [CashSessionItem(
        id=value.id, resource_id=value.resource_id, status=value.status,
        currency=value.currency, expected_cash=value.expected_cash,
        frozen_variance=value.frozen_variance, opened_at=value.opened_at,
    ) for value in cash_projections]

    fiscal_states = ('PENDING', 'IN_PROGRESS', 'SUCCEEDED', 'FAILED', 'REJECTED', 'UNCERTAIN')
    fiscal_issuance_counts = await _counts(db, BillingIssuance, BillingIssuance.state, tenant_id=tenant_id, location_id=location_id, states=fiscal_states)
    fiscal_rows = tuple((await db.scalars(select(BillingIssuance).where(
        BillingIssuance.tenant_id == tenant_id, BillingIssuance.location_id == location_id,
        BillingIssuance.state.in_(('PENDING', 'IN_PROGRESS', 'FAILED', 'REJECTED', 'UNCERTAIN')),
    ).order_by(BillingIssuance.requested_at, BillingIssuance.id).limit(20))).all())
    fiscal_exceptions = [FiscalExceptionItem(
        id=value.id, billing_document_id=value.billing_document_id,
        provider_key=value.provider_key, state=value.state,
        attempt_count=value.attempt_count, requested_at=value.requested_at,
    ) for value in fiscal_rows]

    paid_print_counts = await _counts(db, PaidCheckDispatch, PaidCheckDispatch.state, tenant_id=tenant_id, location_id=location_id, states=dispatch_states)
    print_rows = tuple((await db.scalars(select(PaidCheckDispatch).where(
        PaidCheckDispatch.tenant_id == tenant_id, PaidCheckDispatch.location_id == location_id,
        PaidCheckDispatch.state != 'DESTINATION_SUBMISSION_ACCEPTED',
    ).order_by(PaidCheckDispatch.created_at, PaidCheckDispatch.id).limit(20))).all())
    paid_print_exceptions = [DispatchExceptionItem(
        id=value.id, reference_id=value.restaurant_check_id, state=value.state,
        destination_name=value.connector_name_snapshot, attempt_count=value.attempt_count,
        last_error_kind=value.last_error_kind, created_at=value.created_at,
    ) for value in print_rows]

    return ManagerOperationalOverview(
        location_id=location_id, generated_at=datetime.now(timezone.utc),
        active_table_count=active_table_count,
        available_table_count=max(0, active_table_count - active_service_session_count),
        active_service_session_count=active_service_session_count,
        active_diner_count=active_diner_count, service_sessions=service_sessions,
        request_counts_by_status=request_counts_by_status,
        request_counts_by_type=request_counts_by_type,
        preparation_item_counts=preparation_item_counts,
        preparation_dispatch_counts=preparation_dispatch_counts,
        preparation_dispatch_exceptions=preparation_dispatch_exceptions,
        check_counts_by_status=check_counts_by_status,
        checks_with_outstanding_count=checks_with_outstanding_count,
        check_exceptions=check_exceptions, uncertain_payments=uncertain_payments,
        cash_session_counts=cash_session_counts,
        cash_session_exceptions=cash_session_exceptions,
        fiscal_issuance_counts=fiscal_issuance_counts,
        fiscal_exceptions=fiscal_exceptions, paid_print_counts=paid_print_counts,
        paid_print_exceptions=paid_print_exceptions,
    )
