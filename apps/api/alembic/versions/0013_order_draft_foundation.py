"""establish canonical Restaurant Order Draft foundation

Revision ID: 0013_order_draft_foundation
Revises: 0012_product_resolution_foundation
Create Date: 2026-08-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0013_order_draft_foundation'
down_revision: str | None = '0012_product_resolution_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WS_14_PERMISSIONS = {
    'order_draft.read': 'Read canonical Restaurant Order Drafts.',
    'order_draft.manage': 'Manage canonical Restaurant Order Drafts.',
}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
    )


def _options() -> dict[str, str]:
    return {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
    }


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('code', sa.String()),
        sa.column('description', sa.String()),
    )
    roles = sa.table(
        'roles',
        sa.column('id', sa.BigInteger()),
        sa.column('name', sa.String()),
        sa.column('status', sa.String()),
    )
    role_permissions = sa.table(
        'role_permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()),
        sa.column('permission_id', sa.BigInteger()),
    )
    role_ids = tuple(
        connection.execute(
            sa.select(roles.c.id).where(
                roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE'
            )
        ).scalars()
    )
    for code, description in WS_14_PERMISSIONS.items():
        permission_id = connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(
                sa.select(permissions.c.id).where(permissions.c.code == code)
            ).scalar_one()
        for role_id in role_ids:
            assignment = connection.execute(
                sa.select(role_permissions.c.id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            ).scalar_one_or_none()
            if assignment is None:
                connection.execute(
                    role_permissions.insert().values(
                        role_id=role_id, permission_id=permission_id
                    )
                )


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_conversations_id_tenant_org_location',
        'conversations',
        ['id', 'tenant_id', 'organization_id', 'location_id'],
    )
    op.create_unique_constraint(
        'uq_product_compositions_id_tenant_org_product',
        'product_compositions',
        ['id', 'tenant_id', 'organization_id', 'product_id'],
    )
    op.create_unique_constraint(
        'uq_product_choice_groups_id_tenant_org_composition',
        'product_choice_groups',
        ['id', 'tenant_id', 'organization_id', 'composition_id'],
    )
    op.create_unique_constraint(
        'uq_product_choice_options_id_tenant_org_group',
        'product_choice_options',
        ['id', 'tenant_id', 'organization_id', 'group_id'],
    )

    options = _options()
    op.create_table(
        'order_drafts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('conversation_id', sa.BigInteger(), nullable=False),
        sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('version >= 1', name='ck_order_drafts_version'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_order_drafts_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_order_drafts_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_order_drafts_location_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['conversation_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'conversations.id',
                'conversations.tenant_id',
                'conversations.organization_id',
                'conversations.location_id',
            ],
            name='fk_order_drafts_conversation_scope',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'conversation_id', name='uq_order_drafts_tenant_conversation'
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_order_drafts_id_tenant_org'
        ),
        **options,
    )
    op.create_index(
        'ix_order_drafts_tenant_org_location',
        'order_drafts',
        ['tenant_id', 'organization_id', 'location_id', 'id'],
    )

    op.create_table(
        'order_draft_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('draft_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('composition_id', sa.BigInteger(), nullable=True),
        sa.Column('quantity', sa.Numeric(19, 4), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('quantity > 0', name='ck_order_draft_items_quantity'),
        sa.CheckConstraint('position >= 0', name='ck_order_draft_items_position'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_order_draft_items_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['draft_id', 'tenant_id', 'organization_id'],
            ['order_drafts.id', 'order_drafts.tenant_id', 'order_drafts.organization_id'],
            name='fk_order_draft_items_draft_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_order_draft_items_product_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['composition_id', 'tenant_id', 'organization_id', 'product_id'],
            [
                'product_compositions.id',
                'product_compositions.tenant_id',
                'product_compositions.organization_id',
                'product_compositions.product_id',
            ],
            name='fk_order_draft_items_composition_product',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('draft_id', 'position', name='uq_order_draft_items_draft_position'),
        sa.UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            'draft_id',
            'composition_id',
            name='uq_order_draft_items_selection_scope',
        ),
        **options,
    )
    op.create_index(
        'ix_order_draft_items_tenant_draft_order',
        'order_draft_items',
        ['tenant_id', 'draft_id', 'position', 'id'],
    )
    op.create_index(
        'ix_order_draft_items_tenant_org_product',
        'order_draft_items',
        ['tenant_id', 'organization_id', 'product_id', 'id'],
    )

    op.create_table(
        'order_draft_item_selections',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('draft_id', sa.BigInteger(), nullable=False),
        sa.Column('draft_item_id', sa.BigInteger(), nullable=False),
        sa.Column('composition_id', sa.BigInteger(), nullable=False),
        sa.Column('choice_group_id', sa.BigInteger(), nullable=False),
        sa.Column('choice_option_id', sa.BigInteger(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_order_draft_item_selections_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['draft_item_id', 'tenant_id', 'organization_id', 'draft_id', 'composition_id'],
            [
                'order_draft_items.id',
                'order_draft_items.tenant_id',
                'order_draft_items.organization_id',
                'order_draft_items.draft_id',
                'order_draft_items.composition_id',
            ],
            name='fk_order_draft_selections_item_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['choice_group_id', 'tenant_id', 'organization_id', 'composition_id'],
            [
                'product_choice_groups.id',
                'product_choice_groups.tenant_id',
                'product_choice_groups.organization_id',
                'product_choice_groups.composition_id',
            ],
            name='fk_order_draft_selections_group_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['choice_option_id', 'tenant_id', 'organization_id', 'choice_group_id'],
            [
                'product_choice_options.id',
                'product_choice_options.tenant_id',
                'product_choice_options.organization_id',
                'product_choice_options.group_id',
            ],
            name='fk_order_draft_selections_option_scope',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'draft_item_id',
            'choice_option_id',
            name='uq_order_draft_selections_item_option',
        ),
        **options,
    )
    op.create_index(
        'ix_order_draft_selections_tenant_item_group',
        'order_draft_item_selections',
        ['tenant_id', 'draft_item_id', 'choice_group_id', 'choice_option_id'],
    )
    op.create_index(
        'ix_order_draft_selections_tenant_choice',
        'order_draft_item_selections',
        ['tenant_id', 'organization_id', 'choice_group_id', 'choice_option_id', 'id'],
    )
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('order_draft_item_selections')
    op.drop_table('order_draft_items')
    op.drop_table('order_drafts')
    op.drop_constraint(
        'uq_product_choice_options_id_tenant_org_group',
        'product_choice_options',
        type_='unique',
    )
    op.drop_constraint(
        'uq_product_choice_groups_id_tenant_org_composition',
        'product_choice_groups',
        type_='unique',
    )
    op.drop_constraint(
        'uq_product_compositions_id_tenant_org_product',
        'product_compositions',
        type_='unique',
    )
    op.drop_constraint(
        'uq_conversations_id_tenant_org_location', 'conversations', type_='unique'
    )
    # Preserve global permission rows and grants; their later provenance is unknowable.
