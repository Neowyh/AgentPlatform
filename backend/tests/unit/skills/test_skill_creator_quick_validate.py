import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
QUICK_VALIDATE_PATH = REPO_ROOT / "resources" / "skills" / "skill-creator" / "scripts" / "quick_validate.py"
SKILLS_ROOT = REPO_ROOT / "resources" / "skills"


def _load_quick_validate():
    spec = importlib.util.spec_from_file_location("skill_creator_quick_validate", QUICK_VALIDATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_bundled_skills_pass_quick_validation():
    validate_skill = _load_quick_validate().validate_skill

    for skill_name in ("eli5", "summarize", "wps-gongwen", "wps-proofread"):
        valid, message = validate_skill(SKILLS_ROOT / skill_name)
        assert valid, f"{skill_name}: {message}"


def test_quick_validation_accepts_current_frontmatter_extensions(tmp_path: Path):
    skill_dir = tmp_path / "modern-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: modern-skill\ndescription: A modern skill\ndescription_zh: 现代技能\ndescription_en: A modern skill\nrequires-internet: false\nversion: 1.0.0\nvisibility: public\nmetadata:\n  category: productivity\n---\n\nBody\n",
        encoding="utf-8",
    )

    valid, message = _load_quick_validate().validate_skill(skill_dir)

    assert valid, message


def test_quick_validation_rejects_unknown_top_level_frontmatter_property(tmp_path: Path):
    skill_dir = tmp_path / "invalid-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: invalid-skill\ndescription: Invalid\nunknown-field: true\n---\n\nBody\n",
        encoding="utf-8",
    )

    valid, message = _load_quick_validate().validate_skill(skill_dir)

    assert not valid
    assert "Unexpected key" in message
