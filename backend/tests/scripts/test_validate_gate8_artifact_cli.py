from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _minimal_artifact(tmp_path: Path) -> Path:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    names = (
        "candidate_preparation",
        "trial_retrieval",
        "eval_case_management",
        "profile_ab_comparison",
        "matching_candidate_evaluation",
        "formal_publish",
        "run_snapshot_freeze",
        "rbac_and_secrecy",
        "failure_recovery",
        "browser_review",
    )
    observations = {
        "candidate_preparation": {"revision_id": "rev", "manifest_hash": "hash", "document_count": 1},
        "trial_retrieval": {"profile_parameters": {}, "revision_trace": "rev", "zero_hit": True},
        "eval_case_management": {"case_versions": [1], "expected_document_ids": ["doc"], "deduplicated": True},
        "profile_ab_comparison": {"profile_a": "frozen", "profile_b": "configured", "metrics": {}},
        "matching_candidate_evaluation": {"candidate_revision_id": "rev", "run_id": "run", "qualification": "passed"},
        "formal_publish": {"published_revision_id": "rev", "active_revision_id": "rev", "gate_decision": "passed"},
        "run_snapshot_freeze": {"old_run_snapshot": "old", "new_run_snapshot": "new", "latest_pointer": "rev"},
        "rbac_and_secrecy": {"users": ["owner", "viewer"], "knowledge_bases": ["kb"], "revoked_access": True, "redaction_check": True},
        "failure_recovery": {"zero_hit": True, "provider_down": "error", "timeout_partial": "partial", "retry_restart_history": True},
        "browser_review": {"evidence": True, "comparison": True, "gate_feedback": True, "ui_states": ["loading"], "keyboard_focus": True},
    }
    scenarios = {}
    for name in names:
        evidence = evidence_dir / f"{name}.json"
        evidence.write_text(json.dumps({"candidate_commit": "abc123", "scenario": name, "real_execution": True, "observed_steps": ["observed"]}), encoding="utf-8")
        scenarios[name] = {
            "result": "passed",
            "status": "executed",
            "exit_status": 0,
            "command": "python3 scripts/acceptance/validate_gate8_artifact.py artifact.json",
            "evidence": str(evidence),
            "started_at": "2026-09-22T00:00:00Z",
            "finished_at": "2026-09-22T00:00:01Z",
            "duration_seconds": 1,
            "assertions": ["observed"],
            "observations": observations[name],
        }
    gate7 = evidence_dir / "gate7.json"
    gate7.write_text('{"candidate_commit":"abc123"}', encoding="utf-8")
    artifact = {
        "candidate": {"commit": "abc123", "branch": "candidate", "recorded_at": "2026-09-22T00:00:00Z"},
        "prerequisites": {"gate7_artifact": str(gate7)},
        "environment": {"provider": "ragflow", "real": True, "assets": ["isolated-kb"]},
        "scenarios": scenarios,
        "verdict": "passed",
    }
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def test_validate_gate8_artifact_cli_passes_valid_record(tmp_path: Path) -> None:
    artifact = _minimal_artifact(tmp_path)
    result = subprocess.run(
        [sys.executable, "scripts/acceptance/validate_gate8_artifact.py", str(artifact), "--current-commit", "abc123"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout


def test_validate_gate8_artifact_cli_rejects_stale_candidate(tmp_path: Path) -> None:
    artifact = _minimal_artifact(tmp_path)
    result = subprocess.run(
        [sys.executable, "scripts/acceptance/validate_gate8_artifact.py", str(artifact), "--current-commit", "different"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "FAIL" in result.stderr
