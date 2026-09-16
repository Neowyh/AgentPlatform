from __future__ import annotations

import pytest

from tests.gate8_acceptance import validate_gate8_artifact


def _artifact() -> dict[str, object]:
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
    return {
        "candidate": {"commit": "abc123", "branch": "candidate", "recorded_at": "2026-09-17T00:00:00Z"},
        "prerequisites": {"gate7_artifact": "gate7.json"},
        "environment": {"provider": "ragflow", "real": True, "assets": ["isolated-kb"]},
        "scenarios": {name: {"result": "passed", "exit_status": 0, "command": "command", "evidence": f"{name}.json"} for name in names},
        "verdict": "passed",
    }


def test_gate8_artifact_requires_real_evidence_for_every_scenario() -> None:
    validate_gate8_artifact(_artifact())


def test_gate8_artifact_rejects_missing_scenario() -> None:
    artifact = _artifact()
    del artifact["scenarios"]["formal_publish"]  # type: ignore[index]

    with pytest.raises(AssertionError, match="formal_publish"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_unexecuted_or_mocked_evidence() -> None:
    artifact = _artifact()
    artifact["environment"]["real"] = False  # type: ignore[index]

    with pytest.raises(AssertionError, match="real environment"):
        validate_gate8_artifact(artifact)


def test_gate8_artifact_rejects_provider_identity_or_secret() -> None:
    artifact = _artifact()
    artifact["environment"]["provider_dataset_id"] = "internal-id"  # type: ignore[index]

    with pytest.raises(AssertionError, match="provider identity"):
        validate_gate8_artifact(artifact)
