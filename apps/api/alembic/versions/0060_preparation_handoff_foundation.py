"""add preparation physical handoff persistence foundation

Revision ID: 0060_preparation_handoff_foundation
Revises: 0059_service_responsibility_foundation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0060_preparation_handoff_foundation'
down_revision: str | None = '0059_service_responsibility_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'preparation_works',
        sa.Column('picked_up_by_membership_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'preparation_works',
        sa.Column('picked_up_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'preparation_works',
        sa.Column('delivered_by_membership_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'preparation_works',
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
    )
    op.create_unique_constraint(
        'uq_preparation_works_id_tenant',
        'preparation_works',
        ['id', 'tenant_id'],
    )
    op.create_foreign_key(
        'fk_preparation_works_pickup_actor_tenant',
        'preparation_works',
        'tenant_memberships',
        ['picked_up_by_membership_id', 'tenant_id'],
        ['id', 'tenant_id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_preparation_works_delivery_actor_tenant',
        'preparation_works',
        'tenant_memberships',
        ['delivered_by_membership_id', 'tenant_id'],
        ['id', 'tenant_id'],
        ondelete='RESTRICT',
    )
    op.create_check_constraint(
        'ck_preparation_works_pickup_pair',
        'preparation_works',
        '(picked_up_by_membership_id IS NULL AND picked_up_at IS NULL) OR '
        '(picked_up_by_membership_id IS NOT NULL AND picked_up_at IS NOT NULL)',
    )
    op.create_check_constraint(
        'ck_preparation_works_delivery_pair',
        'preparation_works',
        '(delivered_by_membership_id IS NULL AND delivered_at IS NULL) OR '
        '(delivered_by_membership_id IS NOT NULL AND delivered_at IS NOT NULL)',
    )
    op.create_check_constraint(
        'ck_preparation_works_delivery_requires_pickup',
        'preparation_works',
        'delivered_by_membership_id IS NULL OR picked_up_by_membership_id IS NOT NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_preparation_works_delivery_requires_pickup',
        'preparation_works',
        type_='check',
    )
    op.drop_constraint(
        'ck_preparation_works_delivery_pair',
        'preparation_works',
        type_='check',
    )
    op.drop_constraint(
        'ck_preparation_works_pickup_pair',
        'preparation_works',
        type_='check',
    )
    op.drop_constraint(
        'fk_preparation_works_delivery_actor_tenant',
        'preparation_works',
        type_='foreignkey',
    )
    op.drop_constraint(
        'fk_preparation_works_pickup_actor_tenant',
        'preparation_works',
        type_='foreignkey',
    )
    op.drop_constraint(
        'uq_preparation_works_id_tenant',
        'preparation_works',
        type_='unique',
    )
    op.drop_column('preparation_works', 'delivered_at')
    op.drop_column('preparation_works', 'delivered_by_membership_id')
    op.drop_column('preparation_works', 'picked_up_at')
    op.drop_column('preparation_works', 'picked_up_by_membership_id')
