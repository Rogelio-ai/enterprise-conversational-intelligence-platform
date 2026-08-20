from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.models import Customer, CustomerExternalIdentity
from app.restaurant.customers.service import (
    normalize_display_name,
    normalize_email,
    normalize_phone,
)


router = APIRouter(prefix='/customers', tags=['customers'])
logger = logging.getLogger('ecip.customers')


class CustomerCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return normalize_display_name(value)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_email(value)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @model_validator(mode='after')
    def validate_identity(self) -> 'CustomerCreateRequest':
        if self.display_name is None and self.email is None and self.phone is None:
            raise ValueError('At least one Customer identity or contact field is required')
        return self


class CustomerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    status: Literal['ACTIVE', 'INACTIVE'] | None = None

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return normalize_display_name(value)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_email(value)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @model_validator(mode='after')
    def validate_patch(self) -> 'CustomerUpdateRequest':
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        if 'status' in self.model_fields_set and self.status is None:
            raise ValueError('Customer status cannot be null')
        return self


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    display_name: str | None
    email: str | None
    phone: str | None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    limit: int
    offset: int


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Customer not found')


def _identity_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail='Customer requires an identity/contact field or external identity',
    )


async def _get_customer(
    db: AsyncSession,
    *,
    customer_id: int,
    tenant_id: int,
    for_update: bool = False,
) -> Customer:
    statement = select(Customer).where(
        Customer.id == customer_id,
        Customer.tenant_id == tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    customer = await db.scalar(statement)
    if customer is None:
        raise _not_found()
    return customer


@router.get('', response_model=CustomerListResponse)
async def list_customers(
    context: Annotated[AuthenticatedContext, Depends(require_permission('customer.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str | None = Query(default=None, max_length=320),
    phone: str | None = Query(default=None, max_length=64),
    status_filter: Literal['ACTIVE', 'INACTIVE'] | None = Query(default=None, alias='status'),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CustomerListResponse:
    try:
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    statement = select(Customer).where(Customer.tenant_id == context.tenant_id)
    if normalized_email is not None:
        statement = statement.where(Customer.email == normalized_email)
    if normalized_phone is not None:
        statement = statement.where(Customer.phone == normalized_phone)
    if status_filter is not None:
        statement = statement.where(Customer.status == status_filter)
    result = await db.execute(statement.order_by(Customer.id).limit(limit).offset(offset))
    return CustomerListResponse(items=list(result.scalars().all()), limit=limit, offset=offset)


@router.post('', response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('customer.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Customer:
    customer = Customer(
        tenant_id=context.tenant_id,
        display_name=payload.display_name,
        email=payload.email,
        phone=payload.phone,
        status='ACTIVE',
        source='PLATFORM',
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    logger.info(
        'Customer created',
        extra={
            'event': 'customer_created',
            'operation': 'create',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'customer_id': customer.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return customer


@router.get('/{customer_id}', response_model=CustomerResponse)
async def get_customer(
    customer_id: Annotated[int, Path(gt=0)],
    context: Annotated[AuthenticatedContext, Depends(require_permission('customer.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Customer:
    return await _get_customer(
        db,
        customer_id=customer_id,
        tenant_id=context.tenant_id,
    )


@router.patch('/{customer_id}', response_model=CustomerResponse)
async def update_customer(
    customer_id: Annotated[int, Path(gt=0)],
    payload: CustomerUpdateRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('customer.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Customer:
    customer = await _get_customer(
        db,
        customer_id=customer_id,
        tenant_id=context.tenant_id,
        for_update=True,
    )
    values = payload.model_dump(exclude_unset=True)
    resulting_identity = {
        field: values.get(field, getattr(customer, field))
        for field in ('display_name', 'email', 'phone')
    }
    if all(value is None for value in resulting_identity.values()):
        has_external_identity = await db.scalar(
            select(
                exists().where(
                    CustomerExternalIdentity.tenant_id == context.tenant_id,
                    CustomerExternalIdentity.customer_id == customer.id,
                )
            )
        )
        if not has_external_identity:
            raise _identity_required()

    for field, value in values.items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    logger.info(
        'Customer updated',
        extra={
            'event': 'customer_updated',
            'operation': 'update',
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'customer_id': customer.id,
            'correlation_id': get_correlation_id(),
        },
    )
    return customer
