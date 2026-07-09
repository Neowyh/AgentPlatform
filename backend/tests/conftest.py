"""Test configuration for the backend test suite.

Sets up sys.path and pre-mocks modules that would cause circular import
issues when unit-testing lightweight config/registry code in isolation.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dotenv import load_dotenv

# Load .env from project root (for OPENAI_API_KEY etc.)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Make 'app' and 'ideer' importable from any working directory
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

# Make test helpers (e.g. _router_auth_helpers) importable from test modules
sys.path.insert(0, str(Path(__file__).parent))

# Break the circular import chain that exists in production code:
#   ideer.subagents.__init__
#     -> .executor (SubagentExecutor, SubagentResult)
#       -> ideer.agents.thread_state
#         -> ideer.agents.__init__
#           -> lead_agent.agent
#             -> subagent_limit_middleware
#               -> ideer.subagents.executor  <-- circular!
#
# By injecting a mock for ideer.subagents.executor *before* any test module
# triggers the import, __init__.py's "from .executor import ..." succeeds
# immediately without running the real executor module.
_executor_mock = MagicMock()
_executor_mock.SubagentExecutor = MagicMock
_executor_mock.SubagentResult = MagicMock
_executor_mock.SubagentStatus = MagicMock
_executor_mock.MAX_CONCURRENT_SUBAGENTS = 3
_executor_mock.get_background_task_result = MagicMock()

sys.modules["ideer.subagents.executor"] = _executor_mock

# Capture initial API key state BEFORE any test module imports ideer.client
# (which sets OPENAI_API_KEY as a side effect from config.yaml/.env loading).
# This lets _skip_llm_if_no_key reliably detect "no user-supplied key".
_initial_openai_api_key = os.environ.get("OPENAI_API_KEY")


# ---------------------------------------------------------------------------
# Shared test fixtures — reduce mock boilerplate across test files
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_app_config():
    """Unified application config mock for tests."""
    config = MagicMock()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4"
    config.sandbox.enabled = True
    return config


@pytest.fixture()
def mock_http_client():
    """Unified HTTP client mock for tests."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={})))
    client.post = AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={})))
    return client


@pytest.fixture()
def mock_db_session():
    """Unified database session mock for tests."""
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture()
def mock_db_session_factory():
    """Factory fixture that returns a (mock_session, mock_session_factory) pair.

    Usage in tests::

        def test_something(mock_db_session_factory):
            mock_session, mock_sf = mock_db_session_factory(scalar_result=some_user)
            # mock_sf can be used as a session factory dependency
    """

    def _factory(scalar_result=None):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = scalar_result
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)
        return mock_session, mock_sf

    return _factory


@pytest.fixture()
def mock_sse_bridge():
    """Unified SSE bridge mock for run-worker tests."""
    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()
    return bridge


@pytest.fixture()
def mock_run_manager():
    """Unified run manager mock for run-worker tests."""
    manager = MagicMock()
    manager.set_status = AsyncMock()
    manager.update_model_name = AsyncMock()
    manager.update_run_completion = AsyncMock()
    return manager


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
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Auto-set user context for every test unless marked no_auto_user
# ---------------------------------------------------------------------------
#
# Repository methods read ``user_id`` from a contextvar by default
# (see ``ideer.runtime.user_context``). Without this fixture, every
# pre-existing persistence test would raise RuntimeError because the
# contextvar is unset. The fixture sets a default test user on every
# test; tests that explicitly want to verify behaviour *without* a user
# context should mark themselves ``@pytest.mark.no_auto_user``.


@pytest.fixture(autouse=True)
def _reset_skill_storage_singleton():
    """Reset the SkillStorage singleton between tests to prevent cross-test contamination."""
    try:
        from ideer.skills.storage import reset_skill_storage
    except ImportError:
        yield
        return
    reset_skill_storage()
    try:
        yield
    finally:
        reset_skill_storage()


@pytest.fixture(autouse=True)
def _reset_registration_attempts():
    """Reset the in-process registration rate limit state between tests.

    ``_registration_attempts`` is a module-level dict in
    ``app.gateway.routers.auth`` that accumulates per-IP counters. Without
    this cleanup, a test that triggers registration can leak state into
    subsequent tests and cause spurious 429 errors.
    """
    try:
        import app.gateway.routers.auth as auth_mod

        auth_mod._registration_attempts.clear()
    except ImportError:
        pass
    yield
    try:
        import app.gateway.routers.auth as auth_mod

        auth_mod._registration_attempts.clear()
    except ImportError:
        pass


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
        from ideer.config.title_config import reset_title_config
    except ImportError:
        yield
        return

    try:
        yield
    finally:
        reset_title_config()


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
        from ideer.runtime.user_context import (
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


# ---------------------------------------------------------------------------
# LLM test helpers — skip, serialise, and throttle
# ---------------------------------------------------------------------------
#
# Tests marked ``@pytest.mark.requires_llm`` hit a real LLM API (Mimo by
# default).  Three concerns:
#
# 1. **Skip when no key** — CI and local runs without OPENAI_API_KEY should
#    skip, not fail.  The ``_skip_llm_if_no_key`` fixture handles this.
#
# 2. **Serialise** — LLM tests must not run in parallel (no pytest-xdist
#    today, but future-proofing).  The ``_llm_rate_limit`` fixture enforces
#    a minimum gap between consecutive LLM calls.
#
# 3. **Retry on transient failure** — API rate-limits and network blips
#    cause occasional failures.  ``pytest_collection_modifyitems`` adds
#    ``pytest.mark.flaky(reruns=2, reruns_delay=5)`` so pytest-rerunfailures
#    retries them automatically.


@pytest.fixture(autouse=True)
def _skip_llm_if_no_key(request):
    """Auto-skip ``requires_llm`` tests when no API key is available."""
    if request.node.get_closest_marker("requires_llm"):
        if os.getenv("CI", "").lower() in ("true", "1") or not _initial_openai_api_key:
            pytest.skip("Requires LLM API key — skipped in CI or when OPENAI_API_KEY is unset")
    yield


_llm_test_last_run: list[float] = [0.0]


@pytest.fixture(autouse=True)
def _llm_rate_limit(request):
    """Serialise ``requires_llm`` tests and enforce a minimum interval.

    Prevents hitting Mimo API rate-limits when the full suite runs.
    Non-LLM tests pass through with zero overhead.
    """
    if request.node.get_closest_marker("requires_llm"):
        gap = 1.5  # seconds between LLM calls
        elapsed = time.monotonic() - _llm_test_last_run[0]
        if elapsed < gap:
            time.sleep(gap - elapsed)
        yield
        _llm_test_last_run[0] = time.monotonic()
    else:
        yield


# ---------------------------------------------------------------------------
# Shared RBAC user fixtures — reduce boilerplate across permission-matrix tests
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str | None = None,
    role: str = "user",
    department_id: str | None = None,
    disabled: bool = False,
    username: str | None = None,
) -> MagicMock:
    """Create a mock RBAC UserModel (shared helper, not a fixture)."""
    from datetime import datetime

    uid = user_id or str(uuid4())
    user = MagicMock()
    user.id = uid
    user.email = f"{username or f'user-{uid[:8]}'}@test.com"
    user.role = role
    user.department_id = department_id
    user.disabled = disabled
    user.username = username or f"user-{uid[:8]}"
    user.created_at = datetime.now(tz=UTC)
    user.last_login = datetime.now(tz=UTC)
    user.department = MagicMock()
    user.department.id = department_id
    return user


@pytest.fixture
def super_admin_user() -> MagicMock:
    return _make_rbac_user(role="super_admin", department_id=None)


@pytest.fixture
def dept_admin_user() -> MagicMock:
    return _make_rbac_user(role="department_admin", department_id="dept-1")


@pytest.fixture
def regular_user() -> MagicMock:
    return _make_rbac_user(role="user", department_id="dept-1")


@pytest.fixture
def viewer_user() -> MagicMock:
    return _make_rbac_user(role="viewer", department_id="dept-1")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Add flaky-rerun markers to ``requires_llm`` tests.

    pytest-rerunfailures will retry up to 2 times with a 5-second delay,
    absorbing transient rate-limit and network errors.
    """
    for item in items:
        if item.get_closest_marker("requires_llm"):
            item.add_marker(pytest.mark.flaky(reruns=2, reruns_delay=5))
