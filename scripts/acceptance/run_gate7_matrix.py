#!/usr/bin/env python3
"""Run the Gate 7 matrix against a real isolated Gateway.

The runner deliberately has no mock or "mark passed" mode.  Agent and
Workflow/Sub-Agent use the Gateway HTTP API directly.  The other rows are
provided as commands in a JSON manifest because their fault/browser fixtures
are deployment-specific; each command must write one sanitized evidence JSON
file and exit zero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROWS = (
    "agent",
    "workflow_subagent",
    "two_users_two_kbs",
    "revoked_access",
    "revision_freeze_provider_outage",
    "empty_hit",
    "truncated",
    "retry",
    "duplicate",
    "archive_failure",
    "forged_citation",
    "history_without_receipt",
    "mixed_web",
    "streaming",
    "loading_error_restricted",
    "keyboard",
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--gateway", default=os.environ.get("GATE7_GATEWAY", "http://127.0.0.1:8003")
    )
    p.add_argument("--dataset", default=os.environ.get("RAGFLOW_GATE7_DATASET_ID"))
    p.add_argument("--agent", default=os.environ.get("GATE7_AGENT_ID"))
    p.add_argument("--knowledge-base", default=os.environ.get("GATE7_KB_ID"))
    p.add_argument(
        "--workflow-agent-name",
        default=os.environ.get("GATE7_WORKFLOW_AGENT_NAME", "g7b-agent-v3"),
    )
    p.add_argument("--model", default=os.environ.get("GATE7_MODEL", "agnes-3.0-flash"))
    p.add_argument("--user", default="user@test.com")
    p.add_argument(
        "--resume",
        action="store_true",
        help="reuse only passed evidence bound to this candidate and rerun incomplete/stale rows",
    )
    return p


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Gateway:
    def __init__(self, base: str, username: str) -> None:
        self.client = httpx.Client(base_url=base, timeout=120)
        response = self.client.post(
            "/api/v1/auth/login/local",
            data={"username": username, "password": username},
        )
        response.raise_for_status()
        self.cookies = {cookie.name: cookie.value for cookie in response.cookies.jar}

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        headers["X-CSRF-Token"] = self.cookies["csrf_token"]
        response = self.client.request(
            method,
            path,
            cookies={k: v for k, v in self.cookies.items() if k != "csrf_token"},
            headers=headers,
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def request_text(self, method: str, path: str, **kwargs: Any) -> str:
        headers = dict(kwargs.pop("headers", {}))
        headers["X-CSRF-Token"] = self.cookies["csrf_token"]
        response = self.client.request(
            method,
            path,
            cookies={k: v for k, v in self.cookies.items() if k != "csrf_token"},
            headers=headers,
            **kwargs,
        )
        response.raise_for_status()
        return response.text

    def run_agent(self, agent: str, knowledge_base: str) -> dict[str, Any]:
        thread = self.request("POST", "/api/threads", json={})["thread_id"]
        question = (
            f"Call the knowledge_search tool exactly once with "
            f"knowledge_base='{knowledge_base}' and query "
            "'Gate 7 isolated matrix citation marker'. Do not use web_search "
            "or any other tool. Quote the exact retrieved source sentence and "
            "append its citation link."
        )
        run = self.request(
            "POST",
            f"/api/threads/{thread}/runs",
            json={
                "assistant_id": agent,
                "input": {"messages": [{"role": "user", "content": question}]},
            },
        )["run_id"]
        deadline = time.monotonic() + 900
        while True:
            state = self.request("GET", f"/api/threads/{thread}/runs/{run}")
            status = state.get("status")
            if status in {"completed", "success", "failed", "error"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"agent run {run} did not reach a terminal state")
            time.sleep(5)
        evidence = self.request("GET", f"/api/runs/{run}/evidence")
        receipts = evidence.get("receipts", [])
        if status not in {"completed", "success"} or not receipts:
            raise RuntimeError(
                f"agent run {run} status={status!r} receipts={len(receipts)}"
            )
        evidence = {
            "thread_id": thread,
            "run_id": run,
            "status": status,
            "receipts": receipts,
        }
        _require_archived_receipts(evidence, "agent run")
        return evidence

    def run_workflow(
        self, knowledge_base: str, dataset: str, model: str
    ) -> dict[str, Any]:
        revisions = self.request(
            "GET", f"/api/resources/{knowledge_base}/knowledge-revisions"
        )["items"]
        revision = max(
            (item for item in revisions if item.get("status") == "published"),
            key=lambda item: item["revision_no"],
        )
        agent_name = f"gate7-workflow-{uuid.uuid4().hex[:12]}"
        agent = self.request(
            "POST",
            "/api/resources",
            json={
                "type": "agent",
                "slug": agent_name,
                "display_name": agent_name,
                "storage_kind": "filesystem",
            },
        )["id"]
        self.request(
            "PUT",
            f"/api/resources/{agent}/agent-draft",
            json={
                "config": {
                    "name": agent_name,
                    "description": "Real Gate 7 Workflow/Sub-Agent acceptance probe",
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
                        "resource_id": knowledge_base,
                        "dependency_mode": "pinned",
                        "revision_id": revision["id"],
                        "required": True,
                        "purpose": "Gate 7 Workflow/Sub-Agent scenario",
                    }
                ],
                "expected_revision": 0,
            },
        )
        self.request(
            "POST",
            f"/api/resources/{agent}/publish",
            json={"expected_draft_revision": 1},
        )
        slug = f"gate7-matrix-{uuid.uuid4().hex[:12]}"
        workflow = self.request(
            "POST",
            "/api/resources",
            json={
                "type": "workflow",
                "slug": slug,
                "display_name": slug,
                "storage_kind": "database",
            },
        )["id"]
        question = (
            "Make exactly one knowledge_search call using these exact arguments: "
            f"knowledge_base='{knowledge_base}' and query="
            "'Gate 7 isolated matrix citation marker'. Do not call "
            "list_uploaded_files, web_search, or any other tool. After that "
            "call, immediately quote the exact returned source sentence and "
            "citation; do not make another tool call."
        )
        content = {
            "schema_version": 2,
            "name": slug,
            "inputs": {},
            "state": {},
            "entrypoint": "cite",
            "nodes": [
                {
                    "id": "cite",
                    "type": "action",
                    "action": {
                        "kind": "agent",
                        "name": agent_name,
                        "params": {"max_turns": 10, "prompt": question},
                    },
                }
            ],
            "edges": [],
        }
        self.request(
            "PUT",
            f"/api/resources/{workflow}/workflow-draft",
            json={"content": content, "expected_revision": 0},
        )
        self.request(
            "POST",
            f"/api/resources/{workflow}/publish",
            json={"expected_draft_revision": 1},
        )
        run = self.request(
            "POST",
            f"/api/resources/{workflow}/workflow-runs",
            json={
                "inputs": {"knowledge_scope": {"bindings": {knowledge_base: dataset}}},
                "model_name": model,
            },
        )["run_id"]
        deadline = time.monotonic() + 900
        while True:
            state = self.request(
                "GET", f"/api/resources/{workflow}/workflow-runs/{run}"
            )
            status = state.get("status")
            if status in {"completed", "failed", "error", "paused"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"workflow run {run} did not reach a terminal state")
            time.sleep(10)
        if status != "completed":
            raise RuntimeError(f"workflow run {run} status={status!r}")
        run_evidence = state.get("snapshot", {}).get("run_evidence", {})
        scope = run_evidence.get("knowledge_scope", {})
        revision = scope.get("revisions", {}).get(knowledge_base, {})
        if (
            knowledge_base not in scope.get("logical_selectors", [])
            or not revision.get("revision_id")
            or not revision.get("manifest_hash")
        ):
            raise RuntimeError(f"workflow run {run} lacks a frozen KB revision")

        raw_events = self.request_text(
            "GET",
            f"/api/resources/{workflow}/workflow-runs/{run}/events?after_seq=0",
            headers={"Accept": "text/event-stream"},
        )
        events = []
        for block in raw_events.split("\n\n"):
            data = next(
                (line[6:] for line in block.splitlines() if line.startswith("data: ")),
                None,
            )
            if data is not None:
                event_type = next(
                    (line[7:] for line in block.splitlines() if line.startswith("event: ")),
                    "",
                )
                events.append({"event_type": event_type, **json.loads(data)})
        tool_events = [
            event
            for event in events
            if event.get("event_type") == "action_progress"
            and "knowledge_search" in str(event.get("message", ""))
        ]
        node_results = [
            event.get("result")
            for event in events
            if event.get("event_type") == "node_completed"
        ]
        result_text = "\n".join(str(value) for value in node_results)
        if (
            not tool_events
            or not _has_workflow_citation(result_text)
        ):
            raise RuntimeError(
                f"workflow run {run} did not persist the expected knowledge tool call and citation"
            )
        receipts = run_evidence.get("retrieval_receipts", [])
        evidence = {
            "workflow_id": workflow,
            "run_id": run,
            "status": status,
            "receipts": receipts,
            "frozen_knowledge_revision": revision,
            "knowledge_tool_event_count": len(tool_events),
            "node_result": result_text,
            "receipt_chain_persisted": bool(receipts),
        }
        return evidence


def _require_archived_receipts(evidence: dict[str, Any], label: str) -> None:
    receipts = evidence.get("receipts", [])
    if not receipts or any(
        receipt.get("archive_status") != "archived"
        or receipt.get("result_status") != "success"
        or not receipt.get("items")
        for receipt in receipts
    ):
        raise RuntimeError(
            f"{label} did not produce an archived successful retrieval receipt"
        )


def _has_workflow_citation(result_text: str) -> bool:
    has_marker = "Gate 7 isolated matrix citation marker 8d7d6179." in result_text
    has_numbered_source = re.search(
        r"\[\d+\][^\n]*gate7-matrix-marker\.txt", result_text
    ) is not None
    has_legacy_citation = (
        "[citation:" in result_text and "gate7-matrix-marker.txt" in result_text
    )
    return has_marker and (has_numbered_source or has_legacy_citation)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _resumable_row(
    row: dict[str, Any], evidence_path: Path, scenario: str, candidate: str
) -> bool:
    if row.get("result") != "passed" or row.get("evidence") != evidence_path.name:
        return False
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        evidence.get("candidate_commit") == candidate
        and evidence.get("scenario") == scenario
        and evidence.get("real_execution") is True
        and evidence.get("result") == "passed"
        and bool(evidence.get("observed_steps"))
    )


def _annotate_real_evidence(
    evidence: dict[str, Any],
    candidate: str,
    scenario: str,
    observed_steps: list[str],
) -> dict[str, Any]:
    evidence.update(
        {
            "candidate_commit": candidate,
            "scenario": scenario,
            "real_execution": True,
            "result": "passed",
            "observed_steps": observed_steps,
        }
    )
    return evidence


def _external_row(
    row: str, spec: dict[str, Any], output: Path, candidate: str
) -> dict[str, Any]:
    command = spec.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) for item in command)
    ):
        raise ValueError(
            f"manifest command missing for {row}; real execution is required"
        )
    evidence = output / f"{row}.json"
    env = os.environ.copy()
    env.update(
        {
            "GATE7_CANDIDATE_COMMIT": candidate,
            "GATE7_SCENARIO": row,
            "GATE7_EVIDENCE_PATH": str(evidence),
            "GATE7_MATRIX_OUTPUT_DIR": str(output),
        }
    )
    started = time.monotonic()
    completed = subprocess.run(
        command,
        env=env,
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        text=True,
        capture_output=True,
        timeout=int(spec.get("timeout_seconds", 900)),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"scenario command exited {completed.returncode}: {completed.stderr[-1000:]}"
        )
    if not evidence.exists():
        raise RuntimeError(f"scenario command did not create {evidence}")
    recorded = json.loads(evidence.read_text(encoding="utf-8"))
    if (
        recorded.get("candidate_commit") != candidate
        or recorded.get("scenario") != row
        or recorded.get("result") != "passed"
        or recorded.get("real_execution") is not True
        or not recorded.get("observed_steps")
    ):
        raise ValueError(f"{row} evidence is not attributable real evidence")
    recorded["runner_duration_seconds"] = round(time.monotonic() - started, 3)
    _write_json(evidence, recorded)
    return recorded


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    candidate = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not candidate.startswith("5694971b"):
        raise SystemExit(
            f"refusing to run: current candidate is {candidate}, expected 5694971b"
        )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    specs = manifest.get("scenarios", {})
    if set(specs) != set(ROWS):
        raise SystemExit("manifest must define exactly the 16 Gate 7 scenarios")
    args.output.mkdir(parents=True, exist_ok=True)
    prior_rows: dict[str, Any] = {}
    matrix_path = args.output / "gate7-matrix.json"
    if args.resume and matrix_path.exists():
        prior = json.loads(matrix_path.read_text(encoding="utf-8"))
        if prior.get("candidate_commit") != candidate:
            raise SystemExit("refusing to resume a matrix bound to another candidate")
        if not isinstance(prior.get("rows"), dict) or set(prior["rows"]) - set(ROWS):
            raise SystemExit("refusing to resume a malformed matrix row set")
        prior_rows = prior["rows"]
    matrix: dict[str, Any] = {
        "candidate_commit": candidate,
        "recorded_at": _now(),
        "status": "incomplete",
        "rows": prior_rows,
    }
    if args.resume and prior_rows:
        matrix["resumed_at"] = _now()
    gateway = Gateway(args.gateway, args.user)
    for row in ROWS:
        prior_row = matrix["rows"].get(row, {})
        if args.resume and _resumable_row(
            prior_row, args.output / f"{row}.json", row, candidate
        ):
            continue
        started, started_at = time.monotonic(), _now()
        try:
            if row == "agent":
                if not args.agent or not args.knowledge_base:
                    raise ValueError(
                        "--agent and --knowledge-base are required for the real Agent row"
                    )
                evidence = gateway.run_agent(args.agent, args.knowledge_base)
                _annotate_real_evidence(
                    evidence,
                    candidate,
                    row,
                    [
                            "created a real Gateway Agent run",
                            "waited for terminal completion",
                            "read persisted run evidence receipts",
                    ],
                )
                _write_json(args.output / f"{row}.json", evidence)
            elif row == "workflow_subagent":
                if not args.knowledge_base or not args.dataset:
                    raise ValueError(
                        "--knowledge-base and --dataset are required for the real Workflow row"
                    )
                evidence = gateway.run_workflow(
                    args.knowledge_base,
                    args.dataset,
                    args.model,
                )
                _annotate_real_evidence(
                    evidence,
                    candidate,
                    row,
                    [
                            "created a real Workflow resource",
                            "published an Agent action and ran it",
                            "verified terminal completion",
                    ],
                )
                _write_json(args.output / f"{row}.json", evidence)
            else:
                evidence = _external_row(row, specs[row], args.output, candidate)
            matrix["rows"][row] = {
                "result": "passed",
                "provider": specs[row].get("provider", "ragflow"),
                "model": specs[row].get("model", args.model),
                "browser": specs[row].get("browser", "not-applicable"),
                "evidence": f"{row}.json",
                "started_at": started_at,
                "finished_at": _now(),
                "duration_seconds": round(time.monotonic() - started, 3),
            }
        except (
            OSError,
            RuntimeError,
            TimeoutError,
            ValueError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            httpx.HTTPError,
        ) as exc:
            matrix["rows"][row] = {
                "result": "incomplete",
                "error": str(exc),
                "started_at": started_at,
                "finished_at": _now(),
                "duration_seconds": round(time.monotonic() - started, 3),
            }
    if len(matrix["rows"]) == len(ROWS) and all(
        item.get("result") == "passed" for item in matrix["rows"].values()
    ):
        matrix["status"] = "passed"
    _write_json(args.output / "gate7-matrix.json", matrix)
    return 0 if matrix["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
