from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.api.diner_deps import DinerAuthenticatedContext, get_diner_authenticated_context
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.integrations.payments.contracts import EphemeralCustomerPaymentSource
from app.restaurant.integrations.payments.resolver import (
    PaymentExecutorResolver,
    PaymentExecutorSelectionMode,
)
from app.restaurant.payments import errors, service


router = APIRouter(tags=['restaurant-payments'])
IdempotencyKey = Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[\x21-\x7e]+$')]


def _exact(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact money')
    return value


PositiveMoney = Annotated[Decimal, BeforeValidator(_exact), Field(gt=0, allow_inf_nan=False)]


class PaymentInitiationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_check_version: int = Field(ge=1)
    expected_check_fingerprint: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    amount: PositiveMoney
    currency: str = Field(min_length=3, max_length=3)
    method_category: Literal['CASH', 'CARD', 'TRANSFER']
    payer_type: Literal['DINER', 'OTHER']
    payer_diner_session_id: int | None = Field(default=None, gt=0)
    payer_reference: str | None = Field(default=None, min_length=1, max_length=200)
    cash_tendered_amount: PositiveMoney | None = None
    selection_mode: Literal['EXPLICIT', 'AUTO'] | None = None
    executor_key: str | None = Field(default=None, min_length=1, max_length=128)
    customer_payment_source: SecretStr | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
        description='Opaque payment-source token/reference; never PAN or CVV',
    )
    execution_credential: SecretStr | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
        json_schema_extra={'deprecated': True},
        description='Deprecated alias for customer_payment_source',
    )

    @model_validator(mode='after')
    def validate_payer(self):
        if self.payer_type == 'DINER' and self.payer_diner_session_id is None:
            raise ValueError('DINER payer requires payer_diner_session_id')
        if self.payer_type == 'OTHER' and not self.payer_reference:
            raise ValueError('OTHER payer requires payer_reference')
        if self.customer_payment_source is not None and self.execution_credential is not None:
            raise ValueError('Supply only customer_payment_source, not its deprecated alias')
        if self.method_category == 'CASH' and self.selection_mode is not None:
            raise ValueError('CASH does not accept executor selection')
        if self.selection_mode == 'EXPLICIT' and not self.executor_key:
            raise ValueError('EXPLICIT selection requires executor_key')
        if self.selection_mode == 'AUTO' and self.executor_key is not None:
            raise ValueError('AUTO selection cannot include executor_key')
        return self


class RetryPaymentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer_payment_source: SecretStr | None = Field(
        default=None, min_length=1, max_length=4096
    )
    execution_credential: SecretStr | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
        json_schema_extra={'deprecated': True},
    )

    @model_validator(mode='after')
    def validate_source(self):
        if self.customer_payment_source is not None and self.execution_credential is not None:
            raise ValueError('Supply only customer_payment_source, not its deprecated alias')
        return self


class AvailablePaymentExecutorResponse(BaseModel):
    executor_key: str
    display_name: str
    topology: str
    method_category: str
    currency: str


class PaymentAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence: int
    attempt_type: str
    executor_key: str
    actor_type: str
    actor_id: int | None
    correlation_id: str | None
    started_at: Any
    external_call_started_at: Any
    completed_at: Any
    result: str
    external_reference: str | None
    external_status: str | None
    error_code: str | None
    error_message: str | None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    check_id: int
    check_version: int
    check_fingerprint: str
    amount: Decimal
    currency: str
    method_category: str
    payer_type: str
    payer_diner_session_id: int | None
    payer_reference: str | None
    state: str
    executor_key: str | None
    external_reference: str | None
    external_status: str | None
    instrument_brand: str | None
    instrument_last_four: str | None
    instrument_display: str | None
    cash_tendered_amount: Decimal | None
    cash_change_due: Decimal | None
    terminal_at: Any
    attempts: tuple[PaymentAttemptResponse, ...]


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    check_id: int
    check_status: str
    check_version: int
    check_fingerprint: str
    liability_total: Decimal
    currency: str
    confirmed_settlement: Decimal
    reserved_financial_exposure: Decimal
    uncertain_exposure: Decimal
    available_to_initiate: Decimal
    payments: tuple[PaymentResponse, ...]


def _staff_execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(ActorType.EMPLOYEE, context.tenant_id, context.membership_id, None, get_correlation_id())


def _diner_execution(context: DinerAuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(ActorType.DINER, context.tenant_id, context.diner_session_id, None, get_correlation_id())


def _customer_payment_source(
    canonical: SecretStr | None,
    legacy: SecretStr | None,
) -> EphemeralCustomerPaymentSource | None:
    value = canonical if canonical is not None else legacy
    return None if value is None else EphemeralCustomerPaymentSource(value=value)


def _selection_mode(
    payload: PaymentInitiationRequest,
) -> PaymentExecutorSelectionMode | None:
    if payload.method_category == 'CASH':
        return None
    if payload.selection_mode is not None:
        return PaymentExecutorSelectionMode(payload.selection_mode)
    return (
        PaymentExecutorSelectionMode.EXPLICIT
        if payload.executor_key else PaymentExecutorSelectionMode.AUTO
    )


def _error(exc: Exception) -> HTTPException:
    from app.restaurant.checks.errors import RestaurantCheckError

    if isinstance(exc, errors.PaymentPermissionError):
        return HTTPException(status.HTTP_403_FORBIDDEN, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, errors.PaymentNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, (
        errors.PaymentExecutorAdapterNotRegisteredError,
        errors.PaymentExecutorConfigurationNotFoundError,
        errors.PaymentExecutorConfigurationInactiveError,
        errors.NoEligiblePaymentExecutorError,
        errors.UnsupportedPaymentExecutorMethodError,
        errors.UnsupportedPaymentExecutorCurrencyError,
        errors.UnsupportedPaymentExecutorCapabilityError,
    )):
        return HTTPException(status.HTTP_409_CONFLICT, {
            'code': 'PAYMENT_EXECUTOR_UNAVAILABLE',
            'message': 'Payment executor is unavailable',
        })
    if isinstance(exc, errors.MerchantCredentialResolutionError):
        return HTTPException(status.HTTP_409_CONFLICT, {
            'code': 'PAYMENT_EXECUTION_UNAVAILABLE',
            'message': 'Payment execution is unavailable',
        })
    if isinstance(exc, (
        errors.InvalidPaymentAmountError,
        errors.InvalidCashTenderError,
        errors.SensitiveCredentialMisuseError,
        errors.InvalidPaymentExecutorSelectionError,
    )):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, errors.RestaurantPaymentError):
        return HTTPException(status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, RestaurantCheckError):
        return HTTPException(status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)})
    raise exc


async def _initiate(
    *, db: AsyncSession, execution: ExecutionContext, check_id: int,
    payload: PaymentInitiationRequest, idempotency_key: str,
) -> tuple[object, bool]:
    return await service.initiate_payment(
        db, context=execution, check_id=check_id,
        expected_check_version=payload.expected_check_version,
        expected_check_fingerprint=payload.expected_check_fingerprint,
        amount=payload.amount, currency=payload.currency,
        method_category=payload.method_category, payer_type=payload.payer_type,
        payer_diner_session_id=payload.payer_diner_session_id,
        payer_reference=payload.payer_reference,
        cash_tendered_amount=payload.cash_tendered_amount,
        executor_key=payload.executor_key, idempotency_key=idempotency_key,
        selection_mode=_selection_mode(payload),
        executor_registry=db.info['payment_executor_registry'],
        credential_resolver=db.info.get('merchant_credential_resolver'),
        customer_payment_source=_customer_payment_source(
            payload.customer_payment_source, payload.execution_credential
        ),
    )


async def _available_executors(
    *,
    db: AsyncSession,
    tenant_id: int,
    organization_id: int,
    location_id: int,
    method_category: str,
    currency: str,
) -> list[AvailablePaymentExecutorResponse]:
    resolved = await PaymentExecutorResolver(
        db, db.info['payment_executor_registry']
    ).list_available(
        tenant_id=tenant_id,
        organization_id=organization_id,
        location_id=location_id,
        method_category=method_category,
        currency=currency,
    )
    return [AvailablePaymentExecutorResponse(
        executor_key=value.configuration.executor_key,
        display_name=value.configuration.display_name,
        topology=value.configuration.topology,
        method_category=method_category,
        currency=currency.strip().upper(),
    ) for value in resolved]


@router.get('/diner/payment-executors', response_model=list[AvailablePaymentExecutorResponse])
async def diner_available_payment_executors(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    method_category: Literal['CARD', 'TRANSFER'] = Query(),
    currency: str = Query(min_length=3, max_length=3, pattern='^[A-Za-z]{3}$'),
) -> list[AvailablePaymentExecutorResponse]:
    return await _available_executors(
        db=db,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        location_id=context.location_id,
        method_category=method_category,
        currency=currency,
    )


@router.get('/payment-executors', response_model=list[AvailablePaymentExecutorResponse])
async def staff_available_payment_executors(
    context: Annotated[
        AuthenticatedContext, Depends(require_permission('restaurant_payment.read'))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    organization_id: int = Query(gt=0),
    location_id: int = Query(gt=0),
    method_category: Literal['CARD', 'TRANSFER'] = Query(),
    currency: str = Query(min_length=3, max_length=3, pattern='^[A-Za-z]{3}$'),
) -> list[AvailablePaymentExecutorResponse]:
    return await _available_executors(
        db=db,
        tenant_id=context.tenant_id,
        organization_id=organization_id,
        location_id=location_id,
        method_category=method_category,
        currency=currency,
    )


@router.post('/diner/restaurant-checks/{check_id}/payments', response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def diner_initiate_payment(
    check_id: int, payload: PaymentInitiationRequest, response: Response,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> object:
    if payload.method_category == 'CASH' or payload.payer_type != 'DINER' or payload.payer_diner_session_id != context.diner_session_id:
        raise _error(errors.PaymentPermissionError('Diner payment must identify the authenticated diner and cannot confirm cash'))
    try:
        value, replayed = await _initiate(
            db=db, execution=_diner_execution(context), check_id=check_id,
            payload=payload, idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.get('/diner/restaurant-checks/{check_id}/settlement', response_model=SettlementResponse)
async def diner_get_settlement(
    check_id: int,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_check_settlement(
            db, tenant_id=context.tenant_id, check_id=check_id,
            owner_diner_session_id=context.diner_session_id,
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/restaurant-checks/{check_id}/payments', response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def staff_initiate_payment(
    check_id: int, payload: PaymentInitiationRequest, response: Response,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_payment.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> object:
    try:
        value, replayed = await _initiate(
            db=db, execution=_staff_execution(context), check_id=check_id,
            payload=payload, idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _error(exc) from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
    return value


@router.get('/restaurant-checks/{check_id}/settlement', response_model=SettlementResponse)
async def staff_get_settlement(
    check_id: int,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_payment.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.get_check_settlement(db, tenant_id=context.tenant_id, check_id=check_id)
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/restaurant-payments/{payment_id}/retry', response_model=PaymentResponse)
async def staff_retry_payment(
    payment_id: int, payload: RetryPaymentRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_payment.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.retry_payment(
            db, context=_staff_execution(context), payment_id=payment_id,
            executor_registry=db.info['payment_executor_registry'],
            credential_resolver=db.info.get('merchant_credential_resolver'),
            customer_payment_source=_customer_payment_source(
                payload.customer_payment_source, payload.execution_credential
            ),
        )
    except Exception as exc:
        raise _error(exc) from exc


@router.post('/restaurant-payments/{payment_id}/recover', response_model=PaymentResponse)
async def staff_recover_payment(
    payment_id: int,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_payment.recover'))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> object:
    try:
        return await service.recover_payment(
            db, context=_staff_execution(context), payment_id=payment_id,
            executor_registry=db.info['payment_executor_registry'],
            credential_resolver=db.info.get('merchant_credential_resolver'),
        )
    except Exception as exc:
        raise _error(exc) from exc
