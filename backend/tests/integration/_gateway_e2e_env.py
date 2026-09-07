"""Staging helpers for gateway-level integration tests.

New E2E tests that boot the real FastAPI app stage their environment through
this module so the process-singleton reset boundary has one canonical
implementation (``tests/integration/conftest.py`` exposes it as fixtures).
The two older lifecycle suites keep local copies; converge them here when
they next change.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

MINIMAL_CONFIG_YAML = """\
log_level: info
models:
  - name: fake-test-model
    display_name: Fake Test Model
    use: langchain_openai:ChatOpenAI
    model: gpt-4o-mini
    api_key: $OPENAI_API_KEY
    base_url: $OPENAI_API_BASE
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
agents_api:
  enabled: true
title:
  enabled: false
memory:
  enabled: false
database:
  backend: sqlite
run_events:
  backend: memory
"""


def stage_isolated_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    config_yaml: str = MINIMAL_CONFIG_YAML,
) -> Path:
    """Stage a temporary DEER_FLOW_HOME + config + extensions config."""
    home = tmp_path / "ideer-home"
    home.mkdir()
    monkeypatch.setenv("DEER_FLOW_HOME", str(home))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-key-not-used")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.invalid")

    staged_config = tmp_path / "config.yaml"
    staged_config.write_text(config_yaml, encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_CONFIG_PATH", str(staged_config))

    staged_extensions_config = tmp_path / "extensions_config.json"
    staged_extensions_config.write_text('{"mcpServers": {}, "skills": {}}', encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(staged_extensions_config))
    return home


def reset_process_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear runtime singletons that depend on the staged temporary config.

    The Gateway app/lifespan path reads process-wide caches before wiring
    request-scoped dependencies, so every cached object derived from the
    previous test's config/home must be dropped before ``create_app()``.
    """

    from app.gateway import deps as deps_module
    from app.gateway.routers import auth as auth_router_module
    from deerflow.config import app_config as app_config_module
    from deerflow.config import extensions_config as extensions_config_module
    from deerflow.config import paths as paths_module
    from deerflow.persistence import engine as engine_module

    for module, attr, value in (
        (app_config_module, "_app_config", None),
        (app_config_module, "_app_config_path", None),
        (app_config_module, "_app_config_mtime", None),
        (app_config_module, "_app_config_is_custom", False),
        (extensions_config_module, "_extensions_config", None),
        (paths_module, "_paths_singleton", None),
        (paths_module, "_paths", None),
        (engine_module, "_engine", None),
        (engine_module, "_session_factory", None),
        (deps_module, "_cached_local_provider", None),
        (deps_module, "_cached_repo", None),
        # Per-IP registration limiter is process-wide; without a reset the
        # 4th registration in a file would trip the production 3/hour cap.
        (auth_router_module, "_registration_attempts", {}),
    ):
        monkeypatch.setattr(module, attr, value, raising=False)


def preserve_process_config_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore config singletons mutated as a side effect of AppConfig loading.

    ``AppConfig.from_file()`` calls ``_apply_singleton_configs()``, which pushes
    nested config sections into module-level caches used by middlewares, tool
    selection, and runtime providers. Snapshotting those attributes with
    ``monkeypatch`` lets pytest restore the pre-test values during teardown, so
    loading the isolated test config does not leak into later tests.
    """

    from deerflow.config import (
        acp_config,
        checkpointer_config,
        guardrails_config,
        memory_config,
        stream_bridge_config,
        subagents_config,
        summarization_config,
        title_config,
        tool_search_config,
    )

    for module, attr in (
        (title_config, "_title_config"),
        (summarization_config, "_summarization_config"),
        (memory_config, "_memory_config"),
        (subagents_config, "_subagents_config"),
        (tool_search_config, "_tool_search_config"),
        (guardrails_config, "_guardrails_config"),
        (checkpointer_config, "_checkpointer_config"),
        (stream_bridge_config, "_stream_bridge_config"),
        (acp_config, "_acp_agents"),
    ):
        monkeypatch.setattr(module, attr, getattr(module, attr), raising=False)


def register_user(client: TestClient, *, email: str = "runtime-e2e@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "very-strong-password-123"},
    )
    assert response.status_code == 201, response.text
    csrf_token = client.cookies.get("csrf_token")
    assert csrf_token
    return csrf_token


def auth_user_id(client: TestClient) -> str:
    return client.get("/api/v1/auth/me").json()["id"]


def create_thread(client: TestClient, csrf_token: str) -> str:
    import uuid

    thread_id = str(uuid.uuid4())
    response = client.post(
        "/api/threads",
        json={"thread_id": thread_id, "metadata": {"purpose": "gateway-e2e"}},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200, response.text
    return thread_id
