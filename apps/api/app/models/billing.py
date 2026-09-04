from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class IssuerFiscalProfile(TimestampMixin, Base):
    __tablename__ = 'issuer_fiscal_profiles'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_issuer_fiscal_profiles_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_issuer_fiscal_profiles_organization_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id',
            name='uq_issuer_fiscal_profiles_scope',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_issuer_fiscal_profiles_status',
        ),
        Index(
            'ix_issuer_fiscal_profiles_organization_status',
            'tenant_id', 'organization_id', 'status', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_identifier: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    tax_regime: Mapped[str] = mapped_column(String(100), nullable=False)
    fiscal_postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )


class CustomerFiscalProfile(TimestampMixin, Base):
    __tablename__ = 'customer_fiscal_profiles'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_customer_fiscal_profiles_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['customer_id', 'tenant_id'],
            ['customers.id', 'customers.tenant_id'],
            name='fk_customer_fiscal_profiles_customer_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'customer_id',
            name='uq_customer_fiscal_profiles_scope',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_customer_fiscal_profiles_status',
        ),
        Index(
            'ix_customer_fiscal_profiles_customer_status',
            'tenant_id', 'customer_id', 'status', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_identifier: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    tax_regime: Mapped[str] = mapped_column(String(100), nullable=False)
    fiscal_postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_usage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )


class BillingDocument(TimestampMixin, Base):
    __tablename__ = 'billing_documents'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_billing_documents_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_billing_documents_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_billing_documents_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_checks.id',
                'restaurant_checks.tenant_id',
                'restaurant_checks.organization_id',
                'restaurant_checks.location_id',
            ],
            name='fk_billing_documents_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_check_id', 'source_check_version'],
            ['restaurant_check_versions.check_id', 'restaurant_check_versions.version'],
            name='fk_billing_documents_check_version', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_billing_documents_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'actor_scope', 'idempotency_key',
            name='uq_billing_documents_idempotency',
        ),
        CheckConstraint(
            "document_type IN ('INVOICE')",
            name='ck_billing_documents_type',
        ),
        CheckConstraint(
            "status IN ('DRAFT')",
            name='ck_billing_documents_status',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_billing_documents_currency',
        ),
        CheckConstraint(
            'source_check_version >= 1',
            name='ck_billing_documents_check_version_value',
        ),
        CheckConstraint(
            'subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0',
            name='ck_billing_documents_money',
        ),
        Index(
            'ix_billing_documents_check_history',
            'tenant_id', 'restaurant_check_id', 'created_at', 'id',
        ),
        Index(
            'ix_billing_documents_organization_status',
            'tenant_id', 'organization_id', 'status', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_check_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_check_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default='INVOICE', server_default=text("'INVOICE'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='DRAFT', server_default=text("'DRAFT'")
    )
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    issuer_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    recipient_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )


class BillingDocumentLine(Base):
    __tablename__ = 'billing_document_lines'
    __table_args__ = (
        ForeignKeyConstraint(
            ['billing_document_id'], ['billing_documents.id'],
            name='fk_billing_document_lines_document', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_restaurant_order_id'], ['restaurant_orders.id'],
            name='fk_billing_document_lines_source_order', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_restaurant_order_item_id'], ['restaurant_order_items.id'],
            name='fk_billing_document_lines_source_order_item', ondelete='RESTRICT',
        ),
        CheckConstraint(
            'quantity > 0',
            name='ck_billing_document_lines_quantity',
        ),
        CheckConstraint(
            'unit_price >= 0 AND base_amount >= 0 AND discount_amount >= 0 '
            'AND commercial_total >= 0',
            name='ck_billing_document_lines_money',
        ),
        CheckConstraint(
            'commercial_total = base_amount - discount_amount',
            name='ck_billing_document_lines_arithmetic',
        ),
        Index(
            'ix_billing_document_lines_document',
            'billing_document_id', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    billing_document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_restaurant_order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    commercial_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class BillingDocumentLineTax(Base):
    __tablename__ = 'billing_document_line_taxes'
    __table_args__ = (
        ForeignKeyConstraint(
            ['billing_document_line_id'], ['billing_document_lines.id'],
            name='fk_billing_document_line_taxes_line', ondelete='RESTRICT',
        ),
        CheckConstraint(
            'tax_rate >= 0 AND taxable_base >= 0 AND tax_amount >= 0',
            name='ck_billing_document_line_taxes_values',
        ),
        Index(
            'ix_billing_document_line_taxes_line',
            'billing_document_line_id', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    billing_document_line_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_category: Mapped[str] = mapped_column(String(64), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    taxable_base: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    tax_treatment: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
