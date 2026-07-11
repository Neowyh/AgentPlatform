"""Tests for ideer.sandbox.middleware covering uncovered lines."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestSandboxMiddlewareBeforeAgent:
    """Lines 68-75: before_agent with lazy_init=False, acquiring sandbox."""

    def test_before_agent_eager_acquires_sandbox(self):
        """Lines 68-75: when lazy_init=False and no sandbox in state, acquire one."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware(lazy_init=False)

        state = {}
        runtime = MagicMock()
        runtime.context = {"thread_id": "thread-123"}

        mock_provider = MagicMock()
        mock_provider.acquire.return_value = "sandbox-abc"

        with patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider):
            result = middleware.before_agent(state, runtime)

        assert result == {"sandbox": {"sandbox_id": "sandbox-abc"}}
        mock_provider.acquire.assert_called_once_with("thread-123")

    def test_before_agent_eager_no_thread_id_returns_none(self):
        """Lines 70-71: when no thread_id, returns super()."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware(lazy_init=False)
        state = {}
        runtime = MagicMock()
        runtime.context = {}

        result = middleware.before_agent(state, runtime)
        assert result is None

    def test_before_agent_lazy_returns_none(self):
        """Lines 64-65: when lazy_init=True, skip acquisition."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware(lazy_init=True)
        state = {}
        runtime = MagicMock()
        runtime.context = {"thread_id": "thread-123"}

        result = middleware.before_agent(state, runtime)
        assert result is None

    def test_before_agent_eager_sandbox_already_exists(self):
        """When sandbox already in state, skip acquisition."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware(lazy_init=False)
        state = {"sandbox": {"sandbox_id": "existing"}}
        runtime = MagicMock()
        runtime.context = {"thread_id": "thread-123"}

        result = middleware.before_agent(state, runtime)
        assert result is None


class TestSandboxMiddlewareAfterAgent:
    """Lines 96-101: after_agent releases sandbox from state."""

    def test_after_agent_releases_sandbox(self):
        """Lines 96-101: when sandbox in state, release it."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware()
        state = {"sandbox": {"sandbox_id": "sandbox-abc"}}
        runtime = MagicMock()
        runtime.context = {}

        mock_provider = MagicMock()
        with patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider):
            result = middleware.after_agent(state, runtime)

        mock_provider.release.assert_called_once_with("sandbox-abc")
        assert result is None

    def test_after_agent_releases_from_context(self):
        """Lines 103-107: release sandbox from runtime.context."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware()
        state = {}
        runtime = MagicMock()
        runtime.context = {"sandbox_id": "ctx-sandbox"}

        mock_provider = MagicMock()
        with patch("ideer.sandbox.middleware.get_sandbox_provider", return_value=mock_provider):
            result = middleware.after_agent(state, runtime)

        mock_provider.release.assert_called_once_with("ctx-sandbox")
        assert result is None

    def test_after_agent_no_sandbox_returns_none(self):
        """Lines 109-110: no sandbox to release, return super()."""
        from ideer.sandbox.middleware import SandboxMiddleware

        middleware = SandboxMiddleware()
        state = {}
        runtime = MagicMock()
        runtime.context = {}

        result = middleware.after_agent(state, runtime)
        assert result is None
