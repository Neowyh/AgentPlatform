"""Source for the one-off Gate 8 snapshot probe; run from the repository root.

The probe preserves its isolated /tmp state for diagnosis. Remove its generated
RAGFlow datasets and that state after recording evidence.
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

ROOT = Path.cwd()
state = Path(tempfile.mkdtemp(prefix="gate8-targeted-", dir="/tmp"))
source = yaml.safe_load((ROOT / "config.yaml").read_text())
codex = next(x for x in source["models"] if x.get("name") == "codex-gpt-5-5")
ragflow = next(x for x in source["tools"] if x.get("name") == "knowledge_search")
config = {
    "log_level": "info",
    "models": [codex],
    "tool_groups": [{"name": "knowledge"}],
    "tools": [ragflow],
    "sandbox": {"use": "deerflow.sandbox.local:LocalSandboxProvider"},
    "agents_api": {"enabled": True},
    "database": {"backend": "sqlite", "sqlite_dir": str(state / "sqlite")},
}
(state / "sqlite").mkdir()
config_path = state / "config.yaml"
config_path.write_text(yaml.safe_dump(config, allow_unicode=True))
config_path.chmod(0o600)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
base = f"http://127.0.0.1:{port}"
log = (state / "gateway.log").open("wb")
env = {
    **os.environ,
    "IDEER_HOME": str(state),
    "IDEER_CONFIG_PATH": str(config_path),
    "AUTH_JWT_SECRET": "gate8-targeted-secret",
    "QA_ISOLATED": "1",
}
process = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "app.gateway.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ],
    cwd=ROOT / "backend",
    env=env,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
(state / "manifest.json").write_text(
    json.dumps({"pid": process.pid, "port": port, "state_dir": str(state)})
)
print("state", state, "pid", process.pid, flush=True)
client = httpx.Client(base_url=base, timeout=60)


def call(method, path, expected=(200,), **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(f"{method} {path.split('?')[0]} HTTP {response.status_code}")
    return response.json() if response.status_code != 204 else None


def poll(path, statuses, seconds=240):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        result = call("GET", path)
        if result.get("status") in statuses:
            return result
        time.sleep(2)
    raise TimeoutError(f"poll {path} after {seconds}s")


try:
    for _ in range(90):
        if process.poll() is not None:
            raise RuntimeError("gateway exited during startup")
        try:
            if client.get("/health", timeout=1).is_success:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        raise TimeoutError("gateway startup")
    print("gateway_ready", flush=True)
    call(
        "POST",
        "/api/v1/auth/initialize",
        expected=(201,),
        json={"email": "super_admin@test.com", "password": "super_admin@test.com"},
    )
    call(
        "POST",
        "/api/v1/auth/login/local",
        data={"username": "super_admin@test.com", "password": "super_admin@test.com"},
    )
    client.headers["X-CSRF-Token"] = client.cookies.get("csrf_token", "")
    dept = call(
        "POST",
        "/api/admin/departments",
        json={"name": "Gate 8 Targeted", "description": "Isolated"},
    )
    call(
        "POST",
        "/api/admin/users",
        expected=(201,),
        json={
            "email": "user@test.com",
            "password": "user@test.com",
            "username": "user@test.com",
            "role": "user",
            "department_id": dept["id"],
        },
    )
    client.cookies.clear()
    call(
        "POST",
        "/api/v1/auth/login/local",
        data={"username": "user@test.com", "password": "user@test.com"},
    )
    client.headers["X-CSRF-Token"] = client.cookies.get("csrf_token", "")
    slug = f"g8-targeted-{uuid.uuid4().hex[:8]}"
    kb = call(
        "POST",
        "/api/resources",
        expected=(201,),
        json={
            "type": "knowledge_base",
            "slug": slug,
            "display_name": slug,
            "storage_kind": "database",
        },
    )
    kb_id = kb["id"]
    print("kb_created", flush=True)
    call("POST", f"/api/resources/{kb_id}/knowledge/initialize", expected=(202,))
    marker = f"gate8-targeted-{uuid.uuid4().hex}"
    doc = call(
        "POST",
        f"/api/resources/{kb_id}/documents",
        expected=(201,),
        files={
            "file": (
                "evidence.txt",
                f"Gate 8 targeted canonical marker {marker}".encode(),
                "text/plain",
            )
        },
    )
    for _ in range(120):
        item = call("GET", f"/api/resources/{kb_id}/documents/{doc['id']}")
        if item.get("status") in ("ready", "failed"):
            print("document_status", item.get("status"), flush=True)
            if item.get("status") != "ready":
                raise RuntimeError(f"document ingestion {item.get('status')}")
            break
        time.sleep(2)
    else:
        raise TimeoutError("document ingestion")
    case = call(
        "POST",
        f"/api/resources/{kb_id}/eval-cases",
        expected=(201,),
        json={
            "question": marker,
            "expected_document_ids": [doc["id"]],
            "tags": ["gate8", "targeted"],
        },
    )
    call(
        "PUT",
        f"/api/resources/{kb_id}/evaluation-policy",
        json={
            "profile_id": "frozen",
            "top_k": 5,
            "case_ids": [case["id"]],
            "min_expected_hit_rate": 1.0,
            "min_recall_at_k": 1.0,
            "min_mrr_at_k": 1.0,
        },
    )

    def publish_revision():
        revision = call(
            "POST", f"/api/resources/{kb_id}/knowledge-revisions", expected=(201,)
        )
        call(
            "POST",
            f"/api/resources/{kb_id}/knowledge-revisions/{revision['id']}/prepare",
        )
        prepared = poll(
            f"/api/resources/{kb_id}/knowledge-revisions/{revision['id']}",
            {"ready", "failed"},
        )
        print("revision_prepare", prepared["status"], flush=True)
        if prepared["status"] != "ready":
            raise RuntimeError("revision prepare failed")
        evaluation = call(
            "POST",
            f"/api/resources/{kb_id}/evaluations",
            expected=(202,),
            json={
                "revision_id": revision["id"],
                "profile_id": "frozen",
                "top_k": 5,
                "case_ids": [case["id"]],
            },
        )
        evaluation = poll(
            f"/api/resources/{kb_id}/evaluations/{evaluation['id']}",
            {"completed", "failed"},
        )
        print(
            "revision_qualification", evaluation.get("qualification_status"), flush=True
        )
        if evaluation.get("qualification_status") != "passed":
            raise RuntimeError("evaluation did not qualify")
        call(
            "POST",
            f"/api/resources/{kb_id}/knowledge-revisions/{revision['id']}/publish",
        )
        published = poll(
            f"/api/resources/{kb_id}/knowledge-revisions/{revision['id']}",
            {"published", "failed"},
        )
        if published["status"] != "published":
            raise RuntimeError("publish failed")
        return revision["id"]

    old_revision = publish_revision()
    agent_slug = f"g8-snapshot-{uuid.uuid4().hex[:8]}"
    agent = call(
        "POST",
        "/api/resources",
        expected=(201,),
        json={
            "type": "agent",
            "slug": agent_slug,
            "display_name": agent_slug,
            "storage_kind": "filesystem",
        },
    )
    agent_id = agent["id"]
    call(
        "PUT",
        f"/api/resources/{agent_id}/agent-draft",
        json={
            "config": {
                "name": agent_slug,
                "description": "Gate 8 targeted snapshot",
                "model": "codex-gpt-5-5",
                "tool_groups": ["knowledge"],
                "skills": [],
            },
            "soul": "Answer briefly and use available knowledge only when needed.",
            "expected_revision": 0,
            "knowledge_dependencies": [
                {
                    "resource_id": kb_id,
                    "dependency_mode": "live",
                    "required": True,
                    "purpose": "Gate 8 snapshot acceptance",
                }
            ],
        },
    )
    call(
        "POST",
        f"/api/resources/{agent_id}/publish",
        json={"expected_draft_revision": 1},
    )

    def run(expected_revision):
        thread = call(
            "POST",
            "/api/threads",
            json={
                "assistant_id": agent_id,
                "metadata": {"acceptance": "gate8-targeted"},
            },
        )
        created = call(
            "POST",
            f"/api/threads/{thread['thread_id']}/runs",
            json={
                "assistant_id": agent_id,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Reply with one brief acknowledgment.",
                        }
                    ]
                },
                "context": {"model_name": "codex-gpt-5-5"},
            },
        )
        result = poll(
            f"/api/threads/{thread['thread_id']}/runs/{created['run_id']}",
            {"success", "error", "timeout", "cancelled"},
            seconds=300,
        )
        selection = result.get("metadata", {}).get("selection_snapshot", {})
        snap = next(
            (
                s
                for s in selection.get("resource_snapshots", [])
                if s.get("knowledge_revision_id")
            ),
            {},
        )
        with sqlite3.connect(state / "sqlite" / "deerflow.db") as db:
            error = db.execute(
                "SELECT error FROM runs WHERE run_id = ?", (created["run_id"],)
            ).fetchone()
        entry = {
            "status": result["status"],
            "revision_match": snap.get("knowledge_revision_id") == expected_revision,
            "manifest_present": bool(snap.get("knowledge_manifest_hash")),
            "error_present": bool(error and error[0]),
            "run_id": created["run_id"],
        }
        (state / f"run-{expected_revision}.json").write_text(json.dumps(entry))
        print(
            "run_result",
            json.dumps({k: v for k, v in entry.items() if k != "run_id"}),
            flush=True,
        )
        if error and error[0]:
            (state / f"error-{expected_revision}.txt").write_text(error[0])
        return entry

    old = run(old_revision)
    new_revision = publish_revision()
    new = run(new_revision)
    result = {
        "candidate_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "old": old,
        "new": new,
        "different_revisions": old_revision != new_revision,
    }
    (state / "result.json").write_text(json.dumps(result, indent=2))
    print(
        "targeted_verdict",
        all(
            (
                old["status"] == "success",
                new["status"] == "success",
                old["revision_match"],
                new["revision_match"],
                result["different_revisions"],
            )
        ),
        flush=True,
    )
finally:
    client.close()
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    log.close()
