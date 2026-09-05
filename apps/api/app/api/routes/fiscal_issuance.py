from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.fiscal_issuance import errors, service
from app.restaurant.fiscal_issuance.contracts import (
    InitiateFiscalIssuanceCommand,
    RecoverFiscalIssuanceCommand,
    RetryFiscalIssuanceCommand,
)


router = APIRouter(tags=['restaurant-fiscal-issuance'])
IdempotencyKey = Annotated[
    str,
    Header(
        alias='Idempotency-Key',
        min_length=1,
        max_length=128,
        pattern=r'^[\x21-\x7e]+$',
    ),
]


class FiscalIssuanceCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    provider_key: str = Field(min_length=1, max_length=128)
    credential_binding: str | None = Field(default=None, min_length=1, max_length=200)


class FiscalIssuanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    billing_document_id: int
    provider_key: str
    state: str
    external_reference: str | None
    external_status: str | None
    attempt_count: int
    requested_at: datetime
    completed_at: datetime | None


def _execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(
        actor_type=ActorType.EMPLOYEE,
        tenant_id=context.tenant_id,
        principal_id=context.membership_id,
        principal_reference=None,
        correlation_id=get_correlation_id(),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (
        errors.FiscalBillingDocumentNotFoundError,
        errors.FiscalIssuanceNotFoundError,
    )):
        return HTTPException(status.HTTP_404_NOT_FOUND, {
            'code': exc.code,
            'message': 'Fiscal issuance resource was not found',
        })
    if isinstance(exc, (
        errors.FiscalIssuanceRequestInvalidError,
        errors.FiscalCanonicalEvidenceInvalidError,
    )):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {
            'code': exc.code,
            'message': str(exc),
        })
    if isinstance(exc, errors.FiscalProviderUnavailableError):
        return HTTPException(status.HTTP_409_CONFLICT, {
            'code': exc.code,
            'message': 'Fiscal provider is unavailable',
        })
    if isinstance(exc, errors.FiscalCredentialResolutionError):
        return HTTPException(status.HTTP_409_CONFLICT, {
            'code': exc.code,
            'message': 'Fiscal issuance credentials are unavailable',
        })
    if isinstance(exc, errors.FiscalIssuanceError):
        return HTTPException(status.HTTP_409_CONFLICT, {
            'code': exc.code,
            'message': str(exc),
        })
    raise exc


@router.post(
    '/billing-documents/{billing_document_id}/issuances',
    response_model=FiscalIssuanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_fiscal_issuance(
    billing_document_id: int,
    payload: FiscalIssuanceCreateRequest,
    response: Response,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission('restaurant_check.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
    organization_id: int = Query(gt=0),
    location_id: int = Query(gt=0),
) -> object:
    try:
        value, replayed = await service.initiate_fiscal_issuance(
            db,
            execution=_execution(context),
            command=InitiateFiscalIssuanceCommand(
                organization_id=organization_id,
                location_id=location_id,
                billing_document_id=billing_document_id,
                provider_key=payload.provider_key,
                credential_binding=payload.credential_binding,
                idempotency_key=idempotency_key,
            ),
            provider_registry=db.info['fiscal_provider_registry'],
            credential_resolver=db.info.get('fiscal_credential_resolver'),
            artifact_storage=db.info.get('fiscal_artifact_storage'),
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.post(
    '/billing-issuances/{issuance_id}/recover',
    response_model=FiscalIssuanceResponse,
)
async def recover_fiscal_issuance(
    issuance_id: int,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission('restaurant_check.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    location_id: int = Query(gt=0),
) -> object:
    try:
        return await service.recover_fiscal_issuance(
            db,
            execution=_execution(context),
            command=RecoverFiscalIssuanceCommand(
                organization_id=organization_id,
                location_id=location_id,
                billing_issuance_id=issuance_id,
            ),
            provider_registry=db.info['fiscal_provider_registry'],
            credential_resolver=db.info.get('fiscal_credential_resolver'),
            artifact_storage=db.info.get('fiscal_artifact_storage'),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post(
    '/billing-issuances/{issuance_id}/retry',
    response_model=FiscalIssuanceResponse,
)
async def retry_fiscal_issuance(
    issuance_id: int,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission('restaurant_check.manage')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    location_id: int = Query(gt=0),
) -> object:
    try:
        return await service.retry_fiscal_issuance(
            db,
            execution=_execution(context),
            command=RetryFiscalIssuanceCommand(
                organization_id=organization_id,
                location_id=location_id,
                billing_issuance_id=issuance_id,
            ),
            provider_registry=db.info['fiscal_provider_registry'],
            credential_resolver=db.info.get('fiscal_credential_resolver'),
            artifact_storage=db.info.get('fiscal_artifact_storage'),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.get(
    '/billing-issuances/{issuance_id}',
    response_model=FiscalIssuanceResponse,
)
async def get_fiscal_issuance(
    issuance_id: int,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_permission('restaurant_check.read')),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    location_id: int = Query(gt=0),
) -> object:
    try:
        return await service.get_fiscal_issuance(
            db,
            tenant_id=context.tenant_id,
            organization_id=organization_id,
            location_id=location_id,
            issuance_id=issuance_id,
        )
    except Exception as exc:
        raise _error(exc) from exc
