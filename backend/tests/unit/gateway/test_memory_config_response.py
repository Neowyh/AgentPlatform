from __future__ import annotations

from app.gateway.routers.memory import _memory_config_response
from deerflow.config.memory_config import MemoryConfig


def test_memory_config_response_exposes_deerflow_schema_and_legacy_projection() -> None:
    response = _memory_config_response(
        MemoryConfig(
            enabled=True,
            mode="tool",
            injection_enabled=False,
            shutdown_flush_timeout_seconds=45,
            manager_class="deermem",
            backend_config={
                "storage_path": ".deer-flow/memory",
                "max_facts": 42,
                "max_injection_tokens": 1200,
            },
        )
    )

    assert response.mode == "tool"
    assert response.manager_class == "deermem"
    assert response.shutdown_flush_timeout_seconds == 45
    assert response.backend_config["storage_path"] == ".deer-flow/memory"
    assert response.storage_path == ".deer-flow/memory"
    assert response.max_facts == 42
    assert response.max_injection_tokens == 1200
