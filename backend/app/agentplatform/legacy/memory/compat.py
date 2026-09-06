"""Compat reads for pre-abstraction memory settings.

The upstream ``deerflow.config.memory_config.MemoryConfig`` slimmed down to
host-shared fields and auto-migrates the ideer-era knobs (``storage_path``,
``storage_class``, ``debounce_seconds``, ``max_facts``,
``fact_confidence_threshold``, ``max_injection_tokens``, ``model_name``)
into ``backend_config``. The legacy memory modules still honour those knobs,
so all reads go through :func:`legacy_memory_setting` which checks the
top-level attribute first (in case a caller passes an old-style config
double) and falls back to ``backend_config`` with the historical defaults.
"""

from __future__ import annotations

from typing import Any

# Historical ideer defaults (backend/packages/harness/ideer/config/memory_config.py)
LEGACY_STORAGE_CLASS = "app.agentplatform.legacy.memory.storage.FileMemoryStorage"
LEGACY_DEBOUNCE_SECONDS = 30
LEGACY_MAX_FACTS = 100
LEGACY_FACT_CONFIDENCE_THRESHOLD = 0.7
LEGACY_MAX_INJECTION_TOKENS = 2000


def legacy_memory_setting(config: Any, key: str, default: Any) -> Any:
    """Read a legacy memory setting from *config* or its ``backend_config``."""
    value = getattr(config, key, None)
    if value is None or value == "":
        backend = getattr(config, "backend_config", None) or {}
        value = backend.get(key)
    return default if value is None or value == "" else value
