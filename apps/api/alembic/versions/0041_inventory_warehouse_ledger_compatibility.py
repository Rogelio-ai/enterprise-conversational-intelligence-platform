"""add warehouse-scoped inventory ledger compatibility

Revision ID: 0041_inventory_warehouse_ledger_compatibility
Revises: 0040_staff_location_authorization_scope
Create Date: 2026-09-11
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op


revision: str = '0041_inventory_warehouse_ledger_compatibility'
down_revision: str | None = '0040_staff_location_authorization_scope'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column_exists(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_columns(table))


def _index_exists(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_indexes(table))


def _unique_exists(table: str, name: str) -> bool:
    return any(
        value['name'] == name for value in _inspector().get_unique_constraints(table)
    )


def _foreign_key(table: str, name: str) -> dict[str, object] | None:
    return next(
        (
            value for value in _inspector().get_foreign_keys(table)
            if value['name'] == name
        ),
        None,
    )


def _check_exists(table: str, name: str) -> bool:
    return any(
        value['name'] == name for value in _inspector().get_check_constraints(table)
    )


def _create_warehouses() -> None:
    if _table_exists('warehouses'):
        return
    op.create_table(
        'warehouses',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'code', sa.String(64, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column('default_slot', sa.SmallInteger(), nullable=True),
        sa.Column(
            'negative_stock_policy', sa.String(8),
            server_default=sa.text("'ALLOW'"), nullable=False,
        ),
        sa.Column(
            'version', sa.BigInteger(), server_default=sa.text('1'), nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_warehouses_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_warehouses_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_warehouses_location_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_warehouses_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'code',
            name='uq_warehouses_location_code',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'default_slot',
            name='uq_warehouses_location_default',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')", name='ck_warehouses_status',
        ),
        sa.CheckConstraint(
            'default_slot IS NULL OR default_slot=1',
            name='ck_warehouses_default_slot',
        ),
        sa.CheckConstraint(
            "negative_stock_policy IN ('ALLOW','WARN','BLOCK')",
            name='ck_warehouses_negative_stock_policy',
        ),
        sa.CheckConstraint('version >= 1', name='ck_warehouses_version'),
        **OPTIONS,
    )
    op.create_index(
        'ix_warehouses_location_status', 'warehouses',
        ['tenant_id', 'location_id', 'status', 'id'], unique=False,
    )


def _create_default_warehouses() -> None:
    op.execute(sa.text(
        "INSERT INTO warehouses "
        "(tenant_id,organization_id,location_id,code,name,status,default_slot,"
        "negative_stock_policy,version) "
        "SELECT l.tenant_id,l.organization_id,l.id,'DEFAULT','Default Warehouse',"
        "'ACTIVE',1,'ALLOW',1 FROM locations l "
        "WHERE NOT EXISTS (SELECT 1 FROM warehouses w "
        "WHERE w.tenant_id=l.tenant_id AND w.organization_id=l.organization_id "
        "AND w.location_id=l.id AND w.default_slot=1)"
    ))


def _add_movement_columns() -> None:
    if not _column_exists('stock_movements', 'warehouse_id'):
        op.add_column(
            'stock_movements', sa.Column('warehouse_id', sa.BigInteger(), nullable=True)
        )
    if not _column_exists('stock_movements', 'negative_stock_policy'):
        op.add_column(
            'stock_movements',
            sa.Column(
                'negative_stock_policy', sa.String(8),
                server_default=sa.text("'ALLOW'"), nullable=False,
            ),
        )
    if not _column_exists('stock_movements', 'negative_stock_warning'):
        op.add_column(
            'stock_movements',
            sa.Column(
                'negative_stock_warning', sa.Boolean(),
                server_default=sa.text('0'), nullable=False,
            ),
        )
    if not _column_exists('stock_movements', 'resulting_stock_quantity'):
        op.add_column(
            'stock_movements',
            sa.Column('resulting_stock_quantity', sa.Numeric(19, 6), nullable=True),
        )


def _balance_rows(*, warehouse_scoped: bool) -> tuple[tuple[int, int, int, Decimal], ...]:
    connection = op.get_bind()
    warehouse_clause = ' AND warehouse_id IS NOT NULL' if warehouse_scoped else ''
    rows = connection.execute(sa.text(
        'SELECT tenant_id,location_id,inventory_item_id,SUM(quantity) AS quantity '
        'FROM stock_movements WHERE 1=1' + warehouse_clause +
        ' GROUP BY tenant_id,location_id,inventory_item_id '
        'ORDER BY tenant_id,location_id,inventory_item_id'
    )).all()
    return tuple(
        (int(row[0]), int(row[1]), int(row[2]), Decimal(row[3])) for row in rows
    )


def _backfill_movements() -> None:
    before = _balance_rows(warehouse_scoped=False)
    op.execute(sa.text(
        'UPDATE stock_movements sm JOIN warehouses w '
        'ON w.tenant_id=sm.tenant_id AND w.organization_id=sm.organization_id '
        'AND w.location_id=sm.location_id AND w.default_slot=1 '
        'SET sm.warehouse_id=w.id WHERE sm.warehouse_id IS NULL'
    ))
    missing = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM stock_movements WHERE warehouse_id IS NULL'
    )).scalar_one()
    if missing:
        raise RuntimeError('Warehouse backfill left stock movements without authority')
    after = _balance_rows(warehouse_scoped=True)
    if before != after:
        raise RuntimeError('Warehouse backfill changed an inventory balance')
    warehouse_column = next(
        value for value in _inspector().get_columns('stock_movements')
        if value['name'] == 'warehouse_id'
    )
    if warehouse_column['nullable']:
        op.alter_column(
            'stock_movements', 'warehouse_id', existing_type=sa.BigInteger(),
            nullable=False,
        )


def _add_movement_constraints() -> None:
    if not _unique_exists('stock_movements', 'uq_stock_movements_warehouse_scope'):
        op.create_unique_constraint(
            'uq_stock_movements_warehouse_scope', 'stock_movements',
            [
                'id', 'tenant_id', 'organization_id', 'location_id',
                'inventory_item_id', 'warehouse_id',
            ],
        )
    if _foreign_key('stock_movements', 'fk_stock_movements_warehouse_scope') is None:
        if _index_exists('stock_movements', 'fk_stock_movements_warehouse_scope'):
            op.drop_index(
                'fk_stock_movements_warehouse_scope',
                table_name='stock_movements',
            )
        op.create_foreign_key(
            'fk_stock_movements_warehouse_scope', 'stock_movements', 'warehouses',
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id'],
            ondelete='RESTRICT',
        )
    reversal = _foreign_key('stock_movements', 'fk_stock_movements_reversal_scope')
    expected_reversal_columns = (
        'reversal_of_movement_id', 'tenant_id', 'organization_id', 'location_id',
        'inventory_item_id', 'warehouse_id',
    )
    if reversal is not None and tuple(reversal['constrained_columns']) != expected_reversal_columns:
        op.drop_constraint(
            'fk_stock_movements_reversal_scope', 'stock_movements',
            type_='foreignkey',
        )
        reversal = None
    if reversal is None:
        op.create_foreign_key(
            'fk_stock_movements_reversal_scope', 'stock_movements',
            'stock_movements', list(expected_reversal_columns),
            [
                'id', 'tenant_id', 'organization_id', 'location_id',
                'inventory_item_id', 'warehouse_id',
            ], ondelete='RESTRICT',
        )
    if not _check_exists('stock_movements', 'ck_stock_movements_negative_policy'):
        op.create_check_constraint(
            'ck_stock_movements_negative_policy', 'stock_movements',
            "negative_stock_policy IN ('ALLOW','WARN','BLOCK')",
        )
    if not _index_exists('stock_movements', 'ix_stock_movements_warehouse_stock'):
        op.create_index(
            'ix_stock_movements_warehouse_stock', 'stock_movements',
            [
                'tenant_id', 'location_id', 'warehouse_id', 'inventory_item_id',
                'recorded_at', 'id',
            ], unique=False,
        )


def upgrade() -> None:
    _create_warehouses()
    _create_default_warehouses()
    _add_movement_columns()
    _backfill_movements()
    _add_movement_constraints()


def downgrade() -> None:
    reversal = _foreign_key('stock_movements', 'fk_stock_movements_reversal_scope')
    if reversal is not None:
        op.drop_constraint(
            'fk_stock_movements_reversal_scope', 'stock_movements',
            type_='foreignkey',
        )
    op.create_foreign_key(
        'fk_stock_movements_reversal_scope', 'stock_movements', 'stock_movements',
        [
            'reversal_of_movement_id', 'tenant_id', 'organization_id',
            'location_id', 'inventory_item_id',
        ],
        ['id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
        ondelete='RESTRICT',
    )
    if _foreign_key('stock_movements', 'fk_stock_movements_warehouse_scope') is not None:
        op.drop_constraint(
            'fk_stock_movements_warehouse_scope', 'stock_movements',
            type_='foreignkey',
        )
    if _index_exists('stock_movements', 'fk_stock_movements_warehouse_scope'):
        op.drop_index(
            'fk_stock_movements_warehouse_scope', table_name='stock_movements'
        )
    if _index_exists('stock_movements', 'ix_stock_movements_warehouse_stock'):
        op.drop_index(
            'ix_stock_movements_warehouse_stock', table_name='stock_movements'
        )
    if _check_exists('stock_movements', 'ck_stock_movements_negative_policy'):
        op.drop_constraint(
            'ck_stock_movements_negative_policy', 'stock_movements', type_='check'
        )
    if _unique_exists('stock_movements', 'uq_stock_movements_warehouse_scope'):
        op.drop_constraint(
            'uq_stock_movements_warehouse_scope', 'stock_movements', type_='unique'
        )
    for name in (
        'resulting_stock_quantity', 'negative_stock_warning',
        'negative_stock_policy', 'warehouse_id',
    ):
        if _column_exists('stock_movements', name):
            op.drop_column('stock_movements', name)
    if _table_exists('warehouses'):
        op.drop_table('warehouses')
