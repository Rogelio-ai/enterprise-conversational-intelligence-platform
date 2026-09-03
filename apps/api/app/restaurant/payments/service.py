from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Mapping
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    RestaurantCheck,
    RestaurantCheckAllocation,
    RestaurantCheckMember,
    RestaurantCheckSettlement,
    RestaurantCheckTableScope,
    RestaurantPayment,
    RestaurantPaymentAttempt,
    RestaurantServiceSession,
    DinerSession,
)
from app.restaurant.checks import service as check_service
from app.restaurant.integrations.payments.contracts import (
    EphemeralExecutionCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
    PaymentExecutionResult,
    PaymentRecoveryOutcome,
    PaymentRecoveryRequest,
    PaymentRecoveryResult,
)
from app.restaurant.integrations.payments.ports import PaymentExecutionPort, PaymentRecoveryPort
from app.restaurant.payments import errors
from app.restaurant.payments.contracts import (
    CheckSettlementProjection,
    PaymentAttemptProjection,
    PaymentProjection,
)


ZERO = Decimal('0.0000')
MONEY_UNIT = Decimal('0.0001')
REQUEST_SCHEMA_VERSION = 1
CLAIM_LEASE = timedelta(minutes=2)
RESERVING_STATES = ('RESERVED', 'IN_PROGRESS', 'UNCERTAIN')


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _money(value: Decimal) -> str:
    return format(value.quantize(MONEY_UNIT), 'f')


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    ).hexdigest()


def _actor_scope(context: ExecutionContext) -> str:
    identity = str(context.principal_id) if context.principal_id is not None else context.principal_reference
    return f'{context.actor_type.value}:{identity}'


def _actor_values(context: ExecutionContext, prefix: str) -> dict[str, object]:
    return {
        f'{prefix}_actor_type': context.actor_type.value,
        f'{prefix}_actor_id': context.principal_id,
        f'{prefix}_actor_reference': context.principal_reference,
    }


def _validate_amount(value: Decimal) -> Decimal:
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite() or value <= ZERO:
        raise errors.InvalidPaymentAmountError('Payment amount must be a positive exact Decimal')
    if value != value.quantize(MONEY_UNIT):
        raise errors.InvalidPaymentAmountError('Payment amount supports at most four decimal places')
    return value


def _request_fingerprint(
    *, check_id: int, expected_version: int, expected_fingerprint: str, amount: Decimal,
    currency: str, method_category: str, payer_type: str,
    payer_diner_session_id: int | None, payer_reference: str | None,
    cash_tendered_amount: Decimal | None, executor_key: str | None,
) -> str:
    return _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'check_id': check_id,
        'check_version': expected_version,
        'check_fingerprint': expected_fingerprint,
        'amount': _money(amount),
        'currency': currency,
        'method_category': method_category,
        'payer': {
            'type': payer_type,
            'diner_session_id': payer_diner_session_id,
            'reference': payer_reference,
        },
        'cash_tendered_amount': None if cash_tendered_amount is None else _money(cash_tendered_amount),
        'executor_key': executor_key,
    })


def _translate_operational(exc: OperationalError) -> None:
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise errors.PaymentConcurrencyConflictError(
            'Concurrent payment operation lost serialization'
        ) from exc
    raise exc


async def _payment_by_key(
    db: AsyncSession, *, context: ExecutionContext, idempotency_key: str, lock: bool = False
) -> RestaurantPayment | None:
    query = select(RestaurantPayment).where(
        RestaurantPayment.tenant_id == context.tenant_id,
        RestaurantPayment.actor_scope == _actor_scope(context),
        RestaurantPayment.idempotency_key == idempotency_key,
    )
    if lock:
        query = query.with_for_update()
    return await db.scalar(query)


async def _attempts(db: AsyncSession, payment: RestaurantPayment) -> tuple[RestaurantPaymentAttempt, ...]:
    return tuple((await db.execute(
        select(RestaurantPaymentAttempt).where(
            RestaurantPaymentAttempt.tenant_id == payment.tenant_id,
            RestaurantPaymentAttempt.payment_id == payment.id,
        ).order_by(RestaurantPaymentAttempt.attempt_sequence, RestaurantPaymentAttempt.id)
    )).scalars().all())


async def _payment_projection(db: AsyncSession, payment: RestaurantPayment) -> PaymentProjection:
    attempts = await _attempts(db, payment)
    return PaymentProjection(
        id=payment.id, check_id=payment.check_id, check_version=payment.check_version,
        check_fingerprint=payment.check_fingerprint, amount=payment.amount,
        currency=payment.currency, method_category=payment.method_category,
        payer_type=payment.payer_type, payer_diner_session_id=payment.payer_diner_session_id,
        payer_reference=payment.payer_reference, state=payment.state,
        executor_key=payment.executor_key, external_reference=payment.external_reference,
        external_status=payment.external_status, instrument_brand=payment.instrument_brand,
        instrument_last_four=payment.instrument_last_four,
        instrument_display=payment.instrument_display,
        cash_tendered_amount=payment.cash_tendered_amount,
        cash_change_due=payment.cash_change_due, terminal_at=payment.terminal_at,
        attempts=tuple(PaymentAttemptProjection(
            sequence=value.attempt_sequence, attempt_type=value.attempt_type,
            executor_key=value.executor_key, actor_type=value.actor_type,
            actor_id=value.actor_id, correlation_id=value.correlation_id,
            started_at=value.started_at,
            external_call_started_at=value.external_call_started_at,
            completed_at=value.completed_at, result=value.result,
            external_reference=value.external_reference,
            external_status=value.external_status, error_code=value.error_code,
            error_message=value.error_message,
        ) for value in attempts),
    )


async def get_payment(db: AsyncSession, *, tenant_id: int, payment_id: int) -> PaymentProjection:
    payment = await db.scalar(select(RestaurantPayment).where(
        RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
    ))
    if payment is None:
        raise errors.PaymentNotFoundError()
    return await _payment_projection(db, payment)


async def _totals(
    db: AsyncSession, *, check_id: int, lock: bool = False,
) -> tuple[Decimal, Decimal, Decimal]:
    settlement_query = select(RestaurantCheckSettlement.amount).where(
        RestaurantCheckSettlement.check_id == check_id,
    ).order_by(RestaurantCheckSettlement.id)
    payment_query = select(RestaurantPayment.amount, RestaurantPayment.state).where(
        RestaurantPayment.check_id == check_id,
    ).order_by(RestaurantPayment.id)
    if lock:
        settlement_query = settlement_query.with_for_update()
        payment_query = payment_query.with_for_update()
    settlements = tuple((await db.execute(settlement_query)).scalars().all())
    payments = tuple((await db.execute(payment_query)).all())
    confirmed = sum((Decimal(value) for value in settlements), ZERO)
    reserved = sum((Decimal(value.amount) for value in payments if value.state in RESERVING_STATES), ZERO)
    uncertain = sum((Decimal(value.amount) for value in payments if value.state == 'UNCERTAIN'), ZERO)
    return confirmed, reserved, uncertain


async def get_check_settlement(
    db: AsyncSession, *, tenant_id: int, check_id: int,
    owner_diner_session_id: int | None = None,
) -> CheckSettlementProjection:
    check = await db.scalar(select(RestaurantCheck).where(
        RestaurantCheck.id == check_id, RestaurantCheck.tenant_id == tenant_id,
    ))
    if check is None:
        raise errors.CheckNotPayableError('Restaurant Check was not found')
    if owner_diner_session_id is not None:
        member = await db.scalar(select(RestaurantCheckMember.id).where(
            RestaurantCheckMember.check_id == check.id,
            RestaurantCheckMember.tenant_id == tenant_id,
            RestaurantCheckMember.diner_session_id == owner_diner_session_id,
        ))
        if member is None:
            raise errors.PaymentNotFoundError()
    rows = tuple((await db.execute(select(RestaurantPayment).where(
        RestaurantPayment.check_id == check.id,
        RestaurantPayment.tenant_id == tenant_id,
    ).order_by(RestaurantPayment.id))).scalars().all())
    confirmed, reserved, uncertain = await _totals(db, check_id=check.id)
    return CheckSettlementProjection(
        check_id=check.id, check_status=check.status, check_version=check.version,
        check_fingerprint=check.current_fingerprint, liability_total=check.liability_total,
        currency=check.currency, confirmed_settlement=confirmed,
        reserved_financial_exposure=reserved, uncertain_exposure=uncertain,
        available_to_initiate=max(ZERO, check.liability_total - confirmed - reserved),
        payments=tuple([await _payment_projection(db, value) for value in rows]),
    )


async def _authorize_and_freeze(
    db: AsyncSession, *, check: RestaurantCheck, context: ExecutionContext,
) -> tuple[RestaurantCheckMember, ...]:
    members = tuple((await db.execute(select(RestaurantCheckMember).where(
        RestaurantCheckMember.check_id == check.id,
        RestaurantCheckMember.active_slot == 1,
    ).order_by(RestaurantCheckMember.diner_session_id).with_for_update())).scalars().all())
    if not members:
        raise errors.CheckNotPayableError('Restaurant Check has no active members')
    if context.actor_type is ActorType.DINER and context.principal_id not in {
        value.diner_session_id for value in members
    }:
        raise errors.PaymentPermissionError()
    if context.actor_type not in (ActorType.EMPLOYEE, ActorType.DINER):
        raise errors.PaymentPermissionError()
    if check.status == 'OPEN':
        _, diners, _ = await check_service._lock_diners(
            db, tenant_id=check.tenant_id,
            diner_ids=tuple(value.diner_session_id for value in members),
        )
        await check_service._validate_drafts(db, diners)
        await check_service._verify_complete(db, check)
        check.status = 'FROZEN'
        check.frozen_at = _now()
        for key, value in _actor_values(context, 'frozen').items():
            setattr(check, key, value)
    elif check.status != 'FROZEN':
        raise errors.CheckNotPayableError(f'Restaurant Check in {check.status} is not payable')
    return members


async def _finalize_full_check(
    db: AsyncSession, *, check: RestaurantCheck, context: ExecutionContext,
    settlement_reference: str, now: datetime,
) -> None:
    members = tuple((await db.execute(select(RestaurantCheckMember).where(
        RestaurantCheckMember.check_id == check.id,
        RestaurantCheckMember.active_slot == 1,
    ).order_by(RestaurantCheckMember.diner_session_id).with_for_update())).scalars().all())
    session_ids = tuple(sorted({value.service_session_id for value in members}))
    if session_ids:
        await db.execute(select(RestaurantServiceSession).where(
            RestaurantServiceSession.tenant_id == check.tenant_id,
            RestaurantServiceSession.id.in_(session_ids),
        ).order_by(RestaurantServiceSession.id).with_for_update())
        await db.execute(select(DinerSession).where(
            DinerSession.tenant_id == check.tenant_id,
            DinerSession.id.in_(tuple(value.diner_session_id for value in members)),
        ).order_by(DinerSession.id).with_for_update())
    allocations = tuple((await db.execute(select(RestaurantCheckAllocation).where(
        RestaurantCheckAllocation.check_id == check.id,
        RestaurantCheckAllocation.ownership_slot == 1,
    ).order_by(RestaurantCheckAllocation.id).with_for_update())).scalars().all())
    if any(value.state != 'CLAIMED' for value in allocations):
        raise errors.DuplicateSettlementError('Check allocations are not claimable for final settlement')
    check.status = 'SETTLED'
    check.settled_at = now
    check.continuation_decision = 'PENDING'
    for key, value in _actor_values(context, 'settled').items():
        setattr(check, key, value)
    for allocation in allocations:
        allocation.state = 'SETTLED'
        allocation.settled_at = now
        allocation.settlement_reference = settlement_reference
    table_scopes = tuple((await db.execute(select(RestaurantCheckTableScope).where(
        RestaurantCheckTableScope.check_id == check.id,
        RestaurantCheckTableScope.active_slot == 1,
    ).order_by(RestaurantCheckTableScope.service_session_id).with_for_update())).scalars().all())
    for table_scope in table_scopes:
        table_scope.lock_phase = 'CONTINUATION'


async def _apply_success(
    db: AsyncSession, *, payment: RestaurantPayment, check: RestaurantCheck,
    context: ExecutionContext, now: datetime,
) -> None:
    existing = await db.scalar(select(RestaurantCheckSettlement).where(
        RestaurantCheckSettlement.payment_id == payment.id,
    ))
    if existing is not None:
        if payment.state != 'SUCCEEDED':
            raise errors.DuplicateSettlementError()
        return
    confirmed, _, _ = await _totals(db, check_id=check.id, lock=True)
    if confirmed + payment.amount > check.liability_total:
        raise errors.PaymentAmountExceedsAvailableError('Settlement would exceed check liability')
    settlement = RestaurantCheckSettlement(
        tenant_id=payment.tenant_id, organization_id=payment.organization_id,
        location_id=payment.location_id, check_id=payment.check_id,
        payment_id=payment.id, amount=payment.amount, currency=payment.currency,
        application_actor_type=context.actor_type.value,
        application_actor_id=context.principal_id,
        application_actor_reference=context.principal_reference, applied_at=now,
    )
    db.add(settlement)
    payment.state = 'SUCCEEDED'
    payment.terminal_at = now
    if confirmed + payment.amount == check.liability_total:
        _, reserved, _ = await _totals(db, check_id=check.id, lock=True)
        if reserved != ZERO:
            raise errors.PaymentConcurrencyConflictError(
                'Full settlement cannot complete while other financial exposure remains'
            )
        await _finalize_full_check(
            db, check=check, context=context,
            settlement_reference=f'PAYMENT:{payment.id}', now=now,
        )


def _copy_evidence(payment: RestaurantPayment, result: PaymentExecutionResult | PaymentRecoveryResult) -> None:
    payment.external_reference = result.external_reference
    payment.external_status = result.external_status
    payment.instrument_brand = result.instrument_brand
    payment.instrument_last_four = result.instrument_last_four
    payment.instrument_display = result.instrument_display
    payment.last_error_code = result.error_code
    payment.last_error_message = result.error_message


async def _claim(
    db: AsyncSession, *, tenant_id: int, payment_id: int, context: ExecutionContext,
    attempt_type: str, allowed_states: tuple[str, ...], reserve_again: bool = False,
) -> tuple[RestaurantPayment, str]:
    try:
        payment_identity = await db.scalar(select(RestaurantPayment.check_id).where(
            RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
        ))
        if payment_identity is None:
            raise errors.PaymentNotFoundError()
        check = await db.scalar(select(RestaurantCheck).where(
            RestaurantCheck.id == payment_identity, RestaurantCheck.tenant_id == tenant_id,
        ).with_for_update())
        payment = await db.scalar(select(RestaurantPayment).where(
            RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
        ).with_for_update())
        if payment is None:
            raise errors.PaymentNotFoundError()
        if payment.state == 'SUCCEEDED':
            await db.commit()
            return payment, ''
        if payment.state not in allowed_states:
            raise errors.PaymentStateConflictError(
                f'Payment in {payment.state} cannot start {attempt_type.lower()}'
            )
        if reserve_again:
            confirmed, reserved, _ = await _totals(db, check_id=check.id, lock=True)
            if payment.amount > check.liability_total - confirmed - reserved:
                raise errors.PaymentAmountExceedsAvailableError()
        token = str(uuid4())
        now = _now()
        payment.state = 'IN_PROGRESS'
        payment.claim_token = token
        payment.claim_expires_at = now + CLAIM_LEASE
        payment.attempt_count += 1
        payment.last_error_code = None
        payment.last_error_message = None
        payment.terminal_at = None
        db.add(RestaurantPaymentAttempt(
            tenant_id=payment.tenant_id, payment_id=payment.id,
            attempt_sequence=payment.attempt_count, attempt_type=attempt_type,
            executor_key=payment.executor_key, claim_token=token,
            actor_type=context.actor_type.value, actor_id=context.principal_id,
            actor_reference=context.principal_reference,
            correlation_id=context.correlation_id, causation_id=context.causation_id,
            started_at=now, external_call_started_at=now,
            completed_at=None, result='IN_PROGRESS',
        ))
        await db.commit()
        return payment, token
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise


async def _finish(
    db: AsyncSession, *, tenant_id: int, payment_id: int, token: str,
    context: ExecutionContext, result: PaymentExecutionResult | PaymentRecoveryResult,
    state: str,
) -> RestaurantPayment:
    try:
        check_id = await db.scalar(select(RestaurantPayment.check_id).where(
            RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
        ))
        if check_id is None:
            raise errors.PaymentNotFoundError()
        check = await db.scalar(select(RestaurantCheck).where(
            RestaurantCheck.id == check_id, RestaurantCheck.tenant_id == tenant_id,
        ).with_for_update())
        payment = await db.scalar(select(RestaurantPayment).where(
            RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
        ).with_for_update())
        if payment.claim_token != token:
            await db.rollback()
            winner = await db.scalar(select(RestaurantPayment).where(
                RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
            ))
            if winner is None:
                raise errors.PaymentNotFoundError()
            return winner
        attempt = await db.scalar(select(RestaurantPaymentAttempt).where(
            RestaurantPaymentAttempt.payment_id == payment.id,
            RestaurantPaymentAttempt.claim_token == token,
        ).with_for_update())
        if attempt is None or attempt.result != 'IN_PROGRESS':
            raise errors.PaymentStaleResultError()
        now = _now()
        payment.state = state
        payment.claim_token = None
        payment.claim_expires_at = None
        _copy_evidence(payment, result)
        if state == 'SUCCEEDED':
            await _apply_success(db, payment=payment, check=check, context=context, now=now)
        else:
            if state in ('FAILED', 'REJECTED', 'CANCELLED'):
                payment.terminal_at = now
        attempt.result = state
        attempt.completed_at = now
        attempt.external_reference = result.external_reference
        attempt.external_status = result.external_status
        attempt.error_code = result.error_code
        attempt.error_message = result.error_message
        attempt.result_fingerprint = _sha({
            'result': state, 'external_reference': result.external_reference,
            'external_status': result.external_status, 'error_code': result.error_code,
        })
        await db.commit()
        return payment
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise


def _execution_state(result: PaymentExecutionResult) -> str:
    return {
        PaymentExecutionOutcome.SUCCEEDED: 'SUCCEEDED',
        PaymentExecutionOutcome.DEFINITE_FAILURE: 'FAILED',
        PaymentExecutionOutcome.REJECTED: 'REJECTED',
        PaymentExecutionOutcome.UNCERTAIN: 'UNCERTAIN',
    }[result.outcome]


def _recovery_state(result: PaymentRecoveryResult) -> str:
    return {
        PaymentRecoveryOutcome.CONFIRMED_SUCCESS: 'SUCCEEDED',
        PaymentRecoveryOutcome.DEFINITE_ABSENCE: 'FAILED',
        PaymentRecoveryOutcome.DEFINITE_FAILURE: 'FAILED',
        PaymentRecoveryOutcome.STILL_UNCERTAIN: 'UNCERTAIN',
    }[result.outcome]


async def _execute_claimed(
    db: AsyncSession, *, payment: RestaurantPayment, token: str,
    context: ExecutionContext, executor: object | None,
    credential: EphemeralExecutionCredential | None,
) -> PaymentProjection:
    if executor is None or not isinstance(executor, PaymentExecutionPort):
        result = PaymentExecutionResult(
            outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
            error_code=errors.UnsupportedExecutionCapabilityError.code,
            error_message='Configured payment executor is unavailable',
        )
    elif credential is None:
        result = PaymentExecutionResult(
            outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
            error_code=errors.SensitiveCredentialMisuseError.code,
            error_message='Ephemeral execution credential is required',
        )
    else:
        request = PaymentExecutionRequest(
            operation_reference=str(payment.id), amount=payment.amount,
            currency=payment.currency, method_category=payment.method_category,
            idempotency_key=payment.provider_idempotency_key,
            request_fingerprint=payment.request_fingerprint,
        )
        try:
            result = await executor.execute(request=request, credential=credential)
        except Exception as exc:
            result = PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.UNCERTAIN,
                error_code='PAYMENT_EXECUTION_RESULT_UNCERTAIN',
                error_message=f'Unexpected failure after payment call boundary: {type(exc).__name__}',
            )
    finished = await _finish(
        db, tenant_id=payment.tenant_id, payment_id=payment.id, token=token,
        context=context, result=result, state=_execution_state(result),
    )
    return await _payment_projection(db, finished)


async def initiate_payment(
    db: AsyncSession, *, context: ExecutionContext, check_id: int,
    expected_check_version: int, expected_check_fingerprint: str,
    amount: Decimal, currency: str, method_category: str,
    payer_type: str, payer_diner_session_id: int | None,
    payer_reference: str | None, cash_tendered_amount: Decimal | None,
    executor_key: str | None, idempotency_key: str,
    executors: Mapping[str, object], credential: EphemeralExecutionCredential | None,
) -> tuple[PaymentProjection, bool]:
    amount = _validate_amount(amount)
    currency = currency.strip().upper()
    method_category = method_category.strip().upper()
    payer_type = payer_type.strip().upper()
    payer_reference = payer_reference.strip() if payer_reference else None
    executor_key = executor_key.strip() if executor_key else None
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise errors.InvalidPaymentAmountError('Currency must be a three-letter ASCII code')
    if method_category not in ('CASH', 'CARD', 'TRANSFER'):
        raise errors.UnsupportedExecutionCapabilityError('Unsupported payment method category')
    if payer_type not in ('DINER', 'OTHER'):
        raise errors.PaymentPermissionError('Unsupported payer identity type')
    if (payer_type == 'DINER') != (payer_diner_session_id is not None):
        raise errors.PaymentPermissionError('Diner payer identity is incomplete')
    if payer_type == 'OTHER' and not payer_reference:
        raise errors.PaymentPermissionError('Other payer reference is required')
    if method_category == 'CASH':
        if context.actor_type is not ActorType.EMPLOYEE:
            raise errors.PaymentPermissionError('Only authorized staff may confirm physical cash receipt')
        if executor_key is not None or credential is not None:
            raise errors.SensitiveCredentialMisuseError('Cash payment cannot carry execution credentials')
        if cash_tendered_amount is None:
            raise errors.InvalidCashTenderError()
        cash_tendered_amount = _validate_amount(cash_tendered_amount)
        if cash_tendered_amount < amount:
            raise errors.InvalidCashTenderError('Cash tender must cover the settlement amount')
    elif not executor_key:
        raise errors.UnsupportedExecutionCapabilityError('Electronic payment requires an executor key')
    elif cash_tendered_amount is not None:
        raise errors.InvalidCashTenderError('Electronic payment cannot include cash tender evidence')

    fingerprint = _request_fingerprint(
        check_id=check_id, expected_version=expected_check_version,
        expected_fingerprint=expected_check_fingerprint, amount=amount,
        currency=currency, method_category=method_category, payer_type=payer_type,
        payer_diner_session_id=payer_diner_session_id, payer_reference=payer_reference,
        cash_tendered_amount=cash_tendered_amount, executor_key=executor_key,
    )
    existing = await _payment_by_key(db, context=context, idempotency_key=idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise errors.PaymentIdempotencyConflictError()
        return await _payment_projection(db, existing), True

    try:
        check = await db.scalar(select(RestaurantCheck).where(
            RestaurantCheck.id == check_id, RestaurantCheck.tenant_id == context.tenant_id,
        ).with_for_update())
        if check is None:
            raise errors.CheckNotPayableError('Restaurant Check was not found')
        replay = await _payment_by_key(db, context=context, idempotency_key=idempotency_key, lock=True)
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise errors.PaymentIdempotencyConflictError()
            await db.commit()
            return await _payment_projection(db, replay), True
        if check.version != expected_check_version or check.current_fingerprint != expected_check_fingerprint:
            raise errors.CheckFinancialIdentityConflictError()
        if check.currency != currency:
            raise errors.CheckFinancialIdentityConflictError('Payment currency differs from check currency')
        members = await _authorize_and_freeze(db, check=check, context=context)
        if payer_type == 'DINER' and payer_diner_session_id not in {
            value.diner_session_id for value in members
        }:
            raise errors.PaymentPermissionError('Diner payer does not participate in this check')
        confirmed, reserved, _ = await _totals(db, check_id=check.id, lock=True)
        available = check.liability_total - confirmed - reserved
        if amount > available:
            raise errors.PaymentAmountExceedsAvailableError()
        now = _now()
        payment = RestaurantPayment(
            tenant_id=check.tenant_id, organization_id=check.organization_id,
            location_id=check.location_id, check_id=check.id,
            check_version=check.version, check_fingerprint=check.current_fingerprint,
            amount=amount, currency=currency, method_category=method_category,
            payer_type=payer_type, payer_diner_session_id=payer_diner_session_id,
            payer_reference=payer_reference,
            initiated_actor_type=context.actor_type.value,
            initiated_actor_id=context.principal_id,
            initiated_actor_reference=context.principal_reference,
            actor_scope=_actor_scope(context), idempotency_key=idempotency_key,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=fingerprint, state='RESERVED', executor_key=executor_key,
            provider_idempotency_key=(
                None if method_category == 'CASH' else
                f'payment-v1:{context.tenant_id}:{fingerprint[:32]}:{_sha([_actor_scope(context), idempotency_key])[:16]}'
            ),
            cash_tendered_amount=cash_tendered_amount,
            cash_change_due=(None if cash_tendered_amount is None else cash_tendered_amount - amount),
            attempt_count=0,
        )
        db.add(payment)
        await db.flush()
        if method_category == 'CASH':
            await _apply_success(db, payment=payment, check=check, context=context, now=now)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        winner = await _payment_by_key(db, context=context, idempotency_key=idempotency_key)
        if winner is None:
            raise
        if winner.request_fingerprint != fingerprint:
            raise errors.PaymentIdempotencyConflictError() from exc
        return await _payment_projection(db, winner), True
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise

    if method_category == 'CASH':
        return await _payment_projection(db, payment), False
    claimed, token = await _claim(
        db, tenant_id=context.tenant_id, payment_id=payment.id, context=context,
        attempt_type='EXECUTE', allowed_states=('RESERVED',),
    )
    if not token:
        return await _payment_projection(db, claimed), True
    return await _execute_claimed(
        db, payment=claimed, token=token, context=context,
        executor=executors.get(claimed.executor_key), credential=credential,
    ), False


async def retry_payment(
    db: AsyncSession, *, context: ExecutionContext, payment_id: int,
    executors: Mapping[str, object], credential: EphemeralExecutionCredential | None,
) -> PaymentProjection:
    claimed, token = await _claim(
        db, tenant_id=context.tenant_id, payment_id=payment_id, context=context,
        attempt_type='RETRY', allowed_states=('FAILED',), reserve_again=True,
    )
    if not token:
        return await _payment_projection(db, claimed)
    return await _execute_claimed(
        db, payment=claimed, token=token, context=context,
        executor=executors.get(claimed.executor_key), credential=credential,
    )


async def recover_payment(
    db: AsyncSession, *, context: ExecutionContext, payment_id: int,
    executors: Mapping[str, object],
) -> PaymentProjection:
    payment = await db.scalar(select(RestaurantPayment).where(
        RestaurantPayment.id == payment_id,
        RestaurantPayment.tenant_id == context.tenant_id,
    ).with_for_update())
    if payment is None:
        raise errors.PaymentNotFoundError()
    attempt_type = 'RECOVER'
    if payment.state == 'IN_PROGRESS':
        if payment.claim_expires_at is not None and payment.claim_expires_at > _now():
            raise errors.PaymentStateConflictError('Active payment execution claim has not expired')
        previous = await db.scalar(select(RestaurantPaymentAttempt).where(
            RestaurantPaymentAttempt.payment_id == payment.id,
            RestaurantPaymentAttempt.claim_token == payment.claim_token,
        ).with_for_update())
        if previous is not None and previous.result == 'IN_PROGRESS':
            previous.result = 'FENCED'
            previous.completed_at = _now()
            previous.error_code = 'PAYMENT_STALE_ATTEMPT_FENCED'
            previous.error_message = 'Expired attempt fenced before recovery'
        payment.state = 'UNCERTAIN'
        payment.claim_token = None
        payment.claim_expires_at = None
        attempt_type = 'STALE_RECOVERY'
        await db.commit()
    elif payment.state != 'UNCERTAIN':
        current_state = payment.state
        await db.rollback()
        raise errors.PaymentStateConflictError(
            f'Payment in {current_state} does not require recovery'
        )
    else:
        await db.commit()

    claimed, token = await _claim(
        db, tenant_id=context.tenant_id, payment_id=payment_id, context=context,
        attempt_type=attempt_type, allowed_states=('UNCERTAIN',),
    )
    executor = executors.get(claimed.executor_key)
    if executor is None or not isinstance(executor, PaymentRecoveryPort):
        result = PaymentRecoveryResult(
            outcome=PaymentRecoveryOutcome.STILL_UNCERTAIN,
            error_code=errors.RecoveryUnavailableError.code,
            error_message='Configured executor has no recovery capability',
        )
    else:
        request = PaymentRecoveryRequest(
            operation_reference=str(claimed.id),
            idempotency_key=claimed.provider_idempotency_key,
            request_fingerprint=claimed.request_fingerprint,
        )
        try:
            result = await executor.recover(request=request)
        except Exception as exc:
            result = PaymentRecoveryResult(
                outcome=PaymentRecoveryOutcome.STILL_UNCERTAIN,
                error_code='PAYMENT_RECOVERY_RESULT_UNCERTAIN',
                error_message=f'Unexpected recovery failure: {type(exc).__name__}',
            )
    finished = await _finish(
        db, tenant_id=context.tenant_id, payment_id=payment_id, token=token,
        context=context, result=result, state=_recovery_state(result),
    )
    return await _payment_projection(db, finished)
