"""add authoritative staff location grants

Revision ID: 0040_staff_location_authorization_scope
Revises: 0039_payment_executor_client_configuration
Create Date: 2026-09-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0040_staff_location_authorization_scope'
down_revision: str | None = '0039_payment_executor_client_configuration'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'membership_location_grants',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('membership_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_membership_location_grants_membership_tenant',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id'],
            ['locations.id', 'locations.tenant_id'],
            name='fk_membership_location_grants_location_tenant',
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'membership_id', 'location_id',
            name='uq_membership_location_grants_membership_location',
        ),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )


def downgrade() -> None:
    op.drop_table('membership_location_grants')
