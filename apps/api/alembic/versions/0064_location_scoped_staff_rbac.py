"""add Location-scoped Staff role assignments

Revision ID: 0064_location_scoped_staff_rbac
Revises: 0063_staff_username_login
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0064_location_scoped_staff_rbac'
down_revision: str | None = '0063_staff_username_login'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_membership_location_grants_membership_location_tenant',
        'membership_location_grants',
        ['membership_id', 'location_id', 'tenant_id'],
    )
    op.create_table(
        'membership_location_roles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('membership_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('role_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.ForeignKeyConstraint(
            ['membership_id', 'location_id', 'tenant_id'],
            [
                'membership_location_grants.membership_id',
                'membership_location_grants.location_id',
                'membership_location_grants.tenant_id',
            ],
            name='fk_membership_location_roles_grant',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['role_id', 'tenant_id'], ['roles.id', 'roles.tenant_id'],
            name='fk_membership_location_roles_role_tenant',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'membership_id', 'location_id', 'role_id',
            name='uq_membership_location_roles_membership_location_role',
        ),
    )
    op.execute(sa.text(
        'INSERT INTO membership_location_roles '
        '(tenant_id,membership_id,location_id,role_id) '
        'SELECT grants.tenant_id,grants.membership_id,grants.location_id,roles.role_id '
        'FROM membership_location_grants grants '
        'JOIN membership_roles roles '
        'ON roles.tenant_id=grants.tenant_id '
        'AND roles.membership_id=grants.membership_id'
    ))


def downgrade() -> None:
    op.drop_table('membership_location_roles')
    op.drop_constraint(
        'uq_membership_location_grants_membership_location_tenant',
        'membership_location_grants', type_='unique',
    )
