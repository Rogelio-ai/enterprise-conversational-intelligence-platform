from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    DinerSession,
    Location,
    Organization,
    PaidCheckDispatch,
    PaidCheckDispatchAttempt,
    PreparationDeliveryConnector,
    Resource,
    RestaurantCheck,
    RestaurantCheckAllocation,
    RestaurantCheckSettlement,
    RestaurantCheckVersion,
    RestaurantOrder,
    RestaurantOrderItem,
    RestaurantOrderItemComponent,
    RestaurantOrderPromotion,
    RestaurantPayment,
)
from app.restaurant.paid_check_printing import errors
from app.restaurant.paid_check_printing.contracts import (
    PaidCheckAttemptProjection,
    PaidCheckClaimResult,
    PaidCheckDispatchProjection,
    PaidCheckRecordResult,
)
from app.restaurant.preparation_delivery.contracts import DeliveryResult


PAYLOAD_SCHEMA = 'paid-check-v1'
RESULTS = {
    'DESTINATION_SUBMISSION_ACCEPTED',
    'RETRYABLE_FAILURE',
    'UNCERTAIN',
    'ACTION_REQUIRED',
}
ZERO = Decimal('0')


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fingerprint_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _fingerprint(value: object) -> str:
    return fingerprint_text(canonical_json(value))


def result_fingerprint(
    *, result: str, local_job_reference: str | None, error_kind: str | None,
    error_message: str | None,
) -> str:
    return _fingerprint({
        'error_kind': error_kind,
        'error_message': error_message,
        'local_job_reference': local_job_reference,
        'result': result,
    })


def _money(value: Decimal) -> str:
    return format(value, 'f')


def _actor_scope(execution: ExecutionContext) -> str:
    if execution.actor_type is not ActorType.EMPLOYEE or execution.principal_id is None:
        raise errors.PaidCheckTargetError('Paid-check printing requires an employee actor')
    return f'EMPLOYEE:{execution.principal_id}'


def _attempt_projection(value: PaidCheckDispatchAttempt) -> PaidCheckAttemptProjection:
    return PaidCheckAttemptProjection(
        id=value.id,
        attempt_sequence=value.attempt_sequence,
        attempt_type=value.attempt_type,
        connector_id=value.connector_id,
        claim_request_id=value.claim_request_id,
        actor_principal_reference=value.actor_principal_reference,
        correlation_id=value.correlation_id,
        started_at=value.started_at,
        ended_at=value.ended_at,
        result=value.result,
        result_fingerprint=value.result_fingerprint,
        local_job_reference=value.local_job_reference,
        error_kind=value.error_kind,
        error_message=value.error_message,
    )


async def _projection(
    db: AsyncSession, value: PaidCheckDispatch, *, with_attempts: bool = False,
) -> PaidCheckDispatchProjection:
    attempts: tuple[PaidCheckDispatchAttempt, ...] = ()
    if with_attempts:
        attempts = tuple((await db.execute(select(PaidCheckDispatchAttempt).where(
            PaidCheckDispatchAttempt.tenant_id == value.tenant_id,
            PaidCheckDispatchAttempt.dispatch_id == value.id,
        ).order_by(
            PaidCheckDispatchAttempt.attempt_sequence,
            PaidCheckDispatchAttempt.id,
        ))).scalars().all())
    return PaidCheckDispatchProjection(
        id=value.id,
        tenant_id=value.tenant_id,
        organization_id=value.organization_id,
        location_id=value.location_id,
        restaurant_check_id=value.restaurant_check_id,
        check_version=value.check_version,
        check_fingerprint=value.check_fingerprint,
        cashier_resource_id=value.cashier_resource_id,
        cashier_resource_code=value.cashier_resource_code_snapshot,
        cashier_resource_name=value.cashier_resource_name_snapshot,
        connector_id=value.connector_id,
        connector_code=value.connector_code_snapshot,
        connector_name=value.connector_name_snapshot,
        local_target_key=value.local_target_key_snapshot,
        operation_id=value.operation_id,
        state=value.state,
        payload_schema=value.payload_schema,
        payload_text=value.payload_text,
        payload_fingerprint=value.payload_fingerprint,
        claim_expires_at=value.claim_expires_at,
        attempt_count=value.attempt_count,
        available_at=value.available_at,
        last_error_kind=value.last_error_kind,
        last_error_message=value.last_error_message,
        created_by_membership_id=value.created_by_membership_id,
        correlation_id=value.correlation_id,
        terminal_at=value.terminal_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
        attempts=tuple(_attempt_projection(attempt) for attempt in attempts),
    )


async def _canonical_payload(
    db: AsyncSession, *, check: RestaurantCheck,
    cashier: Resource, connector: PreparationDeliveryConnector,
    local_target_key: str,
) -> tuple[str, str]:
    version = await db.scalar(select(RestaurantCheckVersion).where(
        RestaurantCheckVersion.check_id == check.id,
        RestaurantCheckVersion.version == check.version,
        RestaurantCheckVersion.fingerprint == check.current_fingerprint,
    ))
    if version is None:
        raise errors.PaidCheckNotSettledError(
            'Canonical RestaurantCheck version evidence is missing'
        )
    organization = await db.scalar(select(Organization).where(
        Organization.id == check.organization_id,
        Organization.tenant_id == check.tenant_id,
    ))
    location = await db.scalar(select(Location).where(
        Location.id == check.location_id,
        Location.tenant_id == check.tenant_id,
        Location.organization_id == check.organization_id,
    ))
    if organization is None or location is None:
        raise errors.PaidCheckTargetError('Restaurant identity is unavailable')

    allocations = tuple((await db.execute(select(RestaurantCheckAllocation).where(
        RestaurantCheckAllocation.check_id == check.id,
        RestaurantCheckAllocation.tenant_id == check.tenant_id,
        RestaurantCheckAllocation.state == 'SETTLED',
    ).order_by(RestaurantCheckAllocation.restaurant_order_id))).scalars().all())
    order_ids = tuple(value.restaurant_order_id for value in allocations)
    orders = {value.id: value for value in (await db.execute(select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == check.tenant_id,
        RestaurantOrder.id.in_(order_ids or (-1,)),
    ))).scalars().all()}
    items = tuple((await db.execute(select(RestaurantOrderItem).where(
        RestaurantOrderItem.tenant_id == check.tenant_id,
        RestaurantOrderItem.order_id.in_(order_ids or (-1,)),
    ).order_by(
        RestaurantOrderItem.order_id,
        RestaurantOrderItem.position,
        RestaurantOrderItem.id,
    ))).scalars().all())
    item_ids = tuple(item.id for item in items)
    components = tuple((await db.execute(select(RestaurantOrderItemComponent).where(
        RestaurantOrderItemComponent.tenant_id == check.tenant_id,
        RestaurantOrderItemComponent.order_item_id.in_(item_ids or (-1,)),
    ).order_by(
        RestaurantOrderItemComponent.order_item_id,
        RestaurantOrderItemComponent.position,
        RestaurantOrderItemComponent.id,
    ))).scalars().all())
    promotions = tuple((await db.execute(select(RestaurantOrderPromotion).where(
        RestaurantOrderPromotion.tenant_id == check.tenant_id,
        RestaurantOrderPromotion.order_item_id.in_(item_ids or (-1,)),
    ).order_by(
        RestaurantOrderPromotion.order_item_id,
        RestaurantOrderPromotion.application_order,
        RestaurantOrderPromotion.id,
    ))).scalars().all())
    components_by_item: dict[int, list[dict[str, object]]] = {}
    for component in components:
        components_by_item.setdefault(component.order_item_id, []).append({
            'component_id': component.id,
            'kind': component.kind,
            'choice_group_name': component.choice_group_name,
            'product_id': component.product_id,
            'product_name': component.product_name,
            'quantity': _money(component.quantity),
        })
    promotions_by_item: dict[int, list[dict[str, object]]] = {}
    for promotion in promotions:
        promotions_by_item.setdefault(promotion.order_item_id, []).append({
            'promotion_id': promotion.promotion_id,
            'promotion_name': promotion.promotion_name,
            'promotion_type': promotion.promotion_type,
            'calculated_discount': _money(promotion.calculated_discount),
        })
    items_by_order: dict[int, list[dict[str, object]]] = {}
    for item in items:
        items_by_order.setdefault(item.order_id, []).append({
            'item_id': item.id,
            'product_id': item.product_id,
            'product_name': item.product_name,
            'quantity': _money(item.quantity),
            'unit_price': _money(item.unit_price),
            'base_amount': _money(item.base_amount),
            'discount_amount': _money(item.discount_amount),
            'commercial_amount': _money(item.commercial_amount),
            'components': components_by_item.get(item.id, []),
            'promotions': promotions_by_item.get(item.id, []),
        })
    diner_ids = tuple(sorted({value.source_diner_session_id for value in allocations}))
    diners = dict((await db.execute(select(
        DinerSession.id, DinerSession.display_name,
    ).where(DinerSession.id.in_(diner_ids or (-1,))))).all())
    resource_ids = tuple(sorted({value.source_resource_id for value in allocations}))
    resources = {
        value.id: value for value in (await db.execute(select(Resource).where(
            Resource.tenant_id == check.tenant_id,
            Resource.id.in_(resource_ids or (-1,)),
        ))).scalars().all()
    }

    settlements = tuple((await db.execute(
        select(RestaurantCheckSettlement, RestaurantPayment)
        .join(RestaurantPayment, RestaurantPayment.id == RestaurantCheckSettlement.payment_id)
        .where(
            RestaurantCheckSettlement.tenant_id == check.tenant_id,
            RestaurantCheckSettlement.check_id == check.id,
        )
        .order_by(RestaurantCheckSettlement.applied_at, RestaurantCheckSettlement.id)
    )).all())
    confirmed_total = sum((settlement.amount for settlement, _ in settlements), ZERO)
    if confirmed_total != check.liability_total:
        raise errors.PaidCheckNotSettledError(
            'RestaurantCheck settlement evidence is not fully paid'
        )

    payload = {
        'schema': PAYLOAD_SCHEMA,
        'restaurant': {
            'organization_id': organization.id,
            'organization_code': organization.code,
            'organization_name': organization.name,
            'location_id': location.id,
            'location_code': location.code,
            'location_name': location.name,
            'address_line1': location.address_line1,
            'address_line2': location.address_line2,
            'locality': location.locality,
            'administrative_area': location.administrative_area,
            'postal_code': location.postal_code,
            'country_code': location.country_code,
        },
        'check': {
            'id': check.id,
            'version': check.version,
            'fingerprint': check.current_fingerprint,
            'status': check.status,
            'currency': check.currency,
            'member_snapshot': version.member_snapshot,
            'allocation_snapshot': version.allocation_snapshot,
            'orders': [
                {
                    'restaurant_order_id': allocation.restaurant_order_id,
                    'commercial_fingerprint': allocation.accepted_commercial_fingerprint,
                    'accepted_at': orders[allocation.restaurant_order_id].accepted_at.isoformat(),
                    'diner_session_id': allocation.source_diner_session_id,
                    'diner_display_name': diners.get(allocation.source_diner_session_id),
                    'service_session_id': allocation.source_service_session_id,
                    'resource_id': allocation.source_resource_id,
                    'resource_code': (
                        resources[allocation.source_resource_id].code
                        if allocation.source_resource_id in resources else None
                    ),
                    'resource_name': (
                        resources[allocation.source_resource_id].name
                        if allocation.source_resource_id in resources else None
                    ),
                    'accepted_payable_amount': _money(allocation.accepted_payable_amount),
                    'items': items_by_order.get(allocation.restaurant_order_id, []),
                }
                for allocation in allocations
            ],
            'consumption_total': _money(check.consumption_total),
            'gratuity_total': _money(check.gratuity_total),
            'liability_total': _money(check.liability_total),
            'confirmed_paid_total': _money(confirmed_total),
            'outstanding_total': _money(ZERO),
            'settled_at': check.settled_at.isoformat() if check.settled_at else None,
            'payments': [
                {
                    'settlement_id': settlement.id,
                    'payment_id': payment.id,
                    'method_category': payment.method_category,
                    'amount': _money(settlement.amount),
                    'currency': settlement.currency,
                    'payer_type': payment.payer_type,
                    'payer_reference': payment.payer_reference,
                    'cash_tendered_amount': (
                        _money(payment.cash_tendered_amount)
                        if payment.cash_tendered_amount is not None else None
                    ),
                    'cash_change_due': (
                        _money(payment.cash_change_due)
                        if payment.cash_change_due is not None else None
                    ),
                    'external_reference': payment.external_reference,
                    'instrument_display': payment.instrument_display,
                    'applied_at': settlement.applied_at.isoformat(),
                }
                for settlement, payment in settlements
            ],
        },
        'print_target': {
            'cashier_resource_id': cashier.id,
            'cashier_resource_code': cashier.code,
            'cashier_resource_name': cashier.name,
            'connector_id': connector.id,
            'connector_code': connector.code,
            'connector_name': connector.name,
            'local_target_key': local_target_key,
        },
    }
    payload_text = canonical_json(payload)
    return payload_text, fingerprint_text(payload_text)


async def create_dispatch(
    db: AsyncSession, *, execution: ExecutionContext, check_id: int,
    cashier_resource_id: int, connector_id: int, local_target_key: str,
    idempotency_key: str,
) -> tuple[PaidCheckDispatchProjection, bool]:
    actor_scope = _actor_scope(execution)
    target_key = local_target_key.strip()
    if not target_key or len(target_key) > 128 or '://' in target_key:
        raise errors.PaidCheckTargetError('Invalid local printer target key')
    try:
        check = await db.scalar(select(RestaurantCheck).where(
            RestaurantCheck.id == check_id,
            RestaurantCheck.tenant_id == execution.tenant_id,
        ).with_for_update())
        if check is None:
            raise errors.PaidCheckDispatchNotFoundError('RestaurantCheck not found')
        request = {
            'restaurant_check_id': check.id,
            'check_fingerprint': check.current_fingerprint,
            'cashier_resource_id': cashier_resource_id,
            'connector_id': connector_id,
            'local_target_key': target_key,
        }
        request_fingerprint = _fingerprint(request)
        replay = await db.scalar(select(PaidCheckDispatch).where(
            PaidCheckDispatch.tenant_id == execution.tenant_id,
            PaidCheckDispatch.actor_scope == actor_scope,
            PaidCheckDispatch.idempotency_key == idempotency_key,
        ).with_for_update())
        if replay is not None:
            if replay.request_fingerprint != request_fingerprint:
                raise errors.PaidCheckIdempotencyConflictError(
                    'Idempotency key was already used for a different paid-check print request'
                )
            await db.commit()
            return await _projection(db, replay), True
        if check.status != 'SETTLED' or check.settled_at is None:
            raise errors.PaidCheckNotSettledError(
                'Only a fully SETTLED RestaurantCheck can be printed as paid'
            )
        cashier = await db.scalar(select(Resource).where(
            Resource.id == cashier_resource_id,
            Resource.tenant_id == check.tenant_id,
            Resource.location_id == check.location_id,
        ))
        if cashier is None:
            raise errors.PaidCheckDispatchNotFoundError('Cashier resource not found')
        if cashier.resource_type != 'CASH_REGISTER' or cashier.status != 'ACTIVE':
            raise errors.PaidCheckTargetError(
                'Paid-check printing requires an ACTIVE CASH_REGISTER resource'
            )
        connector = await db.scalar(select(PreparationDeliveryConnector).where(
            PreparationDeliveryConnector.id == connector_id,
            PreparationDeliveryConnector.tenant_id == check.tenant_id,
            PreparationDeliveryConnector.organization_id == check.organization_id,
            PreparationDeliveryConnector.location_id == check.location_id,
        ))
        if connector is None:
            raise errors.PaidCheckDispatchNotFoundError('Local connector not found')
        if connector.status != 'ACTIVE':
            raise errors.PaidCheckTargetError('Local connector is not active')
        payload_text, payload_fingerprint = await _canonical_payload(
            db, check=check, cashier=cashier, connector=connector,
            local_target_key=target_key,
        )
        now = _now()
        dispatch = PaidCheckDispatch(
            tenant_id=check.tenant_id,
            organization_id=check.organization_id,
            location_id=check.location_id,
            restaurant_check_id=check.id,
            check_version=check.version,
            check_fingerprint=check.current_fingerprint,
            cashier_resource_id=cashier.id,
            cashier_resource_code_snapshot=cashier.code,
            cashier_resource_name_snapshot=cashier.name,
            connector_id=connector.id,
            connector_code_snapshot=connector.code,
            connector_name_snapshot=connector.name,
            local_target_key_snapshot=target_key,
            operation_id=str(uuid4()),
            actor_scope=actor_scope,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            state='PENDING',
            payload_schema=PAYLOAD_SCHEMA,
            payload_text=payload_text,
            payload_fingerprint=payload_fingerprint,
            attempt_count=0,
            available_at=now,
            created_by_membership_id=execution.principal_id,
            correlation_id=execution.correlation_id,
        )
        db.add(dispatch)
        await db.commit()
        await db.refresh(dispatch)
        return await _projection(db, dispatch), False
    except IntegrityError as exc:
        await db.rollback()
        replay = await db.scalar(select(PaidCheckDispatch).where(
            PaidCheckDispatch.tenant_id == execution.tenant_id,
            PaidCheckDispatch.actor_scope == actor_scope,
            PaidCheckDispatch.idempotency_key == idempotency_key,
        ))
        if replay is not None and replay.request_fingerprint == request_fingerprint:
            return await _projection(db, replay), True
        raise errors.PaidCheckIdempotencyConflictError(
            'Concurrent paid-check print request conflicted'
        ) from exc
    except Exception:
        await db.rollback()
        raise


async def get_dispatch(
    db: AsyncSession, *, tenant_id: int, dispatch_id: int,
    with_attempts: bool = True,
) -> PaidCheckDispatchProjection:
    value = await db.scalar(select(PaidCheckDispatch).where(
        PaidCheckDispatch.id == dispatch_id,
        PaidCheckDispatch.tenant_id == tenant_id,
    ))
    if value is None:
        raise errors.PaidCheckDispatchNotFoundError('Paid-check dispatch not found')
    return await _projection(db, value, with_attempts=with_attempts)


async def claim_dispatch(
    db: AsyncSession, *, dispatch_id: int, connector_id: int,
    execution: ExecutionContext, recovery: bool = False,
    claim_request_id: str | None = None, claim_lease_seconds: int = 120,
) -> PaidCheckClaimResult:
    now = _now()
    if claim_request_id is not None:
        replay = await db.scalar(select(PaidCheckDispatchAttempt).where(
            PaidCheckDispatchAttempt.tenant_id == execution.tenant_id,
            PaidCheckDispatchAttempt.connector_id == connector_id,
            PaidCheckDispatchAttempt.claim_request_id == claim_request_id,
        ))
        if replay is not None:
            if replay.dispatch_id != dispatch_id:
                raise errors.PaidCheckDeliveryConflictError(
                    'claim_request_id was already used for a different paid-check dispatch'
                )
            replay_dispatch = await db.scalar(select(PaidCheckDispatch).where(
                PaidCheckDispatch.id == dispatch_id,
                PaidCheckDispatch.tenant_id == execution.tenant_id,
                PaidCheckDispatch.connector_id == connector_id,
            ))
            if replay_dispatch is None:
                raise errors.PaidCheckDispatchNotFoundError('Paid-check dispatch not found')
            return PaidCheckClaimResult(
                dispatch=await _projection(db, replay_dispatch),
                attempt=_attempt_projection(replay),
                claim_token=replay.claim_token,
            )
    dispatch = await db.scalar(select(PaidCheckDispatch).where(
        PaidCheckDispatch.id == dispatch_id,
        PaidCheckDispatch.tenant_id == execution.tenant_id,
    ).with_for_update())
    if dispatch is None or dispatch.connector_id != connector_id:
        raise errors.PaidCheckDispatchNotFoundError('Paid-check dispatch not found')
    if dispatch.state == 'IN_PROGRESS':
        if dispatch.claim_expires_at is not None and dispatch.claim_expires_at > now:
            raise errors.PaidCheckDeliveryConflictError(
                'Paid-check dispatch already has an active claim'
            )
        if not recovery:
            raise errors.PaidCheckDeliveryConflictError('Expired claim requires recovery')
        previous = await db.scalar(select(PaidCheckDispatchAttempt).where(
            PaidCheckDispatchAttempt.dispatch_id == dispatch.id,
            PaidCheckDispatchAttempt.claim_token == dispatch.claim_token,
        ).with_for_update())
        if previous is None or previous.result != 'IN_PROGRESS':
            raise errors.PaidCheckDeliveryConflictError('Active delivery attempt is missing')
        previous.result = 'UNCERTAIN'
        previous.ended_at = now
        previous.error_kind = 'CLAIM_EXPIRED'
        previous.error_message = (
            'Claim expired after the printer boundary may have been crossed'
        )
        previous.result_fingerprint = result_fingerprint(
            result=previous.result,
            local_job_reference=None,
            error_kind=previous.error_kind,
            error_message=previous.error_message,
        )
        attempt_type = 'RECOVERY'
    elif dispatch.state == 'PENDING':
        attempt_type = 'DELIVER' if dispatch.attempt_count == 0 else 'RETRY'
    elif dispatch.state == 'RETRYABLE_FAILURE':
        attempt_type = 'RETRY'
    elif dispatch.state in {'UNCERTAIN', 'ACTION_REQUIRED'} and recovery:
        attempt_type = 'RECOVERY'
    else:
        raise errors.PaidCheckDeliveryConflictError(
            f'Paid-check dispatch in {dispatch.state} cannot be claimed'
        )
    if dispatch.available_at > now:
        raise errors.PaidCheckDeliveryConflictError('Paid-check dispatch is not yet available')
    connector = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == connector_id,
        PreparationDeliveryConnector.tenant_id == dispatch.tenant_id,
        PreparationDeliveryConnector.organization_id == dispatch.organization_id,
        PreparationDeliveryConnector.location_id == dispatch.location_id,
        PreparationDeliveryConnector.status == 'ACTIVE',
    ))
    if (
        connector is None
        or execution.actor_type is not ActorType.EXTERNAL_SYSTEM
        or execution.principal_reference != connector.auth_subject
    ):
        raise errors.PaidCheckDispatchNotFoundError('Local connector not found')
    token = str(uuid4())
    attempt = PaidCheckDispatchAttempt(
        tenant_id=dispatch.tenant_id,
        organization_id=dispatch.organization_id,
        location_id=dispatch.location_id,
        dispatch_id=dispatch.id,
        connector_id=connector.id,
        attempt_sequence=dispatch.attempt_count + 1,
        attempt_type=attempt_type,
        claim_token=token,
        claim_request_id=claim_request_id,
        actor_principal_reference=connector.auth_subject,
        correlation_id=execution.correlation_id,
        started_at=now,
        result='IN_PROGRESS',
    )
    db.add(attempt)
    dispatch.state = 'IN_PROGRESS'
    dispatch.claim_token = token
    dispatch.claim_expires_at = now + timedelta(seconds=claim_lease_seconds)
    dispatch.attempt_count += 1
    dispatch.last_error_kind = None
    dispatch.last_error_message = None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise errors.PaidCheckDeliveryConflictError(
            'Paid-check dispatch claim conflicted'
        ) from exc
    await db.refresh(dispatch)
    await db.refresh(attempt)
    return PaidCheckClaimResult(
        dispatch=await _projection(db, dispatch),
        attempt=_attempt_projection(attempt),
        claim_token=token,
    )


async def record_result(
    db: AsyncSession, *, dispatch_id: int, connector_id: int, claim_token: str,
    delivery_result: DeliveryResult, execution: ExecutionContext,
    retry_available_at: datetime | None = None,
) -> PaidCheckRecordResult:
    if delivery_result.result not in RESULTS:
        raise ValueError('Unsupported paid-check delivery result')
    expected = result_fingerprint(
        result=delivery_result.result,
        local_job_reference=delivery_result.local_job_reference,
        error_kind=delivery_result.error_kind,
        error_message=delivery_result.error_message,
    )
    if delivery_result.result_fingerprint != expected:
        raise errors.PaidCheckDeliveryConflictError(
            'Paid-check delivery result fingerprint does not match'
        )
    dispatch = await db.scalar(select(PaidCheckDispatch).where(
        PaidCheckDispatch.id == dispatch_id,
        PaidCheckDispatch.tenant_id == execution.tenant_id,
    ).with_for_update())
    if dispatch is None or dispatch.connector_id != connector_id:
        raise errors.PaidCheckDispatchNotFoundError('Paid-check dispatch not found')
    connector = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == connector_id,
        PreparationDeliveryConnector.tenant_id == dispatch.tenant_id,
        PreparationDeliveryConnector.organization_id == dispatch.organization_id,
        PreparationDeliveryConnector.location_id == dispatch.location_id,
    ))
    if (
        connector is None
        or execution.actor_type is not ActorType.EXTERNAL_SYSTEM
        or execution.principal_reference != connector.auth_subject
    ):
        raise errors.PaidCheckDispatchNotFoundError('Local connector not found')
    attempt = await db.scalar(select(PaidCheckDispatchAttempt).where(
        PaidCheckDispatchAttempt.dispatch_id == dispatch.id,
        PaidCheckDispatchAttempt.claim_token == claim_token,
        PaidCheckDispatchAttempt.connector_id == connector_id,
    ).with_for_update())
    if attempt is None:
        raise errors.PaidCheckDispatchNotFoundError('Paid-check attempt not found')
    if attempt.result != 'IN_PROGRESS':
        if attempt.result_fingerprint != expected:
            raise errors.PaidCheckDeliveryConflictError(
                'Paid-check delivery result conflicts with finalized evidence'
            )
        return PaidCheckRecordResult(
            dispatch=await _projection(db, dispatch),
            attempt=_attempt_projection(attempt),
            replayed=True,
        )
    if dispatch.state != 'IN_PROGRESS' or dispatch.claim_token != claim_token:
        raise errors.PaidCheckDeliveryConflictError('Paid-check delivery result is fenced')
    now = _now()
    attempt.result = delivery_result.result
    attempt.result_fingerprint = expected
    attempt.local_job_reference = delivery_result.local_job_reference
    attempt.error_kind = delivery_result.error_kind
    attempt.error_message = (
        delivery_result.error_message[:500] if delivery_result.error_message else None
    )
    attempt.ended_at = now
    dispatch.state = delivery_result.result
    dispatch.claim_token = None
    dispatch.claim_expires_at = None
    dispatch.last_error_kind = delivery_result.error_kind
    dispatch.last_error_message = (
        delivery_result.error_message[:500] if delivery_result.error_message else None
    )
    if delivery_result.result == 'RETRYABLE_FAILURE':
        dispatch.available_at = retry_available_at or now
    if delivery_result.result == 'DESTINATION_SUBMISSION_ACCEPTED':
        dispatch.terminal_at = now
    await db.commit()
    await db.refresh(dispatch)
    await db.refresh(attempt)
    return PaidCheckRecordResult(
        dispatch=await _projection(db, dispatch),
        attempt=_attempt_projection(attempt),
        replayed=False,
    )
