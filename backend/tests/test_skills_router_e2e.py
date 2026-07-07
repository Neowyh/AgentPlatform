"""E2E tests for the skills router (backend/app/gateway/routers/skills.py).

Covers all 10 skills endpoints:
- GET /api/skills
- GET /api/skills/{skill_name}
- PUT /api/skills/{skill_name}
- POST /api/skills/install
- GET /api/skills/custom
- GET /api/skills/custom/{skill_name}
- PUT /api/skills/custom/{skill_name}
- DELETE /api/skills/custom/{skill_name}
- GET /api/skills/custom/{skill_name}/history
- POST /api/skills/custom/{skill_name}/rollback
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.deps import get_config
from app.gateway.routers.skills import router as skills_router
from ideer.skills.types import Skill, SkillCategory

pytestmark = pytest.mark.no_auto_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STORAGE_PATCH = "app.gateway.routers.skills.get_or_new_skill_storage"
_META_PATCH = "app.gateway.routers.skills._load_skill_meta"


def _make_user(role: str = "user") -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    user.role = role
    user.department_id = "dept-1"
    user.disabled = False
    return user


def _make_app(role: str = "user"):
    user = _make_user(role=role)
    app = make_authed_test_app()
    app.include_router(skills_router)

    async def _stub():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub
    app.dependency_overrides[get_optional_rbac_user] = _stub
    app.dependency_overrides[get_config] = lambda: SimpleNamespace()
    return app, user


def _make_skill(
    name: str = "test-skill",
    description: str = "Test skill",
    category: SkillCategory = SkillCategory.PUBLIC,
    enabled: bool = True,
) -> MagicMock:
    """Create a mock Skill object."""
    skill = MagicMock(spec=Skill)
    skill.name = name
    skill.description = description
    skill.category = category
    skill.enabled = enabled
    skill.license = None
    skill.skill_dir = Path(f"/tmp/skills/{name}")
    skill.skill_file = Path(f"/tmp/skills/{name}/SKILL.md")
    skill.relative_path = Path(name)
    skill.allowed_tools = None
    skill.requires_internet = False
    skill.visibility = "private"
    skill.owner_id = "user-1"
    skill.department_id = None
    return skill


def _make_mock_storage(skills=None, custom_content="# Custom Skill"):
    """Create a mock skill storage."""
    storage = MagicMock()
    storage.load_skills.return_value = skills or []
    storage.read_custom_skill.return_value = custom_content
    storage.write_custom_skill.return_value = None
    storage.ensure_custom_skill_is_editable.return_value = None
    storage.validate_skill_markdown_content.return_value = None
    storage.append_history.return_value = None
    storage.ainstall_skill_from_archive = AsyncMock(return_value={"name": "new-skill", "installed": True})
    storage.custom_skill_exists.return_value = True
    storage.read_history.return_value = []
    non_existent = Path("/tmp/nonexistent-skill-dir")
    storage.get_custom_skill_dir.return_value = non_existent
    storage.get_skill_history_file.return_value = non_existent / "history.json"
    storage.get_custom_skill_file.return_value = non_existent / "SKILL.md"
    return storage


# ---------------------------------------------------------------------------
# Tests — GET /api/skills
# ---------------------------------------------------------------------------


class TestListSkills:
    """Tests for GET /api/skills."""

    @patch(_STORAGE_PATCH)
    def test_list_skills_returns_list(self, mock_storage_fn):
        """List skills returns a list."""
        mock_storage_fn.return_value = _make_mock_storage(skills=[])
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("skills", data if isinstance(data, list) else []), list)

    @patch(_STORAGE_PATCH)
    def test_list_skills_with_results(self, mock_storage_fn):
        """List skills returns skill data."""
        skill = _make_skill()
        mock_storage_fn.return_value = _make_mock_storage(skills=[skill])
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET /api/skills/{skill_name}
# ---------------------------------------------------------------------------


class TestGetSkill:
    """Tests for GET /api/skills/{skill_name}."""

    @patch(_STORAGE_PATCH)
    def test_get_skill_found(self, mock_storage_fn):
        """Get skill returns skill details."""
        skill = _make_skill()
        mock_storage_fn.return_value = _make_mock_storage(skills=[skill])
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills/test-skill")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-skill"

    @patch(_STORAGE_PATCH)
    def test_get_skill_not_found(self, mock_storage_fn):
        """Get skill returns 404 when not found."""
        mock_storage_fn.return_value = _make_mock_storage(skills=[])
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — PUT /api/skills/{skill_name}
# ---------------------------------------------------------------------------


class TestUpdateSkill:
    """Tests for PUT /api/skills/{skill_name}."""

    @patch(_STORAGE_PATCH)
    @patch("app.gateway.routers.skills.ExtensionsConfig.resolve_config_path")
    @patch("app.gateway.routers.skills.get_extensions_config")
    @patch("app.gateway.routers.skills.reload_extensions_config")
    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    def test_update_skill_enable(self, mock_refresh, mock_reload, mock_get_ext, mock_resolve, mock_storage_fn, tmp_path):
        """Update skill to enabled succeeds."""
        skill = _make_skill(enabled=False)
        config_file = tmp_path / "extensions_config.json"
        config_file.write_text("{}")

        mock_resolve.return_value = config_file
        mock_ext = MagicMock()
        mock_ext.skills = {}
        mock_ext.mcp_servers = {}
        mock_get_ext.return_value = mock_ext

        storage = _make_mock_storage(skills=[skill, skill])
        mock_storage_fn.return_value = storage
        app, _ = _make_app(role="department_admin")
        with TestClient(app) as client:
            resp = client.put("/api/skills/test-skill", json={"enabled": True})
        assert resp.status_code == 200

    @patch(_STORAGE_PATCH)
    @patch("app.gateway.routers.skills.ExtensionsConfig.resolve_config_path")
    @patch("app.gateway.routers.skills.get_extensions_config")
    @patch("app.gateway.routers.skills.reload_extensions_config")
    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    def test_update_skill_disable(self, mock_refresh, mock_reload, mock_get_ext, mock_resolve, mock_storage_fn, tmp_path):
        """Update skill to disabled succeeds."""
        skill = _make_skill(enabled=True)
        config_file = tmp_path / "extensions_config.json"
        config_file.write_text("{}")

        mock_resolve.return_value = config_file
        mock_ext = MagicMock()
        mock_ext.skills = {}
        mock_ext.mcp_servers = {}
        mock_get_ext.return_value = mock_ext

        storage = _make_mock_storage(skills=[skill, skill])
        mock_storage_fn.return_value = storage
        app, _ = _make_app(role="department_admin")
        with TestClient(app) as client:
            resp = client.put("/api/skills/test-skill", json={"enabled": False})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — POST /api/skills/install
# ---------------------------------------------------------------------------


class TestInstallSkill:
    """Tests for POST /api/skills/install."""

    @patch(_STORAGE_PATCH)
    @patch("app.gateway.routers.skills.resolve_thread_virtual_path")
    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    def test_install_skill_success(self, mock_refresh, mock_resolve, mock_storage_fn, tmp_path):
        """Install skill succeeds with valid archive."""
        skill_file = tmp_path / "test.skill"
        skill_file.write_bytes(b"fake-zip-content")
        mock_resolve.return_value = skill_file

        storage = _make_mock_storage()
        storage.ainstall_skill_from_archive = AsyncMock(return_value={"success": True, "skill_name": "new-skill", "message": "Installed"})
        mock_storage_fn.return_value = storage
        app, _ = _make_app(role="department_admin")
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/install",
                json={"thread_id": "t1", "path": "test.skill"},
            )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Tests — GET /api/skills/custom
# ---------------------------------------------------------------------------


class TestListCustomSkills:
    """Tests for GET /api/skills/custom."""

    @patch(_STORAGE_PATCH)
    def test_list_custom_skills(self, mock_storage_fn):
        """List custom skills returns a list."""
        skill = _make_skill(category=SkillCategory.CUSTOM)
        mock_storage_fn.return_value = _make_mock_storage(skills=[skill])
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills/custom")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET /api/skills/custom/{skill_name}
# ---------------------------------------------------------------------------


class TestGetCustomSkill:
    """Tests for GET /api/skills/custom/{skill_name}."""

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public"})
    def test_get_custom_skill_found(self, mock_meta, mock_storage_fn):
        """Get custom skill returns content."""
        skill = _make_skill(category=SkillCategory.CUSTOM)
        mock_storage_fn.return_value = _make_mock_storage(skills=[skill], custom_content="# Custom Content")
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills/custom/test-skill")
        assert resp.status_code == 200

    @patch(_STORAGE_PATCH)
    def test_get_custom_skill_not_found(self, mock_storage_fn):
        """Get custom skill returns 404 when not found."""
        mock_storage_fn.return_value = _make_mock_storage(skills=[])
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills/custom/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — PUT /api/skills/custom/{skill_name}
# ---------------------------------------------------------------------------


class TestUpdateCustomSkill:
    """Tests for PUT /api/skills/custom/{skill_name}."""

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public", "owner_id": "user-1"})
    @patch("app.gateway.routers.skills.scan_skill_content")
    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    def test_update_custom_skill_success(self, mock_refresh, mock_scan, mock_meta, mock_storage_fn):
        """Update custom skill succeeds."""
        from ideer.skills.security_scanner import ScanResult

        mock_scan.return_value = ScanResult(decision="allow", reason="")

        skill = _make_skill(category=SkillCategory.CUSTOM)
        mock_storage_fn.return_value = _make_mock_storage(skills=[skill], custom_content="# Updated")
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/skills/custom/test-skill",
                json={"content": "# Updated Skill", "version": 1},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — DELETE /api/skills/custom/{skill_name}
# ---------------------------------------------------------------------------


class TestDeleteCustomSkill:
    """Tests for DELETE /api/skills/custom/{skill_name}."""

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public", "owner_id": "user-1"})
    def test_delete_custom_skill_success(self, mock_meta, mock_storage_fn):
        """Delete custom skill succeeds."""
        storage = _make_mock_storage()
        storage.delete_custom_skill = MagicMock(return_value=True)
        mock_storage_fn.return_value = storage
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.delete("/api/skills/custom/test-skill")
        assert resp.status_code in (200, 204)

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public", "owner_id": "user-1"})
    def test_delete_custom_skill_not_found(self, mock_meta, mock_storage_fn):
        """Delete custom skill returns 404 when not found."""
        storage = _make_mock_storage()
        storage.delete_custom_skill = MagicMock(side_effect=FileNotFoundError("not found"))
        mock_storage_fn.return_value = storage
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.delete("/api/skills/custom/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — GET /api/skills/custom/{skill_name}/history
# ---------------------------------------------------------------------------


class TestGetCustomSkillHistory:
    """Tests for GET /api/skills/custom/{skill_name}/history."""

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public"})
    def test_get_history_returns_list(self, mock_meta, mock_storage_fn):
        """Get skill history returns list of versions."""
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = True
        storage.read_history.return_value = []
        mock_storage_fn.return_value = storage
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/skills/custom/test-skill/history")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — POST /api/skills/custom/{skill_name}/rollback
# ---------------------------------------------------------------------------


class TestRollbackCustomSkill:
    """Tests for POST /api/skills/custom/{skill_name}/rollback."""

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public", "owner_id": "user-1"})
    @patch("app.gateway.routers.skills.scan_skill_content")
    @patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async")
    def test_rollback_success(self, mock_refresh, mock_scan, mock_meta, mock_storage_fn):
        """Rollback skill succeeds."""
        from ideer.skills.security_scanner import ScanResult

        mock_scan.return_value = ScanResult(decision="allow", reason="")

        skill = _make_skill(category=SkillCategory.CUSTOM)
        storage = _make_mock_storage(skills=[skill], custom_content="# Rolled back")
        storage.custom_skill_exists.return_value = True
        storage.read_history.return_value = [{"ts": "2026-01-01", "prev_content": "# Old", "action": "edit"}]
        non_existent = Path("/tmp/nonexistent-skill-dir")
        storage.get_custom_skill_file.return_value = non_existent / "SKILL.md"
        mock_storage_fn.return_value = storage
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/custom/test-skill/rollback",
                json={"history_index": 0},
            )
        assert resp.status_code == 200

    @patch(_STORAGE_PATCH)
    @patch(_META_PATCH, new_callable=AsyncMock, return_value={"visibility": "public"})
    def test_rollback_not_found(self, mock_meta, mock_storage_fn):
        """Rollback skill returns 404 when not found."""
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = False
        non_existent = Path("/tmp/nonexistent-skill-dir")
        storage.get_skill_history_file.return_value = non_existent / "history.json"
        mock_storage_fn.return_value = storage
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/skills/custom/test-skill/rollback",
                json={"history_index": 0},
            )
        assert resp.status_code in (404, 400)
