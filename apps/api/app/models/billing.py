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
        CheckConstraint(
            '(issuer_fiscal_postal_code IS NULL AND readiness_evidence_fingerprint IS NULL) '
            'OR (issuer_fiscal_postal_code IS NOT NULL '
            'AND readiness_evidence_fingerprint IS NOT NULL)',
            name='ck_billing_documents_fiscal_readiness',
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
    issuer_fiscal_postal_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    readiness_evidence_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
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
        CheckConstraint(
            '(fiscal_product_classification_scheme IS NULL '
            'AND fiscal_product_classification_code IS NULL '
            'AND fiscal_unit_classification_scheme IS NULL '
            'AND fiscal_unit_classification_code IS NULL '
            'AND fiscal_unit_value IS NULL AND fiscal_line_amount IS NULL '
            'AND fiscal_discount_amount IS NULL '
            'AND source_fiscal_evidence_fingerprint IS NULL) OR '
            '(fiscal_product_classification_scheme IS NOT NULL '
            'AND fiscal_product_classification_code IS NOT NULL '
            'AND fiscal_unit_classification_scheme IS NOT NULL '
            'AND fiscal_unit_classification_code IS NOT NULL '
            'AND fiscal_unit_value IS NOT NULL AND fiscal_line_amount IS NOT NULL '
            'AND fiscal_discount_amount IS NOT NULL '
            'AND source_fiscal_evidence_fingerprint IS NOT NULL '
            'AND fiscal_unit_value >= 0 AND fiscal_line_amount >= 0 '
            'AND fiscal_discount_amount >= 0)',
            name='ck_billing_document_lines_fiscal_evidence',
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
    fiscal_product_classification_scheme: Mapped[str | None] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=True
    )
    fiscal_product_classification_code: Mapped[str | None] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=True
    )
    fiscal_unit_classification_scheme: Mapped[str | None] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=True
    )
    fiscal_unit_classification_code: Mapped[str | None] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=True
    )
    fiscal_unit_value: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    fiscal_line_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    fiscal_discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    source_fiscal_evidence_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
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
        CheckConstraint(
            '(jurisdiction_code IS NULL AND tax_effect IS NULL '
            'AND source_tax_evidence_fingerprint IS NULL) OR '
            '(jurisdiction_code IS NOT NULL AND tax_effect IS NOT NULL '
            'AND source_tax_evidence_fingerprint IS NOT NULL '
            "AND tax_effect IN ('TRANSFERRED','WITHHELD'))",
            name='ck_billing_document_line_taxes_fiscal_evidence',
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
    jurisdiction_code: Mapped[str | None] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=True
    )
    tax_effect: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_tax_evidence_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class BillingIssuance(TimestampMixin, Base):
    __tablename__ = 'billing_issuances'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_billing_issuances_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_billing_issuances_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_billing_issuances_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['billing_document_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_documents.id',
                'billing_documents.tenant_id',
                'billing_documents.organization_id',
                'billing_documents.location_id',
            ],
            name='fk_billing_issuances_document_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_billing_issuances_scope',
        ),
        UniqueConstraint(
            'billing_document_id', name='uq_billing_issuances_document',
        ),
        UniqueConstraint(
            'tenant_id', 'actor_scope', 'idempotency_key',
            name='uq_billing_issuances_idempotency',
        ),
        UniqueConstraint(
            'tenant_id', 'provider_key', 'provider_idempotency_key',
            name='uq_billing_issuances_provider_operation',
        ),
        CheckConstraint(
            "state IN ('PENDING','IN_PROGRESS','SUCCEEDED','FAILED','REJECTED','UNCERTAIN')",
            name='ck_billing_issuances_state',
        ),
        CheckConstraint(
            'request_schema_version >= 1 AND attempt_count >= 0',
            name='ck_billing_issuances_versions',
        ),
        CheckConstraint(
            "(state='IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR "
            "(state<>'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)",
            name='ck_billing_issuances_claim',
        ),
        CheckConstraint(
            "(state IN ('SUCCEEDED','REJECTED') AND completed_at IS NOT NULL) OR "
            "(state NOT IN ('SUCCEEDED','REJECTED') AND completed_at IS NULL)",
            name='ck_billing_issuances_lifecycle',
        ),
        CheckConstraint(
            "state<>'SUCCEEDED' OR external_reference IS NOT NULL",
            name='ck_billing_issuances_success',
        ),
        Index(
            'ix_billing_issuances_state',
            'tenant_id', 'state', 'requested_at', 'id',
        ),
        Index(
            'ix_billing_issuances_claim',
            'tenant_id', 'state', 'claim_expires_at', 'id',
        ),
        Index(
            'ix_billing_issuances_external',
            'tenant_id', 'provider_key', 'external_reference', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    billing_document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_key: Mapped[str] = mapped_column(
        String(128, collation='utf8mb4_bin'), nullable=False
    )
    credential_binding: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default='PENDING', server_default=text("'PENDING'")
    )
    actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text('1')
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    provider_idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    external_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    external_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(
        String(36, collation='ascii_bin'), nullable=True
    )
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    last_error_kind: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class BillingIssuanceAttempt(Base):
    __tablename__ = 'billing_issuance_attempts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['billing_issuance_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_issuances.id',
                'billing_issuances.tenant_id',
                'billing_issuances.organization_id',
                'billing_issuances.location_id',
            ],
            name='fk_billing_issuance_attempts_issuance_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'billing_issuance_id', 'attempt_sequence',
            name='uq_billing_issuance_attempts_sequence',
        ),
        UniqueConstraint(
            'claim_token', name='uq_billing_issuance_attempts_claim',
        ),
        CheckConstraint(
            "attempt_type IN ('ISSUE','RETRY','RECOVER')",
            name='ck_billing_issuance_attempts_type',
        ),
        CheckConstraint(
            "result IS NULL OR result IN ('SUCCEEDED','FAILED','REJECTED','UNCERTAIN')",
            name='ck_billing_issuance_attempts_result',
        ),
        CheckConstraint(
            'attempt_sequence >= 1', name='ck_billing_issuance_attempts_sequence',
        ),
        CheckConstraint(
            '(result IS NULL AND completed_at IS NULL) OR '
            '(result IS NOT NULL AND completed_at IS NOT NULL)',
            name='ck_billing_issuance_attempts_lifecycle',
        ),
        CheckConstraint(
            "actor_type IS NULL OR actor_type IN "
            "('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')",
            name='ck_billing_issuance_attempts_actor',
        ),
        Index(
            'ix_billing_issuance_attempts_ordered',
            'tenant_id', 'billing_issuance_id', 'attempt_sequence', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    billing_issuance_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_type: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(
        String(36, collation='ascii_bin'), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    external_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_kind: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    actor_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
