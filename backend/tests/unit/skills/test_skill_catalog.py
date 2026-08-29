from pathlib import Path

from ideer.skills.catalog import SkillCatalog, get_skill_catalog


class _Source:
    def __init__(self, root: Path):
        self.root = root
        self.calls = 0

    def get_skills_root_path(self) -> Path:
        return self.root

    def load_skills(self, *, enabled_only: bool = False):
        self.calls += 1
        return [f"enabled={enabled_only}"]


def test_catalog_caches_by_enabled_policy_until_skill_files_change(tmp_path: Path):
    source = _Source(tmp_path)
    catalog = SkillCatalog(source)

    assert catalog.list_skills(enabled_only=True) == ["enabled=True"]
    assert catalog.list_skills(enabled_only=True) == ["enabled=True"]
    assert source.calls == 1

    skill = tmp_path / "example" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("content", encoding="utf-8")

    assert catalog.list_skills(enabled_only=True) == ["enabled=True"]
    assert source.calls == 2


def test_catalog_discards_old_root_signature_entries(tmp_path: Path):
    source = _Source(tmp_path)
    catalog = SkillCatalog(source)

    catalog.list_skills()
    skill = tmp_path / "example" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("first", encoding="utf-8")
    catalog.list_skills()

    assert len(catalog._cache) == 1


def test_catalog_invalidate_forces_reload(tmp_path: Path):
    source = _Source(tmp_path)
    catalog = SkillCatalog(source)

    catalog.list_skills()
    catalog.invalidate()
    catalog.list_skills()

    assert source.calls == 2


def test_get_skill_catalog_reuses_catalog_and_keeps_policy_caches(tmp_path: Path):
    source = _Source(tmp_path)
    catalog = get_skill_catalog(source)

    catalog.list_skills(enabled_only=True)
    catalog.list_skills(enabled_only=False)

    assert get_skill_catalog(source) is catalog
    assert source.calls == 2
