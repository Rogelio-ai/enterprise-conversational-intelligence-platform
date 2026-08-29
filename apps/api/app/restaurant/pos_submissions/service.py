from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    LocationPosConnection,
    PosOrderSubmission,
    PosOrderSubmissionAttempt,
    PosOrderSubmissionComponent,
    PosOrderSubmissionLine,
    ProductExternalMapping,
    RestaurantOrder,
    RestaurantOrderItem,
    RestaurantOrderItemComponent,
    RestaurantOrderPromotion,
)
from app.restaurant.integrations.pos.contracts import (
    CreateOrderComponent,
    CreateOrderItem,
    CreateOrderPromotion,
    CreateOrderRequest,
    CreateRecoveryOutcome,
    LocationScopedPosRequestContext,
)
from app.restaurant.integrations.pos.errors import PosErrorKind, PosIntegrationError
from app.restaurant.integrations.pos.ports import OrderPort, OrderRecoveryPort
from app.restaurant.pos_submissions import errors
from app.restaurant.pos_submissions.contracts import (
    PosSubmissionAttemptProjection,
    PosSubmissionProjection,
)


logger = logging.getLogger('ecip.pos_submissions')
CLAIM_LEASE = timedelta(seconds=30)
REQUEST_SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _event(name: str, *, execution: ExecutionContext, **values: object) -> None:
    logger.info(
        name.replace('_', ' ').capitalize(),
        extra={
            'event': name,
            'tenant_id': execution.tenant_id,
            'actor_type': execution.actor_type.value,
            'correlation_id': execution.correlation_id,
            **values,
        },
    )


def _actor_values(execution: ExecutionContext) -> dict[str, object]:
    return {
        'actor_type': execution.actor_type.value,
        'actor_membership_id': execution.principal_id if execution.actor_type is ActorType.EMPLOYEE else None,
        'actor_principal_reference': execution.principal_reference,
    }


def _fingerprint(request: CreateOrderRequest) -> str:
    serialized = json.dumps(
        request.model_dump(mode='json'), sort_keys=True, separators=(',', ':'), ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


async def _order_rows(
    db: AsyncSession, *, tenant_id: int, order_id: int
) -> tuple[
    RestaurantOrder,
    tuple[RestaurantOrderItem, ...],
    dict[int, tuple[RestaurantOrderItemComponent, ...]],
    dict[int, tuple[RestaurantOrderPromotion, ...]],
]:
    order = await db.scalar(
        select(RestaurantOrder).where(
            RestaurantOrder.id == order_id, RestaurantOrder.tenant_id == tenant_id
        )
    )
    if order is None:
        raise errors.PosSubmissionNotFoundError('Restaurant Order not found')
    if order.status != 'ACCEPTED':
        raise errors.PosSubmissionStateError('Only an accepted Restaurant Order may be submitted')
    items = tuple(
        (
            await db.execute(
                select(RestaurantOrderItem)
                .where(
                    RestaurantOrderItem.tenant_id == tenant_id,
                    RestaurantOrderItem.order_id == order.id,
                )
                .order_by(RestaurantOrderItem.position, RestaurantOrderItem.id)
            )
        ).scalars().all()
    )
    components: dict[int, tuple[RestaurantOrderItemComponent, ...]] = {}
    promotions: dict[int, tuple[RestaurantOrderPromotion, ...]] = {}
    for item in items:
        components[item.id] = tuple(
            (
                await db.execute(
                    select(RestaurantOrderItemComponent)
                    .where(
                        RestaurantOrderItemComponent.tenant_id == tenant_id,
                        RestaurantOrderItemComponent.order_id == order.id,
                        RestaurantOrderItemComponent.order_item_id == item.id,
                    )
                    .order_by(RestaurantOrderItemComponent.position, RestaurantOrderItemComponent.id)
                )
            ).scalars().all()
        )
        promotions[item.id] = tuple(
            (
                await db.execute(
                    select(RestaurantOrderPromotion)
                    .where(
                        RestaurantOrderPromotion.tenant_id == tenant_id,
                        RestaurantOrderPromotion.order_id == order.id,
                        RestaurantOrderPromotion.order_item_id == item.id,
                    )
                    .order_by(RestaurantOrderPromotion.application_order, RestaurantOrderPromotion.id)
                )
            ).scalars().all()
        )
    return order, items, components, promotions


async def _active_connection(
    db: AsyncSession, *, order: RestaurantOrder
) -> LocationPosConnection:
    connection = await db.scalar(
        select(LocationPosConnection).where(
            LocationPosConnection.tenant_id == order.tenant_id,
            LocationPosConnection.organization_id == order.organization_id,
            LocationPosConnection.location_id == order.location_id,
            LocationPosConnection.status == 'ACTIVE',
            LocationPosConnection.active_slot == 1,
        )
    )
    if connection is None:
        raise errors.PosSubmissionConfigurationError('Active Location POS connection not found')
    return connection


async def _external_mapping(
    db: AsyncSession, *, tenant_id: int, connector_key: str, product_id: int
) -> str:
    values = tuple(
        (
            await db.execute(
                select(ProductExternalMapping.external_product_id)
                .where(
                    ProductExternalMapping.tenant_id == tenant_id,
                    ProductExternalMapping.connector_key == connector_key,
                    ProductExternalMapping.product_id == product_id,
                )
                .limit(2)
            )
        ).scalars().all()
    )
    if len(values) != 1:
        raise errors.PosSubmissionConfigurationError(
            'Exactly one outbound POS Product mapping is required'
        )
    return values[0]


async def _new_request_and_mappings(
    db: AsyncSession,
    *,
    order: RestaurantOrder,
    items: tuple[RestaurantOrderItem, ...],
    components: dict[int, tuple[RestaurantOrderItemComponent, ...]],
    promotions: dict[int, tuple[RestaurantOrderPromotion, ...]],
    connector_key: str,
) -> tuple[CreateOrderRequest, list[tuple[RestaurantOrderItem, str]], dict[int, list[tuple[RestaurantOrderItemComponent, str]]]]:
    mapped_lines: list[tuple[RestaurantOrderItem, str]] = []
    mapped_components: dict[int, list[tuple[RestaurantOrderItemComponent, str]]] = {}
    request_items: list[CreateOrderItem] = []
    for item in items:
        external_product_id = await _external_mapping(
            db, tenant_id=order.tenant_id, connector_key=connector_key, product_id=item.product_id
        )
        mapped_lines.append((item, external_product_id))
        component_values: list[CreateOrderComponent] = []
        mapped_components[item.id] = []
        for component in components[item.id]:
            external_component_id = await _external_mapping(
                db,
                tenant_id=order.tenant_id,
                connector_key=connector_key,
                product_id=component.product_id,
            )
            mapped_components[item.id].append((component, external_component_id))
            component_values.append(
                CreateOrderComponent(
                    accepted_component_reference=str(component.id),
                    kind=component.kind,
                    product_external_id=external_component_id,
                    name=component.product_name,
                    quantity=component.quantity,
                    choice_group_name=component.choice_group_name,
                )
            )
        promotion_values = tuple(
            CreateOrderPromotion(
                accepted_promotion_reference=str(promotion.id),
                name=promotion.promotion_name,
                promotion_type=promotion.promotion_type,
                calculated_discount=promotion.calculated_discount,
            )
            for promotion in promotions[item.id]
        )
        request_items.append(
            CreateOrderItem(
                accepted_item_reference=str(item.id),
                external_line_reference=f'ecip-order-{order.id}-line-{item.id}',
                product_external_id=external_product_id,
                name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                base_amount=item.base_amount,
                discount_amount=item.discount_amount,
                line_total=item.commercial_amount,
                components=tuple(component_values),
                promotions=promotion_values,
            )
        )
    return (
        CreateOrderRequest(
            canonical_order_reference=str(order.id),
            items=tuple(request_items),
            currency=order.currency,
            subtotal=order.subtotal,
            total_discount=order.total_discount,
            payable_total=order.payable_total,
        ),
        mapped_lines,
        mapped_components,
    )


async def _request_from_frozen(
    db: AsyncSession, *, submission: PosOrderSubmission
) -> CreateOrderRequest:
    order, items, components, promotions = await _order_rows(
        db, tenant_id=submission.tenant_id, order_id=submission.restaurant_order_id
    )
    lines = tuple(
        (
            await db.execute(
                select(PosOrderSubmissionLine)
                .where(
                    PosOrderSubmissionLine.tenant_id == submission.tenant_id,
                    PosOrderSubmissionLine.submission_id == submission.id,
                )
                .order_by(PosOrderSubmissionLine.position, PosOrderSubmissionLine.id)
            )
        ).scalars().all()
    )
    lines_by_item = {line.restaurant_order_item_id: line for line in lines}
    frozen_components = tuple(
        (
            await db.execute(
                select(PosOrderSubmissionComponent)
                .where(
                    PosOrderSubmissionComponent.tenant_id == submission.tenant_id,
                    PosOrderSubmissionComponent.submission_id == submission.id,
                )
                .order_by(PosOrderSubmissionComponent.position, PosOrderSubmissionComponent.id)
            )
        ).scalars().all()
    )
    frozen_by_source = {
        component.restaurant_order_item_component_id: component
        for component in frozen_components
    }
    request_items: list[CreateOrderItem] = []
    for item in items:
        line = lines_by_item.get(item.id)
        if line is None:
            raise errors.PosSubmissionConfigurationError('Frozen POS line mapping is incomplete')
        component_values: list[CreateOrderComponent] = []
        for component in components[item.id]:
            frozen = frozen_by_source.get(component.id)
            if frozen is None:
                raise errors.PosSubmissionConfigurationError('Frozen POS component mapping is incomplete')
            component_values.append(
                CreateOrderComponent(
                    accepted_component_reference=str(component.id),
                    kind=component.kind,
                    product_external_id=frozen.external_product_id,
                    name=component.product_name,
                    quantity=component.quantity,
                    choice_group_name=component.choice_group_name,
                )
            )
        request_items.append(
            CreateOrderItem(
                accepted_item_reference=str(item.id),
                external_line_reference=line.external_line_reference,
                product_external_id=line.external_product_id,
                name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                base_amount=item.base_amount,
                discount_amount=item.discount_amount,
                line_total=item.commercial_amount,
                components=tuple(component_values),
                promotions=tuple(
                    CreateOrderPromotion(
                        accepted_promotion_reference=str(promotion.id),
                        name=promotion.promotion_name,
                        promotion_type=promotion.promotion_type,
                        calculated_discount=promotion.calculated_discount,
                    )
                    for promotion in promotions[item.id]
                ),
            )
        )
    request = CreateOrderRequest(
        canonical_order_reference=str(order.id),
        items=tuple(request_items),
        currency=order.currency,
        subtotal=order.subtotal,
        total_discount=order.total_discount,
        payable_total=order.payable_total,
    )
    if _fingerprint(request) != submission.request_fingerprint:
        raise errors.PosSubmissionStateError('Frozen POS request fingerprint does not match')
    return request


def _new_attempt(
    submission: PosOrderSubmission,
    *,
    attempt_type: str,
    token: str,
    execution: ExecutionContext,
    started_at: datetime,
) -> PosOrderSubmissionAttempt:
    actor = _actor_values(execution)
    return PosOrderSubmissionAttempt(
        tenant_id=submission.tenant_id,
        submission_id=submission.id,
        attempt_sequence=submission.attempt_count,
        attempt_type=attempt_type,
        claim_token=token,
        actor_type=actor['actor_type'],
        actor_membership_id=actor['actor_membership_id'],
        actor_principal_reference=actor['actor_principal_reference'],
        correlation_id=execution.correlation_id,
        started_at=started_at,
        ended_at=None,
        result='IN_PROGRESS',
    )


async def _projection(db: AsyncSession, submission: PosOrderSubmission) -> PosSubmissionProjection:
    attempts = tuple(
        (
            await db.execute(
                select(PosOrderSubmissionAttempt)
                .where(
                    PosOrderSubmissionAttempt.tenant_id == submission.tenant_id,
                    PosOrderSubmissionAttempt.submission_id == submission.id,
                )
                .order_by(PosOrderSubmissionAttempt.attempt_sequence, PosOrderSubmissionAttempt.id)
            )
        ).scalars().all()
    )
    return PosSubmissionProjection(
        id=submission.id,
        restaurant_order_id=submission.restaurant_order_id,
        connector_key=submission.connector_key,
        external_location_id=submission.external_location_id,
        state=submission.state,
        idempotency_key=submission.idempotency_key,
        request_fingerprint=submission.request_fingerprint,
        external_order_id=submission.external_order_id,
        external_status=submission.external_status,
        claim_expires_at=submission.claim_expires_at,
        last_error_kind=submission.last_error_kind,
        last_error_message=submission.last_error_message,
        attempts=tuple(
            PosSubmissionAttemptProjection(
                sequence=value.attempt_sequence,
                attempt_type=value.attempt_type,
                actor_type=value.actor_type,
                actor_membership_id=value.actor_membership_id,
                correlation_id=value.correlation_id,
                started_at=value.started_at,
                ended_at=value.ended_at,
                result=value.result,
                error_kind=value.error_kind,
                error_message=value.error_message,
                external_order_id=value.external_order_id,
            )
            for value in attempts
        ),
    )


async def get_submission(
    db: AsyncSession, *, tenant_id: int, order_id: int
) -> PosSubmissionProjection:
    submission = await db.scalar(
        select(PosOrderSubmission).where(
            PosOrderSubmission.tenant_id == tenant_id,
            PosOrderSubmission.restaurant_order_id == order_id,
        )
    )
    if submission is None:
        raise errors.PosSubmissionNotFoundError('POS Order Submission not found')
    return await _projection(db, submission)


async def _initialize(
    db: AsyncSession,
    *,
    order_id: int,
    execution: ExecutionContext,
) -> tuple[PosOrderSubmission, CreateOrderRequest | None, bool]:
    order, items, components, promotions = await _order_rows(
        db, tenant_id=execution.tenant_id, order_id=order_id
    )
    connection = await _active_connection(db, order=order)
    existing = await db.scalar(
        select(PosOrderSubmission).where(
            PosOrderSubmission.tenant_id == execution.tenant_id,
            PosOrderSubmission.restaurant_order_id == order.id,
            PosOrderSubmission.connector_key == connection.connector_key,
        )
    )
    if existing is not None:
        request = None if existing.state == 'ACTION_REQUIRED' else await _request_from_frozen(db, submission=existing)
        return existing, request, False
    now = _now()
    token = str(uuid4())
    actor = _actor_values(execution)
    try:
        request, mapped_lines, mapped_components = await _new_request_and_mappings(
            db,
            order=order,
            items=items,
            components=components,
            promotions=promotions,
            connector_key=connection.connector_key,
        )
    except errors.PosSubmissionConfigurationError as exc:
        submission = PosOrderSubmission(
            tenant_id=order.tenant_id,
            organization_id=order.organization_id,
            location_id=order.location_id,
            restaurant_order_id=order.id,
            connection_id=connection.id,
            connector_key=connection.connector_key,
            external_location_id=connection.external_location_id,
            stable_replay_supported=connection.stable_replay_supported,
            recovery_supported=connection.recovery_supported,
            idempotency_key=f'pos-create-v1:{order.tenant_id}:{order.id}:{connection.id}',
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=hashlib.sha256(
                f'{order.commercial_fingerprint}\x00{connection.connector_key}\x00mapping-error'.encode()
            ).hexdigest(),
            state='ACTION_REQUIRED',
            claim_token=None,
            claim_expires_at=None,
            attempt_count=1,
            last_error_kind=PosErrorKind.MAPPING.value,
            last_error_message=str(exc),
            initiated_actor_type=actor['actor_type'],
            initiated_membership_id=actor['actor_membership_id'],
            initiated_principal_reference=actor['actor_principal_reference'],
        )
        db.add(submission)
        await db.flush()
        attempt = _new_attempt(
            submission, attempt_type='CREATE', token=token, execution=execution, started_at=now
        )
        attempt.result = 'ACTION_REQUIRED'
        attempt.ended_at = now
        attempt.error_kind = PosErrorKind.MAPPING.value
        attempt.error_message = str(exc)
        db.add(attempt)
        return submission, None, True
    submission = PosOrderSubmission(
        tenant_id=order.tenant_id,
        organization_id=order.organization_id,
        location_id=order.location_id,
        restaurant_order_id=order.id,
        connection_id=connection.id,
        connector_key=connection.connector_key,
        external_location_id=connection.external_location_id,
        stable_replay_supported=connection.stable_replay_supported,
        recovery_supported=connection.recovery_supported,
        idempotency_key=f'pos-create-v1:{order.tenant_id}:{order.id}:{connection.id}',
        request_schema_version=REQUEST_SCHEMA_VERSION,
        request_fingerprint=_fingerprint(request),
        state='IN_PROGRESS',
        claim_token=token,
        claim_expires_at=now + CLAIM_LEASE,
        attempt_count=1,
        initiated_actor_type=actor['actor_type'],
        initiated_membership_id=actor['actor_membership_id'],
        initiated_principal_reference=actor['actor_principal_reference'],
    )
    db.add(submission)
    await db.flush()
    for item, external_product_id in mapped_lines:
        line = PosOrderSubmissionLine(
            tenant_id=order.tenant_id,
            restaurant_order_id=order.id,
            submission_id=submission.id,
            restaurant_order_item_id=item.id,
            position=item.position,
            external_product_id=external_product_id,
            external_line_reference=f'ecip-order-{order.id}-line-{item.id}',
        )
        db.add(line)
        await db.flush()
        for component, external_component_id in mapped_components[item.id]:
            db.add(
                PosOrderSubmissionComponent(
                    tenant_id=order.tenant_id,
                    restaurant_order_id=order.id,
                    restaurant_order_item_id=item.id,
                    submission_id=submission.id,
                    submission_line_id=line.id,
                    restaurant_order_item_component_id=component.id,
                    position=component.position,
                    external_product_id=external_component_id,
                )
            )
    db.add(_new_attempt(submission, attempt_type='CREATE', token=token, execution=execution, started_at=now))
    return submission, request, True


async def _claim_existing(
    db: AsyncSession,
    *,
    submission: PosOrderSubmission,
    execution: ExecutionContext,
    action: str,
) -> tuple[CreateOrderRequest, str] | None:
    now = _now()
    if submission.state == 'SUCCEEDED':
        return None
    if submission.state == 'IN_PROGRESS':
        if submission.claim_expires_at is not None and submission.claim_expires_at > now:
            return None
        if action not in ('submit', 'recover'):
            raise errors.PosSubmissionStateError('Expired POS claim requires recovery')
        previous = await db.scalar(
            select(PosOrderSubmissionAttempt).where(
                PosOrderSubmissionAttempt.submission_id == submission.id,
                PosOrderSubmissionAttempt.claim_token == submission.claim_token,
            )
        )
        if previous is not None and previous.result == 'IN_PROGRESS':
            previous.result = 'UNCERTAIN'
            previous.ended_at = now
            previous.error_kind = PosErrorKind.UNCERTAIN_RESULT.value
            previous.error_message = 'Claim expired after the external call boundary may have been crossed'
        attempt_type = 'STALE_RECOVERY'
        _event('pos_submission_stale_claim_reclaimed', execution=execution, submission_id=submission.id)
    elif action == 'retry' and submission.state == 'RETRYABLE_FAILURE':
        attempt_type = 'RETRY'
    elif action == 'recover' and submission.state == 'UNCERTAIN':
        attempt_type = 'RECOVER'
    else:
        raise errors.PosSubmissionStateError(
            f'POS submission in {submission.state} cannot perform {action}'
        )
    request = await _request_from_frozen(db, submission=submission)
    token = str(uuid4())
    submission.state = 'IN_PROGRESS'
    submission.claim_token = token
    submission.claim_expires_at = now + CLAIM_LEASE
    submission.attempt_count += 1
    submission.last_error_kind = None
    submission.last_error_message = None
    db.add(
        _new_attempt(
            submission,
            attempt_type=attempt_type,
            token=token,
            execution=execution,
            started_at=now,
        )
    )
    return request, attempt_type


def _error_state(exc: PosIntegrationError) -> str:
    if exc.kind is PosErrorKind.TEMPORARY_FAILURE:
        return 'RETRYABLE_FAILURE'
    if exc.kind is PosErrorKind.REJECTED:
        return 'REJECTED'
    if exc.kind is PosErrorKind.UNCERTAIN_RESULT:
        return 'UNCERTAIN'
    return 'ACTION_REQUIRED'


async def _finish(
    db: AsyncSession,
    *,
    tenant_id: int,
    submission_id: int,
    token: str,
    state: str,
    external_order=None,
    error_kind: str | None = None,
    error_message: str | None = None,
) -> PosOrderSubmission:
    submission = await db.scalar(
        select(PosOrderSubmission)
        .where(PosOrderSubmission.id == submission_id, PosOrderSubmission.tenant_id == tenant_id)
        .with_for_update()
    )
    if submission is None:
        raise errors.PosSubmissionNotFoundError('POS Order Submission not found')
    if submission.claim_token != token:
        await db.rollback()
        winner = await db.scalar(
            select(PosOrderSubmission).where(
                PosOrderSubmission.id == submission_id,
                PosOrderSubmission.tenant_id == tenant_id,
            )
        )
        if winner is None:
            raise errors.PosSubmissionNotFoundError('POS Order Submission not found')
        return winner
    now = _now()
    attempt = await db.scalar(
        select(PosOrderSubmissionAttempt).where(
            PosOrderSubmissionAttempt.submission_id == submission.id,
            PosOrderSubmissionAttempt.claim_token == token,
        )
    )
    if attempt is None or attempt.result != 'IN_PROGRESS':
        raise errors.PosSubmissionStateError('POS submission attempt is not current')
    submission.state = state
    submission.claim_token = None
    submission.claim_expires_at = None
    submission.last_error_kind = error_kind
    submission.last_error_message = error_message[:500] if error_message else None
    attempt.result = state
    attempt.ended_at = now
    attempt.error_kind = error_kind
    attempt.error_message = error_message[:500] if error_message else None
    if external_order is not None:
        submission.external_order_id = external_order.external_id
        submission.external_status = external_order.status.value
        attempt.external_order_id = external_order.external_id
    if state in ('SUCCEEDED', 'REJECTED'):
        submission.terminal_at = now
    await db.commit()
    return submission


async def execute_submission(
    db: AsyncSession,
    *,
    order_id: int,
    execution: ExecutionContext,
    adapters: Mapping[str, object],
    action: str,
) -> PosSubmissionProjection:
    if action not in ('submit', 'retry', 'recover'):
        raise ValueError('Unsupported POS submission action')
    if execution.actor_type is not ActorType.EMPLOYEE:
        raise errors.PosSubmissionStateError('This POS endpoint requires an employee actor')
    try:
        if action == 'submit':
            submission, request, created = await _initialize(
                db, order_id=order_id, execution=execution
            )
            if submission.id is None:
                raise RuntimeError('POS submission was not persisted')
            if submission.state == 'ACTION_REQUIRED':
                await db.commit()
                return await _projection(db, submission)
            if created:
                assert request is not None
                attempt_type = 'CREATE'
            else:
                locked = await db.scalar(
                    select(PosOrderSubmission)
                    .where(PosOrderSubmission.id == submission.id)
                    .with_for_update()
                )
                claimed = await _claim_existing(
                    db, submission=locked, execution=execution, action=action
                )
                if claimed is None:
                    await db.commit()
                    return await _projection(db, locked)
                request, attempt_type = claimed
        else:
            submission = await db.scalar(
                select(PosOrderSubmission)
                .where(
                    PosOrderSubmission.tenant_id == execution.tenant_id,
                    PosOrderSubmission.restaurant_order_id == order_id,
                )
                .with_for_update()
            )
            if submission is None:
                raise errors.PosSubmissionNotFoundError('POS Order Submission not found')
            claimed = await _claim_existing(
                db, submission=submission, execution=execution, action=action
            )
            if claimed is None:
                await db.commit()
                return await _projection(db, submission)
            request, attempt_type = claimed
        token = submission.claim_token
        submission_id = submission.id
        connector_key = submission.connector_key
        context = LocationScopedPosRequestContext(
            tenant_id=submission.tenant_id,
            location_id=submission.location_id,
            connector_key=connector_key,
            correlation_id=execution.correlation_id or f'pos-submission-{submission.id}',
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner = await db.scalar(
            select(PosOrderSubmission).where(
                PosOrderSubmission.tenant_id == execution.tenant_id,
                PosOrderSubmission.restaurant_order_id == order_id,
            )
        )
        if winner is None:
            raise
        return await _projection(db, winner)
    except Exception:
        await db.rollback()
        raise

    assert token is not None
    adapter = adapters.get(connector_key)
    if adapter is None or not isinstance(adapter, OrderPort):
        submission = await _finish(
            db,
            tenant_id=execution.tenant_id,
            submission_id=submission_id,
            token=token,
            state='ACTION_REQUIRED',
            error_kind=PosErrorKind.UNSUPPORTED_CAPABILITY.value,
            error_message='Configured POS adapter is unavailable',
        )
        return await _projection(db, submission)

    try:
        _event('pos_external_call_started', execution=execution, submission_id=submission_id, operation=attempt_type)
        if action == 'recover' or attempt_type == 'STALE_RECOVERY':
            connection_recovery = submission.recovery_supported and isinstance(adapter, OrderRecoveryPort)
            if connection_recovery:
                recovered = await adapter.recover_create_order(
                    context,
                    idempotency_key=submission.idempotency_key,
                    request_fingerprint=submission.request_fingerprint,
                )
                if recovered.outcome is CreateRecoveryOutcome.RECOVERED_SUCCESS:
                    state, external_order = 'SUCCEEDED', recovered.order
                elif recovered.outcome is CreateRecoveryOutcome.DEFINITE_ABSENCE:
                    state, external_order = 'RETRYABLE_FAILURE', None
                elif recovered.outcome is CreateRecoveryOutcome.UNSUPPORTED:
                    state, external_order = 'ACTION_REQUIRED', None
                else:
                    state, external_order = 'UNCERTAIN', None
            else:
                if not submission.stable_replay_supported:
                    finished = await _finish(
                        db,
                        tenant_id=execution.tenant_id,
                        submission_id=submission_id,
                        token=token,
                        state='ACTION_REQUIRED',
                        error_kind=PosErrorKind.UNSUPPORTED_CAPABILITY.value,
                        error_message='Connector has no safe create recovery capability',
                    )
                    return await _projection(db, finished)
                external_order = await adapter.create_order(
                    context,
                    request=request,
                    idempotency_key=submission.idempotency_key,
                    request_fingerprint=submission.request_fingerprint,
                )
                state = 'SUCCEEDED'
        else:
            external_order = await adapter.create_order(
                context,
                request=request,
                idempotency_key=submission.idempotency_key,
                request_fingerprint=submission.request_fingerprint,
            )
            state = 'SUCCEEDED'
        finished = await _finish(
            db,
            tenant_id=execution.tenant_id,
            submission_id=submission_id,
            token=token,
            state=state,
            external_order=external_order,
            error_kind=(PosErrorKind.UNSUPPORTED_CAPABILITY.value if state == 'ACTION_REQUIRED' else None),
            error_message=('POS create recovery is unsupported' if state == 'ACTION_REQUIRED' else None),
        )
    except PosIntegrationError as exc:
        state = _error_state(exc)
        finished = await _finish(
            db,
            tenant_id=execution.tenant_id,
            submission_id=submission_id,
            token=token,
            state=state,
            error_kind=exc.kind.value,
            error_message=str(exc),
        )
    except Exception as exc:
        finished = await _finish(
            db,
            tenant_id=execution.tenant_id,
            submission_id=submission_id,
            token=token,
            state='UNCERTAIN',
            error_kind=PosErrorKind.UNCERTAIN_RESULT.value,
            error_message=f'Unexpected failure after the POS call boundary: {type(exc).__name__}',
        )
    _event(
        f'pos_submission_{finished.state.lower()}',
        execution=execution,
        submission_id=finished.id,
        connector_key=finished.connector_key,
    )
    return await _projection(db, finished)
