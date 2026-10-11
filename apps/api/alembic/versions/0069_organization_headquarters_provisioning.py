"""add organization headquarters and minimal provisioning evidence

Revision ID: 0069_org_hq_provisioning
Revises: 0068_schema_collation_alignment

The backfill selects a headquarters only when an Organization has exactly one
ACTIVE Location. Zero or multiple candidates remain explicitly unconfigured.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0069_org_hq_provisioning'
down_revision: str | None = '0068_schema_collation_alignment'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('headquarters_location_id', sa.BigInteger(), nullable=True),
    )
    op.execute(sa.text(
        'UPDATE organizations AS organization '
        'JOIN ('
        '  SELECT tenant_id, organization_id, MAX(id) AS location_id '
        '  FROM locations WHERE status = \'ACTIVE\' '
        '  GROUP BY tenant_id, organization_id HAVING COUNT(*) = 1'
        ') AS candidate '
        'ON candidate.tenant_id = organization.tenant_id '
        'AND candidate.organization_id = organization.id '
        'SET organization.headquarters_location_id = candidate.location_id '
        'WHERE organization.headquarters_location_id IS NULL'
    ))
    op.create_foreign_key(
        'fk_organizations_headquarters_scope',
        'organizations', 'locations',
        ['headquarters_location_id', 'tenant_id', 'id'],
        ['id', 'tenant_id', 'organization_id'],
        ondelete='RESTRICT',
    )

    op.create_table(
        'organization_headquarters_changes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('previous_location_id', sa.BigInteger(), nullable=True),
        sa.Column('new_location_id', sa.BigInteger(), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('operation_id', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column(
            'changed_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_headquarters_changes_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['previous_location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_headquarters_changes_previous_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['new_location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_headquarters_changes_new_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_headquarters_changes_actor_scope', ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'operation_id', name='uq_headquarters_changes_operation',
        ),
    )
    op.create_index(
        'ix_headquarters_changes_organization_time',
        'organization_headquarters_changes',
        ['tenant_id', 'organization_id', 'changed_at', 'id'],
    )

    op.create_table(
        'minimal_provisioning_runs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('operation_id', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('manifest_version', sa.SmallInteger(), nullable=False),
        sa.Column('request_fingerprint', sa.CHAR(64, collation='ascii_bin'), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('staff_user_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'completed_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_minimal_provisioning_runs_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_minimal_provisioning_runs_actor_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_minimal_provisioning_runs_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_minimal_provisioning_runs_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['staff_user_id'], ['users.id'],
            name='fk_minimal_provisioning_runs_staff_user', ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'operation_id', name='uq_minimal_provisioning_runs_operation',
        ),
    )
    op.create_index(
        'ix_minimal_provisioning_runs_organization',
        'minimal_provisioning_runs',
        ['tenant_id', 'organization_id', 'id'],
    )


def downgrade() -> None:
    raise RuntimeError(
        '0069 is forward-only: headquarters and provisioning evidence cannot be '
        'removed without discarding governed state'
    )
