"""Validate every bundled SKILL.md under skills/public/.

Catches regressions like #2443 — a SKILL.md whose YAML front-matter fails to
parse (e.g. an unquoted description containing a colon, which YAML interprets
as a nested mapping). Each bundled skill is checked individually so the
failure message identifies the exact file.
"""

import re
from pathlib import Path

import pytest
import yaml

from ideer.skills.validation import _validate_skill_frontmatter

SKILLS_PUBLIC_DIR = Path(__file__).resolve().parents[4] / "skills" / "public"
BUNDLED_SKILL_DIRS = sorted(p.parent for p in SKILLS_PUBLIC_DIR.rglob("SKILL.md"))
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DANGEROUS_INSTRUCTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
        r"disregard\s+(?:previous|prior)\s+instructions",
        r"exfiltrate",
        r"leak\s+secrets?",
        r"steal\s+(?:secrets?|credentials?|tokens?)",
        r"rm\s+-rf\s+/",
        r"curl\b[^\n|]*\|\s*(?:sh|bash)",
    )
]


def _skill_md(skill_dir: Path) -> Path:
    return skill_dir / "SKILL.md"


def _frontmatter(skill_dir: Path) -> dict:
    text = _skill_md(skill_dir).read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    assert match, f"{skill_dir.relative_to(SKILLS_PUBLIC_DIR)}: missing YAML frontmatter"
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict), f"{skill_dir.relative_to(SKILLS_PUBLIC_DIR)}: frontmatter is not a mapping"
    return parsed


@pytest.mark.parametrize(
    "skill_dir",
    BUNDLED_SKILL_DIRS,
    ids=lambda p: str(p.relative_to(SKILLS_PUBLIC_DIR)),
)
def test_bundled_skill_frontmatter_is_valid(skill_dir: Path) -> None:
    valid, msg, name = _validate_skill_frontmatter(skill_dir)
    assert valid, f"{skill_dir.relative_to(SKILLS_PUBLIC_DIR)}: {msg}"
    assert name, f"{skill_dir.relative_to(SKILLS_PUBLIC_DIR)}: no name extracted"


@pytest.mark.parametrize(
    "skill_dir",
    BUNDLED_SKILL_DIRS,
    ids=lambda p: str(p.relative_to(SKILLS_PUBLIC_DIR)),
)
def test_bundled_skill_has_required_catalog_fields(skill_dir: Path) -> None:
    data = _frontmatter(skill_dir)
    assert isinstance(data.get("name"), str)
    assert data["name"].strip()
    assert isinstance(data.get("description"), str)
    assert data["description"].strip()


@pytest.mark.parametrize(
    "skill_dir",
    BUNDLED_SKILL_DIRS,
    ids=lambda p: str(p.relative_to(SKILLS_PUBLIC_DIR)),
)
def test_bundled_skill_is_offline_readable(skill_dir: Path) -> None:
    text = _skill_md(skill_dir).read_text(encoding="utf-8")
    body = FRONTMATTER_RE.sub("", text, count=1).strip()
    assert body, f"{skill_dir.relative_to(SKILLS_PUBLIC_DIR)}: missing readable body"


@pytest.mark.parametrize(
    "skill_dir",
    BUNDLED_SKILL_DIRS,
    ids=lambda p: str(p.relative_to(SKILLS_PUBLIC_DIR)),
)
def test_bundled_skill_omits_dangerous_instructions(skill_dir: Path) -> None:
    text = _skill_md(skill_dir).read_text(encoding="utf-8")
    for pattern in DANGEROUS_INSTRUCTION_PATTERNS:
        assert not pattern.search(text), f"{skill_dir.relative_to(SKILLS_PUBLIC_DIR)} contains dangerous instruction pattern {pattern.pattern!r}"


def test_skills_public_dir_has_skills() -> None:
    assert BUNDLED_SKILL_DIRS, f"no SKILL.md found under {SKILLS_PUBLIC_DIR}"
