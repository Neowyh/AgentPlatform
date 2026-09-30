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
    # Scanner Status disclosure gate (ticket 04): the packaged copy must share
    # the canonical gate's constants verbatim.
    assert packaged.CODE_EVIDENCE_SIDE == contract.CODE_EVIDENCE_SIDE
    assert packaged.SCAN_SUMMARY_OUTPUT == contract.SCAN_SUMMARY_OUTPUT
    assert packaged.SCANNERS_UNAVAILABLE == contract.SCANNERS_UNAVAILABLE
    assert packaged.SCANNER_OVERALL_GRADES == contract.SCANNER_OVERALL_GRADES
    assert packaged.SCANNER_UNAVAILABLE_DISCLOSURE == contract.SCANNER_UNAVAILABLE_DISCLOSURE
    assert packaged.EVIDENCE_SIDE_DISCLOSURE == contract.EVIDENCE_SIDE_DISCLOSURE


def test_packaged_cli_and_repo_contract_agree_on_the_scanner_gate(tmp_path: Path) -> None:
    """Scanner Status 披露门三态在打包副本与 canonical 上行为一致。"""

    fixtures = _contract_fixtures()
    repo_contract = _load(CONTRACT, "fz_repo_contract")

    def outputs_dir(name: str) -> Path:
        path = tmp_path / name
        path.mkdir(exist_ok=True)
        return path

    def packaged_verdict(outputs: Path, *flags: str) -> tuple[int, str]:
        completed = subprocess.run(
            [sys.executable, str(PACKAGED), "--outputs-dir", str(outputs), "--json", *flags],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return completed.returncode, completed.stdout

    # State 1 — code side present, scan record missing: structured violation
    # on both forms ("缺失" is never a clean scan).
    outputs = fixtures.write_outputs(outputs_dir("missing"))
    (outputs / "artifacts" / "evidence" / "scan_summary.json").unlink()
    expected = repo_contract.evaluate_result_contract(outputs)
    assert not expected.ok and "scanner_status_missing" in expected.codes()
    code, stdout = packaged_verdict(outputs)
    assert code == 1
    assert "scanner_status_missing" in stdout

    # State 2 — explicit scanners_unavailable with the report disclosure: both pass.
    outputs = fixtures.write_outputs(outputs_dir("disclosed"))
    fixtures.write_scan_summary(
        outputs,
        {
            "package_id": "pkg-fixture",
            "overall": "scanners_unavailable",
            "scanners": [{"name": "cppcheck", "available": False, "version": None, "exit_code": None, "timed_out": False, "skipped_reason": "binary not found on PATH"}],
        },
    )
    report = fixtures.valid_report().replace(
        "暂无缺失资料风险；BE-02 仍待验证。",
        "静态扫描器不可用，本次无机器扫描告警；BE-02 仍待验证。",
    )
    (outputs / "zeroing_report.md").write_text(report, encoding="utf-8")
    expected = repo_contract.evaluate_result_contract(outputs)
    assert expected.ok, expected.errors
    code, stdout = packaged_verdict(outputs)
    assert code == 0, stdout
    assert '"ok": true' in stdout

    # State 3 — scanners_unavailable without the disclosure: both flag it
    # (未扫描不得静默当作干净扫描).
    outputs = fixtures.write_outputs(outputs_dir("undisclosed"))
    fixtures.write_scan_summary(
        outputs,
        {
            "package_id": "pkg-fixture",
            "overall": "scanners_unavailable",
            "scanners": [{"name": "cppcheck", "available": False, "version": None, "exit_code": None, "timed_out": False, "skipped_reason": "binary not found on PATH"}],
        },
    )
    expected = repo_contract.evaluate_result_contract(outputs)
    assert not expected.ok and "scanner_unavailable_undisclosed" in expected.codes()
    code, stdout = packaged_verdict(outputs)
    assert code == 1
    assert "scanner_unavailable_undisclosed" in stdout

    # Document-only run (declared missing code side): both skip the gate.
    outputs = fixtures.write_outputs(outputs_dir("doc_only"))
    (outputs / "artifacts" / "evidence" / "scan_summary.json").unlink()
    report = (
        fixtures.valid_report()
        .replace(
            "| 问题描述 | 已覆盖 | 01_problem.md | 无 |",
            "| 问题描述 | 已覆盖 | 01_problem.md | 无 |\n| 代码证据包 | 未提供 | — | 代码证据包未提供 |",
        )
        .replace(
            "暂无缺失资料风险；BE-02 仍待验证。",
            "代码证据包未提供，本次无静态扫描输入；BE-02 仍待验证。",
        )
    )
    (outputs / "zeroing_report.md").write_text(report, encoding="utf-8")
    expected = repo_contract.evaluate_result_contract(outputs, missing_evidence_sides=("code_evidence_package",))
    assert expected.ok, expected.errors
    code, stdout = packaged_verdict(outputs, "--missing-evidence-side", "code_evidence_package")
    assert code == 0, stdout
    assert '"ok": true' in stdout

    # State 4 — a disguised record ("document_only" on a code-side run) is
    # invalid on both forms: a missing scan never masquerades as a clean one.
    outputs = fixtures.write_outputs(outputs_dir("disguised"))
    fixtures.write_scan_summary(outputs, {"package_id": "pkg-fixture", "overall": "document_only", "scanners": []})
    expected = repo_contract.evaluate_result_contract(outputs)
    assert not expected.ok and "scanner_status_invalid" in expected.codes()
    code, stdout = packaged_verdict(outputs)
    assert code == 1
    assert "scanner_status_invalid" in stdout


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


def test_packaged_cli_reports_non_utf8_artifact_as_a_structured_finding(tmp_path: Path) -> None:
    """非法 UTF-8 的 fault_tree.json → 结构化 verdict（artifact_not_utf8），不崩溃。"""

    fixtures = _contract_fixtures()
    outputs = fixtures.write_outputs(tmp_path, fault_tree=fixtures.valid_fault_tree(), report=fixtures.valid_report())
    (outputs / "fault_tree.json").write_bytes(b"\xff\xfe{\x00not utf-8")

    completed = subprocess.run(
        [sys.executable, str(PACKAGED), "--outputs-dir", str(outputs), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 1
    assert "artifact_not_utf8" in completed.stdout


def test_skill_text_points_at_the_mounted_validator_path() -> None:
    skill = (REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "SKILL.md").read_text(encoding="utf-8")
    soul = (REPO_ROOT / "resources" / "agents" / "fault-zeroing" / "SOUL.md").read_text(encoding="utf-8")
    for text in (skill, soul):
        assert "/mnt/skills/fault-zeroing/scripts/validate_fault_zeroing_outputs.py" in text
