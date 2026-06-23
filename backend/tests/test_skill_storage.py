"""Tests for SkillStorage abstract base class."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ideer.skills.storage.skill_storage import _SKILL_NAME_PATTERN, SkillStorage
from ideer.skills.types import SKILL_MD_FILE, Skill, SkillCategory

# ---------------------------------------------------------------------------
# Concrete subclass for testing
# ---------------------------------------------------------------------------


class _FakeSkillStorage(SkillStorage):
    """Minimal concrete implementation for testing the ABC."""

    def __init__(self, root_path: Path, container_path: str = "/mnt/skills"):
        super().__init__(container_path)
        self._root = root_path
        self._skills: dict[str, str] = {}
        self._history: dict[str, list[dict]] = {}
        self._public_skills: set[str] = set()
        self._written_files: list[tuple[str, str, str]] = []

    def get_skills_root_path(self) -> Path:
        return self._root

    def _iter_skill_files(self):
        for name, content in self._skills.items():
            cat = SkillCategory.CUSTOM if not name.startswith("pub-") else SkillCategory.PUBLIC
            cat_root = self._root / cat.value
            md_path = cat_root / name / SKILL_MD_FILE
            yield cat, cat_root, md_path

    def read_custom_skill(self, name: str) -> str:
        self.validate_skill_name(name)
        return self._skills.get(name, "")

    def write_custom_skill(self, name: str, relative_path: str, content: str) -> None:
        self._written_files.append((name, relative_path, content))

    async def ainstall_skill_from_archive(self, archive_path):
        return {"installed": True, "name": "test-skill"}

    def delete_custom_skill(self, name: str, *, history_meta=None):
        self.validate_skill_name(name)
        self._skills.pop(name, None)

    def custom_skill_exists(self, name: str) -> bool:
        return name in self._skills

    def public_skill_exists(self, name: str) -> bool:
        return name in self._public_skills

    def append_history(self, name: str, record: dict) -> None:
        self._history.setdefault(name, []).append(record)

    def read_history(self, name: str) -> list[dict]:
        return list(self._history.get(name, []))


# ---------------------------------------------------------------------------
# _SKILL_NAME_PATTERN
# ---------------------------------------------------------------------------


class TestSkillNamePattern:
    def test_valid_names(self):
        for name in ["my-skill", "skill123", "a", "test-skill-2"]:
            assert _SKILL_NAME_PATTERN.fullmatch(name), f"Expected '{name}' to match"

    def test_invalid_names(self):
        for name in ["My-Skill", "my_skill", "my skill", "-leading", "trailing-", "UPPER"]:
            assert not _SKILL_NAME_PATTERN.fullmatch(name), f"Expected '{name}' to NOT match"


# ---------------------------------------------------------------------------
# validate_skill_name
# ---------------------------------------------------------------------------


class TestValidateSkillName:
    def test_valid_name(self):
        assert SkillStorage.validate_skill_name("my-skill") == "my-skill"

    def test_strips_whitespace(self):
        assert SkillStorage.validate_skill_name("  my-skill  ") == "my-skill"

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="hyphen-case"):
            SkillStorage.validate_skill_name("My_Skill")

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="64 characters"):
            SkillStorage.validate_skill_name("a" * 65)

    def test_exactly_64_chars(self):
        name = "a" * 64
        assert SkillStorage.validate_skill_name(name) == name

    def test_empty_after_strip_raises(self):
        with pytest.raises(ValueError, match="hyphen-case"):
            SkillStorage.validate_skill_name("   ")


# ---------------------------------------------------------------------------
# validate_relative_path
# ---------------------------------------------------------------------------


class TestValidateRelativePath:
    def test_valid_path(self, tmp_path):
        result = SkillStorage.validate_relative_path("subdir/file.txt", tmp_path)
        assert result == (tmp_path / "subdir/file.txt").resolve()

    def test_empty_path_raises(self, tmp_path):
        with pytest.raises(ValueError, match="must not be empty"):
            SkillStorage.validate_relative_path("", tmp_path)

    def test_traversal_raises(self, tmp_path):
        with pytest.raises(ValueError, match="within the skill directory"):
            SkillStorage.validate_relative_path("../escape.txt", tmp_path)

    def test_absolute_within_base(self, tmp_path):
        # A relative path that resolves within base_dir should work
        result = SkillStorage.validate_relative_path("file.txt", tmp_path)
        assert result == (tmp_path / "file.txt").resolve()


# ---------------------------------------------------------------------------
# ensure_safe_support_path
# ---------------------------------------------------------------------------


class TestEnsureSafeSupportPath:
    def test_valid_support_path(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        skill_dir = tmp_path / "custom" / "my-skill"
        (skill_dir / "references").mkdir(parents=True)
        result = storage.ensure_safe_support_path("my-skill", "references/doc.md")
        assert result == (skill_dir / "references" / "doc.md").resolve()

    def test_empty_path_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(ValueError, match="must include a filename"):
            storage.ensure_safe_support_path("my-skill", "")

    def test_trailing_slash_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(ValueError, match="must include a filename"):
            storage.ensure_safe_support_path("my-skill", "references/")

    def test_absolute_path_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(ValueError, match="must be relative"):
            storage.ensure_safe_support_path("my-skill", "/etc/passwd")

    def test_parent_traversal_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(ValueError, match="must not contain parent-directory"):
            storage.ensure_safe_support_path("my-skill", "references/../../../escape")

    def test_disallowed_subdir_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        skill_dir = tmp_path / "custom" / "my-skill"
        skill_dir.mkdir(parents=True)
        with pytest.raises(ValueError, match="must live under one of"):
            storage.ensure_safe_support_path("my-skill", "evil/file.txt")

    def test_allowed_subdirs(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        for subdir in ("references", "templates", "scripts", "assets"):
            skill_dir = tmp_path / "custom" / "my-skill" / subdir
            skill_dir.mkdir(parents=True, exist_ok=True)
            result = storage.ensure_safe_support_path("my-skill", f"{subdir}/file.txt")
            assert result.name == "file.txt"

    def test_invalid_skill_name_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(ValueError, match="hyphen-case"):
            storage.ensure_safe_support_path("Bad_Name", "references/file.txt")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_get_container_root(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path, container_path="/custom/skills")
        assert storage.get_container_root() == "/custom/skills"

    def test_get_custom_skill_dir(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        result = storage.get_custom_skill_dir("my-skill")
        assert result == tmp_path / "custom" / "my-skill"

    def test_get_custom_skill_file(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        result = storage.get_custom_skill_file("my-skill")
        assert result == tmp_path / "custom" / "my-skill" / SKILL_MD_FILE

    def test_get_skill_history_file(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        result = storage.get_skill_history_file("my-skill")
        assert result == tmp_path / "custom" / ".history" / "my-skill.jsonl"

    def test_path_helpers_validate_name(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(ValueError, match="hyphen-case"):
            storage.get_custom_skill_dir("Bad Name")
        with pytest.raises(ValueError, match="hyphen-case"):
            storage.get_custom_skill_file("Bad Name")
        with pytest.raises(ValueError, match="hyphen-case"):
            storage.get_skill_history_file("Bad Name")


# ---------------------------------------------------------------------------
# install_skill_from_archive (sync wrapper)
# ---------------------------------------------------------------------------


class TestInstallSkillFromArchive:
    def test_sync_wrapper(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with patch("ideer.skills.installer._run_async_install", return_value={"installed": True}) as mock_run:
            result = storage.install_skill_from_archive("/tmp/test.skill")
            mock_run.assert_called_once()
            assert result == {"installed": True}


# ---------------------------------------------------------------------------
# ensure_custom_skill_is_editable
# ---------------------------------------------------------------------------


class TestEnsureCustomSkillIsEditable:
    def test_custom_skill_exists(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["my-skill"] = "content"
        # Should not raise
        storage.ensure_custom_skill_is_editable("my-skill")

    def test_public_skill_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._public_skills.add("builtin-skill")
        with pytest.raises(ValueError, match="built-in skill"):
            storage.ensure_custom_skill_is_editable("builtin-skill")

    def test_not_found_raises(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        with pytest.raises(FileNotFoundError, match="not found"):
            storage.ensure_custom_skill_is_editable("nonexistent")


# ---------------------------------------------------------------------------
# load_skills
# ---------------------------------------------------------------------------


class TestLoadSkills:
    def test_load_skills_basic(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["test-skill"] = "name: test-skill\ndescription: test"

        # Create actual files for parse_skill_file
        skill_dir = tmp_path / "custom" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / SKILL_MD_FILE).write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n# Test\n",
            encoding="utf-8",
        )

        with (
            patch("ideer.skills.parser.parse_skill_file") as mock_parse,
            patch("ideer.config.extensions_config.ExtensionsConfig.from_file") as mock_ext,
            patch("ideer.config.network_mode.is_offline", return_value=False),
        ):
            skill = Skill(
                name="test-skill",
                description="A test skill",
                license=None,
                skill_dir=skill_dir,
                skill_file=skill_dir / SKILL_MD_FILE,
                relative_path=Path("test-skill"),
                category=SkillCategory.CUSTOM,
            )
            mock_parse.return_value = skill
            mock_ext.return_value = MagicMock(is_skill_enabled=MagicMock(return_value=True))

            skills = storage.load_skills()

        assert len(skills) == 1
        assert skills[0].name == "test-skill"
        assert skills[0].enabled is True

    def test_load_skills_enabled_only_filter(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["skill-a"] = "content"
        storage._skills["skill-b"] = "content"

        skill_dir_a = tmp_path / "custom" / "skill-a"
        skill_dir_a.mkdir(parents=True)
        skill_dir_b = tmp_path / "custom" / "skill-b"
        skill_dir_b.mkdir(parents=True)

        with (
            patch("ideer.skills.parser.parse_skill_file") as mock_parse,
            patch("ideer.config.extensions_config.ExtensionsConfig.from_file") as mock_ext,
            patch("ideer.config.network_mode.is_offline", return_value=False),
        ):
            skill_a = Skill(
                name="skill-a",
                description="a",
                license=None,
                skill_dir=skill_dir_a,
                skill_file=skill_dir_a / SKILL_MD_FILE,
                relative_path=Path("skill-a"),
                category=SkillCategory.CUSTOM,
            )
            skill_b = Skill(
                name="skill-b",
                description="b",
                license=None,
                skill_dir=skill_dir_b,
                skill_file=skill_dir_b / SKILL_MD_FILE,
                relative_path=Path("skill-b"),
                category=SkillCategory.CUSTOM,
            )

            def parse_side_effect(md_path, **kwargs):
                if "skill-a" in str(md_path):
                    return skill_a
                return skill_b

            mock_parse.side_effect = parse_side_effect
            mock_ext.return_value = MagicMock(is_skill_enabled=MagicMock(side_effect=lambda name, cat: name == "skill-a"))

            skills = storage.load_skills(enabled_only=True)

        assert len(skills) == 1
        assert skills[0].name == "skill-a"

    def test_load_skills_offline_filters_internet_skills(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["online-skill"] = "content"
        storage._skills["offline-skill"] = "content"

        skill_dir_a = tmp_path / "custom" / "online-skill"
        skill_dir_a.mkdir(parents=True)
        skill_dir_b = tmp_path / "custom" / "offline-skill"
        skill_dir_b.mkdir(parents=True)

        with (
            patch("ideer.skills.parser.parse_skill_file") as mock_parse,
            patch("ideer.config.extensions_config.ExtensionsConfig.from_file") as mock_ext,
            patch("ideer.config.network_mode.is_offline", return_value=True),
        ):
            skill_online = Skill(
                name="online-skill",
                description="needs internet",
                license=None,
                skill_dir=skill_dir_a,
                skill_file=skill_dir_a / SKILL_MD_FILE,
                relative_path=Path("online-skill"),
                category=SkillCategory.CUSTOM,
                requires_internet=True,
            )
            skill_offline = Skill(
                name="offline-skill",
                description="works offline",
                license=None,
                skill_dir=skill_dir_b,
                skill_file=skill_dir_b / SKILL_MD_FILE,
                relative_path=Path("offline-skill"),
                category=SkillCategory.CUSTOM,
                requires_internet=False,
            )

            def parse_side_effect(md_path, **kwargs):
                if "online-skill" in str(md_path):
                    return skill_online
                return skill_offline

            mock_parse.side_effect = parse_side_effect
            mock_ext.return_value = MagicMock(is_skill_enabled=MagicMock(return_value=True))

            skills = storage.load_skills()

        assert len(skills) == 1
        assert skills[0].name == "offline-skill"

    def test_load_skills_extensions_config_failure_continues(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["test-skill"] = "content"

        skill_dir = tmp_path / "custom" / "test-skill"
        skill_dir.mkdir(parents=True)

        with (
            patch("ideer.skills.parser.parse_skill_file") as mock_parse,
            patch("ideer.config.extensions_config.ExtensionsConfig.from_file", side_effect=RuntimeError("config error")),
            patch("ideer.config.network_mode.is_offline", return_value=False),
        ):
            skill = Skill(
                name="test-skill",
                description="test",
                license=None,
                skill_dir=skill_dir,
                skill_file=skill_dir / SKILL_MD_FILE,
                relative_path=Path("test-skill"),
                category=SkillCategory.CUSTOM,
            )
            mock_parse.return_value = skill

            skills = storage.load_skills()

        assert len(skills) == 1

    def test_load_skills_sorted_by_name(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["z-skill"] = "content"
        storage._skills["a-skill"] = "content"

        for name in ("z-skill", "a-skill"):
            skill_dir = tmp_path / "custom" / name
            skill_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("ideer.skills.parser.parse_skill_file") as mock_parse,
            patch("ideer.config.extensions_config.ExtensionsConfig.from_file") as mock_ext,
            patch("ideer.config.network_mode.is_offline", return_value=False),
        ):

            def make_skill(name):
                d = tmp_path / "custom" / name
                return Skill(
                    name=name,
                    description="",
                    license=None,
                    skill_dir=d,
                    skill_file=d / SKILL_MD_FILE,
                    relative_path=Path(name),
                    category=SkillCategory.CUSTOM,
                )

            def parse_side_effect(md_path, **kwargs):
                for n in ("z-skill", "a-skill"):
                    if n in str(md_path):
                        return make_skill(n)
                return None

            mock_parse.side_effect = parse_side_effect
            mock_ext.return_value = MagicMock(is_skill_enabled=MagicMock(return_value=True))

            skills = storage.load_skills()

        assert [s.name for s in skills] == ["a-skill", "z-skill"]

    def test_load_skills_parse_returns_none_skips(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["bad-skill"] = "content"

        skill_dir = tmp_path / "custom" / "bad-skill"
        skill_dir.mkdir(parents=True)

        with (
            patch("ideer.skills.parser.parse_skill_file", return_value=None),
            patch("ideer.config.extensions_config.ExtensionsConfig.from_file") as mock_ext,
            patch("ideer.config.network_mode.is_offline", return_value=False),
        ):
            mock_ext.return_value = MagicMock(is_skill_enabled=MagicMock(return_value=True))
            skills = storage.load_skills()

        assert skills == []


# ---------------------------------------------------------------------------
# Abstract operations (delegate to concrete subclass)
# ---------------------------------------------------------------------------


class TestAbstractOperations:
    def test_read_custom_skill(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["my-skill"] = "content here"
        assert storage.read_custom_skill("my-skill") == "content here"

    def test_read_custom_skill_not_found(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        assert storage.read_custom_skill("nonexistent") == ""

    def test_delete_custom_skill(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["my-skill"] = "content"
        storage.delete_custom_skill("my-skill")
        assert "my-skill" not in storage._skills

    def test_delete_custom_skill_with_history(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["my-skill"] = "content"
        storage.delete_custom_skill("my-skill", history_meta={"action": "deleted"})
        assert "my-skill" not in storage._skills

    def test_custom_skill_exists(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._skills["exists"] = "content"
        assert storage.custom_skill_exists("exists") is True
        assert storage.custom_skill_exists("nope") is False

    def test_public_skill_exists(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage._public_skills.add("builtin")
        assert storage.public_skill_exists("builtin") is True
        assert storage.public_skill_exists("nope") is False

    def test_append_and_read_history(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage.append_history("my-skill", {"action": "created"})
        storage.append_history("my-skill", {"action": "updated"})
        history = storage.read_history("my-skill")
        assert len(history) == 2
        assert history[0]["action"] == "created"
        assert history[1]["action"] == "updated"

    def test_read_history_empty(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        assert storage.read_history("nonexistent") == []

    def test_write_custom_skill(self, tmp_path):
        storage = _FakeSkillStorage(tmp_path)
        storage.write_custom_skill("my-skill", "SKILL.md", "content")
        assert storage._written_files == [("my-skill", "SKILL.md", "content")]


# ---------------------------------------------------------------------------
# validate_skill_markdown_content
# ---------------------------------------------------------------------------


class TestValidateSkillMarkdownContent:
    def test_valid_content(self, tmp_path):
        with patch("ideer.skills.validation._validate_skill_frontmatter") as mock_validate:
            mock_validate.return_value = (True, "", "test-skill")
            # Should not raise
            SkillStorage.validate_skill_markdown_content("test-skill", "# Test")

    def test_invalid_frontmatter_raises(self, tmp_path):
        with patch("ideer.skills.validation._validate_skill_frontmatter") as mock_validate:
            mock_validate.return_value = (False, "Invalid frontmatter", None)
            with pytest.raises(ValueError, match="Invalid frontmatter"):
                SkillStorage.validate_skill_markdown_content("test-skill", "# Bad")

    def test_name_mismatch_raises(self, tmp_path):
        with patch("ideer.skills.validation._validate_skill_frontmatter") as mock_validate:
            mock_validate.return_value = (True, "", "different-name")
            with pytest.raises(ValueError, match="must match requested skill name"):
                SkillStorage.validate_skill_markdown_content("test-skill", "# Test")
