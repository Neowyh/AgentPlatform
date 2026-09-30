"""Stub Result Contract validators for engine contract-gate tests.

These importable callables let workflow definitions declare a gate whose
behavior a test controls, without stubbing engine internals.
"""

from __future__ import annotations

from typing import Any

RECORDED_OUTPUTS_DIR: list[str] = []
RECORDED_SNAPSHOTS: list[dict[str, Any]] = []


def accepting_validator(outputs_dir: str, run_snapshot: dict) -> list[str]:
    return []


def rejecting_validator(outputs_dir: str, run_snapshot: dict) -> list[str]:
    return ["报告缺少章节 X", "证据引用悬空"]


def exploding_validator(outputs_dir: str, run_snapshot: dict) -> list[str]:
    raise RuntimeError("validator exploded")


def non_list_validator(outputs_dir: str, run_snapshot: dict) -> Any:
    return "ok"


def none_validator(outputs_dir: str, run_snapshot: dict) -> Any:
    return None


def recording_validator(outputs_dir: str, run_snapshot: dict) -> list[str]:
    RECORDED_OUTPUTS_DIR.append(str(outputs_dir))
    RECORDED_SNAPSHOTS.append(run_snapshot)
    return []
