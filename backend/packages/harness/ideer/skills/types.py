from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ideer.persistence.models.user import ResourceVisibility

SKILL_MD_FILE = "SKILL.md"


class SkillCategory(StrEnum):
    """Source category for a skill.

    - ``PUBLIC``: built-in skill bundled with the platform, read-only.
    - ``CUSTOM``: user-authored skill that can be edited or deleted.
    """

    PUBLIC = "public"
    CUSTOM = "custom"


@dataclass
class Skill:
    """Represents a skill with its metadata and file path"""

    name: str
    description: str
    license: str | None
    skill_dir: Path
    skill_file: Path
    relative_path: Path  # Relative path from category root to skill directory
    category: SkillCategory  # 'public' or 'custom'
    allowed_tools: list[str] | None = None
    enabled: bool = False  # Whether this skill is enabled
    requires_internet: bool = False  # Whether this skill requires internet access
    visibility: ResourceVisibility = ResourceVisibility.PRIVATE
    owner_id: str | None = None
    department_id: str | None = None

    @property
    def skill_path(self) -> str:
        """Returns the relative path from the category root (skills/{category}) to this skill's directory"""
        path = self.relative_path.as_posix()
        return "" if path == "." else path

    def get_container_path(self, container_base_path: str = "/mnt/skills") -> str:
        """
        Get the full path to this skill in the container.

        Args:
            container_base_path: Base path where skills are mounted in the container

        Returns:
            Full container path to the skill directory

        Raises:
            ValueError: If the resolved path escapes the container base directory
        """
        category_base = f"{container_base_path}/{self.category}"
        skill_path = self.skill_path
        if skill_path:
            full_path = f"{category_base}/{skill_path}"
        else:
            full_path = category_base

        # Prevent path traversal: resolve and verify the path stays under container_base_path
        resolved = Path(full_path).resolve()
        resolved_base = Path(container_base_path).resolve()
        if not resolved.is_relative_to(resolved_base):
            raise ValueError(f"Path traversal detected: skill path '{skill_path}' escapes container base '{container_base_path}'")

        return full_path

    def get_container_file_path(self, container_base_path: str = "/mnt/skills") -> str:
        """
        Get the full path to this skill's main file (SKILL.md) in the container.

        Args:
            container_base_path: Base path where skills are mounted in the container

        Returns:
            Full container path to the skill's SKILL.md file
        """
        return f"{self.get_container_path(container_base_path)}/SKILL.md"

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, description={self.description!r}, category={self.category!r})"
