"""Tests targeting specific uncovered lines in ideer.skills.parser.

Covered lines:
  - Line 30: empty tool name in allowed-tools list (ValueError)
  - Lines 67-68: front-matter is not a YAML mapping (logger.error, return None)
  - Line 84: name or description becomes empty after stripping whitespace (return None)
  - Lines 111-113: unexpected exception during parsing (logger.exception, return None)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ideer.skills.parser import parse_allowed_tools, parse_skill_file
from ideer.skills.types import SkillCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(tmp_path: Path, front_matter: str, body: str = "# Skill\n") -> Path:
    """Write a minimal SKILL.md under *tmp_path* and return its path."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(f"---\n{front_matter}\n---\n{body}", encoding="utf-8")
    return skill_file


def _make_skill_dir(tmp_path: Path, name: str = "test-skill") -> Path:
    """Create and return a skill directory (no file written yet)."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    return skill_dir


# ---------------------------------------------------------------------------
# 1. parse_allowed_tools – empty tool name in list  (line 30)
# ---------------------------------------------------------------------------


class TestParseAllowedToolsEmptyName:
    """Line 30: tool name is empty string or whitespace-only after strip."""

    def test_empty_string_in_list(self, tmp_path):
        """An empty string in the allowed-tools list raises ValueError."""
        skill_file = tmp_path / "SKILL.md"
        with pytest.raises(ValueError, match="cannot contain empty tool names"):
            parse_allowed_tools(["valid-tool", ""], skill_file)

    def test_whitespace_only_in_list(self, tmp_path):
        """A whitespace-only string in the allowed-tools list raises ValueError."""
        skill_file = tmp_path / "SKILL.md"
        with pytest.raises(ValueError, match="cannot contain empty tool names"):
            parse_allowed_tools(["   ", "bash"], skill_file)

    def test_single_empty_string(self, tmp_path):
        """A single empty string in the list raises ValueError."""
        skill_file = tmp_path / "SKILL.md"
        with pytest.raises(ValueError, match="cannot contain empty tool names"):
            parse_allowed_tools([""], skill_file)


# ---------------------------------------------------------------------------
# 2. parse_skill_file – front-matter is not a YAML mapping  (lines 67-68)
# ---------------------------------------------------------------------------


class TestParseSkillFileNotAMapping:
    """Lines 67-68: front-matter parses to a non-dict (e.g. a YAML list)."""

    def test_front_matter_is_a_list(self, tmp_path):
        """Front-matter that is a YAML list should return None."""
        skill_file = _write_skill(tmp_path, "- item1\n- item2")
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_front_matter_is_a_string(self, tmp_path):
        """Front-matter that is a plain YAML string should return None."""
        skill_file = _write_skill(tmp_path, "just-a-string")
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_front_matter_is_a_number(self, tmp_path):
        """Front-matter that is a YAML number should return None."""
        skill_file = _write_skill(tmp_path, "42")
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_front_matter_is_a_boolean(self, tmp_path):
        """Front-matter that is a YAML boolean should return None."""
        skill_file = _write_skill(tmp_path, "true")
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None


# ---------------------------------------------------------------------------
# 3. parse_skill_file – name/description whitespace-only after strip  (line 84)
# ---------------------------------------------------------------------------


class TestParseSkillFileWhitespaceNameDescription:
    """Line 84: name or description is empty after stripping whitespace."""

    def test_name_whitespace_only(self, tmp_path):
        """A name consisting only of spaces should return None."""
        skill_file = _write_skill(tmp_path, 'name: "   "\ndescription: A valid description')
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_description_whitespace_only(self, tmp_path):
        """A description consisting only of spaces should return None."""
        skill_file = _write_skill(tmp_path, 'name: valid-name\ndescription: "   "')
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_name_tabs_only(self, tmp_path):
        """A name consisting only of tabs should return None."""
        skill_file = _write_skill(tmp_path, 'name: "\t\t"\ndescription: A valid description')
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_both_whitespace(self, tmp_path):
        """Both name and description whitespace-only should return None."""
        skill_file = _write_skill(tmp_path, 'name: " "\ndescription: "\t"')
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_newline_only_name(self, tmp_path):
        """A name that is just a newline character should return None."""
        skill_file = _write_skill(tmp_path, 'name: "\n"\ndescription: valid')
        skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None


# ---------------------------------------------------------------------------
# 4. parse_skill_file – unexpected exception  (lines 111-113)
# ---------------------------------------------------------------------------


class TestParseSkillFileUnexpectedException:
    """Lines 111-113: catch-all exception handler returns None."""

    def test_read_permission_error(self, tmp_path):
        """If reading the file raises an unexpected OSError, return None."""
        skill_file = _write_skill(tmp_path, "name: my-skill\ndescription: Test")
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_unexpected_runtime_error(self, tmp_path):
        """An arbitrary RuntimeError during file read is caught and returns None."""
        skill_file = _write_skill(tmp_path, "name: my-skill\ndescription: Test")
        with patch.object(Path, "read_text", side_effect=RuntimeError("kaboom")):
            skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_index_error_during_read(self, tmp_path):
        """An IndexError during file read is caught and returns None."""
        skill_file = _write_skill(tmp_path, "name: my-skill\ndescription: Test")
        with patch.object(Path, "read_text", side_effect=IndexError("out of bounds")):
            skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None

    def test_recursion_error(self, tmp_path):
        """A RecursionError during file read is caught and returns None."""
        skill_file = _write_skill(tmp_path, "name: my-skill\ndescription: Test")
        with patch.object(Path, "read_text", side_effect=RecursionError()):
            skill = parse_skill_file(skill_file, category=SkillCategory.CUSTOM)
        assert skill is None
