from __future__ import annotations

import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pymysql
import pytest
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint

from app import models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base


APPLICATION_TABLES = {
    'billing_documents',
    'billing_document_lines',
    'billing_document_line_taxes',
    'issuer_fiscal_profiles',
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
    'customer_fiscal_profiles',
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
    'product_aliases',
    'order_drafts',
    'order_draft_items',
    'order_draft_item_selections',
    'restaurant_service_sessions',
    'diner_sessions',
    'restaurant_orders',
    'restaurant_order_items',
    'restaurant_order_item_components',
    'restaurant_order_promotions',
    'location_pos_connections',
    'pos_order_submissions',
    'pos_order_submission_lines',
    'pos_order_submission_components',
    'pos_order_submission_attempts',
    'location_preparation_configurations',
    'preparation_areas',
    'product_preparation_routes',
    'preparation_routings',
    'preparation_works',
    'preparation_work_items',
    'preparation_item_transitions',
    'preparation_delivery_connectors',
    'preparation_delivery_connector_enrollments',
    'preparation_delivery_connector_credentials',
    'preparation_delivery_destinations',
    'preparation_dispatches',
    'preparation_dispatch_attempts',
    'restaurant_checks',
    'restaurant_check_members',
    'restaurant_check_allocations',
    'restaurant_check_versions',
    'restaurant_check_gratuities',
    'restaurant_check_commands',
    'restaurant_check_table_scopes',
    'restaurant_payments',
    'restaurant_payment_attempts',
    'restaurant_check_settlements',
    'restaurant_tax_rules',
    'restaurant_order_item_tax_snapshots',
    'location_payment_executor_configurations',
    'location_payment_executor_capabilities',
}


APPLICATION_TABLES_0024 = APPLICATION_TABLES - {
    'billing_documents',
    'billing_document_lines',
    'billing_document_line_taxes',
    'issuer_fiscal_profiles',
    'customer_fiscal_profiles',
    'restaurant_tax_rules',
    'restaurant_order_item_tax_snapshots',
}

LEGACY_APPLICATION_TABLES = APPLICATION_TABLES - {
    'billing_documents',
    'billing_document_lines',
    'billing_document_line_taxes',
    'organizations',
    'issuer_fiscal_profiles',
    'locations',
    'resources',
    'customers',
    'customer_fiscal_profiles',
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
    'product_aliases',
    'order_drafts',
    'order_draft_items',
    'order_draft_item_selections',
    'restaurant_service_sessions',
    'diner_sessions',
    'restaurant_orders',
    'restaurant_order_items',
    'restaurant_order_item_components',
    'restaurant_order_promotions',
    'location_pos_connections',
    'pos_order_submissions',
    'pos_order_submission_lines',
    'pos_order_submission_components',
    'pos_order_submission_attempts',
    'location_preparation_configurations',
    'preparation_areas',
    'product_preparation_routes',
    'preparation_routings',
    'preparation_works',
    'preparation_work_items',
    'preparation_item_transitions',
    'preparation_delivery_connectors',
    'preparation_delivery_connector_enrollments',
    'preparation_delivery_connector_credentials',
    'preparation_delivery_destinations',
    'preparation_dispatches',
    'preparation_dispatch_attempts',
    'restaurant_checks',
    'restaurant_check_members',
    'restaurant_check_allocations',
    'restaurant_check_versions',
    'restaurant_check_gratuities',
    'restaurant_check_commands',
    'restaurant_check_table_scopes',
    'restaurant_payments',
    'location_payment_executor_configurations',
    'location_payment_executor_capabilities',
    'restaurant_payment_attempts',
    'restaurant_check_settlements',
    'restaurant_tax_rules',
    'restaurant_order_item_tax_snapshots',
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
    ('restaurant_checks', 'ck_restaurant_checks_lifecycle'),
    ('restaurant_checks', 'ck_restaurant_checks_controller_actor'),
    ('restaurant_checks', 'ck_restaurant_checks_created_actor'),
    ('restaurant_checks', 'ck_restaurant_checks_status'),
    ('restaurant_checks', 'ck_restaurant_checks_money'),
    ('restaurant_checks', 'ck_restaurant_checks_arithmetic'),
    ('restaurant_checks', 'ck_restaurant_checks_versions'),
    ('restaurant_check_members', 'ck_check_members_relationship'),
    ('restaurant_check_members', 'ck_check_members_lifecycle'),
    ('restaurant_check_members', 'ck_check_members_versions'),
    ('restaurant_check_members', 'ck_check_members_active_slot'),
    ('restaurant_check_allocations', 'ck_check_allocations_lifecycle'),
    ('restaurant_check_allocations', 'ck_check_allocations_state'),
    ('restaurant_check_allocations', 'ck_check_allocations_values'),
    ('restaurant_check_allocations', 'ck_check_allocations_owner_slot'),
    ('restaurant_check_versions', 'ck_check_versions_money'),
    ('restaurant_check_versions', 'ck_check_versions_versions'),
    ('restaurant_check_gratuities', 'ck_check_gratuities_type'),
    ('restaurant_check_gratuities', 'ck_check_gratuities_rounding'),
    ('restaurant_check_gratuities', 'ck_check_gratuities_values'),
    ('restaurant_check_commands', 'ck_check_commands_result_version'),
    ('restaurant_checks', 'ck_restaurant_checks_continuation'),
    ('restaurant_check_table_scopes', 'ck_check_table_scopes_active_slot'),
    ('restaurant_check_table_scopes', 'ck_check_table_scopes_phase'),
    ('restaurant_check_table_scopes', 'ck_check_table_scopes_lifecycle'),
    ('restaurant_payments', 'ck_restaurant_payments_state'),
    ('restaurant_payments', 'ck_restaurant_payments_method'),
    ('restaurant_payments', 'ck_restaurant_payments_payer_type'),
    ('restaurant_payments', 'ck_restaurant_payments_actor'),
    ('restaurant_payments', 'ck_restaurant_payments_values'),
    ('restaurant_payments', 'ck_restaurant_payments_payer'),
    ('restaurant_payments', 'ck_restaurant_payments_claim'),
    ('restaurant_payments', 'ck_restaurant_payments_execution_evidence'),
    ('restaurant_payment_attempts', 'ck_restaurant_payment_attempts_type'),
    ('restaurant_payment_attempts', 'ck_restaurant_payment_attempts_result'),
    ('restaurant_payment_attempts', 'ck_restaurant_payment_attempts_actor'),
    ('restaurant_payment_attempts', 'ck_restaurant_payment_attempts_lifecycle'),
    ('restaurant_check_settlements', 'ck_check_settlements_amount'),
    ('restaurant_check_settlements', 'ck_check_settlements_actor'),
    ('location_payment_executor_configurations', 'ck_payment_executor_configurations_topology'),
    ('location_payment_executor_configurations', 'ck_payment_executor_configurations_status'),
    ('location_payment_executor_configurations', 'ck_payment_executor_configurations_priority'),
    ('location_payment_executor_capabilities', 'ck_payment_executor_capabilities_method'),
    ('location_payment_executor_capabilities', 'ck_payment_executor_capabilities_currency'),
    ('preparation_delivery_connector_enrollments', 'ck_connector_enrollments_active_slot'),
    ('preparation_delivery_connector_credentials', 'ck_connector_credentials_status'),
    ('resources', 'ck_resources_status'),
    ('resources', 'ck_resources_type'),
    ('restaurant_service_sessions', 'ck_restaurant_service_sessions_status'),
    ('restaurant_service_sessions', 'ck_restaurant_service_sessions_party_size'),
    ('restaurant_service_sessions', 'ck_restaurant_service_sessions_code_version'),
    ('restaurant_service_sessions', 'ck_restaurant_service_sessions_failed_attempts'),
    ('restaurant_service_sessions', 'ck_restaurant_service_sessions_open_slot'),
    ('restaurant_service_sessions', 'ck_restaurant_service_sessions_lifecycle'),
    ('diner_sessions', 'ck_diner_sessions_status'),
    ('diner_sessions', 'ck_diner_sessions_active_slot'),
    ('diner_sessions', 'ck_diner_sessions_display_name'),
    ('diner_sessions', 'ck_diner_sessions_lifecycle'),
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
    ('promotions', 'ck_promotions_is_combinable'),
    ('promotions', 'ck_promotions_priority'),
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
    ('product_aliases', 'ck_product_aliases_status'),
    ('product_aliases', 'ck_product_aliases_alias_nonempty'),
    ('product_aliases', 'ck_product_aliases_normalized_nonempty'),
    ('product_aliases', 'ck_product_aliases_language_length'),
    ('order_drafts', 'ck_order_drafts_version'),
    ('order_drafts', 'ck_order_drafts_status'),
    ('order_drafts', 'ck_order_drafts_current_slot'),
    ('order_drafts', 'ck_order_drafts_lifecycle'),
    ('order_draft_items', 'ck_order_draft_items_quantity'),
    ('order_draft_items', 'ck_order_draft_items_position'),
    ('restaurant_orders', 'ck_restaurant_orders_status'),
    ('restaurant_orders', 'ck_restaurant_orders_draft_version'),
    ('restaurant_orders', 'ck_restaurant_orders_fingerprint_version'),
    ('restaurant_orders', 'ck_restaurant_orders_tax_mode'),
    ('restaurant_orders', 'ck_restaurant_orders_rounding_policy'),
    ('restaurant_orders', 'ck_restaurant_orders_money_nonnegative'),
    ('restaurant_orders', 'ck_restaurant_orders_pre_round_arithmetic'),
    ('restaurant_orders', 'ck_restaurant_orders_payable_arithmetic'),
    ('restaurant_order_items', 'ck_restaurant_order_items_quantity'),
    ('restaurant_order_items', 'ck_restaurant_order_items_position'),
    ('restaurant_order_items', 'ck_restaurant_order_items_money'),
    ('restaurant_order_items', 'ck_restaurant_order_items_arithmetic'),
    ('restaurant_order_item_components', 'ck_restaurant_order_components_kind'),
    ('restaurant_order_item_components', 'ck_restaurant_order_components_values'),
    ('restaurant_order_item_components', 'ck_restaurant_order_components_source'),
    ('restaurant_order_promotions', 'ck_restaurant_order_promotions_ordering'),
    ('restaurant_order_promotions', 'ck_restaurant_order_promotions_money'),
    ('location_pos_connections', 'ck_location_pos_connections_active_slot'),
    ('location_pos_connections', 'ck_location_pos_connections_lifecycle'),
    ('location_pos_connections', 'ck_location_pos_connections_status'),
    ('location_pos_connections', 'ck_location_pos_connections_preparation_behavior'),
    ('pos_order_submissions', 'ck_pos_order_submissions_actor'),
    ('pos_order_submissions', 'ck_pos_order_submissions_claim'),
    ('pos_order_submissions', 'ck_pos_order_submissions_state'),
    ('pos_order_submissions', 'ck_pos_order_submissions_success'),
    ('pos_order_submissions', 'ck_pos_order_submissions_versions'),
    ('pos_order_submission_attempts', 'ck_pos_submission_attempts_actor'),
    ('pos_order_submission_attempts', 'ck_pos_submission_attempts_lifecycle'),
    ('pos_order_submission_attempts', 'ck_pos_submission_attempts_result'),
    ('pos_order_submission_attempts', 'ck_pos_submission_attempts_type'),
    ('location_preparation_configurations', 'ck_location_preparation_configurations_owner'),
    ('preparation_areas', 'ck_preparation_areas_status'),
    ('product_preparation_routes', 'ck_product_preparation_routes_policy'),
    ('product_preparation_routes', 'ck_product_preparation_routes_status'),
    ('product_preparation_routes', 'ck_product_preparation_routes_active_slot'),
    ('product_preparation_routes', 'ck_product_preparation_routes_lifecycle'),
    ('product_preparation_routes', 'ck_product_preparation_routes_area'),
    ('preparation_routings', 'ck_preparation_routings_owner'),
    ('preparation_routings', 'ck_preparation_routings_state'),
    ('preparation_routings', 'ck_preparation_routings_version'),
    ('preparation_routings', 'ck_preparation_routings_actor'),
    ('preparation_routings', 'ck_preparation_routings_lifecycle'),
    ('preparation_works', 'ck_preparation_works_owner'),
    ('preparation_works', 'ck_preparation_works_version'),
    ('preparation_work_items', 'ck_preparation_work_items_quantity'),
    ('preparation_work_items', 'ck_preparation_work_items_policy'),
    ('preparation_work_items', 'ck_preparation_work_items_source_xor'),
    ('preparation_work_items', 'ck_preparation_work_items_execution_state'),
    ('preparation_work_items', 'ck_preparation_work_items_execution_version'),
    ('preparation_item_transitions', 'ck_preparation_item_transitions_sequence'),
    ('preparation_item_transitions', 'ck_preparation_item_transitions_edge'),
    ('preparation_item_transitions', 'ck_preparation_item_transitions_actor'),
    ('preparation_delivery_connectors', 'ck_preparation_delivery_connectors_status'),
    ('preparation_delivery_destinations', 'ck_preparation_delivery_destinations_channel'),
    ('preparation_delivery_destinations', 'ck_preparation_delivery_destinations_status'),
    ('preparation_delivery_destinations', 'ck_preparation_delivery_destinations_active_slot'),
    ('preparation_delivery_destinations', 'ck_preparation_delivery_destinations_lifecycle'),
    ('preparation_dispatches', 'ck_preparation_dispatches_operation_kind'),
    ('preparation_dispatches', 'ck_preparation_dispatches_generation'),
    ('preparation_dispatches', 'ck_preparation_dispatches_operation_semantics'),
    ('preparation_dispatches', 'ck_preparation_dispatches_state'),
    ('preparation_dispatches', 'ck_preparation_dispatches_attempt_count'),
    ('preparation_dispatches', 'ck_preparation_dispatches_claim'),
    ('preparation_dispatches', 'ck_preparation_dispatches_actor'),
    ('preparation_dispatch_attempts', 'ck_preparation_dispatch_attempts_type'),
    ('preparation_dispatch_attempts', 'ck_preparation_dispatch_attempts_result'),
    ('preparation_dispatch_attempts', 'ck_preparation_dispatch_attempts_lifecycle'),
    ('preparation_dispatch_attempts', 'ck_preparation_dispatch_attempts_actor'),
    ('restaurant_tax_rules', 'ck_restaurant_tax_rules_rate'),
    ('restaurant_tax_rules', 'ck_restaurant_tax_rules_effective_interval'),
    ('restaurant_tax_rules', 'ck_restaurant_tax_rules_status'),
    ('restaurant_order_item_tax_snapshots', 'ck_order_item_tax_snapshots_values'),
    (
        'restaurant_order_item_tax_snapshots',
        'ck_order_item_tax_snapshots_schema_version',
    ),
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
_index('conversations', 'uq_conversations_id_tenant_org_location', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
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
_index('product_compositions', 'uq_product_compositions_id_tenant_org_product', ('id', 'tenant_id', 'organization_id', 'product_id'), 0)
_index('product_compositions', 'uq_product_compositions_tenant_org_product', ('tenant_id', 'organization_id', 'product_id'), 0)
_index('product_compositions', 'ix_product_compositions_tenant_org_product_status', ('tenant_id', 'organization_id', 'product_id', 'status', 'id'), 1)
_index('product_components', 'uq_product_components_composition_product', ('tenant_id', 'organization_id', 'composition_id', 'component_product_id'), 0)
_index('product_components', 'ix_product_components_tenant_org_composition_status_order', ('tenant_id', 'organization_id', 'composition_id', 'status', 'display_order', 'id'), 1)
_index('product_choice_groups', 'uq_product_choice_groups_id_tenant_org', ('id', 'tenant_id', 'organization_id'), 0)
_index('product_choice_groups', 'uq_product_choice_groups_id_tenant_org_composition', ('id', 'tenant_id', 'organization_id', 'composition_id'), 0)
_index('product_choice_groups', 'uq_product_choice_groups_composition_name', ('tenant_id', 'organization_id', 'composition_id', 'name'), 0)
_index('product_choice_groups', 'ix_product_choice_groups_tenant_org_composition_status_order', ('tenant_id', 'organization_id', 'composition_id', 'status', 'display_order', 'id'), 1)
_index('product_choice_options', 'uq_product_choice_options_group_product', ('tenant_id', 'organization_id', 'group_id', 'option_product_id'), 0)
_index('product_choice_options', 'uq_product_choice_options_id_tenant_org_group', ('id', 'tenant_id', 'organization_id', 'group_id'), 0)
_index('product_choice_options', 'ix_product_choice_options_tenant_org_group_status_order', ('tenant_id', 'organization_id', 'group_id', 'status', 'display_order', 'id'), 1)
_index('product_aliases', 'uq_product_aliases_product_identity', ('tenant_id', 'organization_id', 'product_id', 'normalized_alias', 'language'), 0)
_index('product_aliases', 'ix_product_aliases_tenant_org_lookup', ('tenant_id', 'organization_id', 'normalized_alias', 'language', 'status', 'product_id', 'id'), 1)
_index('product_aliases', 'ix_product_aliases_tenant_org_product', ('tenant_id', 'organization_id', 'product_id', 'id'), 1)
_index('order_drafts', 'uq_order_drafts_tenant_conversation_current', ('tenant_id', 'conversation_id', 'current_slot'), 0)
_index('order_drafts', 'uq_order_drafts_id_tenant_org', ('id', 'tenant_id', 'organization_id'), 0)
_index('order_drafts', 'uq_order_drafts_full_scope', ('id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id'), 0)
_index('order_drafts', 'ix_order_drafts_tenant_org_location', ('tenant_id', 'organization_id', 'location_id', 'id'), 1)
_index('order_draft_items', 'uq_order_draft_items_draft_position', ('draft_id', 'position'), 0)
_index('order_draft_items', 'uq_order_draft_items_selection_scope', ('id', 'tenant_id', 'organization_id', 'draft_id', 'composition_id'), 0)
_index('order_draft_items', 'ix_order_draft_items_tenant_draft_order', ('tenant_id', 'draft_id', 'position', 'id'), 1)
_index('order_draft_items', 'ix_order_draft_items_tenant_org_product', ('tenant_id', 'organization_id', 'product_id', 'id'), 1)
_index('order_draft_item_selections', 'uq_order_draft_selections_item_option', ('draft_item_id', 'choice_option_id'), 0)
_index('order_draft_item_selections', 'ix_order_draft_selections_tenant_item_group', ('tenant_id', 'draft_item_id', 'choice_group_id', 'choice_option_id'), 1)
_index('order_draft_item_selections', 'ix_order_draft_selections_tenant_choice', ('tenant_id', 'organization_id', 'choice_group_id', 'choice_option_id', 'id'), 1)
_index('restaurant_service_sessions', 'uq_restaurant_service_sessions_resource_open', ('resource_id', 'open_slot'), 0)
_index('restaurant_service_sessions', 'uq_restaurant_service_sessions_join_context', ('join_context_key',), 0)
_index('restaurant_service_sessions', 'uq_restaurant_service_sessions_scope', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 0)
_index('restaurant_service_sessions', 'ix_restaurant_service_sessions_resource_history', ('resource_id', 'id'), 1)
_index('restaurant_service_sessions', 'ix_restaurant_service_sessions_tenant_location_status', ('tenant_id', 'location_id', 'status', 'id'), 1)
_index('diner_sessions', 'uq_diner_sessions_active_email', ('service_session_id', 'normalized_email', 'active_slot'), 0)
_index('diner_sessions', 'uq_diner_sessions_conversation', ('conversation_id',), 0)
_index('diner_sessions', 'uq_diner_sessions_participant', ('conversation_participant_id',), 0)
_index('diner_sessions', 'uq_diner_sessions_full_scope', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'), 0)
_index('diner_sessions', 'ix_diner_sessions_service_active', ('service_session_id', 'active_slot', 'id'), 1)
_index('diner_sessions', 'ix_diner_sessions_customer', ('tenant_id', 'customer_id', 'id'), 1)

_index('restaurant_orders', 'uq_restaurant_orders_source_draft', ('source_order_draft_id',), 0)
_index('restaurant_orders', 'uq_restaurant_orders_diner_idempotency', ('tenant_id', 'diner_session_id', 'confirmation_idempotency_key'), 0)
_index('restaurant_orders', 'uq_restaurant_orders_id_tenant', ('id', 'tenant_id'), 0)
_index('restaurant_orders', 'ix_restaurant_orders_diner_history', ('tenant_id', 'diner_session_id', 'accepted_at', 'id'), 1)
_index('restaurant_orders', 'ix_restaurant_orders_service_history', ('tenant_id', 'service_session_id', 'accepted_at', 'id'), 1)
_index('restaurant_orders', 'ix_restaurant_orders_conversation_history', ('tenant_id', 'conversation_id', 'accepted_at', 'id'), 1)
_index('restaurant_orders', 'ix_restaurant_orders_location_staff', ('tenant_id', 'location_id', 'accepted_at', 'id'), 1)
_index('restaurant_orders', 'fk_restaurant_orders_service_scope', ('service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 1)
_index('restaurant_orders', 'fk_restaurant_orders_diner_scope', ('diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'), 1)
_index('restaurant_orders', 'fk_restaurant_orders_conversation_scope', ('conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 1)
_index('restaurant_orders', 'fk_restaurant_orders_customer_tenant', ('customer_id', 'tenant_id'), 1)
_index('restaurant_order_items', 'uq_restaurant_order_items_source', ('order_id', 'source_order_draft_item_id'), 0)
_index('restaurant_order_items', 'uq_restaurant_order_items_position', ('order_id', 'position'), 0)
_index('restaurant_order_items', 'uq_restaurant_order_items_scope', ('id', 'tenant_id', 'order_id'), 0)
_index('restaurant_order_items', 'ix_restaurant_order_items_ordered', ('tenant_id', 'order_id', 'position', 'id'), 1)
_index('restaurant_order_items', 'fk_restaurant_order_items_order_scope', ('order_id', 'tenant_id'), 1)
_index('restaurant_order_items', 'fk_restaurant_order_items_product_scope', ('product_id', 'tenant_id', 'organization_id'), 1)
_index('restaurant_order_items', 'fk_restaurant_order_items_source_draft_item', ('source_order_draft_item_id',), 1)
_index('restaurant_order_items', 'fk_restaurant_order_items_source_price', ('source_product_price_id',), 1)
_index('restaurant_order_items', 'fk_restaurant_order_items_source_composition', ('composition_id',), 1)
_index('restaurant_order_item_components', 'uq_restaurant_order_components_position', ('order_item_id', 'position'), 0)
_index('restaurant_order_item_components', 'ix_restaurant_order_components_ordered', ('tenant_id', 'order_id', 'order_item_id', 'position', 'id'), 1)
_index('restaurant_order_item_components', 'fk_restaurant_order_components_item_scope', ('order_item_id', 'tenant_id', 'order_id'), 1)
_index('restaurant_order_item_components', 'fk_restaurant_order_components_product_scope', ('product_id', 'tenant_id', 'organization_id'), 1)
_index('restaurant_order_item_components', 'fk_restaurant_order_components_source_component', ('source_component_id',), 1)
_index('restaurant_order_item_components', 'fk_restaurant_order_components_source_group', ('source_choice_group_id',), 1)
_index('restaurant_order_item_components', 'fk_restaurant_order_components_source_option', ('source_choice_option_id',), 1)
_index('restaurant_order_promotions', 'uq_restaurant_order_promotions_order', ('order_item_id', 'application_order'), 0)
_index('restaurant_order_promotions', 'ix_restaurant_order_promotions_ordered', ('tenant_id', 'order_id', 'order_item_id', 'application_order', 'id'), 1)
_index('restaurant_order_promotions', 'fk_restaurant_order_promotions_item_scope', ('order_item_id', 'tenant_id', 'order_id'), 1)
_index('restaurant_order_promotions', 'fk_restaurant_order_promotions_source_scope', ('promotion_id', 'tenant_id', 'organization_id'), 1)
_index('restaurant_orders', 'uq_restaurant_orders_pos_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('restaurant_order_item_components', 'uq_restaurant_order_components_scope', ('id', 'tenant_id', 'order_id', 'order_item_id'), 0)
_index('location_pos_connections', 'uq_location_pos_connections_active', ('location_id', 'active_slot'), 0)
_index('location_pos_connections', 'uq_location_pos_connections_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('location_pos_connections', 'ix_location_pos_connections_lookup', ('tenant_id', 'location_id', 'status', 'id'), 1)
_index('pos_order_submissions', 'uq_pos_order_submissions_materialization', ('tenant_id', 'restaurant_order_id', 'connector_key'), 0)
_index('pos_order_submissions', 'uq_pos_order_submissions_external_operation', ('tenant_id', 'connector_key', 'external_location_id', 'idempotency_key'), 0)
_index('pos_order_submissions', 'uq_pos_order_submissions_id_tenant', ('id', 'tenant_id'), 0)
_index('pos_order_submissions', 'uq_pos_order_submissions_scope', ('id', 'tenant_id', 'restaurant_order_id'), 0)
_index('pos_order_submissions', 'ix_pos_order_submissions_state_claim', ('tenant_id', 'state', 'claim_expires_at', 'id'), 1)
_index('pos_order_submissions', 'ix_pos_order_submissions_location', ('tenant_id', 'location_id', 'connector_key', 'id'), 1)
_index('pos_order_submissions', 'ix_pos_order_submissions_external', ('tenant_id', 'connector_key', 'external_order_id', 'id'), 1)
_index('pos_order_submission_lines', 'uq_pos_submission_lines_order_item', ('submission_id', 'restaurant_order_item_id'), 0)
_index('pos_order_submission_lines', 'uq_pos_submission_lines_external_ref', ('submission_id', 'external_line_reference'), 0)
_index('pos_order_submission_lines', 'uq_pos_submission_lines_scope', ('id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id'), 0)
_index('pos_order_submission_lines', 'ix_pos_submission_lines_ordered', ('tenant_id', 'submission_id', 'position', 'id'), 1)
_index('pos_order_submission_components', 'uq_pos_submission_components_source', ('submission_id', 'restaurant_order_item_component_id'), 0)
_index('pos_order_submission_components', 'ix_pos_submission_components_ordered', ('tenant_id', 'submission_line_id', 'position', 'id'), 1)
_index('pos_order_submission_attempts', 'uq_pos_submission_attempts_sequence', ('submission_id', 'attempt_sequence'), 0)
_index('pos_order_submission_attempts', 'uq_pos_submission_attempts_claim', ('claim_token',), 0)
_index('pos_order_submission_attempts', 'ix_pos_submission_attempts_ordered', ('tenant_id', 'submission_id', 'attempt_sequence', 'id'), 1)
_index('location_preparation_configurations', 'uq_location_preparation_configurations_location', ('location_id',), 0)
_index('location_preparation_configurations', 'uq_location_preparation_configurations_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('location_preparation_configurations', 'ix_location_preparation_configurations_lookup', ('tenant_id', 'location_id', 'id'), 1)
_index('preparation_areas', 'uq_preparation_areas_location_code', ('location_id', 'code'), 0)
_index('preparation_areas', 'uq_preparation_areas_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('preparation_areas', 'ix_preparation_areas_lookup', ('tenant_id', 'location_id', 'status', 'code', 'id'), 1)
_index('product_preparation_routes', 'uq_product_preparation_routes_current', ('location_id', 'product_id', 'active_slot'), 0)
_index('product_preparation_routes', 'uq_product_preparation_routes_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('product_preparation_routes', 'ix_product_preparation_routes_lookup', ('tenant_id', 'location_id', 'product_id', 'status', 'id'), 1)
_index('preparation_routings', 'uq_preparation_routings_order', ('tenant_id', 'restaurant_order_id'), 0)
_index('preparation_routings', 'uq_preparation_routings_scope', ('id', 'tenant_id', 'restaurant_order_id'), 0)
_index('preparation_routings', 'ix_preparation_routings_state', ('tenant_id', 'state', 'location_id', 'id'), 1)
_index('preparation_works', 'uq_preparation_works_order_area', ('tenant_id', 'restaurant_order_id', 'preparation_area_id'), 0)
_index('preparation_works', 'uq_preparation_works_scope', ('id', 'tenant_id', 'restaurant_order_id'), 0)
_index('preparation_works', 'ix_preparation_works_area', ('tenant_id', 'location_id', 'preparation_area_id', 'id'), 1)
_index('preparation_work_items', 'uq_preparation_work_items_source_item', ('tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_id'), 0)
_index('preparation_work_items', 'uq_preparation_work_items_source_component', ('tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_component_id'), 0)
_index('preparation_work_items', 'ix_preparation_work_items_ordered', ('tenant_id', 'preparation_work_id', 'id'), 1)
_index('preparation_work_items', 'uq_preparation_work_items_execution_scope', ('id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id'), 0)
_index('preparation_work_items', 'ix_preparation_work_items_queue', ('tenant_id', 'location_id', 'execution_state', 'preparation_work_id', 'id'), 1)
_index('preparation_item_transitions', 'uq_preparation_item_transitions_sequence', ('tenant_id', 'preparation_work_item_id', 'sequence'), 0)
_index('preparation_item_transitions', 'uq_preparation_item_transitions_idempotency', ('tenant_id', 'preparation_work_item_id', 'idempotency_key'), 0)
_index('preparation_item_transitions', 'ix_preparation_item_transitions_ordered', ('tenant_id', 'preparation_work_item_id', 'sequence', 'id'), 1)
_index('preparation_works', 'uq_preparation_works_dispatch_scope', ('id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_area_id'), 0)
_index('preparation_delivery_connectors', 'uq_preparation_delivery_connectors_location_code', ('location_id', 'code'), 0)
_index('preparation_delivery_connectors', 'uq_preparation_delivery_connectors_auth_subject', ('auth_subject',), 0)
_index('preparation_delivery_connectors', 'uq_preparation_delivery_connectors_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('preparation_delivery_connectors', 'ix_preparation_delivery_connectors_lookup', ('tenant_id', 'location_id', 'status', 'code', 'id'), 1)
_index('preparation_delivery_connector_enrollments', 'uq_connector_enrollments_public_id', ('enrollment_id',), 0)
_index('preparation_delivery_connector_enrollments', 'uq_connector_enrollments_active_slot', ('connector_id', 'active_slot'), 0)
_index('preparation_delivery_connector_enrollments', 'ix_connector_enrollments_lookup', ('enrollment_id', 'connector_id', 'expires_at'), 1)
_index('preparation_delivery_connector_credentials', 'uq_connector_credentials_client_id', ('client_id',), 0)
_index('preparation_delivery_connector_credentials', 'uq_connector_credentials_connector', ('id', 'connector_id'), 0)
_index('preparation_delivery_connector_credentials', 'ix_connector_credentials_auth', ('client_id', 'status', 'expires_at'), 1)
_index('preparation_delivery_connector_credentials', 'ix_connector_credentials_connector', ('tenant_id', 'connector_id', 'status', 'id'), 1)
_index('preparation_delivery_destinations', 'uq_preparation_delivery_destinations_location_code', ('location_id', 'code'), 0)
_index('preparation_delivery_destinations', 'uq_preparation_delivery_destinations_active_target', ('connector_id', 'local_target_key', 'active_slot'), 0)
_index('preparation_delivery_destinations', 'uq_preparation_delivery_destinations_scope', ('id', 'tenant_id', 'organization_id', 'location_id', 'preparation_area_id'), 0)
_index('preparation_delivery_destinations', 'ix_preparation_delivery_destinations_lookup', ('tenant_id', 'location_id', 'preparation_area_id', 'status', 'id'), 1)
_index('preparation_dispatches', 'uq_preparation_dispatches_generation', ('tenant_id', 'preparation_work_id', 'destination_id', 'generation'), 0)
_index('preparation_dispatches', 'uq_preparation_dispatches_operation', ('tenant_id', 'operation_id'), 0)
_index('preparation_dispatches', 'uq_preparation_dispatches_id_tenant', ('id', 'tenant_id'), 0)
_index('preparation_dispatches', 'uq_preparation_dispatches_reprint_scope', ('id', 'tenant_id', 'preparation_work_id', 'destination_id'), 0)
_index('preparation_dispatches', 'ix_preparation_dispatches_eligibility', ('tenant_id', 'location_id', 'state', 'available_at', 'id'), 1)
_index('preparation_dispatches', 'ix_preparation_dispatches_work', ('tenant_id', 'preparation_work_id', 'generation', 'id'), 1)
_index('preparation_dispatches', 'ix_preparation_dispatches_destination', ('tenant_id', 'destination_id', 'state', 'id'), 1)
_index('preparation_dispatches', 'ix_preparation_dispatches_connector_eligibility', ('tenant_id', 'connector_id_snapshot', 'state', 'available_at', 'id'), 1)
_index('preparation_dispatch_attempts', 'uq_preparation_dispatch_attempts_sequence', ('dispatch_id', 'attempt_sequence'), 0)
_index('preparation_dispatch_attempts', 'uq_preparation_dispatch_attempts_claim', ('claim_token',), 0)
_index('preparation_dispatch_attempts', 'uq_dispatch_attempts_claim_request', ('tenant_id', 'connector_id', 'claim_request_id'), 0)
_index('preparation_dispatch_attempts', 'ix_preparation_dispatch_attempts_ordered', ('tenant_id', 'dispatch_id', 'attempt_sequence', 'id'), 1)
_index('diner_sessions', 'uq_diner_sessions_check_controller_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('order_drafts', 'uq_order_drafts_abandon_idempotency', ('tenant_id', 'conversation_id', 'abandon_idempotency_key'), 0)
_index('restaurant_checks', 'uq_restaurant_checks_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0)
_index('restaurant_checks', 'uq_restaurant_checks_id_tenant', ('id', 'tenant_id'), 0)
_index('restaurant_checks', 'ix_restaurant_checks_location_status', ('tenant_id', 'location_id', 'status', 'id'), 1)
_index('restaurant_checks', 'fk_restaurant_checks_location_scope', ('location_id', 'tenant_id', 'organization_id'), 1)
_index('restaurant_checks', 'fk_restaurant_checks_controller_diner_scope', ('controller_diner_session_id', 'tenant_id', 'organization_id', 'location_id'), 1)
_index('restaurant_check_members', 'uq_check_members_check_diner', ('check_id', 'diner_session_id'), 0)
_index('restaurant_check_members', 'uq_check_members_diner_active', ('tenant_id', 'diner_session_id', 'active_slot'), 0)
_index('restaurant_check_members', 'ix_check_members_check_active', ('tenant_id', 'check_id', 'active_slot', 'diner_session_id'), 1)
_index('restaurant_check_members', 'fk_check_members_check_scope', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 1)
_index('restaurant_check_members', 'fk_check_members_diner_scope', ('diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'), 1)
_index('restaurant_check_allocations', 'uq_check_allocations_check_order', ('check_id', 'restaurant_order_id'), 0)
_index('restaurant_check_allocations', 'uq_check_allocations_order_owner', ('tenant_id', 'restaurant_order_id', 'ownership_slot'), 0)
_index('restaurant_check_allocations', 'ix_check_allocations_check_state', ('tenant_id', 'check_id', 'state', 'restaurant_order_id'), 1)
_index('restaurant_check_allocations', 'ix_check_allocations_service_balance', ('tenant_id', 'source_service_session_id', 'state', 'restaurant_order_id'), 1)
_index('restaurant_check_allocations', 'fk_check_allocations_check_scope', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 1)
_index('restaurant_check_allocations', 'fk_check_allocations_order_scope', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 1)
_index('restaurant_check_allocations', 'fk_check_allocations_diner_scope', ('source_diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'source_resource_id', 'source_service_session_id', 'source_conversation_id'), 1)
_index('restaurant_check_versions', 'uq_check_versions_check_version', ('check_id', 'version'), 0)
_index('restaurant_check_versions', 'uq_check_versions_check_fingerprint', ('check_id', 'fingerprint'), 0)
_index('restaurant_check_versions', 'fk_check_versions_check_scope', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 1)
_index('restaurant_check_gratuities', 'uq_check_gratuities_check_version', ('check_id', 'check_version'), 0)
_index('restaurant_check_gratuities', 'fk_check_gratuities_check_scope', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 1)
_index('restaurant_check_commands', 'uq_check_commands_idempotency', ('tenant_id', 'actor_scope', 'idempotency_key'), 0)
_index('restaurant_check_commands', 'fk_check_commands_check_tenant', ('check_id', 'tenant_id'), 1)

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
    ('fk_product_aliases_tenant', 'product_aliases', ('tenant_id',), 'tenants', ('id',)),
    ('fk_product_aliases_organization_tenant', 'product_aliases', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_product_aliases_product_tenant_org', 'product_aliases', ('product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
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
    ('fk_order_drafts_tenant', 'order_drafts', ('tenant_id',), 'tenants', ('id',)),
    ('fk_order_drafts_organization_tenant', 'order_drafts', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_order_drafts_location_tenant_org', 'order_drafts', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_order_drafts_conversation_scope', 'order_drafts', ('conversation_id', 'tenant_id', 'organization_id', 'location_id'), 'conversations', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_order_draft_items_tenant', 'order_draft_items', ('tenant_id',), 'tenants', ('id',)),
    ('fk_order_draft_items_draft_scope', 'order_draft_items', ('draft_id', 'tenant_id', 'organization_id'), 'order_drafts', ('id', 'tenant_id', 'organization_id')),
    ('fk_order_draft_items_product_scope', 'order_draft_items', ('product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_order_draft_items_composition_product', 'order_draft_items', ('composition_id', 'tenant_id', 'organization_id', 'product_id'), 'product_compositions', ('id', 'tenant_id', 'organization_id', 'product_id')),
    ('fk_order_draft_item_selections_tenant', 'order_draft_item_selections', ('tenant_id',), 'tenants', ('id',)),
    ('fk_order_draft_selections_item_scope', 'order_draft_item_selections', ('draft_item_id', 'tenant_id', 'organization_id', 'draft_id', 'composition_id'), 'order_draft_items', ('id', 'tenant_id', 'organization_id', 'draft_id', 'composition_id')),
    ('fk_order_draft_selections_group_scope', 'order_draft_item_selections', ('choice_group_id', 'tenant_id', 'organization_id', 'composition_id'), 'product_choice_groups', ('id', 'tenant_id', 'organization_id', 'composition_id')),
    ('fk_order_draft_selections_option_scope', 'order_draft_item_selections', ('choice_option_id', 'tenant_id', 'organization_id', 'choice_group_id'), 'product_choice_options', ('id', 'tenant_id', 'organization_id', 'group_id')),
    ('fk_restaurant_service_sessions_tenant', 'restaurant_service_sessions', ('tenant_id',), 'tenants', ('id',)),
    ('fk_restaurant_service_sessions_organization_tenant', 'restaurant_service_sessions', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_restaurant_service_sessions_location_scope', 'restaurant_service_sessions', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_restaurant_service_sessions_resource_scope', 'restaurant_service_sessions', ('resource_id', 'tenant_id', 'location_id'), 'resources', ('id', 'tenant_id', 'location_id')),
    ('fk_restaurant_service_sessions_opened_membership', 'restaurant_service_sessions', ('opened_by_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_restaurant_service_sessions_closed_membership', 'restaurant_service_sessions', ('closed_by_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_diner_sessions_tenant', 'diner_sessions', ('tenant_id',), 'tenants', ('id',)),
    ('fk_diner_sessions_service_scope', 'diner_sessions', ('service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 'restaurant_service_sessions', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id')),
    ('fk_diner_sessions_customer_tenant', 'diner_sessions', ('customer_id', 'tenant_id'), 'customers', ('id', 'tenant_id')),
    ('fk_diner_sessions_conversation_scope', 'diner_sessions', ('conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 'conversations', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id')),
    ('fk_diner_sessions_participant_scope', 'diner_sessions', ('conversation_participant_id', 'tenant_id', 'conversation_id'), 'conversation_participants', ('id', 'tenant_id', 'conversation_id')),
    ('fk_restaurant_orders_tenant', 'restaurant_orders', ('tenant_id',), 'tenants', ('id',)),
    ('fk_restaurant_orders_service_scope', 'restaurant_orders', ('service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 'restaurant_service_sessions', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id')),
    ('fk_restaurant_orders_diner_scope', 'restaurant_orders', ('diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'), 'diner_sessions', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id')),
    ('fk_restaurant_orders_conversation_scope', 'restaurant_orders', ('conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 'conversations', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id')),
    ('fk_restaurant_orders_draft_scope', 'restaurant_orders', ('source_order_draft_id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id'), 'order_drafts', ('id', 'tenant_id', 'organization_id', 'location_id', 'conversation_id')),
    ('fk_restaurant_orders_customer_tenant', 'restaurant_orders', ('customer_id', 'tenant_id'), 'customers', ('id', 'tenant_id')),
    ('fk_restaurant_order_items_order_scope', 'restaurant_order_items', ('order_id', 'tenant_id'), 'restaurant_orders', ('id', 'tenant_id')),
    ('fk_restaurant_order_items_product_scope', 'restaurant_order_items', ('product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_restaurant_order_items_source_draft_item', 'restaurant_order_items', ('source_order_draft_item_id',), 'order_draft_items', ('id',)),
    ('fk_restaurant_order_items_source_price', 'restaurant_order_items', ('source_product_price_id',), 'product_prices', ('id',)),
    ('fk_restaurant_order_items_source_composition', 'restaurant_order_items', ('composition_id',), 'product_compositions', ('id',)),
    ('fk_restaurant_order_components_item_scope', 'restaurant_order_item_components', ('order_item_id', 'tenant_id', 'order_id'), 'restaurant_order_items', ('id', 'tenant_id', 'order_id')),
    ('fk_restaurant_order_components_product_scope', 'restaurant_order_item_components', ('product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_restaurant_order_components_source_component', 'restaurant_order_item_components', ('source_component_id',), 'product_components', ('id',)),
    ('fk_restaurant_order_components_source_group', 'restaurant_order_item_components', ('source_choice_group_id',), 'product_choice_groups', ('id',)),
    ('fk_restaurant_order_components_source_option', 'restaurant_order_item_components', ('source_choice_option_id',), 'product_choice_options', ('id',)),
    ('fk_restaurant_order_promotions_item_scope', 'restaurant_order_promotions', ('order_item_id', 'tenant_id', 'order_id'), 'restaurant_order_items', ('id', 'tenant_id', 'order_id')),
    ('fk_restaurant_order_promotions_source_scope', 'restaurant_order_promotions', ('promotion_id', 'tenant_id', 'organization_id'), 'promotions', ('id', 'tenant_id', 'organization_id')),
    ('fk_location_pos_connections_tenant', 'location_pos_connections', ('tenant_id',), 'tenants', ('id',)),
    ('fk_location_pos_connections_location_scope', 'location_pos_connections', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_pos_order_submissions_tenant', 'pos_order_submissions', ('tenant_id',), 'tenants', ('id',)),
    ('fk_pos_order_submissions_order_scope', 'pos_order_submissions', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_orders', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_pos_order_submissions_connection_scope', 'pos_order_submissions', ('connection_id', 'tenant_id', 'organization_id', 'location_id'), 'location_pos_connections', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_pos_order_submissions_membership', 'pos_order_submissions', ('initiated_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_pos_submission_lines_submission_scope', 'pos_order_submission_lines', ('submission_id', 'tenant_id', 'restaurant_order_id'), 'pos_order_submissions', ('id', 'tenant_id', 'restaurant_order_id')),
    ('fk_pos_submission_lines_order_item_scope', 'pos_order_submission_lines', ('restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'), 'restaurant_order_items', ('id', 'tenant_id', 'order_id')),
    ('fk_pos_submission_components_line_scope', 'pos_order_submission_components', ('submission_line_id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id'), 'pos_order_submission_lines', ('id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id')),
    ('fk_pos_submission_components_component_scope', 'pos_order_submission_components', ('restaurant_order_item_component_id', 'tenant_id', 'restaurant_order_id', 'restaurant_order_item_id'), 'restaurant_order_item_components', ('id', 'tenant_id', 'order_id', 'order_item_id')),
    ('fk_pos_submission_attempts_submission_scope', 'pos_order_submission_attempts', ('submission_id', 'tenant_id'), 'pos_order_submissions', ('id', 'tenant_id')),
    ('fk_pos_submission_attempts_membership', 'pos_order_submission_attempts', ('actor_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_location_preparation_configurations_tenant', 'location_preparation_configurations', ('tenant_id',), 'tenants', ('id',)),
    ('fk_location_preparation_configurations_location_scope', 'location_preparation_configurations', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_preparation_areas_tenant', 'preparation_areas', ('tenant_id',), 'tenants', ('id',)),
    ('fk_preparation_areas_location_scope', 'preparation_areas', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_preparation_areas_resource_scope', 'preparation_areas', ('resource_id', 'tenant_id', 'location_id'), 'resources', ('id', 'tenant_id', 'location_id')),
    ('fk_product_preparation_routes_tenant', 'product_preparation_routes', ('tenant_id',), 'tenants', ('id',)),
    ('fk_product_preparation_routes_location_scope', 'product_preparation_routes', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_preparation_routes_product_scope', 'product_preparation_routes', ('product_id', 'tenant_id', 'organization_id'), 'products', ('id', 'tenant_id', 'organization_id')),
    ('fk_product_preparation_routes_area_scope', 'product_preparation_routes', ('preparation_area_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_areas', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_routings_tenant', 'preparation_routings', ('tenant_id',), 'tenants', ('id',)),
    ('fk_preparation_routings_order_scope', 'preparation_routings', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_orders', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_routings_membership', 'preparation_routings', ('initiating_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_preparation_works_tenant', 'preparation_works', ('tenant_id',), 'tenants', ('id',)),
    ('fk_preparation_works_routing_scope', 'preparation_works', ('routing_id', 'tenant_id', 'restaurant_order_id'), 'preparation_routings', ('id', 'tenant_id', 'restaurant_order_id')),
    ('fk_preparation_works_area_scope', 'preparation_works', ('preparation_area_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_areas', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_work_items_work_scope', 'preparation_work_items', ('preparation_work_id', 'tenant_id', 'restaurant_order_id'), 'preparation_works', ('id', 'tenant_id', 'restaurant_order_id')),
    ('fk_preparation_work_items_source_item_scope', 'preparation_work_items', ('source_restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'), 'restaurant_order_items', ('id', 'tenant_id', 'order_id')),
    ('fk_preparation_work_items_source_component_scope', 'preparation_work_items', ('source_restaurant_order_item_component_id', 'tenant_id', 'restaurant_order_id', 'source_restaurant_order_item_id_for_component'), 'restaurant_order_item_components', ('id', 'tenant_id', 'order_id', 'order_item_id')),
    ('fk_preparation_work_items_route_scope', 'preparation_work_items', ('route_id', 'tenant_id', 'organization_id', 'location_id'), 'product_preparation_routes', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_item_transitions_item_scope', 'preparation_item_transitions', ('preparation_work_item_id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id'), 'preparation_work_items', ('id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_work_id')),
    ('fk_preparation_item_transitions_membership', 'preparation_item_transitions', ('actor_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_preparation_delivery_connectors_tenant', 'preparation_delivery_connectors', ('tenant_id',), 'tenants', ('id',)),
    ('fk_preparation_delivery_connectors_location_scope', 'preparation_delivery_connectors', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_connector_enrollments_tenant', 'preparation_delivery_connector_enrollments', ('tenant_id',), 'tenants', ('id',)),
    ('fk_connector_enrollments_connector_scope', 'preparation_delivery_connector_enrollments', ('connector_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_delivery_connectors', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_connector_enrollments_membership', 'preparation_delivery_connector_enrollments', ('created_by_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_connector_credentials_tenant', 'preparation_delivery_connector_credentials', ('tenant_id',), 'tenants', ('id',)),
    ('fk_connector_credentials_connector_scope', 'preparation_delivery_connector_credentials', ('connector_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_delivery_connectors', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_connector_credentials_replacement', 'preparation_delivery_connector_credentials', ('replaces_credential_id', 'connector_id'), 'preparation_delivery_connector_credentials', ('id', 'connector_id')),
    ('fk_preparation_delivery_destinations_tenant', 'preparation_delivery_destinations', ('tenant_id',), 'tenants', ('id',)),
    ('fk_preparation_delivery_destinations_area_scope', 'preparation_delivery_destinations', ('preparation_area_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_areas', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_delivery_destinations_connector_scope', 'preparation_delivery_destinations', ('connector_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_delivery_connectors', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_dispatches_tenant', 'preparation_dispatches', ('tenant_id',), 'tenants', ('id',)),
    ('fk_preparation_dispatches_order_scope', 'preparation_dispatches', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_orders', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_dispatches_work_scope', 'preparation_dispatches', ('preparation_work_id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_area_id'), 'preparation_works', ('id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_area_id')),
    ('fk_preparation_dispatches_destination_scope', 'preparation_dispatches', ('destination_id', 'tenant_id', 'organization_id', 'location_id', 'preparation_area_id'), 'preparation_delivery_destinations', ('id', 'tenant_id', 'organization_id', 'location_id', 'preparation_area_id')),
    ('fk_preparation_dispatches_membership', 'preparation_dispatches', ('initiating_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
    ('fk_preparation_dispatches_reprint_origin', 'preparation_dispatches', ('reprint_of_dispatch_id', 'tenant_id', 'preparation_work_id', 'destination_id'), 'preparation_dispatches', ('id', 'tenant_id', 'preparation_work_id', 'destination_id')),
    ('fk_preparation_dispatch_attempts_dispatch_scope', 'preparation_dispatch_attempts', ('dispatch_id', 'tenant_id'), 'preparation_dispatches', ('id', 'tenant_id')),
    ('fk_preparation_dispatch_attempts_connector_scope', 'preparation_dispatch_attempts', ('connector_id', 'tenant_id', 'organization_id', 'location_id'), 'preparation_delivery_connectors', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_preparation_dispatch_attempts_membership', 'preparation_dispatch_attempts', ('actor_membership_id', 'tenant_id'), 'tenant_memberships', ('id', 'tenant_id')),
):
    EXPECTED_FOREIGN_KEY_COLUMNS.update(
        (constraint, table, local, target_table, target, position)
        for position, (local, target) in enumerate(zip(local_columns, target_columns), 1)
    )

for constraint, table, local_columns, target_table, target_columns in (
    ('fk_restaurant_checks_tenant', 'restaurant_checks', ('tenant_id',), 'tenants', ('id',)),
    ('fk_restaurant_checks_location_scope', 'restaurant_checks', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_restaurant_checks_controller_diner_scope', 'restaurant_checks', ('controller_diner_session_id', 'tenant_id', 'organization_id', 'location_id'), 'diner_sessions', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_members_check_scope', 'restaurant_check_members', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_members_diner_scope', 'restaurant_check_members', ('diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'), 'diner_sessions', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id')),
    ('fk_check_allocations_check_scope', 'restaurant_check_allocations', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_allocations_order_scope', 'restaurant_check_allocations', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_orders', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_allocations_diner_scope', 'restaurant_check_allocations', ('source_diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'source_resource_id', 'source_service_session_id', 'source_conversation_id'), 'diner_sessions', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id')),
    ('fk_check_versions_check_scope', 'restaurant_check_versions', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_gratuities_check_scope', 'restaurant_check_gratuities', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_commands_tenant', 'restaurant_check_commands', ('tenant_id',), 'tenants', ('id',)),
    ('fk_check_commands_check_tenant', 'restaurant_check_commands', ('check_id', 'tenant_id'), 'restaurant_checks', ('id', 'tenant_id')),
    ('fk_check_table_scopes_check_scope', 'restaurant_check_table_scopes', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_table_scopes_service_scope', 'restaurant_check_table_scopes', ('service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 'restaurant_service_sessions', ('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id')),
    ('fk_restaurant_payments_tenant', 'restaurant_payments', ('tenant_id',), 'tenants', ('id',)),
    ('fk_restaurant_payments_check_scope', 'restaurant_payments', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_restaurant_payments_payer_diner_scope', 'restaurant_payments', ('payer_diner_session_id', 'tenant_id', 'organization_id', 'location_id'), 'diner_sessions', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_payment_executor_configurations_tenant', 'location_payment_executor_configurations', ('tenant_id',), 'tenants', ('id',)),
    ('fk_payment_executor_configurations_location_scope', 'location_payment_executor_configurations', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_payment_executor_capabilities_configuration_scope', 'location_payment_executor_capabilities', ('executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'), 'location_payment_executor_configurations', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_restaurant_payments_executor_configuration_scope', 'restaurant_payments', ('executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'), 'location_payment_executor_configurations', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_restaurant_payment_attempts_payment_scope', 'restaurant_payment_attempts', ('payment_id', 'tenant_id'), 'restaurant_payments', ('id', 'tenant_id')),
    ('fk_check_settlements_check_scope', 'restaurant_check_settlements', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_check_settlements_payment_scope', 'restaurant_check_settlements', ('payment_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_payments', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_issuer_fiscal_profiles_tenant', 'issuer_fiscal_profiles', ('tenant_id',), 'tenants', ('id',)),
    ('fk_issuer_fiscal_profiles_organization_scope', 'issuer_fiscal_profiles', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_customer_fiscal_profiles_tenant', 'customer_fiscal_profiles', ('tenant_id',), 'tenants', ('id',)),
    ('fk_customer_fiscal_profiles_customer_scope', 'customer_fiscal_profiles', ('customer_id', 'tenant_id'), 'customers', ('id', 'tenant_id')),
    ('fk_billing_documents_tenant', 'billing_documents', ('tenant_id',), 'tenants', ('id',)),
    ('fk_billing_documents_organization_scope', 'billing_documents', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_billing_documents_location_scope', 'billing_documents', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_billing_documents_check_scope', 'billing_documents', ('restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_checks', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_billing_documents_check_version', 'billing_documents', ('restaurant_check_id', 'source_check_version'), 'restaurant_check_versions', ('check_id', 'version')),
    ('fk_billing_document_lines_document', 'billing_document_lines', ('billing_document_id',), 'billing_documents', ('id',)),
    ('fk_billing_document_lines_source_order', 'billing_document_lines', ('source_restaurant_order_id',), 'restaurant_orders', ('id',)),
    ('fk_billing_document_lines_source_order_item', 'billing_document_lines', ('source_restaurant_order_item_id',), 'restaurant_order_items', ('id',)),
    ('fk_billing_document_line_taxes_line', 'billing_document_line_taxes', ('billing_document_line_id',), 'billing_document_lines', ('id',)),
    ('fk_restaurant_tax_rules_tenant', 'restaurant_tax_rules', ('tenant_id',), 'tenants', ('id',)),
    ('fk_restaurant_tax_rules_organization_scope', 'restaurant_tax_rules', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_restaurant_tax_rules_location_scope', 'restaurant_tax_rules', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_order_item_tax_snapshots_tenant', 'restaurant_order_item_tax_snapshots', ('tenant_id',), 'tenants', ('id',)),
    ('fk_order_item_tax_snapshots_organization_scope', 'restaurant_order_item_tax_snapshots', ('organization_id', 'tenant_id'), 'organizations', ('id', 'tenant_id')),
    ('fk_order_item_tax_snapshots_location_scope', 'restaurant_order_item_tax_snapshots', ('location_id', 'tenant_id', 'organization_id'), 'locations', ('id', 'tenant_id', 'organization_id')),
    ('fk_order_item_tax_snapshots_order_scope', 'restaurant_order_item_tax_snapshots', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 'restaurant_orders', ('id', 'tenant_id', 'organization_id', 'location_id')),
    ('fk_order_item_tax_snapshots_item_scope', 'restaurant_order_item_tax_snapshots', ('restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'), 'restaurant_order_items', ('id', 'tenant_id', 'order_id')),
    ('fk_order_item_tax_snapshots_rule_scope', 'restaurant_order_item_tax_snapshots', ('source_tax_rule_id', 'tenant_id', 'organization_id'), 'restaurant_tax_rules', ('id', 'tenant_id', 'organization_id')),
):
    EXPECTED_FOREIGN_KEY_COLUMNS.update(
        (constraint, table, local, target_table, target, position)
        for position, (local, target) in enumerate(zip(local_columns, target_columns), 1)
    )

for table, name, columns, non_unique in (
    ('restaurant_check_table_scopes', 'uq_check_table_scopes_check_service', ('check_id', 'service_session_id'), 0),
    ('restaurant_check_table_scopes', 'uq_check_table_scopes_service_active', ('tenant_id', 'service_session_id', 'active_slot'), 0),
    ('restaurant_check_table_scopes', 'ix_check_table_scopes_check_active', ('tenant_id', 'check_id', 'active_slot', 'service_session_id'), 1),
    ('restaurant_check_table_scopes', 'fk_check_table_scopes_service_scope', ('service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'), 1),
    ('restaurant_payments', 'uq_restaurant_payments_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0),
    ('restaurant_payments', 'uq_restaurant_payments_id_tenant', ('id', 'tenant_id'), 0),
    ('restaurant_payments', 'uq_restaurant_payments_idempotency', ('tenant_id', 'actor_scope', 'idempotency_key'), 0),
    ('restaurant_payments', 'uq_restaurant_payments_configuration_external_reference', ('executor_configuration_id', 'external_reference'), 0),
    ('restaurant_payments', 'ix_restaurant_payments_check_state', ('tenant_id', 'check_id', 'state', 'id'), 1),
    ('restaurant_payments', 'ix_restaurant_payments_claim', ('tenant_id', 'state', 'claim_expires_at', 'id'), 1),
    ('restaurant_payments', 'ix_restaurant_payments_external', ('tenant_id', 'executor_key', 'external_reference', 'id'), 1),
    ('restaurant_payments', 'fk_restaurant_payments_check_scope', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('restaurant_payments', 'fk_restaurant_payments_payer_diner_scope', ('payer_diner_session_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('restaurant_payments', 'fk_restaurant_payments_executor_configuration_scope', ('executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('location_payment_executor_configurations', 'uq_payment_executor_configurations_scope', ('id', 'tenant_id', 'organization_id', 'location_id'), 0),
    ('location_payment_executor_configurations', 'uq_payment_executor_configurations_location_key', ('tenant_id', 'organization_id', 'location_id', 'executor_key'), 0),
    ('location_payment_executor_configurations', 'ix_payment_executor_configurations_lookup', ('tenant_id', 'organization_id', 'location_id', 'status', 'selection_priority', 'id'), 1),
    ('location_payment_executor_configurations', 'fk_payment_executor_configurations_location_scope', ('location_id', 'tenant_id', 'organization_id'), 1),
    ('location_payment_executor_capabilities', 'uq_payment_executor_capabilities_method_currency', ('executor_configuration_id', 'method_category', 'currency'), 0),
    ('location_payment_executor_capabilities', 'ix_payment_executor_capabilities_lookup', ('tenant_id', 'organization_id', 'location_id', 'method_category', 'currency', 'executor_configuration_id'), 1),
    ('location_payment_executor_capabilities', 'fk_payment_executor_capabilities_configuration_scope', ('executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('restaurant_payment_attempts', 'uq_restaurant_payment_attempts_sequence', ('payment_id', 'attempt_sequence'), 0),
    ('restaurant_payment_attempts', 'uq_restaurant_payment_attempts_claim', ('claim_token',), 0),
    ('restaurant_payment_attempts', 'ix_restaurant_payment_attempts_ordered', ('tenant_id', 'payment_id', 'attempt_sequence', 'id'), 1),
    ('restaurant_payment_attempts', 'fk_restaurant_payment_attempts_payment_scope', ('payment_id', 'tenant_id'), 1),
    ('restaurant_check_settlements', 'uq_check_settlements_payment', ('payment_id',), 0),
    ('restaurant_check_settlements', 'ix_check_settlements_check', ('tenant_id', 'check_id', 'applied_at', 'id'), 1),
    ('restaurant_check_settlements', 'fk_check_settlements_check_scope', ('check_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('restaurant_check_settlements', 'fk_check_settlements_payment_scope', ('payment_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('restaurant_tax_rules', 'uq_restaurant_tax_rules_scope', ('id', 'tenant_id', 'organization_id'), 0),
    ('restaurant_tax_rules', 'ix_restaurant_tax_rules_resolution', ('tenant_id', 'organization_id', 'location_id', 'tax_classification_code', 'status', 'effective_from', 'effective_to', 'id'), 1),
    ('restaurant_tax_rules', 'fk_restaurant_tax_rules_organization_scope', ('organization_id', 'tenant_id'), 1),
    ('restaurant_tax_rules', 'fk_restaurant_tax_rules_location_scope', ('location_id', 'tenant_id', 'organization_id'), 1),
    ('restaurant_order_item_tax_snapshots', 'ix_order_item_tax_snapshots_item', ('tenant_id', 'restaurant_order_id', 'restaurant_order_item_id', 'id'), 1),
    ('restaurant_order_item_tax_snapshots', 'fk_order_item_tax_snapshots_organization_scope', ('organization_id', 'tenant_id'), 1),
    ('restaurant_order_item_tax_snapshots', 'fk_order_item_tax_snapshots_location_scope', ('location_id', 'tenant_id', 'organization_id'), 1),
    ('restaurant_order_item_tax_snapshots', 'fk_order_item_tax_snapshots_order_scope', ('restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'), 1),
    ('restaurant_order_item_tax_snapshots', 'fk_order_item_tax_snapshots_item_scope', ('restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'), 1),
    ('restaurant_order_item_tax_snapshots', 'fk_order_item_tax_snapshots_rule_scope', ('source_tax_rule_id', 'tenant_id', 'organization_id'), 1),
):
    _index(table, name, columns, non_unique)

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


def _assert_database_contract(
    connection,
    expected_tables: set[str] = APPLICATION_TABLES,
) -> None:
    tables, foreign_keys, indexes = _database_contract(connection)

    expected_foreign_keys = {
        row
        for row in EXPECTED_FOREIGN_KEY_COLUMNS
        if row[1] in expected_tables
    }
    expected_indexes = {
        row
        for row in EXPECTED_INDEX_COLUMNS
        if row[0] in expected_tables
    }

    assert {row[0] for row in tables} == expected_tables
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}
    assert foreign_keys == expected_foreign_keys
    assert indexes == expected_indexes
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
                  AND CONSTRAINT_TYPE = 'CHECK'
                  AND CONSTRAINT_NAME NOT IN (
                      'member_snapshot', 'allocation_snapshot', 'gratuity_snapshot'
                  )
              AND TABLE_NAME IN (
                  'resources', 'customers', 'product_categories', 'products', 'menus',
                  'menu_locations', 'menu_sections', 'menu_items', 'product_prices',
                  'promotions', 'promotion_products', 'promotion_locations',
                  'conversations', 'conversation_participants', 'conversation_messages',
                  'intelligence_derivations', 'restaurant_message_intents',
                  'product_compositions', 'product_components',
                  'product_choice_groups', 'product_choice_options', 'product_aliases'
                  , 'order_drafts', 'order_draft_items', 'order_draft_item_selections'
                  , 'restaurant_service_sessions', 'diner_sessions'
                  , 'restaurant_orders', 'restaurant_order_items'
                  , 'restaurant_order_item_components', 'restaurant_order_promotions'
                  , 'location_pos_connections', 'pos_order_submissions'
                  , 'pos_order_submission_attempts'
                  , 'location_preparation_configurations', 'preparation_areas'
                  , 'product_preparation_routes', 'preparation_routings'
                  , 'preparation_works', 'preparation_work_items'
                  , 'preparation_item_transitions'
                  , 'preparation_delivery_connectors'
                  , 'preparation_delivery_connector_enrollments'
                  , 'preparation_delivery_connector_credentials'
                      , 'preparation_delivery_destinations'
                      , 'preparation_dispatches', 'preparation_dispatch_attempts'
                      , 'restaurant_checks', 'restaurant_check_members'
                      , 'restaurant_check_allocations', 'restaurant_check_versions'
                      , 'restaurant_check_gratuities', 'restaurant_check_commands'
                      , 'restaurant_check_table_scopes'
                      , 'restaurant_payments', 'restaurant_payment_attempts'
                      , 'restaurant_check_settlements'
                      , 'restaurant_tax_rules'
                      , 'restaurant_order_item_tax_snapshots'
                      , 'location_payment_executor_configurations'
                      , 'location_payment_executor_capabilities'
                  )
            '''
        )
        expected_domain_checks = {
            row
            for row in EXPECTED_DOMAIN_CHECKS
            if row[0] in expected_tables
        }
        assert {
            (row['TABLE_NAME'], row['CONSTRAINT_NAME'])
            for row in cursor.fetchall()
        } == expected_domain_checks
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
                  OR
                  (TABLE_NAME = 'product_aliases'
                   AND COLUMN_NAME IN ('normalized_alias', 'language'))
                  OR
                  (TABLE_NAME = 'restaurant_service_sessions'
                   AND COLUMN_NAME = 'join_context_key')
                  OR
                  (TABLE_NAME = 'restaurant_orders'
                   AND COLUMN_NAME IN ('confirmation_idempotency_key', 'commercial_fingerprint'))
                  OR
                  (TABLE_NAME = 'location_pos_connections'
                   AND COLUMN_NAME IN ('connector_key', 'external_location_id'))
                  OR
                  (TABLE_NAME = 'pos_order_submissions'
                   AND COLUMN_NAME IN ('connector_key', 'external_location_id', 'idempotency_key', 'request_fingerprint', 'external_order_id', 'claim_token'))
                  OR
                  (TABLE_NAME = 'pos_order_submission_lines'
                   AND COLUMN_NAME IN ('external_product_id', 'external_line_reference'))
                  OR
                  (TABLE_NAME = 'pos_order_submission_components'
                   AND COLUMN_NAME = 'external_product_id')
                  OR
                  (TABLE_NAME = 'pos_order_submission_attempts'
                   AND COLUMN_NAME IN ('claim_token', 'external_order_id'))
                  OR
                  (TABLE_NAME = 'preparation_areas'
                   AND COLUMN_NAME = 'code')
                  OR
                  (TABLE_NAME = 'preparation_routings'
                   AND COLUMN_NAME IN ('routing_fingerprint', 'error_code'))
                  OR
                  (TABLE_NAME = 'preparation_works'
                   AND COLUMN_NAME IN ('area_code_snapshot', 'routing_fingerprint'))
                  OR
                  (TABLE_NAME = 'preparation_item_transitions'
                   AND COLUMN_NAME = 'idempotency_key')
                  OR
                  (TABLE_NAME = 'preparation_delivery_connectors'
                   AND COLUMN_NAME IN ('code', 'auth_subject', 'connector_version', 'protocol_version'))
                  OR
                  (TABLE_NAME = 'preparation_delivery_connector_enrollments'
                   AND COLUMN_NAME IN ('enrollment_id', 'secret_digest'))
                  OR
                  (TABLE_NAME = 'preparation_delivery_connector_credentials'
                   AND COLUMN_NAME IN ('client_id', 'secret_digest'))
                  OR
                  (TABLE_NAME = 'preparation_delivery_destinations'
                   AND COLUMN_NAME IN ('code', 'local_target_key'))
                  OR
                  (TABLE_NAME = 'preparation_dispatches'
                   AND COLUMN_NAME IN (
                       'operation_id', 'payload_schema', 'payload_text',
                       'payload_fingerprint', 'destination_code_snapshot',
                       'connector_code_snapshot', 'local_target_key_snapshot',
                       'claim_token', 'last_error_kind'
                   ))
                  OR
                  (TABLE_NAME = 'preparation_dispatch_attempts'
                   AND COLUMN_NAME IN (
                       'claim_token', 'claim_request_id', 'result_fingerprint', 'local_job_reference',
                       'error_kind'
                   ))
                  OR
                  (TABLE_NAME = 'restaurant_checks'
                   AND COLUMN_NAME IN (
                       'current_fingerprint', 'controller_actor_reference',
                       'created_actor_reference', 'frozen_actor_reference',
                       'settled_actor_reference', 'continuation_actor_reference',
                       'cancelled_actor_reference'
                   ))
                  OR
                  (TABLE_NAME = 'restaurant_check_members'
                   AND COLUMN_NAME IN ('acquired_actor_reference', 'released_actor_reference'))
                  OR
                  (TABLE_NAME = 'restaurant_check_table_scopes'
                   AND COLUMN_NAME IN ('acquired_actor_reference', 'released_actor_reference'))
                  OR
                  (TABLE_NAME = 'restaurant_check_allocations'
                   AND COLUMN_NAME IN (
                       'accepted_commercial_fingerprint', 'claimed_actor_reference',
                       'released_actor_reference', 'settlement_reference'
                   ))
                  OR
                  (TABLE_NAME = 'restaurant_check_versions'
                   AND COLUMN_NAME IN ('fingerprint', 'actor_reference'))
                  OR
                  (TABLE_NAME = 'restaurant_check_gratuities'
                   AND COLUMN_NAME = 'actor_reference')
                  OR
                  (TABLE_NAME = 'restaurant_check_commands'
                   AND COLUMN_NAME IN ('actor_scope', 'idempotency_key', 'request_fingerprint'))
                  OR
                  (TABLE_NAME = 'restaurant_payments'
                   AND COLUMN_NAME IN (
                       'check_fingerprint', 'payer_reference', 'initiated_actor_reference',
                       'actor_scope', 'idempotency_key', 'request_fingerprint',
                       'executor_key', 'provider_idempotency_key', 'external_reference',
                       'claim_token'
                   ))
                  OR
                  (TABLE_NAME = 'location_payment_executor_configurations'
                   AND COLUMN_NAME IN ('executor_key', 'adapter_kind', 'credential_binding'))
                  OR
                  (TABLE_NAME = 'location_payment_executor_capabilities'
                   AND COLUMN_NAME = 'currency')
                  OR
                  (TABLE_NAME = 'restaurant_payment_attempts'
                   AND COLUMN_NAME IN (
                       'executor_key', 'claim_token', 'actor_reference',
                       'correlation_id', 'causation_id', 'external_reference',
                       'result_fingerprint'
                   ))
                  OR
                  (TABLE_NAME = 'restaurant_check_settlements'
                   AND COLUMN_NAME = 'application_actor_reference')
                  OR
                  (TABLE_NAME = 'products'
                   AND COLUMN_NAME = 'tax_classification_code')
                  OR
                  (TABLE_NAME = 'restaurant_tax_rules'
                   AND COLUMN_NAME IN (
                       'tax_classification_code', 'jurisdiction_code',
                       'calculation_policy', 'rounding_policy'
                   ))
                  OR
                  (TABLE_NAME = 'restaurant_order_item_tax_snapshots'
                   AND COLUMN_NAME IN (
                       'jurisdiction_code', 'calculation_policy',
                       'rounding_policy', 'evidence_fingerprint'
                   ))
              )
            '''
        )
        actual_collations = {
            (row['TABLE_NAME'], row['COLUMN_NAME'], row['COLLATION_NAME'])
            for row in cursor.fetchall()
        }
        expected_collations = {
            ('customer_external_identities', 'external_customer_id', 'utf8mb4_bin'),
            ('product_external_mappings', 'external_product_id', 'utf8mb4_bin'),
            ('product_aliases', 'normalized_alias', 'utf8mb4_bin'),
            ('product_aliases', 'language', 'utf8mb4_bin'),
            ('restaurant_service_sessions', 'join_context_key', 'utf8mb4_bin'),
            ('restaurant_orders', 'confirmation_idempotency_key', 'ascii_bin'),
            ('restaurant_orders', 'commercial_fingerprint', 'ascii_bin'),
            ('location_pos_connections', 'connector_key', 'utf8mb4_bin'),
            ('location_pos_connections', 'external_location_id', 'utf8mb4_bin'),
            ('pos_order_submissions', 'connector_key', 'utf8mb4_bin'),
            ('pos_order_submissions', 'external_location_id', 'utf8mb4_bin'),
            ('pos_order_submissions', 'idempotency_key', 'ascii_bin'),
            ('pos_order_submissions', 'request_fingerprint', 'ascii_bin'),
            ('pos_order_submissions', 'external_order_id', 'utf8mb4_bin'),
            ('pos_order_submissions', 'claim_token', 'ascii_bin'),
            ('pos_order_submission_lines', 'external_product_id', 'utf8mb4_bin'),
            ('pos_order_submission_lines', 'external_line_reference', 'utf8mb4_bin'),
            ('pos_order_submission_components', 'external_product_id', 'utf8mb4_bin'),
            ('pos_order_submission_attempts', 'claim_token', 'ascii_bin'),
            ('pos_order_submission_attempts', 'external_order_id', 'utf8mb4_bin'),
            ('preparation_areas', 'code', 'utf8mb4_bin'),
            ('preparation_routings', 'routing_fingerprint', 'ascii_bin'),
            ('preparation_routings', 'error_code', 'ascii_bin'),
            ('preparation_works', 'area_code_snapshot', 'utf8mb4_bin'),
            ('preparation_works', 'routing_fingerprint', 'ascii_bin'),
            ('preparation_item_transitions', 'idempotency_key', 'ascii_bin'),
            ('preparation_delivery_connectors', 'code', 'utf8mb4_bin'),
            ('preparation_delivery_connectors', 'auth_subject', 'ascii_bin'),
            ('preparation_delivery_connectors', 'connector_version', 'ascii_bin'),
            ('preparation_delivery_connectors', 'protocol_version', 'ascii_bin'),
            ('preparation_delivery_connector_enrollments', 'enrollment_id', 'ascii_bin'),
            ('preparation_delivery_connector_enrollments', 'secret_digest', 'ascii_bin'),
            ('preparation_delivery_connector_credentials', 'client_id', 'ascii_bin'),
            ('preparation_delivery_connector_credentials', 'secret_digest', 'ascii_bin'),
            ('preparation_delivery_destinations', 'code', 'utf8mb4_bin'),
            ('preparation_delivery_destinations', 'local_target_key', 'utf8mb4_bin'),
            ('preparation_dispatches', 'operation_id', 'ascii_bin'),
            ('preparation_dispatches', 'payload_schema', 'ascii_bin'),
            ('preparation_dispatches', 'payload_text', 'utf8mb4_bin'),
            ('preparation_dispatches', 'payload_fingerprint', 'ascii_bin'),
            ('preparation_dispatches', 'destination_code_snapshot', 'utf8mb4_bin'),
            ('preparation_dispatches', 'connector_code_snapshot', 'utf8mb4_bin'),
            ('preparation_dispatches', 'local_target_key_snapshot', 'utf8mb4_bin'),
            ('preparation_dispatches', 'claim_token', 'ascii_bin'),
            ('preparation_dispatches', 'last_error_kind', 'ascii_bin'),
            ('preparation_dispatch_attempts', 'claim_token', 'ascii_bin'),
            ('preparation_dispatch_attempts', 'claim_request_id', 'ascii_bin'),
            ('preparation_dispatch_attempts', 'result_fingerprint', 'ascii_bin'),
            ('preparation_dispatch_attempts', 'local_job_reference', 'utf8mb4_bin'),
            ('preparation_dispatch_attempts', 'error_kind', 'ascii_bin'),
            ('restaurant_checks', 'current_fingerprint', 'ascii_bin'),
            ('restaurant_checks', 'controller_actor_reference', 'utf8mb4_bin'),
            ('restaurant_checks', 'created_actor_reference', 'utf8mb4_bin'),
            ('restaurant_checks', 'frozen_actor_reference', 'utf8mb4_bin'),
            ('restaurant_checks', 'settled_actor_reference', 'utf8mb4_bin'),
            ('restaurant_checks', 'continuation_actor_reference', 'utf8mb4_bin'),
            ('restaurant_checks', 'cancelled_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_members', 'acquired_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_members', 'released_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_table_scopes', 'acquired_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_table_scopes', 'released_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_allocations', 'accepted_commercial_fingerprint', 'ascii_bin'),
            ('restaurant_check_allocations', 'claimed_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_allocations', 'released_actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_allocations', 'settlement_reference', 'ascii_bin'),
            ('restaurant_check_versions', 'fingerprint', 'ascii_bin'),
            ('restaurant_check_versions', 'actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_gratuities', 'actor_reference', 'utf8mb4_bin'),
            ('restaurant_check_commands', 'actor_scope', 'ascii_bin'),
            ('restaurant_check_commands', 'idempotency_key', 'ascii_bin'),
            ('restaurant_check_commands', 'request_fingerprint', 'ascii_bin'),
            ('restaurant_payments', 'check_fingerprint', 'ascii_bin'),
            ('restaurant_payments', 'payer_reference', 'utf8mb4_bin'),
            ('restaurant_payments', 'initiated_actor_reference', 'utf8mb4_bin'),
            ('restaurant_payments', 'actor_scope', 'ascii_bin'),
            ('restaurant_payments', 'idempotency_key', 'ascii_bin'),
            ('restaurant_payments', 'request_fingerprint', 'ascii_bin'),
            ('restaurant_payments', 'executor_key', 'utf8mb4_bin'),
            ('restaurant_payments', 'provider_idempotency_key', 'ascii_bin'),
            ('restaurant_payments', 'external_reference', 'utf8mb4_bin'),
            ('restaurant_payments', 'claim_token', 'ascii_bin'),
            ('location_payment_executor_configurations', 'executor_key', 'utf8mb4_bin'),
            ('location_payment_executor_configurations', 'adapter_kind', 'utf8mb4_bin'),
            ('location_payment_executor_configurations', 'credential_binding', 'utf8mb4_bin'),
            ('location_payment_executor_capabilities', 'currency', 'ascii_bin'),
            ('restaurant_payment_attempts', 'executor_key', 'utf8mb4_bin'),
            ('restaurant_payment_attempts', 'claim_token', 'ascii_bin'),
            ('restaurant_payment_attempts', 'actor_reference', 'utf8mb4_bin'),
            ('restaurant_payment_attempts', 'correlation_id', 'ascii_bin'),
            ('restaurant_payment_attempts', 'causation_id', 'ascii_bin'),
            ('restaurant_payment_attempts', 'external_reference', 'utf8mb4_bin'),
            ('restaurant_payment_attempts', 'result_fingerprint', 'ascii_bin'),
            ('restaurant_check_settlements', 'application_actor_reference', 'utf8mb4_bin'),
            ('products', 'tax_classification_code', 'utf8mb4_bin'),
            ('restaurant_tax_rules', 'tax_classification_code', 'utf8mb4_bin'),
            ('restaurant_tax_rules', 'jurisdiction_code', 'utf8mb4_bin'),
            ('restaurant_tax_rules', 'calculation_policy', 'utf8mb4_bin'),
            ('restaurant_tax_rules', 'rounding_policy', 'utf8mb4_bin'),
            ('restaurant_order_item_tax_snapshots', 'jurisdiction_code', 'utf8mb4_bin'),
            ('restaurant_order_item_tax_snapshots', 'calculation_policy', 'utf8mb4_bin'),
            ('restaurant_order_item_tax_snapshots', 'rounding_policy', 'utf8mb4_bin'),
            ('restaurant_order_item_tax_snapshots', 'evidence_fingerprint', 'ascii_bin'),
        }
        expected_collations = {
            row
            for row in expected_collations
            if row[0] in expected_tables
        }
        if expected_tables == APPLICATION_TABLES_0024:
            expected_collations.discard(
                ('products', 'tax_classification_code', 'utf8mb4_bin')
            )
        assert actual_collations == expected_collations


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


def _run_alembic_downgrade(database_name: str, revision: str) -> None:
    environment = os.environ.copy()
    environment['MYSQL_DATABASE'] = database_name
    environment['MYSQL_USER'] = 'root'
    environment['MYSQL_PASSWORD'] = environment['MYSQL_ROOT_PASSWORD']
    subprocess.run(
        ['alembic', 'downgrade', revision],
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


def test_authoritative_tax_evidence_metadata_contract() -> None:
    products = Base.metadata.tables['products']
    rules = Base.metadata.tables['restaurant_tax_rules']
    snapshots = Base.metadata.tables['restaurant_order_item_tax_snapshots']

    assert products.c.tax_classification_code.nullable
    assert set(rules.c.keys()) == {
        'id', 'tenant_id', 'organization_id', 'location_id',
        'tax_classification_code', 'jurisdiction_code', 'tax_category',
        'tax_treatment', 'tax_rate', 'calculation_policy', 'rounding_policy',
        'effective_from', 'effective_to', 'status', 'created_at', 'updated_at',
    }
    assert rules.c.location_id.nullable
    assert rules.c.effective_to.nullable
    assert isinstance(rules.c.tax_rate.type, Numeric)

    assert set(snapshots.c.keys()) == {
        'id', 'tenant_id', 'organization_id', 'location_id',
        'restaurant_order_id', 'restaurant_order_item_id', 'source_tax_rule_id',
        'tax_category', 'tax_treatment', 'tax_rate', 'taxable_base', 'tax_amount',
        'jurisdiction_code', 'calculation_policy', 'rounding_policy',
        'schema_version', 'evidence_fingerprint', 'created_at',
    }
    assert 'updated_at' not in snapshots.c
    assert all(
        constraint.ondelete == 'RESTRICT'
        for table in (rules, snapshots)
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    assert not any(
        'restaurant_order_item_id' in constraint.columns
        for constraint in snapshots.constraints
        if isinstance(constraint, UniqueConstraint)
    )


def test_database_tables_enforce_storage_contract(sql_connection) -> None:
    connection, _ = sql_connection
    tables, _, _ = _database_contract(connection)
    assert {row[0] for row in tables} == APPLICATION_TABLES
    assert {row[1] for row in tables} == {'InnoDB'}
    assert {row[2] for row in tables} == {'utf8mb4'}
    assert {row[3] for row in tables} == {'utf8mb4_unicode_ci'}


def test_database_has_all_expected_foreign_keys(sql_connection) -> None:
    connection, _ = sql_connection
    _assert_database_contract(connection)


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


def test_ws14_raw_scope_and_check_probes_are_rollback_only(sql_connection) -> None:
    connection, prefix = sql_connection
    connection.autocommit(False)
    connection.begin()
    try:
        with connection.cursor() as cursor:
            tenants = []
            for suffix in ('a', 'b'):
                cursor.execute(
                    "INSERT INTO tenants (name,slug,status) VALUES (%s,%s,'ACTIVE')",
                    (f'Draft Probe {suffix}', f'{prefix}-draft-{suffix}'),
                )
                tenants.append(int(cursor.lastrowid))
            tenant_a, tenant_b = tenants
            organizations = []
            for tenant_id, code in ((tenant_a, 'A'), (tenant_a, 'A2'), (tenant_b, 'B')):
                cursor.execute(
                    "INSERT INTO organizations (tenant_id,code,name,status) "
                    "VALUES (%s,%s,%s,'ACTIVE')",
                    (tenant_id, f'{code}-{uuid4().hex[:8]}', code),
                )
                organizations.append(int(cursor.lastrowid))
            org_a, org_a2, org_b = organizations
            locations = []
            for tenant_id, organization_id, code in (
                (tenant_a, org_a, 'A'),
                (tenant_a, org_a, 'A-OTHER'),
                (tenant_a, org_a2, 'A2'),
                (tenant_b, org_b, 'B'),
            ):
                cursor.execute(
                    "INSERT INTO locations "
                    "(tenant_id,organization_id,code,name,timezone,status) "
                    "VALUES (%s,%s,%s,%s,'America/Mexico_City','ACTIVE')",
                    (tenant_id, organization_id, f'{code}-{uuid4().hex[:8]}', code),
                )
                locations.append(int(cursor.lastrowid))
            location_a, location_a_other, location_a2, location_b = locations
            conversations = []
            for tenant_id, organization_id, location_id in (
                (tenant_a, org_a, location_a),
                (tenant_a, org_a, location_a_other),
                (tenant_b, org_b, location_b),
            ):
                cursor.execute(
                    "INSERT INTO conversations "
                    "(tenant_id,organization_id,location_id,channel,status,next_message_sequence) "
                    "VALUES (%s,%s,%s,'MOBILE_APP','ACTIVE',1)",
                    (tenant_id, organization_id, location_id),
                )
                conversations.append(int(cursor.lastrowid))
            conversation_a, conversation_a_other, conversation_b = conversations
            products = []
            for tenant_id, organization_id, name in (
                (tenant_a, org_a, 'Parent A'),
                (tenant_a, org_a, 'Option A'),
                (tenant_a, org_a, 'Parent Other'),
                (tenant_a, org_a, 'Option Other'),
                (tenant_a, org_a2, 'Product A2'),
                (tenant_b, org_b, 'Product B'),
            ):
                cursor.execute(
                    "INSERT INTO products (tenant_id,organization_id,name,status,source) "
                    "VALUES (%s,%s,%s,'ACTIVE','PLATFORM')",
                    (tenant_id, organization_id, name),
                )
                products.append(int(cursor.lastrowid))
            parent_a, option_a_product, parent_other, option_other_product, product_a2, product_b = products
            composition_ids = []
            for product_id in (parent_a, parent_other):
                cursor.execute(
                    "INSERT INTO product_compositions "
                    "(tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'ACTIVE')",
                    (tenant_a, org_a, product_id),
                )
                composition_ids.append(int(cursor.lastrowid))
            composition_a, composition_other = composition_ids
            groups = []
            for composition_id, name in ((composition_a, 'Group A'), (composition_other, 'Other')):
                cursor.execute(
                    "INSERT INTO product_choice_groups "
                    "(tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) "
                    "VALUES (%s,%s,%s,%s,0,1,0,'ACTIVE')",
                    (tenant_a, org_a, composition_id, name),
                )
                groups.append(int(cursor.lastrowid))
            group_a, group_other = groups
            options = []
            for group_id, product_id in ((group_a, option_a_product), (group_other, option_other_product)):
                cursor.execute(
                    "INSERT INTO product_choice_options "
                    "(tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) "
                    "VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
                    (tenant_a, org_a, group_id, product_id),
                )
                options.append(int(cursor.lastrowid))
            option_a, option_other = options
            cursor.execute(
                "INSERT INTO order_drafts "
                "(tenant_id,organization_id,location_id,conversation_id,version) "
                "VALUES (%s,%s,%s,%s,1)",
                (tenant_a, org_a, location_a, conversation_a),
            )
            draft_a = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO order_drafts "
                "(tenant_id,organization_id,location_id,conversation_id,version) "
                "VALUES (%s,%s,%s,%s,1)",
                (tenant_a, org_a, location_a_other, conversation_a_other),
            )
            draft_other = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO order_draft_items "
                "(tenant_id,organization_id,draft_id,product_id,composition_id,quantity,position) "
                "VALUES (%s,%s,%s,%s,%s,1,0)",
                (tenant_a, org_a, draft_a, parent_a, composition_a),
            )
            item_a = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO order_draft_item_selections "
                "(tenant_id,organization_id,draft_id,draft_item_id,composition_id,choice_group_id,choice_option_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (tenant_a, org_a, draft_a, item_a, composition_a, group_a, option_a),
            )

        probes = (
            (
                "INSERT INTO order_draft_item_selections (tenant_id,organization_id,draft_id,draft_item_id,composition_id,choice_group_id,choice_option_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (tenant_a, org_a, draft_a, item_a, composition_a, group_a, option_a),
            ),
            (
                "INSERT INTO order_drafts (tenant_id,organization_id,location_id,conversation_id,version) VALUES (%s,%s,%s,%s,1)",
                (tenant_a, org_a, location_a, conversation_b),
            ),
            (
                "INSERT INTO order_drafts (tenant_id,organization_id,location_id,conversation_id,version) VALUES (%s,%s,%s,%s,1)",
                (tenant_a, org_a2, location_a2, conversation_a),
            ),
            (
                "INSERT INTO order_drafts (tenant_id,organization_id,location_id,conversation_id,version) VALUES (%s,%s,%s,%s,1)",
                (tenant_a, org_a, location_a_other, conversation_a),
            ),
            (
                "INSERT INTO order_draft_items (tenant_id,organization_id,draft_id,product_id,quantity,position) VALUES (%s,%s,%s,%s,1,1)",
                (tenant_b, org_b, draft_a, product_b),
            ),
            (
                "INSERT INTO order_draft_items (tenant_id,organization_id,draft_id,product_id,quantity,position) VALUES (%s,%s,%s,%s,1,1)",
                (tenant_a, org_a, draft_a, product_a2),
            ),
            (
                "INSERT INTO order_draft_items (tenant_id,organization_id,draft_id,product_id,composition_id,quantity,position) VALUES (%s,%s,%s,%s,%s,1,1)",
                (tenant_a, org_a, draft_a, parent_a, composition_other),
            ),
            (
                "INSERT INTO order_draft_item_selections (tenant_id,organization_id,draft_id,draft_item_id,composition_id,choice_group_id,choice_option_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (tenant_a, org_a, draft_other, item_a, composition_a, group_a, option_a),
            ),
            (
                "INSERT INTO order_draft_item_selections (tenant_id,organization_id,draft_id,draft_item_id,composition_id,choice_group_id,choice_option_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (tenant_a, org_a, draft_a, item_a, composition_a, group_other, option_other),
            ),
            (
                "INSERT INTO order_draft_item_selections (tenant_id,organization_id,draft_id,draft_item_id,composition_id,choice_group_id,choice_option_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (tenant_a, org_a, draft_a, item_a, composition_a, group_a, option_other),
            ),
            (
                "INSERT INTO order_draft_items (tenant_id,organization_id,draft_id,product_id,quantity,position) VALUES (%s,%s,%s,%s,0,2)",
                (tenant_a, org_a, draft_a, parent_a),
            ),
            (
                "INSERT INTO order_draft_items (tenant_id,organization_id,draft_id,product_id,quantity,position) VALUES (%s,%s,%s,%s,1,-1)",
                (tenant_a, org_a, draft_a, parent_a),
            ),
            ('UPDATE order_drafts SET version=0 WHERE id=%s', (draft_a,)),
        )
        for statement, parameters in probes:
            with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
    finally:
        connection.rollback()
        connection.autocommit(True)

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM tenants WHERE slug LIKE %s',
            (f'{prefix}-draft-%',),
        )
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


def test_0017_upgrade_downgrade_and_reupgrade_preserve_permission_provenance(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0016_canonical_order_commercial_acceptance')
    _run_alembic(database_name, '0017_pos_order_submission_recovery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0017_pos_order_submission_recovery'
            cursor.execute("SELECT code FROM permissions WHERE code LIKE 'pos_submission.%' ORDER BY code")
            assert [row['code'] for row in cursor.fetchall()] == [
                'pos_submission.read',
                'pos_submission.recover',
                'pos_submission.retry',
                'pos_submission.submit',
            ]
    finally:
        connection.close()
    _run_alembic_downgrade(database_name, '0016_canonical_order_commercial_acceptance')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0016_canonical_order_commercial_acceptance'
            cursor.execute("SELECT COUNT(*) AS count FROM permissions WHERE code LIKE 'pos_submission.%'")
            assert cursor.fetchone()['count'] == 4
    finally:
        connection.close()
    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()


def test_0018_upgrade_downgrade_and_reupgrade_preserve_permission_provenance(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0017_pos_order_submission_recovery')
    _run_alembic(database_name, '0018_preparation_routing_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0018_preparation_routing_foundation'
            cursor.execute("SELECT code FROM permissions WHERE code LIKE 'preparation.%' ORDER BY code")
            assert [row['code'] for row in cursor.fetchall()] == [
                'preparation.configure',
                'preparation.read',
                'preparation.route',
            ]
            cursor.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='location_pos_connections' AND COLUMN_NAME='external_preparation_behavior'")
            assert cursor.fetchone() is not None
    finally:
        connection.close()
    _run_alembic_downgrade(database_name, '0017_pos_order_submission_recovery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0017_pos_order_submission_recovery'
            cursor.execute("SELECT COUNT(*) AS count FROM permissions WHERE code LIKE 'preparation.%'")
            assert cursor.fetchone()['count'] == 3
            cursor.execute("SELECT COUNT(*) AS count FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preparation_routings'")
            assert cursor.fetchone()['count'] == 0
    finally:
        connection.close()
    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()


def test_0019_backfills_existing_work_items_and_downgrade_reupgrade(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0018_preparation_routing_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            # Migration mechanics are isolated here: the row represents a valid pre-0019
            # work item while unrelated parent fixtures are intentionally omitted.
            cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            cursor.execute(
                "INSERT INTO preparation_work_items "
                '(id,tenant_id,organization_id,location_id,restaurant_order_id,'
                'preparation_work_id,source_restaurant_order_item_id,'
                'source_restaurant_order_item_component_id,'
                'source_restaurant_order_item_id_for_component,route_id,route_policy,'
                "required_quantity) VALUES (900001,800001,700001,600001,500001,400001,"
                "300001,NULL,NULL,200001,'AREA',1.0000)"
            )
            cursor.execute('SET FOREIGN_KEY_CHECKS=1')
    finally:
        connection.close()

    _run_alembic(database_name, '0019_preparation_execution_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0019_preparation_execution_foundation'
            cursor.execute('SELECT execution_state,execution_version FROM preparation_work_items WHERE id=900001')
            assert cursor.fetchone() == {'execution_state': 'NEW', 'execution_version': 0}
            cursor.execute('SELECT COUNT(*) AS count FROM preparation_item_transitions')
            assert cursor.fetchone()['count'] == 0
            cursor.execute("SELECT code FROM permissions WHERE code LIKE 'preparation.%' ORDER BY code")
            assert [row['code'] for row in cursor.fetchall()] == [
                'preparation.configure',
                'preparation.execute',
                'preparation.read',
                'preparation.route',
            ]
    finally:
        connection.close()

    _run_alembic_downgrade(database_name, '0018_preparation_routing_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0018_preparation_routing_foundation'
            cursor.execute("SELECT COUNT(*) AS count FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preparation_item_transitions'")
            assert cursor.fetchone()['count'] == 0
            cursor.execute("SELECT COUNT(*) AS count FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preparation_work_items' AND COLUMN_NAME IN ('execution_state','execution_version')")
            assert cursor.fetchone()['count'] == 0
            cursor.execute("SELECT COUNT(*) AS count FROM permissions WHERE code='preparation.execute'")
            assert cursor.fetchone()['count'] == 1
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT execution_state,execution_version FROM preparation_work_items WHERE id=900001')
            assert cursor.fetchone() == {'execution_state': 'NEW', 'execution_version': 0}
            cursor.execute('SELECT COUNT(*) AS count FROM preparation_item_transitions')
            assert cursor.fetchone()['count'] == 0
    finally:
        connection.close()


def test_0020_creates_dispatch_contract_without_backfill_and_preserves_permission(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0019_preparation_execution_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('WS21','ws21','ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO roles (tenant_id,name,description,status) "
                "VALUES (%s,'TENANT_ADMIN','Existing administrator','ACTIVE')",
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            cursor.execute(
                'INSERT INTO preparation_works '
                '(id,tenant_id,organization_id,location_id,restaurant_order_id,routing_id,'
                'preparation_area_id,preparation_owner,area_code_snapshot,area_name_snapshot,'
                'routing_schema_version,routing_fingerprint,routed_at) '
                "VALUES (910001,%s,920001,930001,940001,950001,960001,'PLATFORM',"
                "'COCINA','Cocina',1,%s,CURRENT_TIMESTAMP)",
                (tenant_id, 'a' * 64),
            )
            cursor.execute('SET FOREIGN_KEY_CHECKS=1')
    finally:
        connection.close()

    _run_alembic(database_name, '0020_preparation_dispatch_operational_delivery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0020_preparation_dispatch_operational_delivery'
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'preparation_dispatch%' "
                'ORDER BY TABLE_NAME'
            )
            assert {row['TABLE_NAME'] for row in cursor.fetchall()} == {
                'preparation_dispatch_attempts',
                'preparation_dispatches',
            }
            cursor.execute('SELECT COUNT(*) AS count FROM preparation_dispatches')
            assert cursor.fetchone()['count'] == 0
            cursor.execute(
                "SELECT COUNT(*) AS count FROM role_permissions AS RP "
                "JOIN permissions AS P ON P.id=RP.permission_id "
                "WHERE RP.role_id=%s AND P.code='preparation.dispatch'",
                (role_id,),
            )
            assert cursor.fetchone()['count'] == 1
    finally:
        connection.close()

    _run_alembic_downgrade(database_name, '0019_preparation_execution_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS count FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ("
                "'preparation_delivery_connectors','preparation_delivery_destinations',"
                "'preparation_dispatches','preparation_dispatch_attempts')"
            )
            assert cursor.fetchone()['count'] == 0
            cursor.execute(
                "SELECT COUNT(*) AS count FROM permissions WHERE code='preparation.dispatch'"
            )
            assert cursor.fetchone()['count'] == 1
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) AS count FROM preparation_dispatches')
            assert cursor.fetchone()['count'] == 0
    finally:
        connection.close()


def test_0021_upgrade_downgrade_reupgrade_preserves_unenrolled_connectors(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0020_preparation_dispatch_operational_delivery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO tenants(name,slug,status) VALUES('WS21C','ws21c','ACTIVE')")
            tenant_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO users(email,password_hash,display_name,status) VALUES('ws21c@example.test','hash','Admin','ACTIVE')")
            user_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO tenant_memberships(tenant_id,user_id,status) VALUES(%s,%s,'ACTIVE')", (tenant_id, user_id))
            membership_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO roles(tenant_id,name,description,status) VALUES(%s,'TENANT_ADMIN','Admin','ACTIVE')", (tenant_id,))
            role_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO organizations(tenant_id,code,name,status) VALUES(%s,'ORG','Org','ACTIVE')", (tenant_id,))
            organization_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO locations(tenant_id,organization_id,code,name,timezone,status) VALUES(%s,%s,'LOC','Location','America/Mexico_City','ACTIVE')", (tenant_id, organization_id))
            location_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO preparation_delivery_connectors(tenant_id,organization_id,location_id,code,name,auth_subject,status) VALUES(%s,%s,%s,'LOCAL','Local','preparation-connector:existing','ACTIVE')",
                (tenant_id, organization_id, location_id),
            )
            connector_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, '0021_restaurant_local_connector_machine_delivery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0021_restaurant_local_connector_machine_delivery'
            cursor.execute('SELECT last_seen_at,connector_version,protocol_version FROM preparation_delivery_connectors WHERE id=%s', (connector_id,))
            assert cursor.fetchone() == {'last_seen_at': None, 'connector_version': None, 'protocol_version': None}
            cursor.execute('SELECT COUNT(*) AS count FROM preparation_delivery_connector_enrollments')
            assert cursor.fetchone()['count'] == 0
            cursor.execute('SELECT COUNT(*) AS count FROM preparation_delivery_connector_credentials')
            assert cursor.fetchone()['count'] == 0
            cursor.execute("SELECT COUNT(*) AS count FROM role_permissions RP JOIN permissions P ON P.id=RP.permission_id WHERE RP.role_id=%s AND P.code='preparation.connector.manage'", (role_id,))
            assert cursor.fetchone()['count'] == 1
    finally:
        connection.close()

    _run_alembic_downgrade(database_name, '0020_preparation_dispatch_operational_delivery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0020_preparation_dispatch_operational_delivery'
            cursor.execute("SELECT COUNT(*) AS count FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('preparation_delivery_connector_enrollments','preparation_delivery_connector_credentials')")
            assert cursor.fetchone()['count'] == 0
            cursor.execute("SELECT COUNT(*) AS count FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='preparation_delivery_connectors' AND COLUMN_NAME='last_seen_at'")
            assert cursor.fetchone()['count'] == 0
    finally:
        connection.close()
    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()


def test_upgrade_from_0015_backfills_current_draft_and_grants_order_read(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0015_restaurant_service_diner_access_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO tenants (name,slug,status) VALUES ('WS17','upgrade-0015','ACTIVE')")
            tenant_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,'TENANT_ADMIN','Existing administrator','ACTIVE')", (tenant_id,))
            role_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'ORG','Organization','ACTIVE')", (tenant_id,))
            organization_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC','Location','UTC','ACTIVE')", (tenant_id, organization_id))
            location_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO conversations (tenant_id,organization_id,location_id,channel,status,next_message_sequence) VALUES (%s,%s,%s,'WEB_CHAT','ACTIVE',1)", (tenant_id, organization_id, location_id))
            conversation_id = int(cursor.lastrowid)
            cursor.execute('INSERT INTO order_drafts (tenant_id,organization_id,location_id,conversation_id,version) VALUES (%s,%s,%s,%s,3)', (tenant_id, organization_id, location_id, conversation_id))
            draft_id = int(cursor.lastrowid)
    finally:
        connection.close()
    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute('SELECT status,current_slot,terminal_at,version FROM order_drafts WHERE id=%s', (draft_id,))
            assert cursor.fetchone() == {'status': 'OPEN', 'current_slot': 1, 'terminal_at': None, 'version': 3}
            cursor.execute("SELECT COUNT(*) AS count FROM role_permissions RP JOIN permissions P ON P.id=RP.permission_id WHERE RP.role_id=%s AND P.code='restaurant_order.read'", (role_id,))
            assert cursor.fetchone()['count'] == 1
    finally:
        connection.close()


def test_0016_downgrade_refuses_multiple_drafts_per_conversation(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO tenants (name,slug,status) VALUES ('WS17','unsafe-downgrade','ACTIVE')")
            tenant_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'ORG','Organization','ACTIVE')", (tenant_id,))
            organization_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC','Location','UTC','ACTIVE')", (tenant_id, organization_id))
            location_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO conversations (tenant_id,organization_id,location_id,channel,status,next_message_sequence) VALUES (%s,%s,%s,'WEB_CHAT','ACTIVE',1)", (tenant_id, organization_id, location_id))
            conversation_id = int(cursor.lastrowid)
            for _ in range(2):
                cursor.execute("INSERT INTO order_drafts (tenant_id,organization_id,location_id,conversation_id,version,status,current_slot,terminal_at) VALUES (%s,%s,%s,%s,1,'ABANDONED',NULL,CURRENT_TIMESTAMP)", (tenant_id, organization_id, location_id, conversation_id))
    finally:
        connection.close()
    with pytest.raises(subprocess.CalledProcessError):
        _run_alembic_downgrade(database_name, '0015_restaurant_service_diner_access_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert cursor.fetchone()['version_num'] == '0016_canonical_order_commercial_acceptance'
    finally:
        connection.close()


def test_upgrade_from_0014_adds_restaurant_service_contract_and_grants_permissions(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0014_commercial_resolution_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO tenants (name,slug,status) VALUES ('WS16','upgrade-0014','ACTIVE')")
            tenant_id = int(cursor.lastrowid)
            cursor.execute("INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,'TENANT_ADMIN','Existing administrator','ACTIVE')", (tenant_id,))
            role_id = int(cursor.lastrowid)
    finally:
        connection.close()
    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT P.code,COUNT(*) AS assignment_count FROM role_permissions RP "
                "JOIN permissions P ON P.id=RP.permission_id WHERE RP.role_id=%s "
                "AND P.code IN ('restaurant_service.read','restaurant_service.manage') GROUP BY P.code",
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'restaurant_service.manage': 1,
                'restaurant_service.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0013_preserves_promotions_and_adds_commercial_policy(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0013_order_draft_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('WS15','upgrade-0013','ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO organizations (tenant_id,code,name,status) "
                "VALUES (%s,'ORG','Preserved Organization','ACTIVE')",
                (tenant_id,),
            )
            organization_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO promotions "
                "(tenant_id,organization_id,name,promotion_type,benefit_value,currency,"
                "starts_at,ends_at,applies_to_all_locations,status,source) "
                "VALUES (%s,%s,'Preserved','PERCENTAGE_DISCOUNT',10,NULL,"
                "'2026-01-01','2027-01-01',1,'INACTIVE','PLATFORM')",
                (tenant_id, organization_id),
            )
            promotion_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT is_combinable, priority FROM promotions WHERE id=%s',
                (promotion_id,),
            )
            assert cursor.fetchone() == {'is_combinable': 0, 'priority': 0}
            cursor.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='promotions' "
                "AND COLUMN_NAME IN ('is_combinable','priority')"
            )
            columns = {row['COLUMN_NAME']: row for row in cursor.fetchall()}
            assert columns['is_combinable']['DATA_TYPE'] == 'tinyint'
            assert columns['priority']['DATA_TYPE'] in {'int', 'integer'}
            assert {row['IS_NULLABLE'] for row in columns.values()} == {'NO'}
            assert {str(row['COLUMN_DEFAULT']) for row in columns.values()} == {'0'}
    finally:
        connection.close()


def test_upgrade_from_0012_reaches_order_draft_contract_and_grants_permissions(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0012_product_resolution_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('WS14','upgrade-0012','ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO roles (tenant_id,name,description,status) "
                "VALUES (%s,'TENANT_ADMIN','Existing administrator','ACTIVE')",
                (tenant_id,),
            )
            role_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO organizations (tenant_id,code,name,status) "
                "VALUES (%s,'ORG','Preserved Organization','ACTIVE')",
                (tenant_id,),
            )
            organization_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
                "VALUES (%s,%s,'LOC','Preserved Location','America/Mexico_City','ACTIVE')",
                (tenant_id, organization_id),
            )
            location_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO conversations "
                "(tenant_id,organization_id,location_id,channel,status,next_message_sequence) "
                "VALUES (%s,%s,%s,'MOBILE_APP','ACTIVE',1)",
                (tenant_id, organization_id, location_id),
            )
            conversation_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute('SELECT status FROM conversations WHERE id=%s', (conversation_id,))
            assert cursor.fetchone()['status'] == 'ACTIVE'
            cursor.execute(
                "INSERT INTO order_drafts "
                "(tenant_id,organization_id,location_id,conversation_id,version) "
                "VALUES (%s,%s,%s,%s,1)",
                (tenant_id, organization_id, location_id, conversation_id),
            )
            cursor.execute(
                '''
                SELECT P.code, COUNT(*) AS assignment_count
                FROM role_permissions AS RP
                JOIN permissions AS P ON P.id = RP.permission_id
                WHERE RP.role_id = %s
                  AND P.code IN ('order_draft.read', 'order_draft.manage')
                GROUP BY P.code
                ''',
                (role_id,),
            )
            assert {row['code']: row['assignment_count'] for row in cursor.fetchall()} == {
                'order_draft.manage': 1,
                'order_draft.read': 1,
            }
    finally:
        connection.close()


def test_upgrade_from_0011_reaches_product_resolution_contract(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    _run_alembic(database_name, '0011_product_structure_composition_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (name,slug,status) VALUES ('WS13','upgrade-0011','ACTIVE')"
            )
            tenant_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO organizations (tenant_id,code,name,status) "
                "VALUES (%s,'ORG','Organization','ACTIVE')",
                (tenant_id,),
            )
            organization_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO products (tenant_id,organization_id,name,status,source) "
                "VALUES (%s,%s,'Preserved Product','ACTIVE','PLATFORM')",
                (tenant_id, organization_id),
            )
            product_id = int(cursor.lastrowid)
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute('SELECT name FROM products WHERE id=%s', (product_id,))
            assert cursor.fetchone()['name'] == 'Preserved Product'
            cursor.execute(
                "INSERT INTO product_aliases "
                "(tenant_id,organization_id,product_id,alias,normalized_alias,language,status) "
                "VALUES (%s,%s,%s,'Alias','alias','','ACTIVE')",
                (tenant_id, organization_id, product_id),
            )
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


def test_0023_upgrade_downgrade_upgrade_preserves_single_portable_head(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    check_tables = {
        'restaurant_checks',
        'restaurant_check_members',
        'restaurant_check_allocations',
        'restaurant_check_versions',
        'restaurant_check_gratuities',
        'restaurant_check_commands',
    }
    payment_tables = {
        'restaurant_check_table_scopes',
        'restaurant_payments',
        'restaurant_payment_attempts',
        'restaurant_check_settlements',
    }

    _run_alembic(database_name, '0021_restaurant_local_connector_machine_delivery')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT TABLE_NAME FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE %s',
                ('restaurant_check%',),
            )
            assert {row['TABLE_NAME'] for row in cursor.fetchall()} == set()
    finally:
        connection.close()

    _run_alembic(database_name, '0022_restaurant_check_settlement_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT TABLE_NAME FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s,%s,%s)',
                tuple(sorted(payment_tables)),
            )
            assert {row['TABLE_NAME'] for row in cursor.fetchall()} == set()
            cursor.execute('SELECT version_num FROM alembic_version')
            assert [row['version_num'] for row in cursor.fetchall()] == [
                '0022_restaurant_check_settlement_foundation'
            ]
    finally:
        connection.close()

    _run_alembic(database_name, '0023_restaurant_payment_settlement_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT TABLE_NAME FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s,%s,%s)',
                tuple(sorted(payment_tables)),
            )
            assert {row['TABLE_NAME'] for row in cursor.fetchall()} == payment_tables
            cursor.execute('SELECT version_num FROM alembic_version')
            assert [row['version_num'] for row in cursor.fetchall()] == [
                '0023_restaurant_payment_settlement_foundation'
            ]
    finally:
        connection.close()

    _run_alembic_downgrade(database_name, '0022_restaurant_check_settlement_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() '
                'AND (TABLE_NAME IN (%s,%s,%s,%s,%s,%s) OR TABLE_NAME IN (%s,%s,%s,%s))',
                tuple(sorted(check_tables)) + tuple(sorted(payment_tables)),
            )
            assert {row['TABLE_NAME'] for row in cursor.fetchall()} == check_tables
            cursor.execute(
                'SELECT COLUMN_NAME FROM information_schema.COLUMNS '
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='restaurant_checks' "
                "AND COLUMN_NAME LIKE 'settled_%'",
            )
            assert {row['COLUMN_NAME'] for row in cursor.fetchall()} == set()
    finally:
        connection.close()

    _run_alembic(database_name, '0023_restaurant_payment_settlement_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert [row['version_num'] for row in cursor.fetchall()] == [
                '0023_restaurant_payment_settlement_foundation'
            ]
    finally:
        connection.close()

    _run_alembic(database_name, 'head')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(connection)
    finally:
        connection.close()


def test_0024_upgrade_from_0023_establishes_payment_executor_foundation(
    isolated_database,
    integration_settings: Settings,
) -> None:
    database_name, _ = isolated_database
    executor_tables = {
        'location_payment_executor_configurations',
        'location_payment_executor_capabilities',
    }

    _run_alembic(database_name, '0023_restaurant_payment_settlement_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT TABLE_NAME FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s,%s)',
                tuple(sorted(executor_tables)),
            )
            assert {row['TABLE_NAME'] for row in cursor.fetchall()} == set()
            cursor.execute(
                'SELECT COLUMN_NAME FROM information_schema.COLUMNS '
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='restaurant_payments' "
                "AND COLUMN_NAME='executor_configuration_id'"
            )
            assert cursor.fetchall() == ()
    finally:
        connection.close()

    _run_alembic(database_name, '0024_payment_executor_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(
            connection,
            expected_tables=APPLICATION_TABLES_0024,
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert [row['version_num'] for row in cursor.fetchall()] == [
                '0024_payment_executor_foundation'
            ]
    finally:
        connection.close()

    _run_alembic_downgrade(database_name, '0023_restaurant_payment_settlement_foundation')
    _run_alembic(database_name, '0024_payment_executor_foundation')
    connection = _connect_isolated_database(integration_settings, database_name)
    try:
        _assert_database_contract(
            connection,
            expected_tables=APPLICATION_TABLES_0024,
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT version_num FROM alembic_version')
            assert [row['version_num'] for row in cursor.fetchall()] == [
                '0024_payment_executor_foundation'
            ]
    finally:
        connection.close()
