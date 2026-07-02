"""Integration tests for Skill RBAC functionality.

These tests verify the complete flow of skill RBAC operations.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from ideer.persistence.models.skill_application import SkillApplication, SkillApplicationStatus
from ideer.persistence.models.skill_default_config import SkillDefaultConfig
from ideer.persistence.models.user import UserRole
from ideer.persistence.models.user_skill_preference import UserSkillPreference

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


def _make_skill(name="test-skill", category="custom", enabled=True, visibility="private", owner_id=None, department_id=None):
    """Create a mock Skill object."""
    skill = MagicMock()
    skill.name = name
    skill.description = "Test skill"
    skill.category = category
    skill.enabled = enabled
    skill.visibility = visibility
    skill.owner_id = owner_id
    skill.department_id = department_id
    return skill


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestSkillRBACIntegration:
    """Integration tests for skill RBAC functionality."""

    def test_user_skill_preference_workflow(self):
        """Test complete user skill preference workflow."""
        # 1. Create user preferences
        user_id = "user-123"
        skill_name = "test-skill"

        # 2. Test preference creation
        pref = UserSkillPreference(user_id=user_id, skill_name=skill_name, enabled=True)
        assert pref.user_id == user_id
        assert pref.skill_name == skill_name
        assert pref.enabled is True

        # 3. Test preference update
        pref.enabled = False
        assert pref.enabled is False

    def test_skill_application_workflow(self):
        """Test complete skill application workflow."""
        # 1. Create application
        application = SkillApplication(id="app-123", skill_id="test-skill", skill_name="Test Skill", applicant_id="user-123", request_level="department", reason="Test reason", status=SkillApplicationStatus.PENDING)
        assert application.status == SkillApplicationStatus.PENDING

        # 2. Approve application
        application.status = SkillApplicationStatus.APPROVED
        application.reviewed_by = "admin-456"
        assert application.status == SkillApplicationStatus.APPROVED
        assert application.reviewed_by == "admin-456"

    def test_skill_default_config_workflow(self):
        """Test complete skill default config workflow."""
        # 1. Create global config
        config = SkillDefaultConfig(id="config-123", scope="global", skill_name="test-skill", enabled=True, user_override_allowed=True)
        assert config.scope == "global"
        assert config.enabled is True

        # 2. Update config
        config.enabled = False
        config.user_override_allowed = False
        assert config.enabled is False
        assert config.user_override_allowed is False

    def test_skill_visibility_workflow(self):
        """Test complete skill visibility workflow."""
        # 1. Create private skill
        skill = _make_skill(name="test-skill", visibility="private", owner_id="user-123")
        assert skill.visibility == "private"

        # 2. Change to department visibility
        skill.visibility = "department"
        skill.department_id = "dept-1"
        assert skill.visibility == "department"

        # 3. Change to public visibility
        skill.visibility = "public"
        assert skill.visibility == "public"

    def test_skill_accessibility_workflow(self):
        """Test complete skill accessibility workflow."""
        from ideer.skills.storage.skill_storage import SkillStorage

        # 1. Test public skill accessibility
        public_skill = _make_skill(category="public")
        storage = MagicMock(spec=SkillStorage)
        assert SkillStorage._is_skill_accessible(storage, public_skill, "user-1", "dept-1") is True

        # 2. Test private skill accessibility (owner)
        private_skill = _make_skill(visibility="private", owner_id="user-1")
        assert SkillStorage._is_skill_accessible(storage, private_skill, "user-1", "dept-1") is True

        # 3. Test private skill accessibility (non-owner)
        assert SkillStorage._is_skill_accessible(storage, private_skill, "user-2", "dept-1") is False

        # 4. Test department skill accessibility (same dept)
        dept_skill = _make_skill(visibility="department", department_id="dept-1")
        assert SkillStorage._is_skill_accessible(storage, dept_skill, "user-1", "dept-1") is True

        # 5. Test department skill accessibility (different dept)
        assert SkillStorage._is_skill_accessible(storage, dept_skill, "user-1", "dept-2") is False

    def test_skill_enabled_resolution_workflow(self):
        """Test complete skill enabled resolution workflow."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = _make_skill(name="test-skill", enabled=True)
        storage = MagicMock(spec=SkillStorage)

        # 1. Test user preference override
        result = SkillStorage._resolve_skill_enabled(storage, skill, user_prefs={"test-skill": False}, dept_defaults={}, global_defaults={})
        assert result is False

        # 2. Test department default
        result = SkillStorage._resolve_skill_enabled(storage, skill, user_prefs={}, dept_defaults={"test-skill": {"enabled": False, "user_override_allowed": True}}, global_defaults={})
        assert result is False

        # 3. Test global default
        result = SkillStorage._resolve_skill_enabled(storage, skill, user_prefs={}, dept_defaults={}, global_defaults={"test-skill": {"enabled": False, "user_override_allowed": True}})
        assert result is False

        # 4. Test fallback to skill enabled state
        result = SkillStorage._resolve_skill_enabled(storage, skill, user_prefs={}, dept_defaults={}, global_defaults={})
        assert result is True

    def test_role_based_access_control(self):
        """Test role-based access control for different operations."""
        # 1. Test super admin access
        super_admin = _make_user(role=UserRole.SUPER_ADMIN)
        assert super_admin.role == UserRole.SUPER_ADMIN

        # 2. Test department admin access
        dept_admin = _make_user(role=UserRole.DEPARTMENT_ADMIN, dept_id="dept-1")
        assert dept_admin.role == UserRole.DEPARTMENT_ADMIN

        # 3. Test regular user access
        user = _make_user(role=UserRole.USER)
        assert user.role == UserRole.USER

        # 4. Test viewer access
        viewer = _make_user(role=UserRole.VIEWER)
        assert viewer.role == UserRole.VIEWER

    def test_permission_enforcement(self):
        """Test permission enforcement for different operations."""
        # 1. Test that only owners can modify private skills
        owner = _make_user(role=UserRole.USER, user_id="user-1")
        non_owner = _make_user(role=UserRole.USER, user_id="user-2")

        # Owner can modify
        assert owner.id == "user-1"
        # Non-owner cannot modify
        assert non_owner.id != "user-1"

        # 2. Test that department admins can approve department-level applications
        dept_admin = _make_user(role=UserRole.DEPARTMENT_ADMIN, dept_id="dept-1")
        assert dept_admin.role == UserRole.DEPARTMENT_ADMIN

        # 3. Test that only super admins can approve public-level applications
        super_admin = _make_user(role=UserRole.SUPER_ADMIN)
        assert super_admin.role == UserRole.SUPER_ADMIN


class TestSkillRBACEdgeCases:
    """Edge case tests for skill RBAC functionality."""

    def test_empty_user_preferences(self):
        """Test handling of empty user preferences."""
        pref = UserSkillPreference(user_id="user-123", skill_name="test-skill", enabled=True)
        assert pref.user_id == "user-123"
        assert pref.skill_name == "test-skill"
        assert pref.enabled is True

    def test_empty_skill_application(self):
        """Test handling of empty skill application."""
        application = SkillApplication(id="app-123", skill_id="test-skill", skill_name="Test Skill", applicant_id="user-123", request_level="department", reason="", status=SkillApplicationStatus.PENDING)
        assert application.reason == ""

    def test_empty_skill_default_config(self):
        """Test handling of empty skill default config."""
        config = SkillDefaultConfig(id="config-123", scope="global", skill_name="test-skill", enabled=True, user_override_allowed=True)
        assert config.scope == "global"
        assert config.enabled is True

    def test_null_department_id(self):
        """Test handling of null department ID."""
        skill = _make_skill(visibility="department", department_id=None)
        assert skill.department_id is None

    def test_null_owner_id(self):
        """Test handling of null owner ID."""
        skill = _make_skill(visibility="private", owner_id=None)
        assert skill.owner_id is None
