from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DiningSection,
    Location,
    Resource,
    RestaurantServiceSession,
    RestaurantTableProfile,
    TableGroup,
    TableGroupMembership,
    TableGroupResponsibleWaiter,
    TableManagementHistory,
    TableWaiterAssignment,
)


class TableManagementError(RuntimeError):
    pass


class TableManagementNotFoundError(TableManagementError):
    pass


class TableManagementConflictError(TableManagementError):
    pass


_CODE = re.compile(r'^[A-Z0-9_-]{1,64}$')
_SECTION_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_ADMINISTRATIVE_TRANSITIONS = {
    'ACTIVE': frozenset({'SUSPENDED', 'OUT_OF_SERVICE', 'RETIRED'}),
    'SUSPENDED': frozenset({'ACTIVE'}),
    'OUT_OF_SERVICE': frozenset({'ACTIVE'}),
    'RETIRED': frozenset(),
}


@dataclass(frozen=True, slots=True)
class TableProjection:
    resource_id: int
    code: str
    name: str
    physical_capacity: int | None
    dining_section_id: int | None
    dining_section_code: str | None
    dining_section_name: str | None
    administrative_status: str | None
    individually_movable: bool
    section_movable: bool
    effective_movable: bool
    metadata_version: int | None
    operational_status: str
    active_group_id: int | None
    is_group_representative: bool


@dataclass(frozen=True, slots=True)
class GroupProjection:
    id: int
    representative_resource_id: int
    representative_code: str
    status: str
    version: int
    member_resource_ids: tuple[int, ...]
    member_codes: tuple[str, ...]
    responsible_membership_ids: tuple[int, ...]
    derived_capacity: int
    created_by_membership_id: int
    created_at: datetime
    closed_by_membership_id: int | None
    closed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProposedTableProjection:
    resource_id: int
    code: str
    name: str
    physical_capacity: int
    is_representative: bool


@dataclass(frozen=True, slots=True)
class GroupPreviewProjection:
    representative: ProposedTableProjection
    members: tuple[ProposedTableProjection, ...]
    derived_capacity: int
    assigned_membership_ids: tuple[int, ...]
    automatic_responsible_membership_ids: tuple[int, ...]
    responsibility_selection_required: bool
    organization_id: int


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CODE.fullmatch(normalized):
        raise ValueError('Dining Section code must contain only A-Z, 0-9, _ or -')
    return normalized


def _section_name(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise ValueError('Dining Section name must contain between 1 and 200 characters')
    return normalized


def _section_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _SECTION_STATUSES:
        raise ValueError('Unsupported Dining Section status')
    return normalized


def _administrative_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in _ADMINISTRATIVE_TRANSITIONS:
        raise ValueError('Unsupported Table administrative status')
    return normalized


def _assert_administrative_transition(current: str, target: str) -> None:
    if current != target and target not in _ADMINISTRATIVE_TRANSITIONS[current]:
        raise TableManagementConflictError('Administrative status transition is not allowed')


async def plan_table_profile(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
    resource_id: int, dining_section_code: str, dining_section_name: str,
    physical_capacity: int, section_movable: bool = True,
    table_movable: bool = True, administrative_status: str = 'ACTIVE',
) -> str:
    """Return UPDATE/UNCHANGED for existing Resource onboarding metadata."""
    if not 1 <= physical_capacity <= 999:
        raise ValueError('physical_capacity must be between 1 and 999')
    code = normalize_code(dining_section_code)
    name = _section_name(dining_section_name)
    target_status = _administrative_status(administrative_status)
    resource = await db.scalar(select(Resource.id).where(
        Resource.id == resource_id, Resource.tenant_id == tenant_id,
        Resource.location_id == location_id, Resource.resource_type == 'TABLE',
    ))
    if resource is None:
        raise TableManagementNotFoundError('Table not found')
    section = await db.scalar(select(DiningSection).where(
        DiningSection.tenant_id == tenant_id,
        DiningSection.organization_id == organization_id,
        DiningSection.location_id == location_id,
        DiningSection.code == code,
    ))
    profile = await db.scalar(select(RestaurantTableProfile).where(
        RestaurantTableProfile.resource_id == resource_id,
        RestaurantTableProfile.tenant_id == tenant_id,
    ))
    if profile is not None:
        _assert_administrative_transition(
            profile.administrative_status, target_status,
        )
        if profile.administrative_status == 'RETIRED' and (
            section is None
            or profile.dining_section_id != section.id
            or profile.physical_capacity != physical_capacity
            or bool(profile.movable) != table_movable
        ):
            raise TableManagementConflictError('A RETIRED Table cannot be modified')
    if section is None or profile is None:
        return 'UPDATE'
    if bool(section.movable) != section_movable or section.status != 'ACTIVE':
        await _assert_section_change_allowed(db, section_id=section.id)
    unchanged = (
        section.name == name
        and bool(section.movable) == section_movable
        and section.status == 'ACTIVE'
        and profile.dining_section_id == section.id
        and profile.physical_capacity == physical_capacity
        and bool(profile.movable) == table_movable
        and profile.administrative_status == target_status
    )
    return 'UNCHANGED' if unchanged else 'UPDATE'


async def _assert_section_change_allowed(
    db: AsyncSession, *, section_id: int,
) -> None:
    table_ids = select(RestaurantTableProfile.resource_id).where(
        RestaurantTableProfile.dining_section_id == section_id,
    )
    if await db.scalar(select(TableGroupMembership.id).where(
        TableGroupMembership.table_resource_id.in_(table_ids),
        TableGroupMembership.active_slot == 1,
    ).limit(1)) is not None:
        raise TableManagementConflictError(
            'Dining Section movability cannot change during ACTIVE group membership'
        )
    if await db.scalar(select(RestaurantServiceSession.id).where(
        RestaurantServiceSession.resource_id.in_(table_ids),
        RestaurantServiceSession.status == 'OPEN',
    ).limit(1)) is not None:
        raise TableManagementConflictError(
            'Dining Section movability cannot change during an OPEN Service Session'
        )


async def provision_dining_section(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
    code: str, name: str, movable: bool = True, status: str = 'ACTIVE',
) -> DiningSection:
    code = normalize_code(code)
    name = _section_name(name)
    status = _section_status(status)
    location = await db.scalar(select(Location).where(
        Location.id == location_id, Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    ))
    if location is None:
        raise TableManagementNotFoundError('Location not found')
    value = await db.scalar(select(DiningSection).where(
        DiningSection.tenant_id == tenant_id,
        DiningSection.location_id == location_id,
        DiningSection.code == code,
    ).with_for_update())
    if value is None:
        value = DiningSection(
            tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, code=code, name=name,
            movable=movable, status=status,
        )
        db.add(value)
        await db.flush()
    else:
        if bool(value.movable) != movable or value.status != status:
            await _assert_section_change_allowed(db, section_id=value.id)
        value.name = name
        value.movable = movable
        value.status = status
    return value


async def provision_table_profile(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
    resource_id: int, dining_section_id: int, physical_capacity: int,
    movable: bool = True, administrative_status: str = 'ACTIVE',
) -> RestaurantTableProfile:
    if not 1 <= physical_capacity <= 999:
        raise ValueError('physical_capacity must be between 1 and 999')
    administrative_status = _administrative_status(administrative_status)
    resource = await db.scalar(select(Resource).where(
        Resource.id == resource_id, Resource.tenant_id == tenant_id,
        Resource.location_id == location_id, Resource.resource_type == 'TABLE',
    ).with_for_update())
    section = await db.scalar(select(DiningSection).where(
        DiningSection.id == dining_section_id, DiningSection.tenant_id == tenant_id,
        DiningSection.organization_id == organization_id,
        DiningSection.location_id == location_id,
    ))
    if resource is None or section is None:
        raise TableManagementNotFoundError('Table or Dining Section not found')
    value = await db.scalar(select(RestaurantTableProfile).where(
        RestaurantTableProfile.resource_id == resource_id,
        RestaurantTableProfile.tenant_id == tenant_id,
    ))
    requested = (
        dining_section_id, physical_capacity, movable, administrative_status,
    )
    current = None if value is None else (
        value.dining_section_id, value.physical_capacity,
        bool(value.movable), value.administrative_status,
    )
    if value is not None:
        _assert_administrative_transition(
            value.administrative_status, administrative_status,
        )
        if value.administrative_status == 'RETIRED' and current != requested:
            raise TableManagementConflictError('A RETIRED Table cannot be modified')
    if current != requested:
        if await db.scalar(select(RestaurantServiceSession.id).where(
            RestaurantServiceSession.resource_id == resource_id,
            RestaurantServiceSession.status == 'OPEN',
        ).limit(1).with_for_update()) is not None:
            raise TableManagementConflictError(
                'Table metadata cannot change during an OPEN Service Session'
            )
        if await db.scalar(select(TableGroupMembership.id).where(
            TableGroupMembership.table_resource_id == resource_id,
            TableGroupMembership.active_slot == 1,
        ).limit(1).with_for_update()) is not None:
            raise TableManagementConflictError(
                'Table metadata cannot change during ACTIVE group membership'
            )
    if value is None:
        value = RestaurantTableProfile(
            tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, resource_id=resource_id,
            dining_section_id=dining_section_id, physical_capacity=physical_capacity,
            movable=movable, administrative_status=administrative_status, version=1,
        )
        db.add(value)
        await db.flush()
    else:
        if current != requested:
            value.dining_section_id = dining_section_id
            value.physical_capacity = physical_capacity
            value.movable = movable
            value.administrative_status = administrative_status
            value.version += 1
    return value


async def list_dining_sections(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> tuple[DiningSection, ...]:
    return tuple((await db.scalars(select(DiningSection).where(
        DiningSection.tenant_id == tenant_id,
        DiningSection.location_id == location_id,
    ).order_by(DiningSection.code, DiningSection.id))).all())


async def _active_membership_map(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> dict[int, tuple[int, bool]]:
    rows = (await db.execute(select(
        TableGroupMembership.table_resource_id,
        TableGroupMembership.table_group_id,
        TableGroupMembership.is_representative,
    ).where(
        TableGroupMembership.tenant_id == tenant_id,
        TableGroupMembership.location_id == location_id,
        TableGroupMembership.active_slot == 1,
    ))).all()
    return {int(row.table_resource_id): (int(row.table_group_id), bool(row.is_representative)) for row in rows}


async def list_tables(
    db: AsyncSession, *, tenant_id: int, location_id: int,
) -> tuple[TableProjection, ...]:
    rows = (await db.execute(select(Resource, RestaurantTableProfile, DiningSection).outerjoin(
        RestaurantTableProfile,
        and_(RestaurantTableProfile.resource_id == Resource.id,
             RestaurantTableProfile.tenant_id == Resource.tenant_id),
    ).outerjoin(
        DiningSection,
        and_(DiningSection.id == RestaurantTableProfile.dining_section_id,
             DiningSection.tenant_id == RestaurantTableProfile.tenant_id),
    ).where(
        Resource.tenant_id == tenant_id, Resource.location_id == location_id,
        Resource.resource_type == 'TABLE',
    ).order_by(Resource.code, Resource.id))).all()
    memberships = await _active_membership_map(db, tenant_id=tenant_id, location_id=location_id)
    group_representatives = dict((await db.execute(select(
        TableGroup.id, TableGroup.representative_resource_id,
    ).where(
        TableGroup.tenant_id == tenant_id,
        TableGroup.location_id == location_id,
        TableGroup.status == 'ACTIVE',
    ))).all())
    open_rows = (await db.execute(select(
        RestaurantServiceSession.resource_id, RestaurantServiceSession.id,
    ).where(
        RestaurantServiceSession.tenant_id == tenant_id,
        RestaurantServiceSession.location_id == location_id,
        RestaurantServiceSession.status == 'OPEN',
    ))).all()
    open_sessions = {int(row.resource_id): int(row.id) for row in open_rows}
    payment_states: dict[int, str] = {}
    if open_sessions:
        from app.restaurant.checks import service as check_service
        for resource_id, session_id in open_sessions.items():
            balance = await check_service.table_balance(
                db, tenant_id=tenant_id, service_session_id=session_id,
            )
            if balance.accepted_consumption > 0 and balance.financial_closure_eligible:
                payment_states[resource_id] = 'FINAL_PAYMENT'
            elif balance.settled_consumption > 0:
                payment_states[resource_id] = 'PARTIAL_PAYMENT'
    result: list[TableProjection] = []
    for resource, profile, section in rows:
        group = memberships.get(resource.id)
        individually_movable = True if profile is None else bool(profile.movable)
        section_movable = True if section is None else bool(section.movable)
        admin = None if profile is None else profile.administrative_status
        service_resource_id = (
            group_representatives.get(group[0], resource.id) if group else resource.id
        )
        if service_resource_id in open_sessions:
            operational = payment_states.get(service_resource_id, 'OCCUPIED')
        elif (
            resource.status != 'ACTIVE'
            or admin not in {None, 'ACTIVE'}
            or (group and not group[1])
        ):
            operational = 'UNAVAILABLE'
        else:
            operational = 'AVAILABLE'
        result.append(TableProjection(
            resource_id=resource.id, code=resource.code, name=resource.name,
            physical_capacity=None if profile is None else profile.physical_capacity,
            dining_section_id=None if section is None else section.id,
            dining_section_code=None if section is None else section.code,
            dining_section_name=None if section is None else section.name,
            administrative_status=admin,
            individually_movable=individually_movable,
            section_movable=section_movable,
            effective_movable=individually_movable and section_movable,
            metadata_version=None if profile is None else profile.version,
            operational_status=operational,
            active_group_id=None if group is None else group[0],
            is_group_representative=False if group is None else group[1],
        ))
    return tuple(result)


async def _resources_for_proposal(
    db: AsyncSession, *, tenant_id: int, location_id: int, resource_ids: set[int],
    lock: bool,
) -> list[Resource]:
    statement = select(Resource).where(
        Resource.id.in_(sorted(resource_ids)), Resource.tenant_id == tenant_id,
        Resource.location_id == location_id,
    ).order_by(Resource.id)
    if lock:
        statement = statement.with_for_update()
    values = list((await db.scalars(statement)).all())
    if len(values) != len(resource_ids) or any(v.resource_type != 'TABLE' for v in values):
        raise TableManagementNotFoundError('Table not found')
    return values


async def _lock_resources(
    db: AsyncSession, *, tenant_id: int, location_id: int, resource_ids: set[int],
) -> list[Resource]:
    return await _resources_for_proposal(
        db, tenant_id=tenant_id, location_id=location_id,
        resource_ids=resource_ids, lock=True,
    )


async def _profiles_and_sections(
    db: AsyncSession, *, tenant_id: int, location_id: int, resource_ids: set[int],
    lock: bool = True,
) -> dict[int, tuple[RestaurantTableProfile, DiningSection]]:
    statement = select(RestaurantTableProfile, DiningSection).join(
        DiningSection,
        and_(DiningSection.id == RestaurantTableProfile.dining_section_id,
             DiningSection.tenant_id == RestaurantTableProfile.tenant_id),
    ).where(
        RestaurantTableProfile.tenant_id == tenant_id,
        RestaurantTableProfile.location_id == location_id,
        RestaurantTableProfile.resource_id.in_(sorted(resource_ids)),
    ).order_by(RestaurantTableProfile.resource_id)
    if lock:
        statement = statement.with_for_update()
    rows = (await db.execute(statement)).all()
    if len(rows) != len(resource_ids):
        raise TableManagementConflictError('Every Table requires physical metadata and a Dining Section')
    return {profile.resource_id: (profile, section) for profile, section in rows}


async def _assert_available(
    db: AsyncSession, *, resources: list[Resource],
    profiles: dict[int, tuple[RestaurantTableProfile, DiningSection]],
    lock: bool = True,
) -> None:
    ids = {value.id for value in resources}
    for resource in resources:
        profile, section = profiles[resource.id]
        if resource.status != 'ACTIVE' or profile.administrative_status != 'ACTIVE':
            raise TableManagementConflictError('Only administratively ACTIVE Tables are available')
        if not profile.movable or not section.movable or section.status != 'ACTIVE':
            raise TableManagementConflictError('Every selected Table must be effectively movable')
    session_statement = select(RestaurantServiceSession.id).where(
        RestaurantServiceSession.resource_id.in_(ids),
        RestaurantServiceSession.status == 'OPEN',
    ).limit(1)
    membership_statement = select(TableGroupMembership.id).where(
        TableGroupMembership.table_resource_id.in_(ids),
        TableGroupMembership.active_slot == 1,
    ).limit(1)
    if lock:
        session_statement = session_statement.with_for_update()
        membership_statement = membership_statement.with_for_update()
    if await db.scalar(session_statement) is not None:
        raise TableManagementConflictError('A selected Table has an OPEN Service Session')
    if await db.scalar(membership_statement) is not None:
        raise TableManagementConflictError('A selected Table already belongs to an ACTIVE TableGroup')


async def _assigned_waiters(
    db: AsyncSession, *, tenant_id: int, location_id: int, resource_ids: set[int],
) -> set[int]:
    return set((await db.scalars(select(TableWaiterAssignment.waiter_membership_id).where(
        TableWaiterAssignment.tenant_id == tenant_id,
        TableWaiterAssignment.location_id == location_id,
        TableWaiterAssignment.table_resource_id.in_(resource_ids),
    ).distinct())).all())


def _responsible(assigned: set[int], requested: set[int]) -> set[int]:
    if not assigned:
        raise TableManagementConflictError('Selected Tables require at least one assigned waiter')
    if len(assigned) == 1:
        if requested and requested != assigned:
            raise TableManagementConflictError('The only assigned waiter is automatically responsible')
        return assigned
    if not requested:
        raise TableManagementConflictError('Select responsible waiter(s) when multiple waiters are represented')
    if not requested <= assigned:
        raise TableManagementConflictError('Responsible waiters must be assigned to a selected Table')
    return requested


def _snapshot(member_ids: list[int], capacities: dict[int, int], status: str) -> dict:
    return {
        'status': status, 'member_resource_ids': member_ids,
        'derived_capacity': sum(capacities[value] for value in member_ids) - ((len(member_ids) - 1) * 2),
    }


async def _canonical_group_proposal(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    representative_resource_id: int, joined_resource_ids: set[int], lock: bool,
) -> GroupPreviewProjection:
    if not joined_resource_ids or representative_resource_id in joined_resource_ids:
        raise TableManagementConflictError(
            'A group requires a representative and at least one distinct additional Table'
        )
    ids = joined_resource_ids | {representative_resource_id}
    resources = await _resources_for_proposal(
        db, tenant_id=tenant_id, location_id=location_id,
        resource_ids=ids, lock=lock,
    )
    profiles = await _profiles_and_sections(
        db, tenant_id=tenant_id, location_id=location_id,
        resource_ids=ids, lock=lock,
    )
    location_organization_id = await db.scalar(select(Location.organization_id).where(
        Location.id == location_id, Location.tenant_id == tenant_id,
    ))
    organization_ids = {
        profile.organization_id
        for profile, _section in profiles.values()
    } | {
        section.organization_id
        for _profile, section in profiles.values()
    }
    if location_organization_id is None or organization_ids != {location_organization_id}:
        raise TableManagementConflictError(
            'Every selected Table must belong to the same Organization and Location'
        )
    await _assert_available(
        db, resources=resources, profiles=profiles, lock=lock,
    )
    assigned = await _assigned_waiters(
        db, tenant_id=tenant_id, location_id=location_id, resource_ids=ids,
    )
    if not assigned:
        raise TableManagementConflictError(
            'Selected Tables require at least one assigned waiter'
        )
    ordered_ids = [representative_resource_id, *sorted(joined_resource_ids)]
    capacities = {key: value[0].physical_capacity for key, value in profiles.items()}
    snapshot = _snapshot(ordered_ids, capacities, 'ACTIVE')
    resources_by_id = {value.id: value for value in resources}
    members = tuple(ProposedTableProjection(
        resource_id=resource_id,
        code=resources_by_id[resource_id].code,
        name=resources_by_id[resource_id].name,
        physical_capacity=capacities[resource_id],
        is_representative=resource_id == representative_resource_id,
    ) for resource_id in ordered_ids)
    automatic = tuple(sorted(assigned)) if len(assigned) == 1 else ()
    return GroupPreviewProjection(
        representative=members[0],
        members=members,
        derived_capacity=int(snapshot['derived_capacity']),
        assigned_membership_ids=tuple(sorted(assigned)),
        automatic_responsible_membership_ids=automatic,
        responsibility_selection_required=len(assigned) > 1,
        organization_id=location_organization_id,
    )


async def preview_group(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    representative_resource_id: int, joined_resource_ids: set[int],
) -> GroupPreviewProjection:
    return await _canonical_group_proposal(
        db, tenant_id=tenant_id, location_id=location_id,
        representative_resource_id=representative_resource_id,
        joined_resource_ids=joined_resource_ids, lock=False,
    )


def _history(
    db: AsyncSession, *, group: TableGroup | None, table_resource_id: int | None,
    event_type: str, actor_membership_id: int, result_version: int,
    before: dict | None, after: dict | None, correlation_id: str | None,
    tenant_id: int | None = None, organization_id: int | None = None,
    location_id: int | None = None,
) -> None:
    db.add(TableManagementHistory(
        tenant_id=group.tenant_id if group else tenant_id,
        organization_id=group.organization_id if group else organization_id,
        location_id=group.location_id if group else location_id,
        table_group_id=None if group is None else group.id,
        table_resource_id=table_resource_id,
        event_type=event_type, actor_membership_id=actor_membership_id,
        result_version=result_version, before_state=before, after_state=after,
        correlation_id=correlation_id,
    ))


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise TableManagementConflictError('Table Management state changed; refresh and retry') from exc


async def create_group(
    db: AsyncSession, *, tenant_id: int, location_id: int,
    representative_resource_id: int, joined_resource_ids: set[int],
    responsible_membership_ids: set[int], actor_membership_id: int,
    correlation_id: str | None,
) -> GroupProjection:
    try:
        proposal = await _canonical_group_proposal(
            db, tenant_id=tenant_id, location_id=location_id,
            representative_resource_id=representative_resource_id,
            joined_resource_ids=joined_resource_ids, lock=True,
        )
        responsible = _responsible(
            set(proposal.assigned_membership_ids),
            responsible_membership_ids,
        )
        organization_id = proposal.organization_id
        group = TableGroup(
            tenant_id=tenant_id, organization_id=organization_id, location_id=location_id,
            representative_resource_id=representative_resource_id,
            status='ACTIVE', active_slot=1, version=1,
            created_by_membership_id=actor_membership_id,
        )
        db.add(group)
        await db.flush()
        now = _now()
        for member in proposal.members:
            resource_id = member.resource_id
            db.add(TableGroupMembership(
                tenant_id=tenant_id, organization_id=organization_id,
                location_id=location_id, table_group_id=group.id,
                table_resource_id=resource_id,
                is_representative=resource_id == representative_resource_id,
                active_slot=1, added_at=now,
            ))
        for waiter_id in sorted(responsible):
            db.add(TableGroupResponsibleWaiter(
                tenant_id=tenant_id, organization_id=organization_id,
                location_id=location_id, table_group_id=group.id,
                waiter_membership_id=waiter_id,
            ))
        after = {
            'status': 'ACTIVE',
            'member_resource_ids': [member.resource_id for member in proposal.members],
            'derived_capacity': proposal.derived_capacity,
        }
        _history(db, group=group, table_resource_id=representative_resource_id,
                 event_type='CREATE_GROUP', actor_membership_id=actor_membership_id,
                 result_version=1, before=None, after=after, correlation_id=correlation_id)
        await _commit(db)
        return await get_group(db, tenant_id=tenant_id, location_id=location_id, group_id=group.id)
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise


async def _locked_group_and_members(
    db: AsyncSession, *, tenant_id: int, location_id: int, group_id: int,
    expected_version: int,
) -> tuple[TableGroup, list[TableGroupMembership]]:
    identity = await db.scalar(select(TableGroup.representative_resource_id).where(
        TableGroup.id == group_id, TableGroup.tenant_id == tenant_id,
        TableGroup.location_id == location_id,
    ))
    if identity is None:
        raise TableManagementNotFoundError('TableGroup not found')
    await _lock_resources(db, tenant_id=tenant_id, location_id=location_id, resource_ids={identity})
    group = await db.scalar(select(TableGroup).where(
        TableGroup.id == group_id, TableGroup.tenant_id == tenant_id,
        TableGroup.location_id == location_id,
    ).with_for_update())
    if group is None:
        raise TableManagementNotFoundError('TableGroup not found')
    if group.status != 'ACTIVE' or group.version != expected_version:
        raise TableManagementConflictError('TableGroup changed; refresh and retry')
    members = list((await db.scalars(select(TableGroupMembership).where(
        TableGroupMembership.table_group_id == group.id,
        TableGroupMembership.active_slot == 1,
    ).order_by(TableGroupMembership.table_resource_id).with_for_update())).all())
    if await db.scalar(select(RestaurantServiceSession.id).where(
        RestaurantServiceSession.resource_id == group.representative_resource_id,
        RestaurantServiceSession.status == 'OPEN',
    ).limit(1).with_for_update()) is not None:
        raise TableManagementConflictError('The representative Table has an OPEN Service Session')
    return group, members


async def _member_snapshot(db: AsyncSession, members: list[TableGroupMembership], status: str) -> dict:
    ids = [value.table_resource_id for value in sorted(members, key=lambda x: (not x.is_representative, x.table_resource_id))]
    capacities = dict((await db.execute(select(
        RestaurantTableProfile.resource_id, RestaurantTableProfile.physical_capacity,
    ).where(RestaurantTableProfile.resource_id.in_(ids)))).all())
    return _snapshot(ids, capacities, status)


async def add_table(
    db: AsyncSession, *, tenant_id: int, location_id: int, group_id: int,
    table_resource_id: int, expected_version: int, actor_membership_id: int,
    correlation_id: str | None,
) -> GroupProjection:
    try:
        identity = await db.scalar(select(TableGroup.representative_resource_id).where(
            TableGroup.id == group_id, TableGroup.tenant_id == tenant_id,
            TableGroup.location_id == location_id,
        ))
        if identity is None:
            raise TableManagementNotFoundError('TableGroup not found')
        resources = await _lock_resources(db, tenant_id=tenant_id, location_id=location_id, resource_ids={identity, table_resource_id})
        group, members = await _locked_group_and_members(db, tenant_id=tenant_id, location_id=location_id, group_id=group_id, expected_version=expected_version)
        profiles = await _profiles_and_sections(db, tenant_id=tenant_id, location_id=location_id, resource_ids={table_resource_id})
        await _assert_available(db, resources=[v for v in resources if v.id == table_resource_id], profiles=profiles)
        before = await _member_snapshot(db, members, 'ACTIVE')
        membership = TableGroupMembership(
            tenant_id=tenant_id, organization_id=group.organization_id,
            location_id=location_id, table_group_id=group.id,
            table_resource_id=table_resource_id, is_representative=False,
            active_slot=1, added_at=_now(),
        )
        db.add(membership)
        members.append(membership)
        group.version += 1
        after = await _member_snapshot(db, members, 'ACTIVE')
        _history(db, group=group, table_resource_id=table_resource_id, event_type='ADD_TABLE',
                 actor_membership_id=actor_membership_id, result_version=group.version,
                 before=before, after=after, correlation_id=correlation_id)
        await _commit(db)
        return await get_group(db, tenant_id=tenant_id, location_id=location_id, group_id=group.id)
    except Exception:
        if db.in_transaction(): await db.rollback()
        raise


async def remove_table(
    db: AsyncSession, *, tenant_id: int, location_id: int, group_id: int,
    table_resource_id: int, expected_version: int, actor_membership_id: int,
    correlation_id: str | None,
) -> GroupProjection:
    try:
        group, members = await _locked_group_and_members(db, tenant_id=tenant_id, location_id=location_id, group_id=group_id, expected_version=expected_version)
        await _lock_resources(db, tenant_id=tenant_id, location_id=location_id, resource_ids={group.representative_resource_id, table_resource_id})
        target = next((v for v in members if v.table_resource_id == table_resource_id), None)
        if target is None:
            raise TableManagementConflictError('Table is not an ACTIVE member of this group')
        if target.is_representative:
            raise TableManagementConflictError('The representative Table cannot be removed')
        if len(members) <= 2:
            raise TableManagementConflictError('REMOVE cannot leave only the representative; dissolve explicitly')
        before = await _member_snapshot(db, members, 'ACTIVE')
        target.active_slot = None
        target.removed_at = _now()
        remaining = [value for value in members if value is not target]
        group.version += 1
        after = await _member_snapshot(db, remaining, 'ACTIVE')
        _history(db, group=group, table_resource_id=table_resource_id, event_type='REMOVE_TABLE',
                 actor_membership_id=actor_membership_id, result_version=group.version,
                 before=before, after=after, correlation_id=correlation_id)
        await _commit(db)
        return await get_group(db, tenant_id=tenant_id, location_id=location_id, group_id=group.id)
    except Exception:
        if db.in_transaction(): await db.rollback()
        raise


async def _close_group(
    db: AsyncSession, *, group: TableGroup, members: list[TableGroupMembership],
    actor_membership_id: int, event_type: str, correlation_id: str | None,
) -> None:
    before = await _member_snapshot(db, members, 'ACTIVE')
    now = _now()
    for member in members:
        member.active_slot = None
        member.removed_at = now
    group.status = 'CLOSED'
    group.active_slot = None
    group.version += 1
    group.closed_by_membership_id = actor_membership_id
    group.closed_at = now
    after = {**before, 'status': 'CLOSED'}
    _history(db, group=group, table_resource_id=group.representative_resource_id,
             event_type=event_type, actor_membership_id=actor_membership_id,
             result_version=group.version, before=before, after=after,
             correlation_id=correlation_id)


async def dissolve_group(
    db: AsyncSession, *, tenant_id: int, location_id: int, group_id: int,
    expected_version: int, actor_membership_id: int, correlation_id: str | None,
) -> GroupProjection:
    try:
        group, members = await _locked_group_and_members(db, tenant_id=tenant_id, location_id=location_id, group_id=group_id, expected_version=expected_version)
        await _close_group(db, group=group, members=members, actor_membership_id=actor_membership_id, event_type='DISSOLVE_GROUP', correlation_id=correlation_id)
        await _commit(db)
        return await get_group(db, tenant_id=tenant_id, location_id=location_id, group_id=group.id)
    except Exception:
        if db.in_transaction(): await db.rollback()
        raise


async def close_group_for_service_session(
    db: AsyncSession, *, session: RestaurantServiceSession,
    actor_membership_id: int, correlation_id: str | None,
) -> None:
    group = await db.scalar(select(TableGroup).where(
        TableGroup.tenant_id == session.tenant_id,
        TableGroup.location_id == session.location_id,
        TableGroup.representative_resource_id == session.resource_id,
        TableGroup.status == 'ACTIVE',
    ).with_for_update())
    if group is None:
        return
    members = list((await db.scalars(select(TableGroupMembership).where(
        TableGroupMembership.table_group_id == group.id,
        TableGroupMembership.active_slot == 1,
    ).order_by(TableGroupMembership.table_resource_id).with_for_update())).all())
    await _close_group(db, group=group, members=members,
                       actor_membership_id=actor_membership_id,
                       event_type='CLOSE_GROUP', correlation_id=correlation_id)


async def assert_table_can_open_service(
    db: AsyncSession, *, tenant_id: int, location_id: int, resource_id: int,
) -> None:
    profile = await db.scalar(select(RestaurantTableProfile).where(
        RestaurantTableProfile.tenant_id == tenant_id,
        RestaurantTableProfile.location_id == location_id,
        RestaurantTableProfile.resource_id == resource_id,
    ))
    if profile is not None and profile.administrative_status != 'ACTIVE':
        raise TableManagementConflictError('Table is not administratively ACTIVE')
    membership = await db.scalar(select(TableGroupMembership).where(
        TableGroupMembership.tenant_id == tenant_id,
        TableGroupMembership.location_id == location_id,
        TableGroupMembership.table_resource_id == resource_id,
        TableGroupMembership.active_slot == 1,
    ))
    if membership is not None and not membership.is_representative:
        raise TableManagementConflictError('Only the representative Table may open group service')


async def move_section(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
    destination_section_id: int, expected_version: int,
    actor_membership_id: int, correlation_id: str | None,
) -> TableProjection:
    try:
        resources = await _lock_resources(db, tenant_id=tenant_id, location_id=location_id, resource_ids={table_resource_id})
        profile = await db.scalar(select(RestaurantTableProfile).where(
            RestaurantTableProfile.resource_id == table_resource_id,
            RestaurantTableProfile.tenant_id == tenant_id,
        ).with_for_update())
        destination = await db.scalar(select(DiningSection).where(
            DiningSection.id == destination_section_id,
            DiningSection.tenant_id == tenant_id,
            DiningSection.location_id == location_id,
            DiningSection.status == 'ACTIVE',
        ))
        if profile is None or destination is None:
            raise TableManagementNotFoundError('Table metadata or destination Dining Section not found')
        source = await db.scalar(select(DiningSection).where(DiningSection.id == profile.dining_section_id))
        if profile.version != expected_version:
            raise TableManagementConflictError('Table metadata changed; refresh and retry')
        await _assert_available(db, resources=resources, profiles={table_resource_id: (profile, source)})
        before = {'dining_section_id': profile.dining_section_id, 'administrative_status': profile.administrative_status}
        profile.dining_section_id = destination.id
        profile.version += 1
        after = {'dining_section_id': destination.id, 'administrative_status': profile.administrative_status}
        _history(db, group=None, table_resource_id=table_resource_id, event_type='MOVE_SECTION',
                 actor_membership_id=actor_membership_id, result_version=profile.version,
                 before=before, after=after, correlation_id=correlation_id,
                 tenant_id=tenant_id, organization_id=profile.organization_id, location_id=location_id)
        await _commit(db)
        return next(value for value in await list_tables(db, tenant_id=tenant_id, location_id=location_id) if value.resource_id == table_resource_id)
    except Exception:
        if db.in_transaction(): await db.rollback()
        raise


async def transition_administrative_status(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
    target_status: str, expected_version: int, actor_membership_id: int,
    correlation_id: str | None,
) -> TableProjection:
    try:
        await _lock_resources(db, tenant_id=tenant_id, location_id=location_id, resource_ids={table_resource_id})
        profile = await db.scalar(select(RestaurantTableProfile).where(
            RestaurantTableProfile.resource_id == table_resource_id,
            RestaurantTableProfile.tenant_id == tenant_id,
        ).with_for_update())
        if profile is None:
            raise TableManagementNotFoundError('Table metadata not found')
        if profile.version != expected_version:
            raise TableManagementConflictError('Table metadata changed; refresh and retry')
        _assert_administrative_transition(profile.administrative_status, target_status)
        if target_status == profile.administrative_status:
            raise TableManagementConflictError('Administrative status transition is not allowed')
        if await db.scalar(select(RestaurantServiceSession.id).where(
            RestaurantServiceSession.resource_id == table_resource_id,
            RestaurantServiceSession.status == 'OPEN',
        ).limit(1).with_for_update()) is not None:
            raise TableManagementConflictError('Table has an OPEN Service Session')
        if await db.scalar(select(TableGroupMembership.id).where(
            TableGroupMembership.table_resource_id == table_resource_id,
            TableGroupMembership.active_slot == 1,
        ).limit(1).with_for_update()) is not None:
            raise TableManagementConflictError('Table belongs to an ACTIVE TableGroup')
        before = {'administrative_status': profile.administrative_status}
        profile.administrative_status = target_status
        profile.version += 1
        after = {'administrative_status': target_status}
        _history(db, group=None, table_resource_id=table_resource_id,
                 event_type='ADMIN_STATUS_CHANGE', actor_membership_id=actor_membership_id,
                 result_version=profile.version, before=before, after=after,
                 correlation_id=correlation_id, tenant_id=tenant_id,
                 organization_id=profile.organization_id, location_id=location_id)
        await _commit(db)
        return next(value for value in await list_tables(db, tenant_id=tenant_id, location_id=location_id) if value.resource_id == table_resource_id)
    except Exception:
        if db.in_transaction(): await db.rollback()
        raise


async def get_group(
    db: AsyncSession, *, tenant_id: int, location_id: int, group_id: int,
) -> GroupProjection:
    group = await db.scalar(select(TableGroup).where(
        TableGroup.id == group_id, TableGroup.tenant_id == tenant_id,
        TableGroup.location_id == location_id,
    ))
    if group is None:
        raise TableManagementNotFoundError('TableGroup not found')
    members = list((await db.scalars(select(TableGroupMembership).where(
        TableGroupMembership.table_group_id == group.id,
        TableGroupMembership.active_slot == 1,
    ).order_by(TableGroupMembership.is_representative.desc(), TableGroupMembership.table_resource_id))).all())
    historical_capacity: int | None = None
    if group.status == 'CLOSED':
        latest = await db.scalar(select(TableManagementHistory).where(
            TableManagementHistory.table_group_id == group.id,
        ).order_by(TableManagementHistory.result_version.desc(), TableManagementHistory.id.desc()).limit(1))
        state = None if latest is None else latest.after_state
        ids = [] if not isinstance(state, dict) else list(state.get('member_resource_ids', []))
        historical_capacity = None if not isinstance(state, dict) else state.get('derived_capacity')
    else:
        ids = [value.table_resource_id for value in members]
    resource_rows = (await db.execute(select(Resource.id, Resource.code).where(Resource.id.in_(ids or [-1])))).all()
    codes = dict(resource_rows)
    capacities = dict((await db.execute(select(RestaurantTableProfile.resource_id, RestaurantTableProfile.physical_capacity).where(
        RestaurantTableProfile.resource_id.in_(ids or [-1]),
    ))).all())
    responsible = tuple((await db.scalars(select(TableGroupResponsibleWaiter.waiter_membership_id).where(
        TableGroupResponsibleWaiter.table_group_id == group.id,
    ).order_by(TableGroupResponsibleWaiter.waiter_membership_id))).all())
    return GroupProjection(
        id=group.id, representative_resource_id=group.representative_resource_id,
        representative_code=codes[group.representative_resource_id],
        status=group.status, version=group.version,
        member_resource_ids=tuple(ids), member_codes=tuple(codes[value] for value in ids),
        responsible_membership_ids=responsible,
        derived_capacity=(
            int(historical_capacity) if historical_capacity is not None
            else sum(capacities[value] for value in ids) - ((len(ids) - 1) * 2)
        ),
        created_by_membership_id=group.created_by_membership_id,
        created_at=group.created_at, closed_by_membership_id=group.closed_by_membership_id,
        closed_at=group.closed_at,
    )


async def get_active_group(
    db: AsyncSession, *, tenant_id: int, location_id: int, representative_resource_id: int,
) -> GroupProjection | None:
    group_id = await db.scalar(select(TableGroup.id).where(
        TableGroup.tenant_id == tenant_id, TableGroup.location_id == location_id,
        TableGroup.representative_resource_id == representative_resource_id,
        TableGroup.status == 'ACTIVE',
    ))
    return None if group_id is None else await get_group(db, tenant_id=tenant_id, location_id=location_id, group_id=group_id)


async def group_history(
    db: AsyncSession, *, tenant_id: int, location_id: int, group_id: int,
) -> tuple[TableManagementHistory, ...]:
    if await db.scalar(select(TableGroup.id).where(
        TableGroup.id == group_id, TableGroup.tenant_id == tenant_id,
        TableGroup.location_id == location_id,
    )) is None:
        raise TableManagementNotFoundError('TableGroup not found')
    return tuple((await db.scalars(select(TableManagementHistory).where(
        TableManagementHistory.tenant_id == tenant_id,
        TableManagementHistory.location_id == location_id,
        TableManagementHistory.table_group_id == group_id,
    ).order_by(TableManagementHistory.recorded_at, TableManagementHistory.id))).all())


async def table_history(
    db: AsyncSession, *, tenant_id: int, location_id: int, table_resource_id: int,
) -> tuple[TableManagementHistory, ...]:
    if await db.scalar(select(Resource.id).where(
        Resource.id == table_resource_id, Resource.tenant_id == tenant_id,
        Resource.location_id == location_id, Resource.resource_type == 'TABLE',
    )) is None:
        raise TableManagementNotFoundError('Table not found')
    return tuple((await db.scalars(select(TableManagementHistory).where(
        TableManagementHistory.tenant_id == tenant_id,
        TableManagementHistory.location_id == location_id,
        TableManagementHistory.table_resource_id == table_resource_id,
    ).order_by(TableManagementHistory.recorded_at, TableManagementHistory.id))).all())
