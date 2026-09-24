"""Authoritative capture-only contract for Stage 0 restaurant onboarding.

This module describes operator input. It deliberately performs no parsing, validation
against a database, or persistence. Existing application/domain services remain the
only authorities that may eventually apply these values.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTRACT_VERSION = "restaurant-onboarding/v1"
MAX_CAPTURE_ROWS = 500
LIFECYCLE = ("ACTIVE", "INACTIVE")
YES_NO = ("YES", "NO")
# Mirrors the closed UnitCode authority in restaurant.inventory.units. Keeping the
# manifest import-free lets template generation run without loading application runtime.
UNIT_CODES = ("KG", "G", "L", "ML", "UNIT", "PORTION")


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    label: str
    value_type: str
    required: bool
    description: str
    format: str | None = None
    allowed_values: tuple[str, ...] = ()
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class Group:
    key: str
    sheet: str
    purpose: str
    order: int
    scope: str
    business_key: tuple[str, ...]
    authority: str
    fields: tuple[Field, ...]
    required_for_stage0: bool = True


def f(
    key: str,
    label: str,
    value_type: str,
    required: bool,
    description: str,
    *,
    format: str | None = None,
    allowed: tuple[str, ...] = (),
    reference: str | None = None,
) -> Field:
    return Field(key, label, value_type, required, description, format, allowed, reference)


def ref(key: str, label: str, target: str, description: str, *, required: bool = True) -> Field:
    return f(key, label, "text", required, description, reference=target)


def lifecycle(*, required: bool = True) -> Field:
    return f("status", "Estado", "enum", required, "Ciclo de vida del registro.", allowed=LIFECYCLE)


def local_key(key: str, label: str, description: str) -> Field:
    return f(
        key,
        label,
        "text",
        True,
        description + " Es una clave estable sólo dentro de este workbook; no es un ID de plataforma.",
        format="^[A-Z][A-Z0-9_-]{0,63}$",
    )


ONBOARDING_CONTRACT: tuple[Group, ...] = (
    Group(
        "restaurant_profile", "01_Restaurant", "Identidad y contacto de la ubicación piloto.", 10,
        "tenant / organization / location", ("tenant_slug", "organization_code", "location_code"),
        "models.identity.Tenant + models.organization.Organization/Location",
        (
            f("tenant_slug", "Tenant slug", "text", True, "Tenant existente que recibirá los datos.", format="slug"),
            f("tenant_name", "Tenant", "text", True, "Nombre comercial del tenant."),
            f("organization_code", "Código organización", "text", True, "Código único dentro del tenant.", format="code:64"),
            f("organization_name", "Organización", "text", True, "Nombre de la organización."),
            f("location_code", "Código ubicación", "text", True, "Código único dentro de la organización.", format="code:64"),
            f("location_name", "Ubicación", "text", True, "Nombre operativo de la ubicación."),
            f("timezone", "Zona horaria", "text", True, "Zona IANA, por ejemplo America/Mexico_City.", format="IANA timezone"),
            f("address_line1", "Dirección", "text", False, "Calle y número."),
            f("address_line2", "Dirección 2", "text", False, "Complemento de dirección."),
            f("locality", "Ciudad/localidad", "text", False, "Localidad de la ubicación."),
            f("administrative_area", "Estado/provincia", "text", False, "Área administrativa."),
            f("postal_code", "Código postal", "text", False, "Código postal."),
            f("country_code", "País", "text", True, "Código ISO 3166-1 alfa-2.", format="^[A-Z]{2}$"),
            f("phone", "Teléfono", "text", False, "Teléfono de negocio."),
            f("email", "Email", "text", False, "Email de negocio.", format="email"),
            lifecycle(),
        ),
    ),
    Group(
        "staff", "02_Staff", "Roster, membresía, rol solicitado y alcance de ubicación; nunca credenciales.", 20,
        "tenant / location", ("staff_key", "role_name", "location_code"),
        "models.identity.User/TenantMembership/Role/MembershipRole/"
        "MembershipLocationGrant/MembershipLocationRole",
        (
            local_key("staff_key", "Clave personal", "Referencia del empleado en la captura"),
            ref("tenant_slug", "Tenant slug", "restaurant_profile.tenant_slug", "Tenant del empleado."),
            f("display_name", "Nombre", "text", True, "Nombre visible del empleado."),
            f("email", "Email/login", "text", True, "Login único global; no escribir contraseña.", format="email"),
            f("role_name", "Rol", "text", True, "Rol aprobado que deberá provisionarse posteriormente."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación autorizada."),
            lifecycle(),
        ),
    ),
    Group(
        "resources", "03_Resources", "Mesas, cajas y otros recursos operativos reales.", 30,
        "location", ("location_code", "resource_code"), "models.resource.Resource",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación propietaria."),
            f("resource_code", "Código recurso", "text", True, "Código único dentro de la ubicación.", format="code:64"),
            f("name", "Nombre", "text", True, "Nombre visible."),
            f("resource_type", "Tipo", "enum", True, "Tipo de recurso existente.", allowed=("AREA", "TABLE", "WORKSTATION", "EQUIPMENT", "VEHICLE", "DEVICE", "CASH_REGISTER")),
            lifecycle(),
        ),
    ),
    Group(
        "preparation_configuration", "04_Prep_Config", "Autoridad que prepara pedidos en la ubicación.", 40,
        "location", ("location_code",), "models.preparation.LocationPreparationConfiguration",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación configurada."),
            f("preparation_owner", "Responsable", "enum", True, "PLATFORM para operación interna; EXTERNAL_POS sólo si se autoriza esa integración.", allowed=("PLATFORM", "EXTERNAL_POS")),
        ),
    ),
    Group(
        "preparation_areas", "05_Prep_Areas", "Áreas configurables que reciben trabajo de preparación.", 50,
        "location", ("location_code", "preparation_area_code"), "models.preparation.PreparationArea",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación propietaria."),
            f("preparation_area_code", "Código área", "text", True, "Código único dentro de la ubicación.", format="^[A-Z0-9_-]{1,64}$"),
            f("name", "Nombre", "text", True, "Nombre visible del área."),
            ref("resource_code", "Código recurso", "resources.resource_code", "Recurso AREA opcional vinculado.", required=False),
            lifecycle(),
        ),
    ),
    Group(
        "categories", "06_Categories", "Jerarquía de categorías de productos.", 60,
        "organization", ("category_key",), "models.menu.ProductCategory",
        (
            local_key("category_key", "Clave categoría", "Referencia inequívoca de la categoría"),
            ref("organization_code", "Código organización", "restaurant_profile.organization_code", "Organización propietaria."),
            f("name", "Categoría", "text", True, "Nombre único dentro de la organización."),
            ref("parent_category_key", "Clave categoría padre", "categories.category_key", "Padre opcional en la misma organización.", required=False),
            f("display_order", "Orden", "integer", False, "Orden de presentación, cero o mayor.", format=">=0"),
            lifecycle(),
        ),
    ),
    Group(
        "products", "07_Products", "Productos comerciales y productos usados como opciones/componentes.", 70,
        "organization", ("product_key",), "models.menu.Product",
        (
            local_key("product_key", "Clave producto", "Referencia inequívoca del producto"),
            ref("organization_code", "Código organización", "restaurant_profile.organization_code", "Organización propietaria."),
            ref("category_key", "Clave categoría", "categories.category_key", "Categoría elegida explícitamente; opcional.", required=False),
            f("name", "Producto", "text", True, "Nombre visible; la plataforma no posee hoy product_code."),
            f("description", "Descripción", "text", False, "Descripción visible."),
            lifecycle(),
        ),
    ),
    Group(
        "product_aliases", "08_Product_Aliases", "Nombres alternos usados por la resolución natural de productos.", 75,
        "product / organization", ("product_key", "alias", "language"), "models.product_resolution.ProductAlias",
        (
            ref("product_key", "Clave producto", "products.product_key", "Producto al que pertenece el alias."),
            f("alias", "Alias", "text", True, "Nombre alterno que el comensal puede utilizar."),
            f("language", "Idioma", "text", False, "Etiqueta BCP-47 opcional; vacío significa neutral.", format="BCP-47"),
            lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "menus", "08_Menus", "Menús y su disponibilidad por ubicación.", 80,
        "organization / location", ("menu_key", "location_code"), "models.menu.Menu/MenuLocation",
        (
            local_key("menu_key", "Clave menú", "Referencia inequívoca del menú"),
            ref("organization_code", "Código organización", "restaurant_profile.organization_code", "Organización propietaria."),
            f("name", "Menú", "text", True, "Nombre visible."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación donde estará disponible."),
            lifecycle(),
        ),
    ),
    Group(
        "menu_sections", "09_Menu_Sections", "Secciones ordenadas de cada menú.", 90,
        "menu", ("section_key",), "models.menu.MenuSection",
        (
            local_key("section_key", "Clave sección", "Referencia inequívoca de la sección"),
            ref("menu_key", "Clave menú", "menus.menu_key", "Menú propietario."),
            f("name", "Sección", "text", True, "Nombre visible."),
            f("display_order", "Orden", "integer", True, "Orden de presentación.", format=">=0"),
            lifecycle(),
        ),
    ),
    Group(
        "menu_items", "10_Menu_Items", "Ubicación de productos dentro de secciones de menú.", 100,
        "menu", ("menu_key", "product_key"), "models.menu.MenuItem",
        (
            ref("menu_key", "Clave menú", "menus.menu_key", "Menú propietario."),
            ref("section_key", "Clave sección", "menu_sections.section_key", "Sección del mismo menú."),
            ref("product_key", "Clave producto", "products.product_key", "Producto mostrado."),
            f("display_order", "Orden", "integer", True, "Orden de presentación.", format=">=0"),
            lifecycle(),
        ),
    ),
    Group(
        "prices", "11_Prices", "Precio vigente por producto y ubicación.", 110,
        "product / location", ("product_key", "location_code"), "models.pricing.ProductPrice",
        (
            ref("product_key", "Clave producto", "products.product_key", "Producto vendido."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación del precio."),
            f("amount", "Precio", "decimal", True, "Importe exacto no negativo, máximo cuatro decimales.", format="decimal(19,4) >= 0"),
            f("currency", "Moneda", "text", True, "Código ISO 4217 en mayúsculas.", format="^[A-Z]{3}$"),
            lifecycle(),
        ),
    ),
    Group(
        "product_compositions", "12_Compositions", "Activa la composición de combos, paquetes o productos configurables.", 120,
        "product", ("product_key",), "models.product_structure.ProductComposition",
        (ref("product_key", "Producto padre", "products.product_key", "Producto compuesto."), lifecycle()),
        required_for_stage0=False,
    ),
    Group(
        "product_components", "13_Fixed_Components", "Componentes fijos de una composición.", 130,
        "product composition", ("parent_product_key", "component_product_key"), "models.product_structure.ProductComponent",
        (
            ref("parent_product_key", "Producto padre", "product_compositions.product_key", "Composición propietaria."),
            ref("component_product_key", "Producto componente", "products.product_key", "Producto incluido."),
            f("quantity", "Cantidad", "decimal", True, "Cantidad positiva, máximo cuatro decimales.", format="decimal(19,4) > 0"),
            f("display_order", "Orden", "integer", True, "Orden de presentación.", format=">=0"), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "choice_groups", "14_Choice_Groups", "Grupos de selección de modificadores/opciones.", 140,
        "product composition", ("choice_group_key",), "models.product_structure.ProductChoiceGroup",
        (
            local_key("choice_group_key", "Clave grupo", "Referencia inequívoca del grupo"),
            ref("parent_product_key", "Producto padre", "product_compositions.product_key", "Composición propietaria."),
            f("name", "Grupo", "text", True, "Nombre visible."),
            f("min_selections", "Mínimo", "integer", True, "Selecciones mínimas.", format=">=0"),
            f("max_selections", "Máximo", "integer", True, "Selecciones máximas; debe ser >= mínimo.", format=">0"),
            f("display_order", "Orden", "integer", True, "Orden de presentación.", format=">=0"), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "choice_options", "15_Choice_Options", "Productos disponibles como opciones en un grupo.", 150,
        "choice group", ("choice_group_key", "option_product_key"), "models.product_structure.ProductChoiceOption",
        (
            ref("choice_group_key", "Clave grupo", "choice_groups.choice_group_key", "Grupo propietario."),
            ref("option_product_key", "Producto opción", "products.product_key", "Producto elegido."),
            f("quantity", "Cantidad", "decimal", True, "Cantidad positiva, máximo cuatro decimales.", format="decimal(19,4) > 0"),
            f("display_order", "Orden", "integer", True, "Orden de presentación.", format=">=0"), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "promotions", "16_Promotions", "Promociones temporales confirmadas para el piloto.", 160,
        "organization", ("promotion_key",), "models.pricing.Promotion",
        (
            local_key("promotion_key", "Clave promoción", "Referencia inequívoca de la promoción"),
            ref("organization_code", "Código organización", "restaurant_profile.organization_code", "Organización propietaria."),
            f("name", "Promoción", "text", True, "Nombre visible."), f("description", "Descripción", "text", False, "Descripción."),
            f("promotion_type", "Tipo", "enum", True, "Tipo de descuento.", allowed=("PERCENTAGE_DISCOUNT", "FIXED_AMOUNT_DISCOUNT")),
            f("benefit_value", "Beneficio", "decimal", True, "Porcentaje <=100 o importe fijo positivo.", format="decimal(19,4) > 0"),
            f("currency", "Moneda", "text", False, "Obligatoria sólo para descuento fijo.", format="^[A-Z]{3}$"),
            f("starts_at", "Inicio", "datetime", True, "Fecha/hora con zona horaria.", format="ISO 8601 timezone-aware"),
            f("ends_at", "Fin", "datetime", True, "Posterior a inicio; con zona horaria.", format="ISO 8601 timezone-aware"),
            f("applies_to_all_locations", "Todas ubicaciones", "enum", True, "Aplicación global dentro de la organización.", allowed=YES_NO),
            f("is_combinable", "Combinable", "enum", True, "Permite combinar con otras promociones.", allowed=YES_NO),
            f("priority", "Prioridad", "integer", True, "Prioridad cero o mayor.", format=">=0"), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "promotion_products", "17_Promotion_Products", "Productos incluidos en una promoción.", 170,
        "promotion", ("promotion_key", "product_key"), "models.pricing.PromotionProduct",
        (ref("promotion_key", "Clave promoción", "promotions.promotion_key", "Promoción."), ref("product_key", "Clave producto", "products.product_key", "Producto."), lifecycle()),
        required_for_stage0=False,
    ),
    Group(
        "promotion_locations", "18_Promotion_Locations", "Ubicaciones incluidas cuando la promoción no aplica a todas.", 175,
        "promotion", ("promotion_key", "location_code"), "models.pricing.PromotionLocation",
        (
            ref("promotion_key", "Clave promoción", "promotions.promotion_key", "Promoción con applies_to_all_locations=NO."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación incluida."),
            lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "warehouses", "18_Warehouses", "Almacenes reales y política de existencia negativa.", 180,
        "location", ("location_code", "warehouse_code"), "models.inventory.Warehouse",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación propietaria."),
            f("warehouse_code", "Código almacén", "text", True, "Código único por ubicación.", format="code:64"),
            f("name", "Almacén", "text", True, "Nombre visible."),
            f("is_default", "Predeterminado", "enum", True, "Sólo uno por ubicación.", allowed=YES_NO),
            f("negative_stock_policy", "Existencia negativa", "enum", True, "Política autorizada.", allowed=("ALLOW", "WARN", "BLOCK")), lifecycle(),
        ),
    ),
    Group(
        "inventory_items", "19_Inventory_Items", "Ingredientes, insumos y productos preparados controlados en inventario.", 190,
        "location", ("location_code", "inventory_item_code"), "models.inventory.InventoryItem",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación propietaria."),
            f("inventory_item_code", "Código artículo", "text", True, "Código único por ubicación.", format="code:64"),
            f("name", "Artículo", "text", True, "Nombre visible."),
            f("base_uom", "Unidad base", "enum", True, "Unidad canónica.", allowed=UNIT_CODES),
            f("standard_unit_cost", "Costo estándar", "decimal", True, "Costo por unidad base no negativo.", format="decimal(19,6) >= 0"),
            f("currency", "Moneda", "text", True, "Código ISO 4217.", format="^[A-Z]{3}$"),
            f("lot_tracking_policy", "Control de lote", "enum", True, "Política de lote.", allowed=("OPTIONAL", "REQUIRED")),
            f("date_tracking_policy", "Control de fecha", "enum", True, "Política de caducidad/consumo preferente.", allowed=("NONE", "EXPIRY", "BEST_BEFORE", "BOTH")), lifecycle(),
        ),
    ),
    Group(
        "uom_conversions", "20_UOM_Conversions", "Conversiones operativas hacia la unidad base del artículo.", 200,
        "inventory item", ("inventory_item_code", "operational_uom"), "models.inventory.ItemUomConversion",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación del artículo."),
            ref("inventory_item_code", "Código artículo", "inventory_items.inventory_item_code", "Artículo convertido."),
            f("operational_uom", "Unidad operativa", "text", True, "Código de unidad usada al comprar/producir.", format="^[A-Z][A-Z0-9_]{0,31}$"),
            f("factor_to_base", "Factor a base", "decimal", True, "Unidades base equivalentes a una unidad operativa.", format=">0"),
            f("effective_at", "Vigente desde", "datetime", False, "Fecha efectiva opcional con zona horaria.", format="ISO 8601 timezone-aware"),
            f("reference", "Referencia", "text", False, "Fuente o nota aprobada."),
        ),
    ),
    Group(
        "suppliers", "21_Suppliers", "Proveedores y disponibilidad en la ubicación piloto.", 210,
        "organization / location", ("organization_code", "supplier_code", "location_code"), "models.inventory.Supplier/SupplierLocation",
        (
            ref("organization_code", "Código organización", "restaurant_profile.organization_code", "Organización propietaria."),
            f("supplier_code", "Código proveedor", "text", True, "Código único por organización.", format="code:64"),
            f("name", "Proveedor", "text", True, "Nombre visible."), f("contact_reference", "Contacto", "text", False, "Referencia de contacto no secreta."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación atendida."), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "supplier_offerings", "22_Supplier_Offers", "Artículos que cada proveedor suministra y unidad de compra.", 220,
        "supplier / location", ("supplier_code", "location_code", "inventory_item_code"), "models.inventory.SupplierOffering",
        (
            ref("supplier_code", "Código proveedor", "suppliers.supplier_code", "Proveedor."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación atendida."),
            ref("inventory_item_code", "Código artículo", "inventory_items.inventory_item_code", "Artículo suministrado."),
            f("supplier_item_code", "Código del proveedor", "text", False, "Código externo del proveedor, no del POS."),
            f("purchase_uom", "Unidad de compra", "text", True, "Debe ser base o tener conversión declarada.", format="^[A-Z][A-Z0-9_]{0,31}$"), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "consumption_definitions", "23_Consumption", "Política de consumo de inventario por producto vendido.", 230,
        "product / location", ("product_key", "location_code"), "models.inventory.ProductConsumptionDefinition",
        (
            ref("product_key", "Clave producto", "products.product_key", "Producto vendido."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación."),
            f("tracking_mode", "Modo", "enum", True, "DERIVABLE exige componentes; NON_DERIVABLE no descuenta receta.", allowed=("DERIVABLE", "NON_DERIVABLE")),
            f("effective_from", "Vigente desde", "datetime", False, "Fecha efectiva con zona horaria.", format="ISO 8601 timezone-aware"), lifecycle(),
        ),
    ),
    Group(
        "consumption_components", "24_Consumption_Lines", "Ingredientes consumidos por unidad de producto vendido.", 240,
        "consumption definition", ("product_key", "location_code", "inventory_item_code"), "models.inventory.ProductConsumptionComponent",
        (
            ref("product_key", "Clave producto", "consumption_definitions.product_key", "Definición propietaria."),
            ref("location_code", "Código ubicación", "consumption_definitions.location_code", "Ubicación de la definición."),
            ref("inventory_item_code", "Código artículo", "inventory_items.inventory_item_code", "Ingrediente consumido."),
            f("quantity", "Cantidad", "decimal", True, "Cantidad positiva por unidad vendida.", format=">0"),
            f("uom", "Unidad", "text", True, "Unidad base u operativa con conversión.", format="unit code:32"),
        ),
    ),
    Group(
        "preparation_recipes", "25_Recipes", "Versiones publicables de recetas para artículos preparados.", 250,
        "location / output item", ("recipe_key",), "models.inventory.PreparationRecipeVersion",
        (
            local_key("recipe_key", "Clave receta", "Referencia inequívoca de esta versión a publicar"),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación."),
            ref("output_inventory_item_code", "Artículo resultado", "inventory_items.inventory_item_code", "Artículo preparado resultante."),
            f("expected_output_quantity", "Rendimiento esperado", "decimal", True, "Cantidad positiva esperada.", format=">0"),
            f("output_uom", "Unidad resultado", "text", True, "Unidad base u operativa con conversión.", format="unit code:32"),
            f("effective_from", "Vigente desde", "datetime", False, "Inicio efectivo con zona horaria.", format="ISO 8601 timezone-aware"),
            f("effective_to", "Vigente hasta", "datetime", False, "Fin efectivo opcional.", format="ISO 8601 timezone-aware"), lifecycle(),
        ), required_for_stage0=False,
    ),
    Group(
        "preparation_recipe_components", "26_Recipe_Lines", "Ingredientes de cada receta preparada.", 260,
        "preparation recipe", ("recipe_key", "inventory_item_code"), "models.inventory.PreparationRecipeComponent",
        (
            ref("recipe_key", "Clave receta", "preparation_recipes.recipe_key", "Receta propietaria."),
            ref("inventory_item_code", "Código ingrediente", "inventory_items.inventory_item_code", "Ingrediente."),
            f("expected_quantity", "Cantidad esperada", "decimal", True, "Cantidad positiva.", format=">0"),
            f("source_uom", "Unidad", "text", True, "Unidad base u operativa con conversión.", format="unit code:32"),
            f("yield_basis", "Base rendimiento", "enum", True, "Sólo un componente por receta puede ser YES.", allowed=YES_NO),
        ), required_for_stage0=False,
    ),
    Group(
        "preparation_routes", "27_Prep_Routes", "Routing determinista de cada producto a preparación.", 270,
        "product / location", ("product_key", "location_code"), "models.preparation.ProductPreparationRoute",
        (
            ref("product_key", "Clave producto", "products.product_key", "Producto comercial."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación."),
            f("policy", "Política", "enum", True, "AREA requiere área; otras políticas no la permiten.", allowed=("AREA", "COMPONENTS", "NO_PREPARATION")),
            ref("preparation_area_code", "Código área", "preparation_areas.preparation_area_code", "Obligatorio sólo con policy AREA.", required=False),
            lifecycle(),
        ),
    ),
    Group(
        "tax_rules", "28_Tax_Rules", "Reglas fiscales aprobadas por contador para aceptación de órdenes.", 280,
        "organization / optional location", ("tax_rule_key",), "models.restaurant_tax.RestaurantTaxRule",
        (
            local_key("tax_rule_key", "Clave regla", "Referencia de captura de la regla"),
            ref("organization_code", "Código organización", "restaurant_profile.organization_code", "Organización."),
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Vacío para alcance organización.", required=False),
            f("tax_classification_code", "Clasificación impuesto", "text", True, "Código que también se asignará al producto."),
            f("jurisdiction_code", "Jurisdicción", "text", True, "Jurisdicción fiscal."), f("tax_category", "Categoría fiscal", "text", True, "Categoría fiscal aprobada."),
            f("tax_treatment", "Tratamiento", "text", True, "Tratamiento fiscal aprobado."),
            f("tax_effect", "Efecto", "enum", True, "Impuesto trasladado o retenido.", allowed=("TRANSFERRED", "WITHHELD")),
            f("tax_rate", "Tasa", "decimal", True, "Tasa no negativa, máximo seis decimales.", format="decimal(9,6) >= 0"),
            f("calculation_policy", "Cálculo", "text", True, "Política existente aprobada."), f("rounding_policy", "Redondeo", "text", True, "Política existente aprobada."),
            f("effective_from", "Vigente desde", "datetime", True, "Inicio efectivo con zona horaria.", format="ISO 8601 timezone-aware"),
            f("effective_to", "Vigente hasta", "datetime", False, "Fin efectivo opcional.", format="ISO 8601 timezone-aware"), lifecycle(),
        ),
    ),
    Group(
        "product_fiscal_classifications", "29_Product_Fiscal", "Clasificación fiscal vigente de cada producto.", 290,
        "product / jurisdiction", ("product_key", "fiscal_jurisdiction_code", "effective_from"), "models.fiscal_product.ProductFiscalClassification",
        (
            ref("product_key", "Clave producto", "products.product_key", "Producto clasificado."),
            f("tax_classification_code", "Clasificación impuesto", "text", True, "Código que enlaza la resolución de tax rule."),
            f("fiscal_jurisdiction_code", "Jurisdicción fiscal", "text", True, "Jurisdicción de clasificación."),
            f("product_classification_scheme", "Esquema producto", "text", True, "Esquema oficial."), f("product_classification_code", "Código producto", "text", True, "Código oficial."),
            f("unit_classification_scheme", "Esquema unidad", "text", True, "Esquema oficial."), f("unit_classification_code", "Código unidad", "text", True, "Código oficial."),
            f("effective_from", "Vigente desde", "datetime", True, "Inicio efectivo con zona horaria.", format="ISO 8601 timezone-aware"),
            f("effective_to", "Vigente hasta", "datetime", False, "Fin efectivo opcional.", format="ISO 8601 timezone-aware"), lifecycle(),
        ),
    ),
    Group(
        "payment_methods", "30_Payment_Methods", "Decisión de métodos de pago del piloto, sin credenciales.", 300,
        "location", ("location_code", "method"), "restaurant payment capability selection",
        (
            ref("location_code", "Código ubicación", "restaurant_profile.location_code", "Ubicación."),
            f("method", "Método", "enum", True, "Método considerado.", allowed=("CASH", "CARD", "TRANSFER")),
            f("enabled", "Habilitado", "enum", True, "Decisión explícita del alcance.", allowed=YES_NO),
            f("currency", "Moneda", "text", True, "Código ISO 4217.", format="^[A-Z]{3}$"),
            f("provider", "Proveedor", "text", False, "Obligatorio para método no efectivo habilitado; nunca credenciales."),
        ),
    ),
)


def validate_contract(groups: tuple[Group, ...] = ONBOARDING_CONTRACT) -> None:
    if not CONTRACT_VERSION or "/" not in CONTRACT_VERSION:
        raise ValueError("Contract version must be namespaced")
    group_keys = [group.key for group in groups]
    sheets = [group.sheet for group in groups]
    orders = [group.order for group in groups]
    if len(group_keys) != len(set(group_keys)) or len(sheets) != len(set(sheets)):
        raise ValueError("Group keys and sheet names must be unique")
    if orders != sorted(orders) or len(orders) != len(set(orders)):
        raise ValueError("Dependency order must be unique and increasing")
    if any(len(group.sheet) > 31 for group in groups):
        raise ValueError("Excel sheet names cannot exceed 31 characters")
    index = {group.key: group for group in groups}
    for group in groups:
        keys = [field.key for field in group.fields]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError(f"Field keys must be present and unique in {group.key}")
        if not group.business_key or not set(group.business_key) <= set(keys):
            raise ValueError(f"Business key is invalid in {group.key}")
        for field in group.fields:
            if not field.key.isidentifier() or field.value_type not in {"text", "integer", "decimal", "datetime", "enum"}:
                raise ValueError(f"Invalid field definition {group.key}.{field.key}")
            if field.value_type == "enum" and not field.allowed_values:
                raise ValueError(f"Enum has no values: {group.key}.{field.key}")
            if field.reference:
                target_group_key, separator, target_field_key = field.reference.partition(".")
                if not separator or target_group_key not in index:
                    raise ValueError(f"Invalid reference {field.reference}")
                target = index[target_group_key]
                if target.order > group.order or target_field_key not in {item.key for item in target.fields}:
                    raise ValueError(f"Unresolvable reference {field.reference}")


validate_contract()
