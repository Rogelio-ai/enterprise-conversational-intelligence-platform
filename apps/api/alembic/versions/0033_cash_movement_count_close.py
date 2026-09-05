"""add cash movement, count, and session close evidence

Revision ID: 0033_cash_movement_count_close
Revises: 0032_cash_management_foundation
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0033_cash_movement_count_close'
down_revision: str | None = '0032_cash_management_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _seed_permission() -> None:
    connection = op.get_bind()
    permissions = sa.table(
        'permissions', sa.column('id', sa.BigInteger()),
        sa.column('code', sa.String()), sa.column('description', sa.String()),
    )
    roles = sa.table(
        'roles', sa.column('id', sa.BigInteger()),
        sa.column('name', sa.String()), sa.column('status', sa.String()),
    )
    grants = sa.table(
        'role_permissions', sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()),
        sa.column('permission_id', sa.BigInteger()),
    )
    code = 'cash_movement.manage'
    permission_id = connection.execute(
        sa.select(permissions.c.id).where(permissions.c.code == code)
    ).scalar_one_or_none()
    if permission_id is None:
        connection.execute(permissions.insert().values(
            code=code, description='Record authorized manual cash movements.'
        ))
        permission_id = connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one()
    admin_role_ids = tuple(connection.execute(sa.select(roles.c.id).where(
        roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE'
    )).scalars())
    for role_id in admin_role_ids:
        exists = connection.execute(sa.select(grants.c.id).where(
            grants.c.role_id == role_id,
            grants.c.permission_id == permission_id,
        )).scalar_one_or_none()
        if exists is None:
            connection.execute(grants.insert().values(
                role_id=role_id, permission_id=permission_id
            ))


def _actor_check(prefix: str) -> str:
    field = f'{prefix}_' if prefix else ''
    return (
        f"({field}actor_type='EMPLOYEE' AND {field}actor_id IS NOT NULL "
        f"AND {field}actor_reference IS NULL) OR "
        f"({field}actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
        f"AND {field}actor_id IS NULL AND {field}actor_reference IS NOT NULL)"
    )


def upgrade() -> None:
    op.drop_constraint('ck_cash_sessions_lifecycle', 'cash_sessions', type_='check')
    op.add_column('cash_sessions', sa.Column(
        'selected_cash_count_id', sa.BigInteger(), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'final_movement_version', sa.BigInteger(), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'frozen_expected_cash', sa.Numeric(19, 4), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'frozen_variance', sa.Numeric(19, 4), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column('closed_at', sa.DateTime(), nullable=True))
    op.add_column('cash_sessions', sa.Column(
        'closed_by_actor_type', sa.String(24), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'closed_by_actor_id', sa.BigInteger(), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'closed_by_actor_reference',
        sa.String(200, collation='utf8mb4_bin'), nullable=True,
    ))
    op.add_column('cash_sessions', sa.Column(
        'variance_reason', sa.String(500), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'close_actor_scope', sa.String(200, collation='ascii_bin'), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'close_idempotency_key',
        sa.String(128, collation='ascii_bin'), nullable=True,
    ))
    op.add_column('cash_sessions', sa.Column(
        'close_request_schema_version', sa.Integer(), nullable=True
    ))
    op.add_column('cash_sessions', sa.Column(
        'close_request_fingerprint',
        sa.String(64, collation='ascii_bin'), nullable=True,
    ))
    op.create_unique_constraint(
        'uq_cash_sessions_command_scope', 'cash_sessions',
        ['id', 'tenant_id', 'organization_id', 'location_id'],
    )
    op.create_unique_constraint(
        'uq_cash_sessions_close_idempotency', 'cash_sessions',
        ['tenant_id', 'close_actor_scope', 'close_idempotency_key'],
    )

    op.create_table(
        'cash_movements',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('cash_session_id', sa.BigInteger(), nullable=False),
        sa.Column('movement_type', sa.String(24), nullable=False),
        sa.Column('amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('actor_type', sa.String(24), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('authorized_by_actor_type', sa.String(24), nullable=False),
        sa.Column('authorized_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('authorized_by_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('opening_float_slot', sa.SmallInteger(), nullable=True),
        sa.Column('idempotency_actor_scope', sa.String(200, collation='ascii_bin'), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_schema_version', sa.Integer(), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'cash_session_id', name='uq_cash_movements_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_cash_movements_idempotency',
        ),
        sa.UniqueConstraint(
            'cash_session_id', 'opening_float_slot',
            name='uq_cash_movements_opening_float',
        ),
        sa.CheckConstraint(
            "movement_type IN ('OPENING_FLOAT','CUSTOMER_TENDER',"
            "'CUSTOMER_CHANGE','CASH_IN','CASH_OUT','WITHDRAWAL','ADJUSTMENT')",
            name='ck_cash_movements_type',
        ),
        sa.CheckConstraint('amount <> 0', name='ck_cash_movements_nonzero'),
        sa.CheckConstraint(
            "(movement_type IN ('OPENING_FLOAT','CUSTOMER_TENDER','CASH_IN') "
            "AND amount>0) OR "
            "(movement_type IN ('CUSTOMER_CHANGE','CASH_OUT','WITHDRAWAL') "
            "AND amount<0) OR (movement_type='ADJUSTMENT' AND amount<>0)",
            name='ck_cash_movements_sign',
        ),
        sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_cash_movements_currency'),
        sa.CheckConstraint(
            "(movement_type='OPENING_FLOAT' AND opening_float_slot=1) OR "
            "(movement_type<>'OPENING_FLOAT' AND opening_float_slot IS NULL)",
            name='ck_cash_movements_opening_float_slot',
        ),
        sa.CheckConstraint(
            "movement_type='OPENING_FLOAT' OR "
            "(reason IS NOT NULL AND TRIM(reason)<>'')",
            name='ck_cash_movements_reason',
        ),
        sa.CheckConstraint('request_schema_version >= 1', name='ck_cash_movements_version'),
        sa.CheckConstraint(_actor_check(''), name='ck_cash_movements_actor'),
        sa.CheckConstraint(
            "(authorized_by_actor_type='EMPLOYEE' "
            "AND authorized_by_actor_id IS NOT NULL "
            "AND authorized_by_actor_reference IS NULL) OR "
            "(authorized_by_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND authorized_by_actor_id IS NULL "
            "AND authorized_by_actor_reference IS NOT NULL)",
            name='ck_cash_movements_authorizer',
        ),
        sa.ForeignKeyConstraint(
            ['cash_session_id', 'tenant_id', 'organization_id', 'location_id'],
            ['cash_sessions.id', 'cash_sessions.tenant_id',
             'cash_sessions.organization_id', 'cash_sessions.location_id'],
            name='fk_cash_movements_session_scope', ondelete='RESTRICT',
        ),
        mysql_engine='InnoDB', mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_cash_movements_session_history', 'cash_movements',
        ['tenant_id', 'cash_session_id', 'recorded_at', 'id'], unique=False,
    )

    op.create_table(
        'cash_counts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('cash_session_id', sa.BigInteger(), nullable=False),
        sa.Column('counted_amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column('captured_movement_version', sa.BigInteger(), nullable=False),
        sa.Column('counted_at', sa.DateTime(), nullable=False),
        sa.Column('actor_type', sa.String(24), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('idempotency_actor_scope', sa.String(200, collation='ascii_bin'), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_schema_version', sa.Integer(), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'cash_session_id', name='uq_cash_counts_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_cash_counts_idempotency',
        ),
        sa.CheckConstraint('counted_amount >= 0', name='ck_cash_counts_amount'),
        sa.CheckConstraint(
            'captured_movement_version >= 0 AND request_schema_version >= 1',
            name='ck_cash_counts_versions',
        ),
        sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_cash_counts_currency'),
        sa.CheckConstraint(_actor_check(''), name='ck_cash_counts_actor'),
        sa.ForeignKeyConstraint(
            ['cash_session_id', 'tenant_id', 'organization_id', 'location_id'],
            ['cash_sessions.id', 'cash_sessions.tenant_id',
             'cash_sessions.organization_id', 'cash_sessions.location_id'],
            name='fk_cash_counts_session_scope', ondelete='RESTRICT',
        ),
        mysql_engine='InnoDB', mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_cash_counts_session_history', 'cash_counts',
        ['tenant_id', 'cash_session_id', 'counted_at', 'id'], unique=False,
    )
    op.create_foreign_key(
        'fk_cash_sessions_selected_count_scope',
        'cash_sessions', 'cash_counts',
        [
            'selected_cash_count_id', 'tenant_id', 'organization_id',
            'location_id', 'id',
        ],
        [
            'id', 'tenant_id', 'organization_id', 'location_id',
            'cash_session_id',
        ],
        ondelete='RESTRICT',
    )
    op.create_check_constraint(
        'ck_cash_sessions_lifecycle', 'cash_sessions',
        "(status='OPEN' AND open_slot=1 AND selected_cash_count_id IS NULL "
        "AND final_movement_version IS NULL AND frozen_expected_cash IS NULL "
        "AND frozen_variance IS NULL AND closed_at IS NULL "
        "AND closed_by_actor_type IS NULL AND closed_by_actor_id IS NULL "
        "AND closed_by_actor_reference IS NULL AND variance_reason IS NULL "
        "AND close_actor_scope IS NULL AND close_idempotency_key IS NULL "
        "AND close_request_schema_version IS NULL "
        "AND close_request_fingerprint IS NULL) OR "
        "(status='CLOSED' AND open_slot IS NULL "
        "AND selected_cash_count_id IS NOT NULL "
        "AND final_movement_version IS NOT NULL "
        "AND frozen_expected_cash IS NOT NULL AND frozen_variance IS NOT NULL "
        "AND closed_at IS NOT NULL AND closed_by_actor_type IS NOT NULL "
        "AND close_actor_scope IS NOT NULL AND close_idempotency_key IS NOT NULL "
        "AND close_request_schema_version IS NOT NULL "
        "AND close_request_fingerprint IS NOT NULL)",
    )
    op.create_check_constraint(
        'ck_cash_sessions_close_actor', 'cash_sessions',
        "(status='OPEN' AND closed_by_actor_type IS NULL) OR "
        "(status='CLOSED' AND ((closed_by_actor_type='EMPLOYEE' "
        "AND closed_by_actor_id IS NOT NULL AND closed_by_actor_reference IS NULL) "
        "OR (closed_by_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
        "AND closed_by_actor_id IS NULL "
        "AND closed_by_actor_reference IS NOT NULL)))",
    )
    op.create_check_constraint(
        'ck_cash_sessions_variance_reason', 'cash_sessions',
        "(status='OPEN') OR (frozen_variance=0) OR "
        "(variance_reason IS NOT NULL AND TRIM(variance_reason)<>'')",
    )
    op.create_check_constraint(
        'ck_cash_sessions_final_version', 'cash_sessions',
        'final_movement_version IS NULL OR final_movement_version >= 0',
    )
    _seed_permission()


def downgrade() -> None:
    op.drop_constraint(
        'fk_cash_sessions_selected_count_scope', 'cash_sessions',
        type_='foreignkey',
    )
    op.drop_constraint('ck_cash_sessions_final_version', 'cash_sessions', type_='check')
    op.drop_constraint('ck_cash_sessions_variance_reason', 'cash_sessions', type_='check')
    op.drop_constraint('ck_cash_sessions_close_actor', 'cash_sessions', type_='check')
    op.drop_constraint('ck_cash_sessions_lifecycle', 'cash_sessions', type_='check')
    op.drop_table('cash_counts')
    op.drop_table('cash_movements')
    op.drop_constraint(
        'uq_cash_sessions_close_idempotency', 'cash_sessions', type_='unique'
    )
    op.drop_constraint(
        'uq_cash_sessions_command_scope', 'cash_sessions', type_='unique'
    )
    for column in (
        'close_request_fingerprint', 'close_request_schema_version',
        'close_idempotency_key', 'close_actor_scope', 'variance_reason',
        'closed_by_actor_reference', 'closed_by_actor_id',
        'closed_by_actor_type', 'closed_at', 'frozen_variance',
        'frozen_expected_cash', 'final_movement_version',
        'selected_cash_count_id',
    ):
        op.drop_column('cash_sessions', column)
    op.create_check_constraint(
        'ck_cash_sessions_lifecycle', 'cash_sessions',
        "(status='OPEN' AND open_slot=1) OR "
        "(status='CLOSED' AND open_slot IS NULL)",
    )
    # Preserve permission rows and grants because later provenance is unknowable.
