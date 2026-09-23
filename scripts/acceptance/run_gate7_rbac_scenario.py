#!/usr/bin/env python3
"""Exercise real private-KB isolation and revoked-session behavior."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from run_gate7_matrix import Gateway


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("two_users_two_kbs", "revoked_access"), required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--existing-kb")
    return parser


def _response(gateway: Gateway, path: str) -> tuple[int, str]:
    response = gateway.client.get(
        path,
        cookies={key: value for key, value in gateway.cookies.items() if key != "csrf_token"},
        headers={"X-CSRF-Token": gateway.cookies["csrf_token"]},
    )
    return response.status_code, response.text[:300]


def _create_user_and_kb(admin: Gateway) -> tuple[str, Gateway, str]:
    email = f"gate7-{uuid4().hex[:16]}@example.com"
    password = f"Gate7-{uuid4().hex}"
    user = admin.request(
        "POST",
        "/api/admin/users",
        json={"email": email, "username": email, "password": password, "role": "user"},
    )
    client = Gateway.__new__(Gateway)
    client.client = httpx.Client(base_url=str(admin.client.base_url), timeout=120)
    login = client.client.post(
        "/api/v1/auth/login/local", data={"username": email, "password": password}
    )
    login.raise_for_status()
    client.cookies = {cookie.name: cookie.value for cookie in login.cookies.jar}
    resource = client.request(
        "POST",
        "/api/resources",
        json={
            "type": "knowledge_base",
            "slug": f"gate7-{uuid4().hex[:12]}",
            "display_name": "Gate 7 isolated private KB",
            "storage_kind": "database",
        },
    )
    return user["id"], client, resource["id"]


def _evidence(scenario: str, observations: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_commit": os.environ["GATE7_CANDIDATE_COMMIT"],
        "scenario": scenario,
        "real_execution": True,
        "result": "passed",
        "observed_steps": observations["observed_steps"],
        "observations": observations,
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def main() -> int:
    args = _parser().parse_args()
    admin = Gateway(args.gateway, "super_admin@test.com")
    user_id, user, new_kb = _create_user_and_kb(admin)

    if args.scenario == "two_users_two_kbs":
        if not args.existing_kb:
            raise ValueError("--existing-kb is required for two_users_two_kbs")
        owner = Gateway(args.gateway, "user@test.com")
        statuses = {
            "owner1_reads_kb1": _response(owner, f"/api/resources/{args.existing_kb}")[0],
            "owner1_reads_kb2": _response(owner, f"/api/resources/{new_kb}")[0],
            "owner2_reads_kb1": _response(user, f"/api/resources/{args.existing_kb}")[0],
            "owner2_reads_kb2": _response(user, f"/api/resources/{new_kb}")[0],
        }
        if statuses != {
            "owner1_reads_kb1": 200,
            "owner1_reads_kb2": 404,
            "owner2_reads_kb1": 404,
            "owner2_reads_kb2": 200,
        }:
            raise ValueError(f"private KB ownership matrix failed: {statuses}")
        steps = [
            "created a second real local user through the isolated admin API",
            "created a private Knowledge Base owned by that user",
            "checked both users against both private KB resource APIs",
        ]
    else:
        before = _response(user, f"/api/resources/{new_kb}")[0]
        admin.request("PATCH", f"/api/admin/users/{user_id}/status")
        try:
            me_status, me_body = _response(user, "/api/v1/auth/me")
        except httpx.HTTPError as exc:
            me_status, me_body = 0, type(exc).__name__
        try:
            after, body = _response(user, f"/api/resources/{new_kb}")
        except httpx.HTTPError as exc:
            after, body = 0, type(exc).__name__
        if before != 200 or after not in {401, 403}:
            raise ValueError(
                f"revoked session status mismatch: before={before}, after={after}, "
                f"body={body}, me_status={me_status}, me_body={me_body}"
            )
        statuses = {"before_disable": before, "after_disable": after}
        steps = [
            "created a real local user and private Knowledge Base",
            "verified the user's existing authenticated session could read its KB",
            "disabled the user through the isolated admin API",
            "verified the same session no longer had access",
        ]

    evidence = _evidence(args.scenario, {"observed_steps": steps, "http_statuses": statuses})
    output = Path(os.environ["GATE7_EVIDENCE_PATH"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
