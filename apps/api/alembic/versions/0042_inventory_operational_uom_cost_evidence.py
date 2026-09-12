"""add operational UOM and standard-cost evidence

Revision ID: 0042_inventory_operational_uom_cost_evidence
Revises: 0041_inventory_warehouse_ledger_compatibility
Create Date: 2026-09-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0042_inventory_operational_uom_cost_evidence'
down_revision: str | None = '0041_inventory_warehouse_ledger_compatibility'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_columns(table))


def _foreign_key(table: str, name: str) -> bool:
    return any(
        value['name'] == name for value in _inspector().get_foreign_keys(table)
    )


def _check(table: str, name: str) -> bool:
    return any(
        value['name'] == name for value in _inspector().get_check_constraints(table)
    )


def _index(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_indexes(table))


def _create_conversion_table() -> None:
    if _table('item_uom_conversions'):
        return
    op.create_table(
        'item_uom_conversions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('operational_uom', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('factor_to_base', sa.Numeric(25, 12), nullable=False),
        sa.Column('revision', sa.BigInteger(), nullable=False),
        sa.Column('effective_at', sa.DateTime(), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=False),
        sa.Column('reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            ['inventory_items.id', 'inventory_items.tenant_id', 'inventory_items.organization_id', 'inventory_items.location_id'],
            name='fk_item_uom_conversions_item_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id', name='uq_item_uom_conversions_scope'),
        sa.UniqueConstraint('inventory_item_id', 'operational_uom', 'revision', name='uq_item_uom_conversions_revision'),
        sa.CheckConstraint('factor_to_base > 0', name='ck_item_uom_conversions_factor'),
        sa.CheckConstraint('revision >= 1', name='ck_item_uom_conversions_revision'),
        sa.CheckConstraint("operational_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'", name='ck_item_uom_conversions_uom'),
        **OPTIONS,
    )
    op.create_index('ix_item_uom_conversions_resolve', 'item_uom_conversions', ['tenant_id', 'inventory_item_id', 'operational_uom', 'effective_at', 'revision'])


def _create_cost_table() -> None:
    if _table('inventory_cost_revisions'):
        return
    op.create_table(
        'inventory_cost_revisions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('revision', sa.BigInteger(), nullable=False),
        sa.Column('standard_unit_cost', sa.Numeric(19, 6), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column('effective_at', sa.DateTime(), nullable=False),
        sa.Column('source', sa.String(48, collation='ascii_bin'), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column('reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            ['inventory_items.id', 'inventory_items.tenant_id', 'inventory_items.organization_id', 'inventory_items.location_id'],
            name='fk_inventory_cost_revisions_item_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id', name='uq_inventory_cost_revisions_scope'),
        sa.UniqueConstraint('inventory_item_id', 'revision', name='uq_inventory_cost_revisions_revision'),
        sa.CheckConstraint('standard_unit_cost >= 0', name='ck_cost_revisions_cost'),
        sa.CheckConstraint('revision >= 1', name='ck_cost_revisions_revision'),
        sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_cost_revisions_currency'),
        **OPTIONS,
    )
    op.create_index('ix_inventory_cost_revisions_resolve', 'inventory_cost_revisions', ['tenant_id', 'inventory_item_id', 'effective_at', 'revision'])


MOVEMENT_COLUMNS = (
    ('source_quantity', sa.Numeric(19, 6), None),
    ('source_uom', sa.String(32, collation='ascii_bin'), None),
    ('conversion_revision_id', sa.BigInteger(), None),
    ('conversion_factor', sa.Numeric(25, 12), None),
    ('base_uom_evidence', sa.String(16), None),
    ('standard_cost_revision_id', sa.BigInteger(), None),
    ('standard_unit_cost_evidence', sa.Numeric(19, 6), None),
    ('cost_currency_evidence', sa.String(3, collation='ascii_bin'), None),
    ('extended_standard_cost', sa.Numeric(31, 12), None),
    ('evidence_status', sa.String(24), sa.text("'LEGACY_UNAVAILABLE'")),
)


def _add_evidence() -> None:
    for name, kind, default in MOVEMENT_COLUMNS:
        if not _column('stock_movements', name):
            op.add_column('stock_movements', sa.Column(
                name, kind, nullable=name != 'evidence_status', server_default=default,
            ))
    op.execute(sa.text(
        "UPDATE stock_movements SET source_quantity=quantity,"
        "source_uom=base_uom_snapshot,conversion_factor=1.000000000000,"
        "base_uom_evidence=base_uom_snapshot,"
        "standard_unit_cost_evidence=unit_cost_snapshot,"
        "cost_currency_evidence=currency_snapshot,"
        "extended_standard_cost=quantity*unit_cost_snapshot,"
        "evidence_status='LEGACY_SNAPSHOT' WHERE movement_type='CONSUMPTION' "
        "AND evidence_status='LEGACY_UNAVAILABLE'"
    ))
    if not _foreign_key('stock_movements', 'fk_stock_movements_conversion_scope'):
        op.create_foreign_key(
            'fk_stock_movements_conversion_scope', 'stock_movements',
            'item_uom_conversions',
            ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
            ondelete='RESTRICT',
        )
    if not _foreign_key('stock_movements', 'fk_stock_movements_cost_revision_scope'):
        op.create_foreign_key(
            'fk_stock_movements_cost_revision_scope', 'stock_movements',
            'inventory_cost_revisions',
            ['standard_cost_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
            ondelete='RESTRICT',
        )
    checks = {
        'ck_stock_movements_evidence_status': "evidence_status IN ('LEGACY_UNAVAILABLE','LEGACY_SNAPSHOT','RESOLVED','COST_NON_DERIVABLE')",
        'ck_stock_movements_operational_evidence_values': '(conversion_factor IS NULL OR conversion_factor > 0) AND (standard_unit_cost_evidence IS NULL OR standard_unit_cost_evidence >= 0)',
        'ck_stock_movements_quantity_evidence': "(evidence_status IN ('RESOLVED','COST_NON_DERIVABLE','LEGACY_SNAPSHOT') AND source_quantity IS NOT NULL AND source_uom IS NOT NULL AND conversion_factor IS NOT NULL AND base_uom_evidence IS NOT NULL) OR evidence_status='LEGACY_UNAVAILABLE'",
        'ck_stock_movements_standard_cost_evidence': "(evidence_status='RESOLVED' AND standard_cost_revision_id IS NOT NULL AND standard_unit_cost_evidence IS NOT NULL AND cost_currency_evidence IS NOT NULL AND extended_standard_cost IS NOT NULL) OR (evidence_status='COST_NON_DERIVABLE' AND standard_cost_revision_id IS NULL AND standard_unit_cost_evidence IS NULL AND cost_currency_evidence IS NULL AND extended_standard_cost IS NULL) OR evidence_status IN ('LEGACY_UNAVAILABLE','LEGACY_SNAPSHOT')",
    }
    for name, condition in checks.items():
        if not _check('stock_movements', name):
            op.create_check_constraint(name, 'stock_movements', condition)


def upgrade() -> None:
    _create_conversion_table()
    _create_cost_table()
    op.execute(sa.text(
        "INSERT INTO inventory_cost_revisions "
        "(tenant_id,organization_id,location_id,inventory_item_id,revision,"
        "standard_unit_cost,currency,effective_at,source,actor_id,reference) "
        "SELECT i.tenant_id,i.organization_id,i.location_id,i.id,1,"
        "i.standard_unit_cost,i.currency,CURRENT_TIMESTAMP,"
        "'LEGACY_STANDARD_COST_SNAPSHOT',NULL,'migration:0042' "
        "FROM inventory_items i WHERE NOT EXISTS "
        "(SELECT 1 FROM inventory_cost_revisions r WHERE r.inventory_item_id=i.id)"
    ))
    _add_evidence()


def downgrade() -> None:
    for name in (
        'fk_stock_movements_cost_revision_scope',
        'fk_stock_movements_conversion_scope',
    ):
        if _foreign_key('stock_movements', name):
            op.drop_constraint(name, 'stock_movements', type_='foreignkey')
        # MySQL/MariaDB retain the implicit supporting index after a foreign
        # key is removed. Drop it so a downgrade/re-upgrade can recreate the
        # named foreign key without colliding with a stale index.
        if _index('stock_movements', name):
            op.drop_index(name, table_name='stock_movements')
    for name in (
        'ck_stock_movements_standard_cost_evidence',
        'ck_stock_movements_quantity_evidence',
        'ck_stock_movements_operational_evidence_values',
        'ck_stock_movements_evidence_status',
    ):
        if _check('stock_movements', name):
            op.drop_constraint(name, 'stock_movements', type_='check')
    for name, _, _ in reversed(MOVEMENT_COLUMNS):
        if _column('stock_movements', name):
            op.drop_column('stock_movements', name)
    if _table('inventory_cost_revisions'):
        op.drop_table('inventory_cost_revisions')
    if _table('item_uom_conversions'):
        op.drop_table('item_uom_conversions')
