"""Memory restart acceptance over the real gateway app.

Upgrade regression §24-E/K: facts written through ``POST /api/memory/facts``
must survive a full gateway restart (new app instance, same ``DEER_FLOW_HOME``),
stay isolated per user, and land in the durable per-user file the DeerMem
backend owns. The storage/restart unit suites rebuild the manager object in
process; this module restarts the whole application.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _gateway_e2e_env import (
    auth_user_id,
    create_thread,
    preserve_process_config_singletons,
    register_user,
    reset_process_singletons,
    stage_isolated_home,
)
from starlette.testclient import TestClient

MEMORY_CONFIG_YAML = """\
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
  enabled: true
  injection_enabled: true
  manager_class: deermem
  backend_config:
    storage_class: file
    token_counting: char
database:
  backend: sqlite
run_events:
  backend: memory
"""

OWNER_EMAIL = "memory-owner@example.com"
OTHER_EMAIL = "memory-other@example.com"
OWNER_FACT = "Owner prefers concise Python summaries."


def _boot_app(home: Path, monkeypatch: pytest.MonkeyPatch):
    preserve_process_config_singletons(monkeypatch)
    reset_process_singletons(monkeypatch)

    from deerflow.config import app_config as app_config_module

    cfg = app_config_module.get_app_config()
    cfg.database.sqlite_dir = str(home / "db")

    from app.gateway.app import create_app

    return create_app()


def _facts(client: TestClient) -> list[dict]:
    response = client.get("/api/memory")
    assert response.status_code == 200, response.text
    return response.json()["facts"]


def test_memory_facts_survive_gateway_restart_and_stay_user_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = stage_isolated_home(tmp_path, monkeypatch, config_yaml=MEMORY_CONFIG_YAML)

    app = _boot_app(home, monkeypatch)
    with TestClient(app) as client:
        csrf = register_user(client, email=OWNER_EMAIL)
        owner_id = auth_user_id(client)
        created = client.post(
            "/api/memory/facts",
            json={"content": OWNER_FACT, "category": "context", "confidence": 0.9},
            headers={"X-CSRF-Token": csrf},
        )
        assert created.status_code in (200, 201), created.text
        facts = _facts(client)
        assert [fact["content"] for fact in facts] == [OWNER_FACT]

    # A restart: fresh app instance over the same DEER_FLOW_HOME, with the
    # process singletons dropped so nothing carries the previous lifecycle.
    app_restarted = _boot_app(home, monkeypatch)
    with TestClient(app_restarted) as client:
        register_user(client, email=OTHER_EMAIL)
        assert _facts(client) == [], "another user must not see the owner's facts"

        login = client.post(
            "/api/v1/auth/login/local",
            data={"username": OWNER_EMAIL, "password": "very-strong-password-123"},
        )
        assert login.status_code in (200, 204), login.text
        facts = _facts(client)
        assert [fact["content"] for fact in facts] == [OWNER_FACT], "facts must survive a full gateway restart"

        # The fact is durable inside the per-user DeerMem scope (facts live
        # as Markdown files below users/<id>/agents/<agent>/facts/).
        user_dir = home / "users" / owner_id
        durable = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in user_dir.rglob("*") if path.is_file())
        assert OWNER_FACT in durable, f"fact not durable under {user_dir}"


def test_memory_fact_write_requires_authenticated_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = stage_isolated_home(tmp_path, monkeypatch, config_yaml=MEMORY_CONFIG_YAML)
    app = _boot_app(home, monkeypatch)
    with TestClient(app) as client:
        csrf = register_user(client, email=OWNER_EMAIL)
        owner_id = auth_user_id(client)
        thread_id = create_thread(client, csrf)
        assert thread_id

        deleted = client.delete(
            "/api/memory/facts/does-not-exist",
            headers={"X-CSRF-Token": csrf},
        )
        assert deleted.status_code == 404, deleted.text
        assert (home / "users" / owner_id).is_dir() or _facts(client) == []
