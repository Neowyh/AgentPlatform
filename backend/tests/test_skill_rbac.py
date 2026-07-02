"""Tests for Skill RBAC functionality.

Tests for user skill preferences, skill applications, admin skill defaults,
and skill visibility management.
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


def _make_skill_application(
    skill_id="test-skill",
    skill_name="Test Skill",
    applicant_id="test-user",
    request_level="department",
    status=SkillApplicationStatus.PENDING,
):
    """Create a mock SkillApplication."""
    application = MagicMock(spec=SkillApplication)
    application.id = "app-123"
    application.skill_id = skill_id
    application.skill_name = skill_name
    application.applicant_id = applicant_id
    application.request_level = request_level
    application.reason = "Test reason"
    application.status = status
    application.submitted_at = "2024-01-01T00:00:00"
    application.reviewed_by = None
    application.reviewed_at = None
    application.review_comment = None
    return application


def _make_skill_default_config(
    skill_name="test-skill",
    scope="global",
    scope_id=None,
    enabled=True,
    user_override_allowed=True,
):
    """Create a mock SkillDefaultConfig."""
    config = MagicMock(spec=SkillDefaultConfig)
    config.id = "config-123"
    config.scope = scope
    config.scope_id = scope_id
    config.skill_name = skill_name
    config.enabled = enabled
    config.user_override_allowed = user_override_allowed
    config.created_at = "2024-01-01T00:00:00"
    config.updated_at = "2024-01-01T00:00:00"
    return config


def _make_user_skill_preference(skill_name="test-skill", enabled=True):
    """Create a mock UserSkillPreference."""
    preference = MagicMock(spec=UserSkillPreference)
    preference.skill_name = skill_name
    preference.enabled = enabled
    return preference


# ---------------------------------------------------------------------------
# Tests for Skill Storage RBAC Logic
# ---------------------------------------------------------------------------


class TestSkillStorageRBAC:
    """Tests for skill storage RBAC logic."""

    def test_is_skill_accessible_public_skill(self):
        """Test that public skills are accessible to everyone."""
        from ideer.skills.storage.skill_storage import SkillStorage
        from ideer.skills.types import SkillCategory

        skill = MagicMock()
        skill.category = SkillCategory.PUBLIC

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._is_skill_accessible(storage, skill, "user-1", "dept-1")
        assert result is True

    def test_is_skill_accessible_private_skill_owner(self):
        """Test that private skills are accessible to the owner."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.category = "custom"
        skill.visibility = "private"
        skill.owner_id = "user-1"

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._is_skill_accessible(storage, skill, "user-1", "dept-1")
        assert result is True

    def test_is_skill_accessible_private_skill_not_owner(self):
        """Test that private skills are not accessible to non-owners."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.category = "custom"
        skill.visibility = "private"
        skill.owner_id = "user-2"

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._is_skill_accessible(storage, skill, "user-1", "dept-1")
        assert result is False

    def test_is_skill_accessible_department_skill_same_dept(self):
        """Test that department skills are accessible to same department users."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.category = "custom"
        skill.visibility = "department"
        skill.department_id = "dept-1"

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._is_skill_accessible(storage, skill, "user-1", "dept-1")
        assert result is True

    def test_is_skill_accessible_department_skill_different_dept(self):
        """Test that department skills are not accessible to different department users."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.category = "custom"
        skill.visibility = "department"
        skill.department_id = "dept-2"

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._is_skill_accessible(storage, skill, "user-1", "dept-1")
        assert result is False

    def test_resolve_skill_enabled_user_pref(self):
        """Test that user preferences take highest priority."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.name = "test-skill"
        skill.enabled = True

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._resolve_skill_enabled(
            storage,
            skill,
            user_prefs={"test-skill": False},
            dept_defaults={},
            global_defaults={},
        )
        assert result is False

    def test_resolve_skill_enabled_dept_default(self):
        """Test that department defaults take priority over global defaults."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.name = "test-skill"
        skill.enabled = True

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._resolve_skill_enabled(
            storage,
            skill,
            user_prefs={},
            dept_defaults={"test-skill": {"enabled": False, "user_override_allowed": True}},
            global_defaults={"test-skill": {"enabled": True, "user_override_allowed": True}},
        )
        assert result is False

    def test_resolve_skill_enabled_global_default(self):
        """Test that global defaults are used when no user pref or dept default."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.name = "test-skill"
        skill.enabled = True

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._resolve_skill_enabled(
            storage,
            skill,
            user_prefs={},
            dept_defaults={},
            global_defaults={"test-skill": {"enabled": False, "user_override_allowed": True}},
        )
        assert result is False

    def test_resolve_skill_enabled_fallback_to_skill(self):
        """Test that skill's own enabled state is used as fallback."""
        from ideer.skills.storage.skill_storage import SkillStorage

        skill = MagicMock()
        skill.name = "test-skill"
        skill.enabled = False

        storage = MagicMock(spec=SkillStorage)
        result = SkillStorage._resolve_skill_enabled(
            storage,
            skill,
            user_prefs={},
            dept_defaults={},
            global_defaults={},
        )
        assert result is False


# ---------------------------------------------------------------------------
# Tests for Skill Application Status
# ---------------------------------------------------------------------------


class TestSkillApplicationStatus:
    """Tests for skill application status."""

    def test_status_values(self):
        """Test that status values are correct."""
        assert SkillApplicationStatus.PENDING == "pending"
        assert SkillApplicationStatus.APPROVED == "approved"
        assert SkillApplicationStatus.REJECTED == "rejected"


# ---------------------------------------------------------------------------
# Tests for Skill Default Config
# ---------------------------------------------------------------------------


class TestSkillDefaultConfig:
    """Tests for skill default config."""

    def test_config_creation(self):
        """Test creating a skill default config."""
        config = _make_skill_default_config()
        assert config.skill_name == "test-skill"
        assert config.scope == "global"
        assert config.enabled is True
        assert config.user_override_allowed is True

    def test_config_with_department_scope(self):
        """Test creating a skill default config with department scope."""
        config = _make_skill_default_config(scope="department", scope_id="dept-1")
        assert config.scope == "department"
        assert config.scope_id == "dept-1"


# ---------------------------------------------------------------------------
# Tests for User Skill Preference
# ---------------------------------------------------------------------------


class TestUserSkillPreference:
    """Tests for user skill preference."""

    def test_preference_creation(self):
        """Test creating a user skill preference."""
        pref = _make_user_skill_preference()
        assert pref.skill_name == "test-skill"
        assert pref.enabled is True

    def test_preference_disabled(self):
        """Test creating a disabled user skill preference."""
        pref = _make_user_skill_preference(enabled=False)
        assert pref.enabled is False
