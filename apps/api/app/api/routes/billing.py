from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.billing import errors, service
from app.restaurant.billing.contracts import CreateBillingDocumentCommand


router = APIRouter(tags=['restaurant-billing'])
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key',
        min_length=1,
        max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


class BillingCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    organization_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    issuer_fiscal_profile_id: int = Field(gt=0)
    recipient_fiscal_profile_id: int = Field(gt=0)


class BillingDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    restaurant_check_id: int
    source_check_version: int
    source_check_fingerprint: str
    document_type: str
    status: str
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    issuer_snapshot: dict[str, str]
    recipient_snapshot: dict[str, str]
    issuer_fiscal_postal_code: str | None
    readiness_evidence_fingerprint: str | None
    created_at: datetime
    updated_at: datetime


class BillingDocumentLineTaxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tax_category: str
    tax_rate: Decimal
    taxable_base: Decimal
    tax_amount: Decimal
    tax_treatment: str
    jurisdiction_code: str | None
    tax_effect: str | None
    source_tax_evidence_fingerprint: str | None
    created_at: datetime


class BillingDocumentLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_restaurant_order_id: int
    source_restaurant_order_item_id: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    base_amount: Decimal
    discount_amount: Decimal
    commercial_total: Decimal
    fiscal_product_classification_scheme: str | None
    fiscal_product_classification_code: str | None
    fiscal_unit_classification_scheme: str | None
    fiscal_unit_classification_code: str | None
    fiscal_unit_value: Decimal | None
    fiscal_line_amount: Decimal | None
    fiscal_discount_amount: Decimal | None
    source_fiscal_evidence_fingerprint: str | None
    created_at: datetime
    taxes: tuple[BillingDocumentLineTaxResponse, ...]


class BillingDocumentDetailResponse(BillingDocumentResponse):
    model_config = ConfigDict(from_attributes=True)

    lines: tuple[BillingDocumentLineResponse, ...]


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.EMPLOYEE,
        context.tenant_id,
        context.membership_id,
        None,
        get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    detail = {'code': getattr(exc, 'code', 'RESTAURANT_BILLING_ERROR'), 'message': str(exc)}
    if isinstance(exc, errors.BillingDocumentNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail)
    if isinstance(exc, errors.BillingRequestInvalidError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)
    if isinstance(exc, errors.RestaurantBillingError):
        return HTTPException(status.HTTP_409_CONFLICT, detail)
    raise exc


@router.post(
    '/restaurant-checks/{check_id}/billing-documents',
    response_model=BillingDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_billing_document(
    check_id: int,
    payload: BillingCreateRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission('restaurant_check.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> object:
    try:
        value, replayed = await service.create_billing_document(
            db,
            context=_execution(context),
            command=CreateBillingDocumentCommand(
                restaurant_check_id=check_id,
                organization_id=payload.organization_id,
                location_id=payload.location_id,
                issuer_fiscal_profile_id=payload.issuer_fiscal_profile_id,
                recipient_fiscal_profile_id=payload.recipient_fiscal_profile_id,
                idempotency_key=idempotency_key,
            ),
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.get(
    '/billing-documents/{document_id}',
    response_model=BillingDocumentDetailResponse,
)
async def get_billing_document(
    document_id: int,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission('restaurant_check.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    location_id: int = Query(gt=0),
) -> object:
    try:
        return await service.get_billing_document(
            db,
            tenant_id=context.tenant_id,
            organization_id=organization_id,
            location_id=location_id,
            document_id=document_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
