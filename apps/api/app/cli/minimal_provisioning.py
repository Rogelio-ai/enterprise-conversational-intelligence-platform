"""Run minimal provisioning from a non-secret JSON manifest.

Usage: python -m app.cli.minimal_provisioning --manifest /path/to/manifest.json
The Staff password is read only from MINIMAL_PROVISIONING_STAFF_PASSWORD.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from app.core.config import get_settings
from app.db.session import DatabaseManager
from app.minimal_provisioning import MinimalProvisioningManifest, provision_minimal_core


async def _run(manifest_path: Path) -> dict[str, int | bool]:
    password = os.environ.get('MINIMAL_PROVISIONING_STAFF_PASSWORD')
    if password is None:
        raise RuntimeError('MINIMAL_PROVISIONING_STAFF_PASSWORD is required')
    manifest = MinimalProvisioningManifest.model_validate_json(
        manifest_path.read_text(encoding='utf-8')
    )
    settings = get_settings()
    database = DatabaseManager(settings)
    try:
        async with database.session_factory() as session:
            result = await provision_minimal_core(
                session,
                manifest=manifest,
                staff_password=password,
                password_minimum_length=settings.password_min_length,
            )
            return {
                'organization_id': result.organization_id,
                'location_id': result.location_id,
                'staff_user_id': result.staff_user_id,
                'replayed': result.replayed,
            }
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description='Provision minimal Restaurant core state')
    parser.add_argument('--manifest', type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(_run(arguments.manifest)), sort_keys=True))


if __name__ == '__main__':
    main()
