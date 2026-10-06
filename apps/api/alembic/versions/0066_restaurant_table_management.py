"""add bounded restaurant table management foundation

Revision ID: 0066_restaurant_table_management
Revises: 0065_staff_auth_session_foundation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0066_restaurant_table_management'
down_revision: str | None = '0065_staff_auth_session_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def upgrade() -> None:
    op.create_table(
        'dining_sections',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('movable', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('status', sa.String(16), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_dining_sections_location_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_dining_sections_scope'),
        sa.UniqueConstraint('location_id', 'code', name='uq_dining_sections_location_code'),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_dining_sections_status'),
        **OPTIONS,
    )
    op.create_index('ix_dining_sections_location_status', 'dining_sections', ['tenant_id', 'location_id', 'status', 'id'])
    op.create_table(
        'restaurant_table_profiles',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('dining_section_id', sa.BigInteger(), nullable=False),
        sa.Column('physical_capacity', sa.Integer(), nullable=False),
        sa.Column('movable', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('administrative_status', sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column('version', sa.BigInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_restaurant_table_profiles_resource_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['dining_section_id', 'tenant_id', 'organization_id', 'location_id'],
            ['dining_sections.id', 'dining_sections.tenant_id', 'dining_sections.organization_id', 'dining_sections.location_id'],
            name='fk_restaurant_table_profiles_section_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('resource_id', name='uq_restaurant_table_profiles_resource'),
        sa.CheckConstraint('physical_capacity BETWEEN 1 AND 999', name='ck_restaurant_table_profiles_capacity'),
        sa.CheckConstraint("administrative_status IN ('ACTIVE','SUSPENDED','OUT_OF_SERVICE','RETIRED')", name='ck_restaurant_table_profiles_admin_status'),
        sa.CheckConstraint('movable IN (0,1)', name='ck_restaurant_table_profiles_movable'),
        sa.CheckConstraint('version >= 1', name='ck_restaurant_table_profiles_version'),
        **OPTIONS,
    )
    op.create_index('ix_restaurant_table_profiles_section', 'restaurant_table_profiles', ['tenant_id', 'location_id', 'dining_section_id', 'resource_id'])
    op.create_table(
        'table_groups',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('representative_resource_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column('active_slot', sa.SmallInteger(), nullable=True, server_default=sa.text('1')),
        sa.Column('version', sa.BigInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_by_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('closed_by_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['representative_resource_id', 'tenant_id', 'location_id'], ['resources.id', 'resources.tenant_id', 'resources.location_id'], name='fk_table_groups_representative_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_table_groups_creator', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['closed_by_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_table_groups_closer', ondelete='RESTRICT'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_table_groups_scope'),
        sa.UniqueConstraint('representative_resource_id', 'active_slot', name='uq_table_groups_representative_active'),
        sa.CheckConstraint("status IN ('ACTIVE','CLOSED')", name='ck_table_groups_status'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_table_groups_active_slot'),
        sa.CheckConstraint('version >= 1', name='ck_table_groups_version'),
        sa.CheckConstraint("(status='ACTIVE' AND active_slot=1 AND closed_at IS NULL AND closed_by_membership_id IS NULL) OR (status='CLOSED' AND active_slot IS NULL AND closed_at IS NOT NULL AND closed_by_membership_id IS NOT NULL)", name='ck_table_groups_lifecycle'),
        **OPTIONS,
    )
    op.create_index('ix_table_groups_location_status', 'table_groups', ['tenant_id', 'location_id', 'status', 'id'])
    op.create_table(
        'table_group_memberships',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('table_group_id', sa.BigInteger(), nullable=False),
        sa.Column('table_resource_id', sa.BigInteger(), nullable=False),
        sa.Column('is_representative', sa.Boolean(), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), nullable=True, server_default=sa.text('1')),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('removed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['table_group_id', 'tenant_id', 'organization_id', 'location_id'], ['table_groups.id', 'table_groups.tenant_id', 'table_groups.organization_id', 'table_groups.location_id'], name='fk_table_group_memberships_group_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['table_resource_id', 'tenant_id', 'location_id'], ['resources.id', 'resources.tenant_id', 'resources.location_id'], name='fk_table_group_memberships_table_scope', ondelete='RESTRICT'),
        sa.UniqueConstraint('table_resource_id', 'active_slot', name='uq_table_group_memberships_table_active'),
        sa.CheckConstraint('is_representative IN (0,1)', name='ck_table_group_memberships_representative'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_table_group_memberships_active_slot'),
        sa.CheckConstraint('(active_slot=1 AND removed_at IS NULL) OR (active_slot IS NULL AND removed_at IS NOT NULL)', name='ck_table_group_memberships_lifecycle'),
        **OPTIONS,
    )
    op.create_index('ix_table_group_memberships_group_active', 'table_group_memberships', ['table_group_id', 'active_slot', 'id'])
    op.create_table(
        'table_group_responsible_waiters',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('table_group_id', sa.BigInteger(), nullable=False),
        sa.Column('waiter_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['table_group_id', 'tenant_id', 'organization_id', 'location_id'], ['table_groups.id', 'table_groups.tenant_id', 'table_groups.organization_id', 'table_groups.location_id'], name='fk_table_group_responsible_waiters_group_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['waiter_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_table_group_responsible_waiters_waiter', ondelete='RESTRICT'),
        sa.UniqueConstraint('table_group_id', 'waiter_membership_id', name='uq_table_group_responsible_waiters'),
        **OPTIONS,
    )
    op.create_table(
        'table_management_history',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('table_group_id', sa.BigInteger(), nullable=True),
        sa.Column('table_resource_id', sa.BigInteger(), nullable=True),
        sa.Column('event_type', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('result_version', sa.BigInteger(), nullable=False),
        sa.Column('before_state', sa.JSON(), nullable=True),
        sa.Column('after_state', sa.JSON(), nullable=True),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['actor_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_table_management_history_actor', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['table_group_id', 'tenant_id', 'organization_id', 'location_id'], ['table_groups.id', 'table_groups.tenant_id', 'table_groups.organization_id', 'table_groups.location_id'], name='fk_table_management_history_group_scope', ondelete='RESTRICT'),
        sa.CheckConstraint("event_type IN ('CREATE_GROUP','ADD_TABLE','REMOVE_TABLE','DISSOLVE_GROUP','CLOSE_GROUP','MOVE_SECTION','ADMIN_STATUS_CHANGE')", name='ck_table_management_history_event_type'),
        sa.CheckConstraint('result_version >= 1', name='ck_table_management_history_version'),
        **OPTIONS,
    )
    op.create_index('ix_table_management_history_location_time', 'table_management_history', ['tenant_id', 'location_id', 'recorded_at', 'id'])
    op.create_index('ix_table_management_history_group', 'table_management_history', ['table_group_id', 'result_version', 'id'])

    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    connection = op.get_bind()
    connection.execute(permissions.insert().values(code='table_management.manage', description='Manage dining sections, table lifecycle, movement, and groups.'))
    permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == 'table_management.manage')).scalar_one()
    admin_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for role_id in admin_ids:
        connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def downgrade() -> None:
    connection = op.get_bind()
    permission_id = connection.execute(sa.text("SELECT id FROM permissions WHERE code='table_management.manage'")).scalar_one_or_none()
    if permission_id is not None:
        connection.execute(sa.text('DELETE FROM role_permissions WHERE permission_id=:permission_id'), {'permission_id': permission_id})
        connection.execute(sa.text('DELETE FROM permissions WHERE id=:permission_id'), {'permission_id': permission_id})
    op.drop_index('ix_table_management_history_group', table_name='table_management_history')
    op.drop_index('ix_table_management_history_location_time', table_name='table_management_history')
    op.drop_table('table_management_history')
    op.drop_table('table_group_responsible_waiters')
    op.drop_index('ix_table_group_memberships_group_active', table_name='table_group_memberships')
    op.drop_table('table_group_memberships')
    op.drop_index('ix_table_groups_location_status', table_name='table_groups')
    op.drop_table('table_groups')
    op.drop_index('ix_restaurant_table_profiles_section', table_name='restaurant_table_profiles')
    op.drop_table('restaurant_table_profiles')
    op.drop_index('ix_dining_sections_location_status', table_name='dining_sections')
    op.drop_table('dining_sections')
