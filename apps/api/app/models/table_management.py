from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


SCOPE = ('tenant_id', 'organization_id', 'location_id')


class DiningSection(TimestampMixin, Base):
    __tablename__ = 'dining_sections'
    __table_args__ = (
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_dining_sections_location_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', *SCOPE, name='uq_dining_sections_scope'),
        UniqueConstraint('location_id', 'code', name='uq_dining_sections_location_code'),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_dining_sections_status'),
        Index('ix_dining_sections_location_status', 'tenant_id', 'location_id', 'status', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    movable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('1'))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))


class RestaurantTableProfile(TimestampMixin, Base):
    __tablename__ = 'restaurant_table_profiles'
    __table_args__ = (
        ForeignKeyConstraint(
            ['resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_restaurant_table_profiles_resource_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['dining_section_id', 'tenant_id', 'organization_id', 'location_id'],
            ['dining_sections.id', 'dining_sections.tenant_id',
             'dining_sections.organization_id', 'dining_sections.location_id'],
            name='fk_restaurant_table_profiles_section_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('resource_id', name='uq_restaurant_table_profiles_resource'),
        CheckConstraint('physical_capacity BETWEEN 1 AND 999', name='ck_restaurant_table_profiles_capacity'),
        CheckConstraint(
            "administrative_status IN ('ACTIVE','SUSPENDED','OUT_OF_SERVICE','RETIRED')",
            name='ck_restaurant_table_profiles_admin_status',
        ),
        CheckConstraint('movable IN (0,1)', name='ck_restaurant_table_profiles_movable'),
        CheckConstraint('version >= 1', name='ck_restaurant_table_profiles_version'),
        Index('ix_restaurant_table_profiles_section', 'tenant_id', 'location_id', 'dining_section_id', 'resource_id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dining_section_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    movable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('1'))
    administrative_status: Mapped[str] = mapped_column(String(20), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default=text('1'))


class TableGroup(TimestampMixin, Base):
    __tablename__ = 'table_groups'
    __table_args__ = (
        ForeignKeyConstraint(
            ['representative_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_table_groups_representative_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['created_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_groups_creator', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['closed_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_groups_closer', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', *SCOPE, name='uq_table_groups_scope'),
        UniqueConstraint('representative_resource_id', 'active_slot', name='uq_table_groups_representative_active'),
        CheckConstraint("status IN ('ACTIVE','CLOSED')", name='ck_table_groups_status'),
        CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_table_groups_active_slot'),
        CheckConstraint('version >= 1', name='ck_table_groups_version'),
        CheckConstraint(
            "(status='ACTIVE' AND active_slot=1 AND closed_at IS NULL AND closed_by_membership_id IS NULL) OR "
            "(status='CLOSED' AND active_slot IS NULL AND closed_at IS NOT NULL AND closed_by_membership_id IS NOT NULL)",
            name='ck_table_groups_lifecycle',
        ),
        Index('ix_table_groups_location_status', 'tenant_id', 'location_id', 'status', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    representative_resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
    active_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default=text('1'))
    created_by_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    closed_by_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class TableGroupMembership(Base):
    __tablename__ = 'table_group_memberships'
    __table_args__ = (
        ForeignKeyConstraint(
            ['table_group_id', 'tenant_id', 'organization_id', 'location_id'],
            ['table_groups.id', 'table_groups.tenant_id', 'table_groups.organization_id', 'table_groups.location_id'],
            name='fk_table_group_memberships_group_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_table_group_memberships_table_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('table_resource_id', 'active_slot', name='uq_table_group_memberships_table_active'),
        CheckConstraint('is_representative IN (0,1)', name='ck_table_group_memberships_representative'),
        CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_table_group_memberships_active_slot'),
        CheckConstraint(
            '(active_slot=1 AND removed_at IS NULL) OR (active_slot IS NULL AND removed_at IS NOT NULL)',
            name='ck_table_group_memberships_lifecycle',
        ),
        Index('ix_table_group_memberships_group_active', 'table_group_id', 'active_slot', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    table_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    table_resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_representative: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    added_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.current_timestamp())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class TableGroupResponsibleWaiter(Base):
    __tablename__ = 'table_group_responsible_waiters'
    __table_args__ = (
        ForeignKeyConstraint(
            ['table_group_id', 'tenant_id', 'organization_id', 'location_id'],
            ['table_groups.id', 'table_groups.tenant_id', 'table_groups.organization_id', 'table_groups.location_id'],
            name='fk_table_group_responsible_waiters_group_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_group_responsible_waiters_waiter', ondelete='RESTRICT',
        ),
        UniqueConstraint('table_group_id', 'waiter_membership_id', name='uq_table_group_responsible_waiters'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    table_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    waiter_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.current_timestamp())


class TableManagementHistory(Base):
    __tablename__ = 'table_management_history'
    __table_args__ = (
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_management_history_actor', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['table_group_id', 'tenant_id', 'organization_id', 'location_id'],
            ['table_groups.id', 'table_groups.tenant_id', 'table_groups.organization_id', 'table_groups.location_id'],
            name='fk_table_management_history_group_scope', ondelete='RESTRICT',
        ),
        CheckConstraint(
            "event_type IN ('CREATE_GROUP','ADD_TABLE','REMOVE_TABLE','DISSOLVE_GROUP','CLOSE_GROUP','MOVE_SECTION','ADMIN_STATUS_CHANGE')",
            name='ck_table_management_history_event_type',
        ),
        CheckConstraint('result_version >= 1', name='ck_table_management_history_version'),
        Index('ix_table_management_history_location_time', 'tenant_id', 'location_id', 'recorded_at', 'id'),
        Index('ix_table_management_history_group', 'table_group_id', 'result_version', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    table_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    table_resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_type: Mapped[str] = mapped_column(String(32, collation='ascii_bin'), nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before_state: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=func.current_timestamp())
