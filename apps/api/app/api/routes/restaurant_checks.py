from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.api.diner_deps import DinerAuthenticatedContext, get_diner_authenticated_context
from app.core.execution import ActorType, ExecutionContext
from app.core.middleware import get_correlation_id
from app.restaurant.checks import errors, service
from app.restaurant.orders import service as draft_service


router = APIRouter(tags=['restaurant-checks'])
IdempotencyKey = Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[\x21-\x7e]+$')]


def _exact(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact money')
    return value


ExactNonNegativeMoney = Annotated[Decimal, BeforeValidator(_exact), Field(ge=0, allow_inf_nan=False)]


class CheckCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['INDIVIDUAL', 'GLOBAL_TABLE', 'SELECTED'] = 'INDIVIDUAL'
    diner_session_ids: list[int] = Field(default_factory=list)
    service_session_id: int | None = Field(default=None, gt=0)
    controller_diner_session_id: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def validate_composition(self):
        if self.mode == 'SELECTED' and not self.diner_session_ids:
            raise ValueError('SELECTED mode requires diner_session_ids')
        if len(self.diner_session_ids) != len(set(self.diner_session_ids)):
            raise ValueError('diner_session_ids must be distinct')
        if any(value <= 0 for value in self.diner_session_ids):
            raise ValueError('diner_session_ids must be positive')
        return self


class StaffCheckCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    diner_session_ids: list[int] = Field(default_factory=list)
    table_service_session_ids: list[int] = Field(default_factory=list)
    controller_diner_session_id: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def validate_scope(self):
        if not self.diner_session_ids and not self.table_service_session_ids:
            raise ValueError('At least one DINER or TABLE scope is required')
        if len(self.diner_session_ids) != len(set(self.diner_session_ids)):
            raise ValueError('diner_session_ids must be distinct')
        if len(self.table_service_session_ids) != len(set(self.table_service_session_ids)):
            raise ValueError('table_service_session_ids must be distinct')
        return self


class CheckVersionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class AddMemberRequest(CheckVersionRequest):
    diner_session_id: int = Field(gt=0)


class TransferControllerRequest(CheckVersionRequest):
    diner_session_id: int = Field(gt=0)


class ReasonRequest(CheckVersionRequest):
    reason: str = Field(min_length=1, max_length=500)


class GratuityRequest(CheckVersionRequest):
    input_type: Literal['PERCENTAGE', 'FIXED_AMOUNT']
    input_value: ExactNonNegativeMoney


class ContinuationDecisionRequest(CheckVersionRequest):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['YES', 'NO']


class DraftAbandonRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class CheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    status: str
    version: int
    fingerprint: str
    currency: str
    controller_diner_session_id: int | None
    member_ids: tuple[int, ...]
    diner_scope_ids: tuple[int, ...]
    table_scope_session_ids: tuple[int, ...]
    consumption_total: Decimal
    gratuity_total: Decimal
    liability_total: Decimal
    confirmed_settlement: Decimal
    outstanding: Decimal
    uncertain_exposure: Decimal
    frozen_at: Any
    settled_at: Any
    continuation_decision: str
    cancelled_at: Any
    details: Any
    signal: str | None = None


class EligibleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    diner_session_id: int
    service_session_id: int
    resource_id: int
    display_name: str
    eligible_order_ids: tuple[int, ...]
    eligible_total: Decimal
    currency: str | None
    active_check_id: int | None
    has_active_nonempty_draft: bool


class TableBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    service_session_id: int
    resource_id: int
    currency: str | None
    accepted_consumption: Decimal
    reserved_in_active_checks: Decimal
    unreserved_unsettled_consumption: Decimal
    settled_consumption: Decimal
    pending_exposure: Decimal
    reserved_payment_exposure: Decimal
    uncertain_exposure: Decimal
    outstanding_confirmed_balance: Decimal
    unresolved_active_checks: int
    closure_eligible: bool
    service_continuation_decision_required: bool


def _diner_execution(context: DinerAuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(ActorType.DINER, context.tenant_id, context.diner_session_id, None, get_correlation_id())


def _staff_execution(context: AuthenticatedContext) -> ExecutionContext:
    return ExecutionContext(ActorType.EMPLOYEE, context.tenant_id, context.membership_id, None, get_correlation_id())


def _error(exc: Exception, *, diner: bool = False) -> HTTPException:
    if isinstance(exc, errors.CheckPermissionError):
        return HTTPException(status.HTTP_403_FORBIDDEN, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, errors.CheckNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, errors.RestaurantCheckError):
        return HTTPException(status.HTTP_409_CONFLICT, {'code': exc.code, 'message': str(exc)})
    if isinstance(exc, ValueError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    raise exc


@router.get('/diner/eligible-consumption', response_model=tuple[EligibleResponse, ...])
async def diner_eligible(
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> tuple[object, ...]:
    return await service.eligible_consumption(
        db, tenant_id=context.tenant_id, location_id=context.location_id,
        owner_diner_session_id=context.diner_session_id,
    )


@router.post('/diner/restaurant-checks', response_model=CheckResponse, status_code=status.HTTP_201_CREATED)
async def diner_create_check(
    payload: CheckCreateRequest, response: Response,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> object:
    execution = _diner_execution(context)
    try:
        if payload.mode == 'INDIVIDUAL':
            value, replayed = await service.create_individual_check(
                db, context=execution, diner_session_id=context.diner_session_id, idempotency_key=idempotency_key,
            )
        elif payload.mode == 'GLOBAL_TABLE':
            if payload.service_session_id not in (None, context.service_session_id):
                raise errors.CheckNotFoundError('Service Session not found')
            value, replayed = await service.create_global_table_check(
                db, context=execution, service_session_id=context.service_session_id,
                controller_diner_session_id=context.diner_session_id, idempotency_key=idempotency_key,
            )
        else:
            selected = tuple(payload.diner_session_ids)
            if context.diner_session_id not in selected:
                raise errors.CheckPermissionError('Diner controller must be selected')
            value, replayed = await service.create_check(
                db, context=execution, diner_ids=selected,
                controller_diner_session_id=context.diner_session_id, idempotency_key=idempotency_key,
            )
    except Exception as exc:
        raise _error(exc, diner=True) from exc
    if replayed: response.status_code = status.HTTP_200_OK
    return value


@router.get('/diner/restaurant-checks/{check_id}', response_model=CheckResponse)
async def diner_get_check(
    check_id: Annotated[int, Path(gt=0)],
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    view: Literal['totalized', 'detailed'] = Query('totalized'),
) -> object:
    try:
        return await service.get_check(
            db, tenant_id=context.tenant_id, check_id=check_id, detailed=view == 'detailed',
            owner_diner_session_id=context.diner_session_id,
        )
    except Exception as exc:
        raise _error(exc, diner=True) from exc


async def _diner_mutation(call, *, context, db, **values):
    try:
        return await call(db, context=_diner_execution(context), **values)
    except Exception as exc:
        raise _error(exc, diner=True) from exc


@router.post('/diner/restaurant-checks/{check_id}/members', response_model=CheckResponse)
async def diner_add_member(check_id: int, payload: AddMemberRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey, response: Response) -> object:
    value, replayed = await _diner_mutation(service.add_member, context=context, db=db, check_id=check_id,
        diner_session_id=payload.diner_session_id, expected_version=payload.expected_version, idempotency_key=idempotency_key)
    if replayed: response.status_code = status.HTTP_200_OK
    return value


@router.delete('/diner/restaurant-checks/{check_id}/members/{diner_session_id}', response_model=CheckResponse)
async def diner_remove_member(
    check_id: int,
    diner_session_id: int,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
    expected_version: int = Query(ge=1),
    reason: str = Query(min_length=1, max_length=500),
) -> object:
    return (await _diner_mutation(service.remove_member, context=context, db=db, check_id=check_id,
        diner_session_id=diner_session_id, expected_version=expected_version, idempotency_key=idempotency_key, reason=reason))[0]


@router.put('/diner/restaurant-checks/{check_id}/gratuity', response_model=CheckResponse)
async def diner_gratuity(check_id: int, payload: GratuityRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    return (await _diner_mutation(service.update_gratuity, context=context, db=db, check_id=check_id,
        expected_version=payload.expected_version, input_type=payload.input_type,
        input_value=payload.input_value, idempotency_key=idempotency_key))[0]


@router.post('/diner/restaurant-checks/{check_id}/confirm-for-settlement', response_model=CheckResponse)
async def diner_freeze(check_id: int, payload: CheckVersionRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    return (await _diner_mutation(service.freeze_check, context=context, db=db, check_id=check_id,
        expected_version=payload.expected_version, idempotency_key=idempotency_key))[0]


@router.post('/diner/restaurant-checks/{check_id}/cancellation', response_model=CheckResponse)
async def diner_cancel(check_id: int, payload: ReasonRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    return (await _diner_mutation(service.cancel_check, context=context, db=db, check_id=check_id,
        expected_version=payload.expected_version, idempotency_key=idempotency_key, reason=payload.reason))[0]


@router.post('/diner/order-draft/abandon', status_code=status.HTTP_204_NO_CONTENT)
async def diner_abandon_draft(payload: DraftAbandonRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> Response:
    try:
        await draft_service.abandon_current_draft(
            db, tenant_id=context.tenant_id, conversation_id=context.conversation_id,
            expected_version=payload.expected_version, idempotency_key=idempotency_key,
            context=_diner_execution(context), owner_diner_session_id=context.diner_session_id,
            owned_conversation_id=context.conversation_id, correlation_id=get_correlation_id(),
        )
    except Exception as exc:
        from app.api.routes.diner_sessions import _draft_error
        raise _draft_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/restaurant-checks', response_model=CheckResponse, status_code=status.HTTP_201_CREATED)
async def staff_create_check(payload: StaffCheckCreateRequest, response: Response,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    try:
        value, replayed = await service.create_scoped_check(
            db, context=_staff_execution(context), diner_ids=tuple(payload.diner_session_ids),
            table_service_session_ids=tuple(payload.table_service_session_ids),
            controller_diner_session_id=payload.controller_diner_session_id, idempotency_key=idempotency_key,
        )
    except Exception as exc: raise _error(exc) from exc
    if replayed: response.status_code = status.HTTP_200_OK
    return value


@router.get('/restaurant-checks/{check_id}', response_model=CheckResponse)
async def staff_get_check(
    check_id: int,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.read'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    view: Literal['totalized', 'detailed'] = Query('totalized'),
) -> object:
    try: return await service.get_check(db, tenant_id=context.tenant_id, check_id=check_id, detailed=view == 'detailed')
    except Exception as exc: raise _error(exc) from exc


@router.get('/restaurant-service-sessions/{session_id}/outstanding-balance', response_model=TableBalanceResponse)
async def staff_table_balance(session_id: int,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.read'))],
    db: Annotated[AsyncSession, Depends(get_db)]) -> object:
    try: return await service.table_balance(db, tenant_id=context.tenant_id, service_session_id=session_id)
    except Exception as exc: raise _error(exc) from exc


@router.post('/restaurant-checks/{check_id}/members', response_model=CheckResponse)
async def staff_add_member(check_id: int, payload: AddMemberRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    try: return (await service.add_member(db, context=_staff_execution(context), check_id=check_id,
        diner_session_id=payload.diner_session_id, expected_version=payload.expected_version, idempotency_key=idempotency_key))[0]
    except Exception as exc: raise _error(exc) from exc


@router.delete('/restaurant-checks/{check_id}/members/{diner_session_id}', response_model=CheckResponse)
async def staff_remove_member(
    check_id: int,
    diner_session_id: int,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
    expected_version: int = Query(ge=1),
    reason: str = Query(min_length=1, max_length=500),
) -> object:
    try: return (await service.remove_member(db, context=_staff_execution(context), check_id=check_id,
        diner_session_id=diner_session_id, expected_version=expected_version, idempotency_key=idempotency_key, reason=reason))[0]
    except Exception as exc: raise _error(exc) from exc


@router.post('/restaurant-checks/{check_id}/controller', response_model=CheckResponse)
async def staff_transfer_controller(
    check_id: int,
    payload: TransferControllerRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: IdempotencyKey,
) -> object:
    try:
        return (await service.transfer_controller(
            db, context=_staff_execution(context), check_id=check_id,
            diner_session_id=payload.diner_session_id,
            expected_version=payload.expected_version,
            idempotency_key=idempotency_key,
        ))[0]
    except Exception as exc:
        raise _error(exc) from exc


@router.put('/restaurant-checks/{check_id}/gratuity', response_model=CheckResponse)
async def staff_gratuity(check_id: int, payload: GratuityRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    try: return (await service.update_gratuity(db, context=_staff_execution(context), check_id=check_id,
        expected_version=payload.expected_version, input_type=payload.input_type,
        input_value=payload.input_value, idempotency_key=idempotency_key))[0]
    except Exception as exc: raise _error(exc) from exc


@router.post('/restaurant-checks/{check_id}/confirm-for-settlement', response_model=CheckResponse)
async def staff_freeze(check_id: int, payload: CheckVersionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    try: return (await service.freeze_check(db, context=_staff_execution(context), check_id=check_id,
        expected_version=payload.expected_version, idempotency_key=idempotency_key))[0]
    except Exception as exc: raise _error(exc) from exc


@router.post('/restaurant-checks/{check_id}/cancellation', response_model=CheckResponse)
async def staff_cancel(check_id: int, payload: ReasonRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey) -> object:
    try: return (await service.cancel_check(db, context=_staff_execution(context), check_id=check_id,
        expected_version=payload.expected_version, idempotency_key=idempotency_key, reason=payload.reason))[0]
    except Exception as exc: raise _error(exc) from exc


@router.post('/diner/restaurant-checks/{check_id}/continuation-decision', response_model=CheckResponse)
async def diner_continuation_decision(
    check_id: int, payload: ContinuationDecisionRequest,
    context: Annotated[DinerAuthenticatedContext, Depends(get_diner_authenticated_context)],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> object:
    try:
        return (await service.decide_continuation(
            db, context=_diner_execution(context), check_id=check_id,
            expected_version=payload.expected_version, decision=payload.decision,
            idempotency_key=idempotency_key,
        ))[0]
    except Exception as exc:
        raise _error(exc, diner=True) from exc


@router.post('/restaurant-checks/{check_id}/continuation-decision', response_model=CheckResponse)
async def staff_continuation_decision(
    check_id: int, payload: ContinuationDecisionRequest,
    context: Annotated[AuthenticatedContext, Depends(require_permission('restaurant_check.manage'))],
    db: Annotated[AsyncSession, Depends(get_db)], idempotency_key: IdempotencyKey,
) -> object:
    try:
        return (await service.decide_continuation(
            db, context=_staff_execution(context), check_id=check_id,
            expected_version=payload.expected_version, decision=payload.decision,
            idempotency_key=idempotency_key,
        ))[0]
    except Exception as exc:
        raise _error(exc) from exc
