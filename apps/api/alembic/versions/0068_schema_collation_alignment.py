"""align four table-default collations with the canonical schema contract

Revision ID: 0068_schema_collation_alignment
Revises: 0067_internal_operational_message_foundation

MySQL executes ALTER TABLE with implicit commits and may acquire metadata locks.
If an upgrade is interrupted, inspect every target table's TABLE_COLLATION and
rerun this idempotent revision after resolving the operational failure.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0068_schema_collation_alignment'
down_revision: str | None = '0067_internal_operational_message_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAMES = (
    'billing_fiscal_results',
    'billing_fiscal_artifacts',
    'membership_location_roles',
    'staff_auth_sessions',
)


def upgrade() -> None:
    for table_name in TABLE_NAMES:
        op.execute(sa.text(
            f'ALTER TABLE `{table_name}` DEFAULT CHARACTER SET utf8mb4 '
            'COLLATE utf8mb4_unicode_ci'
        ))


def downgrade() -> None:
    raise RuntimeError(
        '0068 is forward-only: previous table defaults are environment-specific '
        'and cannot be reconstructed safely'
    )
