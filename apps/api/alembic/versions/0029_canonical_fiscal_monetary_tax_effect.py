"""freeze canonical fiscal monetary and tax-effect evidence

Revision ID: 0029_canonical_fiscal_monetary_tax_effect
Revises: 0028_canonical_fiscal_product_evidence
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0029_canonical_fiscal_monetary_tax_effect'
down_revision: str | None = '0028_canonical_fiscal_product_evidence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'restaurant_tax_rules',
        sa.Column(
            'tax_effect', sa.String(16), server_default=sa.text("'TRANSFERRED'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'ck_restaurant_tax_rules_effect',
        'restaurant_tax_rules',
        "tax_effect IN ('TRANSFERRED', 'WITHHELD')",
    )

    op.add_column(
        'restaurant_order_item_tax_snapshots',
        sa.Column('tax_effect', sa.String(16), nullable=True),
    )
    op.add_column(
        'restaurant_order_item_tax_snapshots',
        sa.Column('fiscal_unit_value', sa.Numeric(19, 4), nullable=True),
    )
    op.add_column(
        'restaurant_order_item_tax_snapshots',
        sa.Column('fiscal_line_amount', sa.Numeric(19, 4), nullable=True),
    )
    op.add_column(
        'restaurant_order_item_tax_snapshots',
        sa.Column('fiscal_discount_amount', sa.Numeric(19, 4), nullable=True),
    )
    op.create_check_constraint(
        'ck_order_item_tax_snapshots_effect',
        'restaurant_order_item_tax_snapshots',
        "tax_effect IS NULL OR tax_effect IN ('TRANSFERRED', 'WITHHELD')",
    )
    op.create_check_constraint(
        'ck_order_item_tax_snapshots_fiscal_money',
        'restaurant_order_item_tax_snapshots',
        '(fiscal_unit_value IS NULL AND fiscal_line_amount IS NULL '
        'AND fiscal_discount_amount IS NULL AND tax_effect IS NULL) OR '
        '(fiscal_unit_value IS NOT NULL AND fiscal_line_amount IS NOT NULL '
        'AND fiscal_discount_amount IS NOT NULL AND tax_effect IS NOT NULL '
        'AND fiscal_unit_value >= 0 AND fiscal_line_amount >= 0 '
        'AND fiscal_discount_amount >= 0 '
        'AND fiscal_line_amount - fiscal_discount_amount = taxable_base)',
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_order_item_tax_snapshots_fiscal_money',
        'restaurant_order_item_tax_snapshots', type_='check',
    )
    op.drop_constraint(
        'ck_order_item_tax_snapshots_effect',
        'restaurant_order_item_tax_snapshots', type_='check',
    )
    op.drop_column('restaurant_order_item_tax_snapshots', 'fiscal_discount_amount')
    op.drop_column('restaurant_order_item_tax_snapshots', 'fiscal_line_amount')
    op.drop_column('restaurant_order_item_tax_snapshots', 'fiscal_unit_value')
    op.drop_column('restaurant_order_item_tax_snapshots', 'tax_effect')
    op.drop_constraint(
        'ck_restaurant_tax_rules_effect', 'restaurant_tax_rules', type_='check'
    )
    op.drop_column('restaurant_tax_rules', 'tax_effect')
