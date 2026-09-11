from __future__ import annotations

import asyncio

import pytest

from app.configure_pilot_known_real import configure_known_real
from app.models import Location, Organization, Tenant


class FakeSession:
    def __init__(self, *records: object) -> None:
        self.records = iter(records)
        self.flush_count = 0

    async def scalar(self, _statement: object) -> object:
        return next(self.records)

    async def flush(self) -> None:
        self.flush_count += 1


def authority(*, locality: str | None = None) -> tuple[object, object, object]:
    return (
        Tenant(
            id=1,
            name="Carnitas Muñoz y Cortes",
            slug="carnitas-munoz-y-cortes",
            status="ACTIVE",
        ),
        Organization(
            id=1,
            tenant_id=1,
            code="CMC",
            name="Carnitas Muñoz y Cortes",
            status="ACTIVE",
        ),
        Location(
            id=1,
            tenant_id=1,
            organization_id=1,
            code="SLP-CARNITAS-MUNOZ",
            name="Carnitas Muñoz",
            timezone="America/Mexico_City",
            status="ACTIVE",
            locality=locality,
            administrative_area=None,
            country_code="MX",
        ),
    )


def test_configure_known_real_fills_only_missing_confirmed_fields() -> None:
    session = FakeSession(*authority())

    result = asyncio.run(configure_known_real(session))  # type: ignore[arg-type]

    assert result.fields_updated == ("locality", "administrative_area")
    assert session.flush_count == 1


def test_configure_known_real_is_idempotent() -> None:
    tenant, organization, location = authority(locality="San Luis Potosí")
    location.administrative_area = "San Luis Potosí"
    session = FakeSession(tenant, organization, location)

    result = asyncio.run(configure_known_real(session))  # type: ignore[arg-type]

    assert result.fields_updated == ()


def test_configure_known_real_rejects_conflicting_fact() -> None:
    session = FakeSession(*authority(locality="Another city"))

    with pytest.raises(RuntimeError, match="Location.locality conflicts"):
        asyncio.run(configure_known_real(session))  # type: ignore[arg-type]
