from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    DateTime,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class OrderDraft(TimestampMixin, Base):
    __tablename__ = 'order_drafts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_order_drafts_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_order_drafts_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_order_drafts_location_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
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
        UniqueConstraint(
            'tenant_id', 'conversation_id', 'current_slot',
            name='uq_order_drafts_tenant_conversation_current'
        ),
        UniqueConstraint(
            'tenant_id', 'conversation_id', 'abandon_idempotency_key',
            name='uq_order_drafts_abandon_idempotency',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_order_drafts_id_tenant_org'
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id',
            name='uq_order_drafts_full_scope',
        ),
        CheckConstraint('version >= 1', name='ck_order_drafts_version'),
        CheckConstraint("status IN ('OPEN', 'ACCEPTED', 'ABANDONED')", name='ck_order_drafts_status'),
        CheckConstraint('current_slot IS NULL OR current_slot = 1', name='ck_order_drafts_current_slot'),
        CheckConstraint(
            "(status = 'OPEN' AND current_slot = 1 AND terminal_at IS NULL) OR "
            "(status IN ('ACCEPTED', 'ABANDONED') AND current_slot IS NULL AND terminal_at IS NOT NULL)",
            name='ck_order_drafts_lifecycle',
        ),
        Index(
            'ix_order_drafts_tenant_org_location',
            'tenant_id',
            'organization_id',
            'location_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='OPEN', server_default=text("'OPEN'")
    )
    current_slot: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, default=1, server_default=text('1')
    )
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    abandoned_actor_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    abandoned_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    abandoned_actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    abandon_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    abandon_request_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )


class OrderDraftItem(TimestampMixin, Base):
    __tablename__ = 'order_draft_items'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_order_draft_items_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['draft_id', 'tenant_id', 'organization_id'],
            ['order_drafts.id', 'order_drafts.tenant_id', 'order_drafts.organization_id'],
            name='fk_order_draft_items_draft_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_order_draft_items_product_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
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
        UniqueConstraint('draft_id', 'position', name='uq_order_draft_items_draft_position'),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            'draft_id',
            'composition_id',
            name='uq_order_draft_items_selection_scope',
        ),
        CheckConstraint('quantity > 0', name='ck_order_draft_items_quantity'),
        CheckConstraint('position >= 0', name='ck_order_draft_items_position'),
        Index(
            'ix_order_draft_items_tenant_draft_order',
            'tenant_id',
            'draft_id',
            'position',
            'id',
        ),
        Index(
            'ix_order_draft_items_tenant_org_product',
            'tenant_id',
            'organization_id',
            'product_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    draft_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    composition_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class OrderDraftItemSelection(TimestampMixin, Base):
    __tablename__ = 'order_draft_item_selections'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_order_draft_item_selections_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        UniqueConstraint(
            'draft_item_id',
            'choice_option_id',
            name='uq_order_draft_selections_item_option',
        ),
        Index(
            'ix_order_draft_selections_tenant_item_group',
            'tenant_id',
            'draft_item_id',
            'choice_group_id',
            'choice_option_id',
        ),
        Index(
            'ix_order_draft_selections_tenant_choice',
            'tenant_id',
            'organization_id',
            'choice_group_id',
            'choice_option_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    draft_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    draft_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    composition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    choice_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    choice_option_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
