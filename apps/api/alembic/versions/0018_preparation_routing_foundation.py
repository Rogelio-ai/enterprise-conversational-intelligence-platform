"""establish native preparation routing foundation

Revision ID: 0018_preparation_routing_foundation
Revises: 0017_pos_order_submission_recovery
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0018_preparation_routing_foundation'
down_revision: str | None = '0017_pos_order_submission_recovery'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WS_19_PERMISSIONS = {
    'preparation.read': 'Read preparation configuration, routing, and work.',
    'preparation.route': 'Route accepted Restaurant Orders to preparation.',
    'preparation.configure': 'Configure preparation ownership, areas, and product routes.',
}


def _options() -> dict[str, str]:
    return {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for code, description in WS_19_PERMISSIONS.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        for role_id in role_ids:
            if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
                connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.add_column('location_pos_connections', sa.Column('external_preparation_behavior', sa.String(40), server_default=sa.text("'MAY_PRODUCE_PREPARATION_OUTPUT'"), nullable=False))
    op.create_check_constraint('ck_location_pos_connections_preparation_behavior', 'location_pos_connections', "external_preparation_behavior IN ('NO_PREPARATION_OUTPUT','MAY_PRODUCE_PREPARATION_OUTPUT')")

    op.create_table(
        'location_preparation_configurations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_owner', sa.String(16), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_id', name='uq_location_preparation_configurations_location'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_location_preparation_configurations_scope'),
        sa.CheckConstraint("preparation_owner IN ('PLATFORM','EXTERNAL_POS')", name='ck_location_preparation_configurations_owner'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_location_preparation_configurations_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_location_preparation_configurations_location_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_location_preparation_configurations_lookup', 'location_preparation_configurations', ['tenant_id', 'location_id', 'id'])

    op.create_table(
        'preparation_areas',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=True),
        sa.Column('code', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_id', 'code', name='uq_preparation_areas_location_code'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_preparation_areas_scope'),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_preparation_areas_status'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_areas_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_preparation_areas_location_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_id', 'tenant_id', 'location_id'], ['resources.id', 'resources.tenant_id', 'resources.location_id'], name='fk_preparation_areas_resource_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_areas_lookup', 'preparation_areas', ['tenant_id', 'location_id', 'status', 'code', 'id'])

    op.create_table(
        'product_preparation_routes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('policy', sa.String(24), nullable=False),
        sa.Column('preparation_area_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_id', 'product_id', 'active_slot', name='uq_product_preparation_routes_current'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_product_preparation_routes_scope'),
        sa.CheckConstraint("policy IN ('AREA','COMPONENTS','NO_PREPARATION')", name='ck_product_preparation_routes_policy'),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_product_preparation_routes_status'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_product_preparation_routes_active_slot'),
        sa.CheckConstraint("(status = 'ACTIVE' AND active_slot = 1) OR (status = 'INACTIVE' AND active_slot IS NULL)", name='ck_product_preparation_routes_lifecycle'),
        sa.CheckConstraint("(policy = 'AREA' AND preparation_area_id IS NOT NULL) OR (policy IN ('COMPONENTS','NO_PREPARATION') AND preparation_area_id IS NULL)", name='ck_product_preparation_routes_area'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_product_preparation_routes_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_product_preparation_routes_location_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_product_preparation_routes_product_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['preparation_area_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_areas.id', 'preparation_areas.tenant_id', 'preparation_areas.organization_id', 'preparation_areas.location_id'], name='fk_product_preparation_routes_area_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_product_preparation_routes_lookup', 'product_preparation_routes', ['tenant_id', 'location_id', 'product_id', 'status', 'id'])

    op.create_table(
        'preparation_routings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_owner', sa.String(16), nullable=True),
        sa.Column('state', sa.String(24), nullable=False),
        sa.Column('routing_schema_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('routing_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('initiating_actor_type', sa.String(32), nullable=False),
        sa.Column('initiating_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('initiating_principal_reference', sa.String(128), nullable=True),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('error_code', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('error_detail', sa.String(500), nullable=True),
        sa.Column('routed_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'restaurant_order_id', name='uq_preparation_routings_order'),
        sa.UniqueConstraint('id', 'tenant_id', 'restaurant_order_id', name='uq_preparation_routings_scope'),
        sa.CheckConstraint("preparation_owner IS NULL OR preparation_owner IN ('PLATFORM','EXTERNAL_POS')", name='ck_preparation_routings_owner'),
        sa.CheckConstraint("state IN ('PENDING','ROUTED','EXTERNAL_POS_OWNED','ACTION_REQUIRED')", name='ck_preparation_routings_state'),
        sa.CheckConstraint('routing_schema_version >= 1', name='ck_preparation_routings_version'),
        sa.CheckConstraint("(initiating_actor_type = 'EMPLOYEE' AND initiating_membership_id IS NOT NULL AND initiating_principal_reference IS NULL) OR (initiating_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND initiating_membership_id IS NULL AND initiating_principal_reference IS NOT NULL)", name='ck_preparation_routings_actor'),
        sa.CheckConstraint("(state IN ('ROUTED','EXTERNAL_POS_OWNED') AND preparation_owner IS NOT NULL AND routed_at IS NOT NULL AND routing_fingerprint IS NOT NULL AND error_code IS NULL) OR (state = 'PENDING' AND preparation_owner IS NOT NULL AND routed_at IS NULL AND error_code IS NULL) OR (state = 'ACTION_REQUIRED' AND routed_at IS NULL AND error_code IS NOT NULL)", name='ck_preparation_routings_lifecycle'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_routings_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'], name='fk_preparation_routings_order_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['initiating_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_preparation_routings_membership', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_routings_state', 'preparation_routings', ['tenant_id', 'state', 'location_id', 'id'])

    op.create_table(
        'preparation_works',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('routing_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_area_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_owner', sa.String(16), nullable=False),
        sa.Column('area_code_snapshot', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('area_name_snapshot', sa.String(200), nullable=False),
        sa.Column('routing_schema_version', sa.Integer(), nullable=False),
        sa.Column('routing_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('routed_at', sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'restaurant_order_id', 'preparation_area_id', name='uq_preparation_works_order_area'),
        sa.UniqueConstraint('id', 'tenant_id', 'restaurant_order_id', name='uq_preparation_works_scope'),
        sa.CheckConstraint("preparation_owner = 'PLATFORM'", name='ck_preparation_works_owner'),
        sa.CheckConstraint('routing_schema_version >= 1', name='ck_preparation_works_version'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_works_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['routing_id', 'tenant_id', 'restaurant_order_id'], ['preparation_routings.id', 'preparation_routings.tenant_id', 'preparation_routings.restaurant_order_id'], name='fk_preparation_works_routing_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['preparation_area_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_areas.id', 'preparation_areas.tenant_id', 'preparation_areas.organization_id', 'preparation_areas.location_id'], name='fk_preparation_works_area_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_works_area', 'preparation_works', ['tenant_id', 'location_id', 'preparation_area_id', 'id'])

    op.create_table(
        'preparation_work_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_work_id', sa.BigInteger(), nullable=False),
        sa.Column('source_restaurant_order_item_id', sa.BigInteger(), nullable=True),
        sa.Column('source_restaurant_order_item_component_id', sa.BigInteger(), nullable=True),
        sa.Column('source_restaurant_order_item_id_for_component', sa.BigInteger(), nullable=True),
        sa.Column('route_id', sa.BigInteger(), nullable=False),
        sa.Column('route_policy', sa.String(24), nullable=False),
        sa.Column('required_quantity', sa.Numeric(19, 4), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_id', name='uq_preparation_work_items_source_item'),
        sa.UniqueConstraint('tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_component_id', name='uq_preparation_work_items_source_component'),
        sa.CheckConstraint('required_quantity > 0', name='ck_preparation_work_items_quantity'),
        sa.CheckConstraint("route_policy = 'AREA'", name='ck_preparation_work_items_policy'),
        sa.CheckConstraint('(source_restaurant_order_item_id IS NOT NULL AND source_restaurant_order_item_component_id IS NULL AND source_restaurant_order_item_id_for_component IS NULL) OR (source_restaurant_order_item_id IS NULL AND source_restaurant_order_item_component_id IS NOT NULL AND source_restaurant_order_item_id_for_component IS NOT NULL)', name='ck_preparation_work_items_source_xor'),
        sa.ForeignKeyConstraint(['preparation_work_id', 'tenant_id', 'restaurant_order_id'], ['preparation_works.id', 'preparation_works.tenant_id', 'preparation_works.restaurant_order_id'], name='fk_preparation_work_items_work_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_preparation_work_items_source_item_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_restaurant_order_item_component_id', 'tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_id_for_component'], ['restaurant_order_item_components.id', 'restaurant_order_item_components.tenant_id', 'restaurant_order_item_components.order_id', 'restaurant_order_item_components.order_item_id'], name='fk_preparation_work_items_source_component_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['route_id', 'tenant_id', 'organization_id', 'location_id'], ['product_preparation_routes.id', 'product_preparation_routes.tenant_id', 'product_preparation_routes.organization_id', 'product_preparation_routes.location_id'], name='fk_preparation_work_items_route_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_work_items_ordered', 'preparation_work_items', ['tenant_id', 'preparation_work_id', 'id'])
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('preparation_work_items')
    op.drop_table('preparation_works')
    op.drop_table('preparation_routings')
    op.drop_table('product_preparation_routes')
    op.drop_table('preparation_areas')
    op.drop_table('location_preparation_configurations')
    op.drop_constraint('ck_location_pos_connections_preparation_behavior', 'location_pos_connections', type_='check')
    op.drop_column('location_pos_connections', 'external_preparation_behavior')
    # Preserve global permission rows and grants; their later provenance is unknowable.
