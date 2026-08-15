"""HTTP cutover guards for legacy name-addressed resource facades."""

from fastapi import HTTPException

from ideer.resources.mode import ResourceCatalogMode, get_resource_catalog_mode


def require_legacy_resource_facades() -> None:
    if get_resource_catalog_mode() is ResourceCatalogMode.CANONICAL:
        raise HTTPException(
            status_code=410,
            detail=("Legacy name-addressed resource APIs are disabled in canonical mode; use /api/resources with a resource UUID"),
        )
