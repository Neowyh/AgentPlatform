"""Tests for the fixed Hybrid Evidence Intake (ticket 02)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
INTAKE_PATH = REPO_ROOT / "backend" / "app" / "agentplatform" / "fault_zeroing" / "intake.py"
CONTRACT_PATH = REPO_ROOT / "backend" / "app" / "agentplatform" / "fault_zeroing" / "contract.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def load_intake():
    return load_module("fz_intake", INTAKE_PATH)


# ---------------------------------------------------------------------------
# Intake decision matrix.
# ---------------------------------------------------------------------------


def test_both_sides_present_executes_immediately() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(
        upload_dir="/mnt/user-data/uploads",
        code_package_source="/mnt/user-data/code-evidence/pkg-1/source",
    )

    assert decision.status == intake.EXECUTE
    assert decision.missing == ()
    assert decision.reason_code == intake.INTAKE_COMPLETE
    # The mode is a derived system result, always hybrid (CONTEXT.md:
    # Avoid "Evidence Mode selection", "document-only Run").
    assert decision.evidence_mode == "hybrid"


def test_nonempty_problem_description_satisfies_document_side() -> None:
    """A description alone is documentary evidence (CONTEXT.md glossary)."""

    intake = load_intake()
    decision = intake.assess_evidence_intake(
        problem_description="主轴电机过热报警，请分析根因",
        code_package_source="/mnt/user-data/code-evidence/pkg-1/source",
    )

    assert decision.status == intake.EXECUTE
    assert decision.missing == ()
    assert decision.reason_code == intake.INTAKE_COMPLETE


def test_problem_description_alone_pauses_for_missing_code_side() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(
        problem_description="主轴电机过热报警，请分析根因",
    )

    assert decision.status == intake.PAUSE
    assert decision.missing == ("code_evidence_package",)
    assert decision.reason_code == intake.INTAKE_CONFIRMATION_REQUIRED
    assert decision.evidence_mode == "hybrid"


def test_code_package_alone_pauses_for_missing_document_side() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(
        code_package_source="/mnt/user-data/code-evidence/pkg-1/source",
    )

    assert decision.status == intake.PAUSE
    assert decision.missing == ("document_evidence",)


def test_whitespace_description_does_not_satisfy_document_side() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(problem_description="   \n\t")

    assert decision.status == intake.REJECT
    assert decision.missing == intake.SIDES


def test_one_side_missing_creates_confirmation_pause() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")

    assert decision.status == intake.PAUSE
    assert decision.missing == ("code_evidence_package",)
    assert decision.reason_code == intake.INTAKE_CONFIRMATION_REQUIRED
    # Single-side runs stay hybrid.
    assert decision.evidence_mode == "hybrid"


def test_both_sides_missing_rejects_before_model_execution() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake()

    assert decision.status == intake.REJECT
    assert decision.missing == intake.SIDES
    assert decision.reason_code == intake.INTAKE_MISSING_BOTH
    # Even the rejection record never claims a document-only or code-only mode.
    assert decision.evidence_mode == "hybrid"


def test_evidence_mode_is_derived_never_user_declared() -> None:
    """No caller-selectable mode survives: document/code modes are gone."""

    intake = load_intake()
    import inspect

    params = inspect.signature(intake.assess_evidence_intake).parameters
    assert "evidence_mode" not in params


# ---------------------------------------------------------------------------
# Snapshot-bound confirmation.
# ---------------------------------------------------------------------------


def test_confirmation_binds_to_input_snapshot() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")

    assert intake.confirmation_is_current(decision.input_snapshot_hash, decision.input_snapshot_hash)


def test_problem_description_is_bound_into_the_snapshot_hash() -> None:
    """Changing the description changes the hash: re-confirmation required."""

    intake = load_intake()
    decision = intake.assess_evidence_intake(
        problem_description="主轴电机过热报警",
        upload_dir="/mnt/user-data/uploads",
    )
    rewritten = intake.assess_evidence_intake(
        problem_description="主轴电机过热停机",
        upload_dir="/mnt/user-data/uploads",
    )

    assert rewritten.input_snapshot_hash != decision.input_snapshot_hash
    assert not intake.confirmation_is_current(decision.input_snapshot_hash, rewritten.input_snapshot_hash)


def test_snapshot_records_both_documentary_sources() -> None:
    """The document side snapshot reflects description and attachments."""

    intake = load_intake()
    described = intake.assess_evidence_intake(
        problem_description="主轴电机过热报警",
        upload_dir="/mnt/user-data/uploads",
    )
    described_only = intake.assess_evidence_intake(problem_description="主轴电机过热报警")
    attached_only = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")

    document_value = described.input_snapshot["document_evidence"]
    assert "主轴电机过热报警" in document_value
    assert "/mnt/user-data/uploads" in document_value
    # Each documentary source is part of the hash input.
    assert described_only.input_snapshot_hash != described.input_snapshot_hash
    assert attached_only.input_snapshot_hash != described.input_snapshot_hash
    # And an empty document side stays empty.
    assert intake.build_input_snapshot(None, None, None)["document_evidence"] == ""


def test_new_material_requires_reconfirmation() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")

    updated = intake.assess_evidence_intake(
        upload_dir="/mnt/user-data/uploads",
        code_package_source="/mnt/user-data/code-evidence/pkg-1/source",
    )
    assert not intake.confirmation_is_current(decision.input_snapshot_hash, updated.input_snapshot_hash)


def test_empty_confirmation_is_never_current() -> None:
    intake = load_intake()
    assert not intake.confirmation_is_current(None, "abc")


def test_intake_record_round_trip() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")

    record = json.loads(json.dumps(decision.to_dict()))
    restored = intake.EvidenceIntakeDecision.from_dict(record)
    assert restored == decision


def test_interrupt_payload_discloses_missing_items() -> None:
    intake = load_intake()
    decision = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")

    payload = intake.interrupt_payload(decision)

    assert payload["type"] == intake.INTERRUPT_TYPE
    assert payload["reason_code"] == intake.INTAKE_CONFIRMATION_REQUIRED
    assert payload["missing"] == ["code_evidence_package"]
    assert "代码证据包" in payload["message"]
    assert payload["input_snapshot_hash"] == decision.input_snapshot_hash


# ---------------------------------------------------------------------------
# Contract-side hybrid disclosure check.
# ---------------------------------------------------------------------------


def test_contract_requires_hybrid_disclosure(tmp_path: Path) -> None:
    """A single-side run must disclose the missing side in the report."""

    contract = load_module("fz_contract", CONTRACT_PATH)
    intake = load_intake()
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    # Reuse the valid fixture from the contract test module.
    contract_tests = load_module(
        "fz_contract_tests",
        REPO_ROOT / "backend" / "tests" / "unit" / "fault_zeroing" / "test_contract.py",
    )
    contract_tests.write_outputs(tmp_path)

    decision = intake.assess_evidence_intake(upload_dir="/mnt/user-data/uploads")
    verdict = contract.evaluate_result_contract(
        output_dir,
        missing_evidence_sides=decision.missing,
    )

    assert not verdict.ok
    assert "hybrid_disclosure_missing" in {f.code for f in verdict.findings}

    # With the disclosure phrase present in both sections, the check passes.
    phrase = intake.missing_evidence_disclosure(decision.missing)[0]
    report = (output_dir / "zeroing_report.md").read_text(encoding="utf-8")
    report = report.replace(
        "| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |",
        f"| 历史或复核记录 | 已覆盖 | 05_review_record.md | 无 |\n| 代码证据 | {phrase} | 无 | 无 |",
    )
    report = report.replace(
        "暂无缺失资料风险；BE-02 仍待验证。",
        f"{phrase}，基于文档证据单侧继续分析；BE-02 仍待验证。",
    )
    (output_dir / "zeroing_report.md").write_text(report, encoding="utf-8")

    verdict = contract.evaluate_result_contract(
        output_dir,
        missing_evidence_sides=decision.missing,
    )
    assert verdict.ok, verdict.errors
