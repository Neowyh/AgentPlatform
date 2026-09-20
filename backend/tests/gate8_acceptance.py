"""Validation helpers for Gate 8 real acceptance artifacts.

The live and browser lanes produce the artifact; these checks make the final
verdict reproducible without treating skipped or mocked evidence as success.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

_REQUIRED_SCENARIOS = (
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

_SCENARIO_OBSERVATIONS = {
    "candidate_preparation": ("revision_id", "manifest_hash", "document_count"),
    "trial_retrieval": ("profile_parameters", "revision_trace", "zero_hit"),
    "eval_case_management": ("case_versions", "expected_document_ids", "deduplicated"),
    "profile_ab_comparison": ("profile_a", "profile_b", "metrics"),
    "matching_candidate_evaluation": ("candidate_revision_id", "run_id", "qualification"),
    "formal_publish": ("published_revision_id", "active_revision_id", "gate_decision"),
    "run_snapshot_freeze": ("old_run_snapshot", "new_run_snapshot", "latest_pointer"),
    "rbac_and_secrecy": ("users", "knowledge_bases", "revoked_access", "redaction_check"),
    "failure_recovery": ("zero_hit", "provider_down", "timeout_partial", "retry_restart_history"),
    "browser_review": ("evidence", "comparison", "gate_feedback", "ui_states", "keyboard_focus"),
}


_PLACEHOLDER = re.compile(r"<[^>]+>|\bTODO\b|\bTBD\b", re.IGNORECASE)
_URL = re.compile(r"https?://|\\\\[A-Za-z0-9_.-]+\\")


def validate_gate8_artifact(
    artifact: Mapping[str, object],
    *,
    current_commit: str | None = None,
    forbidden_values: set[str] | None = None,
) -> None:
    """Require attributable, real evidence for every Gate 8 scenario."""
    candidate = _required_mapping(artifact, "candidate")
    for key in ("commit", "branch", "recorded_at"):
        _required_value(candidate, key, "candidate")
    if current_commit is not None:
        _equal(candidate.get("commit"), current_commit, "candidate commit")
    _parse_timestamp(candidate["recorded_at"], "candidate recorded_at")

    prerequisites = _required_mapping(artifact, "prerequisites")
    gate7_path = Path(str(_required_value(prerequisites, "gate7_artifact", "prerequisites")))
    _require_file(gate7_path, "Gate7 evidence file")
    try:
        gate7 = json.loads(gate7_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError("Gate7 evidence file is not valid JSON") from exc
    if isinstance(gate7, Mapping) and "candidate_commit" in gate7:
        _equal(gate7.get("candidate_commit"), candidate.get("commit"), "Gate7 candidate commit")
    environment = _required_mapping(artifact, "environment")
    _equal(environment.get("provider"), "ragflow", "provider")
    _equal(environment.get("real"), True, "real environment")
    _required_value(environment, "assets", "environment")

    scenarios = _required_mapping(artifact, "scenarios")
    for name in _REQUIRED_SCENARIOS:
        entry = _required_mapping(scenarios, name)
        _equal(entry.get("result"), "passed", name)
        _equal(entry.get("status"), "executed", f"{name} execution status")
        _equal(entry.get("exit_status"), 0, f"{name} exit status")
        command = str(_required_value(entry, "command", name))
        assert not _PLACEHOLDER.search(command), f"{name} command contains a placeholder"
        evidence_path = Path(str(_required_value(entry, "evidence", name)))
        _require_file(evidence_path, f"{name} evidence file")
        _validate_evidence_payload(evidence_path, name, candidate["commit"])
        _parse_timestamp(_required_value(entry, "started_at", name), f"{name} started_at")
        _parse_timestamp(_required_value(entry, "finished_at", name), f"{name} finished_at")
        duration = entry.get("duration_seconds")
        assert isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= 0, f"{name} duration_seconds is invalid"
        assertions = entry.get("assertions")
        assert isinstance(assertions, list) and assertions and all(isinstance(item, str) and item.strip() for item in assertions), f"{name} assertions are missing"
        observations = _required_mapping(entry, "observations")
        for observation in _SCENARIO_OBSERVATIONS[name]:
            _required_value(observations, observation, f"{name} observations")

    _equal(artifact.get("verdict"), "passed", "Gate 8 verdict")
    _assert_no_provider_secrets(artifact, forbidden_values=forbidden_values or set())


def _assert_no_provider_secrets(value: object, *, forbidden_values: set[str]) -> None:
    """Reject artifacts that accidentally contain provider implementation data."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            forbidden_key = any(token in key_text for token in ("secret", "api_key", "password", "dataset_id", "internal_id")) or (
                key_text not in {"provider", "provider_down"} and "provider" in key_text and any(token in key_text for token in ("id", "url", "address", "host", "key"))
            )
            assert not forbidden_key, f"provider identity or sensitive field: {key}"
            _assert_no_provider_secrets(item, forbidden_values=forbidden_values)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_provider_secrets(item, forbidden_values=forbidden_values)
    elif isinstance(value, str):
        assert not _URL.search(value), "provider detail or address in artifact"
        assert not any(secret and secret in value for secret in forbidden_values), "provider detail or secret value in artifact"


def _required_mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    item = value.get(key)
    assert isinstance(item, Mapping), f"missing {key}"
    return item


def _required_value(value: Mapping[str, object], key: str, label: str) -> object:
    item = value.get(key)
    assert item not in (None, "", []), f"missing {label} {key}"
    return item


def _equal(actual: object, expected: object, label: str) -> None:
    assert actual == expected, f"{label} does not match expected value"


def _require_file(path: Path, label: str) -> None:
    assert path.is_file(), f"{label} does not exist: {path}"


def _parse_timestamp(value: object, label: str) -> None:
    assert isinstance(value, str) and value.strip(), f"missing {label}"
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"{label} is not an ISO timestamp") from exc


def _validate_evidence_payload(path: Path, scenario: str, candidate_commit: object) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"{scenario} evidence file is not valid JSON") from exc
    assert isinstance(payload, Mapping), f"{scenario} evidence must be a JSON object"
    _equal(payload.get("candidate_commit"), candidate_commit, f"{scenario} evidence candidate commit")
    _equal(payload.get("scenario"), scenario, f"{scenario} evidence scenario")
    _equal(payload.get("real_execution"), True, f"{scenario} evidence real execution")
    steps = payload.get("observed_steps")
    assert isinstance(steps, list) and steps and all(isinstance(step, str) and step.strip() for step in steps), f"{scenario} evidence observed steps are missing"
