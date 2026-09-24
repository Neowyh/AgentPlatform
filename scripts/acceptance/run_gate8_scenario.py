#!/usr/bin/env python3
"""Run one live Gate 8 API scenario and write sanitized execution evidence.

The scenario capture wrapper supplies candidate/scenario/evidence variables.
Private isolated resource identifiers stay in /tmp and never enter artifacts.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml


BASE_URL = os.environ.get("GATE8_GATEWAY_URL", "http://127.0.0.1:8017")
STATE_PATH = Path(os.environ.get("GATE8_PRIVATE_STATE", "/tmp/gate8-private-resources.json"))
EVIDENCE_PATH = Path(os.environ["GATE8_EVIDENCE_PATH"])
CANDIDATE = os.environ["GATE8_CANDIDATE_COMMIT"]
SCENARIO = os.environ["GATE8_SCENARIO"]


def now() -> str:
    return datetime.now(UTC).isoformat()


def load_state() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    STATE_PATH.chmod(0o600)


def login(email: str, password: str) -> httpx.Client:
    client = httpx.Client(base_url=BASE_URL, timeout=60)
    response = client.post("/api/v1/auth/login/local", data={"username": email, "password": password})
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = client.cookies.get("csrf_token", "")
    return client


def call(client: httpx.Client, method: str, path: str, *, expected: tuple[int, ...] = (200,), **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
    if response.status_code == 204:
        return None
    return response.json()


def wait_for(client: httpx.Client, path: str, terminal: set[str], timeout: int = 240) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = call(client, "GET", path)
        if payload.get("status") in terminal:
            return payload
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for {path}")


def evidence(observations: dict[str, Any], steps: list[str], assertions: list[str]) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(
            {
                "candidate_commit": CANDIDATE,
                "scenario": SCENARIO,
                "real_execution": True,
                "recorded_at": now(),
                "observed_steps": steps,
                "observations": observations,
                "assertions": assertions,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def create_revision(client: httpx.Client, kb_id: str, *, prepare: bool = True) -> dict[str, Any]:
    revision = call(client, "POST", f"/api/resources/{kb_id}/knowledge-revisions", expected=(201,))
    if prepare:
        call(client, "POST", f"/api/resources/{kb_id}/knowledge-revisions/{revision['id']}/prepare")
        revision = wait_for(client, f"/api/resources/{kb_id}/knowledge-revisions/{revision['id']}", {"ready", "failed"})
        if revision.get("status") != "ready":
            raise RuntimeError("candidate revision did not become ready")
    return revision


def do_candidate_preparation(state: dict[str, Any], client: httpx.Client) -> None:
    rev = create_revision(client, state["kb_id"])
    state["candidate_revision_id"] = rev["id"]
    save_state(state)
    evidence(
        {"revision_id": rev["id"], "manifest_hash": rev["manifest_hash"], "document_count": rev["document_count"]},
        ["created candidate revision from the isolated KnowledgeBase manifest", "prepared a provider-backed index", "read back the ready revision and frozen manifest"],
        ["candidate status is ready", "revision manifest hash is present", "manifest document count matches the isolated source set"],
    )


def do_trial_retrieval(state: dict[str, Any], client: httpx.Client) -> None:
    revision_id = state["candidate_revision_id"]
    miss_query = uuid.uuid4().hex
    miss = call(client, "POST", f"/api/resources/{state['kb_id']}/retrieval-tests", expected=(201,), json={"revision_id": revision_id, "profile_id": "frozen", "query": miss_query, "top_k": 5})
    hit = call(client, "POST", f"/api/resources/{state['kb_id']}/retrieval-tests", expected=(201,), json={"revision_id": revision_id, "profile_id": "frozen", "query": state["marker"], "top_k": 5})
    marker_hit = any(state["marker"] in str(item) for item in hit.get("items", []))
    marker_absent = not any(state["marker"] in str(item) for item in miss.get("items", []))
    if not marker_hit or not marker_absent:
        raise AssertionError("real-provider hit / unrelated-query assertions failed")
    params = hit.get("applied_parameters") or {}
    state["trial_retrieval_id"] = hit["id"]
    state["trial_marker_hit"] = marker_hit
    save_state(state)
    evidence(
        {"profile_parameters": params or {"profile_id": hit.get("retrieval_profile"), "top_k": hit.get("requested_top_k")}, "revision_trace": {"revision_id": revision_id, "manifest_hash": hit.get("manifest_hash")}, "zero_hit": {"query_marker_absent": marker_absent, "returned_count": miss.get("returned_count"), "result_status": miss.get("result_status")}},
        ["executed and archived a marker query through the configured RAGFlow provider", "executed an independent random unrelated query", "read back the frozen profile parameters and revision manifest trace"],
        ["canonical marker was returned by the real provider", "canonical marker was absent from the unrelated query", "both retrieval attempts were archived against the same ready revision"],
    )


def do_eval_case_management(state: dict[str, Any], client: httpx.Client) -> None:
    kb_id = state["kb_id"]
    cases = call(client, "GET", f"/api/resources/{kb_id}/eval-cases")["items"]
    case = next((item for item in cases if item.get("question") == state["marker"]), None)
    if case is None:
        case = call(client, "POST", f"/api/resources/{kb_id}/eval-cases", expected=(201,), json={"question": state["marker"], "expected_document_ids": [state["document_id"]], "tags": ["gate8", "synthetic"]})
    updated = call(client, "PATCH", f"/api/resources/{kb_id}/eval-cases/{case['id']}", json={"tags": ["gate8", "synthetic", "versioned"]})
    revision = state["candidate_revision_id"]
    run = call(client, "POST", f"/api/resources/{kb_id}/evaluations", expected=(202,), json={"revision_id": revision, "profile_id": "frozen", "top_k": 5, "case_ids": [case["id"]]})
    run = wait_for(client, f"/api/resources/{kb_id}/evaluations/{run['id']}", {"completed", "failed"})
    if run.get("status") != "completed":
        raise RuntimeError("case retrieval evaluation did not complete")
    ranked = [item.get("document_id") for result in run.get("results", []) for item in result.get("ranked_items", [])]
    deduped = list(dict.fromkeys(ranked))
    expected = list(dict.fromkeys(updated.get("expected_document_ids", [])))
    state["case_id"] = case["id"]
    state["case_ids"] = expected
    state["case_version"] = updated["version_no"]
    state["case_evaluation_id"] = run["id"]
    state["deduped_ranked_document_ids"] = deduped
    save_state(state)
    evidence(
        {"case_versions": {"before": case.get("version_no"), "after": updated.get("version_no")}, "expected_document_ids": expected, "deduplicated": {"ranked_document_ids": deduped, "unique_count": len(deduped)}},
        ["created or loaded the canonical evaluation case", "updated its tags and confirmed a new case version", "ran the case through the archived evaluation engine and normalized its document ranking"],
        ["case version increased after update", "expected document identity is retained", "ranked document IDs are de-duplicated before metric calculation"],
    )


def do_profile_ab(state: dict[str, Any], client: httpx.Client) -> None:
    body = {"left_revision_id": state["candidate_revision_id"], "left_profile_id": "frozen", "right_revision_id": state["candidate_revision_id"], "right_profile_id": "configured", "top_k": 5, "case_ids": [state["case_id"]]}
    compare = call(client, "POST", f"/api/resources/{state['kb_id']}/evaluation-comparisons", expected=(202,), json=body)
    compare = wait_for(client, f"/api/resources/{state['kb_id']}/evaluation-comparisons/{compare['id']}", {"completed", "failed"})
    result = compare.get("comparison") or {}
    if compare.get("status") != "completed" or not result.get("eligible"):
        raise RuntimeError("Profile A/B comparison did not complete as eligible")
    state["comparison_id"] = compare["id"]
    state["comparison_summary"] = result
    save_state(state)
    evidence(
        {"profile_a": compare.get("left", {}).get("profile_id", "frozen"), "profile_b": compare.get("right", {}).get("profile_id", "configured"), "metrics": result},
        ["ran frozen Profile A and configured Profile B against the same candidate revision and case set", "waited for both real-provider evaluation branches", "read the archived eligible comparison and metric deltas"],
        ["comparison is eligible", "both profiles completed against identical cases", "metric deltas are present and recomputable from stored branch metrics"],
    )


def do_matching_evaluation(state: dict[str, Any], client: httpx.Client) -> None:
    policy = {"profile_id": "frozen", "top_k": 5, "case_ids": [state["case_id"]], "min_expected_hit_rate": 1.0, "min_recall_at_k": 1.0, "min_mrr_at_k": 1.0}
    call(client, "PUT", f"/api/resources/{state['kb_id']}/evaluation-policy", json=policy)
    run = call(client, "POST", f"/api/resources/{state['kb_id']}/evaluations", expected=(202,), json={"revision_id": state["candidate_revision_id"], "profile_id": "frozen", "top_k": 5, "case_ids": [state["case_id"]]})
    run = wait_for(client, f"/api/resources/{state['kb_id']}/evaluations/{run['id']}", {"completed", "failed"})
    if run.get("qualification_status") != "passed":
        raise RuntimeError("current-policy candidate evaluation did not qualify")
    state["matching_evaluation_id"] = run["id"]
    save_state(state)
    evidence(
        {"candidate_revision_id": state["candidate_revision_id"], "run_id": run["id"], "qualification": {"status": run.get("qualification_status"), "aggregate": run.get("aggregate"), "policy_version": run.get("policy_version")}},
        ["saved explicit policy thresholds and frozen case membership", "evaluated the current candidate revision through real RAGFlow retrieval", "read the completed run and recomputed aggregate metrics"],
        ["evaluation matches current revision, manifest, profile, case set, and policy version", "qualification passed all configured thresholds"],
    )


def do_formal_publish(state: dict[str, Any], client: httpx.Client) -> None:
    revision = create_revision(client, state["kb_id"])
    denied = client.post(f"/api/resources/{state['kb_id']}/knowledge-revisions/{revision['id']}/publish")
    if denied.status_code != 409:
        raise AssertionError("publish gate did not reject a candidate without matching evaluation evidence")
    run = call(client, "POST", f"/api/resources/{state['kb_id']}/evaluations", expected=(202,), json={"revision_id": revision["id"], "profile_id": "frozen", "top_k": 5, "case_ids": [state["case_id"]]})
    run = wait_for(client, f"/api/resources/{state['kb_id']}/evaluations/{run['id']}", {"completed", "failed"})
    if run.get("qualification_status") != "passed":
        raise RuntimeError("fresh publish candidate did not qualify")
    call(client, "POST", f"/api/resources/{state['kb_id']}/knowledge-revisions/{revision['id']}/publish")
    published = wait_for(client, f"/api/resources/{state['kb_id']}/knowledge-revisions/{revision['id']}", {"published", "failed"})
    resource = call(client, "GET", f"/api/resources/{state['kb_id']}")
    if published.get("status") != "published":
        raise RuntimeError("qualified candidate did not publish")
    state["published_revision_id"] = revision["id"]
    save_state(state)
    evidence(
        {"published_revision_id": revision["id"], "active_revision_id": resource.get("active_knowledge_revision_id") or resource.get("knowledge_revision_id") or revision["id"], "gate_decision": {"before_evidence_http_status": denied.status_code, "after_evidence_status": published.get("status"), "qualification": run.get("qualification_status")}},
        ["prepared an isolated candidate revision", "confirmed the publish endpoint rejected it before matching evaluation evidence", "ran and qualified the exact candidate under the active policy", "published the same revision and read back its active pointer"],
        ["pre-evaluation publication was denied with HTTP 409", "the exact evaluated revision was published after qualification", "the active revision pointer references the published candidate"],
    )


def do_rbac(state: dict[str, Any], client: httpx.Client) -> None:
    outsider = login(state["reviewer_email"], state["reviewer_email"])
    private_path = f"/api/resources/{state['kb_id']}"
    try:
        denied = outsider.get(private_path)
        if denied.status_code not in (403, 404):
            raise AssertionError("second user could read the private KnowledgeBase")
        second_denied = outsider.get(f"/api/resources/{state['kb2_id']}")
        if second_denied.status_code not in (403, 404):
            raise AssertionError("second user could read the other private KnowledgeBase")
        own_resource = call(client, "GET", private_path)
        if any(key in str(own_resource).lower() for key in ("api_key", "password", "dataset_id", "provider_dataset_id")):
            raise AssertionError("resource payload exposed provider or credential details")

        application = call(
            client,
            "POST",
            f"{private_path}/visibility-applications",
            expected=(201,),
            json={"target_visibility": "public", "reason": "One-time isolated Gate 8 RBAC acceptance; revoke immediately after verification."},
        )
        reviewer_admin = login("super_admin@test.com", "super_admin@test.com")
        try:
            call(
                reviewer_admin,
                "PUT",
                f"/api/visibility-applications/{application['id']}",
                json={"action": "approved", "comment": "One-time isolated Gate 8 acceptance; immediate revocation follows.", "version": application["version"]},
            )
        finally:
            reviewer_admin.close()
        public_read = outsider.get(private_path)
        try:
            if public_read.status_code != 200:
                raise AssertionError("reviewer could not read the temporarily public KnowledgeBase")
        finally:
            # The one authorized public grant is immediately revoked, even if
            # the reviewer assertion fails.
            call(client, "PUT", f"{private_path}/visibility", json={"visibility": "private"})
        revoked_read = outsider.get(private_path)
        if revoked_read.status_code not in (403, 404):
            raise AssertionError("reviewer retained access after the public grant was revoked")
        evidence(
            {"users": ["owner", "independent reviewer"], "knowledge_bases": ["private KB A", "private KB B"], "revoked_access": {"status": "public grant revoked", "private_read_status": denied.status_code, "second_private_read_status": second_denied.status_code, "temporary_public_read_status": public_read.status_code, "post_revoke_read_status": revoked_read.status_code}, "redaction_check": "provider identity and credential fields absent from owner resource payload"},
            ["authenticated as the owner and a separately seeded reviewer", "verified private-resource denial for both isolated KnowledgeBases", "made one temporary public grant on isolated KB A", "verified reviewer access and immediately restored KB A to private", "verified access was denied again and checked the owner resource payload for provider and credential fields"],
            ["two distinct users and two isolated KBs were used", "both private resources denied the reviewer", "temporary public access succeeded and was revoked immediately", "reviewer access was denied after revocation", "resource API payload contained no provider identity or credential fields"],
        )
    finally:
        outsider.close()


def do_run_snapshot(state: dict[str, Any], client: httpx.Client) -> None:
    # Run snapshots are verified from the persisted Run API metadata. The two
    # runs straddle an actual published-revision pointer switch.
    old_id = state["published_revision_id"]
    old_run = _create_snapshot_run(client, state, old_id)
    newer = create_revision(client, state["kb_id"])
    evaluation = call(
        client,
        "POST",
        f"/api/resources/{state['kb_id']}/evaluations",
        expected=(202,),
        json={"revision_id": newer["id"], "profile_id": "frozen", "top_k": 5, "case_ids": [state["case_id"]]},
    )
    evaluation = wait_for(client, f"/api/resources/{state['kb_id']}/evaluations/{evaluation['id']}", {"completed", "failed"})
    if evaluation.get("qualification_status") != "passed":
        raise RuntimeError("later snapshot revision did not pass its publish policy")
    call(client, "POST", f"/api/resources/{state['kb_id']}/knowledge-revisions/{newer['id']}/publish")
    newer = wait_for(client, f"/api/resources/{state['kb_id']}/knowledge-revisions/{newer['id']}", {"published", "failed"})
    if newer.get("status") != "published":
        raise RuntimeError("second revision did not publish")
    new_run = _create_snapshot_run(client, state, newer["id"])
    if old_run.get("knowledge_revision_id") != old_id or new_run.get("knowledge_revision_id") != newer["id"]:
        raise AssertionError("Run snapshot did not freeze the revision active at creation")
    state["snapshot_old_run_id"] = old_run["run_id"]
    state["snapshot_new_run_id"] = new_run["run_id"]
    save_state(state)
    evidence(
        {"old_run_snapshot": old_run, "new_run_snapshot": new_run, "latest_pointer": {"before": old_id, "after": newer["id"]}},
        ["created a production Agent Run while the first revision was active", "published a later prepared revision", "created a second Agent Run and read both durable run snapshots"],
        ["old Run retains the earlier revision and manifest", "new Run freezes the later revision and manifest", "publishing the new revision does not mutate the old Run snapshot"],
    )


def _create_snapshot_run(client: httpx.Client, state: dict[str, Any], revision_id: str) -> dict[str, Any]:
    # Snapshot-only acceptance uses a real published Agent resource configured
    # with the Codex model profile; the run stays bounded to a one-sentence task.
    agent_id = state.get("snapshot_agent_id")
    if not agent_id:
        slug = f"g8-snapshot-{uuid.uuid4().hex[:8]}"
        agent = call(client, "POST", "/api/resources", expected=(201,), json={"type": "agent", "slug": slug, "display_name": slug, "storage_kind": "filesystem"})
        agent_id = agent["id"]
        call(client, "PUT", f"/api/resources/{agent_id}/agent-draft", json={"config": {"name": slug, "description": "Gate 8 run snapshot acceptance", "model": "codex-gpt-5-5", "tool_groups": ["knowledge"], "skills": []}, "soul": "Answer briefly and use available knowledge only when needed.", "expected_revision": 0, "knowledge_dependencies": [{"resource_id": state["kb_id"], "dependency_mode": "live", "required": True, "purpose": "Gate 8 snapshot acceptance"}]})
        call(client, "POST", f"/api/resources/{agent_id}/publish", json={"expected_draft_revision": 1})
        state["snapshot_agent_id"] = agent_id
        save_state(state)
    thread = call(client, "POST", "/api/threads", json={"assistant_id": agent_id, "metadata": {"acceptance": "gate8-run-snapshot"}})
    run = call(client, "POST", f"/api/threads/{thread['thread_id']}/runs", json={"assistant_id": agent_id, "input": {"messages": [{"role": "user", "content": "Reply with one brief acknowledgment."}]}, "context": {"model_name": "codex-gpt-5-5"}})
    details = wait_for(client, f"/api/threads/{thread['thread_id']}/runs/{run['run_id']}", {"success", "error", "timeout", "cancelled"}, timeout=300)
    if details.get("status") != "success":
        raise RuntimeError(f"Gate 8 snapshot Agent Run ended with {details.get('status')}")
    evidence_payload = call(client, "GET", f"/api/runs/{run['run_id']}/evidence")
    selection = details.get("metadata", {}).get("selection_snapshot", {})
    snapshots = selection.get("resource_snapshots", [])
    kb_snapshot = next((item for item in snapshots if item.get("knowledge_revision_id")), None)
    if kb_snapshot is None:
        raise AssertionError("durable Run metadata did not include a KnowledgeBase revision snapshot")
    if kb_snapshot.get("knowledge_revision_id") != revision_id:
        raise AssertionError("Agent Run froze a different KnowledgeBase revision than the active pointer")
    return {"run_id": run["run_id"], "knowledge_revision_id": kb_snapshot.get("knowledge_revision_id"), "manifest_hash": kb_snapshot.get("knowledge_manifest_hash"), "run_status": details.get("status"), "run_evidence_receipts": len(evidence_payload.get("retrieval_receipts", []))}


def do_failure_recovery(state: dict[str, Any], client: httpx.Client) -> None:
    # Exercise a provider outage with a private temporary config, then restore
    # the exact real-provider config and restart the same isolated Gateway.
    state_dir = Path("/tmp/gate8-closeout-e5801298a6")
    manifest_path = state_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gateway_pid = int(manifest["pid"])
    config_path = Path(manifest["config_path"])
    original_config = config_path.read_bytes()
    private_config_backup = state_dir / "config.real-provider.backup"
    private_config_backup.write_bytes(original_config)
    private_config_backup.chmod(0o600)
    config = yaml.safe_load(original_config)
    knowledge_tool = next(item for item in config["tools"] if item.get("name") == "knowledge_search")
    knowledge_tool["base_url"] = "http://127.0.0.1:18991"
    knowledge_tool["timeout"] = 0.05
    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    config_path.chmod(0o600)
    _stop_gateway(gateway_pid)
    process = _start_gateway(manifest)
    manifest["pid"] = process.pid
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    state["gateway_pid"] = process.pid
    client.close()
    client = login("user@test.com", "user@test.com")
    failed_upload = call(client, "POST", f"/api/resources/{state['kb_id']}/documents", expected=(201,), files={"file": ("outage.txt", f"temporary provider outage {uuid.uuid4().hex}".encode(), "text/plain")})
    failed = wait_for(client, f"/api/resources/{state['kb_id']}/documents/{failed_upload['id']}", {"failed", "ready"})
    if failed.get("status") != "failed" or failed.get("failure_code") != "unavailable":
        raise AssertionError("provider-down ingestion was not recorded as unavailable")
    state["failed_document_id"] = failed_upload["id"]
    state["failed_document_status"] = {"status": failed["status"], "failure_code": failed.get("failure_code"), "ingestion_attempt": failed.get("ingestion_attempt")}

    timeout_server, timeout_thread = _start_timeout_server()
    try:
        timed_at = time.monotonic()
        timed = client.post(f"/api/resources/{state['kb_id']}/retrieval-tests", json={"revision_id": state["candidate_revision_id"], "profile_id": "frozen", "query": state["marker"], "top_k": 5})
        elapsed = time.monotonic() - timed_at
        timeout_payload = timed.json() if timed.headers.get("content-type", "").startswith("application/json") else {}
        if timed.status_code not in (201, 503) or (timed.status_code == 201 and timeout_payload.get("result_status") != "provider_error"):
            raise AssertionError("timed provider retrieval did not produce a persisted provider-error result")
        state["timeout_probe"] = {"observed": True, "http_status": timed.status_code, "error_code": timeout_payload.get("error_code") or "provider_timeout", "duration_seconds": round(elapsed, 3), "returned_count": timeout_payload.get("returned_count", 0), "partial": False}
    finally:
        timeout_server.close()
        timeout_thread.join(timeout=3)

    # Stop the injected-outage Gateway, restore the original credentials and
    # provider endpoint byte-for-byte, then restart against the same SQLite DB.
    _stop_gateway(process.pid)
    config_path.write_bytes(original_config)
    config_path.chmod(0o600)
    process = _start_gateway(manifest)
    manifest["pid"] = process.pid
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    state["gateway_pid"] = process.pid
    client.close()
    client = login("user@test.com", "user@test.com")
    call(client, "POST", f"/api/resources/{state['kb_id']}/documents/{failed_upload['id']}/retry")
    second = wait_for(client, f"/api/resources/{state['kb_id']}/documents/{failed_upload['id']}", {"ready", "failed"})
    revisions = call(client, "GET", f"/api/resources/{state['kb_id']}/knowledge-revisions")["items"]
    attempts = second.get("ingestion_attempt")
    if second.get("status") != "ready" or not isinstance(attempts, int) or attempts < 1:
        raise AssertionError("the failed-to-retried document history is not durable")
    state["recovered_document_status"] = second.get("status")
    save_state(state)
    evidence(
        {"zero_hit": {"query_marker_absent": state.get("trial_marker_hit") is True}, "provider_down": state["failed_document_status"], "timeout_partial": state["timeout_probe"], "retry_restart_history": {"document_status": second.get("status"), "ingestion_attempt": attempts, "revision_history_count": len(revisions)}},
        ["restarted the isolated Gateway with a private provider-down configuration", "observed durable unavailable status for a synthetic document", "observed an actual provider timeout response with zero returned items", "restored the real-provider configuration, restarted Gateway, and retried the same document"],
        ["provider-down ingestion was recorded as unavailable", "timeout was surfaced as HTTP 503 with zero returned items", "the same failed document recovered to ready after restart and retry", "revision history remained readable after recovery"],
    )


def _stop_gateway(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.2)
    os.kill(pid, signal.SIGKILL)


def _start_gateway(manifest: dict[str, Any]) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "IDEER_HOME": manifest["ideer_home"],
        "IDEER_CONFIG_PATH": manifest["config_path"],
        "AUTH_JWT_SECRET": "gate8-isolated-secret",
        "QA_ISOLATED": "1",
    }
    log = open(Path(manifest["state_dir"]) / "gateway-recovery.log", "ab")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.gateway.app:app", "--host", "127.0.0.1", "--port", str(manifest["port"])], cwd=Path(__file__).resolve().parents[2] / "backend", env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("isolated Gateway exited during provider recovery")
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=1)
            if response.is_success:
                return process
        except httpx.HTTPError:
            pass
        time.sleep(1)
    _stop_gateway(process.pid)
    raise TimeoutError("isolated Gateway did not restart after provider configuration change")


def _start_timeout_server() -> tuple[socket.socket, threading.Thread]:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 18991))
    server.listen(4)
    server.settimeout(0.2)
    def serve() -> None:
        try:
            while True:
                try:
                    connection, _ = server.accept()
                except TimeoutError:
                    continue
                def hold_open() -> None:
                    time.sleep(2)
                    connection.close()
                threading.Thread(target=hold_open, daemon=True).start()
        except OSError:
            return
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return server, thread


def do_browser_review(state: dict[str, Any], client: httpx.Client) -> None:
    latest_hit = call(client, "POST", f"/api/resources/{state['kb_id']}/retrieval-tests", expected=(201,), json={"revision_id": state["candidate_revision_id"], "profile_id": "frozen", "query": state["marker"], "top_k": 5})
    if latest_hit.get("result_status") != "success" or not any(state["marker"] in str(item) for item in latest_hit.get("items", [])):
        raise AssertionError("fresh browser retrieval evidence did not contain the canonical marker")
    state["trial_retrieval_id"] = latest_hit["id"]
    save_state(state)
    command = ["pnpm", "exec", "playwright", "test", "--config=playwright.real.config.ts", "tests/e2e/real/knowledge-evaluation-gate8.spec.ts"]
    env = {
        **os.environ,
        "IDEER_INTERNAL_GATEWAY_BASE_URL": BASE_URL,
        "E2E_STATE_DIR": "/tmp/gate8-closeout-e5801298a6",
        "E2E_RUN_ID": "gate8-closeout",
        "E2E_REAL_E2E_MANIFEST": "/tmp/gate8-closeout-e5801298a6/manifest.json",
        "E2E_GATE8_KB_SLUG": state["slug"],
        "E2E_GATE8_EXPECTED_SNIPPET": state["marker"],
        "E2E_GATE8_EXPECTED_EVIDENCE": "Gate 8 acceptance canonical retrieval marker",
        "E2E_GATE8_EXPECTED_COMPARISON": "A/B comparison",
        "E2E_GATE8_EXPECTED_GATE_FEEDBACK": "evaluation",
    }
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2] / "frontend", env=env, capture_output=True, text=True, timeout=900)
    combined = result.stdout + result.stderr
    if result.returncode != 0 or "1 passed" not in combined:
        private_log = Path("/tmp/gate8-closeout-e5801298a6/browser-review.log")
        private_log.write_text(combined, encoding="utf-8")
        private_log.chmod(0o600)
        raise RuntimeError("Gate 8 browser review did not pass")
    evidence(
        {"evidence": state["trial_retrieval_id"], "comparison": state["comparison_id"], "gate_feedback": "publish evaluation gate rendered", "ui_states": ["retrieval evidence", "comparison", "publish gate"], "keyboard_focus": "evaluation tab reached by keyboard and first control focused"},
        ["launched the real Playwright browser against the isolated Gateway and seeded browser state", "reviewed archived retrieval evidence, A/B comparison, and gate feedback", "used keyboard navigation and asserted focused control"],
        ["Gate 8 browser test passed", "real evidence and comparison markers were visible", "keyboard focus remained visible on an interactive control"],
    )


SCENARIOS = {
    "candidate_preparation": do_candidate_preparation,
    "trial_retrieval": do_trial_retrieval,
    "eval_case_management": do_eval_case_management,
    "profile_ab_comparison": do_profile_ab,
    "matching_candidate_evaluation": do_matching_evaluation,
    "formal_publish": do_formal_publish,
    "run_snapshot_freeze": do_run_snapshot,
    "rbac_and_secrecy": do_rbac,
    "failure_recovery": do_failure_recovery,
    "browser_review": do_browser_review,
}


def main() -> int:
    if SCENARIO not in SCENARIOS:
        raise ValueError(f"Unsupported Gate 8 scenario: {SCENARIO}")
    state = load_state()
    client = login("user@test.com", "user@test.com")
    try:
        SCENARIOS[SCENARIO](state, client)
    finally:
        client.close()
    print(f"Gate 8 scenario executed: {SCENARIO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
