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
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class TableWaiterAssignment(TimestampMixin, Base):
    __tablename__ = 'table_waiter_assignments'
    __table_args__ = (
        ForeignKeyConstraint(
            ['table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_table_waiter_assignments_table_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_waiter_assignments_waiter_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['waiter_membership_id', 'location_id'],
            ['membership_location_grants.membership_id', 'membership_location_grants.location_id'],
            name='fk_table_waiter_assignments_waiter_location', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'table_resource_id', 'waiter_membership_id',
            name='uq_table_waiter_assignments_table_waiter',
        ),
        CheckConstraint(
            'is_responsible IN (0, 1)', name='ck_table_waiter_assignments_responsible',
        ),
        Index(
            'ix_table_waiter_assignments_waiter_location',
            'tenant_id', 'location_id', 'waiter_membership_id', 'table_resource_id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    table_resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    waiter_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_responsible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text('0'),
    )


class TableWaiterAssignmentAudit(Base):
    __tablename__ = 'table_waiter_assignment_audits'
    __table_args__ = (
        ForeignKeyConstraint(
            ['table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_table_waiter_audits_table_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_waiter_audits_waiter_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_waiter_audits_actor_tenant', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'table_resource_id', 'result_version',
            name='uq_table_waiter_audits_table_version',
        ),
        CheckConstraint(
            "operation IN ('ASSIGN','UNASSIGN','RESPONSIBILITY_UPDATE')",
            name='ck_table_waiter_audits_operation',
        ),
        CheckConstraint('result_version >= 1', name='ck_table_waiter_audits_version'),
        Index(
            'ix_table_waiter_audits_scope_time',
            'tenant_id', 'location_id', 'table_resource_id', 'recorded_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    table_resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    waiter_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operation: Mapped[str] = mapped_column(String(32, collation='ascii_bin'), nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assigned_membership_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    responsible_membership_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp(),
    )
