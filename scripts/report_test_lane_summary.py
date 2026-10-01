#!/usr/bin/env python3
"""Validate selected PR lane results and render a concise handoff summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CHANNEL_JOBS = {
    "governance": "test-contracts",
    "backend-standard": "backend-unit-tests",
    "frontend-standard": "frontend-unit-tests",
    "local-runtime": "local-runtime",
    "frontend-smoke": "e2e-tests",
    "static-checks": "lint",
}
CHANNEL_ORDER = (
    "governance",
    "backend-standard",
    "frontend-standard",
    "local-runtime",
    "frontend-smoke",
    "static-checks",
    "real-e2e",
)


def summarize(plan: dict[str, Any], needs: dict[str, Any]) -> dict[str, Any]:
    selected = set(plan.get("channels", []))
    channels: dict[str, dict[str, Any]] = {}
    ok = True
    for channel in CHANNEL_ORDER:
        if channel not in selected:
            channels[channel] = {"status": "not-required", "reasons": []}
            continue
        reasons = plan.get("reasons", {}).get(channel, [])
        if channel == "real-e2e":
            channels[channel] = {
                "status": "delegated",
                "reasons": reasons,
                "required_check": "Real E2E Gate",
            }
            continue
        job = CHANNEL_JOBS[channel]
        result = needs.get(job, {}).get("result")
        if result == "success":
            status = "success"
        elif result in {"failure", "cancelled"}:
            status = result
            ok = False
        else:
            status = "missing-required-result"
            ok = False
        channels[channel] = {"status": status, "reasons": reasons, "job": job}
    return {"ok": ok, "channels": channels}


def render(plan: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = ["## PR test lane selection", "", "Changed files:"]
    paths = plan.get("changed_files", [])
    lines.extend([f"- `{path}`" for path in paths] or ["- No changed files"])
    lines.extend(["", "Selected validation:"])
    for channel in CHANNEL_ORDER:
        result = summary["channels"][channel]
        status = result["status"]
        reasons = "; ".join(result.get("reasons", []))
        lines.append(f"- `{channel}`: **{status}**" + (f" — {reasons}" if reasons else ""))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", required=True)
    parser.add_argument("--needs-json", required=True)
    parser.add_argument("--summary-file", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan_json)
    needs = json.loads(args.needs_json)
    summary = summarize(plan, needs)
    output = render(plan, summary)
    print(output)
    if args.summary_file:
        with args.summary_file.open("a", encoding="utf-8") as handle:
            handle.write(output)
    print(json.dumps(summary, sort_keys=True), file=sys.stderr)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
