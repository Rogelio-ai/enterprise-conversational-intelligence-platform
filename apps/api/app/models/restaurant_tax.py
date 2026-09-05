from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


_ACTIVE_DEFAULT = text("'ACTIVE'")
_TRANSFERRED_DEFAULT = text("'TRANSFERRED'")


class RestaurantTaxRule(TimestampMixin, Base):
    __tablename__ = 'restaurant_tax_rules'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_restaurant_tax_rules_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_restaurant_tax_rules_organization_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_restaurant_tax_rules_location_scope',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            name='uq_restaurant_tax_rules_scope',
        ),
        CheckConstraint('tax_rate >= 0', name='ck_restaurant_tax_rules_rate'),
        CheckConstraint(
            'effective_to IS NULL OR effective_from < effective_to',
            name='ck_restaurant_tax_rules_effective_interval',
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name='ck_restaurant_tax_rules_status',
        ),
        CheckConstraint(
            "tax_effect IN ('TRANSFERRED', 'WITHHELD')",
            name='ck_restaurant_tax_rules_effect',
        ),
        Index(
            'ix_restaurant_tax_rules_resolution',
            'tenant_id',
            'organization_id',
            'location_id',
            'tax_classification_code',
            'status',
            'effective_from',
            'effective_to',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tax_classification_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    jurisdiction_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    tax_category: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_treatment: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_effect: Mapped[str] = mapped_column(
        String(16), nullable=False, default='TRANSFERRED',
        server_default=_TRANSFERRED_DEFAULT,
    )
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    calculation_policy: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    rounding_policy: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class RestaurantOrderItemTaxSnapshot(Base):
    __tablename__ = 'restaurant_order_item_tax_snapshots'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_order_item_tax_snapshots_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_order_item_tax_snapshots_organization_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_order_item_tax_snapshots_location_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_orders.id',
                'restaurant_orders.tenant_id',
                'restaurant_orders.organization_id',
                'restaurant_orders.location_id',
            ],
            name='fk_order_item_tax_snapshots_order_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
            [
                'restaurant_order_items.id',
                'restaurant_order_items.tenant_id',
                'restaurant_order_items.order_id',
            ],
            name='fk_order_item_tax_snapshots_item_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_tax_rule_id', 'tenant_id', 'organization_id'],
            [
                'restaurant_tax_rules.id',
                'restaurant_tax_rules.tenant_id',
                'restaurant_tax_rules.organization_id',
            ],
            name='fk_order_item_tax_snapshots_rule_scope',
            ondelete='RESTRICT',
        ),
        CheckConstraint(
            'tax_rate >= 0 AND taxable_base >= 0 AND tax_amount >= 0',
            name='ck_order_item_tax_snapshots_values',
        ),
        CheckConstraint(
            'schema_version >= 1', name='ck_order_item_tax_snapshots_schema_version'
        ),
        CheckConstraint(
            "tax_effect IS NULL OR tax_effect IN ('TRANSFERRED', 'WITHHELD')",
            name='ck_order_item_tax_snapshots_effect',
        ),
        CheckConstraint(
            '(fiscal_unit_value IS NULL AND fiscal_line_amount IS NULL '
            'AND fiscal_discount_amount IS NULL AND tax_effect IS NULL) OR '
            '(fiscal_unit_value IS NOT NULL AND fiscal_line_amount IS NOT NULL '
            'AND fiscal_discount_amount IS NOT NULL AND tax_effect IS NOT NULL '
            'AND fiscal_unit_value >= 0 AND fiscal_line_amount >= 0 '
            'AND fiscal_discount_amount >= 0 '
            'AND fiscal_line_amount - fiscal_discount_amount = taxable_base)',
            name='ck_order_item_tax_snapshots_fiscal_money',
        ),
        Index(
            'ix_order_item_tax_snapshots_item',
            'tenant_id',
            'restaurant_order_id',
            'restaurant_order_item_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_tax_rule_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_category: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_treatment: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_effect: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    fiscal_unit_value: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    fiscal_line_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    fiscal_discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    taxable_base: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    jurisdiction_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    calculation_policy: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    rounding_policy: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
