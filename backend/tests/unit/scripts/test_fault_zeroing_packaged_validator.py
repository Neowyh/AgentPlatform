"""Sync guards for the packaged offline fault-zeroing validator (ticket 04).

The Skill points users at ``/mnt/skills/fault-zeroing/scripts/validate_
fault_zeroing_outputs.py``.  In the mount form the backend tree is not
importable, so the packaged script embeds the versioned Result Contract
verbatim instead of importing it.  These tests keep the embedded copy from
drifting away from the single contract implementation.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PACKAGED = REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "scripts" / "validate_fault_zeroing_outputs.py"
CONTRACT = REPO_ROOT / "backend" / "app" / "agentplatform" / "fault_zeroing" / "contract.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def _contract_fixtures():
    return _load(REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py", "fz_contract_fixtures_packaged")


def test_packaged_script_exists_and_is_stdlib_only() -> None:
    source = PACKAGED.read_text(encoding="utf-8")
    assert source.startswith("#!/usr/bin/env python3")
    for third_party in ("import yaml", "import jsonschema", "from fastapi", "from pydantic"):
        assert third_party not in source
    # Stale module references must stay out of the packaged copy.
    assert "ideer.fault_zeroing" not in source


def test_embedded_contract_matches_the_repo_contract() -> None:
    packaged = _load(PACKAGED, "fz_packaged_validator")
    contract = _load(CONTRACT, "fz_repo_contract")

    assert packaged.CONTRACT_VERSION == contract.CONTRACT_VERSION
    assert packaged.SUPPORTED_CONTRACT_VERSIONS == contract.SUPPORTED_CONTRACT_VERSIONS
    assert packaged.REQUIRED_OUTPUTS == contract.REQUIRED_OUTPUTS
    assert packaged.REQUIRED_COVERAGE == contract.REQUIRED_COVERAGE
    assert packaged.REQUIRED_REPORT_SECTIONS == contract.REQUIRED_REPORT_SECTIONS
    assert packaged.REQUIRED_STAGE_MARKERS == contract.REQUIRED_STAGE_MARKERS


def test_packaged_cli_agrees_with_the_repo_contract_on_a_fixture(tmp_path: Path) -> None:
    fixtures = _contract_fixtures()
    outputs = fixtures.write_outputs(tmp_path, fault_tree=fixtures.valid_fault_tree(), report=fixtures.valid_report())

    repo_contract = _load(CONTRACT, "fz_repo_contract")
    expected = repo_contract.evaluate_result_contract(outputs, contract_version=repo_contract.CONTRACT_VERSION)
    assert expected.ok

    completed = subprocess.run(
        [sys.executable, str(PACKAGED), "--outputs-dir", str(outputs), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"ok": true' in completed.stdout


def test_packaged_cli_reports_violations_with_nonzero_exit(tmp_path: Path) -> None:
    fixtures = _contract_fixtures()
    outputs = fixtures.write_outputs(tmp_path, fault_tree=fixtures.valid_fault_tree(), report=fixtures.valid_report())
    (outputs / "fault_tree.svg").unlink()

    completed = subprocess.run(
        [sys.executable, str(PACKAGED), "--outputs-dir", str(outputs)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 1
    assert "fault_tree.svg" in completed.stderr


def test_skill_text_points_at_the_mounted_validator_path() -> None:
    skill = (REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "SKILL.md").read_text(encoding="utf-8")
    soul = (REPO_ROOT / "resources" / "agents" / "fault-zeroing" / "SOUL.md").read_text(encoding="utf-8")
    for text in (skill, soul):
        assert "/mnt/skills/fault-zeroing/scripts/validate_fault_zeroing_outputs.py" in text
