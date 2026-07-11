"""Additional coverage tests for ideer.sandbox.middleware.

Targets missed lines:
- Lines 53-56: _acquire_sandbox_async
- Line 59: _release_sandbox_async
- Lines 80-92: abefore_agent
- Lines 114-128: aafter_agent
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.sandbox.middleware import SandboxMiddleware


class TestAcquireSandboxAsync:
    """Lines 53-56: _acquire_sandbox_async."""

    @pytest.mark.anyio
    async def test_acquire_sandbox_async(self):
        mw = SandboxMiddleware()
        mock_provider = MagicMock()
        mock_provider.acquire_async = AsyncMock(return_value="sandbox-async-123")

        with patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider):
            result = await mw._acquire_sandbox_async("thread-1")

        assert result == "sandbox-async-123"
        mock_provider.acquire_async.assert_called_once_with("thread-1")


class TestReleaseSandboxAsync:
    """Line 59: _release_sandbox_async."""

    @pytest.mark.anyio
    async def test_release_sandbox_async(self):
        mw = SandboxMiddleware()
        mock_provider = MagicMock()
        mock_provider.release = MagicMock()

        with (
            patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        ):
            await mw._release_sandbox_async("sandbox-123")

        mock_to_thread.assert_called_once()


class TestAsyncBeforeAgent:
    """Lines 80-92: abefore_agent."""

    @pytest.mark.anyio
    async def test_abefore_agent_lazy_returns_none(self):
        """Line 80-81: lazy_init=True -> skip acquisition."""
        mw = SandboxMiddleware(lazy_init=True)
        state = {}
        runtime = MagicMock()
        runtime.context = {"thread_id": "thread-123"}

        result = await mw.abefore_agent(state, runtime)
        assert result is None

    @pytest.mark.anyio
    async def test_abefore_agent_eager_acquires_sandbox(self):
        """Lines 85-87: eager init acquires sandbox async."""
        mw = SandboxMiddleware(lazy_init=False)
        state = {}
        runtime = MagicMock()
        runtime.context = {"thread_id": "thread-123"}

        mock_provider = MagicMock()
        mock_provider.acquire_async = AsyncMock(return_value="sandbox-abc")

        with patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider):
            result = await mw.abefore_agent(state, runtime)

        assert result == {"sandbox": {"sandbox_id": "sandbox-abc"}}
        mock_provider.acquire_async.assert_called_once_with("thread-123")

    @pytest.mark.anyio
    async def test_abefore_agent_eager_no_thread_id(self):
        """Lines 83-84: no thread_id -> return super()."""
        mw = SandboxMiddleware(lazy_init=False)
        state = {}
        runtime = MagicMock()
        runtime.context = {}

        result = await mw.abefore_agent(state, runtime)
        assert result is None

    @pytest.mark.anyio
    async def test_abefore_agent_eager_sandbox_already_exists(self):
        """Sandbox already in state -> skip acquisition."""
        mw = SandboxMiddleware(lazy_init=False)
        state = {"sandbox": {"sandbox_id": "existing"}}
        runtime = MagicMock()
        runtime.context = {"thread_id": "thread-123"}

        result = await mw.abefore_agent(state, runtime)
        assert result is None


class TestAsyncAfterAgent:
    """Lines 114-128: aafter_agent."""

    @pytest.mark.anyio
    async def test_aafter_agent_releases_sandbox(self):
        """Lines 114-118: sandbox in state -> release async."""
        mw = SandboxMiddleware()
        state = {"sandbox": {"sandbox_id": "sandbox-abc"}}
        runtime = MagicMock()
        runtime.context = {}

        mock_provider = MagicMock()

        with (
            patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider),
            patch.object(mw, "_release_sandbox_async", new_callable=AsyncMock) as mock_release,
        ):
            result = await mw.aafter_agent(state, runtime)

        mock_release.assert_called_once_with("sandbox-abc")
        assert result is None

    @pytest.mark.anyio
    async def test_aafter_agent_releases_from_context(self):
        """Lines 119-123: sandbox from runtime.context."""
        mw = SandboxMiddleware()
        state = {}
        runtime = MagicMock()
        runtime.context = {"sandbox_id": "ctx-sandbox"}

        mock_provider = MagicMock()

        with (
            patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider),
            patch.object(mw, "_release_sandbox_async", new_callable=AsyncMock) as mock_release,
        ):
            result = await mw.aafter_agent(state, runtime)

        mock_release.assert_called_once_with("ctx-sandbox")
        assert result is None

    @pytest.mark.anyio
    async def test_aafter_agent_no_sandbox(self):
        """Lines 127-128: no sandbox -> return super()."""
        mw = SandboxMiddleware()
        state = {}
        runtime = MagicMock()
        runtime.context = {}

        result = await mw.aafter_agent(state, runtime)
        assert result is None
