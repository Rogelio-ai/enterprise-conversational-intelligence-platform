from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
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
