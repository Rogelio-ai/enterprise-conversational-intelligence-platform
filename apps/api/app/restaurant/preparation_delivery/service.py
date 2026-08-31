from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    PreparationDeliveryConnector,
    PreparationDeliveryDestination,
    PreparationDispatch,
    PreparationDispatchAttempt,
    PreparationWork,
    PreparationWorkItem,
    Resource,
    RestaurantOrder,
    RestaurantOrderItem,
    RestaurantOrderItemComponent,
)
from app.restaurant.preparation_delivery import errors
from app.restaurant.preparation_delivery.contracts import (
    ClaimResult,
    DeliveryResult,
    DispatchAttemptProjection,
    DispatchProjection,
    RecordResultOutcome,
)


PAYLOAD_SCHEMA = 'preparation-delivery-v1'
CLAIM_LEASE = timedelta(minutes=2)
RESULTS = {
    'DESTINATION_SUBMISSION_ACCEPTED',
    'RETRYABLE_FAILURE',
    'UNCERTAIN',
    'ACTION_REQUIRED',
}
logger = logging.getLogger('ecip.preparation_delivery')


def _now() -> datetime:
    # MySQL/MariaDB DATETIME columns in this schema use second precision.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fingerprint_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def operation_id(*, tenant_id: int, work_id: int, destination_id: int, generation: int) -> str:
    return f'{PAYLOAD_SCHEMA}:{tenant_id}:{work_id}:{destination_id}:{generation}'


def result_fingerprint(
    *, result: str, local_job_reference: str | None, error_kind: str | None,
    error_message: str | None,
) -> str:
    return fingerprint_text(canonical_json({
        'error_kind': error_kind,
        'error_message': error_message,
        'local_job_reference': local_job_reference,
        'result': result,
    }))


def _actor(execution: ExecutionContext) -> dict[str, object]:
    return {
        'actor_type': execution.actor_type.value,
        'actor_membership_id': execution.principal_id if execution.actor_type is ActorType.EMPLOYEE else None,
        'actor_principal_reference': execution.principal_reference if execution.actor_type is not ActorType.EMPLOYEE else None,
    }


def _attempt_projection(value: PreparationDispatchAttempt) -> DispatchAttemptProjection:
    return DispatchAttemptProjection(
        id=value.id,
        attempt_sequence=value.attempt_sequence,
        attempt_type=value.attempt_type,
        connector_id=value.connector_id,
        actor_type=value.actor_type,
        actor_membership_id=value.actor_membership_id,
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
    db: AsyncSession, value: PreparationDispatch, *, with_attempts: bool = False
) -> DispatchProjection:
    attempts: tuple[PreparationDispatchAttempt, ...] = ()
    if with_attempts:
        attempts = tuple((await db.execute(select(PreparationDispatchAttempt).where(
            PreparationDispatchAttempt.tenant_id == value.tenant_id,
            PreparationDispatchAttempt.dispatch_id == value.id,
        ).order_by(
            PreparationDispatchAttempt.attempt_sequence,
            PreparationDispatchAttempt.id,
        ))).scalars().all())
    return DispatchProjection(
        id=value.id, tenant_id=value.tenant_id, organization_id=value.organization_id,
        location_id=value.location_id, restaurant_order_id=value.restaurant_order_id,
        preparation_work_id=value.preparation_work_id,
        preparation_area_id=value.preparation_area_id, destination_id=value.destination_id,
        operation_kind=value.operation_kind, generation=value.generation,
        operation_id=value.operation_id, reprint_of_dispatch_id=value.reprint_of_dispatch_id,
        state=value.state, payload_schema=value.payload_schema, payload_text=value.payload_text,
        payload_fingerprint=value.payload_fingerprint,
        destination_code=value.destination_code_snapshot,
        destination_name=value.destination_name_snapshot,
        destination_channel=value.destination_channel_snapshot,
        connector_id=value.connector_id_snapshot, connector_code=value.connector_code_snapshot,
        connector_name=value.connector_name_snapshot,
        local_target_key=value.local_target_key_snapshot,
        claim_expires_at=value.claim_expires_at, attempt_count=value.attempt_count,
        available_at=value.available_at, last_error_kind=value.last_error_kind,
        last_error_message=value.last_error_message,
        initiating_actor_type=value.initiating_actor_type,
        initiating_membership_id=value.initiating_membership_id,
        initiating_principal_reference=value.initiating_principal_reference,
        correlation_id=value.correlation_id, causation_id=value.causation_id,
        terminal_at=value.terminal_at, created_at=value.created_at, updated_at=value.updated_at,
        attempts=tuple(_attempt_projection(attempt) for attempt in attempts),
    )


def _quantity(value: Decimal) -> str:
    return format(value, 'f')


async def build_canonical_payload(
    db: AsyncSession, *, work: PreparationWork
) -> tuple[str, str]:
    order = await db.scalar(select(RestaurantOrder).where(
        RestaurantOrder.id == work.restaurant_order_id,
        RestaurantOrder.tenant_id == work.tenant_id,
    ))
    if order is None:
        raise errors.PreparationDeliveryConfigurationError('Preparation Work order snapshot is missing')
    resource = await db.scalar(select(Resource).where(
        Resource.id == order.resource_id,
        Resource.tenant_id == order.tenant_id,
        Resource.location_id == order.location_id,
    ))
    work_items = tuple((await db.execute(select(PreparationWorkItem).where(
        PreparationWorkItem.tenant_id == work.tenant_id,
        PreparationWorkItem.preparation_work_id == work.id,
    ).order_by(PreparationWorkItem.id))).scalars().all())
    items: list[dict[str, object]] = []
    for work_item in work_items:
        accepted_components: list[dict[str, object]] = []
        if work_item.source_restaurant_order_item_id is not None:
            source = await db.scalar(select(RestaurantOrderItem).where(
                RestaurantOrderItem.id == work_item.source_restaurant_order_item_id,
                RestaurantOrderItem.tenant_id == work.tenant_id,
                RestaurantOrderItem.order_id == work.restaurant_order_id,
            ))
            if source is None:
                raise errors.PreparationDeliveryConfigurationError('Accepted order item snapshot is missing')
            components = tuple((await db.execute(select(RestaurantOrderItemComponent).where(
                RestaurantOrderItemComponent.tenant_id == work.tenant_id,
                RestaurantOrderItemComponent.order_id == work.restaurant_order_id,
                RestaurantOrderItemComponent.order_item_id == source.id,
            ).order_by(RestaurantOrderItemComponent.position, RestaurantOrderItemComponent.id))).scalars().all())
            accepted_components = [{
                'kind': component.kind,
                'choice_group_name': component.choice_group_name,
                'product_name': component.product_name,
                'quantity': _quantity(component.quantity),
            } for component in components]
            source_type = 'ITEM'
            product_name = source.product_name
            parent_product_name = None
        else:
            component = await db.scalar(select(RestaurantOrderItemComponent).where(
                RestaurantOrderItemComponent.id == work_item.source_restaurant_order_item_component_id,
                RestaurantOrderItemComponent.tenant_id == work.tenant_id,
                RestaurantOrderItemComponent.order_id == work.restaurant_order_id,
            ))
            parent = await db.scalar(select(RestaurantOrderItem).where(
                RestaurantOrderItem.id == work_item.source_restaurant_order_item_id_for_component,
                RestaurantOrderItem.tenant_id == work.tenant_id,
                RestaurantOrderItem.order_id == work.restaurant_order_id,
            ))
            if component is None or parent is None:
                raise errors.PreparationDeliveryConfigurationError('Accepted component snapshot is missing')
            accepted_components = [{
                'kind': component.kind,
                'choice_group_name': component.choice_group_name,
                'product_name': component.product_name,
                'quantity': _quantity(component.quantity),
            }]
            source_type = 'COMPONENT'
            product_name = component.product_name
            parent_product_name = parent.product_name
        items.append({
            'accepted_components': accepted_components,
            'parent_product_name': parent_product_name,
            'preparation_work_item_id': work_item.id,
            'product_name': product_name,
            'required_quantity': _quantity(work_item.required_quantity),
            'source_restaurant_order_item_component_id': work_item.source_restaurant_order_item_component_id,
            'source_restaurant_order_item_id': work_item.source_restaurant_order_item_id,
            'source_type': source_type,
        })
    payload = {
        'items': items,
        'location_id': work.location_id,
        'preparation_work': {
            'area_code': work.area_code_snapshot,
            'area_id': work.preparation_area_id,
            'area_name': work.area_name_snapshot,
            'id': work.id,
            'routed_at': work.routed_at.isoformat(),
        },
        'restaurant_order': {
            'accepted_at': order.accepted_at.isoformat(),
            'id': order.id,
            'resource_code_at_dispatch': resource.code if resource is not None else None,
            'resource_id': order.resource_id,
            'resource_name_at_dispatch': resource.name if resource is not None else None,
            'source_channel': order.source_channel,
        },
        'schema': PAYLOAD_SCHEMA,
        'tenant_id': work.tenant_id,
    }
    text = canonical_json(payload)
    return text, fingerprint_text(text)


async def materialize_initial_dispatches(
    db: AsyncSession, *, work: PreparationWork, correlation_id: str | None,
    causation_id: str | None = None,
) -> tuple[PreparationDispatch, ...]:
    if work.preparation_owner != 'PLATFORM':
        return ()
    await db.flush()
    rows = tuple((await db.execute(
        select(PreparationDeliveryDestination, PreparationDeliveryConnector)
        .join(PreparationDeliveryConnector, PreparationDeliveryConnector.id == PreparationDeliveryDestination.connector_id)
        .where(
            PreparationDeliveryDestination.tenant_id == work.tenant_id,
            PreparationDeliveryDestination.organization_id == work.organization_id,
            PreparationDeliveryDestination.location_id == work.location_id,
            PreparationDeliveryDestination.preparation_area_id == work.preparation_area_id,
            PreparationDeliveryDestination.status == 'ACTIVE',
        )
        .order_by(PreparationDeliveryDestination.id)
    )).all())
    if not rows:
        return ()
    payload_text, payload_fingerprint = await build_canonical_payload(db, work=work)
    now = _now()
    dispatches: list[PreparationDispatch] = []
    for destination, connector in rows:
        state = 'PENDING' if connector.status == 'ACTIVE' else 'ACTION_REQUIRED'
        value = PreparationDispatch(
            tenant_id=work.tenant_id, organization_id=work.organization_id,
            location_id=work.location_id, restaurant_order_id=work.restaurant_order_id,
            preparation_work_id=work.id, preparation_area_id=work.preparation_area_id,
            destination_id=destination.id, operation_kind='INITIAL', generation=1,
            operation_id=operation_id(
                tenant_id=work.tenant_id, work_id=work.id,
                destination_id=destination.id, generation=1,
            ),
            reprint_of_dispatch_id=None, state=state, payload_schema=PAYLOAD_SCHEMA,
            payload_text=payload_text, payload_fingerprint=payload_fingerprint,
            destination_code_snapshot=destination.code,
            destination_name_snapshot=destination.name,
            destination_channel_snapshot=destination.channel,
            connector_id_snapshot=connector.id, connector_code_snapshot=connector.code,
            connector_name_snapshot=connector.name,
            local_target_key_snapshot=destination.local_target_key,
            claim_token=None, claim_expires_at=None, attempt_count=0, available_at=now,
            last_error_kind='CONNECTOR_INACTIVE' if state == 'ACTION_REQUIRED' else None,
            last_error_message='Configured delivery connector is inactive' if state == 'ACTION_REQUIRED' else None,
            initiating_actor_type='SYSTEM', initiating_membership_id=None,
            initiating_principal_reference='preparation-dispatch-materializer',
            correlation_id=correlation_id, causation_id=causation_id,
            terminal_at=None,
        )
        db.add(value)
        dispatches.append(value)
    await db.flush()
    logger.info(
        'Preparation dispatches materialized',
        extra={
            'event': 'preparation_dispatches_materialized',
            'tenant_id': work.tenant_id,
            'location_id': work.location_id,
            'restaurant_order_id': work.restaurant_order_id,
            'preparation_work_id': work.id,
            'dispatch_count': len(dispatches),
            'correlation_id': correlation_id,
        },
    )
    return tuple(dispatches)


async def list_dispatches(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    state: str | None = None, destination_id: int | None = None,
    work_id: int | None = None, order_id: int | None = None,
    after_dispatch_id: int | None = None, limit: int = 50,
) -> tuple[DispatchProjection, ...]:
    statement = select(PreparationDispatch).where(
        PreparationDispatch.tenant_id == tenant_id,
        PreparationDispatch.location_id == location_id,
    )
    if state is not None:
        statement = statement.where(PreparationDispatch.state == state)
    if destination_id is not None:
        statement = statement.where(PreparationDispatch.destination_id == destination_id)
    if work_id is not None:
        statement = statement.where(PreparationDispatch.preparation_work_id == work_id)
    if order_id is not None:
        statement = statement.where(PreparationDispatch.restaurant_order_id == order_id)
    if after_dispatch_id is not None:
        cursor = await db.scalar(select(PreparationDispatch).where(
            PreparationDispatch.id == after_dispatch_id,
            PreparationDispatch.tenant_id == tenant_id,
            PreparationDispatch.location_id == location_id,
        ))
        if cursor is None:
            raise errors.PreparationDeliveryNotFoundError('Preparation Dispatch cursor not found')
        statement = statement.where(PreparationDispatch.id > cursor.id)
    values = tuple((await db.execute(statement.order_by(PreparationDispatch.id).limit(limit))).scalars().all())
    return tuple([await _projection(db, value) for value in values])


async def get_dispatch(
    db: AsyncSession, *, tenant_id: int, dispatch_id: int,
    with_attempts: bool = True,
) -> DispatchProjection:
    value = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.id == dispatch_id,
        PreparationDispatch.tenant_id == tenant_id,
    ))
    if value is None:
        raise errors.PreparationDeliveryNotFoundError('Preparation Dispatch not found')
    return await _projection(db, value, with_attempts=with_attempts)


async def claim_dispatch(
    db: AsyncSession, *, dispatch_id: int, connector_id: int,
    execution: ExecutionContext, recovery: bool = False,
) -> ClaimResult:
    now = _now()
    dispatch = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.id == dispatch_id,
        PreparationDispatch.tenant_id == execution.tenant_id,
    ).with_for_update())
    if dispatch is None or dispatch.connector_id_snapshot != connector_id:
        raise errors.PreparationDeliveryNotFoundError('Preparation Dispatch not found')
    if dispatch.state == 'IN_PROGRESS':
        if dispatch.claim_expires_at is not None and dispatch.claim_expires_at > now:
            raise errors.PreparationDeliveryConflictError('Preparation Dispatch already has an active claim')
        if not recovery:
            raise errors.PreparationDeliveryConflictError('Expired claim requires recovery')
        previous = await db.scalar(select(PreparationDispatchAttempt).where(
            PreparationDispatchAttempt.dispatch_id == dispatch.id,
            PreparationDispatchAttempt.claim_token == dispatch.claim_token,
        ).with_for_update())
        if previous is None or previous.result != 'IN_PROGRESS':
            raise errors.PreparationDeliveryConflictError('Active dispatch attempt is missing')
        previous.result = 'UNCERTAIN'
        previous.ended_at = now
        previous.error_kind = 'CLAIM_EXPIRED'
        previous.error_message = 'Claim expired after the destination boundary may have been crossed'
        previous.result_fingerprint = result_fingerprint(
            result=previous.result, local_job_reference=None,
            error_kind=previous.error_kind, error_message=previous.error_message,
        )
        attempt_type = 'RECOVERY'
    elif dispatch.state == 'PENDING':
        attempt_type = 'DELIVER' if dispatch.attempt_count == 0 else 'RETRY'
    elif dispatch.state == 'RETRYABLE_FAILURE':
        attempt_type = 'RETRY'
    elif dispatch.state == 'UNCERTAIN' and recovery:
        attempt_type = 'RECOVERY'
    else:
        raise errors.PreparationDeliveryConflictError(
            f'Preparation Dispatch in {dispatch.state} cannot be claimed'
        )
    if dispatch.available_at > now:
        raise errors.PreparationDeliveryConflictError('Preparation Dispatch is not yet available')
    connector = await db.scalar(select(PreparationDeliveryConnector).where(
        PreparationDeliveryConnector.id == connector_id,
        PreparationDeliveryConnector.tenant_id == dispatch.tenant_id,
        PreparationDeliveryConnector.organization_id == dispatch.organization_id,
        PreparationDeliveryConnector.location_id == dispatch.location_id,
        PreparationDeliveryConnector.status == 'ACTIVE',
    ))
    if connector is None:
        raise errors.PreparationDeliveryNotFoundError('Preparation Delivery Connector not found')
    if (
        execution.actor_type is not ActorType.EXTERNAL_SYSTEM
        or execution.principal_reference != connector.auth_subject
    ):
        raise errors.PreparationDeliveryNotFoundError('Preparation Delivery Connector not found')
    token = str(uuid4())
    actor = _actor(execution)
    attempt = PreparationDispatchAttempt(
        tenant_id=dispatch.tenant_id, organization_id=dispatch.organization_id,
        location_id=dispatch.location_id, dispatch_id=dispatch.id,
        connector_id=connector.id, attempt_sequence=dispatch.attempt_count + 1,
        attempt_type=attempt_type, claim_token=token,
        actor_type=actor['actor_type'], actor_membership_id=actor['actor_membership_id'],
        actor_principal_reference=actor['actor_principal_reference'],
        correlation_id=execution.correlation_id, started_at=now, ended_at=None,
        result='IN_PROGRESS', result_fingerprint=None,
    )
    db.add(attempt)
    dispatch.state = 'IN_PROGRESS'
    dispatch.claim_token = token
    dispatch.claim_expires_at = now + CLAIM_LEASE
    dispatch.attempt_count += 1
    dispatch.last_error_kind = None
    dispatch.last_error_message = None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise errors.PreparationDeliveryConflictError('Preparation Dispatch claim conflicted') from exc
    await db.refresh(dispatch)
    await db.refresh(attempt)
    logger.info(
        'Preparation dispatch claimed',
        extra={
            'event': 'preparation_dispatch_claimed',
            'tenant_id': dispatch.tenant_id,
            'location_id': dispatch.location_id,
            'restaurant_order_id': dispatch.restaurant_order_id,
            'preparation_work_id': dispatch.preparation_work_id,
            'dispatch_id': dispatch.id,
            'destination_id': dispatch.destination_id,
            'attempt_id': attempt.id,
            'operation_id': dispatch.operation_id,
            'correlation_id': execution.correlation_id,
            'state': dispatch.state,
        },
    )
    return ClaimResult(
        dispatch=await _projection(db, dispatch),
        attempt=_attempt_projection(attempt),
        claim_token=token,
    )


async def record_result(
    db: AsyncSession, *, dispatch_id: int, connector_id: int, claim_token: str,
    delivery_result: DeliveryResult, execution: ExecutionContext,
    retry_available_at: datetime | None = None,
) -> RecordResultOutcome:
    if delivery_result.result not in RESULTS:
        raise ValueError('Unsupported preparation delivery result')
    expected = result_fingerprint(
        result=delivery_result.result,
        local_job_reference=delivery_result.local_job_reference,
        error_kind=delivery_result.error_kind,
        error_message=delivery_result.error_message,
    )
    if delivery_result.result_fingerprint != expected:
        raise errors.PreparationDeliveryConflictError('Preparation delivery result fingerprint does not match')
    dispatch = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.id == dispatch_id,
        PreparationDispatch.tenant_id == execution.tenant_id,
    ).with_for_update())
    if dispatch is None or dispatch.connector_id_snapshot != connector_id:
        raise errors.PreparationDeliveryNotFoundError('Preparation Dispatch not found')
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
        raise errors.PreparationDeliveryNotFoundError('Preparation Delivery Connector not found')
    attempt = await db.scalar(select(PreparationDispatchAttempt).where(
        PreparationDispatchAttempt.dispatch_id == dispatch.id,
        PreparationDispatchAttempt.claim_token == claim_token,
        PreparationDispatchAttempt.connector_id == connector_id,
    ).with_for_update())
    if attempt is None:
        raise errors.PreparationDeliveryNotFoundError('Preparation Dispatch Attempt not found')
    if attempt.result != 'IN_PROGRESS':
        if attempt.result_fingerprint != expected:
            raise errors.PreparationDeliveryConflictError('Preparation delivery result conflicts with finalized evidence')
        return RecordResultOutcome(
            dispatch=await _projection(db, dispatch),
            attempt=_attempt_projection(attempt), replayed=True,
        )
    if dispatch.state != 'IN_PROGRESS' or dispatch.claim_token != claim_token:
        raise errors.PreparationDeliveryConflictError('Preparation delivery result is fenced')
    now = _now()
    attempt.result = delivery_result.result
    attempt.result_fingerprint = expected
    attempt.local_job_reference = delivery_result.local_job_reference
    attempt.error_kind = delivery_result.error_kind
    attempt.error_message = delivery_result.error_message[:500] if delivery_result.error_message else None
    attempt.ended_at = now
    dispatch.state = delivery_result.result
    dispatch.claim_token = None
    dispatch.claim_expires_at = None
    dispatch.last_error_kind = delivery_result.error_kind
    dispatch.last_error_message = delivery_result.error_message[:500] if delivery_result.error_message else None
    if delivery_result.result == 'RETRYABLE_FAILURE':
        dispatch.available_at = retry_available_at or now
    if delivery_result.result == 'DESTINATION_SUBMISSION_ACCEPTED':
        dispatch.terminal_at = now
    await db.commit()
    await db.refresh(dispatch)
    await db.refresh(attempt)
    logger.info(
        'Preparation dispatch result recorded',
        extra={
            'event': 'preparation_dispatch_result_recorded',
            'tenant_id': dispatch.tenant_id,
            'location_id': dispatch.location_id,
            'restaurant_order_id': dispatch.restaurant_order_id,
            'preparation_work_id': dispatch.preparation_work_id,
            'dispatch_id': dispatch.id,
            'destination_id': dispatch.destination_id,
            'attempt_id': attempt.id,
            'operation_id': dispatch.operation_id,
            'correlation_id': execution.correlation_id,
            'state': dispatch.state,
        },
    )
    return RecordResultOutcome(
        dispatch=await _projection(db, dispatch),
        attempt=_attempt_projection(attempt), replayed=False,
    )


async def create_reprint(
    db: AsyncSession, *, source_dispatch_id: int, execution: ExecutionContext,
) -> DispatchProjection:
    if execution.actor_type is not ActorType.EMPLOYEE:
        raise errors.PreparationDeliveryConflictError('Reprint requires an employee actor')
    source = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.id == source_dispatch_id,
        PreparationDispatch.tenant_id == execution.tenant_id,
    ).with_for_update())
    if source is None:
        raise errors.PreparationDeliveryNotFoundError('Preparation Dispatch not found')
    latest = await db.scalar(select(PreparationDispatch).where(
        PreparationDispatch.tenant_id == source.tenant_id,
        PreparationDispatch.preparation_work_id == source.preparation_work_id,
        PreparationDispatch.destination_id == source.destination_id,
    ).order_by(PreparationDispatch.generation.desc()).limit(1).with_for_update())
    generation = (latest.generation if latest is not None else source.generation) + 1
    now = _now()
    value = PreparationDispatch(
        tenant_id=source.tenant_id, organization_id=source.organization_id,
        location_id=source.location_id, restaurant_order_id=source.restaurant_order_id,
        preparation_work_id=source.preparation_work_id,
        preparation_area_id=source.preparation_area_id, destination_id=source.destination_id,
        operation_kind='REPRINT', generation=generation,
        operation_id=operation_id(
            tenant_id=source.tenant_id, work_id=source.preparation_work_id,
            destination_id=source.destination_id, generation=generation,
        ),
        reprint_of_dispatch_id=source.id, state='PENDING',
        payload_schema=source.payload_schema, payload_text=source.payload_text,
        payload_fingerprint=source.payload_fingerprint,
        destination_code_snapshot=source.destination_code_snapshot,
        destination_name_snapshot=source.destination_name_snapshot,
        destination_channel_snapshot=source.destination_channel_snapshot,
        connector_id_snapshot=source.connector_id_snapshot,
        connector_code_snapshot=source.connector_code_snapshot,
        connector_name_snapshot=source.connector_name_snapshot,
        local_target_key_snapshot=source.local_target_key_snapshot,
        claim_token=None, claim_expires_at=None, attempt_count=0, available_at=now,
        initiating_actor_type='EMPLOYEE', initiating_membership_id=execution.principal_id,
        initiating_principal_reference=None, correlation_id=execution.correlation_id,
        causation_id=execution.causation_id, terminal_at=None,
    )
    db.add(value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise errors.PreparationDeliveryConflictError('Concurrent reprint generation conflicted') from exc
    await db.refresh(value)
    logger.info(
        'Preparation dispatch reprint created',
        extra={
            'event': 'preparation_dispatch_reprint_created',
            'tenant_id': value.tenant_id,
            'location_id': value.location_id,
            'restaurant_order_id': value.restaurant_order_id,
            'preparation_work_id': value.preparation_work_id,
            'dispatch_id': value.id,
            'destination_id': value.destination_id,
            'operation_id': value.operation_id,
            'correlation_id': execution.correlation_id,
            'state': value.state,
        },
    )
    return await _projection(db, value)
