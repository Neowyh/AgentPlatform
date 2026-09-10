"""Test configuration for the backend test suite.

Sets up sys.path and pre-mocks modules that would cause circular import
issues when unit-testing lightweight config/registry code in isolation.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

try:
    import uvloop
except ImportError:  # pragma: no cover - uvicorn[standard] provides uvloop here
    pass
else:
    # The restricted runner cannot wake a selector loop from another thread.
    # Install the compatible policy before tests create their own event loops.
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="ideer-test-runtime-")
_TEST_RUNTIME_PATH = Path(_TEST_RUNTIME.name)


# Make 'app' and 'deerflow' importable from any working directory
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Give the ``requires_llm`` marker its skip semantics, globally.

    ``tests/test_client_e2e.py`` defines a local ``requires_llm = pytest.mark.skipif(...)``
    decorator, but other files (integration/API e2e, live-model units) annotate with the
    bare ``@pytest.mark.requires_llm`` marker, which without this hook never skips —
    so those tests really called the LLM in every lane run.  Evaluated at run setup
    (not import time) so a collection-order environment leak cannot re-enable them.
    """
    skip_requires_llm = pytest.mark.skipif(
        os.getenv("CI", "").lower() in ("true", "1") or not os.getenv("OPENAI_API_KEY"),
        reason="Requires LLM API key — skipped in CI or when OPENAI_API_KEY is unset",
    )
    for item in items:
        if "requires_llm" in item.keywords:
            item.add_marker(skip_requires_llm)


def _make_rbac_user(
    user_id: str | None = None,
    role: str = "user",
    department_id: str | None = None,
    disabled: bool = False,
    username: str | None = None,
) -> MagicMock:
    """Create the shared lightweight RBAC user used by contract tests.

    Keep this helper in ``conftest`` because contract modules import it as a
    top-level test support module when collected by the standard lane.
    """
    user = MagicMock()
    user.id = user_id or str(uuid4())
    user.role = role
    user.department_id = department_id
    user.disabled = disabled
    user.username = username or f"user-{user.id[:8]}"
    return user


# Break the circular import chain that exists in production code:
#   deerflow.subagents.__init__
#     -> .executor (SubagentExecutor, SubagentResult)
#       -> deerflow.agents.thread_state
#         -> deerflow.agents.__init__
#           -> lead_agent.agent
#             -> subagent_limit_middleware
#               -> deerflow.subagents.executor  <-- circular!
#
# By injecting a mock for deerflow.subagents.executor *before* any test module
# triggers the import, __init__.py's "from .executor import ..." succeeds
# immediately without running the real executor module.
_executor_mock = MagicMock()
_executor_mock.SubagentExecutor = MagicMock
_executor_mock.SubagentResult = MagicMock
_executor_mock.SubagentStatus = MagicMock
_executor_mock.MAX_CONCURRENT_SUBAGENTS = 3
_executor_mock.get_background_task_result = MagicMock()

sys.modules["deerflow.subagents.executor"] = _executor_mock


@pytest.fixture()
def provisioner_module():
    """Load docker/provisioner/app.py as an importable test module.

    Shared by test_provisioner_kubeconfig and test_provisioner_pvc_volumes so
    that any change to the provisioner entry-point path or module name only
    needs to be updated in one place.
    """
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "docker" / "provisioner" / "app.py"
    spec = importlib.util.spec_from_file_location("provisioner_app_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        if previous_module is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous_module


# ---------------------------------------------------------------------------
# Auto-set user context for every test unless marked no_auto_user
# ---------------------------------------------------------------------------
#
# Repository methods read ``user_id`` from a contextvar by default
# (see ``deerflow.runtime.user_context``). Without this fixture, every
# pre-existing persistence test would raise RuntimeError because the
# contextvar is unset. The fixture sets a default test user on every
# test; tests that explicitly want to verify behaviour *without* a user
# context should mark themselves ``@pytest.mark.no_auto_user``.


@pytest.fixture(autouse=True)
def _reset_skill_storage_singleton():
    """Reset the SkillStorage singleton between tests to prevent cross-test contamination."""
    try:
        from deerflow.skills.storage import reset_skill_storage
    except ImportError:
        yield
        return
    reset_skill_storage()
    try:
        yield
    finally:
        reset_skill_storage()


@pytest.fixture(autouse=True)
def _reset_frozen_checkpoint_channel_mode(monkeypatch):
    """Reset the process-global frozen checkpoint channel mode between tests.

    Production treats ``checkpoint_channel_mode`` (and the delta
    ``snapshot_frequency`` frozen alongside it) as restart-required: the
    first client/app freezes it for the process. The test suite builds many
    clients and apps with different modes in one process, so the freeze must
    not leak across tests. Mirrors the per-test ``monkeypatch.setattr``
    resets already used in test_client.py / test_lead_agent_model_resolution.py.
    """
    from deerflow.runtime import checkpoint_mode

    monkeypatch.setattr(checkpoint_mode, "_frozen_checkpoint_channel_mode", None)
    monkeypatch.setattr(checkpoint_mode, "_frozen_checkpoint_snapshot_frequency", None)
    yield


@pytest.fixture(autouse=True)
def _restore_title_config_singleton():
    """Reset ``_title_config`` to its pristine default after every test.

    ``AppConfig.from_file()`` writes the on-disk ``title`` block into the
    module-level singleton (``config/app_config.py`` calls
    ``load_title_config_from_dict``). Any test that loads the real
    ``config.yaml`` therefore leaves the singleton in a state that
    ``test_title_middleware_core_logic.py`` does not expect; that suite
    relies on the pristine ``TitleConfig()`` default (``enabled=True``).
    We restore the default after every test so test files stay
    independent regardless of order.
    """
    try:
        from deerflow.config.title_config import reset_title_config
    except ImportError:
        yield
        return

    try:
        yield
    finally:
        reset_title_config()


@pytest.fixture(autouse=True)
def _isolate_trace_context():
    """Give every test an unbound request trace context.

    Entry points bind a trace id unconditionally, and ``ensure_trace_id()``
    binds one for the remainder of whatever context it is called in. pytest
    runs the whole session in a single context, so without this reset one
    test's trace would leak into the next and quietly satisfy assertions
    about ids the test under exercise never bound.
    """
    from deerflow.trace_context import bind_trace_id, reset_trace_id

    token = bind_trace_id(None)
    try:
        yield
    finally:
        reset_trace_id(token)


@pytest.fixture(autouse=True)
def _reset_auth_throttle_state():
    """Reset process-wide auth throttle state around every test.

    The login lockout table (``_login_attempts``) and the per-IP
    ``/setup-status`` result cache are module globals. Without a reset the
    lockout accumulator leaks across test files (synthetic 429s once an IP
    crosses ``max_login_attempts``) and ``setup-status`` serves a stale
    needs_setup answer recorded by an earlier test.
    """
    try:
        from app.gateway import routers

        auth_router = routers.auth
    except (ImportError, AttributeError):
        yield
        return

    def _clear():
        getattr(auth_router, "_login_attempts", None) and auth_router._login_attempts.clear()
        getattr(auth_router, "_SETUP_STATUS_CACHE", None) and auth_router._SETUP_STATUS_CACHE.clear()
        getattr(auth_router, "_SETUP_STATUS_INFLIGHT", None) and auth_router._SETUP_STATUS_INFLIGHT.clear()

    _clear()
    yield
    _clear()


@pytest.fixture(autouse=True)
def _auto_user_context(request):
    """Inject a default ``test-user-autouse`` into the contextvar.

    Opt-out via ``@pytest.mark.no_auto_user``. Uses lazy import so that
    tests which don't touch the persistence layer never pay the cost
    of importing runtime.user_context.
    """
    if request.node.get_closest_marker("no_auto_user"):
        yield
        return

    try:
        from deerflow.runtime.user_context import (
            reset_current_user,
            set_current_user,
        )
    except ImportError:
        yield
        return

    user = SimpleNamespace(id="test-user-autouse", email="test@local")
    token = set_current_user(user)
    try:
        yield
    finally:
        reset_current_user(token)


@pytest.fixture(autouse=True)
def _use_uvloop_for_testclient(monkeypatch):
    """Use uvloop for TestClient's portal in the restricted test runner.

    The runner's default asyncio selector does not wake a loop from another
    thread, which leaves Starlette's synchronous TestClient waiting forever.
    uvloop provides the same asyncio API while preserving the cross-thread
    wakeup that TestClient requires. This is test-only; application runtime
    event-loop configuration is unchanged.
    """
    from starlette.testclient import TestClient

    original_init = TestClient.__init__

    @wraps(original_init)
    def init_with_uvloop(self, *args, **kwargs):
        kwargs.setdefault("backend_options", {"use_uvloop": True})
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", init_with_uvloop)
    yield


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use uvloop for pytest-asyncio's loop in the restricted test runner.

    Async database drivers such as aiosqlite also notify the event loop from
    worker threads. The runner's default selector loop cannot receive those
    notifications, while uvloop supports the required cross-thread wakeup.
    """
    import uvloop

    return uvloop.EventLoopPolicy()


@pytest.fixture(scope="module")
def anyio_backend():
    """Run AnyIO tests on uvloop in the restricted test runner."""
    return ("asyncio", {"use_uvloop": True})


# ── Gateway-level integration fixtures ──────────────────────────────────────
# Staging helpers live in ``tests/_gateway_e2e_env.py``. Defined here (root
# conftest) rather than a nested conftest so the module name ``conftest``
# keeps resolving to this file for suites that import from it directly.


@pytest.fixture
def isolated_deer_flow_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from _gateway_e2e_env import stage_isolated_home

    return stage_isolated_home(tmp_path, monkeypatch)


@pytest.fixture
def isolated_app(isolated_deer_flow_home: Path, monkeypatch: pytest.MonkeyPatch):
    from _gateway_e2e_env import (
        preserve_process_config_singletons,
        reset_process_singletons,
    )

    preserve_process_config_singletons(monkeypatch)
    reset_process_singletons(monkeypatch)

    from deerflow.config import app_config as app_config_module

    cfg = app_config_module.get_app_config()
    cfg.database.sqlite_dir = str(isolated_deer_flow_home / "db")

    from app.gateway.app import create_app

    return create_app()


@pytest.fixture(autouse=True)
def _test_runtime_config(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.path.name.startswith("test_app_config"):
        return
    if os.getenv("DEER_FLOW_CONFIG_PATH"):
        return

    config_path = _TEST_RUNTIME_PATH / "config.yaml"
    if not config_path.is_file():
        repo_root = Path(__file__).resolve().parents[2]
        config_path.write_text(
            (repo_root / "config.example.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    monkeypatch.setenv("DEER_FLOW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEER_FLOW_HOME", str(_TEST_RUNTIME_PATH / "home"))
    extensions_path = _TEST_RUNTIME_PATH / "extensions_config.json"
    extensions_path.write_text('{"mcpServers": {}, "skills": {}}', encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(extensions_path))
