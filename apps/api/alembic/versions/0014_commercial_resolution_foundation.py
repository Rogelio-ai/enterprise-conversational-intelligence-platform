"""establish commercial resolution Promotion policy

Revision ID: 0014_commercial_resolution_foundation
Revises: 0013_order_draft_foundation
Create Date: 2026-08-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0014_commercial_resolution_foundation'
down_revision: str | None = '0013_order_draft_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'promotions',
        sa.Column('is_combinable', sa.Boolean(), server_default=sa.text('0'), nullable=False),
    )
    op.add_column(
        'promotions',
        sa.Column('priority', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    op.create_check_constraint(
        'ck_promotions_is_combinable', 'promotions', 'is_combinable IN (0, 1)'
    )
    op.create_check_constraint('ck_promotions_priority', 'promotions', 'priority >= 0')


def downgrade() -> None:
    op.drop_constraint('ck_promotions_priority', 'promotions', type_='check')
    op.drop_constraint('ck_promotions_is_combinable', 'promotions', type_='check')
    op.drop_column('promotions', 'priority')
    op.drop_column('promotions', 'is_combinable')
