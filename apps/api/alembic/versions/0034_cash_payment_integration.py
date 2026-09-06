"""link cash payment custody movements to RestaurantPayment

Revision ID: 0034_cash_payment_integration
Revises: 0033_cash_movement_count_close
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0034_cash_payment_integration'
down_revision: str | None = '0033_cash_movement_count_close'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'cash_movements',
        sa.Column('restaurant_payment_id', sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        'uq_cash_movements_payment_type',
        'cash_movements',
        ['restaurant_payment_id', 'movement_type'],
    )
    op.create_check_constraint(
        'ck_cash_movements_payment_relation',
        'cash_movements',
        "(movement_type IN ('CUSTOMER_TENDER','CUSTOMER_CHANGE') "
        "AND restaurant_payment_id IS NOT NULL) OR "
        "(movement_type NOT IN ('CUSTOMER_TENDER','CUSTOMER_CHANGE') "
        "AND restaurant_payment_id IS NULL)",
    )
    op.create_foreign_key(
        'fk_cash_movements_payment_scope',
        'cash_movements',
        'restaurant_payments',
        [
            'restaurant_payment_id', 'tenant_id', 'organization_id',
            'location_id',
        ],
        ['id', 'tenant_id', 'organization_id', 'location_id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_cash_movements_payment_scope', 'cash_movements',
        type_='foreignkey',
    )
    op.drop_constraint(
        'ck_cash_movements_payment_relation', 'cash_movements', type_='check',
    )
    op.drop_constraint(
        'uq_cash_movements_payment_type', 'cash_movements', type_='unique',
    )
    op.drop_column('cash_movements', 'restaurant_payment_id')
