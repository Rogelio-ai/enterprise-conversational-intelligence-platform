#!/usr/bin/env python3
"""Print a secret-safe, read-only inventory of pilot configuration tables."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
import json
import os

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.session import DatabaseManager


TABLES = (
    "tenants",
    "organizations",
    "locations",
    "users",
    "tenant_memberships",
    "roles",
    "membership_roles",
    "membership_location_grants",
    "resources",
    "location_preparation_configurations",
    "preparation_areas",
    "product_preparation_routes",
    "product_categories",
    "products",
    "product_prices",
    "menus",
    "menu_locations",
    "menu_sections",
    "menu_items",
    "product_compositions",
    "product_components",
    "product_choice_groups",
    "product_choice_options",
    "promotions",
    "promotion_products",
    "promotion_locations",
    "restaurant_tax_rules",
    "product_fiscal_classifications",
    "issuer_fiscal_profiles",
    "location_payment_executor_configurations",
    "location_payment_executor_capabilities",
    "preparation_delivery_connectors",
    "preparation_delivery_destinations",
)

EVIDENCE_TABLES = (
    "preparation_delivery_connector_enrollments",
    "preparation_delivery_connector_credentials",
    "cash_sessions",
    "cash_movements",
    "restaurant_service_sessions",
    "restaurant_orders",
    "restaurant_checks",
    "restaurant_payments",
    "preparation_dispatches",
    "paid_check_dispatches",
)

SENSITIVE_FRAGMENTS = (
    "password",
    "secret",
    "credential",
    "digest",
    "token",
    "public_key",
)


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    return value


async def inventory() -> None:
    tenant_id = int(os.environ.get("PILOT_TENANT_ID", "1"))
    if tenant_id <= 0:
        raise ValueError("PILOT_TENANT_ID must be a positive integer")
    database = DatabaseManager(get_settings())
    try:
        async with database.engine.connect() as connection:
            existing = set(
                await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            )
            for table in TABLES:
                if table not in existing:
                    print(json.dumps({"table": table, "available": False}))
                    continue
                result = await connection.execute(
                    text(
                        "SELECT u.id, u.email, u.display_name, u.status, "
                        "u.created_at, u.updated_at FROM users u "
                        "JOIN tenant_memberships tm ON tm.user_id = u.id "
                        "WHERE tm.tenant_id = :tenant_id ORDER BY u.id"
                        if table == "users"
                        else (
                            f"SELECT * FROM `{table}` WHERE id = :tenant_id ORDER BY id"
                            if table == "tenants"
                            else f"SELECT * FROM `{table}` WHERE tenant_id = :tenant_id ORDER BY id"
                        )
                    ),  # noqa: S608 - table comes from the fixed allowlist above
                    {"tenant_id": tenant_id},
                )
                rows = []
                for row in result.mappings():
                    rows.append(
                        {
                            key: (
                                "[REDACTED]"
                                if any(part in key.lower() for part in SENSITIVE_FRAGMENTS)
                                else _json_value(value)
                            )
                            for key, value in row.items()
                        }
                    )
                print(
                    json.dumps(
                        {"table": table, "available": True, "count": len(rows), "rows": rows},
                        ensure_ascii=False,
                    )
                )
            for table in EVIDENCE_TABLES:
                if table not in existing:
                    print(json.dumps({"table": table, "available": False}))
                    continue
                count = await connection.scalar(
                    text(
                        f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id = :tenant_id"
                    ),  # noqa: S608 - table comes from the fixed allowlist above
                    {"tenant_id": tenant_id},
                )
                print(
                    json.dumps(
                        {
                            "table": table,
                            "available": True,
                            "evidence_only": True,
                            "count": int(count or 0),
                        }
                    )
                )
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(inventory())
