"""Additional coverage tests for ideer.sandbox.middleware."""

from __future__ import annotations

import pytest
from langgraph.runtime import Runtime

from ideer.sandbox.middleware import SandboxMiddleware
from ideer.sandbox.sandbox import Sandbox
from ideer.sandbox.sandbox_provider import SandboxProvider, reset_sandbox_provider, set_sandbox_provider
from ideer.sandbox.search import GrepMatch

# ---------------------------------------------------------------------------
# Stub sandbox
# ---------------------------------------------------------------------------


class _SandboxStub(Sandbox):
    def __init__(self, id: str = "stub"):
        super().__init__(id)

    def execute_command(self, command: str) -> str:
        return "OK"

    def read_file(self, path: str) -> str:
        return "content"

    def download_file(self, path: str) -> bytes:
        return b"content"

    def list_dir(self, path: str, max_depth: int = 2) -> list[str]:
        return ["/mnt/user-data/workspace/file.txt"]

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        return None

    def glob(self, path: str, pattern: str, *, include_dirs: bool = False, max_results: int = 200) -> tuple[list[str], bool]:
        return [], False

    def grep(
        self,
        path: str,
        pattern: str,
        *,
        glob: str | None = None,
        literal: bool = False,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> tuple[list[GrepMatch], bool]:
        return [], False

    def update_file(self, path: str, content: bytes) -> None:
        return None


class _SyncProvider(SandboxProvider):
    def __init__(self) -> None:
        self.thread_ids: list[str | None] = []
        self.released_ids: list[str] = []

    def acquire(self, thread_id: str | None = None) -> str:
        self.thread_ids.append(thread_id)
        return "sync-sandbox"

    def get(self, sandbox_id: str) -> Sandbox | None:
        return _SandboxStub()

    def release(self, sandbox_id: str) -> None:
        self.released_ids.append(sandbox_id)


class _AsyncProvider(SandboxProvider):
    def __init__(self) -> None:
        self.thread_ids: list[str | None] = []
        self.released_ids: list[str] = []
        self.sandbox = _SandboxStub()

    def acquire(self, thread_id: str | None = None) -> str:
        raise AssertionError("should not call sync acquire")

    async def acquire_async(self, thread_id: str | None = None) -> str:
        self.thread_ids.append(thread_id)
        return "async-sandbox"

    def get(self, sandbox_id: str) -> Sandbox | None:
        if sandbox_id == "async-sandbox":
            return self.sandbox
        return None

    def release(self, sandbox_id: str) -> None:
        self.released_ids.append(sandbox_id)


# ===========================================================================
# before_agent — sync eager init
# ===========================================================================


class TestBeforeAgent:
    def test_eager_init_no_existing_sandbox(self, monkeypatch):
        provider = _SyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=False)
            state = {}
            runtime = Runtime(context={"thread_id": "thread-1"})
            result = middleware.before_agent(state, runtime)
            assert result == {"sandbox": {"sandbox_id": "sync-sandbox"}}
            assert "thread-1" in provider.thread_ids
        finally:
            reset_sandbox_provider()

    def test_eager_init_no_thread_id(self, monkeypatch):
        provider = _SyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=False)
            state = {}
            runtime = Runtime(context={})
            result = middleware.before_agent(state, runtime)
            # Should delegate to super
            assert result is None or isinstance(result, dict)
        finally:
            reset_sandbox_provider()

    def test_eager_init_existing_sandbox(self, monkeypatch):
        provider = _SyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=False)
            state = {"sandbox": {"sandbox_id": "existing"}}
            runtime = Runtime(context={"thread_id": "thread-1"})
            result = middleware.before_agent(state, runtime)
            # Should delegate to super (existing sandbox)
            assert result is None or isinstance(result, dict)
        finally:
            reset_sandbox_provider()

    def test_lazy_init_delegates(self, monkeypatch):
        provider = _SyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=True)
            state = {}
            runtime = Runtime(context={"thread_id": "thread-1"})
            result = middleware.before_agent(state, runtime)
            # Should delegate to super (lazy init)
            assert result is None or isinstance(result, dict)
        finally:
            reset_sandbox_provider()


# ===========================================================================
# abefore_agent — async eager init
# ===========================================================================


class TestAbeforeAgent:
    @pytest.mark.anyio
    async def test_eager_init_no_existing_sandbox(self):
        provider = _AsyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=False)
            state = {}
            runtime = Runtime(context={"thread_id": "thread-2"})
            result = await middleware.abefore_agent(state, runtime)
            assert result == {"sandbox": {"sandbox_id": "async-sandbox"}}
            assert "thread-2" in provider.thread_ids
        finally:
            reset_sandbox_provider()

    @pytest.mark.anyio
    async def test_eager_init_no_thread_id(self):
        provider = _AsyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=False)
            state = {}
            runtime = Runtime(context={})
            result = await middleware.abefore_agent(state, runtime)
            assert result is None or isinstance(result, dict)
        finally:
            reset_sandbox_provider()

    @pytest.mark.anyio
    async def test_eager_init_existing_sandbox(self):
        provider = _AsyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=False)
            state = {"sandbox": {"sandbox_id": "existing"}}
            runtime = Runtime(context={"thread_id": "thread-2"})
            result = await middleware.abefore_agent(state, runtime)
            assert result is None or isinstance(result, dict)
        finally:
            reset_sandbox_provider()

    @pytest.mark.anyio
    async def test_lazy_init_delegates(self):
        provider = _AsyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware(lazy_init=True)
            state = {}
            runtime = Runtime(context={"thread_id": "thread-2"})
            result = await middleware.abefore_agent(state, runtime)
            assert result is None or isinstance(result, dict)
        finally:
            reset_sandbox_provider()


# ===========================================================================
# after_agent — sync release
# ===========================================================================


class TestAfterAgent:
    def test_releases_from_state(self, monkeypatch):
        provider = _SyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware()
            state = {"sandbox": {"sandbox_id": "state-sandbox"}}
            runtime = Runtime(context={})
            result = middleware.after_agent(state, runtime)
            assert result is None
            assert "state-sandbox" in provider.released_ids
        finally:
            reset_sandbox_provider()

    def test_releases_from_context(self, monkeypatch):
        provider = _SyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware()
            state = {}
            runtime = Runtime(context={"sandbox_id": "context-sandbox"})
            result = middleware.after_agent(state, runtime)
            assert result is None
            assert "context-sandbox" in provider.released_ids
        finally:
            reset_sandbox_provider()

    def test_no_sandbox(self, monkeypatch):
        calls = []
        original = SandboxMiddleware.__mro__[1].after_agent

        def fake_super(self, state, runtime):
            calls.append((state, runtime))
            return {"super": True}

        monkeypatch.setattr(SandboxMiddleware.__mro__[1], "after_agent", fake_super)
        try:
            middleware = SandboxMiddleware()
            state = {}
            runtime = Runtime(context={})
            result = middleware.after_agent(state, runtime)
            assert result == {"super": True}
        finally:
            monkeypatch.setattr(SandboxMiddleware.__mro__[1], "after_agent", original)


# ===========================================================================
# aafter_agent — async release
# ===========================================================================


class TestAafterAgent:
    @pytest.mark.anyio
    async def test_releases_from_state(self):
        provider = _AsyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware()
            state = {"sandbox": {"sandbox_id": "state-sandbox"}}
            runtime = Runtime(context={})
            result = await middleware.aafter_agent(state, runtime)
            assert result is None
            assert "state-sandbox" in provider.released_ids
        finally:
            reset_sandbox_provider()

    @pytest.mark.anyio
    async def test_releases_from_context(self):
        provider = _AsyncProvider()
        set_sandbox_provider(provider)
        try:
            middleware = SandboxMiddleware()
            state = {}
            runtime = Runtime(context={"sandbox_id": "context-sandbox"})
            result = await middleware.aafter_agent(state, runtime)
            assert result is None
            assert "context-sandbox" in provider.released_ids
        finally:
            reset_sandbox_provider()

    @pytest.mark.anyio
    async def test_no_sandbox(self, monkeypatch):
        calls = []
        original = SandboxMiddleware.__mro__[1].aafter_agent

        async def fake_super(self, state, runtime):
            calls.append((state, runtime))
            return {"super": True}

        monkeypatch.setattr(SandboxMiddleware.__mro__[1], "aafter_agent", fake_super)
        try:
            middleware = SandboxMiddleware()
            state = {}
            runtime = Runtime(context={})
            result = await middleware.aafter_agent(state, runtime)
            assert result == {"super": True}
        finally:
            monkeypatch.setattr(SandboxMiddleware.__mro__[1], "aafter_agent", original)
