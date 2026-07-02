"""Abstract SkillStorage base class with template-method flows."""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from ideer.skills.types import SKILL_MD_FILE, Skill, SkillCategory  # noqa: F401

logger = logging.getLogger(__name__)

_SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillStorage(ABC):
    """Abstract base for skill storage backends.

    Subclasses implement a small set of storage-medium-specific atomic
    operations; this base class provides final template-method flows
    (load_skills, history serialisation, path helpers, validation) that
    compose them with protocol-level helpers.
    """

    def __init__(self, container_path: str = "/mnt/skills") -> None:
        self._container_root = container_path
        self._init_caches()

    def _init_caches(self) -> None:
        """Initialize all cache state for skill defaults and user preferences."""
        self._global_defaults_cache: dict[str, dict] | None = None
        self._global_defaults_cache_lock = asyncio.Lock()
        self._global_defaults_cache_time: float = 0

        self._dept_defaults_cache: dict[str, dict[str, dict]] = {}
        self._dept_defaults_cache_lock = asyncio.Lock()
        self._dept_defaults_cache_time: dict[str, float] = {}

        self._user_prefs_cache: dict[str, dict[str, bool]] = {}
        self._user_prefs_cache_lock = asyncio.Lock()
        self._user_prefs_cache_time: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Static protocol helpers (not storage-specific)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_skill_name(name: str) -> str:
        """Validate and normalise a skill name; return the normalised form."""
        normalized = name.strip()
        if not _SKILL_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("Skill name must be hyphen-case using lowercase letters, digits, and hyphens only.")
        if len(normalized) > 64:
            raise ValueError("Skill name must be 64 characters or fewer.")
        return normalized

    @staticmethod
    def validate_relative_path(relative_path: str, base_dir: Path) -> Path:
        """Validate *relative_path* against *base_dir* and return the resolved target.

        Checks that *relative_path* is non-empty, then joins it with *base_dir*
        and resolves the result (following symlinks).  Raises ``ValueError`` if
        the resolved target does not lie within *base_dir*.
        """
        if not relative_path:
            raise ValueError("relative_path must not be empty.")
        resolved_base = base_dir.resolve()
        target = (resolved_base / relative_path).resolve()
        try:
            target.relative_to(resolved_base)
        except ValueError as exc:
            raise ValueError("relative_path must resolve within the skill directory.") from exc
        return target

    @staticmethod
    def validate_skill_markdown_content(name: str, content: str) -> None:
        """Validate SKILL.md content: parse frontmatter and check name matches."""
        import tempfile

        from ideer.skills.validation import _validate_skill_frontmatter

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_skill_dir = Path(tmp_dir) / SkillStorage.validate_skill_name(name)
            temp_skill_dir.mkdir(parents=True, exist_ok=True)
            (temp_skill_dir / SKILL_MD_FILE).write_text(content, encoding="utf-8")
            is_valid, message, parsed_name = _validate_skill_frontmatter(temp_skill_dir)
            if not is_valid:
                raise ValueError(message)
            if parsed_name != name:
                raise ValueError(f"Frontmatter name '{parsed_name}' must match requested skill name '{name}'.")

    def ensure_safe_support_path(self, name: str, relative_path: str) -> Path:
        """Validate and return the resolved absolute path for a support file."""
        _ALLOWED_SUPPORT_SUBDIRS = {"references", "templates", "scripts", "assets"}
        skill_dir = self.get_custom_skill_dir(self.validate_skill_name(name)).resolve()
        if not relative_path or relative_path.endswith("/"):
            raise ValueError("Supporting file path must include a filename.")
        relative = Path(relative_path)
        if relative.is_absolute():
            raise ValueError("Supporting file path must be relative.")
        if any(part in {"..", ""} for part in relative.parts):
            raise ValueError("Supporting file path must not contain parent-directory traversal.")
        top_level = relative.parts[0] if relative.parts else ""
        if top_level not in _ALLOWED_SUPPORT_SUBDIRS:
            raise ValueError(f"Supporting files must live under one of: {', '.join(sorted(_ALLOWED_SUPPORT_SUBDIRS))}.")
        target = (skill_dir / relative).resolve()
        allowed_root = (skill_dir / top_level).resolve()
        try:
            target.relative_to(allowed_root)
        except ValueError as exc:
            raise ValueError("Supporting file path must stay within the selected support directory.") from exc
        return target

    # ------------------------------------------------------------------
    # Abstract atomic operations (storage-medium specific)
    # ------------------------------------------------------------------

    @abstractmethod
    def get_skills_root_path(self) -> Path:
        """Absolute host path to the skills root, used for sandbox mounts.

        Origin: ``ideer.skills.loader.get_skills_root_path``.
        """

    @abstractmethod
    def _iter_skill_files(self) -> Iterable[tuple[SkillCategory, Path, Path]]:
        """Yield ``(category, category_root, skill_md_path)`` for every SKILL.md.

        Origin: extracted from directory-walk logic inside
        ``ideer.skills.loader.load_skills``.
        """

    @abstractmethod
    def read_custom_skill(self, name: str) -> str:
        """Read SKILL.md content for a custom skill.

        Origin: ``ideer.skills.manager.read_custom_skill_content``.
        """

    @abstractmethod
    def write_custom_skill(self, name: str, relative_path: str, content: str) -> None:
        """Atomically write a text file under ``custom/<name>/<relative_path>``.

        Origin: ``ideer.skills.manager.atomic_write``.
        """

    @abstractmethod
    async def ainstall_skill_from_archive(self, archive_path: str | Path) -> dict:
        """Async install of a skill from a ``.skill`` ZIP archive.

        Origin: ``ideer.skills.installer.ainstall_skill_from_archive``.
        """

    def install_skill_from_archive(self, archive_path: str | Path) -> dict:
        """Sync wrapper — delegates to :meth:`ainstall_skill_from_archive`."""
        from ideer.skills.installer import _run_async_install

        return _run_async_install(self.ainstall_skill_from_archive(archive_path))

    @abstractmethod
    def delete_custom_skill(self, name: str, *, history_meta: dict | None = None) -> None:
        """Delete a custom skill (validation + optional history + directory removal).

        Origin: ``app.gateway.routers.skills.delete_custom_skill`` + ``skill_manage_tool``.
        """

    @abstractmethod
    def custom_skill_exists(self, name: str) -> bool:
        """Origin: ``ideer.skills.manager.custom_skill_exists``."""

    @abstractmethod
    def public_skill_exists(self, name: str) -> bool:
        """Origin: ``ideer.skills.manager.public_skill_exists``."""

    @abstractmethod
    def append_history(self, name: str, record: dict) -> None:
        """Append a JSONL history entry for ``name``.

        Origin: ``ideer.skills.manager.append_history``.
        """

    @abstractmethod
    def read_history(self, name: str) -> list[dict]:
        """Return all history records for ``name``, oldest first.

        Origin: ``ideer.skills.manager.read_history``.
        """

    # ------------------------------------------------------------------
    # Concrete path helpers (layout is part of the SKILL.md protocol)
    # ------------------------------------------------------------------

    def get_container_root(self) -> str:
        """Origin: ``ideer.config.skills_config.SkillsConfig.container_path`` accessor."""
        return self._container_root

    def get_custom_skill_dir(self, name: str) -> Path:
        """Path to ``custom/<name>``. Does not create the directory.

        Origin: ``ideer.skills.manager.get_custom_skill_dir``.
        """
        normalized_name = self.validate_skill_name(name)
        return self.get_skills_root_path() / SkillCategory.CUSTOM.value / normalized_name

    def get_custom_skill_file(self, name: str) -> Path:
        """Path to ``custom/<name>/SKILL.md``.

        Origin: ``ideer.skills.manager.get_custom_skill_file``.
        """
        normalized_name = self.validate_skill_name(name)
        return self.get_custom_skill_dir(normalized_name) / SKILL_MD_FILE

    def get_skill_history_file(self, name: str) -> Path:
        """Path to ``custom/.history/<name>.jsonl``. Does not create parents.

        Origin: ``ideer.skills.manager.get_skill_history_file``.
        """
        normalized_name = self.validate_skill_name(name)
        return self.get_skills_root_path() / SkillCategory.CUSTOM.value / ".history" / f"{normalized_name}.jsonl"

    # ------------------------------------------------------------------
    # Final template-method flows
    # ------------------------------------------------------------------

    def load_skills(self, *, enabled_only: bool = False) -> list[Skill]:
        """Discover all skills, merge enabled state, sort and optionally filter.

        Origin: ``ideer.skills.loader.load_skills``.
        """
        from ideer.skills.parser import parse_skill_file

        skills_by_name: dict[str, Skill] = {}
        for category, category_root, md_path in self._iter_skill_files():
            skill = parse_skill_file(
                md_path,
                category=category,
                relative_path=md_path.parent.relative_to(category_root),
            )
            if skill:
                skills_by_name[skill.name] = skill

        skills = list(skills_by_name.values())

        # Merge enabled state from extensions config (re-read every call so
        # changes made by another process are picked up immediately).
        try:
            from ideer.config.extensions_config import ExtensionsConfig

            extensions_config = ExtensionsConfig.from_file()
            for skill in skills:
                skill.enabled = extensions_config.is_skill_enabled(skill.name, skill.category)
        except Exception as e:
            logger.warning("Failed to load extensions config: %s", e)

        # Filter out internet-dependent skills in offline mode
        from ideer.config.network_mode import is_offline

        if is_offline():
            offline_skipped = [s.name for s in skills if s.requires_internet]
            if offline_skipped:
                logger.warning(
                    "Offline mode: skipping %d internet-dependent skill(s): %s",
                    len(offline_skipped),
                    ", ".join(offline_skipped),
                )
            skills = [s for s in skills if not s.requires_internet]

        if enabled_only:
            skills = [s for s in skills if s.enabled]

        skills.sort(key=lambda s: s.name)
        return skills

    def ensure_custom_skill_is_editable(self, name: str) -> None:
        """Origin: ``ideer.skills.manager.ensure_custom_skill_is_editable``."""
        if self.custom_skill_exists(name):
            return
        if self.public_skill_exists(name):
            raise ValueError(f"'{name}' is a built-in skill. To customise it, create a new skill under skills/custom/.")
        raise FileNotFoundError(f"Custom skill '{name}' not found.")

    async def load_skills_for_user(self, user_id: str, department_id: str | None = None, role: str | None = None) -> list[Skill]:
        """Load skills for a specific user, merging default configs and user preferences.

        Priority order: user preferences > department defaults > global defaults
        When user_override_allowed is False, user preferences are ignored.

        Args:
            user_id: The user ID to load skills for
            department_id: The user's department ID (optional)
            role: The user's role (optional, e.g. "super_admin", "department_admin")

        Returns:
            List of skills that are enabled for this user
        """
        # 1. Get all skills the user has access to
        accessible_skills = self._get_accessible_skills(user_id, department_id, role)

        # 2. Get global default configs
        global_defaults = await self._get_global_skill_defaults()

        # 3. Get department default configs
        dept_defaults = await self._get_dept_skill_defaults(department_id) if department_id else {}

        # 4. Get user personal preferences
        user_prefs = await self._get_user_skill_preferences(user_id)

        # 5. Merge configs (priority: user prefs > dept defaults > global defaults)
        effective_skills = []
        for skill in accessible_skills:
            enabled = self._resolve_skill_enabled(
                skill,
                user_prefs=user_prefs,
                dept_defaults=dept_defaults,
                global_defaults=global_defaults,
            )
            if enabled:
                effective_skills.append(skill)

        return effective_skills

    def _get_accessible_skills(self, user_id: str, department_id: str | None, role: str | None = None) -> list[Skill]:
        """Get skills that the user has permission to access."""
        all_skills = self.load_skills(enabled_only=False)

        accessible = []
        for skill in all_skills:
            if self._is_skill_accessible(skill, user_id, department_id, role):
                accessible.append(skill)

        return accessible

    def _is_skill_accessible(self, skill: Skill, user_id: str, department_id: str | None, role: str | None = None) -> bool:
        """Check if user has permission to access the skill."""
        # Public skills are accessible to everyone
        if skill.category == SkillCategory.PUBLIC:
            return True

        # Super admin can access everything
        if role == "super_admin":
            return True

        # For custom skills, check visibility
        visibility = getattr(skill, "visibility", "private")
        owner_id = getattr(skill, "owner_id", None)
        skill_department_id = getattr(skill, "department_id", None)

        # Public custom skills are accessible to everyone
        if visibility == "public":
            return True

        # Department custom skills are accessible to same department users
        if visibility == "department":
            if department_id and skill_department_id and department_id == skill_department_id:
                return True

        # Department admin can access any skill in their own department
        if role == "department_admin":
            if department_id and skill_department_id and department_id == skill_department_id:
                return True

        # Private custom skills are only accessible to the owner
        if owner_id and owner_id == user_id:
            return True

        return False

    async def _get_global_skill_defaults(self) -> dict[str, dict]:
        """Get global skill default configurations with caching."""
        import time

        async with self._global_defaults_cache_lock:
            current_time = time.time()
            if self._global_defaults_cache is not None and (current_time - self._global_defaults_cache_time) < 300:
                return self._global_defaults_cache

            try:
                from sqlalchemy import select

                from ideer.persistence.engine import get_session_factory
                from ideer.persistence.models.skill_default_config import SkillDefaultConfig

                sf = get_session_factory()
                if sf is None:
                    return {}

                async with sf() as session:
                    stmt = select(SkillDefaultConfig).where(SkillDefaultConfig.scope == "global")
                    result = await session.execute(stmt)
                    configs = result.scalars().all()
                    defaults = {
                        config.skill_name: {
                            "enabled": config.enabled,
                            "user_override_allowed": config.user_override_allowed,
                        }
                        for config in configs
                    }

                    self._global_defaults_cache = defaults
                    self._global_defaults_cache_time = current_time

                    return defaults

            except Exception as e:
                logger.warning("Failed to load global skill defaults: %s", e)
                return {}

    async def _get_dept_skill_defaults(self, department_id: str) -> dict[str, dict]:
        """Get department skill default configurations with caching."""
        import time

        async with self._dept_defaults_cache_lock:
            current_time = time.time()
            if department_id in self._dept_defaults_cache and (current_time - self._dept_defaults_cache_time.get(department_id, 0)) < 300:
                return self._dept_defaults_cache[department_id]

            try:
                from sqlalchemy import select

                from ideer.persistence.engine import get_session_factory
                from ideer.persistence.models.skill_default_config import SkillDefaultConfig

                sf = get_session_factory()
                if sf is None:
                    return {}

                async with sf() as session:
                    stmt = select(SkillDefaultConfig).where(
                        SkillDefaultConfig.scope == "department",
                        SkillDefaultConfig.scope_id == department_id,
                    )
                    result = await session.execute(stmt)
                    configs = result.scalars().all()
                    defaults = {
                        config.skill_name: {
                            "enabled": config.enabled,
                            "user_override_allowed": config.user_override_allowed,
                        }
                        for config in configs
                    }

                    self._dept_defaults_cache[department_id] = defaults
                    self._dept_defaults_cache_time[department_id] = current_time

                    return defaults

            except Exception as e:
                logger.warning("Failed to load department skill defaults: %s", e)
                return {}

    async def _get_user_skill_preferences(self, user_id: str) -> dict[str, bool]:
        """Get user's personal skill preferences with caching."""
        import time

        async with self._user_prefs_cache_lock:
            current_time = time.time()
            if user_id in self._user_prefs_cache and (current_time - self._user_prefs_cache_time.get(user_id, 0)) < 120:
                return self._user_prefs_cache[user_id]

            try:
                from sqlalchemy import select

                from ideer.persistence.engine import get_session_factory
                from ideer.persistence.models.user_skill_preference import UserSkillPreference

                sf = get_session_factory()
                if sf is None:
                    return {}

                async with sf() as session:
                    stmt = select(UserSkillPreference).where(UserSkillPreference.user_id == user_id)
                    result = await session.execute(stmt)
                    prefs = result.scalars().all()
                    preferences = {pref.skill_name: pref.enabled for pref in prefs}

                    self._user_prefs_cache[user_id] = preferences
                    self._user_prefs_cache_time[user_id] = current_time

                    return preferences

            except Exception as e:
                logger.warning("Failed to load user skill preferences: %s", e)
                return {}

    def _resolve_skill_enabled(
        self,
        skill: Skill,
        user_prefs: dict[str, bool],
        dept_defaults: dict[str, dict],
        global_defaults: dict[str, dict],
    ) -> bool:
        """Resolve whether a skill is enabled based on priority order.

        Priority: user prefs > dept defaults > global defaults > skill.enabled
        When user_override_allowed is False at dept or global level,
        user preferences are ignored.
        """
        skill_name = skill.name

        # Check if any level has user_override_allowed=False
        dept_config = dept_defaults.get(skill_name)
        global_config = global_defaults.get(skill_name)

        if dept_config and not dept_config.get("user_override_allowed", True):
            return dept_config.get("enabled", True)
        if global_config and not global_config.get("user_override_allowed", True):
            return global_config.get("enabled", True)

        # User override is allowed — apply normal priority
        if skill_name in user_prefs:
            return user_prefs[skill_name]
        if dept_config is not None:
            return dept_config.get("enabled", True)
        if global_config is not None:
            return global_config.get("enabled", True)

        return skill.enabled

    async def clear_cache(self) -> None:
        """Clear all caches for skill defaults and user preferences."""
        async with self._global_defaults_cache_lock:
            self._global_defaults_cache = None
            self._global_defaults_cache_time = 0

        async with self._dept_defaults_cache_lock:
            self._dept_defaults_cache = {}
            self._dept_defaults_cache_time = {}

        async with self._user_prefs_cache_lock:
            self._user_prefs_cache = {}
            self._user_prefs_cache_time = {}

        logger.info("Skill storage cache cleared")
