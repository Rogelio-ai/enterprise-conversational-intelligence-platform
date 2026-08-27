from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
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
            'tenant_id', 'conversation_id', name='uq_order_drafts_tenant_conversation'
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_order_drafts_id_tenant_org'
        ),
        CheckConstraint('version >= 1', name='ck_order_drafts_version'),
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
