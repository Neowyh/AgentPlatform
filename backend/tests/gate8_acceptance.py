"""Validation helpers for Gate 8 real acceptance artifacts.

The live and browser lanes produce the artifact; these checks make the final
verdict reproducible without treating skipped or mocked evidence as success.
"""

from __future__ import annotations

from collections.abc import Mapping

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


def validate_gate8_artifact(artifact: Mapping[str, object]) -> None:
    """Require attributable, real evidence for every Gate 8 scenario."""
    candidate = _required_mapping(artifact, "candidate")
    for key in ("commit", "branch", "recorded_at"):
        _required_value(candidate, key, "candidate")

    prerequisites = _required_mapping(artifact, "prerequisites")
    _required_value(prerequisites, "gate7_artifact", "prerequisites")
    environment = _required_mapping(artifact, "environment")
    _equal(environment.get("provider"), "ragflow", "provider")
    _equal(environment.get("real"), True, "real environment")
    _required_value(environment, "assets", "environment")

    scenarios = _required_mapping(artifact, "scenarios")
    for name in _REQUIRED_SCENARIOS:
        entry = _required_mapping(scenarios, name)
        _equal(entry.get("result"), "passed", name)
        _equal(entry.get("exit_status"), 0, f"{name} exit status")
        _required_value(entry, "command", name)
        _required_value(entry, "evidence", name)

    _equal(artifact.get("verdict"), "passed", "Gate 8 verdict")
    _assert_no_provider_secrets(artifact)


def _assert_no_provider_secrets(value: object) -> None:
    """Reject artifacts that accidentally contain provider implementation data."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            assert "secret" not in key_text and "api_key" not in key_text, f"sensitive field: {key}"
            assert "provider_dataset_id" not in key_text, f"provider identity field: {key}"
            _assert_no_provider_secrets(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_provider_secrets(item)


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
