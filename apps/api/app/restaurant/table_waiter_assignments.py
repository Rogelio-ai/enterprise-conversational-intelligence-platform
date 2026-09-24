"""Transactional TABLE-to-waiter assignment and shared responsibility rules."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Resource,
    TableWaiterAssignment,
    TableWaiterAssignmentAudit,
    TenantMembership,
    User,
)
from app.restaurant.waiter_eligibility import (
    WAITER_CAPABILITIES,
    eligible_waiter_ids,
    eligible_waiter_statement,
)
from app.restaurant.service_sessions.responsibility import (
    ServiceResponsibilityConflictError,
    assert_waiter_not_responsible_for_open_service,
)


class TableWaiterAssignmentError(ValueError):
    pass


class TableNotFoundError(TableWaiterAssignmentError):
    pass


class WaiterNotEligibleError(TableWaiterAssignmentError):
    pass


class AssignmentConflictError(TableWaiterAssignmentError):
    pass


@dataclass(frozen=True, slots=True)
class WaiterAssignmentValue:
    membership_id: int
    display_name: str
    email: str | None
    is_responsible: bool


@dataclass(frozen=True, slots=True)
class AssignmentSetValue:
    table_resource_id: int
    location_id: int
    version: int
    assignments: tuple[WaiterAssignmentValue, ...]


@dataclass(frozen=True, slots=True)
class EligibleWaiterValue:
    membership_id: int
    display_name: str
    email: str | None


@dataclass(frozen=True, slots=True)
class ServiceOpeningResponsibilitySource:
    assignment_version: int
    responsible_membership_ids: tuple[int, ...]


async def _table(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
    for_update: bool = False, active_required: bool = False,
) -> Resource:
    statement = select(Resource).where(
        Resource.id == table_resource_id,
        Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
        Resource.resource_type == 'TABLE',
    )
    if active_required:
        statement = statement.where(Resource.status == 'ACTIVE')
    if for_update:
        statement = statement.with_for_update()
    value = await db.scalar(statement)
    if value is None:
        raise TableNotFoundError('Table not found')
    return value


async def _version(
    db: AsyncSession, table_resource_id: int, *, lock_current: bool = False,
) -> int:
    if lock_current:
        statement = (
            select(TableWaiterAssignmentAudit.result_version)
            .where(TableWaiterAssignmentAudit.table_resource_id == table_resource_id)
            .order_by(TableWaiterAssignmentAudit.result_version.desc())
            .limit(1)
            .with_for_update()
        )
    else:
        statement = select(func.max(TableWaiterAssignmentAudit.result_version)).where(
            TableWaiterAssignmentAudit.table_resource_id == table_resource_id,
        )
    value = await db.scalar(statement)
    return int(value or 0)


async def _rows(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
    for_update: bool = False,
) -> list[TableWaiterAssignment]:
    statement = select(TableWaiterAssignment).where(
        TableWaiterAssignment.tenant_id == tenant_id,
        TableWaiterAssignment.location_id == location_id,
        TableWaiterAssignment.table_resource_id == table_resource_id,
    ).order_by(TableWaiterAssignment.waiter_membership_id)
    if for_update:
        statement = statement.with_for_update()
    return list((await db.scalars(statement)).all())


async def _view(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
) -> AssignmentSetValue:
    result = await db.execute(
        select(TableWaiterAssignment, User)
        .join(
            TenantMembership,
            TenantMembership.id == TableWaiterAssignment.waiter_membership_id,
        )
        .join(User, User.id == TenantMembership.user_id)
        .where(
            TableWaiterAssignment.tenant_id == tenant_id,
            TableWaiterAssignment.location_id == location_id,
            TableWaiterAssignment.table_resource_id == table_resource_id,
        )
        .order_by(User.display_name, TableWaiterAssignment.waiter_membership_id)
    )
    return AssignmentSetValue(
        table_resource_id=table_resource_id,
        location_id=location_id,
        version=await _version(db, table_resource_id),
        assignments=tuple(
            WaiterAssignmentValue(
                membership_id=assignment.waiter_membership_id,
                display_name=user.display_name,
                email=user.email,
                is_responsible=assignment.is_responsible,
            )
            for assignment, user in result.all()
        ),
    )


async def get_assignment_set(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
) -> AssignmentSetValue:
    await _table(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id,
    )
    return await _view(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id,
    )


async def get_locked_service_opening_responsibility_source(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    table_resource_id: int,
) -> ServiceOpeningResponsibilitySource:
    """Read one coherent table responsibility snapshot under the table lock."""
    await _table(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True, active_required=True,
    )
    version = await _version(db, table_resource_id, lock_current=True)
    rows = await _rows(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True,
    )
    _assert_invariants(rows)
    return ServiceOpeningResponsibilitySource(
        assignment_version=version,
        responsible_membership_ids=tuple(sorted(
            value.waiter_membership_id for value in rows if value.is_responsible
        )),
    )


def _eligible_statement(*, tenant_id: int, location_id: int, membership_id: int | None = None):
    return eligible_waiter_statement(
        tenant_id=tenant_id, location_id=location_id, membership_id=membership_id,
    )


async def list_eligible_waiters(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> tuple[EligibleWaiterValue, ...]:
    rows = (await db.execute(
        _eligible_statement(tenant_id=tenant_id, location_id=location_id)
        .order_by(User.display_name, TenantMembership.id)
    )).all()
    return tuple(
        EligibleWaiterValue(membership_id=row.id, display_name=row.display_name, email=row.email)
        for row in rows
    )


async def _require_eligible_waiter(
    db: AsyncSession, *, tenant_id: int, location_id: int, membership_id: int,
) -> None:
    eligible = await eligible_waiter_ids(
        db, tenant_id=tenant_id, location_id=location_id,
        membership_ids=(membership_id,),
    )
    if membership_id not in eligible:
        raise WaiterNotEligibleError('Waiter is not eligible for this location')


def _check_version(current: int, expected: int) -> None:
    if current != expected:
        raise AssignmentConflictError('Table waiter assignments changed; refresh and retry')


def _assert_invariants(rows: list[TableWaiterAssignment]) -> None:
    if not rows:
        raise AssignmentConflictError('A configured table must retain at least one assigned waiter')
    if not any(value.is_responsible for value in rows):
        raise AssignmentConflictError('A configured table must retain at least one responsible waiter')


def _audit(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    table_resource_id: int, waiter_membership_id: int | None, operation: str,
    actor_membership_id: int, result_version: int,
    rows: list[TableWaiterAssignment], correlation_id: str | None,
) -> None:
    assigned = sorted(value.waiter_membership_id for value in rows)
    responsible = sorted(
        value.waiter_membership_id for value in rows if value.is_responsible
    )
    db.add(TableWaiterAssignmentAudit(
        tenant_id=tenant_id,
        location_id=location_id,
        table_resource_id=table_resource_id,
        waiter_membership_id=waiter_membership_id,
        operation=operation,
        actor_membership_id=actor_membership_id,
        result_version=result_version,
        assigned_membership_ids=assigned,
        responsible_membership_ids=responsible,
        correlation_id=correlation_id,
    ))


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AssignmentConflictError(
            'Table waiter assignments changed; refresh and retry'
        ) from exc


async def assign_waiter(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    table_resource_id: int, waiter_membership_id: int, expected_version: int,
    actor_membership_id: int, correlation_id: str | None,
) -> AssignmentSetValue:
    await _table(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True, active_required=True,
    )
    current_version = await _version(db, table_resource_id, lock_current=True)
    _check_version(current_version, expected_version)
    rows = await _rows(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True,
    )
    if any(value.waiter_membership_id == waiter_membership_id for value in rows):
        raise AssignmentConflictError('Waiter is already assigned to this table')
    await _require_eligible_waiter(
        db, tenant_id=tenant_id, location_id=location_id,
        membership_id=waiter_membership_id,
    )
    assignment = TableWaiterAssignment(
        tenant_id=tenant_id,
        location_id=location_id,
        table_resource_id=table_resource_id,
        waiter_membership_id=waiter_membership_id,
        is_responsible=not rows,
    )
    db.add(assignment)
    await db.flush()
    rows.append(assignment)
    _assert_invariants(rows)
    _audit(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, waiter_membership_id=waiter_membership_id,
        operation='ASSIGN', actor_membership_id=actor_membership_id,
        result_version=current_version + 1, rows=rows, correlation_id=correlation_id,
    )
    await _commit(db)
    return await _view(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id,
    )


async def update_responsible_waiters(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    table_resource_id: int, responsible_membership_ids: set[int],
    expected_version: int, actor_membership_id: int, correlation_id: str | None,
) -> AssignmentSetValue:
    await _table(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True, active_required=True,
    )
    current_version = await _version(db, table_resource_id, lock_current=True)
    _check_version(current_version, expected_version)
    rows = await _rows(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True,
    )
    assigned = {value.waiter_membership_id for value in rows}
    if not rows:
        raise AssignmentConflictError('Assign at least one waiter before setting responsibility')
    if not responsible_membership_ids:
        raise AssignmentConflictError('At least one responsible waiter is required')
    if not responsible_membership_ids <= assigned:
        raise AssignmentConflictError('Responsible waiters must be assigned to the table')
    for value in rows:
        value.is_responsible = value.waiter_membership_id in responsible_membership_ids
    _assert_invariants(rows)
    _audit(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, waiter_membership_id=None,
        operation='RESPONSIBILITY_UPDATE', actor_membership_id=actor_membership_id,
        result_version=current_version + 1, rows=rows, correlation_id=correlation_id,
    )
    await _commit(db)
    return await _view(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id,
    )


async def unassign_waiter(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    table_resource_id: int, waiter_membership_id: int,
    replacement_responsible_membership_ids: set[int], expected_version: int,
    actor_membership_id: int, correlation_id: str | None,
) -> AssignmentSetValue:
    await _table(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True, active_required=True,
    )
    try:
        await assert_waiter_not_responsible_for_open_service(
            db, tenant_id=tenant_id, table_resource_id=table_resource_id,
            waiter_membership_id=waiter_membership_id,
        )
    except ServiceResponsibilityConflictError as exc:
        raise AssignmentConflictError(str(exc)) from exc
    current_version = await _version(db, table_resource_id, lock_current=True)
    _check_version(current_version, expected_version)
    rows = await _rows(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, for_update=True,
    )
    target = next(
        (value for value in rows if value.waiter_membership_id == waiter_membership_id),
        None,
    )
    if target is None:
        raise AssignmentConflictError('Waiter is not assigned to this table')
    if len(rows) == 1:
        raise AssignmentConflictError('The last assigned waiter cannot be removed')
    remaining = [value for value in rows if value is not target]
    responsible_remaining = [value for value in remaining if value.is_responsible]
    remaining_ids = {value.waiter_membership_id for value in remaining}
    if replacement_responsible_membership_ids - remaining_ids:
        raise AssignmentConflictError('Replacement responsible waiters must remain assigned')
    if responsible_remaining:
        if replacement_responsible_membership_ids:
            raise AssignmentConflictError(
                'Use the responsibility operation while a responsible waiter remains'
            )
    elif len(remaining) == 1:
        remaining[0].is_responsible = True
    else:
        if not replacement_responsible_membership_ids:
            raise AssignmentConflictError(
                'Select at least one replacement responsible waiter before unassigning'
            )
        for value in remaining:
            value.is_responsible = (
                value.waiter_membership_id in replacement_responsible_membership_ids
            )
    await db.delete(target)
    _assert_invariants(remaining)
    _audit(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id, waiter_membership_id=waiter_membership_id,
        operation='UNASSIGN', actor_membership_id=actor_membership_id,
        result_version=current_version + 1, rows=remaining, correlation_id=correlation_id,
    )
    await _commit(db)
    return await _view(
        db, tenant_id=tenant_id, location_id=location_id,
        table_resource_id=table_resource_id,
    )
