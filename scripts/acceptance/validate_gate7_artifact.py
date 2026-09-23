#!/usr/bin/env python3
"""Strictly validate a real Gate 7 matrix artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from tests.gate7_acceptance import _MATRIX_SCENARIOS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--current-commit")
    args = parser.parse_args(argv)
    current = (
        args.current_commit
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    )
    try:
        artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
        assert artifact.get("candidate_commit") == current, (
            "candidate_commit does not match current checkout"
        )
        assert artifact.get("status") == "passed", "artifact is not passed"
        rows = artifact.get("rows")
        assert isinstance(rows, dict) and set(rows) == set(_MATRIX_SCENARIOS), (
            "artifact does not contain exactly 16 rows"
        )
        for scenario in _MATRIX_SCENARIOS:
            row = rows[scenario]
            assert row.get("result") == "passed", f"{scenario} is not passed"
            assert row.get("provider"), f"{scenario} has no provider record"
            assert row.get("model"), f"{scenario} has no model record"
            assert row.get("browser"), f"{scenario} has no browser record"
            assert (
                isinstance(row.get("duration_seconds"), (int, float))
                and row["duration_seconds"] >= 0
            ), f"{scenario} has invalid duration"
            evidence_path = args.artifact.parent / row["evidence"]
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            assert evidence.get("result") == "passed", (
                f"{scenario} evidence is not passed"
            )
            assert evidence.get("candidate_commit") == current, (
                f"{scenario} evidence has stale candidate"
            )
            assert evidence.get("scenario") == scenario, (
                f"{scenario} evidence has wrong scenario"
            )
            assert evidence.get("real_execution") is True, (
                f"{scenario} is not marked real_execution"
            )
            assert evidence.get("observed_steps"), f"{scenario} has no observed_steps"
    except (
        AssertionError,
        OSError,
        subprocess.CalledProcessError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Gate 7 artifact: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"Gate 7 artifact: PASS ({current}, 16 rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
