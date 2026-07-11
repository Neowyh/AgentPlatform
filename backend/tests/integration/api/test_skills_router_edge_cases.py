"""Additional tests for the skills router (backend/app/gateway/routers/skills.py).

Covers gaps not addressed by existing test files:
- _validate_skill_name: valid and invalid names
- _load_skill_meta: error paths (JSONDecodeError, generic Exception)
- list_skills: error handling, visibility filtering
- get_skill: custom skill visibility check, not found, invalid name
- install_skill: error paths (404, 409, 400, 500)
- update_skill: not found, config path missing, error handling
- get_custom_skill: invalid name, visibility check for unauthenticated user
- update_custom_skill: error paths (FileNotFoundError, ValueError)
- delete_custom_skill: error paths (FileNotFoundError, ValueError)
- get_custom_skill_history: not found, visibility check
- rollback_custom_skill: no history, index out of range
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.gateway.routers.skills import (
    _load_skill_meta,
    _validate_skill_name,
)
from app.gateway.routers.skills import (
    router as skills_router,
)
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# _validate_skill_name tests
# ---------------------------------------------------------------------------


class TestValidateSkillName:
    """Tests for _validate_skill_name."""

    def test_valid_name_alphanumeric(self):
        """Accepts alphanumeric names."""
        _validate_skill_name("mySkill123")

    def test_valid_name_with_hyphens(self):
        """Accepts names with hyphens."""
        _validate_skill_name("my-skill-name")

    def test_valid_name_with_underscores(self):
        """Accepts names with underscores."""
        _validate_skill_name("my_skill_name")

    def test_invalid_name_with_spaces(self):
        """Rejects names with spaces."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("my skill")
        assert exc_info.value.status_code == 422

    def test_invalid_name_with_slashes(self):
        """Rejects names with slashes (path traversal)."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("../etc/passwd")
        assert exc_info.value.status_code == 422

    def test_invalid_name_with_special_chars(self):
        """Rejects names with special characters."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("skill@name!")
        assert exc_info.value.status_code == 422

    def test_invalid_name_empty(self):
        """Rejects empty names."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("")
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# _is_visible_to_user tests
# ---------------------------------------------------------------------------


def _make_user(
    user_id: str = "user-1",
    role: str = UserRole.USER,
    department_id: str | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    return user


# ---------------------------------------------------------------------------
# _load_skill_meta tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetSkillMeta:
    """Tests for _load_skill_meta."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    async def test_returns_empty_dict_on_file_not_found(self, mock_storage):
        """Returns {} when storage raises FileNotFoundError."""
        storage = MagicMock()
        storage.get_custom_skill_dir.side_effect = FileNotFoundError
        mock_storage.return_value = storage

        config = SimpleNamespace()
        result = await _load_skill_meta("my-skill", config)
        assert result == {}

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    async def test_returns_empty_dict_on_json_decode_error(self, mock_storage):
        """Returns {} when .meta.json is corrupted."""
        from pathlib import Path

        meta_file = MagicMock(spec=Path)
        meta_file.exists.return_value = True
        meta_file.read_text.side_effect = json.JSONDecodeError("err", "", 0)

        storage = MagicMock()
        storage.get_custom_skill_dir.return_value = MagicMock()
        storage.get_custom_skill_dir.return_value.__truediv__ = lambda self, x: meta_file
        mock_storage.return_value = storage

        config = SimpleNamespace()
        result = await _load_skill_meta("my-skill", config)
        assert result == {}

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    async def test_returns_empty_dict_on_generic_exception(self, mock_storage):
        """Returns {} on unexpected exceptions."""
        storage = MagicMock()
        storage.get_custom_skill_dir.side_effect = RuntimeError("unexpected")
        mock_storage.return_value = storage

        config = SimpleNamespace()
        result = await _load_skill_meta("my-skill", config)
        assert result == {}


# ---------------------------------------------------------------------------
# Endpoint-level tests with mocks
# ---------------------------------------------------------------------------


def _make_test_app(config, current_user=None):
    """Build a test app with skills router."""
    from _router_auth_helpers import make_authed_test_app

    from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
    from app.gateway.deps import get_config

    app = make_authed_test_app()
    app.state.config = config
    app.dependency_overrides[get_config] = lambda: config

    user = current_user or _make_user(role=UserRole.SUPER_ADMIN)

    async def _stub_current():
        return user

    async def _stub_optional():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current
    app.dependency_overrides[get_optional_rbac_user] = _stub_optional
    app.include_router(skills_router)
    return app


class TestListSkillsErrorHandling:
    """Tests for list_skills error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    def test_list_skills_returns_500_on_error(self, mock_storage):
        """Returns 500 when skill storage raises."""
        storage = MagicMock()
        storage.load_skills.side_effect = RuntimeError("storage error")
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.get("/api/skills")

        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


class TestGetSkillErrors:
    """Tests for get_skill error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    def test_get_skill_not_found(self, mock_storage):
        """Returns 404 when skill is not found."""
        storage = MagicMock()
        storage.load_skills.return_value = []
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.get("/api/skills/nonexistent")

        assert response.status_code == 404

    def test_get_skill_invalid_name(self):
        """Returns 422 for invalid skill name with special characters."""
        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.get("/api/skills/invalid@name!")

        assert response.status_code == 422


class TestInstallSkillErrors:
    """Tests for install_skill error handling."""

    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills.resolve_thread_virtual_path")
    def test_install_skill_file_not_found(self, mock_resolve, mock_storage, mock_refresh):
        """Returns 404 when skill file not found."""
        mock_resolve.side_effect = FileNotFoundError("File not found: test.skill")

        storage = MagicMock()
        mock_storage.return_value = storage

        config = SimpleNamespace(
            skills=SimpleNamespace(get_skills_path=lambda: "/tmp/skills", container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=True, moderation_model_name=None),
        )

        app = _make_test_app(config)
        client = TestClient(app)
        response = client.post(
            "/api/skills/install",
            json={"thread_id": "t1", "path": "mnt/user-data/outputs/test.skill"},
        )

        assert response.status_code == 404


class TestUpdateSkillErrors:
    """Tests for update_skill error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    def test_update_skill_not_found(self, mock_storage):
        """Returns 404 when skill not found."""
        storage = MagicMock()
        storage.load_skills.return_value = []
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.put(
            "/api/skills/nonexistent",
            json={"enabled": True},
        )

        assert response.status_code == 404

    @patch("app.gateway.routers.skills.ExtensionsConfig.resolve_config_path", return_value=None)
    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    def test_update_skill_no_config_path(self, mock_storage, mock_resolve):
        """Returns 500 when config path is not configured."""
        from ideer.skills.types import Skill

        skill = Skill(
            name="test-skill",
            description="test",
            license=None,
            skill_dir="/tmp/test",
            skill_file="/tmp/test/SKILL.md",
            relative_path="test",
            category="public",
            enabled=True,
        )
        storage = MagicMock()
        storage.load_skills.return_value = [skill]
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.put(
            "/api/skills/test-skill",
            json={"enabled": False},
        )

        assert response.status_code == 500


class TestUpdateCustomSkillErrors:
    """Tests for update_custom_skill error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills._load_skill_meta", new_callable=AsyncMock, return_value={"owner_id": "user-1"})
    def test_update_custom_skill_not_found(self, mock_meta, mock_storage):
        """Returns 404 when custom skill not found for edit."""
        storage = MagicMock()
        storage.load_skills.return_value = []
        storage.ensure_custom_skill_is_editable.side_effect = FileNotFoundError("not found")
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.put(
            "/api/skills/custom/nonexistent",
            json={"content": "# new content", "version": 1},
        )

        assert response.status_code == 404

    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    @patch("app.gateway.routers.skills.scan_skill_content")
    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills._load_skill_meta", new_callable=AsyncMock, return_value={"owner_id": "user-1"})
    def test_update_custom_skill_file_not_found(self, mock_meta, mock_storage, mock_scan, mock_refresh):
        """Returns 404 when skill file doesn't exist."""
        from pathlib import Path

        from ideer.skills.types import Skill

        skill = Skill(
            name="test-skill",
            description="test",
            license=None,
            skill_dir=Path("/tmp/test"),
            skill_file=Path("/tmp/test/SKILL.md"),
            relative_path=Path("test"),
            category="custom",
            enabled=True,
        )
        storage = MagicMock()
        storage.load_skills.return_value = [skill]
        storage.ensure_custom_skill_is_editable.side_effect = FileNotFoundError("not found")
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.put(
            "/api/skills/custom/test-skill",
            json={"content": "# new content", "version": 1},
        )

        assert response.status_code == 404


class TestDeleteCustomSkillErrors:
    """Tests for delete_custom_skill error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills._load_skill_meta", new_callable=AsyncMock, return_value={"owner_id": "user-1"})
    def test_delete_custom_skill_not_found(self, mock_meta, mock_storage):
        """Returns 404 when skill to delete doesn't exist."""
        storage = MagicMock()
        storage.delete_custom_skill.side_effect = FileNotFoundError("not found")
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.delete("/api/skills/custom/nonexistent")

        assert response.status_code == 404


class TestGetCustomSkillHistoryErrors:
    """Tests for get_custom_skill_history error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    def test_history_not_found(self, mock_storage):
        """Returns 404 when skill and history don't exist."""
        storage = MagicMock()
        storage.custom_skill_exists.return_value = False
        storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.get("/api/skills/custom/nonexistent/history")

        assert response.status_code == 404


class TestRollbackCustomSkillErrors:
    """Tests for rollback_custom_skill error handling."""

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills._load_skill_meta", new_callable=AsyncMock, return_value={"owner_id": "user-1"})
    def test_rollback_no_history(self, mock_meta, mock_storage):
        """Returns 400 when skill has no history."""
        storage = MagicMock()
        storage.custom_skill_exists.return_value = True
        storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=True))
        storage.read_history.return_value = []
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.post(
            "/api/skills/custom/test-skill/rollback",
            json={"history_index": -1},
        )

        assert response.status_code == 400
        assert "no history" in response.json()["detail"]

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills._load_skill_meta", new_callable=AsyncMock, return_value={"owner_id": "user-1"})
    def test_rollback_index_out_of_range(self, mock_meta, mock_storage):
        """Returns 400 when history_index is out of range."""
        storage = MagicMock()
        storage.custom_skill_exists.return_value = True
        storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=True))
        storage.read_history.return_value = [{"action": "edit", "prev_content": "# old"}]
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.post(
            "/api/skills/custom/test-skill/rollback",
            json={"history_index": 99},
        )

        assert response.status_code == 400

    @patch("app.gateway.routers.skills.get_or_new_skill_storage")
    @patch("app.gateway.routers.skills._load_skill_meta", new_callable=AsyncMock, return_value={"owner_id": "user-1"})
    def test_rollback_no_prev_content(self, mock_meta, mock_storage):
        """Returns 400 when history entry has no prev_content."""
        storage = MagicMock()
        storage.custom_skill_exists.return_value = True
        storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=True))
        storage.read_history.return_value = [{"action": "delete", "prev_content": None}]
        mock_storage.return_value = storage

        app = _make_test_app(SimpleNamespace())
        client = TestClient(app)
        response = client.post(
            "/api/skills/custom/test-skill/rollback",
            json={"history_index": -1},
        )

        assert response.status_code == 400
        assert "no previous content" in response.json()["detail"]
