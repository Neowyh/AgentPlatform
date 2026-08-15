"""Runtime switch for the resource-catalog compatibility period."""

from __future__ import annotations

import os
from enum import StrEnum


class ResourceCatalogMode(StrEnum):
    LEGACY = "legacy"
    DUAL = "dual"
    CANONICAL = "canonical"


def get_resource_catalog_mode() -> ResourceCatalogMode:
    raw_value = os.getenv("IDEER_RESOURCE_CATALOG_MODE", ResourceCatalogMode.DUAL.value)
    try:
        return ResourceCatalogMode(raw_value)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ResourceCatalogMode)
        raise ValueError(f"IDEER_RESOURCE_CATALOG_MODE must be one of: {valid}") from exc
