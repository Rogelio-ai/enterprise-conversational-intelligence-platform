"""Apply only the operator-confirmed public facts known for WS-33-C6.

This is an explicit operator command. It is not imported by application startup.
It fills missing authoritative Location fields, rejects conflicts, and is safe to
run repeatedly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.models import Location, Organization, Tenant


TENANT_ID = 1
TENANT_NAME = "Carnitas Muñoz y Cortes"
TENANT_SLUG = "carnitas-munoz-y-cortes"
ORGANIZATION_ID = 1
ORGANIZATION_CODE = "CMC"
ORGANIZATION_NAME = "Carnitas Muñoz y Cortes"
LOCATION_ID = 1
LOCATION_CODE = "SLP-CARNITAS-MUNOZ"
LOCATION_NAME = "Carnitas Muñoz"
LOCATION_TIMEZONE = "America/Mexico_City"
LOCATION_LOCALITY = "San Luis Potosí"
LOCATION_ADMINISTRATIVE_AREA = "San Luis Potosí"
LOCATION_COUNTRY_CODE = "MX"


@dataclass(frozen=True)
class ConfigurationResult:
    tenant_id: int
    organization_id: int
    location_id: int
    fields_updated: tuple[str, ...]


def _require_match(record: object, label: str, expected: dict[str, object]) -> None:
    conflicts = {
        field: {"actual": getattr(record, field), "expected": value}
        for field, value in expected.items()
        if getattr(record, field) != value
    }
    if conflicts:
        raise RuntimeError(f"{label} conflicts with confirmed pilot authority: {conflicts}")


def _fill_confirmed(
    location: Location,
    field: str,
    expected: str,
    updated: list[str],
) -> None:
    current = getattr(location, field)
    if current is None:
        setattr(location, field, expected)
        updated.append(field)
    elif current != expected:
        raise RuntimeError(
            f"Location.{field} conflicts with confirmed pilot authority: "
            f"actual={current!r}, expected={expected!r}"
        )


async def configure_known_real(session: AsyncSession) -> ConfigurationResult:
    tenant = await session.scalar(
        select(Tenant).where(Tenant.id == TENANT_ID).with_for_update()
    )
    organization = await session.scalar(
        select(Organization).where(
            Organization.id == ORGANIZATION_ID,
            Organization.tenant_id == TENANT_ID,
        ).with_for_update()
    )
    location = await session.scalar(
        select(Location).where(
            Location.id == LOCATION_ID,
            Location.tenant_id == TENANT_ID,
            Location.organization_id == ORGANIZATION_ID,
        ).with_for_update()
    )
    if tenant is None or organization is None or location is None:
        raise RuntimeError("Confirmed Tenant/Organization/Location authority is incomplete")

    _require_match(
        tenant,
        "Tenant",
        {"name": TENANT_NAME, "slug": TENANT_SLUG, "status": "ACTIVE"},
    )
    _require_match(
        organization,
        "Organization",
        {"code": ORGANIZATION_CODE, "name": ORGANIZATION_NAME, "status": "ACTIVE"},
    )
    _require_match(
        location,
        "Location",
        {
            "code": LOCATION_CODE,
            "name": LOCATION_NAME,
            "timezone": LOCATION_TIMEZONE,
            "status": "ACTIVE",
        },
    )

    updated: list[str] = []
    _fill_confirmed(location, "locality", LOCATION_LOCALITY, updated)
    _fill_confirmed(
        location,
        "administrative_area",
        LOCATION_ADMINISTRATIVE_AREA,
        updated,
    )
    _fill_confirmed(location, "country_code", LOCATION_COUNTRY_CODE, updated)
    await session.flush()
    return ConfigurationResult(TENANT_ID, ORGANIZATION_ID, LOCATION_ID, tuple(updated))


async def _main() -> None:
    database = DatabaseManager(get_settings())
    try:
        async with database.session_factory() as session:
            async with session.begin():
                result = await configure_known_real(session)
        print(
            json.dumps(
                {
                    "status": "configured" if result.fields_updated else "already_configured",
                    "tenant_id": result.tenant_id,
                    "organization_id": result.organization_id,
                    "location_id": result.location_id,
                    "fields_updated": list(result.fields_updated),
                },
                ensure_ascii=False,
            )
        )
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
