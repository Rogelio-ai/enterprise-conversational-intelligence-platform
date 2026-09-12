"""expand physical count authority to full scope

Revision ID: 0047_physical_count_full_scope
Revises: 0046_physical_count_reconciliation
Create Date: 2026-09-12
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0047_physical_count_full_scope'
down_revision: str | None = '0046_physical_count_reconciliation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
CONSTRAINT = 'ck_physical_counts_scope'


def _scope_constraint() -> dict | None:
    for value in sa.inspect(op.get_bind()).get_check_constraints('physical_counts'):
        if value['name'] == CONSTRAINT:
            return value
    return None


def _replace_scope_constraint(expression: str) -> None:
    if _scope_constraint() is not None:
        op.drop_constraint(CONSTRAINT, 'physical_counts', type_='check')
    op.create_check_constraint(CONSTRAINT, 'physical_counts', expression)


def upgrade() -> None:
    current = _scope_constraint()
    sql = (current or {}).get('sqltext', '').replace('`', '').replace(' ', '').upper()
    if "COUNTSCOPEIN('PARTIAL','FULL')" not in sql.replace('_', ''):
        _replace_scope_constraint("count_scope IN ('PARTIAL','FULL')")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM physical_counts WHERE count_scope='FULL'")):
        raise RuntimeError('Cannot downgrade 0047: FULL physical count evidence exists')
    _replace_scope_constraint("count_scope='PARTIAL'")
