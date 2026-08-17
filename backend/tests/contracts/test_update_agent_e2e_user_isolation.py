"""End-to-end verification for update_agent's user_id resolution.

PR #2784 hardened setup_agent to prefer runtime.context["user_id"] over the
contextvar. update_agent had the same latent gap: it unconditionally called
get_effective_user_id() at module level, so any scenario where the contextvar
was unavailable while runtime.context carried user_id (a background task
scheduled outside the request task, a worker pool that doesn't copy_context,
checkpoint resume on a different task) would silently route writes to
users/default/agents/...

In canonical mode both tools address resources through the catalog and
resolve the acting user via ``resolve_runtime_user_id(runtime)``. These
tests are load-bearing under @no_auto_user (contextvar empty):

- The negative-control test confirms the fixture actually puts the tool in
  the regime where the user_id fallback would resolve to the default user.
  Without that, the positive test would be vacuously satisfied.
- The positive test verifies update_agent honours runtime.context["user_id"]
  injected by inject_authenticated_user_context in the gateway — the update
  only succeeds when it resolves the same actor that owns the catalog agent.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from _agent_e2e_helpers import build_single_tool_call_model
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.services import (
    build_run_config,
    inject_authenticated_user_context,
    merge_run_context_overrides,
)
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource
from ideer.persistence.models.user import UserModel, UserRole
from ideer.runtime.runs.worker import _build_runtime_context, _install_runtime_context


def _make_request(user_id_str: str | None) -> SimpleNamespace:
    user = SimpleNamespace(id=UUID(user_id_str), email="alice@local") if user_id_str else None
    return SimpleNamespace(state=SimpleNamespace(user=user))


def _assemble_config(*, body_context: dict | None, request_user_id: str | None, thread_id: str) -> dict:
    config = build_run_config(thread_id, {"recursion_limit": 50}, None, assistant_id="lead_agent")
    merge_run_context_overrides(config, body_context)
    inject_authenticated_user_context(config, _make_request(request_user_id))
    return config


def _make_paths_mock(tmp_path: Path):
    paths = MagicMock()
    paths.base_dir = tmp_path
    return paths


@pytest_asyncio.fixture
async def catalog_db(tmp_path: Path) -> AsyncIterator[async_sessionmaker]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_user(catalog_db: async_sessionmaker, user_id: str) -> None:
    async with catalog_db() as session:
        existing = (await session.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
        if existing is None:
            session.add(UserModel(id=user_id, username=f"{user_id}@test.com", role=UserRole.USER, disabled=False))
            await session.commit()


def _create_canonical_agent(tmp_path: Path, catalog_db: async_sessionmaker, name: str, *, owner_id: str, soul: str, description: str) -> None:
    """Create a canonical catalog agent via the real setup_agent tool.

    setup_agent.func is a synchronous tool that runs its own asyncio.run
    internally — call it directly from a sync test (no running event loop),
    and never wrap it in another asyncio.run. The catalog user owning the
    agent is seeded here so setup_agent's owner check passes.
    """
    from ideer.tools.builtins.setup_agent_tool import setup_agent

    asyncio.run(_seed_user(catalog_db, owner_id))
    with (
        patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=catalog_db),
        patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
    ):
        runtime = SimpleNamespace(context={"agent_name": name, "user_id": owner_id}, tool_call_id="tool-setup")
        result = setup_agent.func(soul=soul, description=description, runtime=runtime)
        assert "created_agent_resource_id" in result.update, f"setup_agent failed: {result.update}"


async def _assert_agent_version(catalog_db: async_sessionmaker, slug: str, version: int) -> None:
    async with catalog_db() as session:
        resource = (await session.execute(select(Resource).where(Resource.type == "agent", Resource.slug == slug))).scalar_one_or_none()
        assert resource is not None, f"no catalog agent with slug {slug!r}"
        assert resource.latest_version == version, f"agent {slug!r} at version {resource.latest_version}, expected {version}"


def _patch_update_agent_dependencies(tmp_path: Path, catalog_db: async_sessionmaker):
    """update_agent reads get_app_config — stub it minimally so the tool can
    run without a real config file or LLM. The catalog session is real."""
    fake_model_cfg = SimpleNamespace(name="fake-model")
    fake_app_cfg = MagicMock()
    fake_app_cfg.get_model_config = lambda name: fake_model_cfg if name == "fake-model" else None

    return [
        patch(
            "ideer.tools.builtins.update_agent_tool.get_paths",
            return_value=_make_paths_mock(tmp_path),
        ),
        patch(
            "ideer.tools.builtins.update_agent_tool.get_app_config",
            return_value=fake_app_cfg,
        ),
        patch(
            "ideer.tools.builtins.update_agent_tool.get_session_factory",
            return_value=catalog_db,
        ),
    ]


def _build_update_graph(*, soul_payload: str):
    from langchain.agents import create_agent

    from ideer.tools.builtins.update_agent_tool import update_agent

    fake_model = build_single_tool_call_model(
        tool_name="update_agent",
        tool_args={"soul": soul_payload, "description": "refined"},
        tool_call_id="call_update_1",
        final_text="updated",
    )
    return create_agent(model=fake_model, tools=[update_agent], system_prompt="updater")


def _run_graph(graph, config: dict, *, expect_success: bool, slug: str, catalog_db: async_sessionmaker) -> None:
    from langgraph.runtime import Runtime

    thread_id = config["configurable"]["thread_id"]
    runtime_ctx = _build_runtime_context(thread_id, "run-1", config.get("context"), None)
    _install_runtime_context(config, runtime_ctx)
    runtime = Runtime(context=runtime_ctx, store=None)
    config.setdefault("configurable", {})["__pregel_runtime"] = runtime

    tmp_path = Path(config["configurable"]["tmp_root"])

    with ExitStack() as stack:
        for p in _patch_update_agent_dependencies(tmp_path, catalog_db):
            stack.enter_context(p)
        graph.invoke(
            {"messages": [HumanMessage(content="update agent")]},
            config=config,
        )

    asyncio.run(_assert_agent_version(catalog_db, slug, 2 if expect_success else 1))


# ---------------------------------------------------------------------------
# Negative control — proves the test environment puts update_agent in the
# regime where the user_id fallback would resolve to the default user.
# ---------------------------------------------------------------------------


@pytest.mark.no_auto_user
def test_update_agent_falls_back_to_default_when_no_inject_and_no_contextvar(tmp_path: Path, catalog_db: async_sessionmaker):
    """No request.state.user, no contextvar — update_agent must fail because
    the fallback user does not own the catalog agent. The agent stays at
    version 1 (no update applied)."""
    auth_uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    asyncio.run(_seed_user(catalog_db, auth_uid))
    _create_canonical_agent(tmp_path, catalog_db, "fallback-target", owner_id=auth_uid, soul="# Original", description="old")

    config = _assemble_config(
        body_context={"agent_name": "fallback-target"},
        request_user_id=None,  # no auth, inject is no-op
        thread_id="thread-update-1",
    )
    config.setdefault("configurable", {})["thread_id"] = "thread-update-1"
    config.setdefault("configurable", {})["tmp_root"] = str(tmp_path)

    graph = _build_update_graph(soul_payload="# Fallback Updated")
    _run_graph(graph, config, expect_success=False, slug="fallback-target", catalog_db=catalog_db)


# ---------------------------------------------------------------------------
# Regression guard — passes on this branch, would fail on main before the fix.
# ---------------------------------------------------------------------------


@pytest.mark.no_auto_user
def test_update_agent_should_use_runtime_context_user_id_when_contextvar_missing(tmp_path: Path, catalog_db: async_sessionmaker):
    """update_agent prefers the authenticated user_id carried in
    runtime.context (placed there by inject_authenticated_user_context)
    over the contextvar — same contract as setup_agent (PR #2784).

    Before this PR's fix, update_agent unconditionally called
    get_effective_user_id() and landed in default/ whenever the contextvar
    was unavailable. This test pins the corrected behaviour.
    """
    auth_uid = "abcdef01-2345-6789-abcd-ef0123456789"
    asyncio.run(_seed_user(catalog_db, auth_uid))
    _create_canonical_agent(tmp_path, catalog_db, "shared-name", owner_id=auth_uid, soul="# Original", description="old")

    config = _assemble_config(
        body_context={"agent_name": "shared-name"},
        request_user_id=auth_uid,
        thread_id="thread-update-2",
    )
    runtime_ctx = _build_runtime_context("thread-update-2", "run-2", config.get("context"), None)
    assert runtime_ctx["user_id"] == auth_uid, "Pre-condition: inject must have placed user_id into runtime_ctx"
    config.setdefault("configurable", {})["thread_id"] = "thread-update-2"
    config.setdefault("configurable", {})["tmp_root"] = str(tmp_path)

    graph = _build_update_graph(soul_payload="# Auth Updated")
    _run_graph(graph, config, expect_success=True, slug="shared-name", catalog_db=catalog_db)


# ---------------------------------------------------------------------------
# Positive — when contextvar IS the auth user (the normal HTTP case), things
# already work. Pin it as a regression guard so future refactors don't
# accidentally break the contextvar path in pursuit of the runtime-context fix.
# ---------------------------------------------------------------------------


def test_update_agent_uses_contextvar_when_present(tmp_path: Path, monkeypatch, catalog_db: async_sessionmaker):
    """The normal HTTP case: contextvar is set by auth_middleware. This must
    keep working regardless of how runtime.context is populated."""
    from types import SimpleNamespace as _SN

    from ideer.runtime.user_context import reset_current_user, set_current_user

    auth_uid = "11112222-3333-4444-5555-666677778888"
    asyncio.run(_seed_user(catalog_db, auth_uid))
    _create_canonical_agent(tmp_path, catalog_db, "ctxvar-agent", owner_id=auth_uid, soul="# Original", description="old")
    user = _SN(id=auth_uid, email="ctxvar@local")

    config = _assemble_config(
        body_context={"agent_name": "ctxvar-agent"},
        request_user_id=auth_uid,
        thread_id="thread-update-3",
    )
    config.setdefault("configurable", {})["thread_id"] = "thread-update-3"
    config.setdefault("configurable", {})["tmp_root"] = str(tmp_path)

    graph = _build_update_graph(soul_payload="# CtxVar Updated")

    token = set_current_user(user)
    try:
        _run_graph(graph, config, expect_success=True, slug="ctxvar-agent", catalog_db=catalog_db)
    finally:
        reset_current_user(token)
