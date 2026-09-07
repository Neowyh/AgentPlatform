"""Shared fixtures for integration tests that boot the real gateway app.

The staging helpers live in ``backend/tests/_gateway_e2e_env.py``; the two
older lifecycle suites still carry local copies of these fixtures and shadow
them at module level until they are converged.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _gateway_e2e_env import (
    preserve_process_config_singletons,
    reset_process_singletons,
    stage_isolated_home,
)


@pytest.fixture
def isolated_deer_flow_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return stage_isolated_home(tmp_path, monkeypatch)


@pytest.fixture
def isolated_app(isolated_deer_flow_home: Path, monkeypatch: pytest.MonkeyPatch):
    preserve_process_config_singletons(monkeypatch)
    reset_process_singletons(monkeypatch)

    from deerflow.config import app_config as app_config_module

    cfg = app_config_module.get_app_config()
    cfg.database.sqlite_dir = str(isolated_deer_flow_home / "db")

    from app.gateway.app import create_app

    return create_app()
