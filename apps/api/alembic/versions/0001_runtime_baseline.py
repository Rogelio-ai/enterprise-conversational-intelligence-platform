"""establish runtime migration baseline

Revision ID: 0001_runtime_baseline
Revises:
Create Date: 2026-08-15
"""
from collections.abc import Sequence


revision: str = '0001_runtime_baseline'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Alembic's version table is the only schema artifact required now."""


def downgrade() -> None:
    """No application schema objects exist in this baseline."""
