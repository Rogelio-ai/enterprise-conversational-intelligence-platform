"""add canonical Staff username login

Revision ID: 0063_staff_username_login
Revises: 0062_conversation_responder_foundation
"""
from collections.abc import Sequence
import re

from alembic import op
import sqlalchemy as sa


revision: str = '0063_staff_username_login'
down_revision: str | None = '0062_conversation_responder_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_username(email: str | None, user_id: int) -> str:
    source = (email or '').partition('@')[0].strip().casefold()
    value = re.sub(r'[^a-z0-9._-]+', '-', source).strip('._-')
    if len(value) < 3:
        value = f'staff-{user_id}'
    return value[:64].rstrip('._-')


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('username', sa.String(64, collation='ascii_bin'), nullable=True),
    )
    op.alter_column(
        'users', 'email', existing_type=sa.String(320), nullable=True,
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        'SELECT DISTINCT users.id, users.email FROM users '
        'JOIN tenant_memberships ON tenant_memberships.user_id = users.id '
        'ORDER BY users.id'
    )).mappings().all()
    used: set[str] = set()
    for row in rows:
        base = _base_username(row['email'], row['id'])
        candidate = base
        if candidate in used:
            suffix = f'-{row["id"]}'
            candidate = f'{base[:64 - len(suffix)].rstrip("._-")}{suffix}'
        used.add(candidate)
        bind.execute(
            sa.text('UPDATE users SET username=:username WHERE id=:user_id'),
            {'username': candidate, 'user_id': row['id']},
        )
    op.create_unique_constraint('uq_users_username', 'users', ['username'])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM users WHERE email IS NULL')).scalar_one():
        raise RuntimeError('Cannot downgrade while Staff users without email exist')
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.alter_column(
        'users', 'email', existing_type=sa.String(320), nullable=False,
    )
    op.drop_column('users', 'username')
