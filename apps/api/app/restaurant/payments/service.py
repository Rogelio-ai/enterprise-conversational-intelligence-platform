from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    CashMovement,
    CashSession,
    Location,
    Resource,
    RestaurantCheck,
    RestaurantCheckAllocation,
    RestaurantCheckMember,
    RestaurantCheckSettlement,
    RestaurantCheckTableScope,
    LocationPaymentExecutorConfiguration,
    RestaurantPayment,
    RestaurantPaymentAttempt,
    RestaurantServiceSession,
    DinerSession,
)
from app.restaurant.checks import service as check_service
from app.restaurant.integrations.payments.contracts import (
    EphemeralCustomerPaymentSource,
    EphemeralMerchantCredential,
    PaymentExecutionOutcome,
    PaymentExecutionRequest,
    PaymentExecutionResult,
    PaymentRecoveryOutcome,
    PaymentRecoveryRequest,
    PaymentRecoveryResult,
)
from app.restaurant.integrations.payments.credentials import (
    MerchantCredentialContext,
    MerchantCredentialResolver,
)
from app.restaurant.integrations.payments.observability import (
    PAYMENT_EXECUTION_DURATION_SECONDS,
    PAYMENT_EXECUTION_TOTAL,
    PAYMENT_RECOVERY_TOTAL,
)
from app.restaurant.integrations.payments.ports import PaymentExecutionPort, PaymentRecoveryPort
from app.restaurant.integrations.payments.registry import PaymentExecutorRegistry
from app.restaurant.integrations.payments.resolver import (
    PaymentExecutorResolver,
    PaymentExecutorSelectionMode,
    ResolvedPaymentExecutor,
)
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
logger = logging.getLogger('ecip.restaurant_payments')


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
    cash_tendered_amount: Decimal | None, cash_session_id: int | None,
    executor_key: str | None,
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
        'cash_session_id': cash_session_id,
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


async def _cash_session_for_payment(
    db: AsyncSession, *, check: RestaurantCheck, currency: str,
    cash_session_id: int | None,
) -> CashSession | None:
    location = await db.scalar(select(Location).where(
        Location.id == check.location_id,
        Location.tenant_id == check.tenant_id,
        Location.organization_id == check.organization_id,
    ).with_for_update())
    if location is None:
        raise errors.CheckNotPayableError('Restaurant Check location was not found')
    if location.cash_management_activated_at is None:
        return None
    if cash_session_id is None:
        raise errors.CashSessionRequiredError(
            'Cash Management is active and requires an OPEN CashSession'
        )
    session = await db.scalar(select(CashSession).where(
        CashSession.id == cash_session_id,
        CashSession.tenant_id == check.tenant_id,
    ).with_for_update())
    if session is None:
        raise errors.CashSessionNotFoundError()
    if (
        session.organization_id != check.organization_id
        or session.location_id != check.location_id
    ):
        raise errors.InvalidCashSessionError(
            'CashSession does not belong to the Restaurant Check location'
        )
    if session.status != 'OPEN':
        raise errors.InvalidCashSessionError('CashSession is not OPEN')
    if session.currency != currency:
        raise errors.InvalidCashSessionError(
            'CashSession currency differs from payment currency'
        )
    resource_type = await db.scalar(select(Resource.resource_type).where(
        Resource.id == session.resource_id,
        Resource.tenant_id == session.tenant_id,
        Resource.location_id == session.location_id,
    ))
    if resource_type != 'CASH_REGISTER':
        raise errors.InvalidCashSessionError(
            'CashSession does not belong to a CASH_REGISTER'
        )
    return session


def _record_cash_payment_movements(
    db: AsyncSession, *, session: CashSession, payment: RestaurantPayment,
    context: ExecutionContext, now: datetime,
) -> None:
    evidence = [('CUSTOMER_TENDER', payment.cash_tendered_amount)]
    if payment.cash_change_due is not None and payment.cash_change_due > ZERO:
        evidence.append(('CUSTOMER_CHANGE', -payment.cash_change_due))
    for movement_type, amount in evidence:
        assert amount is not None
        movement = CashMovement(
            tenant_id=session.tenant_id,
            organization_id=session.organization_id,
            location_id=session.location_id,
            cash_session_id=session.id,
            restaurant_payment_id=payment.id,
            movement_type=movement_type,
            amount=amount,
            currency=session.currency,
            reason=(
                'Customer cash tender'
                if movement_type == 'CUSTOMER_TENDER'
                else 'Customer cash change'
            ),
            reference=f'PAYMENT:{payment.id}',
            recorded_at=now,
            actor_type=context.actor_type.value,
            actor_id=context.principal_id,
            actor_reference=context.principal_reference,
            authorized_by_actor_type=context.actor_type.value,
            authorized_by_actor_id=context.principal_id,
            authorized_by_actor_reference=context.principal_reference,
            opening_float_slot=None,
            idempotency_actor_scope=f'PAYMENT:{payment.id}',
            idempotency_key=movement_type,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=_sha({
                'payment_request_fingerprint': payment.request_fingerprint,
                'movement_type': movement_type,
                'amount': _money(amount),
            }),
        )
        db.add(movement)
        session.movement_version += 1


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
        ).with_for_update().execution_options(populate_existing=True))
        payment = await db.scalar(select(RestaurantPayment).where(
            RestaurantPayment.id == payment_id, RestaurantPayment.tenant_id == tenant_id,
        ).with_for_update().execution_options(populate_existing=True))
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
        attempt_external_reference = result.external_reference
        if (
            state == 'SUCCEEDED'
            and result.external_reference is not None
            and payment.executor_configuration_id is not None
        ):
            await db.scalar(select(LocationPaymentExecutorConfiguration.id).where(
                LocationPaymentExecutorConfiguration.id
                == payment.executor_configuration_id,
                LocationPaymentExecutorConfiguration.tenant_id == payment.tenant_id,
                LocationPaymentExecutorConfiguration.organization_id
                == payment.organization_id,
                LocationPaymentExecutorConfiguration.location_id == payment.location_id,
            ).with_for_update())
            duplicate_payment_id = await db.scalar(select(RestaurantPayment.id).where(
                RestaurantPayment.executor_configuration_id
                == payment.executor_configuration_id,
                RestaurantPayment.external_reference == result.external_reference,
                RestaurantPayment.id != payment.id,
            ).with_for_update())
            if duplicate_payment_id is not None:
                state = 'UNCERTAIN'
                updates = {
                    'external_reference': None,
                    'error_code': 'PAYMENT_EXTERNAL_REFERENCE_CONFLICT',
                    'error_message': (
                        'Provider transaction identity is already associated '
                        'with another payment'
                    ),
                }
                if isinstance(result, PaymentExecutionResult):
                    updates['outcome'] = PaymentExecutionOutcome.UNCERTAIN
                else:
                    updates['outcome'] = PaymentRecoveryOutcome.STILL_UNCERTAIN
                result = result.model_copy(update=updates)
                logger.warning(
                    'Duplicate provider transaction identity preserved as uncertain',
                    extra={
                        'event': 'payment_external_reference_conflict',
                        'operation': 'finalize',
                        'tenant_id': payment.tenant_id,
                        'organization_id': payment.organization_id,
                        'location_id': payment.location_id,
                        'payment_id': payment.id,
                        'executor_key': payment.executor_key,
                        'method': payment.method_category,
                        'currency': payment.currency,
                        'payment_state': payment.state,
                        'attempt_number': payment.attempt_count,
                        'correlation_id': context.correlation_id,
                        'outcome': 'UNCERTAIN',
                    },
                )
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
        attempt.external_reference = attempt_external_reference
        attempt.external_status = result.external_status
        attempt.error_code = result.error_code
        attempt.error_message = result.error_message
        attempt.result_fingerprint = _sha({
            'result': state, 'external_reference': attempt_external_reference,
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


async def _historical_executor(
    db: AsyncSession,
    *,
    payment: RestaurantPayment,
    registry: PaymentExecutorRegistry,
) -> ResolvedPaymentExecutor:
    if payment.executor_configuration_id is None:
        raise errors.PaymentExecutorConfigurationNotFoundError(
            'Payment has no durable executor configuration identity'
        )
    try:
        resolved = await PaymentExecutorResolver(db, registry).resolve_historical(
            tenant_id=payment.tenant_id,
            organization_id=payment.organization_id,
            location_id=payment.location_id,
            executor_configuration_id=payment.executor_configuration_id,
        )
        await db.commit()
        return resolved
    except (
        errors.PaymentExecutorRegistryError,
        errors.PaymentExecutorResolutionError,
    ):
        await db.commit()
        raise
    except Exception:
        await db.rollback()
        raise


async def _execution_executor(
    db: AsyncSession,
    *,
    payment: RestaurantPayment,
    registry: PaymentExecutorRegistry,
) -> ResolvedPaymentExecutor:
    if payment.executor_configuration_id is None:
        raise errors.PaymentExecutorConfigurationNotFoundError(
            'Payment has no durable executor configuration identity'
        )
    try:
        resolved = await PaymentExecutorResolver(db, registry).resolve_for_execution(
            tenant_id=payment.tenant_id,
            organization_id=payment.organization_id,
            location_id=payment.location_id,
            executor_configuration_id=payment.executor_configuration_id,
            method_category=payment.method_category,
            currency=payment.currency,
        )
        await db.commit()
        return resolved
    except (
        errors.PaymentExecutorRegistryError,
        errors.PaymentExecutorResolutionError,
    ):
        await db.commit()
        raise
    except Exception:
        await db.rollback()
        raise


async def _merchant_credential(
    *,
    payment: RestaurantPayment,
    configuration: LocationPaymentExecutorConfiguration,
    resolver: MerchantCredentialResolver | None,
) -> EphemeralMerchantCredential | None:
    if configuration.credential_binding is None:
        return None
    if resolver is None or not isinstance(resolver, MerchantCredentialResolver):
        raise errors.MerchantCredentialResolutionError(
            'Merchant credential resolver is unavailable'
        )
    context = MerchantCredentialContext(
        tenant_id=configuration.tenant_id,
        organization_id=configuration.organization_id,
        location_id=configuration.location_id,
        executor_configuration_id=configuration.id,
        adapter_kind=configuration.adapter_kind,
        credential_binding=configuration.credential_binding,
        operation_reference=str(payment.id),
    )
    try:
        credential = await resolver.resolve(context=context)
    except errors.MerchantCredentialResolutionError:
        raise
    except Exception as exc:
        raise errors.MerchantCredentialResolutionError(
            'Merchant credential resolution failed'
        ) from exc
    if not isinstance(credential, EphemeralMerchantCredential):
        raise errors.MerchantCredentialResolutionError(
            'Merchant credential resolver returned an invalid result'
        )
    return credential


async def _execute_claimed(
    db: AsyncSession, *, payment: RestaurantPayment, token: str,
    context: ExecutionContext, executor_registry: PaymentExecutorRegistry,
    credential_resolver: MerchantCredentialResolver | None,
    customer_payment_source: EphemeralCustomerPaymentSource | None,
) -> PaymentProjection:
    try:
        resolved = await _execution_executor(
            db, payment=payment, registry=executor_registry
        )
    except (errors.PaymentExecutorRegistryError, errors.PaymentExecutorResolutionError) as exc:
        logger.warning(
            'Durably selected payment executor is unavailable',
            extra={
                'event': 'payment_executor_unavailable',
                'operation': 'execute',
                'tenant_id': payment.tenant_id,
                'organization_id': payment.organization_id,
                'location_id': payment.location_id,
                'payment_id': payment.id,
                'executor_key': payment.executor_key,
                'method': payment.method_category,
                'currency': payment.currency,
                'payment_state': payment.state,
                'attempt_number': payment.attempt_count,
                'correlation_id': context.correlation_id,
                'outcome': exc.code,
            },
        )
        result = PaymentExecutionResult(
            outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
            error_code=exc.code,
            error_message='Durably selected payment executor is unavailable',
        )
    else:
        executor = resolved.executor
        if not isinstance(executor, PaymentExecutionPort):
            logger.warning(
                'Configured payment executor cannot execute payments',
                extra={
                    'event': 'payment_executor_unavailable',
                    'operation': 'execute',
                    'tenant_id': payment.tenant_id,
                    'organization_id': payment.organization_id,
                    'location_id': payment.location_id,
                    'payment_id': payment.id,
                    'executor_key': resolved.configuration.executor_key,
                    'adapter_kind': resolved.configuration.adapter_kind,
                    'method': payment.method_category,
                    'currency': payment.currency,
                    'payment_state': payment.state,
                    'attempt_number': payment.attempt_count,
                    'correlation_id': context.correlation_id,
                    'outcome': errors.UnsupportedExecutionCapabilityError.code,
                },
            )
            result = PaymentExecutionResult(
                outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
                error_code=errors.UnsupportedExecutionCapabilityError.code,
                error_message='Configured payment executor cannot execute payments',
            )
        else:
            try:
                merchant_credential = await _merchant_credential(
                    payment=payment,
                    configuration=resolved.configuration,
                    resolver=credential_resolver,
                )
            except errors.MerchantCredentialResolutionError as exc:
                logger.warning(
                    'Merchant credential resolution prevented payment execution',
                    extra={
                        'event': 'payment_executor_unavailable',
                        'operation': 'credential_resolution',
                        'tenant_id': payment.tenant_id,
                        'organization_id': payment.organization_id,
                        'location_id': payment.location_id,
                        'payment_id': payment.id,
                        'executor_key': resolved.configuration.executor_key,
                        'adapter_kind': resolved.configuration.adapter_kind,
                        'method': payment.method_category,
                        'currency': payment.currency,
                        'payment_state': payment.state,
                        'attempt_number': payment.attempt_count,
                        'correlation_id': context.correlation_id,
                        'outcome': exc.code,
                    },
                )
                result = PaymentExecutionResult(
                    outcome=PaymentExecutionOutcome.DEFINITE_FAILURE,
                    error_code=exc.code,
                    error_message='Merchant credential could not be resolved',
                )
            else:
                request = PaymentExecutionRequest(
                    operation_reference=str(payment.id), amount=payment.amount,
                    currency=payment.currency, method_category=payment.method_category,
                    idempotency_key=payment.provider_idempotency_key,
                    request_fingerprint=payment.request_fingerprint,
                )
                log_context = {
                    'tenant_id': payment.tenant_id,
                    'organization_id': payment.organization_id,
                    'location_id': payment.location_id,
                    'payment_id': payment.id,
                    'executor_key': resolved.configuration.executor_key,
                    'adapter_kind': resolved.configuration.adapter_kind,
                    'topology': resolved.configuration.topology,
                    'method': payment.method_category,
                    'currency': payment.currency,
                    'payment_state': payment.state,
                    'attempt_number': payment.attempt_count,
                    'correlation_id': context.correlation_id,
                }
                logger.info(
                    'Payment execution started',
                    extra={
                        'event': 'payment_execution_started',
                        'operation': 'execute',
                        **log_context,
                    },
                )
                started = perf_counter()
                try:
                    result = await executor.execute(
                        request=request,
                        merchant_credential=merchant_credential,
                        customer_payment_source=customer_payment_source,
                    )
                except Exception as exc:
                    result = PaymentExecutionResult(
                        outcome=PaymentExecutionOutcome.UNCERTAIN,
                        error_code='PAYMENT_EXECUTION_RESULT_UNCERTAIN',
                        error_message=(
                            'Unexpected failure after payment call boundary: '
                            f'{type(exc).__name__}'
                        ),
                    )
                duration = perf_counter() - started
                outcome = result.outcome.value
                PAYMENT_EXECUTION_TOTAL.labels(
                    method=payment.method_category,
                    outcome=outcome,
                    adapter_kind=resolved.configuration.adapter_kind,
                    topology=resolved.configuration.topology,
                ).inc()
                PAYMENT_EXECUTION_DURATION_SECONDS.labels(
                    method=payment.method_category,
                    outcome=outcome,
                    adapter_kind=resolved.configuration.adapter_kind,
                    topology=resolved.configuration.topology,
                ).observe(duration)
                logger.info(
                    'Payment execution completed',
                    extra={
                        'event': 'payment_execution_completed',
                        'operation': 'execute',
                        **log_context,
                        'outcome': outcome,
                        'duration_ms': round(duration * 1000, 3),
                    },
                )
                if result.outcome is PaymentExecutionOutcome.UNCERTAIN:
                    logger.warning(
                        'Payment execution remains uncertain',
                        extra={
                            'event': 'payment_execution_uncertain',
                            'operation': 'execute',
                            **log_context,
                            'outcome': outcome,
                        },
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
    cash_session_id: int | None, executor_key: str | None, idempotency_key: str,
    selection_mode: PaymentExecutorSelectionMode | str | None,
    executor_registry: PaymentExecutorRegistry,
    credential_resolver: MerchantCredentialResolver | None,
    customer_payment_source: EphemeralCustomerPaymentSource | None,
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
        if executor_key is not None or customer_payment_source is not None:
            raise errors.SensitiveCredentialMisuseError('Cash payment cannot carry execution credentials')
        if cash_tendered_amount is None:
            raise errors.InvalidCashTenderError()
        cash_tendered_amount = _validate_amount(cash_tendered_amount)
        if cash_tendered_amount < amount:
            raise errors.InvalidCashTenderError('Cash tender must cover the settlement amount')
    elif cash_tendered_amount is not None:
        raise errors.InvalidCashTenderError('Electronic payment cannot include cash tender evidence')
    elif selection_mode is None:
        raise errors.InvalidPaymentExecutorSelectionError(
            'Electronic payment requires an executor selection mode'
        )

    fingerprint = _request_fingerprint(
        check_id=check_id, expected_version=expected_check_version,
        expected_fingerprint=expected_check_fingerprint, amount=amount,
        currency=currency, method_category=method_category, payer_type=payer_type,
        payer_diner_session_id=payer_diner_session_id, payer_reference=payer_reference,
        cash_tendered_amount=cash_tendered_amount,
        cash_session_id=cash_session_id, executor_key=executor_key,
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
        cash_session = None
        if method_category == 'CASH':
            cash_session = await _cash_session_for_payment(
                db, check=check, currency=currency,
                cash_session_id=cash_session_id,
            )
        members = await _authorize_and_freeze(db, check=check, context=context)
        if payer_type == 'DINER' and payer_diner_session_id not in {
            value.diner_session_id for value in members
        }:
            raise errors.PaymentPermissionError('Diner payer does not participate in this check')
        confirmed, reserved, _ = await _totals(db, check_id=check.id, lock=True)
        available = check.liability_total - confirmed - reserved
        if amount > available:
            raise errors.PaymentAmountExceedsAvailableError()
        resolved_executor = None
        if method_category != 'CASH':
            try:
                resolved_executor = await PaymentExecutorResolver(
                    db, executor_registry
                ).resolve(
                    tenant_id=check.tenant_id,
                    organization_id=check.organization_id,
                    location_id=check.location_id,
                    method_category=method_category,
                    currency=currency,
                    selection_mode=selection_mode,
                    executor_key=executor_key,
                )
            except (
                errors.PaymentExecutorRegistryError,
                errors.PaymentExecutorResolutionError,
            ) as exc:
                logger.warning(
                    'Payment executor selection rejected',
                    extra={
                        'event': 'payment_executor_unavailable',
                        'operation': 'select',
                        'tenant_id': check.tenant_id,
                        'organization_id': check.organization_id,
                        'location_id': check.location_id,
                        'executor_key': executor_key,
                        'method': method_category,
                        'currency': currency,
                        'correlation_id': context.correlation_id,
                        'outcome': exc.code,
                    },
                )
                raise
            logger.info(
                'Payment executor selected',
                extra={
                    'event': 'payment_executor_selected',
                    'operation': 'select',
                    'tenant_id': check.tenant_id,
                    'organization_id': check.organization_id,
                    'location_id': check.location_id,
                    'executor_key': resolved_executor.configuration.executor_key,
                    'adapter_kind': resolved_executor.configuration.adapter_kind,
                    'topology': resolved_executor.configuration.topology,
                    'method': method_category,
                    'currency': currency,
                    'selection_mode': PaymentExecutorSelectionMode(selection_mode).value,
                    'correlation_id': context.correlation_id,
                    'outcome': 'SELECTED',
                },
            )
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
            request_fingerprint=fingerprint, state='RESERVED',
            executor_key=(
                None if resolved_executor is None else
                resolved_executor.configuration.executor_key
            ),
            executor_configuration_id=(
                None if resolved_executor is None else
                resolved_executor.configuration.id
            ),
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
            if cash_session is not None:
                _record_cash_payment_movements(
                    db, session=cash_session, payment=payment,
                    context=context, now=now,
                )
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
        executor_registry=executor_registry,
        credential_resolver=credential_resolver,
        customer_payment_source=customer_payment_source,
    ), False


async def retry_payment(
    db: AsyncSession, *, context: ExecutionContext, payment_id: int,
    executor_registry: PaymentExecutorRegistry,
    credential_resolver: MerchantCredentialResolver | None,
    customer_payment_source: EphemeralCustomerPaymentSource | None,
) -> PaymentProjection:
    claimed, token = await _claim(
        db, tenant_id=context.tenant_id, payment_id=payment_id, context=context,
        attempt_type='RETRY', allowed_states=('FAILED',), reserve_again=True,
    )
    if not token:
        return await _payment_projection(db, claimed)
    return await _execute_claimed(
        db, payment=claimed, token=token, context=context,
        executor_registry=executor_registry,
        credential_resolver=credential_resolver,
        customer_payment_source=customer_payment_source,
    )


async def recover_payment(
    db: AsyncSession, *, context: ExecutionContext, payment_id: int,
    executor_registry: PaymentExecutorRegistry,
    credential_resolver: MerchantCredentialResolver | None,
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
    try:
        resolved = await _historical_executor(
            db, payment=claimed, registry=executor_registry
        )
    except (errors.PaymentExecutorRegistryError, errors.PaymentExecutorResolutionError) as exc:
        logger.warning(
            'Durably selected payment executor is unavailable for recovery',
            extra={
                'event': 'payment_executor_unavailable',
                'operation': 'recover',
                'tenant_id': claimed.tenant_id,
                'organization_id': claimed.organization_id,
                'location_id': claimed.location_id,
                'payment_id': claimed.id,
                'executor_key': claimed.executor_key,
                'method': claimed.method_category,
                'currency': claimed.currency,
                'payment_state': claimed.state,
                'attempt_number': claimed.attempt_count,
                'correlation_id': context.correlation_id,
                'outcome': exc.code,
            },
        )
        result = PaymentRecoveryResult(
            outcome=PaymentRecoveryOutcome.STILL_UNCERTAIN,
            error_code=errors.RecoveryUnavailableError.code,
            error_message='Durably selected payment executor is unavailable for recovery',
        )
    else:
        executor = resolved.executor
        if not isinstance(executor, PaymentRecoveryPort):
            logger.warning(
                'Configured payment executor cannot recover payments',
                extra={
                    'event': 'payment_executor_unavailable',
                    'operation': 'recover',
                    'tenant_id': claimed.tenant_id,
                    'organization_id': claimed.organization_id,
                    'location_id': claimed.location_id,
                    'payment_id': claimed.id,
                    'executor_key': resolved.configuration.executor_key,
                    'adapter_kind': resolved.configuration.adapter_kind,
                    'method': claimed.method_category,
                    'currency': claimed.currency,
                    'payment_state': claimed.state,
                    'attempt_number': claimed.attempt_count,
                    'correlation_id': context.correlation_id,
                    'outcome': errors.RecoveryUnavailableError.code,
                },
            )
            result = PaymentRecoveryResult(
                outcome=PaymentRecoveryOutcome.STILL_UNCERTAIN,
                error_code=errors.RecoveryUnavailableError.code,
                error_message='Configured executor has no recovery capability',
            )
        else:
            try:
                merchant_credential = await _merchant_credential(
                    payment=claimed,
                    configuration=resolved.configuration,
                    resolver=credential_resolver,
                )
            except errors.MerchantCredentialResolutionError:
                result = PaymentRecoveryResult(
                    outcome=PaymentRecoveryOutcome.STILL_UNCERTAIN,
                    error_code=errors.MerchantCredentialResolutionError.code,
                    error_message='Merchant credential could not be resolved for recovery',
                )
            else:
                request = PaymentRecoveryRequest(
                    operation_reference=str(claimed.id),
                    idempotency_key=claimed.provider_idempotency_key,
                    request_fingerprint=claimed.request_fingerprint,
                    external_reference=claimed.external_reference,
                )
                log_context = {
                    'tenant_id': claimed.tenant_id,
                    'organization_id': claimed.organization_id,
                    'location_id': claimed.location_id,
                    'payment_id': claimed.id,
                    'executor_key': resolved.configuration.executor_key,
                    'adapter_kind': resolved.configuration.adapter_kind,
                    'topology': resolved.configuration.topology,
                    'method': claimed.method_category,
                    'currency': claimed.currency,
                    'payment_state': claimed.state,
                    'attempt_number': claimed.attempt_count,
                    'correlation_id': context.correlation_id,
                }
                logger.info(
                    'Payment recovery started',
                    extra={
                        'event': 'payment_recovery_started',
                        'operation': 'recover',
                        **log_context,
                    },
                )
                try:
                    result = await executor.recover(
                        request=request,
                        merchant_credential=merchant_credential,
                    )
                except Exception as exc:
                    result = PaymentRecoveryResult(
                        outcome=PaymentRecoveryOutcome.STILL_UNCERTAIN,
                        error_code='PAYMENT_RECOVERY_RESULT_UNCERTAIN',
                        error_message=f'Unexpected recovery failure: {type(exc).__name__}',
                    )
                outcome = result.outcome.value
                PAYMENT_RECOVERY_TOTAL.labels(
                    method=claimed.method_category,
                    outcome=outcome,
                    adapter_kind=resolved.configuration.adapter_kind,
                    topology=resolved.configuration.topology,
                ).inc()
                logger.info(
                    'Payment recovery completed',
                    extra={
                        'event': 'payment_recovery_completed',
                        'operation': 'recover',
                        **log_context,
                        'outcome': outcome,
                    },
                )
                if result.outcome is PaymentRecoveryOutcome.STILL_UNCERTAIN:
                    logger.warning(
                        'Payment recovery remains uncertain',
                        extra={
                            'event': 'payment_recovery_uncertain',
                            'operation': 'recover',
                            **log_context,
                            'outcome': outcome,
                        },
                    )
    finished = await _finish(
        db, tenant_id=context.tenant_id, payment_id=payment_id, token=token,
        context=context, result=result, state=_recovery_state(result),
    )
    return await _payment_projection(db, finished)
