"""add Stage 0 onboarding import replay evidence

Revision ID: 0052_onboarding_import_evidence
Revises: 0051_atomic_transfers_fifo
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0052_onboarding_import_evidence'
down_revision: str | None = '0051_atomic_transfers_fifo'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'onboarding_imports',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('import_id', sa.String(36, collation='ascii_bin'), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('contract_version', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('dataset_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(16, collation='ascii_bin'), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_onboarding_imports_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_onboarding_imports_organization_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_onboarding_imports_location_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['actor_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_onboarding_imports_actor_scope', ondelete='RESTRICT'),
        sa.UniqueConstraint('import_id', name='uq_onboarding_imports_public_id'),
        sa.UniqueConstraint('tenant_id', 'organization_id', 'location_id', 'contract_version', 'dataset_fingerprint', name='uq_onboarding_imports_replay_identity'),
        sa.CheckConstraint("status IN ('IN_PROGRESS','SUCCESS','FAILED','PARTIAL')", name='ck_onboarding_imports_status'),
        **OPTIONS,
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT COUNT(*) FROM onboarding_imports')).scalar_one():
        raise RuntimeError('Cannot downgrade 0052 while onboarding import evidence exists')
    op.drop_table('onboarding_imports')
