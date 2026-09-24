from __future__ import annotations

import json

import pytest

from tests.gate8_acceptance import validate_gate8_artifact


def _artifact(tmp_path) -> dict[str, object]:
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
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    for name in names:
        (evidence_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "candidate_commit": "abc123",
                    "scenario": name,
                    "real_execution": True,
                    "observed_steps": ["observed through the public boundary"],
                }
            ),
            encoding="utf-8",
        )
    gate7 = evidence_dir / "gate7.json"
    gate7.write_text('{"candidate_commit":"abc123"}', encoding="utf-8")
    return {
        "candidate": {"commit": "abc123", "branch": "candidate", "recorded_at": "2026-09-17T00:00:00Z"},
        "prerequisites": {"gate7_artifact": str(gate7)},
        "environment": {"provider": "ragflow", "real": True, "assets": ["isolated-kb"]},
        "scenarios": {
            name: {
                "result": "passed",
                "status": "executed",
                "exit_status": 0,
                "command": "pytest tests/test_gate8.py -q",
                "evidence": str(evidence_dir / f"{name}.json"),
                "started_at": "2026-09-17T00:00:00Z",
                "finished_at": "2026-09-17T00:00:01Z",
                "duration_seconds": 1.0,
                "assertions": ["observed real result"],
                "observations": {
                    "revision_id": "revision",
                    "manifest_hash": "manifest",
                    "document_count": 1,
                    "profile_parameters": {"top_k": 8},
                    "revision_trace": "revision",
                    "zero_hit": True,
                    "case_versions": [1],
                    "expected_document_ids": ["document"],
                    "deduplicated": True,
                    "profile_a": "frozen",
                    "profile_b": "configured",
                    "metrics": {"recall_at_k": 1.0},
                    "candidate_revision_id": "revision",
                    "run_id": "run",
                    "qualification": "passed",
                    "published_revision_id": "revision",
                    "active_revision_id": "revision",
                    "gate_decision": "passed",
                    "old_run_snapshot": {"knowledge_revision_id": "old", "run_status": "success"},
                    "new_run_snapshot": {"knowledge_revision_id": "new", "run_status": "success"},
                    "latest_pointer": {"before": "old", "after": "new"},
                    "users": ["owner", "viewer"],
                    "knowledge_bases": ["kb-a", "kb-b"],
                    "revoked_access": True,
                    "redaction_check": True,
                    "provider_down": "error",
                    "timeout_partial": "partial",
                    "retry_restart_history": True,
                    "evidence": True,
                    "comparison": True,
                    "gate_feedback": True,
                    "ui_states": ["loading", "empty", "error", "restricted"],
                    "keyboard_focus": True,
                },
            }
            for name in names
        },
        "verdict": "passed",
    }


def test_gate8_artifact_requires_real_evidence_for_every_scenario(tmp_path) -> None:
    validate_gate8_artifact(_artifact(tmp_path), current_commit="abc123")


def test_gate8_artifact_rejects_failed_snapshot_runs(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    observations = artifact["scenarios"]["run_snapshot_freeze"]["observations"]  # type: ignore[index]
    observations["old_run_snapshot"]["run_status"] = "error"

    with pytest.raises(AssertionError, match="old Run status"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_missing_scenario(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    del artifact["scenarios"]["formal_publish"]  # type: ignore[index]

    with pytest.raises(AssertionError, match="formal_publish"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_unexecuted_or_mocked_evidence(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    artifact["environment"]["real"] = False  # type: ignore[index]

    with pytest.raises(AssertionError, match="real environment"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_provider_identity_or_secret(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    artifact["environment"]["provider_dataset_id"] = "internal-id"  # type: ignore[index]

    with pytest.raises(AssertionError, match="provider identity"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_stale_candidate_and_missing_evidence(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    artifact["candidate"]["commit"] = "old-commit"  # type: ignore[index]

    with pytest.raises(AssertionError, match="candidate commit"):
        validate_gate8_artifact(artifact, current_commit="abc123")

    artifact = _artifact(tmp_path)
    artifact["scenarios"]["formal_publish"]["evidence"] = str(tmp_path / "missing.json")  # type: ignore[index]
    with pytest.raises(AssertionError, match="evidence file"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_sensitive_values_and_placeholders(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    artifact["scenarios"]["formal_publish"]["command"] = "<publish-command>"  # type: ignore[index]
    with pytest.raises(AssertionError, match="placeholder"):
        validate_gate8_artifact(artifact)

    artifact = _artifact(tmp_path)
    artifact["environment"]["notes"] = "provider at http://ragflow.internal/api"  # type: ignore[index]
    with pytest.raises(AssertionError, match="provider detail"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_requires_scenario_specific_observations(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    del artifact["scenarios"]["formal_publish"]["observations"]["active_revision_id"]  # type: ignore[index]

    with pytest.raises(AssertionError, match="active_revision_id"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_unbound_evidence_payload(tmp_path) -> None:
    artifact = _artifact(tmp_path)
    evidence = tmp_path / "evidence" / "formal_publish.json"
    evidence.write_text('{"scenario":"formal_publish","real_execution":true,"observed_steps":["step"]}', encoding="utf-8")

    with pytest.raises(AssertionError, match="evidence candidate commit"):
        validate_gate8_artifact(artifact)
