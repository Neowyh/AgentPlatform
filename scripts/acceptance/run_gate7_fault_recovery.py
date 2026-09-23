#!/usr/bin/env python3
"""Exercise real provider-outage revision freezing and retry recovery."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml


def _validate_outage(run: dict, revision_id: str) -> None:
    receipts = run.get("receipts", [])
    if (
        len(receipts) != 1
        or receipts[0].get("result_status") != "provider_error"
        or receipts[0].get("archive_status") != "archived"
        or receipts[0].get("revision_id") != revision_id
    ):
        raise ValueError("provider outage must archive one provider_error receipt pinned to the frozen revision")


def _validate_retry(failed: dict, recovered: dict, revision_id: str) -> None:
    _validate_outage(failed, revision_id)
    receipts = recovered.get("receipts", [])
    if (
        recovered.get("status") not in {"completed", "success"}
        or len(receipts) != 1
        or receipts[0].get("result_status") != "success"
        or receipts[0].get("archive_status") != "archived"
        or receipts[0].get("revision_id") != revision_id
    ):
        raise ValueError("retry must recover with one archived successful receipt on the same revision")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("revision_freeze_provider_outage", "retry"), required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--knowledge-base", required=True)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    original = args.config.read_bytes()
    config = yaml.safe_load(original)
    tool = next(item for item in config["tools"] if item.get("name") == "knowledge_search")
    original_url = tool["base_url"]
    client = httpx.Client(base_url=args.gateway, timeout=120)
    username = "user@test.com"
    login = client.post("/api/v1/auth/login/local", data={"username": username, "password": username})
    login.raise_for_status()
    cookies = {item.name: item.value for item in login.cookies.jar}

    def request(method: str, path: str, **kwargs: object) -> dict:
        response = client.request(method, path, cookies={k: v for k, v in cookies.items() if k != "csrf_token"}, headers={"X-CSRF-Token": cookies["csrf_token"]}, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}

    def run_once() -> dict:
        thread = request("POST", "/api/threads", json={})["thread_id"]
        run_id = request("POST", f"/api/threads/{thread}/runs", json={"assistant_id": args.agent, "input": {"messages": [{"role": "user", "content": f"Call knowledge_search exactly once for knowledge_base '{args.knowledge_base}' and query 'Gate 7 isolated matrix citation marker'. Then report the result."}]}})["run_id"]
        deadline = time.monotonic() + 300
        while True:
            state = request("GET", f"/api/threads/{thread}/runs/{run_id}")
            if state.get("status") in {"completed", "success", "failed", "error"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Gate 7 run {run_id} did not finish")
            time.sleep(2)
        evidence = request("GET", f"/api/runs/{run_id}/evidence")
        return {"thread_id": thread, "run_id": run_id, "status": state.get("status"), "receipts": evidence.get("receipts", [])}

    try:
        tool["base_url"] = "http://127.0.0.1:1"
        args.config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        failed = run_once()
        receipts = failed["receipts"]
        if len(receipts) != 1 or receipts[0].get("revision_id") is None:
            raise ValueError("outage run did not persist its frozen retrieval revision")
        revision_id = receipts[0]["revision_id"]
        _validate_outage(failed, revision_id)
        runs = [failed]
        if args.scenario == "retry":
            tool["base_url"] = original_url
            args.config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
            recovered = run_once()
            _validate_retry(failed, recovered, revision_id)
            runs.append(recovered)
        result = {
            "candidate_commit": os.environ["GATE7_CANDIDATE_COMMIT"],
            "scenario": args.scenario,
            "real_execution": True,
            "result": "passed",
            "observed_steps": ["ran a real Agent against a deliberately unavailable local provider endpoint", "verified the archived provider_error receipt retained the frozen KB revision"] + (["restored the isolated provider endpoint", "retried the same retrieval request and verified archived success on the same revision"] if args.scenario == "retry" else []),
            "frozen_revision_id": revision_id,
            "runs": runs,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        output = Path(os.environ["GATE7_EVIDENCE_PATH"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    finally:
        tool["base_url"] = original_url
        args.config.write_bytes(original)
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
