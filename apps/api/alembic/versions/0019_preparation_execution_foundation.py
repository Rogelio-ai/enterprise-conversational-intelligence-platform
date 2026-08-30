"""establish native preparation execution foundation

Revision ID: 0019_preparation_execution_foundation
Revises: 0018_preparation_routing_foundation
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0019_preparation_execution_foundation'
down_revision: str | None = '0018_preparation_routing_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _seed_permission() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    code = 'preparation.execute'
    permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
    if permission_id is None:
        connection.execute(permissions.insert().values(code=code, description='Execute native Preparation Work Items.'))
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for role_id in role_ids:
        if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
            connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    op.add_column('preparation_work_items', sa.Column('execution_state', sa.String(16), server_default=sa.text("'NEW'"), nullable=False))
    op.add_column('preparation_work_items', sa.Column('execution_version', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.create_check_constraint('ck_preparation_work_items_execution_state', 'preparation_work_items', "execution_state IN ('NEW','IN_PROGRESS','COMPLETED')")
    op.create_check_constraint('ck_preparation_work_items_execution_version', 'preparation_work_items', 'execution_version >= 0')
    op.create_unique_constraint(
        'uq_preparation_work_items_execution_scope', 'preparation_work_items',
        ['id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id'],
    )
    op.create_index('ix_preparation_work_items_queue', 'preparation_work_items', ['tenant_id', 'location_id', 'execution_state', 'preparation_work_id', 'id'])

    op.create_table(
        'preparation_item_transitions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_work_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_work_item_id', sa.BigInteger(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('from_state', sa.String(16), nullable=False),
        sa.Column('to_state', sa.String(16), nullable=False),
        sa.Column('actor_type', sa.String(32), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_principal_reference', sa.String(128), nullable=True),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'preparation_work_item_id', 'sequence', name='uq_preparation_item_transitions_sequence'),
        sa.UniqueConstraint('tenant_id', 'preparation_work_item_id', 'idempotency_key', name='uq_preparation_item_transitions_idempotency'),
        sa.CheckConstraint('sequence >= 1', name='ck_preparation_item_transitions_sequence'),
        sa.CheckConstraint("(from_state = 'NEW' AND to_state = 'IN_PROGRESS') OR (from_state = 'IN_PROGRESS' AND to_state = 'COMPLETED')", name='ck_preparation_item_transitions_edge'),
        sa.CheckConstraint("(actor_type = 'EMPLOYEE' AND actor_membership_id IS NOT NULL AND actor_principal_reference IS NULL) OR (actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_membership_id IS NULL AND actor_principal_reference IS NOT NULL)", name='ck_preparation_item_transitions_actor'),
        sa.ForeignKeyConstraint(
            ['preparation_work_item_id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id'],
            ['preparation_work_items.id', 'preparation_work_items.tenant_id', 'preparation_work_items.organization_id', 'preparation_work_items.location_id', 'preparation_work_items.restaurant_order_id', 'preparation_work_items.preparation_work_id'],
            name='fk_preparation_item_transitions_item_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(['actor_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_preparation_item_transitions_membership', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_item_transitions_ordered', 'preparation_item_transitions', ['tenant_id', 'preparation_work_item_id', 'sequence', 'id'])
    _seed_permission()


def downgrade() -> None:
    op.drop_table('preparation_item_transitions')
    op.drop_index('ix_preparation_work_items_queue', table_name='preparation_work_items')
    op.drop_constraint('uq_preparation_work_items_execution_scope', 'preparation_work_items', type_='unique')
    op.drop_constraint('ck_preparation_work_items_execution_version', 'preparation_work_items', type_='check')
    op.drop_constraint('ck_preparation_work_items_execution_state', 'preparation_work_items', type_='check')
    op.drop_column('preparation_work_items', 'execution_version')
    op.drop_column('preparation_work_items', 'execution_state')
    # Preserve global permission rows and grants; their later provenance is unknowable.
