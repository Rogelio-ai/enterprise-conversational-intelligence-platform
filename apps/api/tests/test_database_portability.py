from __future__ import annotations

import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pymysql
import pytest

from app import models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base


APPLICATION_TABLES = {
    'tenants',
    'users',
    'permissions',
    'tenant_memberships',
    'roles',
    'role_permissions',
    'membership_roles',
    'organizations',
    'locations',
    'resources',
    'customers',
    'customer_external_identities',
    'product_categories',
    'products',
    'product_external_mappings',
    'menus',
    'menu_locations',
    'menu_sections',
    'menu_items',
    'product_prices',
    'promotions',
    'promotion_products',
    'promotion_locations',
    'conversations',
    'conversation_participants',
    'conversation_messages',
    'intelligence_derivations',
    'restaurant_message_intents',
    'product_compositions',
    'product_components',
    'product_choice_groups',
    'product_choice_options',
}

LEGACY_APPLICATION_TABLES = APPLICATION_TABLES - {
    'organizations',
    'locations',
    'resources',
    'customers',
    'customer_external_identities',
    'product_categories',
    'products',
    'product_external_mappings',
    'menus',
    'menu_locations',
    'menu_sections',
    'menu_items',
    'product_prices',
    'promotions',
    'promotion_products',
    'promotion_locations',
    'conversations',
    'conversation_participants',
    'conversation_messages',
    'intelligence_derivations',
    'restaurant_message_intents',
    'product_compositions',
    'product_components',
    'product_choice_groups',
    'product_choice_options',
}

EXPECTED_FOREIGN_KEY_COLUMNS = {
    ('fk_tenant_memberships_tenant', 'tenant_memberships', 'tenant_id', 'tenants', 'id', 1),
    ('fk_tenant_memberships_user', 'tenant_memberships', 'user_id', 'users', 'id', 1),
    ('fk_roles_tenant', 'roles', 'tenant_id', 'tenants', 'id', 1),
    ('fk_role_permissions_role', 'role_permissions', 'role_id', 'roles', 'id', 1),
    (
        'fk_role_permissions_permission',
        'role_permissions',
        'permission_id',
        'permissions',
        'id',
        1,
    ),
    (
        'fk_membership_roles_membership_tenant',
        'membership_roles',
        'membership_id',
        'tenant_memberships',
        'id',
        1,
    ),
    (
        'fk_membership_roles_membership_tenant',
        'membership_roles',
        'tenant_id',
        'tenant_memberships',
        'tenant_id',
        2,
    ),
    (
        'fk_membership_roles_role_tenant',
        'membership_roles',
        'role_id',
        'roles',
        'id',
        1,
    ),
    (
        'fk_membership_roles_role_tenant',
        'membership_roles',
        'tenant_id',
        'roles',
        'tenant_id',
        2,
    ),
    ('fk_organizations_tenant', 'organizations', 'tenant_id', 'tenants', 'id', 1),
    ('fk_locations_tenant', 'locations', 'tenant_id', 'tenants', 'id', 1),
    (
        'fk_locations_organization_tenant',
        'locations',
        'organization_id',
        'organizations',
        'id',
        1,
    ),
    (
        'fk_locations_organization_tenant',
        'locations',
        'tenant_id',
        'organizations',
        'tenant_id',
        2,
    ),
    ('fk_resources_tenant', 'resources', 'tenant_id', 'tenants', 'id', 1),
    (
        'fk_resources_location_tenant',
        'resources',
        'location_id',
        'locations',
        'id',
        1,
    ),
    (
        'fk_resources_location_tenant',
        'resources',
        'tenant_id',
        'locations',
        'tenant_id',
        2,
    ),
    ('fk_customers_tenant', 'customers', 'tenant_id', 'tenants', 'id', 1),
    (
        'fk_customer_external_identities_tenant',
        'customer_external_identities',
        'tenant_id',
        'tenants',
        'id',
        1,
    ),
    (
        'fk_customer_external_identities_customer_tenant',
        'customer_external_identities',
        'customer_id',
        'customers',
        'id',
        1,
    ),
    (
        'fk_customer_external_identities_customer_tenant',
        'customer_external_identities',
        'tenant_id',
        'customers',
        'tenant_id',
        2,
    ),
    ('fk_product_categories_tenant', 'product_categories', 'tenant_id', 'tenants', 'id', 1),
    ('fk_product_categories_organization_tenant', 'product_categories', 'organization_id', 'organizations', 'id', 1),
    ('fk_product_categories_organization_tenant', 'product_categories', 'tenant_id', 'organizations', 'tenant_id', 2),
    ('fk_products_tenant', 'products', 'tenant_id', 'tenants', 'id', 1),
    ('fk_products_organization_tenant', 'products', 'organization_id', 'organizations', 'id', 1),
    ('fk_products_organization_tenant', 'products', 'tenant_id', 'organizations', 'tenant_id', 2),
    ('fk_products_category_tenant_org', 'products', 'category_id', 'product_categories', 'id', 1),
    ('fk_products_category_tenant_org', 'products', 'tenant_id', 'product_categories', 'tenant_id', 2),
    ('fk_products_category_tenant_org', 'products', 'organization_id', 'product_categories', 'organization_id', 3),
    ('fk_product_external_mappings_tenant', 'product_external_mappings', 'tenant_id', 'tenants', 'id', 1),
    ('fk_product_external_mappings_product_tenant', 'product_external_mappings', 'product_id', 'products', 'id', 1),
    ('fk_product_external_mappings_product_tenant', 'product_external_mappings', 'tenant_id', 'products', 'tenant_id', 2),
    ('fk_menus_tenant', 'menus', 'tenant_id', 'tenants', 'id', 1),
    ('fk_menus_organization_tenant', 'menus', 'organization_id', 'organizations', 'id', 1),
    ('fk_menus_organization_tenant', 'menus', 'tenant_id', 'organizations', 'tenant_id', 2),
    ('fk_menu_locations_tenant', 'menu_locations', 'tenant_id', 'tenants', 'id', 1),
    ('fk_menu_locations_menu_tenant_org', 'menu_locations', 'menu_id', 'menus', 'id', 1),
    ('fk_menu_locations_menu_tenant_org', 'menu_locations', 'tenant_id', 'menus', 'tenant_id', 2),
    ('fk_menu_locations_menu_tenant_org', 'menu_locations', 'organization_id', 'menus', 'organization_id', 3),
    ('fk_menu_locations_location_tenant_org', 'menu_locations', 'location_id', 'locations', 'id', 1),
    ('fk_menu_locations_location_tenant_org', 'menu_locations', 'tenant_id', 'locations', 'tenant_id', 2),
    ('fk_menu_locations_location_tenant_org', 'menu_locations', 'organization_id', 'locations', 'organization_id', 3),
    ('fk_menu_sections_tenant', 'menu_sections', 'tenant_id', 'tenants', 'id', 1),
    ('fk_menu_sections_menu_tenant_org', 'menu_sections', 'menu_id', 'menus', 'id', 1),
    ('fk_menu_sections_menu_tenant_org', 'menu_sections', 'tenant_id', 'menus', 'tenant_id', 2),
    ('fk_menu_sections_menu_tenant_org', 'menu_sections', 'organization_id', 'menus', 'organization_id', 3),
    ('fk_menu_items_tenant', 'menu_items', 'tenant_id', 'tenants', 'id', 1),
    ('fk_menu_items_menu_tenant_org', 'menu_items', 'menu_id', 'menus', 'id', 1),
    ('fk_menu_items_menu_tenant_org', 'menu_items', 'tenant_id', 'menus', 'tenant_id', 2),
    ('fk_menu_items_menu_tenant_org', 'menu_items', 'organization_id', 'menus', 'organization_id', 3),
    ('fk_menu_items_section_menu_tenant_org', 'menu_items', 'section_id', 'menu_sections', 'id', 1),
    ('fk_menu_items_section_menu_tenant_org', 'menu_items', 'menu_id', 'menu_sections', 'menu_id', 2),
    ('fk_menu_items_section_menu_tenant_org', 'menu_items', 'tenant_id', 'menu_sections', 'tenant_id', 3),
    ('fk_menu_items_section_menu_tenant_org', 'menu_items', 'organization_id', 'menu_sections', 'organization_id', 4),
    ('fk_menu_items_product_tenant_org', 'menu_items', 'product_id', 'products', 'id', 1),
    ('fk_menu_items_product_tenant_org', 'menu_items', 'tenant_id', 'products', 'tenant_id', 2),
    ('fk_menu_items_product_tenant_org', 'menu_items', 'organization_id', 'products', 'organization_id', 3),
}

EXPECTED_INDEX_COLUMNS = {
    ('organizations', 'uq_organizations_id_tenant', 'id', 1, 0),
    ('organizations', 'uq_organizations_id_tenant', 'tenant_id', 2, 0),
    ('organizations', 'uq_organizations_tenant_code', 'tenant_id', 1, 0),
    ('organizations', 'uq_organizations_tenant_code', 'code', 2, 0),
    ('organizations', 'ix_organizations_tenant_status', 'tenant_id', 1, 1),
    ('organizations', 'ix_organizations_tenant_status', 'status', 2, 1),
    ('organizations', 'ix_organizations_tenant_status', 'id', 3, 1),
    ('locations', 'uq_locations_id_tenant', 'id', 1, 0),
    ('locations', 'uq_locations_id_tenant', 'tenant_id', 2, 0),
    ('locations', 'uq_locations_organization_code', 'organization_id', 1, 0),
    ('locations', 'uq_locations_organization_code', 'code', 2, 0),
    ('locations', 'ix_locations_tenant_organization_status', 'tenant_id', 1, 1),
    ('locations', 'ix_locations_tenant_organization_status', 'organization_id', 2, 1),
    ('locations', 'ix_locations_tenant_organization_status', 'status', 3, 1),
    ('locations', 'ix_locations_tenant_organization_status', 'id', 4, 1),
    ('resources', 'uq_resources_id_tenant', 'id', 1, 0),
    ('resources', 'uq_resources_id_tenant', 'tenant_id', 2, 0),
    ('resources', 'uq_resources_location_code', 'location_id', 1, 0),
    ('resources', 'uq_resources_location_code', 'code', 2, 0),
    ('resources', 'ix_resources_tenant_location_type_status', 'tenant_id', 1, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'location_id', 2, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'resource_type', 3, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'status', 4, 1),
    ('resources', 'ix_resources_tenant_location_type_status', 'id', 5, 1),
    ('customers', 'uq_customers_id_tenant', 'id', 1, 0),
    ('customers', 'uq_customers_id_tenant', 'tenant_id', 2, 0),
    ('customers', 'ix_customers_tenant_status', 'tenant_id', 1, 1),
    ('customers', 'ix_customers_tenant_status', 'status', 2, 1),
    ('customers', 'ix_customers_tenant_status', 'id', 3, 1),
    ('customers', 'ix_customers_tenant_email', 'tenant_id', 1, 1),
    ('customers', 'ix_customers_tenant_email', 'email', 2, 1),
    ('customers', 'ix_customers_tenant_email', 'id', 3, 1),
    ('customers', 'ix_customers_tenant_phone', 'tenant_id', 1, 1),
    ('customers', 'ix_customers_tenant_phone', 'phone', 2, 1),
    ('customers', 'ix_customers_tenant_phone', 'id', 3, 1),
    (
        'customer_external_identities',
        'uq_customer_external_identity_source',
        'tenant_id',
        1,
        0,
    ),
    (
        'customer_external_identities',
        'uq_customer_external_identity_source',
        'connector_key',
        2,
        0,
    ),
    (
        'customer_external_identities',
        'uq_customer_external_identity_source',
        'external_customer_id',
        3,
        0,
    ),
    (
        'customer_external_identities',
        'ix_customer_external_identities_customer',
        'tenant_id',
        1,
        1,
    ),
    (
        'customer_external_identities',
        'ix_customer_external_identities_customer',
        'customer_id',
        2,
        1,
    ),
    (
        'customer_external_identities',
        'ix_customer_external_identities_customer',
        'id',
        3,
        1,
    ),
    ('locations', 'uq_locations_id_tenant_organization', 'id', 1, 0),
    ('locations', 'uq_locations_id_tenant_organization', 'tenant_id', 2, 0),
    ('locations', 'uq_locations_id_tenant_organization', 'organization_id', 3, 0),
    ('product_categories', 'uq_product_categories_id_tenant', 'id', 1, 0),
    ('product_categories', 'uq_product_categories_id_tenant', 'tenant_id', 2, 0),
    ('product_categories', 'uq_product_categories_id_tenant_org', 'id', 1, 0),
    ('product_categories', 'uq_product_categories_id_tenant_org', 'tenant_id', 2, 0),
    ('product_categories', 'uq_product_categories_id_tenant_org', 'organization_id', 3, 0),
    ('product_categories', 'uq_product_categories_tenant_org_name', 'tenant_id', 1, 0),
    ('product_categories', 'uq_product_categories_tenant_org_name', 'organization_id', 2, 0),
    ('product_categories', 'uq_product_categories_tenant_org_name', 'name', 3, 0),
    ('product_categories', 'ix_product_categories_tenant_org_status_name', 'tenant_id', 1, 1),
    ('product_categories', 'ix_product_categories_tenant_org_status_name', 'organization_id', 2, 1),
    ('product_categories', 'ix_product_categories_tenant_org_status_name', 'status', 3, 1),
    ('product_categories', 'ix_product_categories_tenant_org_status_name', 'name', 4, 1),
    ('product_categories', 'ix_product_categories_tenant_org_status_name', 'id', 5, 1),
    ('products', 'uq_products_id_tenant', 'id', 1, 0),
    ('products', 'uq_products_id_tenant', 'tenant_id', 2, 0),
    ('products', 'uq_products_id_tenant_org', 'id', 1, 0),
    ('products', 'uq_products_id_tenant_org', 'tenant_id', 2, 0),
    ('products', 'uq_products_id_tenant_org', 'organization_id', 3, 0),
    ('products', 'ix_products_tenant_org_status_name', 'tenant_id', 1, 1),
    ('products', 'ix_products_tenant_org_status_name', 'organization_id', 2, 1),
    ('products', 'ix_products_tenant_org_status_name', 'status', 3, 1),
    ('products', 'ix_products_tenant_org_status_name', 'name', 4, 1),
    ('products', 'ix_products_tenant_org_status_name', 'id', 5, 1),
    ('products', 'ix_products_tenant_org_category', 'tenant_id', 1, 1),
    ('products', 'ix_products_tenant_org_category', 'organization_id', 2, 1),
    ('products', 'ix_products_tenant_org_category', 'category_id', 3, 1),
    ('products', 'ix_products_tenant_org_category', 'id', 4, 1),
    ('product_external_mappings', 'uq_product_external_mapping_source', 'tenant_id', 1, 0),
    ('product_external_mappings', 'uq_product_external_mapping_source', 'connector_key', 2, 0),
    ('product_external_mappings', 'uq_product_external_mapping_source', 'external_product_id', 3, 0),
    ('product_external_mappings', 'ix_product_external_mappings_product', 'tenant_id', 1, 1),
    ('product_external_mappings', 'ix_product_external_mappings_product', 'product_id', 2, 1),
    ('product_external_mappings', 'ix_product_external_mappings_product', 'id', 3, 1),
    ('menus', 'uq_menus_id_tenant', 'id', 1, 0),
    ('menus', 'uq_menus_id_tenant', 'tenant_id', 2, 0),
    ('menus', 'uq_menus_id_tenant_org', 'id', 1, 0),
    ('menus', 'uq_menus_id_tenant_org', 'tenant_id', 2, 0),
    ('menus', 'uq_menus_id_tenant_org', 'organization_id', 3, 0),
    ('menus', 'ix_menus_tenant_org_status_name', 'tenant_id', 1, 1),
    ('menus', 'ix_menus_tenant_org_status_name', 'organization_id', 2, 1),
    ('menus', 'ix_menus_tenant_org_status_name', 'status', 3, 1),
    ('menus', 'ix_menus_tenant_org_status_name', 'name', 4, 1),
    ('menus', 'ix_menus_tenant_org_status_name', 'id', 5, 1),
    ('menu_locations', 'uq_menu_locations_tenant_menu_location', 'tenant_id', 1, 0),
    ('menu_locations', 'uq_menu_locations_tenant_menu_location', 'menu_id', 2, 0),
    ('menu_locations', 'uq_menu_locations_tenant_menu_location', 'location_id', 3, 0),
    ('menu_locations', 'ix_menu_locations_tenant_location_status', 'tenant_id', 1, 1),
    ('menu_locations', 'ix_menu_locations_tenant_location_status', 'location_id', 2, 1),
    ('menu_locations', 'ix_menu_locations_tenant_location_status', 'status', 3, 1),
    ('menu_locations', 'ix_menu_locations_tenant_location_status', 'menu_id', 4, 1),
    ('menu_sections', 'uq_menu_sections_id_menu_tenant_org', 'id', 1, 0),
    ('menu_sections', 'uq_menu_sections_id_menu_tenant_org', 'menu_id', 2, 0),
    ('menu_sections', 'uq_menu_sections_id_menu_tenant_org', 'tenant_id', 3, 0),
    ('menu_sections', 'uq_menu_sections_id_menu_tenant_org', 'organization_id', 4, 0),
    ('menu_sections', 'ix_menu_sections_menu_status_order', 'tenant_id', 1, 1),
    ('menu_sections', 'ix_menu_sections_menu_status_order', 'menu_id', 2, 1),
    ('menu_sections', 'ix_menu_sections_menu_status_order', 'status', 3, 1),
    ('menu_sections', 'ix_menu_sections_menu_status_order', 'display_order', 4, 1),
    ('menu_sections', 'ix_menu_sections_menu_status_order', 'id', 5, 1),
    ('menu_items', 'uq_menu_items_tenant_menu_product', 'tenant_id', 1, 0),
    ('menu_items', 'uq_menu_items_tenant_menu_product', 'menu_id', 2, 0),
    ('menu_items', 'uq_menu_items_tenant_menu_product', 'product_id', 3, 0),
    ('menu_items', 'ix_menu_items_section_status_order', 'tenant_id', 1, 1),
    ('menu_items', 'ix_menu_items_section_status_order', 'menu_id', 2, 1),
    ('menu_items', 'ix_menu_items_section_status_order', 'section_id', 3, 1),
    ('menu_items', 'ix_menu_items_section_status_order', 'status', 4, 1),
    ('menu_items', 'ix_menu_items_section_status_order', 'display_order', 5, 1),
    ('menu_items', 'ix_menu_items_section_status_order', 'id', 6, 1),
    ('menu_items', 'ix_menu_items_tenant_product', 'tenant_id', 1, 1),
    ('menu_items', 'ix_menu_items_tenant_product', 'product_id', 2, 1),
    ('menu_items', 'ix_menu_items_tenant_product', 'menu_id', 3, 1),
    ('menu_items', 'ix_menu_items_tenant_product', 'id', 4, 1),
}

EXPECTED_DOMAIN_CHECKS = {
    ('resources', 'ck_resources_status'),
    ('resources', 'ck_resources_type'),
    ('customers', 'ck_customers_status'),
    ('customers', 'ck_customers_source'),
    ('product_categories', 'ck_product_categories_status'),
    ('products', 'ck_products_status'),
    ('products', 'ck_products_source'),
    ('menus', 'ck_menus_status'),
    ('menu_locations', 'ck_menu_locations_status'),
    ('menu_sections', 'ck_menu_sections_status'),
    ('menu_sections', 'ck_menu_sections_display_order'),
    ('menu_items', 'ck_menu_items_status'),
    ('menu_items', 'ck_menu_items_display_order'),
    ('product_prices', 'ck_product_prices_amount'),
    ('product_prices', 'ck_product_prices_currency'),
    ('product_prices', 'ck_product_prices_status'),
    ('product_prices', 'ck_product_prices_source'),
    ('promotions', 'ck_promotions_type'),
    ('promotions', 'ck_promotions_status'),
    ('promotions', 'ck_promotions_source'),
    ('promotions', 'ck_promotions_interval'),
    ('promotions', 'ck_promotions_currency'),
    ('promotions', 'ck_promotions_benefit'),
    ('promotions', 'ck_promotions_all_locations'),
    ('promotion_products', 'ck_promotion_products_status'),
    ('promotion_locations', 'ck_promotion_locations_status'),
    ('conversations', 'ck_conversations_channel'),
    ('conversations', 'ck_conversations_status'),
    ('conversations', 'ck_conversations_status_closed_at'),
    ('conversations', 'ck_conversations_next_sequence'),
    ('conversations', 'ck_conversations_resource_requires_location'),
    ('conversations', 'ck_conversations_default_language_length'),
    ('conversation_participants', 'ck_conversation_participants_type'),
    ('conversation_participants', 'ck_conversation_participants_references'),
    ('conversation_participants', 'ck_conversation_participants_language_length'),
    ('conversation_messages', 'ck_conversation_messages_sequence'),
    ('conversation_messages', 'ck_conversation_messages_modality'),
    ('conversation_messages', 'ck_conversation_messages_content'),
    ('conversation_messages', 'ck_conversation_messages_language_source'),
    ('conversation_messages', 'ck_conversation_messages_language_pair'),
    ('conversation_messages', 'ck_conversation_messages_language_length'),
    ('intelligence_derivations', 'ck_intelligence_derivations_schema_key'),
    ('intelligence_derivations', 'ck_intelligence_derivations_schema_version'),
    ('intelligence_derivations', 'ck_intelligence_derivations_producer_key'),
    ('intelligence_derivations', 'ck_intelligence_derivations_producer_version'),
    ('intelligence_derivations', 'ck_intelligence_derivations_correlation_id'),
    ('restaurant_message_intents', 'ck_restaurant_message_intents_ordinal'),
    ('restaurant_message_intents', 'ck_restaurant_message_intents_confidence'),
    ('restaurant_message_intents', 'ck_restaurant_message_intents_code'),
    ('product_categories', 'ck_product_categories_display_order'),
    ('product_compositions', 'ck_product_compositions_status'),
    ('product_components', 'ck_product_components_quantity'),
    ('product_components', 'ck_product_components_display_order'),
    ('product_components', 'ck_product_components_status'),
    ('product_choice_groups', 'ck_product_choice_groups_min'),
    ('product_choice_groups', 'ck_product_choice_groups_max'),
    ('product_choice_groups', 'ck_product_choice_groups_range'),
    ('product_choice_groups', 'ck_product_choice_groups_display_order'),
    ('product_choice_groups', 'ck_product_choice_groups_status'),
    ('product_choice_options', 'ck_product_choice_options_quantity'),
    ('product_choice_options', 'ck_product_choice_options_display_order'),
    ('product_choice_options', 'ck_product_choice_options_status'),
}

for table, prefix, target, target_table in (
    ('product_prices', 'product_prices', 'product', 'products'),
    ('product_prices', 'product_prices', 'location', 'locations'),
    ('promotion_products', 'promotion_products', 'promotion', 'promotions'),
    ('promotion_products', 'promotion_products', 'product', 'products'),
    ('promotion_locations', 'promotion_locations', 'promotion', 'promotions'),
    ('promotion_locations', 'promotion_locations', 'location', 'locations'),
):
    constraint = f'fk_{prefix}_{target}_tenant_org'
    EXPECTED_FOREIGN_KEY_COLUMNS.update({
        (constraint, table, f'{target}_id', target_table, 'id', 1),
        (constraint, table, 'tenant_id', target_table, 'tenant_id', 2),
        (constraint, table, 'organization_id', target_table, 'organization_id', 3),
    })
for table in ('product_prices', 'promotions', 'promotion_products', 'promotion_locations'):
    EXPECTED_FOREIGN_KEY_COLUMNS.add((f'fk_{table}_tenant', table, 'tenant_id', 'tenants', 'id', 1))
for table in ('product_prices', 'promotions'):
    EXPECTED_FOREIGN_KEY_COLUMNS.update({
        (f'fk_{table}_organization_tenant', table, 'organization_id', 'organizations', 'id', 1),
        (f'fk_{table}_organization_tenant', table, 'tenant_id', 'organizations', 'tenant_id', 2),
    })

def _index(table: str, name: str, columns: tuple[str, ...], non_unique: int) -> None:
    EXPECTED_INDEX_COLUMNS.update((table, name, column, position, non_unique) for position, column in enumerate(columns, 1))

_index('product_prices', 'uq_product_prices_tenant_product_location', ('tenant_id', 'product_id', 'location_id'), 0)
_index('product_prices', 'ix_product_prices_tenant_org_location_status_product', ('tenant_id', 'organization_id', 'location_id', 'status', 'product_id'), 1)
_index('product_prices', 'ix_product_prices_tenant_org_product_status', ('tenant_id', 'organization_id', 'product_id', 'status'), 1)
_index('promotions', 'uq_promotions_id_tenant_org', ('id', 'tenant_id', 'organization_id'), 0)
_index('promotions', 'ix_promotions_tenant_org_status_type', ('tenant_id', 'organization_id', 'status', 'promotion_type', 'id'), 1)
_index('promotions', 'ix_promotions_tenant_org_interval', ('tenant_id', 'organization_id', 'starts_at', 'ends_at', 'id'), 1)
_index('promotion_products', 'uq_promotion_products_tenant_promotion_product', ('tenant_id', 'promotion_id', 'product_id'), 0)
_index('promotion_products', 'ix_promotion_products_tenant_product_status', ('tenant_id', 'product_id', 'status', 'promotion_id'), 1)
_index('promotion_locations', 'uq_promotion_locations_tenant_promotion_location', ('tenant_id', 'promotion_id', 'location_id'), 0)
_index('promotion_locations', 'ix_promotion_locations_tenant_location_status', ('tenant_id', 'location_id', 'status', 'promotion_id'), 1)
_index('resources', 'uq_resources_id_tenant_location', ('id', 'tenant_id', 'location_id'), 0)
_index('conversations', 'uq_conversations_id_tenant', ('id', 'tenant_id'), 0)
_index('conversations', 'ix_conversations_tenant_org_status', ('tenant_id', 'organization_id', 'status', 'id'), 1)
_index('conversations', 'ix_conversations_tenant_location_status', ('tenant_id', 'location_id', 'status', 'id'), 1)
_index('conversations', 'ix_conversations_tenant_resource', ('tenant_id', 'resource_id', 'id'), 1)
_index('conversation_participants', 'uq_conversation_participants_id_tenant_conversation', ('id', 'tenant_id', 'conversation_id'), 0)
_index('conversation_participants', 'uq_conversation_participants_conversation_customer', ('conversation_id', 'customer_id'), 0)
_index('conversation_participants', 'ix_conversation_participants_conversation_type', ('tenant_id', 'conversation_id', 'participant_type', 'id'), 1)
_index('conversation_participants', 'ix_conversation_participants_customer', ('tenant_id', 'customer_id', 'id'), 1)
_index('conversation_participants', 'ix_conversation_participants_membership', ('tenant_id', 'tenant_membership_id', 'id'), 1)
_index('conversation_messages', 'uq_conversation_messages_tenant_conversation_sequence', ('tenant_id', 'conversation_id', 'sequence_number'), 0)
_index('conversation_messages', 'uq_conversation_messages_id_tenant_conversation', ('id', 'tenant_id', 'conversation_id'), 0)
_index('conversation_messages', 'ix_conversation_messages_participant', ('tenant_id', 'participant_id', 'id'), 1)
_index('intelligence_derivations', 'uq_intelligence_derivations_id_tenant', ('id', 'tenant_id'), 0)
_index('intelligence_derivations', 'ix_intelligence_derivations_tenant_message_created', ('tenant_id', 'source_message_id', 'created_at', 'id'), 1)
_index('intelligence_derivations', 'ix_intelligence_derivations_tenant_conversation', ('tenant_id', 'conversation_id', 'id'), 1)
_index('restaurant_message_intents', 'uq_restaurant_message_intents_derivation_ordinal', ('derivation_id', 'ordinal'), 0)
_index('restaurant_message_intents', 'ix_restaurant_message_intents_tenant_code', ('tenant_id', 'intent_code', 'id'), 1)
_index('product_categories', 'ix_product_categories_tenant_org_parent_status_order', ('tenant_id', 'organization_id', 'parent_id', 'status', 'display_order', 'id'), 1)
_index('product_compositions', 'uq_product_compositions_id_tenant_org', ('id', 'tenant_id', 'organization_id'), 0)
_index('product_compositions', 'uq_product_compositions_tenant_org_product', ('tenant_id', 'organization_id', 'product_id'), 0)
_index('product_compositions', 'ix_product_compositions_tenant_org_product_status', ('tenant_id', 'organization_id', 'product_id', 'status', 'id'), 1)
_index('product_components', 'uq_product_components_composition_product', ('tenant_id', 'organization_id', 'composition_id', 'component_product_id'), 0)
_index('product_components', 'ix_product_components_tenant_org_composition_status_order', ('tenant_id', 'organization_id', 'composition_id', 'status', 'display_order', 'id'), 1)
_index('product_choice_groups', 'uq_product_choice_groups_id_tenant_org', ('id', 'tenant_id', 'organization_id'), 0)
_index('product_choice_groups', 'uq_product_choice_groups_composition_name', ('tenant_id', 'organization_id', 'composition_id', 'name'), 0)
_index('product_choice_groups', 'ix_product_choice_groups_tenant_org_composition_status_order', ('tenant_id', 'organization_id', 'composition_id', 'status', 'display_order', 'id'), 1)
_index('product_choice_options', 'uq_product_choice_options_group_product', ('tenant_id', 'organization_id', 'group_id', 'option_product_id'), 0)
_index('product_choice_options', 'ix_product_choice_options_tenant_org_group_status_order', ('tenant_id', 'organization_id', 'group_id', 'status', 'display_order', 'id'), 1)

for constraint, table, local_columns, target_table, target_columns in (
    ('fk_product_categories_parent_tenant_org', 'product_categories', ('parent_id', 'tenant_id', 'organization_id'), 'product_categories', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_compositions_tenant', 'product_compositions', ('tenant_id',), 'tenants', ('id',)),
    ('fk_product_compositions_organization_tenant', 'product_compositions', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_product_compositions_product_tenant_org', 'product_compositions', ('product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_components_tenant', 'product_components', ('tenant_id',), 'tenants', ('id',)),
    ('fk_product_components_organization_tenant', 'product_components', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_product_components_composition_tenant_org', 'product_components', ('composition_id', 'tenant_id', 'organization_id'), 'product_compositions', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_components_product_tenant_org', 'product_components', ('component_product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_choice_groups_tenant', 'product_choice_groups', ('tenant_id',), 'tenants', ('id',)),
    ('fk_product_choice_groups_organization_tenant', 'product_choice_groups', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_product_choice_groups_composition_tenant_org', 'product_choice_groups', ('composition_id', 'tenant_id', 'organization_id'), 'product_compositions', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_choice_options_tenant', 'product_choice_options', ('tenant_id',), 'tenants', ('id',)),
    ('fk_product_choice_options_organization_tenant', 'product_choice_options', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_product_choice_options_group_tenant_org', 'product_choice_options', ('group_id', 'tenant_id', 'organization_id'), 'product_choice_groups', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_choice_options_product_tenant_org', 'product_choice_options', ('option_product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_conversations_tenant', 'conversations', ('tenant_id',), 'tenants', ('id',)),
    ('fk_conversations_organization_tenant', 'conversations', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_conversations_location_tenant_org', 'conversations', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_conversations_resource_tenant_location', 'conversations', ('resource_id', 'tenant_id', 'location_id'), 'resources', ('id', 'tenant_id', 'location_id')),
    ('fk_conversation_participants_tenant', 'conversation_participants', ('tenant_id',), 'tenants', ('id',)),
    ('fk_conversation_participants_conversation_tenant', 'conversation_participants', ('conversation_id', 'tenant_id'), 'conversations', ('id', 'tenant_id')),
    ('fk_conversation_participants_customer_tenant', 'conversation_participants', ('customer_id', 'tenant_id'), 'customers', ('id', 'tenant_id')),
    ('fk_conversation_participants_membership_tenant', 'conversation_participants', ('tenant_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_conversation_messages_tenant', 'conversation_messages', ('tenant_id',), 'tenants', ('id',)),
    ('fk_conversation_messages_conversation_tenant', 'conversation_messages', ('conversation_id', 'tenant_id'), 'conversations', ('id', 'tenant_id')),
    ('fk_conversation_messages_participant_tenant_conversation', 'conversation_messages', ('participant_id', 'tenant_id', 'conversation_id'), 'conversation_participants', ('id', 'tenant_id', 'conversation_id')),
    ('fk_intelligence_derivations_tenant', 'intelligence_derivations', ('tenant_id',), 'tenants', ('id',)),
    ('fk_intelligence_derivations_conversation_tenant', 'intelligence_derivations', ('conversation_id', 'tenant_id'), 'conversations', ('id', 'tenant_id')),
    ('fk_intelligence_derivations_message_tenant_conversation', 'intelligence_derivations', ('source_message_id', 'tenant_id', 'conversation_id'), 'conversation_messages', ('id', 'tenant_id', 'conversation_id')),
    ('fk_restaurant_message_intents_tenant', 'restaurant_message_intents', ('tenant_id',), 'tenants', ('id',)),
    ('fk_restaurant_message_intents_derivation_tenant', 'restaurant_message_intents', ('derivation_id', 'tenant_id'), 'intelligence_derivations', ('id', 'tenant_id')),
):
    EXPECTED_FOREIGN_KEY_COLUMNS.update(
        (constraint, table, local, target_table, target, position)
        for position, (local, target) in enumerate(zip(local_columns, target_columns), 1)
    )

API_ROOT = Path(__file__).resolve().parents[1]


def _database_contract(connection) -> tuple[set[tuple], set[tuple], set[tuple]]:
    with connection.cursor() as cursor:
        placeholders = ', '.join(['%s'] * len(APPLICATION_TABLES))
        cursor.execute(
            f'''
            SELECT TABLE_NAME, ENGINE, TABLE_COLLATION,
                   CCSA.CHARACTER_SET_NAME AS CHARACTER_SET_NAME
            FROM information_schema.TABLES AS T
            JOIN information_schema.COLLATION_CHARACTER_SET_APPLICABILITY AS CCSA
              ON CCSA.COLLATION_NAME = T.TABLE_COLLATION
            WHERE T.TABLE_SCHEMA = DATABASE()
              AND T.TABLE_NAME IN ({placeholders})
            ''',
            tuple(sorted(APPLICATION_TABLES)),
        )
        tables = {
            (
                row['TABLE_NAME'],
                row['ENGINE'],
                row['CHARACTER_SET_NAME'],
                row['TABLE_COLLATION'],
            )
            for row in cursor.fetchall()
        }
        cursor.execute(
            '''
            SELECT KCU.CONSTRAINT_NAME, KCU.TABLE_NAME, KCU.COLUMN_NAME,
                   KCU.REFERENCED_TABLE_NAME, KCU.REFERENCED_COLUMN_NAME,
                   KCU.ORDINAL_POSITION
            FROM information_schema.KEY_COLUMN_USAGE AS KCU
            WHERE KCU.TABLE_SCHEMA = DATABASE()
              AND KCU.REFERENCED_TABLE_NAME IS NOT NULL
            '''
        )
        foreign_keys = {
            (
                row['CONSTRAINT_NAME'],
                row['TABLE_NAME'],
                row['COLUMN_NAME'],
                row['REFERENCED_TABLE_NAME'],
                row['REFERENCED_COLUMN_NAME'],
                row['ORDINAL_POSITION'],
            )
            for row in cursor.fetchall()
        }
        index_names = {row[1] for row in EXPECTED_INDEX_COLUMNS}
        index_placeholders = ', '.join(['%s'] * len(index_names))
        cursor.execute(
            f'''
            SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND INDEX_NAME IN ({index_placeholders})
            ''',
            tuple(sorted(index_names)),
        )
        indexes = {
            (
                row['TABLE_NAME'],
                row['INDEX_NAME'],
                row['COLUMN_NAME'],
                row['SEQ_IN_INDEX'],
                row['NON_UNIQUE'],
            )
            for row in cursor.fetchall()
        }
    return tables, foreign_keys, indexes


def _assert_database_contract(connection) -> None:
    tables, foreign_keys, indexes = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}
    assert foreign_keys == EXPECTED_FOREIGN_KEY_COLUMNS
    assert indexes == EXPECTED_INDEX_COLUMNS
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND CONSTRAINT_TYPE = 'CHECK'
              AND TABLE_NAME IN (
                  'resources', 'customers', 'product_categories', 'products', 'menus',
                  'menu_locations', 'menu_sections', 'menu_items', 'product_prices',
                  'promotions', 'promotion_products', 'promotion_locations',
                  'conversations', 'conversation_participants', 'conversation_messages',
                  'intelligence_derivations', 'restaurant_message_intents',
                  'product_compositions', 'product_components',
                  'product_choice_groups', 'product_choice_options'
              )
            '''
        )
        assert {(row['TABLE_NAME'], row['CONSTRAINT_NAME']) for row in cursor.fetchall()} == (
            EXPECTED_DOMAIN_CHECKS
        )
        cursor.execute(
            '''
            SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND (
                  (TABLE_NAME = 'customer_external_identities'
                   AND COLUMN_NAME = 'external_customer_id')
                  OR
                  (TABLE_NAME = 'product_external_mappings'
                   AND COLUMN_NAME = 'external_product_id')
              )
            '''
        )
        assert {
            (row['TABLE_NAME'], row['COLUMN_NAME'], row['COLLATION_NAME'])
            for row in cursor.fetchall()
        } == {
            ('customer_external_identities', 'external_customer_id', 'utf8mb4_bin'),
            ('product_external_mappings', 'external_product_id', 'utf8mb4_bin'),
        }


def _run_alembic(database_name: str, revision: str) -> None:
    environment = os.environ.copy()
    environment['MYSQL_DATABASE'] = database_name
    environment['MYSQL_USER'] = 'root'
    environment['MYSQL_PASSWORD'] = environment['MYSQL_ROOT_PASSWORD']
    subprocess.run(
        ['alembic', 'upgrade', revision],
        cwd=API_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def isolated_database(integration_settings: Settings):
    root_password = os.getenv('MYSQL_ROOT_PASSWORD')
    assert root_password, 'MYSQL_ROOT_PASSWORD is required for isolated migration-path tests'

    database_name = f'ecip_portability_{uuid4().hex}'
    server_connection = pymysql.connect(
        host=integration_settings.mysql_host,
        port=integration_settings.mysql_port,
        user='root',
        password=root_password,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with server_connection.cursor() as cursor:
        cursor.execute(
            f'CREATE DATABASE `{database_name}` '
            'CHARACTER SET latin1 COLLATE latin1_swedish_ci'
        )
    try:
        yield database_name, server_connection
    finally:
        with server_connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{database_name}`')
        server_connection.close()


def _connect_isolated_database(integration_settings: Settings, database_name: str):
    return pymysql.connect(
        host=integration_settings.mysql_host,
        port=integration_settings.mysql_port,
        user='root',
        password=os.environ['MYSQL_ROOT_PASSWORD'],
        database=database_name,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def test_model_metadata_declares_portable_mysql_table_options() -> None:
    assert set(Base.metadata.tables) == APPLICATION_TABLES
    for table in Base.metadata.sorted_tables:
        options = table.dialect_options['mysql']
        assert options['engine'] == 'InnoDB'
        assert options['charset'] == 'utf8mb4'
        assert options['collate'] == 'utf8mb4_unicode_ci'


def test_database_tables_enforce_storage_contract(sql_connection) -> None:
    connection, _ = sql_connection
    tables, _, _ = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}


def test_database_has_all_expected_foreign_keys(sql_connection) -> None:
    connection, _ = sql_connection
    _, foreign_keys, indexes = _database_contract(connection)
    assert foreign_keys == EXPECTED_FOREIGN_KEY_COLUMNS
    assert indexes == EXPECTED_INDEX_COLUMNS
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND CONSTRAINT_TYPE = 'CHECK'
              AND TABLE_NAME IN (
                  'resources', 'customers', 'product_categories', 'products', 'menus',
                  'menu_locations', 'menu_sections', 'menu_items', 'product_prices',
                  'promotions', 'promotion_products', 'promotion_locations',
                  'conversations', 'conversation_participants', 'conversation_messages',
                  'intelligence_derivations', 'restaurant_message_intents',
                  'product_compositions', 'product_components',
                  'product_choice_groups', 'product_choice_options'
              )
            '''
        )
        assert {(row['TABLE_NAME'], row['CONSTRAINT_NAME']) for row in cursor.fetchall()} == (
            EXPECTED_DOMAIN_CHECKS
        )
        cursor.execute(
            '''
            SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND (
                  (TABLE_NAME = 'customer_external_identities'
                   AND COLUMN_NAME = 'external_customer_id')
                  OR
                  (TABLE_NAME = 'product_external_mappings'
                   AND COLUMN_NAME = 'external_product_id')
              )
            '''
        )
        assert {
            (row['TABLE_NAME'], row['COLUMN_NAME'], row['COLLATION_NAME'])
            for row in cursor.fetchall()
        } == {
            ('customer_external_identities', 'external_customer_id', 'utf8mb4_bin'),
            ('product_external_mappings', 'external_product_id', 'utf8mb4_bin'),
        }


def test_foreign_key_is_actually_enforced(sql_connection) -> None:
    connection, _ = sql_connection
    with pytest.raises(pymysql.err.IntegrityError):
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO tenant_memberships (tenant_id, user_id, status)
                VALUES (%s, %s, 'ACTIVE')
                ''',
                (9_000_000_001, 9_000_000_002),
            )


def test_ws12_raw_scope_and_check_probes_are_rollback_only(sql_connection) -> None:
    connection, prefix = sql_connection
    connection.autocommit(False)
    connection.begin()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('Probe A',%s,'ACTIVE')",
                (f'{prefix}-probe-a',),
            )
            tenant_a = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('Probe B',%s,'ACTIVE')",
                (f'{prefix}-probe-b',),
            )
            tenant_b = int(cursor.lastrowid)
            organizations = []
            for tenant_id, code in ((tenant_a, 'A1'), (tenant_a, 'A2'), (tenant_b, 'B1')):
                cursor.execute(
                    "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,%s,'ACTIVE')",
                    (tenant_id, f'{code}-{uuid4().hex[:8]}', code),
                )
                organizations.append(int(cursor.lastrowid))
            org_a, org_a2, org_b = organizations

            categories = []
            for tenant_id, organization_id, name in (
                (tenant_a, org_a, 'Category A'),
                (tenant_a, org_a2, 'Category A2'),
                (tenant_b, org_b, 'Category B'),
            ):
                cursor.execute(
                    "INSERT INTO product_categories (tenant_id,organization_id,name,status) VALUES (%s,%s,%s,'ACTIVE')",
                    (tenant_id, organization_id, name),
                )
                categories.append(int(cursor.lastrowid))
            category_a, category_a2, category_b = categories

            products = []
            for tenant_id, organization_id, name in (
                (tenant_a, org_a, 'Parent A'),
                (tenant_a, org_a, 'Child A'),
                (tenant_a, org_a2, 'Product A2'),
                (tenant_b, org_b, 'Product B'),
            ):
                cursor.execute(
                    "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,%s,'ACTIVE','PLATFORM')",
                    (tenant_id, organization_id, name),
                )
                products.append(int(cursor.lastrowid))
            parent_a, child_a, product_a2, product_b = products
            cursor.execute(
                "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
                (tenant_a, org_a, parent_a),
            )
            composition_a = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Choice',0,1,0,'ACTIVE')",
                (tenant_a, org_a, composition_a),
            )
            group_a = int(cursor.lastrowid)

        probes = (
            (
                'UPDATE product_categories SET parent_id=%s WHERE id=%s',
                (category_a2, category_a),
            ),
            (
                'UPDATE product_categories SET parent_id=%s WHERE id=%s',
                (category_b, category_a),
            ),
            (
                "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
                (tenant_a, org_a, product_a2),
            ),
            (
                "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
                (tenant_a, org_a, product_b),
            ),
            (
                "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_b, org_b, composition_a, product_b),
            ),
            (
                "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_a, org_a, composition_a, product_a2),
            ),
            (
                "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_a, org_a, composition_a, product_b),
            ),
            (
                "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_a, org_a, group_a, product_a2),
            ),
            (
                "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_a, org_a, group_a, product_b),
            ),
            (
                "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_a, org_a2, group_a, product_a2),
            ),
            (
                "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                (tenant_b, org_b, group_a, product_b),
            ),
            (
                "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,0,0,'ACTIVE')",
                (tenant_a, org_a, composition_a, child_a),
            ),
            (
                "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Invalid range',2,1,0,'ACTIVE')",
                (tenant_a, org_a, composition_a),
            ),
            (
                "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Invalid minimum',-1,1,0,'ACTIVE')",
                (tenant_a, org_a, composition_a),
            ),
            (
                "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Invalid maximum',0,0,0,'ACTIVE')",
                (tenant_a, org_a, composition_a),
            ),
        )
        for statement, parameters in probes:
            with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
    finally:
        connection.rollback()
        connection.autocommit(True)

    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM tenants WHERE slug LIKE %s', (f'{prefix}-probe-%',))
        assert cursor.fetchone()['count'] == 0


def test_fresh_install_reaches_portable_database_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()


def test_upgrade_from_0010_preserves_flat_category_and_reaches_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0010_intelligence_derivation_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('Upgrade','upgrade-0010','ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'ORG','Organization','ACTIVE')",
                (tenant_id,),
            )
            organization_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO product_categories (tenant_id,organization_id,name,status) VALUES (%s,%s,'Legacy Flat','ACTIVE')",
                (tenant_id, organization_id),
            )
            category_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT parent_id,display_order FROM product_categories WHERE id=%s',
                (category_id,),
            )
            assert cursor.fetchone() == {'parent_id': None, 'display_order': 0}
            cursor.execute(
                "SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='product_components' AND COLUMN_NAME='quantity'"
            )
            assert cursor.fetchone()['COLUMN_TYPE'] == 'decimal(19,4)'
    finally:
        connection.close()


def test_upgrade_from_0003_reaches_contract_and_upgrades_existing_tenant_admin(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0003_database_portability_remediation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) VALUES ('Upgrade Tenant', 'upgrade', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO permissions (code, description)
                VALUES ('organization.read', 'Preexisting permission')
                '''
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN (
                      'organization.read', 'organization.manage',
                      'location.read', 'location.manage',
                      'resource.read', 'resource.manage',
                      'customer.read', 'customer.manage'
                  )
                ORDER BY P.code
                ''',
                (role_id,),
            )
            assert [row['code'] for row in cursor.fetchall()] == [
                'customer.manage',
                'customer.read',
                'location.manage',
                'location.read',
                'organization.manage',
                'organization.read',
                'resource.manage',
                'resource.read',
            ]
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN (
                      'organization.read', 'organization.manage',
                      'location.read', 'location.manage',
                      'resource.read', 'resource.manage',
                      'customer.read', 'customer.manage'
                  )
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'customer.manage': 1,
                'customer.read': 1,
                'location.manage': 1,
                'location.read': 1,
                'organization.manage': 1,
                'organization.read': 1,
                'resource.manage': 1,
                'resource.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0004_reaches_contract_and_upgrades_existing_tenant_admin(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0004_organization_location_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO tenants (name, slug, status)
                VALUES ('Resource Tenant', 'resource', 'ACTIVE')
                '''
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO permissions (code, description)
                VALUES ('resource.read', 'Preexisting')
                '''
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('resource.read', 'resource.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'resource.manage': 1,
                'resource.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0005_reaches_customer_contract_and_upgrades_existing_tenant_admin(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0005_resource_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) "
                "VALUES ('Customer Tenant', 'customer', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO permissions (code, description) "
                "VALUES ('customer.read', 'Preexisting')"
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('customer.read', 'customer.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'customer.manage': 1,
                'customer.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0006_reaches_menu_product_contract_and_grants_permissions(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0006_customer_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) VALUES ('Catalog Tenant', 'catalog', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                '''
                INSERT INTO roles (tenant_id, name, description, status)
                VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')
                ''',
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO permissions (code, description) "
                "VALUES ('product.read', 'Preexisting permission')"
            )
            permission_id = int(cursor.lastrowid)
            cursor.execute(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
                (role_id, permission_id),
            )
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('product.read', 'product.manage', 'menu.read', 'menu.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'menu.manage': 1,
                'menu.read': 1,
                'product.manage': 1,
                'product.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0007_reaches_pricing_contract_and_grants_permissions(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0007_menu_product_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) VALUES ('Pricing Tenant', 'pricing', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO roles (tenant_id, name, description, status) "
                "VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')",
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN (
                      'pricing.read', 'pricing.manage',
                      'promotion.read', 'promotion.manage'
                  )
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'pricing.manage': 1,
                'pricing.read': 1,
                'promotion.manage': 1,
                'promotion.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0008_reaches_conversation_contract_and_grants_permissions(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0008_pricing_promotion_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) "
                "VALUES ('Conversation Tenant', 'conversation', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO roles (tenant_id, name, description, status) "
                "VALUES (%s, 'TENANT_ADMIN', 'Existing administrator', 'ACTIVE')",
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('conversation.read', 'conversation.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'conversation.manage': 1,
                'conversation.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0009_reaches_intelligence_derivation_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0009_conversation_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name, slug, status) VALUES ('WS11 Tenant', 'ws11', 'ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO organizations (tenant_id, code, name, status) "
                "VALUES (%s, 'ORG', 'Org', 'ACTIVE')",
                (tenant_id,),
            )
            organization_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO conversations "
                "(tenant_id, organization_id, channel, status, next_message_sequence) "
                "VALUES (%s, %s, 'PHONE', 'ACTIVE', 2)",
                (tenant_id, organization_id),
            )
            conversation_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO conversation_participants "
                "(tenant_id, conversation_id, participant_type) "
                "VALUES (%s, %s, 'CUSTOMER')",
                (tenant_id, conversation_id),
            )
            participant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO conversation_messages "
                "(tenant_id, conversation_id, participant_id, sequence_number, modality, content_text) "
                "VALUES (%s, %s, %s, 1, 'TEXT', 'preserved evidence')",
                (tenant_id, conversation_id, participant_id),
            )
            message_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT content_text FROM conversation_messages WHERE id=%s',
                (message_id,),
            )
            assert cursor.fetchone()['content_text'] == 'preserved evidence'
    finally:
        connection.close()


def test_upgrade_from_unsafe_0002_schema_reaches_portable_database_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0002_auth_tenant_foundation')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT DISTINCT TABLE_NAME, CONSTRAINT_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                '''
            )
            for row in cursor.fetchall():
                cursor.execute(
                    f"ALTER TABLE `{row['TABLE_NAME']}` "
                    f"DROP FOREIGN KEY `{row['CONSTRAINT_NAME']}`"
                )
            for table_name in LEGACY_APPLICATION_TABLES:
                cursor.execute(
                    f'ALTER TABLE `{table_name}` ENGINE=MyISAM, '
                    'CONVERT TO CHARACTER SET latin1 COLLATE latin1_swedish_ci'
                )

        unsafe_tables, unsafe_foreign_keys, _ = _database_contract(connection)
        assert {row[1] for row in unsafe_tables} == {'MyISAM'}
        assert {row[2] for row in unsafe_tables} == {'latin1'}
        assert {row[3] for row in unsafe_tables} == {'latin1_swedish_ci'}
        assert unsafe_foreign_keys == set()
    finally:
        connection.close()

    _run_alembic(database_name, 'head')

    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()
