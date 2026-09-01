from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_DOWN

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from app.core.execution import ActorType, ExecutionContext
from app.models import (
    Conversation,
    DinerSession,
    OrderDraft,
    OrderDraftItem,
    RestaurantCheck,
    RestaurantCheckAllocation,
    RestaurantCheckCommand,
    RestaurantCheckGratuity,
    RestaurantCheckMember,
    RestaurantCheckVersion,
    RestaurantOrder,
    RestaurantOrderItem,
    RestaurantServiceSession,
)
from app.restaurant.checks import errors
from app.restaurant.checks.contracts import (
    CheckDinerGroup,
    CheckOrderLine,
    CheckProjection,
    CheckResourceGroup,
    EligibleDinerConsumption,
    TableBalanceProjection,
)


ZERO = Decimal('0.0000')
MINOR_UNIT = Decimal('0.01')
ROUNDING_POLICY = 'CURRENCY_MINOR_UNIT_HALF_DOWN_V1'
FINGERPRINT_SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal('0.0001')), 'f')


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _actor_values(context: ExecutionContext, prefix: str) -> dict[str, object]:
    return {
        f'{prefix}_actor_type': context.actor_type.value,
        f'{prefix}_actor_id': context.principal_id,
        f'{prefix}_actor_reference': context.principal_reference,
    }


def _actor_scope(context: ExecutionContext) -> str:
    identity = str(context.principal_id) if context.principal_id is not None else context.principal_reference
    return f'{context.actor_type.value}:{identity}'


def _raise_concurrency_conflict(exc: OperationalError) -> None:
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise errors.CheckVersionConflictError(
            'Concurrent Restaurant Check command lost serialization'
        ) from exc
    raise exc


async def ensure_ordering_allowed(db: AsyncSession, *, tenant_id: int, diner_session_id: int) -> None:
    member = await db.scalar(
        select(RestaurantCheckMember.id).where(
            RestaurantCheckMember.tenant_id == tenant_id,
            RestaurantCheckMember.diner_session_id == diner_session_id,
            RestaurantCheckMember.active_slot == 1,
        )
    )
    if member is not None:
        raise errors.OrderingBlockedError()


async def _lock_diners(
    db: AsyncSession, *, tenant_id: int, diner_ids: tuple[int, ...]
) -> tuple[tuple[RestaurantServiceSession, ...], tuple[DinerSession, ...], tuple[Conversation, ...]]:
    identities = tuple(
        (await db.execute(
            select(DinerSession.id, DinerSession.service_session_id, DinerSession.conversation_id)
            .where(DinerSession.tenant_id == tenant_id, DinerSession.id.in_(diner_ids or (-1,)))
            .order_by(DinerSession.id)
        )).all()
    )
    if len(identities) != len(diner_ids):
        raise errors.CheckNotFoundError('Selected diner was not found')
    session_ids = tuple(sorted({row.service_session_id for row in identities}))
    sessions = tuple((await db.execute(
        select(RestaurantServiceSession)
        .where(RestaurantServiceSession.tenant_id == tenant_id, RestaurantServiceSession.id.in_(session_ids))
        .order_by(RestaurantServiceSession.id).with_for_update()
    )).scalars().all())
    diners = tuple((await db.execute(
        select(DinerSession)
        .where(DinerSession.tenant_id == tenant_id, DinerSession.id.in_(diner_ids))
        .order_by(DinerSession.id).with_for_update()
    )).scalars().all())
    conversation_ids = tuple(sorted(row.conversation_id for row in diners))
    conversations = tuple((await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id, Conversation.id.in_(conversation_ids))
        .order_by(Conversation.id).with_for_update()
    )).scalars().all())
    if (
        len(sessions) != len(session_ids)
        or len(diners) != len(diner_ids)
        or len(conversations) != len(conversation_ids)
        or any(value.status != 'OPEN' or value.open_slot != 1 for value in sessions)
        or any(value.status != 'ACTIVE' or value.active_slot != 1 for value in diners)
        or any(value.status != 'ACTIVE' for value in conversations)
    ):
        raise errors.CheckNotFoundError('Selected diner context is not active')
    scopes = {(value.tenant_id, value.organization_id, value.location_id) for value in diners}
    if len(scopes) != 1:
        raise errors.CrossLocationCheckError()
    return sessions, diners, conversations


async def _validate_drafts(db: AsyncSession, diners: tuple[DinerSession, ...]) -> None:
    conversation_ids = tuple(value.conversation_id for value in diners)
    drafts = tuple((await db.execute(
        select(OrderDraft)
        .where(OrderDraft.conversation_id.in_(conversation_ids), OrderDraft.status == 'OPEN', OrderDraft.current_slot == 1)
        .order_by(OrderDraft.id).with_for_update()
    )).scalars().all())
    if not drafts:
        return
    counts = dict((await db.execute(
        select(OrderDraftItem.draft_id, func.count(OrderDraftItem.id))
        .where(OrderDraftItem.draft_id.in_(tuple(value.id for value in drafts)))
        .group_by(OrderDraftItem.draft_id)
    )).all())
    if any(int(counts.get(value.id, 0)) > 0 for value in drafts):
        raise errors.DinerActiveDraftError()


async def _active_membership_conflict(db: AsyncSession, diners: tuple[DinerSession, ...]) -> None:
    conflict = await db.scalar(
        select(RestaurantCheckMember.id)
        .where(
            RestaurantCheckMember.tenant_id == diners[0].tenant_id,
            RestaurantCheckMember.diner_session_id.in_(tuple(value.id for value in diners)),
            RestaurantCheckMember.active_slot == 1,
        )
        .order_by(RestaurantCheckMember.id).with_for_update()
    )
    if conflict is not None:
        raise errors.DinerAlreadyAssignedError()


async def _eligible_orders(
    db: AsyncSession, diners: tuple[DinerSession, ...]
) -> tuple[RestaurantOrder, ...]:
    order_ids = tuple(value.id for value in diners)
    allocated = exists().where(
        RestaurantCheckAllocation.tenant_id == RestaurantOrder.tenant_id,
        RestaurantCheckAllocation.restaurant_order_id == RestaurantOrder.id,
        RestaurantCheckAllocation.ownership_slot == 1,
    )
    return tuple((await db.execute(
        select(RestaurantOrder)
        .where(
            RestaurantOrder.tenant_id == diners[0].tenant_id,
            RestaurantOrder.diner_session_id.in_(order_ids),
            RestaurantOrder.status == 'ACCEPTED',
            ~allocated,
        )
        .order_by(RestaurantOrder.id).with_for_update()
    )).scalars().all())


def _snapshot_payload(
    check: RestaurantCheck,
    members: tuple[RestaurantCheckMember, ...],
    allocations: tuple[RestaurantCheckAllocation, ...],
    *, gratuity_type: str | None,
    gratuity_input: Decimal,
    gratuity_basis: Decimal,
    gratuity_amount: Decimal,
) -> dict:
    return {
        'schema_version': FINGERPRINT_SCHEMA_VERSION,
        'check_id': check.id,
        'version': check.version,
        'tenant_id': check.tenant_id,
        'organization_id': check.organization_id,
        'location_id': check.location_id,
        'currency': check.currency,
        'controller': {
            'actor_type': check.controller_actor_type,
            'actor_id': check.controller_actor_id,
            'actor_reference': check.controller_actor_reference,
            'diner_session_id': check.controller_diner_session_id,
        },
        'member_ids': sorted(value.diner_session_id for value in members if value.active_slot == 1),
        'allocations': [
            {
                'allocation_id': value.id,
                'restaurant_order_id': value.restaurant_order_id,
                'commercial_fingerprint': value.accepted_commercial_fingerprint,
                'accepted_payable_amount': _money(value.accepted_payable_amount),
                'state': value.state,
            }
            for value in sorted(allocations, key=lambda item: (item.restaurant_order_id, item.id))
            if value.state != 'RELEASED'
        ],
        'consumption_total': _money(check.consumption_total),
        'gratuity': {
            'type': gratuity_type,
            'input': _money(gratuity_input),
            'basis': _money(gratuity_basis),
            'rounding_policy': ROUNDING_POLICY,
            'amount': _money(gratuity_amount),
        },
        'liability_total': _money(check.liability_total),
    }


async def _write_version(
    db: AsyncSession,
    check: RestaurantCheck,
    *,
    context: ExecutionContext,
    gratuity_type: str | None = None,
    gratuity_input: Decimal = ZERO,
) -> None:
    members = tuple((await db.execute(
        select(RestaurantCheckMember).where(RestaurantCheckMember.check_id == check.id).order_by(RestaurantCheckMember.diner_session_id)
    )).scalars().all())
    allocations = tuple((await db.execute(
        select(RestaurantCheckAllocation).where(RestaurantCheckAllocation.check_id == check.id).order_by(RestaurantCheckAllocation.restaurant_order_id)
    )).scalars().all())
    gratuity_basis = check.consumption_total
    payload = _snapshot_payload(
        check, members, allocations,
        gratuity_type=gratuity_type,
        gratuity_input=gratuity_input,
        gratuity_basis=gratuity_basis,
        gratuity_amount=check.gratuity_total,
    )
    fingerprint = _sha(payload)
    check.current_fingerprint = fingerprint
    now = _now()
    db.add(RestaurantCheckVersion(
        tenant_id=check.tenant_id, organization_id=check.organization_id, location_id=check.location_id,
        check_id=check.id, version=check.version, schema_version=FINGERPRINT_SCHEMA_VERSION,
        currency=check.currency,
        member_snapshot={
            'member_ids': payload['member_ids'],
            'controller': payload['controller'],
        },
        allocation_snapshot={'allocations': payload['allocations']},
        gratuity_snapshot=payload['gratuity'], consumption_total=check.consumption_total,
        gratuity_amount=check.gratuity_total, liability_total=check.liability_total,
        fingerprint=fingerprint, actor_type=context.actor_type.value, actor_id=context.principal_id,
        actor_reference=context.principal_reference, recorded_at=now,
    ))


async def _command_replay(
    db: AsyncSession, *, context: ExecutionContext, idempotency_key: str, operation: str, request: object
) -> RestaurantCheckCommand | None:
    request_fingerprint = _sha(request)
    command = await db.scalar(select(RestaurantCheckCommand).where(
        RestaurantCheckCommand.tenant_id == context.tenant_id,
        RestaurantCheckCommand.actor_scope == _actor_scope(context),
        RestaurantCheckCommand.idempotency_key == idempotency_key,
    ).with_for_update())
    if command is not None and (command.operation != operation or command.request_fingerprint != request_fingerprint):
        raise errors.CheckIdempotencyConflictError()
    return command


def _record_command(
    db: AsyncSession, *, context: ExecutionContext, idempotency_key: str, operation: str,
    request: object, check: RestaurantCheck,
) -> None:
    db.add(RestaurantCheckCommand(
        tenant_id=context.tenant_id, check_id=check.id, actor_scope=_actor_scope(context),
        idempotency_key=idempotency_key, operation=operation, request_fingerprint=_sha(request),
        result_version=check.version,
    ))


async def create_check(
    db: AsyncSession,
    *,
    context: ExecutionContext,
    diner_ids: tuple[int, ...],
    controller_diner_session_id: int | None,
    idempotency_key: str,
    eligible_members_only: bool = False,
    allow_controller_without_order: bool = False,
    _deadlock_retried: bool = False,
) -> tuple[CheckProjection, bool]:
    selected = tuple(sorted(set(diner_ids)))
    request = {
        'diner_ids': selected,
        'controller_diner_session_id': controller_diner_session_id,
        'eligible_members_only': eligible_members_only,
        'allow_controller_without_order': allow_controller_without_order,
    }
    try:
        replay = await _command_replay(db, context=context, idempotency_key=idempotency_key, operation='CREATE', request=request)
        if replay is not None:
            await db.commit()
            return await get_check(db, tenant_id=context.tenant_id, check_id=replay.check_id), True
        _, locked_diners, _ = await _lock_diners(
            db, tenant_id=context.tenant_id, diner_ids=selected
        )
        if controller_diner_session_id is not None and controller_diner_session_id not in selected:
            raise errors.CheckPermissionError('Diner controller must participate in the check')
        orders = await _eligible_orders(db, locked_diners)
        if not orders:
            raise errors.NoEligibleConsumptionError()
        member_ids = {value.id for value in locked_diners}
        if eligible_members_only:
            member_ids = {value.diner_session_id for value in orders}
            if controller_diner_session_id is not None:
                member_ids.add(controller_diner_session_id)
        diners = tuple(value for value in locked_diners if value.id in member_ids)
        await _validate_drafts(db, diners)
        await _active_membership_conflict(db, diners)
        by_diner = {value.id: 0 for value in diners}
        for order in orders:
            if order.diner_session_id in by_diner:
                by_diner[order.diner_session_id] += 1
        if any(
            count == 0 and not (
                allow_controller_without_order and diner_id == controller_diner_session_id
            )
            for diner_id, count in by_diner.items()
        ):
            raise errors.NoEligibleConsumptionError()
        currencies = {value.currency for value in orders}
        if len(currencies) != 1:
            raise errors.CrossLocationCheckError('Selected consumption does not share one currency')
        now = _now()
        consumption_total = sum((value.payable_total for value in orders), ZERO)
        check = RestaurantCheck(
            tenant_id=context.tenant_id, organization_id=diners[0].organization_id,
            location_id=diners[0].location_id, currency=next(iter(currencies)), status='OPEN', version=1,
            current_fingerprint='0' * 64, fingerprint_schema_version=FINGERPRINT_SCHEMA_VERSION,
            consumption_total=consumption_total, gratuity_total=ZERO, liability_total=consumption_total,
            controller_actor_type=context.actor_type.value, controller_actor_id=context.principal_id,
            controller_actor_reference=context.principal_reference,
            controller_diner_session_id=controller_diner_session_id,
            created_actor_type=context.actor_type.value, created_actor_id=context.principal_id,
            created_actor_reference=context.principal_reference,
        )
        db.add(check)
        await db.flush()
        for diner in diners:
            db.add(RestaurantCheckMember(
                tenant_id=check.tenant_id, organization_id=check.organization_id, location_id=check.location_id,
                check_id=check.id, diner_session_id=diner.id, service_session_id=diner.service_session_id,
                resource_id=diner.resource_id, conversation_id=diner.conversation_id,
                relationship='CONTROLLER' if diner.id == controller_diner_session_id else 'INCLUDED',
                active_slot=1, acquired_at=now, acquired_version=1, **_actor_values(context, 'acquired'),
            ))
        await db.flush()
        for order in orders:
            db.add(RestaurantCheckAllocation(
                tenant_id=check.tenant_id, organization_id=check.organization_id, location_id=check.location_id,
                check_id=check.id, restaurant_order_id=order.id, source_diner_session_id=order.diner_session_id,
                source_service_session_id=order.service_session_id, source_resource_id=order.resource_id,
                source_conversation_id=order.conversation_id, accepted_payable_amount=order.payable_total,
                accepted_currency=order.currency, accepted_commercial_fingerprint=order.commercial_fingerprint,
                state='CLAIMED', ownership_slot=1, claimed_at=now, claimed_version=1,
                **_actor_values(context, 'claimed'),
            ))
        await db.flush()
        await _write_version(db, check, context=context)
        _record_command(db, context=context, idempotency_key=idempotency_key, operation='CREATE', request=request, check=check)
        await db.commit()
    except OperationalError as exc:
        await db.rollback()
        if not _deadlock_retried and exc.orig.args and exc.orig.args[0] == 1213:
            return await create_check(
                db, context=context, diner_ids=diner_ids,
                controller_diner_session_id=controller_diner_session_id,
                idempotency_key=idempotency_key,
                eligible_members_only=eligible_members_only,
                allow_controller_without_order=allow_controller_without_order,
                _deadlock_retried=True,
            )
        raise
    except Exception:
        await db.rollback()
        raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check.id), False


async def create_individual_check(
    db: AsyncSession, *, context: ExecutionContext, diner_session_id: int, idempotency_key: str
) -> tuple[CheckProjection, bool]:
    return await create_check(
        db, context=context, diner_ids=(diner_session_id,),
        controller_diner_session_id=diner_session_id, idempotency_key=idempotency_key,
    )


async def create_global_table_check(
    db: AsyncSession, *, context: ExecutionContext, service_session_id: int,
    controller_diner_session_id: int | None, idempotency_key: str,
) -> tuple[CheckProjection, bool]:
    session = await db.scalar(select(RestaurantServiceSession).where(
        RestaurantServiceSession.id == service_session_id,
        RestaurantServiceSession.tenant_id == context.tenant_id,
        RestaurantServiceSession.status == 'OPEN',
        RestaurantServiceSession.open_slot == 1,
    ).with_for_update())
    if session is None:
        raise errors.CheckNotFoundError('Service Session not found')
    diner_ids = tuple((await db.execute(
        select(DinerSession.id).where(
            DinerSession.tenant_id == context.tenant_id,
            DinerSession.service_session_id == service_session_id,
            DinerSession.active_slot == 1,
        ).order_by(DinerSession.id)
    )).scalars().all())
    if not diner_ids:
        raise errors.NoEligibleConsumptionError()
    return await create_check(
        db, context=context, diner_ids=diner_ids,
        controller_diner_session_id=controller_diner_session_id,
        idempotency_key=idempotency_key,
        eligible_members_only=True,
        allow_controller_without_order=True,
    )


async def _locked_check(db: AsyncSession, *, tenant_id: int, check_id: int, expected_version: int) -> RestaurantCheck:
    check = await db.scalar(select(RestaurantCheck).where(
        RestaurantCheck.id == check_id, RestaurantCheck.tenant_id == tenant_id,
    ).with_for_update())
    if check is None:
        raise errors.CheckNotFoundError()
    if check.version != expected_version:
        raise errors.CheckVersionConflictError()
    if check.status != 'OPEN':
        raise errors.CheckNotModifiableError()
    return check


def _authorize_controller(check: RestaurantCheck, context: ExecutionContext) -> None:
    if context.actor_type == ActorType.EMPLOYEE:
        return
    if context.actor_type != ActorType.DINER or context.principal_id != check.controller_diner_session_id:
        raise errors.CheckPermissionError()


async def add_member(
    db: AsyncSession, *, context: ExecutionContext, check_id: int, diner_session_id: int,
    expected_version: int, idempotency_key: str,
) -> tuple[CheckProjection, bool]:
    request = {'check_id': check_id, 'diner_session_id': diner_session_id, 'expected_version': expected_version}
    try:
        replay = await _command_replay(db, context=context, idempotency_key=idempotency_key, operation='ADD_MEMBER', request=request)
        if replay:
            await db.commit(); return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), True
        check = await _locked_check(db, tenant_id=context.tenant_id, check_id=check_id, expected_version=expected_version)
        _authorize_controller(check, context)
        _, diners, _ = await _lock_diners(db, tenant_id=context.tenant_id, diner_ids=(diner_session_id,))
        diner = diners[0]
        if (diner.organization_id, diner.location_id) != (check.organization_id, check.location_id):
            raise errors.CrossLocationCheckError()
        await _validate_drafts(db, diners)
        await _active_membership_conflict(db, diners)
        orders = await _eligible_orders(db, diners)
        if not orders:
            raise errors.NoEligibleConsumptionError()
        if any(value.currency != check.currency for value in orders):
            raise errors.CrossLocationCheckError('Selected consumption currency differs')
        now = _now(); check.version += 1
        db.add(RestaurantCheckMember(
            tenant_id=check.tenant_id, organization_id=check.organization_id, location_id=check.location_id,
            check_id=check.id, diner_session_id=diner.id, service_session_id=diner.service_session_id,
            resource_id=diner.resource_id, conversation_id=diner.conversation_id, relationship='INCLUDED',
            active_slot=1, acquired_at=now, acquired_version=check.version, **_actor_values(context, 'acquired'),
        ))
        await db.flush()
        for order in orders:
            db.add(RestaurantCheckAllocation(
                tenant_id=check.tenant_id, organization_id=check.organization_id, location_id=check.location_id,
                check_id=check.id, restaurant_order_id=order.id, source_diner_session_id=order.diner_session_id,
                source_service_session_id=order.service_session_id, source_resource_id=order.resource_id,
                source_conversation_id=order.conversation_id, accepted_payable_amount=order.payable_total,
                accepted_currency=order.currency, accepted_commercial_fingerprint=order.commercial_fingerprint,
                state='CLAIMED', ownership_slot=1, claimed_at=now, claimed_version=check.version,
                **_actor_values(context, 'claimed'),
            ))
        check.consumption_total += sum((value.payable_total for value in orders), ZERO)
        check.liability_total = check.consumption_total + check.gratuity_total
        await db.flush(); await _write_version(db, check, context=context)
        _record_command(db, context=context, idempotency_key=idempotency_key, operation='ADD_MEMBER', request=request, check=check)
        await db.commit()
    except OperationalError as exc:
        await db.rollback(); _raise_concurrency_conflict(exc)
    except Exception:
        await db.rollback(); raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), False


async def remove_member(
    db: AsyncSession, *, context: ExecutionContext, check_id: int, diner_session_id: int,
    expected_version: int, idempotency_key: str, reason: str,
) -> tuple[CheckProjection, bool]:
    request = {'check_id': check_id, 'diner_session_id': diner_session_id, 'expected_version': expected_version, 'reason': reason}
    try:
        replay = await _command_replay(db, context=context, idempotency_key=idempotency_key, operation='REMOVE_MEMBER', request=request)
        if replay:
            await db.commit(); return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), True
        check = await _locked_check(db, tenant_id=context.tenant_id, check_id=check_id, expected_version=expected_version)
        _authorize_controller(check, context)
        if diner_session_id == check.controller_diner_session_id:
            raise errors.CheckControllerTransferRequiredError()
        diner = await db.scalar(select(DinerSession).where(DinerSession.id == diner_session_id, DinerSession.tenant_id == context.tenant_id).with_for_update())
        member = await db.scalar(select(RestaurantCheckMember).where(
            RestaurantCheckMember.check_id == check.id, RestaurantCheckMember.diner_session_id == diner_session_id,
            RestaurantCheckMember.active_slot == 1,
        ).with_for_update())
        if diner is None or member is None:
            raise errors.CheckNotFoundError('Active Check member not found')
        allocations = tuple((await db.execute(select(RestaurantCheckAllocation).where(
            RestaurantCheckAllocation.check_id == check.id,
            RestaurantCheckAllocation.source_diner_session_id == diner_session_id,
            RestaurantCheckAllocation.ownership_slot == 1,
        ).order_by(RestaurantCheckAllocation.id).with_for_update())).scalars().all())
        if any(value.state != 'CLAIMED' for value in allocations):
            raise errors.CheckNotModifiableError('Member has financially non-releasable allocations')
        now = _now(); check.version += 1
        member.active_slot = None; member.released_at = now; member.release_reason = reason; member.released_version = check.version
        for key, value in _actor_values(context, 'released').items(): setattr(member, key, value)
        released_total = ZERO
        for allocation in allocations:
            released_total += allocation.accepted_payable_amount
            allocation.state = 'RELEASED'; allocation.ownership_slot = None; allocation.released_at = now
            allocation.release_reason = reason; allocation.released_version = check.version
            for key, value in _actor_values(context, 'released').items(): setattr(allocation, key, value)
        check.consumption_total -= released_total; check.liability_total = check.consumption_total + check.gratuity_total
        await _write_version(db, check, context=context)
        _record_command(db, context=context, idempotency_key=idempotency_key, operation='REMOVE_MEMBER', request=request, check=check)
        await db.commit()
    except OperationalError as exc:
        await db.rollback(); _raise_concurrency_conflict(exc)
    except Exception:
        await db.rollback(); raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), False


async def transfer_controller(
    db: AsyncSession, *, context: ExecutionContext, check_id: int,
    diner_session_id: int, expected_version: int, idempotency_key: str,
) -> tuple[CheckProjection, bool]:
    if context.actor_type != ActorType.EMPLOYEE:
        raise errors.CheckPermissionError('Only authorized staff may transfer Check control')
    request = {
        'check_id': check_id,
        'diner_session_id': diner_session_id,
        'expected_version': expected_version,
    }
    try:
        replay = await _command_replay(
            db, context=context, idempotency_key=idempotency_key,
            operation='TRANSFER_CONTROLLER', request=request,
        )
        if replay:
            await db.commit()
            return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), True
        check = await _locked_check(
            db, tenant_id=context.tenant_id, check_id=check_id,
            expected_version=expected_version,
        )
        members = tuple((await db.execute(
            select(RestaurantCheckMember).where(
                RestaurantCheckMember.check_id == check.id,
                RestaurantCheckMember.active_slot == 1,
            ).order_by(RestaurantCheckMember.diner_session_id).with_for_update()
        )).scalars().all())
        target = next(
            (value for value in members if value.diner_session_id == diner_session_id),
            None,
        )
        if target is None:
            raise errors.CheckNotFoundError('Target controller is not an active Check member')
        if check.controller_diner_session_id == diner_session_id:
            raise errors.CheckNotModifiableError('Target diner already controls this Check')
        for member in members:
            member.relationship = (
                'CONTROLLER' if member.diner_session_id == diner_session_id else 'INCLUDED'
            )
        check.version += 1
        check.controller_actor_type = ActorType.DINER.value
        check.controller_actor_id = diner_session_id
        check.controller_actor_reference = None
        check.controller_diner_session_id = diner_session_id
        await _write_version(db, check, context=context)
        _record_command(
            db, context=context, idempotency_key=idempotency_key,
            operation='TRANSFER_CONTROLLER', request=request, check=check,
        )
        await db.commit()
    except OperationalError as exc:
        await db.rollback()
        _raise_concurrency_conflict(exc)
    except Exception:
        await db.rollback()
        raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), False


async def update_gratuity(
    db: AsyncSession, *, context: ExecutionContext, check_id: int, expected_version: int,
    input_type: str, input_value: Decimal, idempotency_key: str,
) -> tuple[CheckProjection, bool]:
    if isinstance(input_value, float) or not isinstance(input_value, Decimal) or not input_value.is_finite() or input_value < 0:
        raise ValueError('Gratuity input must be a non-negative exact Decimal')
    if input_type not in ('PERCENTAGE', 'FIXED_AMOUNT'):
        raise ValueError('Unsupported gratuity input type')
    request = {'check_id': check_id, 'expected_version': expected_version, 'input_type': input_type, 'input_value': _money(input_value)}
    try:
        replay = await _command_replay(db, context=context, idempotency_key=idempotency_key, operation='GRATUITY', request=request)
        if replay:
            await db.commit(); return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), True
        check = await _locked_check(db, tenant_id=context.tenant_id, check_id=check_id, expected_version=expected_version)
        _authorize_controller(check, context)
        amount = ((check.consumption_total * input_value) / Decimal('100') if input_type == 'PERCENTAGE' else input_value).quantize(MINOR_UNIT, rounding=ROUND_HALF_DOWN)
        check.version += 1; check.gratuity_total = amount; check.liability_total = check.consumption_total + amount
        db.add(RestaurantCheckGratuity(
            tenant_id=check.tenant_id, organization_id=check.organization_id, location_id=check.location_id,
            check_id=check.id, check_version=check.version, input_type=input_type, input_value=input_value,
            calculation_basis=check.consumption_total, calculated_amount=amount, currency=check.currency,
            rounding_policy_id=ROUNDING_POLICY, actor_type=context.actor_type.value,
            actor_id=context.principal_id, actor_reference=context.principal_reference, elected_at=_now(),
        ))
        await db.flush(); await _write_version(db, check, context=context, gratuity_type=input_type, gratuity_input=input_value)
        _record_command(db, context=context, idempotency_key=idempotency_key, operation='GRATUITY', request=request, check=check)
        await db.commit()
    except OperationalError as exc:
        await db.rollback(); _raise_concurrency_conflict(exc)
    except Exception:
        await db.rollback(); raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), False


async def _verify_complete(db: AsyncSession, check: RestaurantCheck) -> None:
    diner_ids = tuple((await db.execute(select(RestaurantCheckMember.diner_session_id).where(
        RestaurantCheckMember.check_id == check.id, RestaurantCheckMember.active_slot == 1,
    ).order_by(RestaurantCheckMember.diner_session_id))).scalars().all())
    order_ids = set((await db.execute(select(RestaurantOrder.id).where(
        RestaurantOrder.tenant_id == check.tenant_id, RestaurantOrder.diner_session_id.in_(diner_ids or (-1,)),
        RestaurantOrder.status == 'ACCEPTED',
    ).order_by(RestaurantOrder.id).with_for_update())).scalars().all())
    allocation_ids = set((await db.execute(select(RestaurantCheckAllocation.restaurant_order_id).where(
        RestaurantCheckAllocation.check_id == check.id, RestaurantCheckAllocation.ownership_slot == 1,
    ).order_by(RestaurantCheckAllocation.restaurant_order_id).with_for_update())).scalars().all())
    if order_ids != allocation_ids:
        raise errors.CheckAllocationIncompleteError()


async def freeze_check(
    db: AsyncSession, *, context: ExecutionContext, check_id: int, expected_version: int, idempotency_key: str,
) -> tuple[CheckProjection, bool]:
    request = {'check_id': check_id, 'expected_version': expected_version}
    try:
        replay = await _command_replay(db, context=context, idempotency_key=idempotency_key, operation='FREEZE', request=request)
        if replay:
            await db.commit(); return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), True
        check = await _locked_check(db, tenant_id=context.tenant_id, check_id=check_id, expected_version=expected_version)
        _authorize_controller(check, context)
        member_ids = tuple((await db.execute(select(RestaurantCheckMember.diner_session_id).where(
            RestaurantCheckMember.check_id == check.id, RestaurantCheckMember.active_slot == 1,
        ).order_by(RestaurantCheckMember.diner_session_id))).scalars().all())
        _, diners, _ = await _lock_diners(db, tenant_id=context.tenant_id, diner_ids=member_ids)
        await _validate_drafts(db, diners); await _verify_complete(db, check)
        check.status = 'FROZEN'; check.frozen_at = _now()
        for key, value in _actor_values(context, 'frozen').items(): setattr(check, key, value)
        _record_command(db, context=context, idempotency_key=idempotency_key, operation='FREEZE', request=request, check=check)
        await db.commit()
    except OperationalError as exc:
        await db.rollback(); _raise_concurrency_conflict(exc)
    except Exception:
        await db.rollback(); raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), False


async def cancel_check(
    db: AsyncSession, *, context: ExecutionContext, check_id: int, expected_version: int,
    idempotency_key: str, reason: str,
) -> tuple[CheckProjection, bool]:
    request = {'check_id': check_id, 'expected_version': expected_version, 'reason': reason}
    try:
        replay = await _command_replay(db, context=context, idempotency_key=idempotency_key, operation='CANCEL', request=request)
        if replay:
            await db.commit(); return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), True
        check = await _locked_check(db, tenant_id=context.tenant_id, check_id=check_id, expected_version=expected_version)
        _authorize_controller(check, context)
        members = tuple((await db.execute(select(RestaurantCheckMember).where(
            RestaurantCheckMember.check_id == check.id, RestaurantCheckMember.active_slot == 1,
        ).order_by(RestaurantCheckMember.diner_session_id).with_for_update())).scalars().all())
        await _lock_diners(db, tenant_id=context.tenant_id, diner_ids=tuple(value.diner_session_id for value in members))
        allocations = tuple((await db.execute(select(RestaurantCheckAllocation).where(
            RestaurantCheckAllocation.check_id == check.id, RestaurantCheckAllocation.ownership_slot == 1,
        ).order_by(RestaurantCheckAllocation.id).with_for_update())).scalars().all())
        if any(value.state != 'CLAIMED' for value in allocations):
            raise errors.CheckNotModifiableError('Check contains financially non-releasable allocations')
        now = _now(); check.version += 1
        for member in members:
            member.active_slot = None; member.released_at = now; member.release_reason = reason; member.released_version = check.version
            for key, value in _actor_values(context, 'released').items(): setattr(member, key, value)
        for allocation in allocations:
            allocation.state = 'RELEASED'; allocation.ownership_slot = None; allocation.released_at = now
            allocation.release_reason = reason; allocation.released_version = check.version
            for key, value in _actor_values(context, 'released').items(): setattr(allocation, key, value)
        check.status = 'CANCELLED'; check.cancelled_at = now; check.cancellation_reason = reason
        for key, value in _actor_values(context, 'cancelled').items(): setattr(check, key, value)
        check.consumption_total = ZERO; check.gratuity_total = ZERO; check.liability_total = ZERO
        await _write_version(db, check, context=context)
        _record_command(db, context=context, idempotency_key=idempotency_key, operation='CANCEL', request=request, check=check)
        await db.commit()
    except OperationalError as exc:
        await db.rollback(); _raise_concurrency_conflict(exc)
    except Exception:
        await db.rollback(); raise
    return await get_check(db, tenant_id=context.tenant_id, check_id=check_id), False


async def get_check(
    db: AsyncSession, *, tenant_id: int, check_id: int, detailed: bool = False,
    owner_diner_session_id: int | None = None,
) -> CheckProjection:
    check = await db.scalar(select(RestaurantCheck).where(RestaurantCheck.id == check_id, RestaurantCheck.tenant_id == tenant_id))
    if check is None:
        raise errors.CheckNotFoundError()
    members = tuple((await db.execute(select(RestaurantCheckMember).where(
        RestaurantCheckMember.check_id == check.id, RestaurantCheckMember.active_slot == 1,
    ).order_by(RestaurantCheckMember.diner_session_id))).scalars().all())
    if owner_diner_session_id is not None and owner_diner_session_id not in {value.diner_session_id for value in members}:
        raise errors.CheckNotFoundError()
    allocations = tuple((await db.execute(select(RestaurantCheckAllocation).where(
        RestaurantCheckAllocation.check_id == check.id, RestaurantCheckAllocation.state != 'RELEASED',
    ).order_by(RestaurantCheckAllocation.source_resource_id, RestaurantCheckAllocation.source_diner_session_id, RestaurantCheckAllocation.restaurant_order_id))).scalars().all())
    details = None
    if detailed:
        orders = {value.id: value for value in (await db.execute(select(RestaurantOrder).where(
            RestaurantOrder.id.in_(tuple(value.restaurant_order_id for value in allocations) or (-1,))
        ))).scalars().all()}
        items_by_order: dict[int, list[dict]] = defaultdict(list)
        item_rows = tuple((await db.execute(select(RestaurantOrderItem).where(
            RestaurantOrderItem.order_id.in_(tuple(orders) or (-1,))
        ).order_by(RestaurantOrderItem.order_id, RestaurantOrderItem.position, RestaurantOrderItem.id))).scalars().all())
        for item in item_rows:
            items_by_order[item.order_id].append({
                'item_id': item.id, 'product_id': item.product_id, 'product_name': item.product_name,
                'quantity': _money(item.quantity), 'commercial_amount': _money(item.commercial_amount),
            })
        diner_names = dict((await db.execute(select(DinerSession.id, DinerSession.display_name).where(
            DinerSession.id.in_(tuple(value.source_diner_session_id for value in allocations) or (-1,))
        ))).all())
        grouped: dict[tuple[int, int], dict[int, list[CheckOrderLine]]] = defaultdict(lambda: defaultdict(list))
        for allocation in allocations:
            order = orders[allocation.restaurant_order_id]
            grouped[(allocation.source_resource_id, allocation.source_service_session_id)][allocation.source_diner_session_id].append(
                CheckOrderLine(order.id, order.diner_session_id, order.service_session_id, order.resource_id,
                    order.accepted_at, allocation.accepted_payable_amount,
                    allocation.accepted_commercial_fingerprint, tuple(items_by_order[order.id]))
            )
        details = tuple(
            CheckResourceGroup(resource_id, session_id, tuple(
                CheckDinerGroup(diner_id, diner_names[diner_id], tuple(order_lines))
                for diner_id, order_lines in sorted(diners.items())
            ))
            for (resource_id, session_id), diners in sorted(grouped.items())
        )
    settled = sum((value.accepted_payable_amount for value in allocations if value.state == 'SETTLED'), ZERO)
    return CheckProjection(
        id=check.id, tenant_id=check.tenant_id, organization_id=check.organization_id,
        location_id=check.location_id, status=check.status, version=check.version,
        fingerprint=check.current_fingerprint, currency=check.currency,
        controller_diner_session_id=check.controller_diner_session_id,
        member_ids=tuple(value.diner_session_id for value in members),
        consumption_total=check.consumption_total, gratuity_total=check.gratuity_total,
        liability_total=check.liability_total, confirmed_settlement=settled,
        outstanding=max(ZERO, check.liability_total - settled), uncertain_exposure=ZERO,
        frozen_at=check.frozen_at, cancelled_at=check.cancelled_at, details=details,
    )


async def eligible_consumption(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    owner_diner_session_id: int | None = None,
) -> tuple[EligibleDinerConsumption, ...]:
    query = select(DinerSession).where(
        DinerSession.tenant_id == tenant_id, DinerSession.location_id == location_id,
        DinerSession.active_slot == 1,
    ).order_by(DinerSession.service_session_id, DinerSession.id)
    if owner_diner_session_id is not None:
        owner = await db.scalar(select(DinerSession).where(DinerSession.id == owner_diner_session_id, DinerSession.tenant_id == tenant_id))
        if owner is None:
            raise errors.CheckNotFoundError()
        query = query.where(DinerSession.service_session_id == owner.service_session_id)
    diners = tuple((await db.execute(query)).scalars().all())
    result = []
    for diner in diners:
        active_check_id = await db.scalar(select(RestaurantCheckMember.check_id).where(
            RestaurantCheckMember.tenant_id == tenant_id,
            RestaurantCheckMember.diner_session_id == diner.id,
            RestaurantCheckMember.active_slot == 1,
        ))
        orders = await _eligible_orders(db, (diner,))
        draft_id = await db.scalar(select(OrderDraft.id).where(
            OrderDraft.tenant_id == tenant_id, OrderDraft.conversation_id == diner.conversation_id,
            OrderDraft.status == 'OPEN', OrderDraft.current_slot == 1,
        ))
        item_count = 0 if draft_id is None else int(await db.scalar(select(func.count(OrderDraftItem.id)).where(OrderDraftItem.draft_id == draft_id)))
        currencies = {value.currency for value in orders}
        result.append(EligibleDinerConsumption(
            diner.id, diner.service_session_id, diner.resource_id, diner.display_name,
            tuple(value.id for value in orders), sum((value.payable_total for value in orders), ZERO),
            next(iter(currencies)) if len(currencies) == 1 else None, active_check_id, item_count > 0,
        ))
    return tuple(result)


async def table_balance(
    db: AsyncSession, *, tenant_id: int, service_session_id: int, lock: bool = False,
) -> TableBalanceProjection:
    session_query = select(RestaurantServiceSession).where(
        RestaurantServiceSession.id == service_session_id, RestaurantServiceSession.tenant_id == tenant_id,
    )
    if lock: session_query = session_query.with_for_update()
    session = await db.scalar(session_query)
    if session is None:
        raise errors.CheckNotFoundError('Service Session not found')
    order_query = select(RestaurantOrder).where(
        RestaurantOrder.tenant_id == tenant_id, RestaurantOrder.service_session_id == service_session_id,
        RestaurantOrder.status == 'ACCEPTED',
    ).order_by(RestaurantOrder.id)
    if lock: order_query = order_query.with_for_update()
    orders = tuple((await db.execute(order_query)).scalars().all())
    allocations = tuple((await db.execute(select(RestaurantCheckAllocation).where(
        RestaurantCheckAllocation.tenant_id == tenant_id,
        RestaurantCheckAllocation.source_service_session_id == service_session_id,
        RestaurantCheckAllocation.ownership_slot == 1,
    ).order_by(RestaurantCheckAllocation.id))).scalars().all())
    allocation_by_order = {value.restaurant_order_id: value for value in allocations}
    accepted = sum((value.payable_total for value in orders), ZERO)
    reserved = sum((value.accepted_payable_amount for value in allocations if value.state == 'CLAIMED'), ZERO)
    settled = sum((value.accepted_payable_amount for value in allocations if value.state == 'SETTLED'), ZERO)
    unreserved = sum((value.payable_total for value in orders if value.id not in allocation_by_order), ZERO)
    check_ids = tuple(sorted({value.check_id for value in allocations}))
    check_rows = tuple((await db.execute(select(RestaurantCheck).where(
        RestaurantCheck.tenant_id == tenant_id,
        RestaurantCheck.id.in_(check_ids or (-1,)),
        RestaurantCheck.status.in_(('OPEN', 'FROZEN')),
    ).order_by(RestaurantCheck.id))).scalars().all())
    claimed_check_ids = {value.check_id for value in allocations if value.state == 'CLAIMED'}
    unresolved_check_ids = claimed_check_ids | {
        value.id for value in check_rows if value.gratuity_total > ZERO
    }
    pending_gratuity = sum(
        (value.gratuity_total for value in check_rows if value.id in unresolved_check_ids),
        ZERO,
    )
    unresolved_checks = len(unresolved_check_ids)
    outstanding = max(ZERO, accepted - settled)
    currencies = {value.currency for value in orders}
    closure_eligible = outstanding == ZERO and unresolved_checks == 0 and unreserved == ZERO
    return TableBalanceProjection(
        session.id, session.resource_id, next(iter(currencies)) if len(currencies) == 1 else None,
        accepted, reserved, unreserved, settled, pending_gratuity, ZERO,
        outstanding, unresolved_checks,
        closure_eligible and pending_gratuity == ZERO,
        closure_eligible and pending_gratuity == ZERO and session.status == 'OPEN',
    )


async def assert_diner_can_end(db: AsyncSession, *, tenant_id: int, diner_session_id: int) -> None:
    active = await db.scalar(select(RestaurantCheckMember.id).where(
        RestaurantCheckMember.tenant_id == tenant_id,
        RestaurantCheckMember.diner_session_id == diner_session_id,
        RestaurantCheckMember.active_slot == 1,
    ))
    if active is not None:
        raise errors.TableNotEligibleError('Diner has active Restaurant Check membership')
    orders = tuple((await db.execute(select(RestaurantOrder.id).where(
        RestaurantOrder.tenant_id == tenant_id, RestaurantOrder.diner_session_id == diner_session_id,
    ))).scalars().all())
    if orders:
        settled = set((await db.execute(select(RestaurantCheckAllocation.restaurant_order_id).where(
            RestaurantCheckAllocation.tenant_id == tenant_id,
            RestaurantCheckAllocation.restaurant_order_id.in_(orders),
            RestaurantCheckAllocation.state == 'SETTLED',
        ))).scalars().all())
        if set(orders) != settled:
            raise errors.TableNotEligibleError('Diner has unsettled accepted consumption')


async def assert_service_can_close(db: AsyncSession, *, tenant_id: int, service_session_id: int) -> TableBalanceProjection:
    balance = await table_balance(db, tenant_id=tenant_id, service_session_id=service_session_id, lock=True)
    if balance.outstanding_confirmed_balance != ZERO:
        raise errors.TableOutstandingBalanceError()
    if not balance.closure_eligible:
        raise errors.TableNotEligibleError()
    return balance
