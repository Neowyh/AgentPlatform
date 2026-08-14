"""Unit tests for resolve_shared_agent_adapters (workflow worker).

The worker registry only contains the runner's own agents; this step adds
shared agents (owned by another user) when the runner has RBAC visibility,
so workflow nodes referencing them resolve instead of failing with
"unknown agent adapter".
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.workflow_worker import resolve_shared_agent_adapters
from ideer.workflows.v2.adapters import ActionAdapterRegistry


class _FakeRow:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, row) -> None:
        self._row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        return _FakeRow(self._row)


class _FakeSessionFactory:
    def __init__(self, row) -> None:
        self._row = row

    def __call__(self):
        return _FakeSession(self._row)


def _definition(*agent_names: str) -> SimpleNamespace:
    nodes: list[SimpleNamespace] = []
    for name in agent_names:
        nodes.append(
            SimpleNamespace(
                id=f"node-{name}",
                type="action",
                action=SimpleNamespace(kind="agent", name=name),
            )
        )
    nodes.append(SimpleNamespace(id="finish", type="action", action=SimpleNamespace(kind="tool", name="finish")))
    return SimpleNamespace(nodes=nodes)


def _runner_row(user_id: str = "runner-1") -> SimpleNamespace:
    return SimpleNamespace(id=user_id, role="user", department_id=None)


@pytest.mark.asyncio
async def test_registers_public_shared_agent_with_owner(tmp_path) -> None:
    definition = _definition("fault-zeroing")
    registry = ActionAdapterRegistry({("tool", "finish"): object()})
    owner_dir = tmp_path / "users" / "owner-1" / "agents" / "fault-zeroing"
    owner_dir.mkdir(parents=True)

    with (
        patch("app.gateway.utils.ResourceMetadataStore") as mock_store_cls,
        patch("ideer.config.paths.get_paths") as mock_paths,
        patch("ideer.persistence.engine.get_session_factory", return_value=_FakeSessionFactory(_runner_row())),
    ):
        mock_store_cls.return_value.load_meta = AsyncMock(return_value={"visibility": "public", "owner_id": "owner-1", "department_id": None})
        mock_paths.return_value.user_agent_dir = lambda owner_id, name: owner_dir

        await resolve_shared_agent_adapters(definition, registry, "runner-1")

    adapter = registry.resolve("agent", "fault-zeroing")
    assert adapter.name == "fault-zeroing"
    assert adapter.user_id == "runner-1"
    assert adapter.owner_id == "owner-1"


@pytest.mark.asyncio
async def test_skips_private_shared_agent(tmp_path) -> None:
    definition = _definition("fault-zeroing")
    registry = ActionAdapterRegistry({("tool", "finish"): object()})
    owner_dir = tmp_path / "users" / "owner-1" / "agents" / "fault-zeroing"
    owner_dir.mkdir(parents=True)

    with (
        patch("app.gateway.utils.ResourceMetadataStore") as mock_store_cls,
        patch("ideer.config.paths.get_paths") as mock_paths,
        patch("ideer.persistence.engine.get_session_factory", return_value=_FakeSessionFactory(_runner_row())),
    ):
        mock_store_cls.return_value.load_meta = AsyncMock(return_value={"visibility": "private", "owner_id": "owner-1", "department_id": None})
        mock_paths.return_value.user_agent_dir = lambda owner_id, name: owner_dir

        await resolve_shared_agent_adapters(definition, registry, "runner-1")

    with pytest.raises(Exception, match="unknown agent adapter 'fault-zeroing'"):
        registry.resolve("agent", "fault-zeroing")


@pytest.mark.asyncio
async def test_keeps_already_registered_agents(tmp_path) -> None:
    definition = _definition("my-agent", "fault-zeroing")
    existing = object()
    registry = ActionAdapterRegistry({("agent", "my-agent"): existing, ("tool", "finish"): object()})
    owner_dir = tmp_path / "users" / "owner-1" / "agents" / "fault-zeroing"
    owner_dir.mkdir(parents=True)

    with (
        patch("app.gateway.utils.ResourceMetadataStore") as mock_store_cls,
        patch("ideer.config.paths.get_paths") as mock_paths,
    ):
        mock_store_cls.return_value.load_meta = AsyncMock(return_value={"visibility": "public", "owner_id": "owner-1", "department_id": None})
        mock_paths.return_value.user_agent_dir = lambda owner_id, name: owner_dir

        await resolve_shared_agent_adapters(definition, registry, "runner-1")

    assert registry.resolve("agent", "my-agent") is existing
    mock_store_cls.return_value.load_meta.assert_awaited_once_with("fault-zeroing")


@pytest.mark.asyncio
async def test_noop_without_database_or_meta(tmp_path) -> None:
    definition = _definition("fault-zeroing")
    registry = ActionAdapterRegistry({("tool", "finish"): object()})

    with (
        patch("app.gateway.utils.ResourceMetadataStore") as mock_store_cls,
        patch("ideer.persistence.engine.get_session_factory", return_value=None),
    ):
        mock_store_cls.return_value.load_meta = AsyncMock(return_value={})

        await resolve_shared_agent_adapters(definition, registry, "runner-1")

    with pytest.raises(Exception, match="unknown agent adapter 'fault-zeroing'"):
        registry.resolve("agent", "fault-zeroing")
