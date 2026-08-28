"""establish canonical Restaurant Order commercial acceptance

Revision ID: 0016_canonical_order_commercial_acceptance
Revises: 0015_restaurant_service_diner_access_foundation
Create Date: 2026-08-28
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0016_canonical_order_commercial_acceptance'
down_revision: str | None = '0015_restaurant_service_diner_access_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def _options() -> dict[str, str]:
    return {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def _seed_permission() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == 'restaurant_order.read')).scalar_one_or_none()
    if permission_id is None:
        connection.execute(permissions.insert().values(code='restaurant_order.read', description='Read immutable accepted Restaurant Orders.'))
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == 'restaurant_order.read')).scalar_one()
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for role_id in role_ids:
        if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
            connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    op.add_column('order_drafts', sa.Column('status', sa.String(16), nullable=True))
    op.add_column('order_drafts', sa.Column('current_slot', sa.SmallInteger(), nullable=True))
    op.add_column('order_drafts', sa.Column('terminal_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE order_drafts SET status = 'OPEN', current_slot = 1, terminal_at = NULL")
    op.alter_column('order_drafts', 'status', existing_type=sa.String(16), nullable=False, server_default=sa.text("'OPEN'"))
    op.alter_column('order_drafts', 'current_slot', existing_type=sa.SmallInteger(), nullable=True, server_default=sa.text('1'))
    op.drop_constraint('uq_order_drafts_tenant_conversation', 'order_drafts', type_='unique')
    op.create_unique_constraint('uq_order_drafts_tenant_conversation_current', 'order_drafts', ['tenant_id', 'conversation_id', 'current_slot'])
    op.create_unique_constraint('uq_order_drafts_full_scope', 'order_drafts', ['id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id'])
    op.create_check_constraint('ck_order_drafts_status', 'order_drafts', "status IN ('OPEN', 'ACCEPTED', 'ABANDONED')")
    op.create_check_constraint('ck_order_drafts_current_slot', 'order_drafts', 'current_slot IS NULL OR current_slot = 1')
    op.create_check_constraint('ck_order_drafts_lifecycle', 'order_drafts', "(status = 'OPEN' AND current_slot = 1 AND terminal_at IS NULL) OR (status IN ('ACCEPTED', 'ABANDONED') AND current_slot IS NULL AND terminal_at IS NOT NULL)")
    op.create_unique_constraint('uq_diner_sessions_full_scope', 'diner_sessions', ['id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'])

    options = _options()
    money = lambda: sa.Numeric(19, 4)
    op.create_table(
        'restaurant_orders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('service_session_id', sa.BigInteger(), nullable=False),
        sa.Column('diner_session_id', sa.BigInteger(), nullable=False),
        sa.Column('customer_id', sa.BigInteger(), nullable=True),
        sa.Column('conversation_id', sa.BigInteger(), nullable=False),
        sa.Column('source_order_draft_id', sa.BigInteger(), nullable=False),
        sa.Column('source_channel', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACCEPTED'"), nullable=False),
        sa.Column('accepted_draft_version', sa.BigInteger(), nullable=False),
        sa.Column('confirmation_idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('commercial_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('fingerprint_schema_version', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('tax_mode', sa.String(16), nullable=False),
        sa.Column('rounding_policy', sa.String(32), nullable=False),
        sa.Column('subtotal', money(), nullable=False),
        sa.Column('total_discount', money(), nullable=False),
        sa.Column('pre_round_total', money(), nullable=False),
        sa.Column('rounding_adjustment', money(), nullable=False),
        sa.Column('payable_total', money(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_order_draft_id', name='uq_restaurant_orders_source_draft'),
        sa.UniqueConstraint('tenant_id', 'diner_session_id', 'confirmation_idempotency_key', name='uq_restaurant_orders_diner_idempotency'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_restaurant_orders_id_tenant'),
        sa.CheckConstraint("status = 'ACCEPTED'", name='ck_restaurant_orders_status'),
        sa.CheckConstraint('accepted_draft_version >= 1', name='ck_restaurant_orders_draft_version'),
        sa.CheckConstraint('fingerprint_schema_version >= 1', name='ck_restaurant_orders_fingerprint_version'),
        sa.CheckConstraint("tax_mode = 'INCLUDED'", name='ck_restaurant_orders_tax_mode'),
        sa.CheckConstraint("rounding_policy = 'WHOLE_UNIT_HALF_DOWN'", name='ck_restaurant_orders_rounding_policy'),
        sa.CheckConstraint('subtotal >= 0 AND total_discount >= 0 AND pre_round_total >= 0 AND payable_total >= 0', name='ck_restaurant_orders_money_nonnegative'),
        sa.CheckConstraint('pre_round_total = subtotal - total_discount', name='ck_restaurant_orders_pre_round_arithmetic'),
        sa.CheckConstraint('payable_total = pre_round_total + rounding_adjustment', name='ck_restaurant_orders_payable_arithmetic'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_orders_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'], ['restaurant_service_sessions.id', 'restaurant_service_sessions.tenant_id', 'restaurant_service_sessions.organization_id', 'restaurant_service_sessions.location_id', 'restaurant_service_sessions.resource_id'], name='fk_restaurant_orders_service_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'], ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id', 'diner_sessions.resource_id', 'diner_sessions.service_session_id', 'diner_sessions.conversation_id'], name='fk_restaurant_orders_diner_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'], ['conversations.id', 'conversations.tenant_id', 'conversations.organization_id', 'conversations.location_id', 'conversations.resource_id'], name='fk_restaurant_orders_conversation_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_order_draft_id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id'], ['order_drafts.id', 'order_drafts.tenant_id', 'order_drafts.organization_id', 'order_drafts.location_id', 'order_drafts.conversation_id'], name='fk_restaurant_orders_draft_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id', 'tenant_id'], ['customers.id', 'customers.tenant_id'], name='fk_restaurant_orders_customer_tenant', ondelete='RESTRICT'),
        **options,
    )
    for name, columns in (
        ('ix_restaurant_orders_diner_history', ['tenant_id', 'diner_session_id', 'accepted_at', 'id']),
        ('ix_restaurant_orders_service_history', ['tenant_id', 'service_session_id', 'accepted_at', 'id']),
        ('ix_restaurant_orders_conversation_history', ['tenant_id', 'conversation_id', 'accepted_at', 'id']),
        ('ix_restaurant_orders_location_staff', ['tenant_id', 'location_id', 'accepted_at', 'id']),
    ):
        op.create_index(name, 'restaurant_orders', columns)

    op.create_table(
        'restaurant_order_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('source_order_draft_item_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('composition_id', sa.BigInteger(), nullable=True),
        sa.Column('quantity', money(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('source_product_price_id', sa.BigInteger(), nullable=False),
        sa.Column('price_source', sa.String(16), nullable=False),
        sa.Column('unit_price', money(), nullable=False),
        sa.Column('base_amount', money(), nullable=False),
        sa.Column('discount_amount', money(), nullable=False),
        sa.Column('commercial_amount', money(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id', 'source_order_draft_item_id', name='uq_restaurant_order_items_source'),
        sa.UniqueConstraint('order_id', 'position', name='uq_restaurant_order_items_position'),
        sa.UniqueConstraint('id', 'tenant_id', 'order_id', name='uq_restaurant_order_items_scope'),
        sa.CheckConstraint('quantity > 0', name='ck_restaurant_order_items_quantity'),
        sa.CheckConstraint('position >= 0', name='ck_restaurant_order_items_position'),
        sa.CheckConstraint('unit_price >= 0 AND base_amount >= 0 AND discount_amount >= 0 AND commercial_amount >= 0', name='ck_restaurant_order_items_money'),
        sa.CheckConstraint('commercial_amount = base_amount - discount_amount', name='ck_restaurant_order_items_arithmetic'),
        sa.ForeignKeyConstraint(['order_id', 'tenant_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id'], name='fk_restaurant_order_items_order_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_restaurant_order_items_product_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_order_draft_item_id'], ['order_draft_items.id'], name='fk_restaurant_order_items_source_draft_item', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_product_price_id'], ['product_prices.id'], name='fk_restaurant_order_items_source_price', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['composition_id'], ['product_compositions.id'], name='fk_restaurant_order_items_source_composition', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_restaurant_order_items_ordered', 'restaurant_order_items', ['tenant_id', 'order_id', 'position', 'id'])

    op.create_table(
        'restaurant_order_item_components',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('order_item_id', sa.BigInteger(), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('source_component_id', sa.BigInteger(), nullable=True),
        sa.Column('source_choice_group_id', sa.BigInteger(), nullable=True),
        sa.Column('source_choice_option_id', sa.BigInteger(), nullable=True),
        sa.Column('choice_group_name', sa.String(200), nullable=True),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('quantity', money(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_item_id', 'position', name='uq_restaurant_order_components_position'),
        sa.CheckConstraint("kind IN ('FIXED', 'CHOICE')", name='ck_restaurant_order_components_kind'),
        sa.CheckConstraint('position >= 0 AND quantity > 0', name='ck_restaurant_order_components_values'),
        sa.CheckConstraint("(kind = 'FIXED' AND source_component_id IS NOT NULL AND source_choice_group_id IS NULL AND source_choice_option_id IS NULL AND choice_group_name IS NULL) OR (kind = 'CHOICE' AND source_component_id IS NULL AND source_choice_group_id IS NOT NULL AND source_choice_option_id IS NOT NULL AND choice_group_name IS NOT NULL)", name='ck_restaurant_order_components_source'),
        sa.ForeignKeyConstraint(['order_item_id', 'tenant_id', 'order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_restaurant_order_components_item_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_restaurant_order_components_product_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_component_id'], ['product_components.id'], name='fk_restaurant_order_components_source_component', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_choice_group_id'], ['product_choice_groups.id'], name='fk_restaurant_order_components_source_group', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_choice_option_id'], ['product_choice_options.id'], name='fk_restaurant_order_components_source_option', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_restaurant_order_components_ordered', 'restaurant_order_item_components', ['tenant_id', 'order_id', 'order_item_id', 'position', 'id'])

    op.create_table(
        'restaurant_order_promotions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('order_item_id', sa.BigInteger(), nullable=False),
        sa.Column('promotion_id', sa.BigInteger(), nullable=False),
        sa.Column('application_order', sa.Integer(), nullable=False),
        sa.Column('promotion_name', sa.String(200), nullable=False),
        sa.Column('promotion_type', sa.String(32), nullable=False),
        sa.Column('promotion_value', money(), nullable=False),
        sa.Column('promotion_currency', sa.String(3), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('is_combinable', sa.Boolean(), nullable=False),
        sa.Column('calculated_discount', money(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_item_id', 'application_order', name='uq_restaurant_order_promotions_order'),
        sa.CheckConstraint('application_order >= 0 AND priority >= 0', name='ck_restaurant_order_promotions_ordering'),
        sa.CheckConstraint('promotion_value > 0 AND calculated_discount >= 0', name='ck_restaurant_order_promotions_money'),
        sa.ForeignKeyConstraint(['order_item_id', 'tenant_id', 'order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_restaurant_order_promotions_item_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['promotion_id', 'tenant_id', 'organization_id'], ['promotions.id', 'promotions.tenant_id', 'promotions.organization_id'], name='fk_restaurant_order_promotions_source_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_restaurant_order_promotions_ordered', 'restaurant_order_promotions', ['tenant_id', 'order_id', 'order_item_id', 'application_order', 'id'])
    _seed_permission()


def downgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(sa.text('SELECT tenant_id, conversation_id FROM order_drafts GROUP BY tenant_id, conversation_id HAVING COUNT(*) > 1 LIMIT 1')).first()
    if duplicate is not None:
        raise RuntimeError('Cannot downgrade 0016: a Conversation has multiple historical Order Drafts')
    op.drop_table('restaurant_order_promotions')
    op.drop_table('restaurant_order_item_components')
    op.drop_table('restaurant_order_items')
    op.drop_table('restaurant_orders')
    op.drop_constraint('uq_diner_sessions_full_scope', 'diner_sessions', type_='unique')
    op.drop_constraint('ck_order_drafts_lifecycle', 'order_drafts', type_='check')
    op.drop_constraint('ck_order_drafts_current_slot', 'order_drafts', type_='check')
    op.drop_constraint('ck_order_drafts_status', 'order_drafts', type_='check')
    op.drop_constraint('uq_order_drafts_full_scope', 'order_drafts', type_='unique')
    op.drop_constraint('uq_order_drafts_tenant_conversation_current', 'order_drafts', type_='unique')
    op.create_unique_constraint('uq_order_drafts_tenant_conversation', 'order_drafts', ['tenant_id', 'conversation_id'])
    op.drop_column('order_drafts', 'terminal_at')
    op.drop_column('order_drafts', 'current_slot')
    op.drop_column('order_drafts', 'status')
    # Preserve global permission rows and grants; their later provenance is unknowable.
