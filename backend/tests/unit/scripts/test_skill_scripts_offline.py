"""Offline-safety regression tests for bundled skill scripts and manifests.

Background: intranet deployments run with no network access. Skill scripts
must never attempt runtime dependency installation or extension downloads,
and internet-only skills must be flagged with ``requires-internet: true`` so
the platform filters them out in offline mode (see
``ideer/skills/storage/skill_storage.py``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
RESOURCES_SKILLS = REPO_ROOT / "resources" / "skills"
DATA_ANALYSIS_SCRIPT = RESOURCES_SKILLS / "data-analysis" / "scripts" / "analyze.py"
PPT_SCRIPT = RESOURCES_SKILLS / "ppt-generation" / "scripts" / "generate.py"

SKILLS_REQUIRING_INTERNET_FLAG = (
    "find-skills",
    "deep-research",
    "newsletter-generation",
)


def _offline_env() -> dict[str, str]:
    """Environment without proxy escape hatches, mimicking an intranet host."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("HTTP_", "HTTPS_", "ALL_PROXY", "http_", "https_", "all_proxy"))}


@pytest.mark.parametrize(
    ("skill", "forbidden"),
    [
        (
            "data-analysis/scripts/analyze.py",
            ("-m pip", "subprocess", "INSTALL spatial", "fetchdf", "st_read"),
        ),
        ("ppt-generation/scripts/generate.py", ("-m pip", "subprocess")),
    ],
)
def test_skill_scripts_have_no_runtime_network_calls(skill: str, forbidden: tuple[str, ...]) -> None:
    source = (RESOURCES_SKILLS / skill).read_text(encoding="utf-8")
    for token in forbidden:
        assert token not in source, f"{skill} must not contain {token!r}: intranet hosts have no network"


@pytest.mark.parametrize("skill", SKILLS_REQUIRING_INTERNET_FLAG)
def test_internet_only_skills_are_flagged(skill: str) -> None:
    frontmatter = (RESOURCES_SKILLS / skill / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
    assert "requires-internet: true" in frontmatter, f"{skill} must be hidden in offline mode"


def _make_xlsx(path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["product", "amount"])
    ws.append(["A", 100])
    ws.append(["B", 250.5])
    ws.append(["A", None])
    ws.append(["B", 49.5])
    wb.save(path)


def test_data_analysis_end_to_end_offline(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    pytest.importorskip("openpyxl")
    xlsx = tmp_path / "data.xlsx"
    _make_xlsx(xlsx)

    result = subprocess.run(
        [
            sys.executable,
            str(DATA_ANALYSIS_SCRIPT),
            "--files",
            str(xlsx),
            "--action",
            "query",
            "--sql",
            "SELECT product, SUM(amount) AS total FROM Sales GROUP BY product ORDER BY product",
        ],
        capture_output=True,
        text=True,
        env=_offline_env(),
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "A" in result.stdout and "100" in result.stdout
    assert "B" in result.stdout and "300" in result.stdout


def test_data_analysis_summary_and_export_offline(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    pytest.importorskip("openpyxl")
    xlsx = tmp_path / "data.xlsx"
    _make_xlsx(xlsx)
    output_csv = tmp_path / "out.csv"

    summary = subprocess.run(
        [sys.executable, str(DATA_ANALYSIS_SCRIPT), "--files", str(xlsx), "--action", "summary", "--table", "Sales"],
        capture_output=True,
        text=True,
        env=_offline_env(),
        cwd=tmp_path,
        timeout=120,
    )
    assert summary.returncode == 0, summary.stderr
    assert "Statistical Summary: Sales" in summary.stdout

    query = subprocess.run(
        [
            sys.executable,
            str(DATA_ANALYSIS_SCRIPT),
            "--files",
            str(xlsx),
            "--action",
            "query",
            "--sql",
            "SELECT * FROM Sales WHERE amount > 50 ORDER BY amount DESC",
            "--output-file",
            str(output_csv),
        ],
        capture_output=True,
        text=True,
        env=_offline_env(),
        cwd=tmp_path,
        timeout=120,
    )
    assert query.returncode == 0, query.stderr
    content = output_csv.read_text(encoding="utf-8")
    assert content.splitlines()[0] == "product,amount"
    assert "250.5" in content


def test_data_analysis_missing_dependency_fails_without_installing(tmp_path: Path) -> None:
    """Simulate a missing duckdb install: script exits with guidance, no pip."""
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    (blocked_dir / "duckdb.py").write_text("raise ImportError('no duckdb')\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(DATA_ANALYSIS_SCRIPT), "--files", "ignored.csv", "--action", "inspect"],
        capture_output=True,
        text=True,
        env={**_offline_env(), "PYTHONPATH": f"{blocked_dir}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"},
        cwd=tmp_path,
        timeout=60,
    )
    assert result.returncode != 0
    assert "pip install --no-index" in result.stdout + result.stderr
    assert "Installing" not in result.stdout


def test_ppt_generation_missing_dependency_fails_without_installing(tmp_path: Path) -> None:
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    (blocked_dir / "pptx.py").write_text("raise ImportError('no pptx')\n", encoding="utf-8")
    (blocked_dir / "PIL.py").write_text("raise ImportError('no PIL')\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(PPT_SCRIPT)],
        capture_output=True,
        text=True,
        env={**_offline_env(), "PYTHONPATH": f"{blocked_dir}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"},
        cwd=tmp_path,
        timeout=60,
    )
    assert result.returncode != 0
    assert "pip install --no-index" in result.stdout + result.stderr
