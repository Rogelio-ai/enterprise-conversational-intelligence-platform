"""add scoped Menu Section import-key bindings

Revision ID: 0055_menu_section_import_binding
Revises: 0054_menu_import_binding
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0055_menu_section_import_binding'
down_revision: str | None = '0054_menu_import_binding'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'menu_section_external_mappings',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('menu_id', sa.BigInteger(), nullable=False),
        sa.Column('section_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_key', sa.String(128), nullable=False),
        sa.Column(
            'external_section_id',
            sa.String(200, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(),
            server_default=sa.func.current_timestamp(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_menu_section_external_mappings_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['section_id', 'menu_id', 'tenant_id', 'organization_id'],
            [
                'menu_sections.id',
                'menu_sections.menu_id',
                'menu_sections.tenant_id',
                'menu_sections.organization_id',
            ],
            name='fk_menu_section_external_mappings_section_scope',
            ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'menu_id', 'connector_key',
            'external_section_id',
            name='uq_menu_section_external_mapping_source',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_menu_section_external_mappings_section',
        'menu_section_external_mappings',
        ['tenant_id', 'organization_id', 'menu_id', 'section_id', 'id'],
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text(
        'SELECT COUNT(*) FROM menu_section_external_mappings'
    )).scalar_one():
        raise RuntimeError('Cannot downgrade 0055 while Menu Section bindings exist')
    op.drop_index(
        'ix_menu_section_external_mappings_section',
        table_name='menu_section_external_mappings',
    )
    op.drop_table('menu_section_external_mappings')
