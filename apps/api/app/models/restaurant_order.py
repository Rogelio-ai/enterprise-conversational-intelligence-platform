from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class RestaurantOrder(TimestampMixin, Base):
    __tablename__ = 'restaurant_orders'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_orders_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(
            ['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
            ['restaurant_service_sessions.id', 'restaurant_service_sessions.tenant_id', 'restaurant_service_sessions.organization_id', 'restaurant_service_sessions.location_id', 'restaurant_service_sessions.resource_id'],
            name='fk_restaurant_orders_service_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'],
            ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id', 'diner_sessions.resource_id', 'diner_sessions.service_session_id', 'diner_sessions.conversation_id'],
            name='fk_restaurant_orders_diner_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
            ['conversations.id', 'conversations.tenant_id', 'conversations.organization_id', 'conversations.location_id', 'conversations.resource_id'],
            name='fk_restaurant_orders_conversation_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_order_draft_id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id'],
            ['order_drafts.id', 'order_drafts.tenant_id', 'order_drafts.organization_id', 'order_drafts.location_id', 'order_drafts.conversation_id'],
            name='fk_restaurant_orders_draft_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(['customer_id', 'tenant_id'], ['customers.id', 'customers.tenant_id'], name='fk_restaurant_orders_customer_tenant', ondelete='RESTRICT'),
        UniqueConstraint('source_order_draft_id', name='uq_restaurant_orders_source_draft'),
        UniqueConstraint('tenant_id', 'diner_session_id', 'confirmation_idempotency_key', name='uq_restaurant_orders_diner_idempotency'),
        UniqueConstraint('id', 'tenant_id', name='uq_restaurant_orders_id_tenant'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_restaurant_orders_pos_scope'),
        CheckConstraint("status = 'ACCEPTED'", name='ck_restaurant_orders_status'),
        CheckConstraint('accepted_draft_version >= 1', name='ck_restaurant_orders_draft_version'),
        CheckConstraint('fingerprint_schema_version >= 1', name='ck_restaurant_orders_fingerprint_version'),
        CheckConstraint("tax_mode = 'INCLUDED'", name='ck_restaurant_orders_tax_mode'),
        CheckConstraint("rounding_policy = 'WHOLE_UNIT_HALF_DOWN'", name='ck_restaurant_orders_rounding_policy'),
        CheckConstraint('subtotal >= 0 AND total_discount >= 0 AND pre_round_total >= 0 AND payable_total >= 0', name='ck_restaurant_orders_money_nonnegative'),
        CheckConstraint('pre_round_total = subtotal - total_discount', name='ck_restaurant_orders_pre_round_arithmetic'),
        CheckConstraint('payable_total = pre_round_total + rounding_adjustment', name='ck_restaurant_orders_payable_arithmetic'),
        Index('ix_restaurant_orders_diner_history', 'tenant_id', 'diner_session_id', 'accepted_at', 'id'),
        Index('ix_restaurant_orders_service_history', 'tenant_id', 'service_session_id', 'accepted_at', 'id'),
        Index('ix_restaurant_orders_conversation_history', 'tenant_id', 'conversation_id', 'accepted_at', 'id'),
        Index('ix_restaurant_orders_location_staff', 'tenant_id', 'location_id', 'accepted_at', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    diner_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_order_draft_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACCEPTED', server_default=text("'ACCEPTED'"))
    accepted_draft_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmation_idempotency_key: Mapped[str] = mapped_column(String(128, collation='ascii_bin'), nullable=False)
    commercial_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    fingerprint_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    tax_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    rounding_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    total_discount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    pre_round_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    rounding_adjustment: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    payable_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class RestaurantOrderItem(TimestampMixin, Base):
    __tablename__ = 'restaurant_order_items'
    __table_args__ = (
        ForeignKeyConstraint(['order_id', 'tenant_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id'], name='fk_restaurant_order_items_order_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_restaurant_order_items_product_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_order_draft_item_id'], ['order_draft_items.id'], name='fk_restaurant_order_items_source_draft_item', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_product_price_id'], ['product_prices.id'], name='fk_restaurant_order_items_source_price', ondelete='RESTRICT'),
        ForeignKeyConstraint(['composition_id'], ['product_compositions.id'], name='fk_restaurant_order_items_source_composition', ondelete='RESTRICT'),
        UniqueConstraint('order_id', 'source_order_draft_item_id', name='uq_restaurant_order_items_source'),
        UniqueConstraint('order_id', 'position', name='uq_restaurant_order_items_position'),
        UniqueConstraint('id', 'tenant_id', 'order_id', name='uq_restaurant_order_items_scope'),
        CheckConstraint('quantity > 0', name='ck_restaurant_order_items_quantity'),
        CheckConstraint('position >= 0', name='ck_restaurant_order_items_position'),
        CheckConstraint('unit_price >= 0 AND base_amount >= 0 AND discount_amount >= 0 AND commercial_amount >= 0', name='ck_restaurant_order_items_money'),
        CheckConstraint('commercial_amount = base_amount - discount_amount', name='ck_restaurant_order_items_arithmetic'),
        Index('ix_restaurant_order_items_ordered', 'tenant_id', 'order_id', 'position', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_order_draft_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    composition_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_product_price_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_source: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    commercial_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)


class RestaurantOrderItemComponent(TimestampMixin, Base):
    __tablename__ = 'restaurant_order_item_components'
    __table_args__ = (
        ForeignKeyConstraint(['order_item_id', 'tenant_id', 'order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_restaurant_order_components_item_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_restaurant_order_components_product_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_component_id'], ['product_components.id'], name='fk_restaurant_order_components_source_component', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_choice_group_id'], ['product_choice_groups.id'], name='fk_restaurant_order_components_source_group', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_choice_option_id'], ['product_choice_options.id'], name='fk_restaurant_order_components_source_option', ondelete='RESTRICT'),
        UniqueConstraint('order_item_id', 'position', name='uq_restaurant_order_components_position'),
        UniqueConstraint(
            'id', 'tenant_id', 'order_id', 'order_item_id',
            name='uq_restaurant_order_components_scope',
        ),
        CheckConstraint("kind IN ('FIXED', 'CHOICE')", name='ck_restaurant_order_components_kind'),
        CheckConstraint('position >= 0 AND quantity > 0', name='ck_restaurant_order_components_values'),
        CheckConstraint("(kind = 'FIXED' AND source_component_id IS NOT NULL AND source_choice_group_id IS NULL AND source_choice_option_id IS NULL AND choice_group_name IS NULL) OR (kind = 'CHOICE' AND source_component_id IS NULL AND source_choice_group_id IS NOT NULL AND source_choice_option_id IS NOT NULL AND choice_group_name IS NOT NULL)", name='ck_restaurant_order_components_source'),
        Index('ix_restaurant_order_components_ordered', 'tenant_id', 'order_id', 'order_item_id', 'position', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_component_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_choice_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_choice_option_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    choice_group_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)


class RestaurantOrderPromotion(TimestampMixin, Base):
    __tablename__ = 'restaurant_order_promotions'
    __table_args__ = (
        ForeignKeyConstraint(['order_item_id', 'tenant_id', 'order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_restaurant_order_promotions_item_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['promotion_id', 'tenant_id', 'organization_id'], ['promotions.id', 'promotions.tenant_id', 'promotions.organization_id'], name='fk_restaurant_order_promotions_source_scope', ondelete='RESTRICT'),
        UniqueConstraint('order_item_id', 'application_order', name='uq_restaurant_order_promotions_order'),
        CheckConstraint('application_order >= 0 AND priority >= 0', name='ck_restaurant_order_promotions_ordering'),
        CheckConstraint('promotion_value > 0 AND calculated_discount >= 0', name='ck_restaurant_order_promotions_money'),
        Index('ix_restaurant_order_promotions_ordered', 'tenant_id', 'order_id', 'order_item_id', 'application_order', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promotion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    application_order: Mapped[int] = mapped_column(Integer, nullable=False)
    promotion_name: Mapped[str] = mapped_column(String(200), nullable=False)
    promotion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    promotion_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    promotion_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_combinable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    calculated_discount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
