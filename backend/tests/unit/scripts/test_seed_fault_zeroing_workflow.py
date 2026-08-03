from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SEED_PATH = REPO_ROOT / "scripts" / "seed_fault_zeroing_workflow.py"
BUNDLED_YAML = REPO_ROOT / "workflows" / "fault-zeroing.yaml"


def load_seed_script():
    spec = importlib.util.spec_from_file_location("seed_fault_zeroing_workflow", SEED_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_script_parses_bundled_yaml() -> None:
    seed = load_seed_script()

    definition = seed.parse_bundled_workflow(BUNDLED_YAML)

    assert definition["name"] == "fault-zeroing"
    assert len(definition["nodes"]) == 11


@pytest.mark.asyncio
async def test_seed_creates_definition_when_absent() -> None:
    seed = load_seed_script()
    store = AsyncMock()
    store.get_latest_definition.return_value = None
    save = AsyncMock(return_value=SimpleNamespace(version=1))
    store.save_definition = save

    result = await seed.seed_workflow(store, BUNDLED_YAML, created_by="admin")

    assert result["status"] == "created"
    assert result["workflow_name"] == "fault-zeroing"
    assert result["version"] == 1
    save.assert_awaited_once()
    args = save.await_args.args
    assert args[0] == "fault-zeroing"
    assert args[3] == "admin"
    assert len(args[2]) == 64


@pytest.mark.asyncio
async def test_seed_skips_when_content_hash_matches() -> None:
    seed = load_seed_script()
    store = AsyncMock()
    existing = SimpleNamespace(version=3, content_hash=seed.content_hash(BUNDLED_YAML))
    store.get_latest_definition.return_value = existing

    result = await seed.seed_workflow(store, BUNDLED_YAML, created_by="admin")

    assert result["status"] == "skipped"
    assert result["version"] == 3
    store.save_definition.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_creates_new_version_when_hash_differs() -> None:
    seed = load_seed_script()
    store = AsyncMock()
    store.get_latest_definition.return_value = SimpleNamespace(version=2, content_hash="old-hash")
    save = AsyncMock(return_value=SimpleNamespace(version=3))
    store.save_definition = save

    result = await seed.seed_workflow(store, BUNDLED_YAML, created_by="admin")

    assert result["status"] == "created"
    assert result["version"] == 3
    save.assert_awaited_once()


def test_seed_rejects_invalid_yaml() -> None:
    seed = load_seed_script()
    bad_path = REPO_ROOT / "backend" / "config.example.yaml"

    with pytest.raises(ValueError, match="Invalid workflow YAML"):
        seed.parse_bundled_workflow(bad_path)
