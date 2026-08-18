"""Tests for recursive skills loading."""

from pathlib import Path
from types import SimpleNamespace

from ideer.config.skills_config import SkillsConfig
from ideer.skills.storage import get_or_new_skill_storage


def _write_skill(skill_dir: Path, name: str, description: str) -> None:
    """Write a minimal SKILL.md for tests."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def test_get_skills_root_path_points_to_current_project_skills(tmp_path: Path, monkeypatch):
    """get_skills_root_path() should point to the caller project skills directory."""
    monkeypatch.delenv("IDEER_SKILLS_PATH", raising=False)
    monkeypatch.delenv("IDEER_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resources" / "skills").mkdir(parents=True)

    app_config = SimpleNamespace(skills=SkillsConfig())
    path = get_or_new_skill_storage(app_config=app_config).get_skills_root_path()
    assert path == tmp_path / "resources" / "skills"


def test_get_skills_root_path_honors_env_override(tmp_path: Path, monkeypatch):
    """IDEER_SKILLS_PATH should override the caller project skills directory."""
    skills_root = tmp_path / "team-skills"
    monkeypatch.setenv("IDEER_SKILLS_PATH", str(skills_root))

    app_config = SimpleNamespace(skills=SkillsConfig())
    path = get_or_new_skill_storage(app_config=app_config).get_skills_root_path()
    assert path == skills_root


def test_load_skills_discovers_nested_skills_and_sets_container_paths(tmp_path: Path):
    """Nested skills should be discovered recursively with correct container paths."""
    skills_root = tmp_path / "skills"

    _write_skill(skills_root / "root-skill", "root-skill", "Root skill")
    _write_skill(skills_root / "parent" / "child-skill", "child-skill", "Child skill")
    _write_skill(skills_root / "team" / "helper", "team-helper", "Team helper")

    skills = get_or_new_skill_storage(skills_path=skills_root).load_skills(enabled_only=False)
    by_name = {skill.name: skill for skill in skills}

    assert {"root-skill", "child-skill", "team-helper"} <= set(by_name)

    root_skill = by_name["root-skill"]
    child_skill = by_name["child-skill"]
    team_skill = by_name["team-helper"]

    assert root_skill.skill_path == "root-skill"
    assert root_skill.get_container_file_path() == "/mnt/skills/root-skill/SKILL.md"

    assert child_skill.skill_path == "parent/child-skill"
    assert child_skill.get_container_file_path() == "/mnt/skills/parent/child-skill/SKILL.md"

    assert team_skill.skill_path == "team/helper"
    assert team_skill.get_container_file_path() == "/mnt/skills/team/helper/SKILL.md"


def test_load_skills_skips_hidden_directories(tmp_path: Path):
    """Hidden directories should be excluded from recursive discovery."""
    skills_root = tmp_path / "skills"

    _write_skill(skills_root / "visible" / "ok-skill", "ok-skill", "Visible skill")
    _write_skill(
        skills_root / "visible" / ".hidden" / "secret-skill",
        "secret-skill",
        "Hidden skill",
    )

    skills = get_or_new_skill_storage(skills_path=skills_root).load_skills(enabled_only=False)
    names = {skill.name for skill in skills}

    assert "ok-skill" in names
    assert "secret-skill" not in names


def test_load_skills_deduplicates_by_name_within_flat_root(tmp_path: Path):
    skills_root = tmp_path / "skills"
    _write_skill(skills_root / "shared-skill", "shared-skill", "Flat version")
    _write_skill(skills_root / "nested" / "shared-skill", "shared-skill", "Nested version")

    skills = get_or_new_skill_storage(skills_path=skills_root).load_skills(enabled_only=False)
    shared = [skill for skill in skills if skill.name == "shared-skill"]

    assert len(shared) == 1
