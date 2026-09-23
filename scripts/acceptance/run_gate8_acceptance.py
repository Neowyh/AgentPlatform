#!/usr/bin/env python3
"""Execute configured real Gate 8 scenarios and capture a strict artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from tests.gate8_acceptance import (  # noqa: E402
    _REQUIRED_SCENARIOS,
    _SCENARIO_OBSERVATIONS,
    _assert_no_provider_secrets,
    validate_gate8_artifact,
)

_SENSITIVE_COMMAND_VALUE = re.compile(
    r"https?://|api[_-]?key|password|dataset[_-]?id|internal[_-]?id",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gate7-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-commit")
    return parser


def _validate_manifest(manifest: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("scenarios"), dict
    ):
        raise ValueError("manifest must contain a scenarios object")
    scenarios = manifest["scenarios"]
    if set(scenarios) != set(_REQUIRED_SCENARIOS):
        raise ValueError("manifest must define exactly the ten Gate 8 scenarios")
    for name, spec in scenarios.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{name} scenario must be an object")
        command = spec.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(value, str) and value for value in command)
        ):
            raise ValueError(f"{name} command must be a non-empty argv list")
        if any(_SENSITIVE_COMMAND_VALUE.search(value) for value in command):
            raise ValueError(
                f"{name} command may not contain provider details or secrets"
            )
        timeout = spec.get("timeout_seconds", 900)
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or timeout < 1
            or timeout > 7200
        ):
            raise ValueError(f"{name} timeout_seconds must be a positive integer")
    return scenarios


def _run_scenario(
    name: str,
    spec: dict[str, Any],
    evidence_path: Path,
    candidate: str,
) -> tuple[dict[str, Any], bool]:
    command = spec["command"]
    command_text = shlex.join(command)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.unlink(missing_ok=True)
    started_at = _now()
    started = time.monotonic()
    env = {
        **os.environ,
        "GATE8_CANDIDATE_COMMIT": candidate,
        "GATE8_SCENARIO": name,
        "GATE8_EVIDENCE_PATH": str(evidence_path.resolve()),
        "GATE8_MATRIX_OUTPUT_DIR": str(evidence_path.parent.resolve()),
        "GATE8_REQUIRED_OBSERVATIONS": json.dumps(
            _SCENARIO_OBSERVATIONS[name],
        ),
    }
    returncode = 124
    status = "failed"
    passed = False
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=spec.get("timeout_seconds", 900),
        )
        returncode = completed.returncode
        if returncode == 0 and evidence_path.is_file():
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            observations = (
                payload.get("observations") if isinstance(payload, dict) else None
            )
            assertions = (
                payload.get("assertions") if isinstance(payload, dict) else None
            )
            required = _SCENARIO_OBSERVATIONS[name]
            forbidden_values = {
                value
                for key, value in env.items()
                if value
                and any(
                    token in key.lower()
                    for token in ("api_key", "api-key", "password", "token")
                )
            }
            valid = (
                isinstance(payload, dict)
                and payload.get("candidate_commit") == candidate
                and payload.get("scenario") == name
                and payload.get("real_execution") is True
                and isinstance(payload.get("observed_steps"), list)
                and bool(payload["observed_steps"])
                and all(
                    isinstance(step, str) and step.strip()
                    for step in payload["observed_steps"]
                )
                and isinstance(observations, dict)
                and all(observations.get(key) not in (None, "", []) for key in required)
                and isinstance(assertions, list)
                and bool(assertions)
                and all(isinstance(item, str) and item.strip() for item in assertions)
            )
            if valid:
                try:
                    _assert_no_provider_secrets(
                        payload, forbidden_values=forbidden_values
                    )
                except AssertionError:
                    valid = False
            if valid:
                status, passed = "executed", True
    except subprocess.TimeoutExpired:
        status = "timeout"
    except (OSError, json.JSONDecodeError):
        status = "failed"

    if not passed:
        evidence_path.unlink(missing_ok=True)

    finished_at = _now()
    entry: dict[str, Any] = {
        "result": "passed" if passed else "incomplete",
        "status": status,
        "exit_status": returncode,
        "command": command_text,
        "evidence": str(evidence_path.resolve()),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(time.monotonic() - started, 3),
        "assertions": [],
        "observations": {},
    }
    if passed:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        entry["assertions"] = payload["assertions"]
        entry["observations"] = payload["observations"]
    return entry, passed


def capture_gate8(
    *,
    manifest_path: Path,
    gate7_artifact: Path,
    output_path: Path,
    candidate: str,
    branch: str,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    specs = _validate_manifest(manifest)
    gate7 = json.loads(gate7_artifact.read_text(encoding="utf-8"))
    if (
        not isinstance(gate7, dict)
        or gate7.get("status") != "passed"
        or gate7.get("candidate_commit") != candidate
    ):
        raise ValueError("Gate 7 artifact must be passed on the same candidate")

    evidence_dir = output_path.parent / f"{output_path.stem}-scenarios"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifact: dict[str, Any] = {
        "candidate": {
            "commit": candidate,
            "branch": branch,
            "recorded_at": _now(),
        },
        "prerequisites": {"gate7_artifact": str(gate7_artifact.resolve())},
        "environment": {
            "provider": "ragflow",
            "real": True,
            "assets": ["isolated Gate 8 provider and browser fixtures"],
        },
        "scenarios": {},
        "verdict": "incomplete",
    }

    all_passed = True
    for name in _REQUIRED_SCENARIOS:
        entry, passed = _run_scenario(
            name, specs[name], evidence_dir / f"{name}.json", candidate
        )
        artifact["scenarios"][name] = entry
        all_passed = all_passed and passed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if all_passed:
        try:
            artifact["verdict"] = "passed"
            validate_gate8_artifact(artifact, current_commit=candidate)
        except (AssertionError, OSError, ValueError):
            artifact["verdict"] = "incomplete"
            artifact["validation"] = "strict-validator-failed"
    output_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return artifact


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        candidate = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        if args.expected_commit and args.expected_commit != candidate:
            raise ValueError("HEAD does not match --expected-commit")
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip()
        artifact = capture_gate8(
            manifest_path=args.manifest,
            gate7_artifact=args.gate7_artifact,
            output_path=args.output,
            candidate=candidate,
            branch=branch,
        )
    except (
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Gate 8 capture: incomplete ({type(exc).__name__})", file=sys.stderr)
        return 1
    if artifact["verdict"] != "passed":
        print(f"Gate 8 capture: incomplete ({args.output})", file=sys.stderr)
        return 1
    print(f"Gate 8 capture: passed ({candidate})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
