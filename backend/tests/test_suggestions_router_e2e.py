"""E2E tests for the suggestions router (backend/app/gateway/routers/suggestions.py).

Covers:
- POST /api/threads/{thread_id}/suggestions
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.suggestions import router as suggestions_router

pytestmark = pytest.mark.no_auto_user

THREAD_ID = "thread-1"


def _make_app():
    app = make_authed_test_app()
    app.include_router(suggestions_router)
    return app


def _messages(role: str = "user", content: str = "Tell me about AI"):
    return [{"role": role, "content": content}]


def _make_mock_model(response_text: str):
    """Create a mock chat model whose ainvoke returns the given text."""
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    return mock_model


# ---------------------------------------------------------------------------
# Tests — POST /api/threads/{thread_id}/suggestions
# ---------------------------------------------------------------------------


class TestGenerateSuggestions:
    """Tests for POST /api/threads/{thread_id}/suggestions."""

    @patch("app.gateway.routers.suggestions.create_chat_model")
    def test_generate_suggestions_success(self, mock_create_chat_model):
        """Generate suggestions returns follow-up questions."""
        mock_create_chat_model.return_value = _make_mock_model('["What else would you like to know?", "Can I help with anything else?"]')
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/suggestions",
                json={"messages": _messages(), "n": 3},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        suggestions = data["suggestions"]
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1
        assert "What else would you like to know?" in suggestions

    @patch("app.gateway.routers.suggestions.create_chat_model")
    def test_generate_suggestions_empty(self, mock_create_chat_model):
        """Generate suggestions returns empty list when messages is empty."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/suggestions",
                json={"messages": []},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"suggestions": []}

    @patch("app.gateway.routers.suggestions.create_chat_model")
    def test_generate_suggestions_service_error(self, mock_create_chat_model):
        """Generate suggestions handles service errors gracefully."""
        mock_create_chat_model.side_effect = Exception("LLM unavailable")
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/suggestions",
                json={"messages": _messages(), "n": 3},
            )
        # Should handle error gracefully — returns 200 with empty suggestions
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"suggestions": []}
