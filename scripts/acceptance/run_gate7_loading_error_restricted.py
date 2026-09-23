#!/usr/bin/env python3
"""Verify real-browser Gate 7 evidence loading, error, and restricted UI states."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    candidate = os.environ["GATE7_CANDIDATE_COMMIT"]
    output = Path(os.environ["GATE7_EVIDENCE_PATH"])
    matrix_dir = Path(os.environ["GATE7_MATRIX_OUTPUT_DIR"])
    agent = json.loads((matrix_dir / "agent.json").read_text(encoding="utf-8"))
    items = [item for receipt in agent.get("receipts", []) for item in receipt.get("items", [])]
    if not items or not items[0].get("content"):
        raise SystemExit("loading/error/restricted browser scenario requires a real archived citation")
    env = os.environ.copy()
    env.update({
        "E2E_GATE7_THREAD_ID": str(agent["thread_id"]),
        "E2E_GATE7_RUN_ID": str(agent["run_id"]),
        "E2E_GATE7_EXPECTED_SNIPPET": next((line.strip() for line in str(items[0]["content"]).splitlines() if line.strip()), ""),
    })
    command = ["pnpm", "exec", "playwright", "test", "--config", "playwright.real.config.ts", "tests/e2e/real/gate7-evidence-states.spec.ts"]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[2] / "frontend", env=env, capture_output=True, text=True, timeout=600, check=False)
    if completed.returncode:
        raise SystemExit(f"real-browser evidence-state scenario failed ({completed.returncode}): {completed.stdout[-2500:]}{completed.stderr[-2500:]}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "candidate_commit": candidate,
        "scenario": "loading_error_restricted",
        "real_execution": True,
        "result": "passed",
        "observed_steps": [
            "opened the real chat containing the candidate-bound archived citation in Chromium",
            "held the Evidence API response to observe the loading state",
            "injected an HTTP 503 to verify the unavailable error state",
            "injected an access_restricted Evidence API response and verified the restricted state",
        ],
        "thread_id": agent["thread_id"],
        "run_id": agent["run_id"],
        "evidence_api_fault_injection": "browser route interception for deterministic error and access_restricted responses",
        "playwright_summary": "1 passed",
        "recorded_at": datetime.now(UTC).isoformat(),
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
