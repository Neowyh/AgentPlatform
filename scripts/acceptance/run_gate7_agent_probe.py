#!/usr/bin/env python3
"""Run deterministic Gate 7 probes through a real Gateway Agent."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


def _validate_probe_results(mode: str, runs: list[dict]) -> None:
    if any(item.get("status") not in {"completed", "success"} for item in runs):
        raise ValueError(f"{mode} Agent run did not complete successfully")
    receipts = [receipt for item in runs for receipt in item.get("receipts", [])]
    if mode == "empty_hit":
        if (
            len(runs) != 1
            or len(receipts) != 1
            or receipts[0].get("result_status") != "empty_hit"
            or receipts[0].get("archive_status") != "archived"
            or receipts[0].get("items")
        ):
            raise ValueError("empty_hit requires one archived empty_hit receipt with no items")
        return
    ids = [receipt.get("receipt_id") for receipt in receipts]
    if (
        len(runs) != 2
        or len(receipts) != 2
        or not all(ids)
        or len(set(ids)) != 2
        or any(
            receipt.get("archive_status") != "archived"
            or receipt.get("result_status") != "success"
            or not receipt.get("items")
            for receipt in receipts
        )
    ):
        raise ValueError("duplicate requires two distinct archived successful receipts with items")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("empty_hit", "duplicate"), required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--knowledge-base", required=True)
    args = parser.parse_args()
    candidate = os.environ["GATE7_CANDIDATE_COMMIT"]
    output = Path(os.environ["GATE7_EVIDENCE_PATH"])
    client = httpx.Client(base_url=args.gateway, timeout=120)
    username = "user@test.com"
    login = client.post(
        "/api/v1/auth/login/local", data={"username": username, "password": username}
    )
    login.raise_for_status()
    cookies = {item.name: item.value for item in login.cookies.jar}

    def request(method: str, path: str, **kwargs: object) -> dict:
        response = client.request(
            method,
            path,
            cookies={k: v for k, v in cookies.items() if k != "csrf_token"},
            headers={"X-CSRF-Token": cookies["csrf_token"]},
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    revisions = request(
        "GET", f"/api/resources/{args.knowledge_base}/knowledge-revisions"
    )["items"]
    revision = max(
        (item for item in revisions if item.get("status") == "published"),
        key=lambda item: item["revision_no"],
    )
    agent_name = f"gate7-{args.mode}-{uuid4().hex[:12]}"
    agent = request(
        "POST",
        "/api/resources",
        json={
            "type": "agent",
            "slug": agent_name,
            "display_name": agent_name,
            "storage_kind": "filesystem",
        },
    )["id"]
    request(
        "PUT",
        f"/api/resources/{agent}/agent-draft",
        json={
            "config": {
                "name": agent_name,
                "description": f"Real Gate 7 {args.mode} acceptance probe",
                "skills": [],
                "tool_groups": ["knowledge"],
            },
            "soul": (
                "Use only knowledge_search. Always supply both required tool "
                "arguments, knowledge_base and query. Follow the user-provided "
                "query exactly and never substitute a different search. Do not "
                "use web_search or any other tool."
            ),
            "knowledge_dependencies": [
                {
                    "resource_id": args.knowledge_base,
                    "dependency_mode": "pinned",
                    "revision_id": revision["id"],
                    "required": True,
                    "purpose": f"Gate 7 {args.mode} scenario",
                }
            ],
            "expected_revision": 0,
        },
    )
    request(
        "POST",
        f"/api/resources/{agent}/publish",
        json={"expected_draft_revision": 1},
    )

    def run(query: str) -> dict:
        thread = request("POST", "/api/threads", json={})["thread_id"]
        run_id = request(
            "POST",
            f"/api/threads/{thread}/runs",
            json={
                "assistant_id": agent,
                "input": {"messages": [{"role": "user", "content": query}]},
            },
        )["run_id"]
        deadline = time.monotonic() + 900
        while True:
            state = request("GET", f"/api/threads/{thread}/runs/{run_id}")
            if state.get("status") in {"completed", "success", "failed", "error"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"run {run_id} timed out")
            time.sleep(5)
        evidence = request("GET", f"/api/runs/{run_id}/evidence")
        return {
            "thread_id": thread,
            "run_id": run_id,
            "status": state.get("status"),
            "receipts": evidence.get("receipts", []),
        }

    token = f"zxqv jjj qqq 99887766554433221100 {uuid4().hex}"
    query = (
        f"Call knowledge_search exactly once with knowledge_base "
        f"'{args.knowledge_base}' and query exactly '{token}'. If retrieval "
        "returns no items, reply that no matching source was found."
        if args.mode == "empty_hit"
        else f"Call knowledge_search with knowledge_base '{args.knowledge_base}' "
        "and query exactly 'Gate 7 isolated matrix citation marker'. Quote the "
        "returned source sentence and citation."
    )
    first = run(query)
    runs = [first]
    if args.mode == "duplicate":
        runs.append(run(query))
    _validate_probe_results(args.mode, runs)
    evidence = {
        "candidate_commit": candidate,
        "scenario": args.mode,
        "real_execution": True,
        "result": "passed",
        "observed_steps": [
            "created and published a scenario-specific real Agent through the Gateway",
            "waited for the real model/provider run to reach terminal state",
            "read persisted Evidence API receipts and verified archive status, result, and item invariants",
        ],
        "probe_agent_id": agent,
        "runs": runs,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
