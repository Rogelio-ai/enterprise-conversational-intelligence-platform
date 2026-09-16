from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class OnboardingImport(TimestampMixin, Base):
    """Durable, pilot-scoped replay and result evidence for Stage 0 imports."""

    __tablename__ = 'onboarding_imports'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_onboarding_imports_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_onboarding_imports_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_onboarding_imports_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_onboarding_imports_actor_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('import_id', name='uq_onboarding_imports_public_id'),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'contract_version',
            'dataset_fingerprint', name='uq_onboarding_imports_replay_identity',
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS','SUCCESS','FAILED','PARTIAL')",
            name='ck_onboarding_imports_status',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[str] = mapped_column(String(36, collation='ascii_bin'), nullable=False)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16, collation='ascii_bin'), nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class OnboardingStaffContinuation(TimestampMixin, Base):
    """Secret-free continuation from Staff invitation to authorized access."""

    __tablename__ = 'onboarding_staff_continuations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_staff_continuations_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_staff_continuations_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_staff_continuations_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_staff_continuations_actor_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'continuation_id', name='uq_staff_continuations_public_id',
        ),
        UniqueConstraint(
            'tenant_id', 'normalized_email', 'role_name', 'location_id',
            name='uq_staff_continuations_logical_request',
        ),
        CheckConstraint(
            "status IN ('PENDING_ACCEPTANCE','COMPLETE','SECURITY_CONFLICT','TERMINAL_FAILURE')",
            name='ck_staff_continuations_status',
        ),
        CheckConstraint(
            "completion_operation IS NULL OR completion_operation IN ('CREATE','UNCHANGED')",
            name='ck_staff_continuations_completion_operation',
        ),
        CheckConstraint(
            "(status='PENDING_ACCEPTANCE' AND identity_invitation_id IS NOT NULL "
            "AND user_id IS NULL AND completion_operation IS NULL "
            "AND error_code IS NULL AND completed_at IS NULL) OR "
            "(status='COMPLETE' AND user_id IS NOT NULL "
            "AND completion_operation IS NOT NULL AND error_code IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status='SECURITY_CONFLICT' AND completion_operation IS NULL "
            "AND error_code IS NOT NULL AND completed_at IS NULL) OR "
            "(status='TERMINAL_FAILURE' AND completion_operation IS NULL "
            "AND error_code IS NOT NULL AND completed_at IS NOT NULL)",
            name='ck_staff_continuations_lifecycle',
        ),
        Index(
            'ix_staff_continuations_resume',
            'tenant_id', 'status', 'normalized_email', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    continuation_id: Mapped[str] = mapped_column(
        String(36, collation='ascii_bin'), nullable=False,
    )
    onboarding_import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('onboarding_imports.id', ondelete='RESTRICT'),
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    identity_invitation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey('identity_invitations.id', ondelete='RESTRICT'),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('users.id', ondelete='RESTRICT'), nullable=True,
    )
    staff_key: Mapped[str] = mapped_column(
        String(100, collation='utf8mb4_bin'), nullable=False,
    )
    normalized_email: Mapped[str] = mapped_column(
        String(320, collation='utf8mb4_bin'), nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_name: Mapped[str] = mapped_column(
        String(100, collation='utf8mb4_bin'), nullable=False,
    )
    requested_permission_codes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False,
    )
    completion_operation: Mapped[str | None] = mapped_column(
        String(16, collation='ascii_bin'), nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
