"""Immutable structural contract for the Product-approved Stage 0 workbook."""

from __future__ import annotations

from dataclasses import dataclass

from app.onboarding.contract import CONTRACT_VERSION


OFFICIAL_PROFILE = "official-35-sheet"
OFFICIAL_MAX_CAPTURE_ROWS = 60
CAPTURE_STATUSES = (
    "PENDIENTE", "CAPTURADO", "POR CONFIRMAR", "CONFIRMADO", "NO APLICA",
)


@dataclass(frozen=True, slots=True)
class OfficialSheet:
    name: str
    key: str
    headers: tuple[str, ...]
    business_key: tuple[str, ...]
    required: tuple[str, ...]
    references: tuple[tuple[str, str, str], ...] = ()
    integer_fields: tuple[str, ...] = ()
    decimal_fields: tuple[str, ...] = ()
    allowed: tuple[tuple[str, tuple[str, ...]], ...] = ()
    owner: str = ""
    design_import_status: str = "UNSUPPORTED"
    dependencies: tuple[str, ...] = ()
    limitation: str | None = None


STATUS = ("ACTIVE", "INACTIVE")
YES_NO = ("YES", "NO")
UOM = ("KG", "G", "L", "ML", "UNIT", "PORTION")
CAPTURE = ("capture_status", CAPTURE_STATUSES)


def _sheet(
    name: str,
    key: str,
    headers: tuple[str, ...],
    business_key: tuple[str, ...],
    required: tuple[str, ...],
    *,
    references: tuple[tuple[str, str, str], ...] = (),
    integer_fields: tuple[str, ...] = (),
    decimal_fields: tuple[str, ...] = (),
    allowed: tuple[tuple[str, tuple[str, ...]], ...] = (),
    owner: str,
    design_import_status: str,
    dependencies: tuple[str, ...] = (),
    limitation: str | None = None,
) -> OfficialSheet:
    return OfficialSheet(
        name, key, headers, business_key, required, references, integer_fields,
        decimal_fields, (*allowed, CAPTURE), owner, design_import_status,
        dependencies, limitation,
    )


OFFICIAL_SHEETS: tuple[OfficialSheet, ...] = (
    _sheet("Organizations", "organizations", ("organization_code", "legal_name", "commercial_name", "status", "capture_status", "notes"), ("organization_code",), ("organization_code", "legal_name", "commercial_name", "status", "capture_status"), allowed=(("status", STATUS),), owner="P02 Organization", design_import_status="SUPPORTED"),
    _sheet("Locations", "locations", ("organization_code", "location_code", "name", "is_headquarters", "status", "native_language", "timezone", "address", "postal_code", "phone", "capture_status", "notes"), ("organization_code", "location_code"), ("organization_code", "location_code", "name", "is_headquarters", "status", "timezone", "capture_status"), references=(("organization_code", "Organizations", "organization_code"),), allowed=(("is_headquarters", YES_NO), ("status", STATUS)), owner="P02 Location/headquarters", design_import_status="SUPPORTED", dependencies=("Organizations",)),
    _sheet("Staff", "staff", ("staff_username", "display_name", "email_optional", "status", "capture_status", "notes"), ("staff_username",), ("staff_username", "display_name", "status", "capture_status"), allowed=(("status", STATUS),), owner="P01 Identity", design_import_status="PARTIAL", limitation="New identities without email remain partial"),
    _sheet("Staff_Location_Roles", "staff_location_roles", ("staff_username", "location_code", "role_key", "status", "capture_status", "notes"), ("staff_username", "location_code", "role_key"), ("staff_username", "location_code", "role_key", "status", "capture_status"), references=(("staff_username", "Staff", "staff_username"), ("location_code", "Locations", "location_code")), allowed=(("status", STATUS),), owner="P01 Location access", design_import_status="SUPPORTED", dependencies=("Staff", "Locations")),
    _sheet("Resources", "resources", ("location_code", "resource_code", "name", "resource_type", "area_or_zone", "capacity", "status", "capture_status", "notes"), ("location_code", "resource_code"), ("location_code", "resource_code", "name", "resource_type", "status", "capture_status"), references=(("location_code", "Locations", "location_code"),), integer_fields=("capacity",), allowed=(("resource_type", ("AREA", "TABLE", "WORKSTATION", "EQUIPMENT", "VEHICLE", "DEVICE", "CASH_REGISTER")), ("status", STATUS)), owner="Resource", design_import_status="SUPPORTED", dependencies=("Locations",)),
    _sheet("Cash_Registers", "cash_registers", ("location_code", "register_code", "name", "resource_code", "cash_enabled", "status", "capture_status", "notes"), ("location_code", "register_code"), ("location_code", "register_code", "name", "cash_enabled", "status", "capture_status"), references=(("location_code", "Locations", "location_code"), ("resource_code", "Resources", "resource_code")), allowed=(("cash_enabled", YES_NO), ("status", STATUS)), owner="Resource/Cash", design_import_status="PARTIAL", dependencies=("Locations", "Resources"), limitation="Cash policy is not an onboarding catalog import"),
    _sheet("Prep_Areas", "prep_areas", ("location_code", "area_code", "name", "printer_code", "status", "capture_status", "notes"), ("location_code", "area_code"), ("location_code", "area_code", "name", "status", "capture_status"), references=(("location_code", "Locations", "location_code"), ("printer_code", "Printers_Devices", "device_code")), allowed=(("status", STATUS),), owner="Preparation", design_import_status="PARTIAL", dependencies=("Locations",), limitation="Printer linkage is not supported"),
    _sheet("Printers_Devices", "printers_devices", ("location_code", "device_code", "name", "resource_type", "purpose", "connection", "status", "capture_status", "notes"), ("location_code", "device_code"), ("location_code", "device_code", "name", "resource_type", "status", "capture_status"), references=(("location_code", "Locations", "location_code"),), allowed=(("resource_type", ("AREA", "TABLE", "WORKSTATION", "EQUIPMENT", "VEHICLE", "DEVICE", "CASH_REGISTER")), ("status", STATUS)), owner="Resource/Preparation", design_import_status="PARTIAL", dependencies=("Locations",), limitation="Device identity only; connection/printing is deferred"),
    _sheet("Categories", "categories", ("category_code", "name", "parent_category_code", "status", "capture_status", "notes"), ("category_code",), ("category_code", "name", "status", "capture_status"), references=(("parent_category_code", "Categories", "category_code"),), allowed=(("status", STATUS),), owner="Catalog", design_import_status="SUPPORTED"),
    _sheet("Products", "products", ("product_code", "category_code", "name", "description", "sale_uom", "status", "capture_status", "notes"), ("product_code",), ("product_code", "name", "sale_uom", "status", "capture_status"), references=(("category_code", "Categories", "category_code"),), allowed=(("sale_uom", UOM), ("status", STATUS)), owner="Catalog", design_import_status="SUPPORTED", dependencies=("Categories",)),
    _sheet("Menus", "menus", ("location_code", "menu_code", "name", "status", "capture_status", "notes"), ("location_code", "menu_code"), ("location_code", "menu_code", "name", "status", "capture_status"), references=(("location_code", "Locations", "location_code"),), allowed=(("status", STATUS),), owner="Menu", design_import_status="SUPPORTED", dependencies=("Locations",)),
    _sheet("Menu_Sections", "menu_sections", ("menu_code", "section_code", "name", "display_order", "status", "capture_status", "notes"), ("menu_code", "section_code"), ("menu_code", "section_code", "name", "display_order", "status", "capture_status"), references=(("menu_code", "Menus", "menu_code"),), integer_fields=("display_order",), allowed=(("status", STATUS),), owner="Menu", design_import_status="SUPPORTED", dependencies=("Menus",)),
    _sheet("Menu_Items", "menu_items", ("menu_code", "section_code", "item_code", "product_code", "display_order", "status", "capture_status", "notes"), ("menu_code", "item_code"), ("menu_code", "section_code", "item_code", "product_code", "display_order", "status", "capture_status"), references=(("menu_code", "Menus", "menu_code"), ("section_code", "Menu_Sections", "section_code"), ("product_code", "Products", "product_code")), integer_fields=("display_order",), allowed=(("status", STATUS),), owner="Menu", design_import_status="SUPPORTED", dependencies=("Menus", "Menu_Sections", "Products")),
    _sheet("Prices", "prices", ("location_code", "item_code", "amount_mxn", "valid_from", "valid_to", "status", "capture_status", "notes"), ("location_code", "item_code", "valid_from"), ("location_code", "item_code", "amount_mxn", "status", "capture_status"), references=(("location_code", "Locations", "location_code"), ("item_code", "Menu_Items", "item_code")), decimal_fields=("amount_mxn",), allowed=(("status", STATUS),), owner="Pricing", design_import_status="PARTIAL", dependencies=("Locations", "Menu_Items"), limitation="Exact validity-window mapping is not available"),
    _sheet("Modifier_Groups", "modifier_groups", ("group_code", "name", "optionality", "min_select", "max_select", "status", "capture_status", "notes"), ("group_code",), ("group_code", "name", "optionality", "min_select", "max_select", "status", "capture_status"), integer_fields=("min_select", "max_select"), allowed=(("optionality", ("OPTIONAL", "REQUIRED")), ("status", STATUS)), owner="Product structure", design_import_status="UNSUPPORTED", limitation="Onboarding authority is absent"),
    _sheet("Modifier_Options", "modifier_options", ("group_code", "option_code", "name", "product_code", "price_adjustment_mxn", "status", "capture_status", "notes"), ("group_code", "option_code"), ("group_code", "option_code", "name", "status", "capture_status"), references=(("group_code", "Modifier_Groups", "group_code"), ("product_code", "Products", "product_code")), decimal_fields=("price_adjustment_mxn",), allowed=(("status", STATUS),), owner="Product structure", design_import_status="UNSUPPORTED", dependencies=("Modifier_Groups",), limitation="Onboarding authority is absent"),
    _sheet("Packages_Combos", "packages_combos", ("offer_code", "name", "component_group", "component_code", "quantity", "selection_rule", "price_mxn", "status", "capture_status", "notes"), ("offer_code", "component_group", "component_code"), ("offer_code", "name", "component_code", "quantity", "status", "capture_status"), decimal_fields=("quantity", "price_mxn"), allowed=(("status", STATUS),), owner="Offers", design_import_status="UNSUPPORTED", limitation="Complete official-schema authority is unavailable"),
    _sheet("Buffets", "buffets", ("buffet_code", "name", "meal_period", "price_mxn", "status", "capture_status", "notes"), ("buffet_code",), ("buffet_code", "name", "price_mxn", "status", "capture_status"), decimal_fields=("price_mxn",), allowed=(("status", STATUS),), owner="Offers", design_import_status="UNSUPPORTED", limitation="Persistence authority is unavailable"),
    _sheet("Buffet_Items", "buffet_items", ("buffet_code", "product_or_group_code", "quantity_or_rule", "prep_area_code", "capture_status", "notes"), ("buffet_code", "product_or_group_code"), ("buffet_code", "product_or_group_code", "capture_status"), references=(("buffet_code", "Buffets", "buffet_code"),), owner="Offers", design_import_status="UNSUPPORTED", dependencies=("Buffets",), limitation="Persistence authority is unavailable"),
    _sheet("Fixed_Meals", "fixed_meals", ("offer_code", "name", "day_or_period", "course_group", "options_rule", "price_mxn", "status", "capture_status", "notes"), ("offer_code", "course_group"), ("offer_code", "name", "course_group", "status", "capture_status"), decimal_fields=("price_mxn",), allowed=(("status", STATUS),), owner="Offers", design_import_status="UNSUPPORTED", limitation="Persistence authority is unavailable"),
    _sheet("Promotions", "promotions", ("promotion_code", "name", "promotion_type", "valid_from", "valid_to", "scope", "condition", "status", "capture_status", "notes"), ("promotion_code",), ("promotion_code", "name", "promotion_type", "valid_from", "valid_to", "scope", "status", "capture_status"), allowed=(("promotion_type", ("PERCENTAGE_DISCOUNT", "FIXED_AMOUNT_DISCOUNT")), ("status", STATUS)), owner="Pricing", design_import_status="UNSUPPORTED", limitation="Official mapping is incomplete"),
    _sheet("Warehouses", "warehouses", ("location_code", "warehouse_code", "name", "status", "capture_status", "notes"), ("location_code", "warehouse_code"), ("location_code", "warehouse_code", "name", "status", "capture_status"), references=(("location_code", "Locations", "location_code"),), allowed=(("status", STATUS),), owner="Inventory", design_import_status="SUPPORTED", dependencies=("Locations",)),
    _sheet("Inventory_Items", "inventory_items", ("inventory_code", "name", "base_uom", "date_control", "warehouse_code", "status", "capture_status", "notes"), ("inventory_code",), ("inventory_code", "name", "base_uom", "date_control", "warehouse_code", "status", "capture_status"), references=(("warehouse_code", "Warehouses", "warehouse_code"),), allowed=(("base_uom", UOM), ("date_control", ("NONE", "EXPIRY", "BEST_BEFORE", "BOTH")), ("status", STATUS)), owner="Inventory", design_import_status="SUPPORTED", dependencies=("Warehouses",)),
    _sheet("UOM_Conversions", "uom_conversions", ("inventory_code", "from_uom", "to_uom", "factor", "capture_status", "notes"), ("inventory_code", "from_uom", "to_uom"), ("inventory_code", "from_uom", "to_uom", "factor", "capture_status"), references=(("inventory_code", "Inventory_Items", "inventory_code"),), decimal_fields=("factor",), allowed=(("from_uom", UOM), ("to_uom", UOM)), owner="Inventory", design_import_status="SUPPORTED", dependencies=("Inventory_Items",)),
    _sheet("Suppliers", "suppliers", ("supplier_code", "name", "contact_name", "phone", "email", "status", "capture_status", "notes"), ("supplier_code",), ("supplier_code", "name", "status", "capture_status"), allowed=(("status", STATUS),), owner="Purchasing", design_import_status="SUPPORTED"),
    _sheet("Supplier_Offerings", "supplier_offerings", ("supplier_code", "inventory_code", "purchase_uom", "presentation", "reference_price_mxn", "status", "capture_status", "notes"), ("supplier_code", "inventory_code", "purchase_uom"), ("supplier_code", "inventory_code", "purchase_uom", "status", "capture_status"), references=(("supplier_code", "Suppliers", "supplier_code"), ("inventory_code", "Inventory_Items", "inventory_code")), decimal_fields=("reference_price_mxn",), allowed=(("purchase_uom", UOM), ("status", STATUS)), owner="Purchasing", design_import_status="PARTIAL", dependencies=("Suppliers", "Inventory_Items"), limitation="Requires unambiguous Location through inventory"),
    _sheet("Consumption_Definitions", "consumption_definitions", ("product_code", "consumption_code", "mode", "status", "capture_status", "notes"), ("consumption_code",), ("product_code", "consumption_code", "mode", "status", "capture_status"), references=(("product_code", "Products", "product_code"),), allowed=(("mode", ("AREA", "COMPONENTS", "NO_PREPARATION")), ("status", STATUS)), owner="Inventory", design_import_status="PARTIAL", dependencies=("Products",), limitation="Requires exactly one confirmed Location"),
    _sheet("Consumption_Components", "consumption_components", ("consumption_code", "inventory_code", "quantity", "uom", "waste_rule", "capture_status", "notes"), ("consumption_code", "inventory_code"), ("consumption_code", "inventory_code", "quantity", "uom", "capture_status"), references=(("consumption_code", "Consumption_Definitions", "consumption_code"), ("inventory_code", "Inventory_Items", "inventory_code")), decimal_fields=("quantity",), allowed=(("uom", UOM),), owner="Inventory", design_import_status="PARTIAL", dependencies=("Consumption_Definitions", "Inventory_Items"), limitation="Inherits definition Location ambiguity"),
    _sheet("Recipes", "recipes", ("product_code", "recipe_code", "component_code", "quantity", "uom", "capture_status", "notes"), ("recipe_code", "component_code"), ("product_code", "recipe_code", "component_code", "quantity", "uom", "capture_status"), references=(("product_code", "Products", "product_code"),), decimal_fields=("quantity",), allowed=(("uom", UOM),), owner="Inventory/Preparation", design_import_status="PARTIAL", dependencies=("Products",), limitation="Official component mapping is incomplete"),
    _sheet("Preparation_Routing", "preparation_routing", ("location_code", "product_or_component_code", "prep_area_code", "routing_rule", "printer_code", "status", "capture_status", "notes"), ("location_code", "product_or_component_code", "prep_area_code"), ("location_code", "product_or_component_code", "prep_area_code", "routing_rule", "status", "capture_status"), references=(("location_code", "Locations", "location_code"), ("prep_area_code", "Prep_Areas", "area_code"), ("printer_code", "Printers_Devices", "device_code")), allowed=(("status", STATUS),), owner="Preparation", design_import_status="PARTIAL", dependencies=("Locations", "Prep_Areas"), limitation="Only product-to-area routing is supported"),
    _sheet("Payment_Methods", "payment_methods", ("location_code", "method_code", "name", "payment_category", "executor_kind", "status", "capture_status", "notes"), ("location_code", "method_code"), ("location_code", "method_code", "name", "payment_category", "executor_kind", "status", "capture_status"), references=(("location_code", "Locations", "location_code"),), allowed=(("payment_category", ("CASH", "CARD", "TRANSFER")), ("executor_kind", ("PLATFORM", "EXTERNAL_POS")), ("status", STATUS)), owner="Payment", design_import_status="UNSUPPORTED", dependencies=("Locations",), limitation="Operational workflow; not a catalog import"),
    _sheet("Fiscal_Tax", "fiscal_tax", ("location_code", "tax_code", "classification", "tax_mode", "rate_or_rule", "status", "capture_status", "notes"), ("location_code", "tax_code", "classification"), ("location_code", "tax_code", "classification", "tax_mode", "rate_or_rule", "status", "capture_status"), references=(("location_code", "Locations", "location_code"),), allowed=(("tax_mode", ("TRANSFERRED", "WITHHELD")), ("status", STATUS)), owner="Tax/Fiscal", design_import_status="PARTIAL", dependencies=("Locations",), limitation="Combined mapping lacks current owner inputs"),
)

OFFICIAL_BY_NAME = {sheet.name: sheet for sheet in OFFICIAL_SHEETS}
OFFICIAL_BY_KEY = {sheet.key: sheet for sheet in OFFICIAL_SHEETS}
OFFICIAL_WORKBOOK_SHEETS = ("Instructions", "Metadata", "_Lists", *(s.name for s in OFFICIAL_SHEETS))
OFFICIAL_METADATA_KEYS = (
    "contract_version", "dataset_kind", "restaurant_name", "organization_code",
    "capture_status", "captured_by", "confirmed_by", "confirmed_at", "notes",
)
OFFICIAL_REQUIRED_METADATA = frozenset(OFFICIAL_METADATA_KEYS[:-1])


def validate_official_contract() -> None:
    assert CONTRACT_VERSION == "restaurant-onboarding/v1"
    assert len(OFFICIAL_SHEETS) == 32
    assert len(OFFICIAL_BY_NAME) == len(OFFICIAL_BY_KEY) == 32
    for sheet in OFFICIAL_SHEETS:
        assert len(sheet.headers) == len(set(sheet.headers))
        assert set(sheet.business_key) <= set(sheet.headers)
        assert set(sheet.required) <= set(sheet.headers)
        assert "capture_status" in sheet.headers


validate_official_contract()
