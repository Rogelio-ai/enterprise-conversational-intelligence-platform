from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedContext,
    get_db,
    require_permission,
    require_staff_location_access,
)
from app.models import (
    Customer,
    CustomerFiscalProfile,
    DinerSession,
    IssuerFiscalProfile,
    RestaurantCheck,
    RestaurantCheckMember,
)


router = APIRouter(tags=['restaurant-fiscal-profiles'])


class FiscalProfilePayload(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    legal_name: str = Field(min_length=1, max_length=200)
    tax_identifier: str = Field(min_length=1, max_length=64)
    tax_regime: str = Field(min_length=1, max_length=100)
    fiscal_postal_code: str = Field(min_length=1, max_length=32)


class RecipientFiscalProfilePayload(FiscalProfilePayload):
    invoice_usage: str = Field(min_length=1, max_length=64)


class IssuerFiscalProfileResponse(FiscalProfilePayload):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class RecipientFiscalProfileResponse(RecipientFiscalProfilePayload):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class BillingFiscalContextResponse(BaseModel):
    check_id: int
    organization_id: int
    location_id: int
    check_status: str
    customer_id: int
    customer_display_name: str | None
    customer_email: str | None
    issuer_profiles: tuple[IssuerFiscalProfileResponse, ...]
    recipient_profile: RecipientFiscalProfileResponse | None


async def _authorized_check(
    db: AsyncSession,
    context: AuthenticatedContext,
    *,
    check_id: int,
    location_id: int,
) -> RestaurantCheck:
    check = await db.scalar(select(RestaurantCheck).where(
        RestaurantCheck.id == check_id,
        RestaurantCheck.tenant_id == context.tenant_id,
        RestaurantCheck.location_id == location_id,
    ))
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Restaurant Check not found')
    await require_staff_location_access(location_id, context, db)
    return check


async def _check_customer_id(db: AsyncSession, check: RestaurantCheck) -> int:
    customer_id = None
    if check.controller_diner_session_id is not None:
        customer_id = await db.scalar(select(DinerSession.customer_id).where(
            DinerSession.id == check.controller_diner_session_id,
            DinerSession.tenant_id == check.tenant_id,
            DinerSession.location_id == check.location_id,
        ))
    if customer_id is None:
        customer_id = await db.scalar(
            select(DinerSession.customer_id)
            .join(
                RestaurantCheckMember,
                RestaurantCheckMember.diner_session_id == DinerSession.id,
            )
            .where(
                RestaurantCheckMember.check_id == check.id,
                RestaurantCheckMember.tenant_id == check.tenant_id,
                RestaurantCheckMember.location_id == check.location_id,
                DinerSession.customer_id.is_not(None),
            )
            .order_by(RestaurantCheckMember.id)
        )
    if customer_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {'code': 'BILLING_CUSTOMER_REQUIRED', 'message': 'Check has no fiscal customer identity'},
        )
    return int(customer_id)


async def _fiscal_context(
    db: AsyncSession,
    *,
    check: RestaurantCheck,
) -> BillingFiscalContextResponse:
    customer_id = await _check_customer_id(db, check)
    customer = await db.scalar(select(Customer).where(
        Customer.id == customer_id,
        Customer.tenant_id == check.tenant_id,
    ))
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Customer not found')
    issuer_profiles = tuple((await db.scalars(select(IssuerFiscalProfile).where(
        IssuerFiscalProfile.tenant_id == check.tenant_id,
        IssuerFiscalProfile.organization_id == check.organization_id,
        IssuerFiscalProfile.status == 'ACTIVE',
    ).order_by(IssuerFiscalProfile.id))).all())
    recipient_profile = await db.scalar(select(CustomerFiscalProfile).where(
        CustomerFiscalProfile.tenant_id == check.tenant_id,
        CustomerFiscalProfile.customer_id == customer_id,
        CustomerFiscalProfile.status == 'ACTIVE',
    ).order_by(CustomerFiscalProfile.id.desc()))
    return BillingFiscalContextResponse(
        check_id=check.id,
        organization_id=check.organization_id,
        location_id=check.location_id,
        check_status=check.status,
        customer_id=customer_id,
        customer_display_name=customer.display_name,
        customer_email=customer.email,
        issuer_profiles=issuer_profiles,
        recipient_profile=recipient_profile,
    )


@router.get(
    '/restaurant-checks/{check_id}/fiscal-context',
    response_model=BillingFiscalContextResponse,
)
async def get_fiscal_context(
    check_id: Annotated[int, Path(gt=0)],
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_check.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    check = await _authorized_check(
        db, context, check_id=check_id, location_id=location_id
    )
    return await _fiscal_context(db, check=check)


@router.put(
    '/restaurant-checks/{check_id}/recipient-fiscal-profile',
    response_model=RecipientFiscalProfileResponse,
)
async def put_recipient_fiscal_profile(
    check_id: Annotated[int, Path(gt=0)],
    payload: RecipientFiscalProfilePayload,
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    check = await _authorized_check(
        db, context, check_id=check_id, location_id=location_id
    )
    customer_id = await _check_customer_id(db, check)
    value = await db.scalar(select(CustomerFiscalProfile).where(
        CustomerFiscalProfile.tenant_id == context.tenant_id,
        CustomerFiscalProfile.customer_id == customer_id,
    ).order_by(CustomerFiscalProfile.id.desc()).with_for_update())
    values = payload.model_dump()
    if value is None:
        value = CustomerFiscalProfile(
            tenant_id=context.tenant_id, customer_id=customer_id,
            status='ACTIVE', **values,
        )
        db.add(value)
    else:
        for field, field_value in values.items():
            setattr(value, field, field_value)
        value.status = 'ACTIVE'
    await db.commit()
    await db.refresh(value)
    return value


@router.put(
    '/restaurant-checks/{check_id}/issuer-fiscal-profile',
    response_model=IssuerFiscalProfileResponse,
)
async def put_issuer_fiscal_profile(
    check_id: Annotated[int, Path(gt=0)],
    payload: FiscalProfilePayload,
    location_id: Annotated[int, Query(gt=0)],
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    check = await _authorized_check(
        db, context, check_id=check_id, location_id=location_id
    )
    value = await db.scalar(select(IssuerFiscalProfile).where(
        IssuerFiscalProfile.tenant_id == context.tenant_id,
        IssuerFiscalProfile.organization_id == check.organization_id,
    ).order_by(IssuerFiscalProfile.id.desc()).with_for_update())
    values = payload.model_dump()
    if value is None:
        value = IssuerFiscalProfile(
            tenant_id=context.tenant_id,
            organization_id=check.organization_id,
            status='ACTIVE',
            **values,
        )
        db.add(value)
    else:
        for field, field_value in values.items():
            setattr(value, field, field_value)
        value.status = 'ACTIVE'
    await db.commit()
    await db.refresh(value)
    return value
