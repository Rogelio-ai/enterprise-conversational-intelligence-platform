"""add client-safe payment executor configuration

Revision ID: 0039_payment_executor_client_configuration
Revises: 0038_diner_operational_requests
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0039_payment_executor_client_configuration'
down_revision: str | None = '0038_diner_operational_requests'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'location_payment_executor_configurations',
        sa.Column(
            'client_public_key',
            sa.String(256, collation='ascii_bin'),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        'ck_payment_executor_configurations_client_public_key',
        'location_payment_executor_configurations',
        "client_public_key IS NULL OR (CHAR_LENGTH(client_public_key) BETWEEN 1 AND 256 "
        "AND TRIM(client_public_key) <> '')",
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_payment_executor_configurations_client_public_key',
        'location_payment_executor_configurations',
        type_='check',
    )
    op.drop_column('location_payment_executor_configurations', 'client_public_key')
