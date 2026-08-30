from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, Numeric, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


OPTIONS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


class LocationPreparationConfiguration(TimestampMixin, Base):
    __tablename__ = 'location_preparation_configurations'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_location_preparation_configurations_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_location_preparation_configurations_location_scope', ondelete='RESTRICT'),
        UniqueConstraint('location_id', name='uq_location_preparation_configurations_location'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_location_preparation_configurations_scope'),
        CheckConstraint("preparation_owner IN ('PLATFORM','EXTERNAL_POS')", name='ck_location_preparation_configurations_owner'),
        Index('ix_location_preparation_configurations_lookup', 'tenant_id', 'location_id', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_owner: Mapped[str] = mapped_column(String(16), nullable=False)


class PreparationArea(TimestampMixin, Base):
    __tablename__ = 'preparation_areas'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_areas_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_preparation_areas_location_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['resource_id', 'tenant_id', 'location_id'], ['resources.id', 'resources.tenant_id', 'resources.location_id'], name='fk_preparation_areas_resource_scope', ondelete='RESTRICT'),
        UniqueConstraint('location_id', 'code', name='uq_preparation_areas_location_code'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_preparation_areas_scope'),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_preparation_areas_status'),
        Index('ix_preparation_areas_lookup', 'tenant_id', 'location_id', 'status', 'code', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    code: Mapped[str] = mapped_column(String(64, collation='utf8mb4_bin'), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))


class ProductPreparationRoute(TimestampMixin, Base):
    __tablename__ = 'product_preparation_routes'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_product_preparation_routes_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_product_preparation_routes_location_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_product_preparation_routes_product_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['preparation_area_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_areas.id', 'preparation_areas.tenant_id', 'preparation_areas.organization_id', 'preparation_areas.location_id'], name='fk_product_preparation_routes_area_scope', ondelete='RESTRICT'),
        UniqueConstraint('location_id', 'product_id', 'active_slot', name='uq_product_preparation_routes_current'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_product_preparation_routes_scope'),
        CheckConstraint("policy IN ('AREA','COMPONENTS','NO_PREPARATION')", name='ck_product_preparation_routes_policy'),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_product_preparation_routes_status'),
        CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_product_preparation_routes_active_slot'),
        CheckConstraint("(status = 'ACTIVE' AND active_slot = 1) OR (status = 'INACTIVE' AND active_slot IS NULL)", name='ck_product_preparation_routes_lifecycle'),
        CheckConstraint("(policy = 'AREA' AND preparation_area_id IS NOT NULL) OR (policy IN ('COMPONENTS','NO_PREPARATION') AND preparation_area_id IS NULL)", name='ck_product_preparation_routes_area'),
        Index('ix_product_preparation_routes_lookup', 'tenant_id', 'location_id', 'product_id', 'status', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy: Mapped[str] = mapped_column(String(24), nullable=False)
    preparation_area_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
    active_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))


class PreparationRouting(TimestampMixin, Base):
    __tablename__ = 'preparation_routings'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_routings_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'], name='fk_preparation_routings_order_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['initiating_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_preparation_routings_membership', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'restaurant_order_id', name='uq_preparation_routings_order'),
        UniqueConstraint('id', 'tenant_id', 'restaurant_order_id', name='uq_preparation_routings_scope'),
        CheckConstraint("preparation_owner IS NULL OR preparation_owner IN ('PLATFORM','EXTERNAL_POS')", name='ck_preparation_routings_owner'),
        CheckConstraint("state IN ('PENDING','ROUTED','EXTERNAL_POS_OWNED','ACTION_REQUIRED')", name='ck_preparation_routings_state'),
        CheckConstraint('routing_schema_version >= 1', name='ck_preparation_routings_version'),
        CheckConstraint("(initiating_actor_type = 'EMPLOYEE' AND initiating_membership_id IS NOT NULL AND initiating_principal_reference IS NULL) OR (initiating_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND initiating_membership_id IS NULL AND initiating_principal_reference IS NOT NULL)", name='ck_preparation_routings_actor'),
        CheckConstraint("(state IN ('ROUTED','EXTERNAL_POS_OWNED') AND preparation_owner IS NOT NULL AND routed_at IS NOT NULL AND routing_fingerprint IS NOT NULL AND error_code IS NULL) OR (state = 'PENDING' AND preparation_owner IS NOT NULL AND routed_at IS NULL AND error_code IS NULL) OR (state = 'ACTION_REQUIRED' AND routed_at IS NULL AND error_code IS NOT NULL)", name='ck_preparation_routings_lifecycle'),
        Index('ix_preparation_routings_state', 'tenant_id', 'state', 'location_id', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_owner: Mapped[str | None] = mapped_column(String(16), nullable=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    routing_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    routing_fingerprint: Mapped[str | None] = mapped_column(String(64, collation='ascii_bin'), nullable=True)
    initiating_actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    initiating_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    initiating_principal_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64, collation='ascii_bin'), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    routed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class PreparationWork(TimestampMixin, Base):
    __tablename__ = 'preparation_works'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_works_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['routing_id', 'tenant_id', 'restaurant_order_id'], ['preparation_routings.id', 'preparation_routings.tenant_id', 'preparation_routings.restaurant_order_id'], name='fk_preparation_works_routing_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['preparation_area_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_areas.id', 'preparation_areas.tenant_id', 'preparation_areas.organization_id', 'preparation_areas.location_id'], name='fk_preparation_works_area_scope', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'restaurant_order_id', 'preparation_area_id', name='uq_preparation_works_order_area'),
        UniqueConstraint('id', 'tenant_id', 'restaurant_order_id', name='uq_preparation_works_scope'),
        CheckConstraint("preparation_owner = 'PLATFORM'", name='ck_preparation_works_owner'),
        CheckConstraint('routing_schema_version >= 1', name='ck_preparation_works_version'),
        Index('ix_preparation_works_area', 'tenant_id', 'location_id', 'preparation_area_id', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    routing_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_area_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_owner: Mapped[str] = mapped_column(String(16), nullable=False)
    area_code_snapshot: Mapped[str] = mapped_column(String(64, collation='utf8mb4_bin'), nullable=False)
    area_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    routing_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    routing_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    routed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class PreparationWorkItem(Base):
    __tablename__ = 'preparation_work_items'
    __table_args__ = (
        ForeignKeyConstraint(['preparation_work_id', 'tenant_id', 'restaurant_order_id'], ['preparation_works.id', 'preparation_works.tenant_id', 'preparation_works.restaurant_order_id'], name='fk_preparation_work_items_work_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_preparation_work_items_source_item_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['source_restaurant_order_item_component_id', 'tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_id_for_component'], ['restaurant_order_item_components.id', 'restaurant_order_item_components.tenant_id', 'restaurant_order_item_components.order_id', 'restaurant_order_item_components.order_item_id'], name='fk_preparation_work_items_source_component_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['route_id', 'tenant_id', 'organization_id', 'location_id'], ['product_preparation_routes.id', 'product_preparation_routes.tenant_id', 'product_preparation_routes.organization_id', 'product_preparation_routes.location_id'], name='fk_preparation_work_items_route_scope', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_id', name='uq_preparation_work_items_source_item'),
        UniqueConstraint('tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_component_id', name='uq_preparation_work_items_source_component'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id', name='uq_preparation_work_items_execution_scope'),
        CheckConstraint('required_quantity > 0', name='ck_preparation_work_items_quantity'),
        CheckConstraint("route_policy = 'AREA'", name='ck_preparation_work_items_policy'),
        CheckConstraint('(source_restaurant_order_item_id IS NOT NULL AND source_restaurant_order_item_component_id IS NULL AND source_restaurant_order_item_id_for_component IS NULL) OR (source_restaurant_order_item_id IS NULL AND source_restaurant_order_item_component_id IS NOT NULL AND source_restaurant_order_item_id_for_component IS NOT NULL)', name='ck_preparation_work_items_source_xor'),
        CheckConstraint("execution_state IN ('NEW','IN_PROGRESS','COMPLETED')", name='ck_preparation_work_items_execution_state'),
        CheckConstraint('execution_version >= 0', name='ck_preparation_work_items_execution_version'),
        Index('ix_preparation_work_items_ordered', 'tenant_id', 'preparation_work_id', 'id'),
        Index('ix_preparation_work_items_queue', 'tenant_id', 'location_id', 'execution_state', 'preparation_work_id', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_work_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_restaurant_order_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_restaurant_order_item_component_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_restaurant_order_item_id_for_component: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    route_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_policy: Mapped[str] = mapped_column(String(24), nullable=False)
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    execution_state: Mapped[str] = mapped_column(String(16), nullable=False, default='NEW', server_default=text("'NEW'"))
    execution_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text('0'))
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class PreparationItemTransition(Base):
    __tablename__ = 'preparation_item_transitions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['preparation_work_item_id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id'],
            ['preparation_work_items.id', 'preparation_work_items.tenant_id', 'preparation_work_items.organization_id', 'preparation_work_items.location_id', 'preparation_work_items.restaurant_order_id', 'preparation_work_items.preparation_work_id'],
            name='fk_preparation_item_transitions_item_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_preparation_item_transitions_membership', ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'preparation_work_item_id', 'sequence', name='uq_preparation_item_transitions_sequence'),
        UniqueConstraint('tenant_id', 'preparation_work_item_id', 'idempotency_key', name='uq_preparation_item_transitions_idempotency'),
        CheckConstraint('sequence >= 1', name='ck_preparation_item_transitions_sequence'),
        CheckConstraint(
            "(from_state = 'NEW' AND to_state = 'IN_PROGRESS') OR "
            "(from_state = 'IN_PROGRESS' AND to_state = 'COMPLETED')",
            name='ck_preparation_item_transitions_edge',
        ),
        CheckConstraint(
            "(actor_type = 'EMPLOYEE' AND actor_membership_id IS NOT NULL AND actor_principal_reference IS NULL) OR "
            "(actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_membership_id IS NULL AND actor_principal_reference IS NOT NULL)",
            name='ck_preparation_item_transitions_actor',
        ),
        Index('ix_preparation_item_transitions_ordered', 'tenant_id', 'preparation_work_item_id', 'sequence', 'id'),
        OPTIONS,
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_work_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preparation_work_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str] = mapped_column(String(16), nullable=False)
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_principal_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128, collation='ascii_bin'), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
