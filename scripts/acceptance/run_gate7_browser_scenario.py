#!/usr/bin/env python3
"""Execute and record the real Gate 7 browser citation scenario."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"missing required real-browser variable: {name}")
    return value


def _browser_citation_snippet(receipts: list[dict]) -> str:
    items = [item for receipt in receipts for item in receipt.get("items", [])]
    item = next(
        (
            candidate
            for candidate in items
            if candidate.get("display_name") == "gate7-matrix-marker.txt"
        ),
        None,
    )
    if item is None:
        raise ValueError("Agent evidence has no gate7-matrix-marker.txt receipt item")
    content = item.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Gate 7 matrix marker receipt item has no citation snippet")
    snippet = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if not snippet:
        raise ValueError("Gate 7 matrix marker receipt item has no citation snippet")
    return snippet


def main() -> int:
    candidate = _required("GATE7_CANDIDATE_COMMIT")
    output = Path(_required("GATE7_EVIDENCE_PATH"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gateway", required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    matrix_dir = Path(_required("GATE7_MATRIX_OUTPUT_DIR"))
    agent_evidence = json.loads((matrix_dir / "agent.json").read_text(encoding="utf-8"))
    receipts = agent_evidence.get("receipts", [])
    snippet = _browser_citation_snippet(receipts)
    state_dir = str(manifest["state_dir"])
    run_id = str(manifest["run_id"])
    gateway = args.gateway
    thread = str(agent_evidence["thread_id"])
    evidence_run = str(agent_evidence["run_id"])
    command = [
        "pnpm",
        "exec",
        "playwright",
        "test",
        "--config",
        "playwright.real.config.ts",
        "tests/e2e/real/knowledge-evidence-gate7.spec.ts",
    ]
    env = os.environ.copy()
    env.update(
        {
            "E2E_STATE_DIR": state_dir,
            "E2E_RUN_ID": run_id,
            "IDEER_INTERNAL_GATEWAY_BASE_URL": gateway,
            "E2E_GATE7_THREAD_ID": thread,
            "E2E_GATE7_RUN_ID": evidence_run,
            "E2E_GATE7_EXPECTED_SNIPPET": snippet,
        }
    )
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2] / "frontend",
        env=env,
        check=False,
        text=True,
        capture_output=True,
        timeout=600,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"real browser scenario failed ({completed.returncode}): {completed.stdout[-2000:]}{completed.stderr[-2000:]}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "candidate_commit": candidate,
                "scenario": "keyboard",
                "real_execution": True,
                "observed_steps": [
                    "built and started the real Next.js frontend",
                    "opened the real thread and verified the exact archived snippet",
                    "opened Evidence Panel with Enter and closed it with Escape",
                    "verified keyboard focus returned to the citation control",
                ],
                "thread_id": thread,
                "run_id": evidence_run,
                "playwright_summary": "1 passed",
                "recorded_at": datetime.now(UTC).isoformat(),
                "result": "passed",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
