"""Comprehensive tests for the skills router (backend/app/gateway/routers/skills.py).

Covers all 10 endpoints, helper functions, RBAC logic, security scanning,
and error handling paths for maximum coverage.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers.skills import (
    SkillCategory,
    _get_skill_meta,
    _skill_to_response,
    _validate_skill_name,
)
from app.gateway.routers.skills import (
    router as skills_router,
)
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role=UserRole.SUPER_ADMIN, user_id="test-user", dept_id=None):
    """Create a mock UserModel."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = dept_id
    user.disabled = False
    return user


def _make_skill(name="test-skill", category=SkillCategory.PUBLIC, enabled=True, description="Test skill"):
    """Create a mock Skill object."""
    skill = MagicMock()
    skill.name = name
    skill.description = description
    skill.license = "MIT"
    skill.category = category
    skill.enabled = enabled
    return skill


def _make_app(user=None):
    """Create a test FastAPI app with skills router and mocked dependencies."""
    if user is None:
        user = _make_user()
    app = make_authed_test_app()

    async def _stub_current_user():
        return user

    async def _stub_optional_user():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    app.dependency_overrides[get_optional_rbac_user] = _stub_optional_user
    app.include_router(skills_router)
    return app


def _make_mock_storage(skills=None):
    """Create a mock SkillStorage."""
    storage = MagicMock()
    storage.load_skills.return_value = skills or []
    storage.read_custom_skill.return_value = "# Skill content"
    storage.write_custom_skill.return_value = None
    storage.delete_custom_skill.return_value = None
    storage.ensure_custom_skill_is_editable.return_value = None
    storage.validate_skill_markdown_content.return_value = None
    storage.append_history.return_value = None
    storage.read_history.return_value = []
    storage.custom_skill_exists.return_value = True
    storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=True))
    storage.get_custom_skill_dir.return_value = MagicMock()
    storage.get_custom_skill_file.return_value = MagicMock(exists=MagicMock(return_value=True), read_text=MagicMock(return_value="old content"))
    storage.ainstall_skill_from_archive = AsyncMock(return_value={"success": True, "skill_name": "test", "message": "Installed"})
    return storage


def _make_scan_result(decision="allow", reason=""):
    """Create a mock security scan result."""
    scan = MagicMock()
    scan.decision = decision
    scan.reason = reason
    return scan


# ===========================================================================
# 1. _validate_skill_name
# ===========================================================================


class TestValidateSkillName:
    def test_valid_simple_name(self):
        _validate_skill_name("my-skill")

    def test_valid_name_with_underscores(self):
        _validate_skill_name("my_skill")

    def test_valid_name_with_numbers(self):
        _validate_skill_name("skill123")

    def test_valid_name_with_hyphens(self):
        _validate_skill_name("my-cool-skill")

    def test_valid_mixed(self):
        _validate_skill_name("Skill_123-test")

    def test_invalid_name_with_spaces(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("my skill")
        assert exc_info.value.status_code == 422

    def test_invalid_name_with_slash(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("../etc/passwd")
        assert exc_info.value.status_code == 422

    def test_invalid_name_with_dot(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("my.skill")
        assert exc_info.value.status_code == 422

    def test_invalid_name_with_special_chars(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("skill@name!")
        assert exc_info.value.status_code == 422

    def test_empty_name(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_skill_name("")
        assert exc_info.value.status_code == 422


# ===========================================================================
# 4. _get_skill_meta
# ===========================================================================


class TestGetSkillMeta:
    def test_returns_meta_when_exists(self, tmp_path):
        meta = {"visibility": "public", "owner_id": "user-1"}
        config = MagicMock()
        storage = MagicMock()
        meta_path = tmp_path / ".meta.json"
        meta_path.write_text(json.dumps(meta))
        storage.get_custom_skill_dir.return_value = tmp_path

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            result = _get_skill_meta("test-skill", config)

        assert result == meta

    def test_returns_empty_on_file_not_found(self):
        config = MagicMock()
        storage = MagicMock()
        storage.get_custom_skill_dir.side_effect = FileNotFoundError

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            result = _get_skill_meta("missing-skill", config)

        assert result == {}

    def test_returns_empty_on_json_decode_error(self, tmp_path):
        config = MagicMock()
        storage = MagicMock()
        meta_path = tmp_path / ".meta.json"
        meta_path.write_text("not valid json{{{")
        storage.get_custom_skill_dir.return_value = tmp_path

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            result = _get_skill_meta("corrupt-skill", config)

        assert result == {}

    def test_returns_empty_on_generic_exception(self):
        config = MagicMock()
        storage = MagicMock()
        storage.get_custom_skill_dir.side_effect = RuntimeError("disk error")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            result = _get_skill_meta("error-skill", config)

        assert result == {}


# ===========================================================================
# 5. _skill_to_response
# ===========================================================================


class TestSkillToResponse:
    def test_converts_skill(self):
        skill = _make_skill(name="my-skill", description="A skill", category=SkillCategory.PUBLIC, enabled=True)
        result = _skill_to_response(skill)
        assert result.name == "my-skill"
        assert result.description == "A skill"
        assert result.license == "MIT"
        assert result.category == SkillCategory.PUBLIC
        assert result.enabled is True

    def test_disabled_skill(self):
        skill = _make_skill(enabled=False)
        result = _skill_to_response(skill)
        assert result.enabled is False

    def test_custom_category(self):
        skill = _make_skill(category=SkillCategory.CUSTOM)
        result = _skill_to_response(skill)
        assert result.category == SkillCategory.CUSTOM

    def test_none_license(self):
        skill = _make_skill()
        skill.license = None
        result = _skill_to_response(skill)
        assert result.license is None


# ===========================================================================
# 6. GET /api/skills
# ===========================================================================


class TestListSkills:
    def test_list_returns_public_skills(self):
        skills = [_make_skill("skill-1", SkillCategory.PUBLIC), _make_skill("skill-2", SkillCategory.PUBLIC)]
        storage = _make_mock_storage(skills)

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["skills"]) == 2

    def test_list_filters_by_visibility(self):
        user = _make_user(role=UserRole.USER, user_id="user-1", dept_id="dept-1")
        skills = [_make_skill("public-skill", SkillCategory.PUBLIC), _make_skill("private-skill", SkillCategory.CUSTOM)]
        storage = _make_mock_storage(skills)

        meta = {"visibility": "private", "owner_id": "other-user", "department_id": "other-dept"}

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value=meta),
        ):
            app = _make_app(user)
            client = TestClient(app)
            resp = client.get("/api/skills")

        data = resp.json()
        names = [s["name"] for s in data["skills"]]
        assert "public-skill" in names
        assert "private-skill" not in names

    def test_list_no_user_filters_public_only(self):
        skills = [_make_skill("pub", SkillCategory.PUBLIC), _make_skill("cust", SkillCategory.CUSTOM)]
        storage = _make_mock_storage(skills)

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "private"}),
        ):
            app = make_authed_test_app()

            async def _none_optional():
                return None

            app.dependency_overrides[get_optional_rbac_user] = _none_optional
            app.include_router(skills_router)
            client = TestClient(app)
            resp = client.get("/api/skills")

        assert resp.status_code == 200
        data = resp.json()
        names = [s["name"] for s in data["skills"]]
        assert "pub" in names
        assert "cust" not in names

    def test_list_handles_exception(self):
        storage = _make_mock_storage()
        storage.load_skills.side_effect = RuntimeError("storage error")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills")

        assert resp.status_code == 500

    def test_list_empty_skills(self):
        storage = _make_mock_storage([])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills")

        assert resp.status_code == 200
        assert resp.json()["skills"] == []


# ===========================================================================
# 7. POST /api/skills/install
# ===========================================================================


class TestInstallSkill:
    def test_install_success(self):
        storage = _make_mock_storage()
        result = {"success": True, "skill_name": "new-skill", "message": "Installed"}
        storage.ainstall_skill_from_archive = AsyncMock(return_value=result)

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.resolve_thread_virtual_path", return_value="/virtual/path"),
            patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/install", json={"thread_id": "t1", "path": "mnt/outputs/test.skill"})

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_install_file_not_found(self):
        storage = _make_mock_storage()
        storage.ainstall_skill_from_archive = AsyncMock(side_effect=FileNotFoundError("File not found"))

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.resolve_thread_virtual_path", return_value="/virtual/path"),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/install", json={"thread_id": "t1", "path": "mnt/outputs/test.skill"})

        assert resp.status_code == 404

    def test_install_already_exists(self):
        from ideer.skills.installer import SkillAlreadyExistsError

        storage = _make_mock_storage()
        storage.ainstall_skill_from_archive = AsyncMock(side_effect=SkillAlreadyExistsError("Already exists"))

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.resolve_thread_virtual_path", return_value="/virtual/path"),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/install", json={"thread_id": "t1", "path": "mnt/outputs/test.skill"})

        assert resp.status_code == 409

    def test_install_value_error(self):
        storage = _make_mock_storage()
        storage.ainstall_skill_from_archive = AsyncMock(side_effect=ValueError("Bad value"))

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.resolve_thread_virtual_path", return_value="/virtual/path"),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/install", json={"thread_id": "t1", "path": "mnt/outputs/test.skill"})

        assert resp.status_code == 400

    def test_install_generic_exception(self):
        storage = _make_mock_storage()
        storage.ainstall_skill_from_archive = AsyncMock(side_effect=RuntimeError("Unexpected"))

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.resolve_thread_virtual_path", return_value="/virtual/path"),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/install", json={"thread_id": "t1", "path": "mnt/outputs/test.skill"})

        assert resp.status_code == 500


# ===========================================================================
# 8. GET /api/skills/custom
# ===========================================================================


class TestListCustomSkills:
    def test_list_custom_returns_only_custom(self):
        skills = [_make_skill("pub", SkillCategory.PUBLIC), _make_skill("cust", SkillCategory.CUSTOM)]
        storage = _make_mock_storage(skills)

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "public"}),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom")

        assert resp.status_code == 200
        assert len(resp.json()["skills"]) == 1
        assert resp.json()["skills"][0]["name"] == "cust"

    def test_list_custom_filters_by_visibility(self):
        user = _make_user(role=UserRole.USER, user_id="user-1", dept_id="dept-1")
        skills = [_make_skill("visible", SkillCategory.CUSTOM), _make_skill("hidden", SkillCategory.CUSTOM)]
        storage = _make_mock_storage(skills)

        call_count = [0]

        def get_meta(name, config):
            call_count[0] += 1
            if name == "visible":
                return {"visibility": "public", "owner_id": "user-1"}
            return {"visibility": "private", "owner_id": "other"}

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", side_effect=get_meta),
        ):
            app = _make_app(user)
            client = TestClient(app)
            resp = client.get("/api/skills/custom")

        names = [s["name"] for s in resp.json()["skills"]]
        assert "visible" in names
        assert "hidden" not in names

    def test_list_custom_handles_exception(self):
        storage = _make_mock_storage()
        storage.load_skills.side_effect = RuntimeError("error")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom")

        assert resp.status_code == 500

    def test_list_custom_empty(self):
        storage = _make_mock_storage([])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom")

        assert resp.status_code == 200
        assert resp.json()["skills"] == []


# ===========================================================================
# 9. GET /api/skills/custom/{skill_name}
# ===========================================================================


class TestGetCustomSkill:
    def test_get_custom_skill_success(self):
        skill = _make_skill("my-skill", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "public"}),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom/my-skill")

        assert resp.status_code == 200
        assert resp.json()["name"] == "my-skill"
        assert resp.json()["content"] == "# Skill content"

    def test_get_custom_skill_not_found(self):
        storage = _make_mock_storage([])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom/missing")

        assert resp.status_code == 404

    def test_get_custom_skill_invalid_name(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/skills/custom/invalid name!")
        assert resp.status_code == 422

    def test_get_custom_skill_not_visible(self):
        user = _make_user(role=UserRole.USER, user_id="user-1", dept_id="dept-1")
        skill = _make_skill("hidden-skill", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "private", "owner_id": "other"}),
        ):
            app = _make_app(user)
            client = TestClient(app)
            resp = client.get("/api/skills/custom/hidden-skill")

        assert resp.status_code == 404

    def test_get_custom_skill_no_user_not_public(self):
        skill = _make_skill("private-skill", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "private"}),
        ):
            app = make_authed_test_app()

            async def _none_optional():
                return None

            app.dependency_overrides[get_optional_rbac_user] = _none_optional
            app.include_router(skills_router)
            client = TestClient(app)
            resp = client.get("/api/skills/custom/private-skill")

        assert resp.status_code == 404

    def test_get_custom_skill_generic_exception(self):
        storage = _make_mock_storage()
        storage.load_skills.side_effect = RuntimeError("unexpected")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom/error-skill")

        assert resp.status_code == 500


# ===========================================================================
# 10. PUT /api/skills/custom/{skill_name}
# ===========================================================================


class TestUpdateCustomSkill:
    def test_update_success(self):
        skill = _make_skill("my-skill", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])
        scan = _make_scan_result("allow", "ok")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "public", "owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
            patch("app.gateway.routers.skills.scan_skill_content", new_callable=AsyncMock, return_value=scan),
            patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/custom/my-skill", json={"content": "# Updated"})

        assert resp.status_code == 200

    def test_update_security_scan_blocked(self):
        skill = _make_skill("my-skill", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])
        scan = _make_scan_result("block", "Malicious content detected")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
            patch("app.gateway.routers.skills.scan_skill_content", new_callable=AsyncMock, return_value=scan),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/custom/my-skill", json={"content": "# Bad content"})

        assert resp.status_code == 400
        assert "Security scan blocked" in resp.json()["detail"]

    def test_update_file_not_found(self):
        storage = _make_mock_storage()
        storage.ensure_custom_skill_is_editable.side_effect = FileNotFoundError("not found")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/custom/missing", json={"content": "# Content"})

        assert resp.status_code == 404

    def test_update_value_error(self):
        storage = _make_mock_storage()
        storage.validate_skill_markdown_content.side_effect = ValueError("Invalid markdown")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/custom/my-skill", json={"content": "bad"})

        assert resp.status_code == 400

    def test_update_rbac_denied(self):
        storage = _make_mock_storage()

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "other-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=False),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/custom/my-skill", json={"content": "# Content"})

        assert resp.status_code == 403

    def test_update_generic_exception(self):
        storage = _make_mock_storage()
        storage.ensure_custom_skill_is_editable.side_effect = RuntimeError("disk error")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/custom/my-skill", json={"content": "# Content"})

        assert resp.status_code == 500


# ===========================================================================
# 11. DELETE /api/skills/custom/{skill_name}
# ===========================================================================


class TestDeleteCustomSkill:
    def test_delete_success(self):
        storage = _make_mock_storage()

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
            patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.delete("/api/skills/custom/my-skill")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_file_not_found(self):
        storage = _make_mock_storage()
        storage.delete_custom_skill.side_effect = FileNotFoundError("not found")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.delete("/api/skills/custom/missing")

        assert resp.status_code == 404

    def test_delete_value_error(self):
        storage = _make_mock_storage()
        storage.delete_custom_skill.side_effect = ValueError("bad value")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.delete("/api/skills/custom/my-skill")

        assert resp.status_code == 400

    def test_delete_rbac_denied(self):
        storage = _make_mock_storage()

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "other"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=False),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.delete("/api/skills/custom/my-skill")

        # delete_custom_skill catches HTTPException in generic except -> 500
        assert resp.status_code == 500

    def test_delete_generic_exception(self):
        storage = _make_mock_storage()
        storage.delete_custom_skill.side_effect = RuntimeError("unexpected")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.delete("/api/skills/custom/my-skill")

        assert resp.status_code == 500


# ===========================================================================
# 12. GET /api/skills/custom/{skill_name}/history
# ===========================================================================


class TestGetCustomSkillHistory:
    def test_get_history_success(self):
        storage = _make_mock_storage()
        storage.read_history.return_value = [{"action": "edit", "ts": "2024-01-01"}]
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "public"}),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom/my-skill/history")

        assert resp.status_code == 200
        assert len(resp.json()["history"]) == 1

    def test_get_history_not_found(self):
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = False
        storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=False))

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom/missing/history")

        assert resp.status_code == 404

    def test_get_history_not_visible(self):
        user = _make_user(role=UserRole.USER, user_id="user-1", dept_id="dept-1")
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "private", "owner_id": "other"}),
        ):
            app = _make_app(user)
            client = TestClient(app)
            resp = client.get("/api/skills/custom/hidden/history")

        assert resp.status_code == 404

    def test_get_history_no_user_not_public(self):
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "private"}),
        ):
            app = make_authed_test_app()

            async def _none_optional():
                return None

            app.dependency_overrides[get_optional_rbac_user] = _none_optional
            app.include_router(skills_router)
            client = TestClient(app)
            resp = client.get("/api/skills/custom/priv/history")

        assert resp.status_code == 404

    def test_get_history_generic_exception(self):
        storage = _make_mock_storage()
        storage.custom_skill_exists.side_effect = RuntimeError("error")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/custom/error-skill/history")

        assert resp.status_code == 500


# ===========================================================================
# 13. POST /api/skills/custom/{skill_name}/rollback
# ===========================================================================


class TestRollbackCustomSkill:
    def test_rollback_success(self):
        skill = _make_skill("my-skill", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])
        storage.read_history.return_value = [{"prev_content": "# Old content", "ts": "2024-01-01"}]
        storage.custom_skill_exists.return_value = True
        scan = _make_scan_result("allow", "ok")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "public", "owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
            patch("app.gateway.routers.skills.scan_skill_content", new_callable=AsyncMock, return_value=scan),
            patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/my-skill/rollback", json={"history_index": 0})

        assert resp.status_code == 200

    def test_rollback_scanner_blocked(self):
        storage = _make_mock_storage()
        storage.read_history.return_value = [{"prev_content": "# Bad", "ts": "2024-01-01"}]
        storage.custom_skill_exists.return_value = True
        scan = _make_scan_result("block", "Malicious")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
            patch("app.gateway.routers.skills.scan_skill_content", new_callable=AsyncMock, return_value=scan),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/my-skill/rollback", json={"history_index": 0})

        assert resp.status_code == 400
        assert "Rollback blocked" in resp.json()["detail"]

    def test_rollback_no_history(self):
        storage = _make_mock_storage()
        storage.read_history.return_value = []
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/my-skill/rollback", json={"history_index": 0})

        assert resp.status_code == 400
        assert "no history" in resp.json()["detail"]

    def test_rollback_index_out_of_range(self):
        storage = _make_mock_storage()
        storage.read_history.return_value = [{"prev_content": "# content"}]
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/my-skill/rollback", json={"history_index": 999})

        assert resp.status_code == 400
        assert "out of range" in resp.json()["detail"]

    def test_rollback_no_prev_content(self):
        storage = _make_mock_storage()
        storage.read_history.return_value = [{"prev_content": None, "ts": "2024-01-01"}]
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/my-skill/rollback", json={"history_index": 0})

        assert resp.status_code == 400
        assert "no previous content" in resp.json()["detail"]

    def test_rollback_not_found(self):
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = False
        storage.get_skill_history_file.return_value = MagicMock(exists=MagicMock(return_value=False))

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/missing/rollback", json={"history_index": 0})

        assert resp.status_code == 404

    def test_rollback_rbac_denied(self):
        storage = _make_mock_storage()
        storage.custom_skill_exists.return_value = True

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "other"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=False),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/my-skill/rollback", json={"history_index": 0})

        assert resp.status_code == 403

    def test_rollback_generic_exception(self):
        storage = _make_mock_storage()
        storage.custom_skill_exists.side_effect = RuntimeError("error")

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"owner_id": "test-user"}),
            patch("app.gateway.routers.skills.check_resource_modify", return_value=True),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.post("/api/skills/custom/error-skill/rollback", json={"history_index": 0})

        assert resp.status_code == 500


# ===========================================================================
# 14. GET /api/skills/{skill_name}
# ===========================================================================


class TestGetSkill:
    def test_get_public_skill(self):
        skill = _make_skill("my-skill", SkillCategory.PUBLIC)
        storage = _make_mock_storage([skill])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/my-skill")

        assert resp.status_code == 200
        assert resp.json()["name"] == "my-skill"

    def test_get_skill_not_found(self):
        storage = _make_mock_storage([])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/missing")

        assert resp.status_code == 404

    def test_get_custom_skill_visibility_check(self):
        user = _make_user(role=UserRole.USER, user_id="user-1", dept_id="dept-1")
        skill = _make_skill("hidden", SkillCategory.CUSTOM)
        storage = _make_mock_storage([skill])

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills._get_skill_meta", return_value={"visibility": "private", "owner_id": "other"}),
        ):
            app = _make_app(user)
            client = TestClient(app)
            resp = client.get("/api/skills/hidden")

        assert resp.status_code == 404

    def test_get_public_skill_no_visibility_check(self):
        skill = _make_skill("pub-skill", SkillCategory.PUBLIC)
        storage = _make_mock_storage([skill])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/pub-skill")

        assert resp.status_code == 200

    def test_get_skill_generic_exception(self):
        storage = _make_mock_storage()
        storage.load_skills.side_effect = RuntimeError("error")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.get("/api/skills/error-skill")

        assert resp.status_code == 500


# ===========================================================================
# 15. PUT /api/skills/{skill_name}
# ===========================================================================


class TestUpdateSkill:
    def test_update_skill_enable(self):
        skill = _make_skill("my-skill", SkillCategory.PUBLIC, enabled=False)
        updated_skill = _make_skill("my-skill", SkillCategory.PUBLIC, enabled=True)
        storage = _make_mock_storage([skill])

        mock_ext_config = MagicMock()
        mock_ext_config.skills = {}
        mock_ext_config.mcp_servers = {}
        config_path = MagicMock()

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.ExtensionsConfig.resolve_config_path", return_value=config_path),
            patch("app.gateway.routers.skills.get_extensions_config", return_value=mock_ext_config),
            patch("app.gateway.routers.skills.reload_extensions_config"),
            patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.skills.json.dump"),
        ):
            app = _make_app()
            # Override storage to return updated skill on second call
            storage.load_skills.side_effect = [[skill], [updated_skill]]
            client = TestClient(app)
            resp = client.put("/api/skills/my-skill", json={"enabled": True})

        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_update_skill_not_found(self):
        storage = _make_mock_storage([])

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/missing", json={"enabled": True})

        assert resp.status_code == 404

    def test_update_skill_invalid_name(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.put("/api/skills/invalid name!", json={"enabled": True})
        assert resp.status_code == 422

    def test_update_skill_config_path_none(self):
        skill = _make_skill("my-skill")
        storage = _make_mock_storage([skill])

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.ExtensionsConfig.resolve_config_path", return_value=None),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/my-skill", json={"enabled": True})

        assert resp.status_code == 500

    def test_update_skill_reload_fails(self):
        skill = _make_skill("my-skill")
        storage = _make_mock_storage([skill])
        # After reload, return empty list so updated_skill is None
        storage.load_skills.side_effect = [[skill], []]

        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage),
            patch("app.gateway.routers.skills.ExtensionsConfig.resolve_config_path", return_value=MagicMock()),
            patch("app.gateway.routers.skills.get_extensions_config", return_value=MagicMock(skills={}, mcp_servers={})),
            patch("app.gateway.routers.skills.reload_extensions_config"),
            patch("app.gateway.routers.skills.refresh_skills_system_prompt_cache_async", new_callable=AsyncMock),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.skills.json.dump"),
        ):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/my-skill", json={"enabled": True})

        assert resp.status_code == 500
        assert "Failed to reload" in resp.json()["detail"]

    def test_update_skill_generic_exception(self):
        storage = _make_mock_storage()
        storage.load_skills.side_effect = RuntimeError("error")

        with patch("app.gateway.routers.skills.get_or_new_skill_storage", return_value=storage):
            app = _make_app()
            client = TestClient(app)
            resp = client.put("/api/skills/my-skill", json={"enabled": True})

        assert resp.status_code == 500
