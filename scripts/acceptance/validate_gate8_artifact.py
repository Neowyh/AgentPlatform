#!/usr/bin/env python3
"""Validate a recorded Gate 8 artifact at the command line.

This command only validates evidence that has already been recorded.  It does
not create scenario results or turn skipped execution into a pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifact", type=Path, help="path to the recorded Gate 8 JSON artifact"
    )
    parser.add_argument(
        "--current-commit",
        help="candidate commit to compare with (defaults to the checked-out HEAD)",
    )
    parser.add_argument(
        "--forbidden-value",
        action="append",
        default=[],
        help="sensitive value that must not occur in the artifact (repeatable)",
    )
    return parser


def _current_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
        if not isinstance(artifact, dict):
            raise ValueError("artifact root must be a JSON object")
        # Keep the test helper as the single schema implementation.  Importing
        # through the backend package also ensures this command and the live
        # acceptance test cannot silently drift apart.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
        from tests.gate8_acceptance import validate_gate8_artifact

        commit = args.current_commit or _current_commit()
        validate_gate8_artifact(
            artifact,
            current_commit=commit,
            forbidden_values=set(args.forbidden_value),
        )
    except (
        AssertionError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Gate 8 artifact: FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"Gate 8 artifact: PASS ({commit})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
