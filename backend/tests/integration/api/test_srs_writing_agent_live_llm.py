"""Real-LLM end-to-end acceptance for the ``srs-writing`` agent (ticket 08).

Drives the bundled ``srs-writing`` Agent through the real FastAPI gateway
(real model, real sandbox, real persistence — nothing in the flow is mocked)
across the six fixed SKILL phases:

    task_book_parsing -> requirement_analysis -> interactive_confirmation
    -> matrix_generation -> document_generation -> review

Driving style mirrors ``tests/integration/api/test_shared_resource_run_e2e.py``:
register a user, seed the bundled resources (agent + skill) from the repo
manifest, install the bundled Skill for the running user (the sandbox
``/mnt/skills`` projection reads the file-based user skill storage), create a
thread, upload a task book, then POST scripted user turns to
``/api/threads/{id}/runs/stream`` and drain the SSE transcript until ``end``.
``ask_clarification`` cards end a run (``ClarificationMiddleware`` returns
``Command(goto=END)`` with a ``human_input`` artifact); the next scripted
message is the user's card answer, so the same text/option decision semantics
apply. The sandbox is the container AIO provider — the deployment shape
``config.intranet.yaml`` uses for this agent — because a restricted-skill
Agent on ``LocalSandboxProvider`` cannot have host bash (officecli) and
per-Agent skill isolation at the same time.

Scripted conversation: turn 1 starts the flow on a minimal inline task book;
every later turn sends one comprehensive decision reply — "confirm the mapping
with the task-book chapter numbering (F-4.1 / F-4.2), accept all candidate
requirements except reject the cloud-upload requirement (classified
environment, no internet), keep progress.json on the SKILL.md/validator
contract" — which is valid at any decision point (mapping confirmation,
per-item confirmation, batch confirmation). The steering only restates the
SKILL.md contract and the bundled validator's checks (requirement ID format
``F-<chapter>-<seq>``, ``stage`` values, ``functions``/``description``/
``source_function``/``source_chapter`` fields, the accepted/modified/rejected
status vocabulary, and the §6 review gate: run the offline validator and fix
to ALL CHECKS PASSED before present_files, falling back to the documented
equivalent self-check when the script is absent in-sandbox); it does not
relax any acceptance assertion. The task book plants exactly one rejectable
requirement (cloud upload) plus unambiguous entries, so the rejection is
deterministic.

Known product finding surfaced by this acceptance (recorded, not worked
around in product code): on the canonical frozen-Agent path the loader
rewrites ``config.skills`` from the slug to the resource UUID, while the
thread skill projection matches skills by slug name — so the sandbox
``/mnt/skills`` view ends up empty and the agent cannot read its own
SKILL.md/validator in-sandbox (dev-log/probe_skill_projection.py probes 1-3;
observed in runs 6-8). The flow therefore runs on the SOUL plus the scripted
contract restatement, and the review-gate steering accepts the documented
equivalent self-check when the validator script is absent in-sandbox. The
host-side validator assertions below are unaffected.

Because one turn may legally advance through several phases before ending on
a clarification card, the turn loop watches ``progress.json`` from a
background poller while the SSE stream drains, so the observed stage sequence
is the file's real phase trace rather than a per-turn snapshot.

Acceptance assertions:
  1. 阶段流转       progress.json ``stage`` respects the canonical phase order,
                    passes through the three user-gated phases, and finishes at
                    ``review``/``complete``.
  2. 进度文件更新   progress.json tracks both function items and terminal
                    decisions for every requirement (exactly one rejected).
  3. 产物生成       srs_document.docx / traceability-matrix.docx /
                    requirement-catalog.md / progress.json exist non-empty.
  4. 校验器 exit 0  the offline validator exits 0 against the host-side mount
                    of ``/mnt/user-data/outputs`` — both from the repo skill
                    package and from the frozen run-skill-view copy that run
                    preparation builds for the canonical run.
  5. 拒绝项不泄漏   the rejected requirement ID and its cloud-upload wording
                    never appear in the generated .docx bodies, while an
                    accepted ID does (positive control) and the rejection is
                    recorded in requirement-catalog.md.

Credentials: the model config comes from the repo-root ``config.yaml``
(``models:`` section). Like every other live test, the platform
``requires_llm`` gate (tests/conftest.py) skips — i.e. reports unexecuted —
when ``OPENAI_API_KEY`` is unset or ``CI`` is truthy; export it from the config
to opt in::

    cd backend && \\
    OPENAI_API_KEY="$(uv run --locked python -c "import yaml; print(yaml.safe_load(open('../config.yaml'))['models'][0]['api_key'])")" \\
    PYTHONPATH=.:tests PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \\
    UV_CACHE_DIR=/tmp/deer-flow-uv-cache \\
    uv run --locked pytest tests/integration/api/test_srs_writing_agent_live_llm.py -q -m requires_llm -s

Without a repo ``config.yaml`` the app falls back to an env-credential model
block (``OPENAI_API_KEY`` / ``OPENAI_API_BASE`` / ``E2E_MODEL_ID``), so the test
also runs on checkouts that only carry environment credentials.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import NamedTuple

import pytest
from _gateway_e2e_env import auth_user_id, create_thread, register_user
from starlette.testclient import TestClient

pytestmark = pytest.mark.requires_llm

REPO_ROOT = Path(__file__).resolve().parents[4]
AGENT_SLUG = "srs-writing"
TASKBOOK_FILENAME = "acceptance-minimal-taskbook.md"
OUTPUTS_SUBDIR = "srs-acceptance-minimal-taskbook"
REJECTED_KEYWORD = "云平台"
FUNCTION_IDS = ("F-4.1", "F-4.2")
MAX_TURNS = 8
# The document-generation turn legitimately chains hundreds of tool steps and
# took ~17 minutes against the real model (dev-log/srs-real-llm-run7.log).
TURN_TIMEOUT_S = 1500.0

STAGE_ORDER = (
    "task_book_parsing",
    "requirement_analysis",
    "interactive_confirmation",
    "matrix_generation",
    "document_generation",
    "review",
    "complete",
)
TERMINAL_REQUIREMENT_STATUSES = frozenset({"accepted", "modified", "rejected"})

# Minimal task book (2 function items) with exactly one rejectable clause
# (cloud upload, rejected by the scripted user) and unambiguous entries
# elsewhere, including a glossary term. ASCII stem keeps the SKILL.md output
# subdir rule deterministic: srs-acceptance-minimal-taskbook.
TASKBOOK_MARKDOWN = """\
# 软件任务书（验收专用·最小样例）

## 1 任务概述

研制"电池检测终端软件"（以下简称"本软件"），用于产线电池检测结果的管理，
供软件需求规格说明书编制使用。

## 2 引用文件

- GJB 438C-2021《军用软件开发文档通用要求》

## 3 术语

- 检测记录：一次电池检测产生的、包含电池编号、检测时间、内阻值与结论的结构化数据条目。

## 4 功能要求

### 4.1 检测记录管理

软件应支持检测记录的录入、查询与删除。检测记录应包含电池编号、检测时间、
内阻值与结论字段。软件应支持按电池编号精确查询检测记录。

### 4.2 数据上报

软件应支持将检测记录自动上传至互联网云平台。软件应支持检测记录的本地备份
与恢复，备份文件可手动导入还原。
"""

START_MESSAGE = (
    f"请开始处理我上传的任务书 /mnt/user-data/uploads/{TASKBOOK_FILENAME}，"
    "按 srs-writing 流程执行：先解析任务书并展示「章节 ↔ 功能项」映射表供我确认，"
    "再逐阶段推进。每个需要我决策的地方直接提问即可。"
    f"产物写入 /mnt/user-data/outputs/{OUTPUTS_SUBDIR}/ 子目录。"
    "请严格遵循 /mnt/skills/srs-writing/SKILL.md 的全部契约，特别注意："
    "功能项编号沿用任务书章节号（4.1 → F-4.1、4.2 → F-4.2）；"
    "需求 ID 用 F-<功能章节号>-<序号> 格式（如 F-4.1-1）；"
    "progress.json 用 stage 字段记录当前阶段，取值依次为 task_book_parsing、"
    "requirement_analysis、interactive_confirmation、matrix_generation、"
    "document_generation、review，全部交付完成后写 complete；"
    "功能项清单字段名必须是 functions（数组，每项含 id）；"
    "每条需求的状态取值只能是 accepted/modified/rejected（不要用 confirmed 等其他词）；"
    "每进入一个新阶段、每条需求决策后都立即更新 progress.json。"
)

# One comprehensive decision reply, valid at every decision point of the flow:
# mapping confirmation (confirm the chapter numbering), per-item/batch
# requirement confirmation ("全部采纳 + 唯一拒绝项"), and any "shall I
# continue" gate. The cloud-upload clause is the planted rejection; everything
# else is accepted. The trailing contract reminder restates SKILL.md's own
# rules and the bundled validator's checks (never weakens them): canonical
# stage field/values and ID format, the progress.json schema the validator
# reads (functions, description, source_function, source_chapter, accepted/
# modified/rejected), the no-leak rule for rejected requirements, and the
# SKILL.md §6 review gate (run the offline validator, fix to ALL CHECKS
# PASSED, only then present_files).
CONFIRM_REPLY = (
    "确认，按此继续。映射确认：功能项编号沿用任务书章节号，即 4.1 → F-4.1"
    "（检测记录管理）、4.2 → F-4.2（数据上报），需求 ID 按 F-<功能章节号>-<序号> 分配。"
    "所有候选需求全部采纳；"
    f"唯一例外：拒绝「自动上传至互联网{REJECTED_KEYWORD}」相关需求（应属 F-4.2-*），"
    "拒绝原因：涉密环境禁止接入互联网。被拒绝需求的 ID 与内容不得出现在 "
    "srs_document.docx 与 traceability-matrix.docx 正文中（矩阵如需标注缺口，"
    "以功能项编号标注，不引用被拒需求 ID）。"
    "请继续推进后续阶段，直至完成追踪矩阵、SRS 文档生成与审阅交付。"
    "文档满足 GJB438C 基本结构与样式规范即可，不要反复微调样式。"
    "progress.json 契约（必须遵守）：阶段字段名必须是 stage（取值 task_book_parsing、"
    "requirement_analysis、interactive_confirmation、matrix_generation、"
    "document_generation、review，全部交付完成后写 complete），每进入新阶段立即更新，"
    "不要使用其他字段名或取值；功能项清单字段名必须是 functions（数组，每项含 id/title）；"
    "每条需求的状态取值只能是 accepted/modified/rejected，已确认无误的写 accepted，"
    "不要写 confirmed；每条采纳/修改的需求必须含 description（需求描述）、"
    "source_function（来源功能项 ID，如 F-4.1）、source_chapter（任务书章节号，如 4.1）字段；"
    "requirement-catalog.md 的需求 ID 集合必须与 progress.json 完全一致。"
    "review 阶段的交付门禁：若沙箱内存在 /mnt/skills/srs-writing/scripts/validate_srs_outputs.py，"
    f"运行它（--outputs-dir /mnt/user-data/outputs/{OUTPUTS_SUBDIR}）并按输出逐项修复，"
    "直到校验输出 ALL CHECKS PASSED；若该脚本在沙箱中不存在（已知部署形态限制，"
    "勿反复重试读取该路径），改为逐项自检等价契约并给出结论：progress.json 的 stage 字段与取值、"
    "functions 含 F-4.1 与 F-4.2、每条需求 status ∈ accepted/modified/rejected 且 "
    "accepted/modified 需求含 description/source_function/source_chapter、"
    "requirement-catalog.md 的需求 ID 集合与 progress.json 完全一致、"
    "两份 docx 非空且不含被拒需求 ID 而 accepted ID 均出现在其中。"
    "自检完成后本轮直接 present_files 交付全部四个产物，不要再询问或等待。"
)


def _fallback_model_config_text() -> str:
    """Env-credential single-model config for checkouts without config.yaml.

    Only ``OPENAI_API_KEY`` is guaranteed here (the ``requires_llm`` gate);
    everything else defaults like the other live tests do.
    """
    from textwrap import dedent, indent

    sandbox_block = indent(_AIO_SANDBOX_BLOCK, " " * 8).rstrip()

    return dedent(
        f"""\
        log_level: info
        models:
          - name: {os.getenv("E2E_MODEL_NAME", "e2e-real-model")}
            display_name: E2E Real Model
            use: langchain_openai:ChatOpenAI
            model: {os.getenv("E2E_MODEL_ID", "gpt-4o-mini")}
            api_key: $OPENAI_API_KEY
            base_url: {os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"}
            timeout: 600.0
            max_retries: 2
{sandbox_block}
        skills:
          container_path: /mnt/skills
        agents_api:
          enabled: true
        tool_groups:
          - name: file:read
          - name: file:write
          - name: bash
          - name: document
        tools:
          - name: read_file
            group: file:read
            use: deerflow.sandbox.tools:read_file_tool
          - name: glob
            group: file:read
            use: deerflow.sandbox.tools:glob_tool
          - name: grep
            group: file:read
            use: deerflow.sandbox.tools:grep_tool
          - name: write_file
            group: file:write
            use: deerflow.sandbox.tools:write_file_tool
          - name: str_replace
            group: file:write
            use: deerflow.sandbox.tools:str_replace_tool
          - name: bash
            group: bash
            use: deerflow.sandbox.tools:bash_tool
          - name: read_document
            group: document
            use: app.agentplatform.community.doc_reader.tools:read_document_tool
        title:
          enabled: false
        memory:
          enabled: false
        summarization:
          enabled: false
        database:
          backend: sqlite
        run_events:
          backend: memory
        """
    )


# ---------------------------------------------------------------------------
# Environment staging (isolated home + the repo's real model config)
# ---------------------------------------------------------------------------

# The srs-writing Agent declares a Skill dependency, which requires a sandbox
# provider that can enforce per-Agent skill filesystem isolation, and it needs
# bash for officecli. LocalSandboxProvider cannot satisfy both (host bash
# disables its isolation advertisement by design), so the acceptance runs on
# the container AIO sandbox — the deployment shape config.intranet.yaml uses
# for this agent. officecli is injected as a read-only bind mount because the
# stock image does not carry the binary.
AIO_SANDBOX_IMAGE = "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest"

_AIO_SANDBOX_BLOCK = (
    "sandbox:\n"
    "  use: deerflow.community.aio_sandbox:AioSandboxProvider\n"
    f"  image: {AIO_SANDBOX_IMAGE}\n"
    "  allow_host_bash: false\n"
    "  bash_command_timeout: 600\n"
    "  mounts:\n"
    f"  - host_path: {REPO_ROOT / 'vendor' / 'officecli' / 'officecli'}\n"
    "    container_path: /usr/local/bin/officecli\n"
    "    read_only: true\n"
    "  environment:\n"
    "    OFFICECLI_SKIP_UPDATE: '1'\n"
)


def _stage_model_config_text() -> str:
    """Return the config.yaml text for the isolated gateway.

    Prefers the repo-root ``config.yaml`` (real credentials) with title /
    summarization / memory generation disabled so the acceptance flow does not
    pay for extra non-deterministic LLM calls, and with the sandbox section
    replaced by the container AIO provider (see ``_AIO_SANDBOX_BLOCK``). Falls
    back to an env-driven single-model block when the repo carries no real
    config.
    """
    real_config = REPO_ROOT / "config.yaml"
    if real_config.is_file():
        text = real_config.read_text(encoding="utf-8")
        for block in ("title", "summarization", "memory"):
            text = re.sub(rf"(?m)^{block}:\n  enabled: true$", f"{block}:\n  enabled: false", text, count=1)
        # Swap the sandbox provider for the AIO container sandbox (the whole
        # indented block after the top-level `sandbox:` key).
        text = re.sub(r"(?ms)^sandbox:\n(?:(?!^\S)[^\n]*\n)+", _AIO_SANDBOX_BLOCK, text, count=1)
        return text
    return _fallback_model_config_text()


def _first_model_name() -> str | None:
    """Best-effort name of the model the gateway will default to."""
    try:
        import yaml

        real_config = REPO_ROOT / "config.yaml"
        if real_config.is_file():
            models = (yaml.safe_load(real_config.read_text(encoding="utf-8")) or {}).get("models") or []
            if models and isinstance(models[0], dict) and models[0].get("name"):
                return str(models[0]["name"])
    except Exception:
        pass
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("E2E_MODEL_NAME", "e2e-real-model")
    return None


class _Gateway(NamedTuple):
    """The staged gateway app plus the handles the test needs afterwards."""

    app: object
    home: Path
    model_name: str


@pytest.fixture()
def srs_llm_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Gateway:
    """Full gateway app on an isolated DEER_FLOW_HOME with real model credentials."""
    model_name = _first_model_name()
    if not model_name:
        pytest.skip("No LLM credentials: repo config.yaml has no models and OPENAI_API_KEY is unset")

    home = tmp_path / "ideer-home"
    home.mkdir()
    monkeypatch.setenv("DEER_FLOW_HOME", str(home))
    staged_config = tmp_path / "config.yaml"
    staged_config.write_text(_stage_model_config_text(), encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_CONFIG_PATH", str(staged_config))
    staged_extensions = tmp_path / "extensions_config.json"
    staged_extensions.write_text('{"mcpServers": {}, "skills": {}}', encoding="utf-8")
    monkeypatch.setenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", str(staged_extensions))

    from _gateway_e2e_env import preserve_process_config_singletons, reset_process_singletons

    preserve_process_config_singletons(monkeypatch)
    reset_process_singletons(monkeypatch)
    # The sandbox provider caches path mappings derived from the previous
    # config/home; a fresh instance must pick up the isolated home.
    from deerflow.sandbox import sandbox_provider as sandbox_provider_module

    monkeypatch.setattr(sandbox_provider_module, "_default_sandbox_provider", None, raising=False)

    from deerflow.config import app_config as app_config_module

    cfg = app_config_module.get_app_config()
    cfg.database.sqlite_dir = str(home / "db")

    from app.gateway.app import create_app

    return _Gateway(app=create_app(), home=home, model_name=model_name)


def _seed_bundled_srs_resources(owner_id: str) -> None:
    """Provision the bundled srs-writing Agent + Skill (platform seed path)."""

    from app.agentplatform.resource_runtime import ResourceStorage, seed_bundled_resources
    from deerflow.config.paths import get_paths
    from deerflow.persistence.engine import get_session_factory

    async def _seed() -> None:
        await seed_bundled_resources(
            get_session_factory(),
            ResourceStorage(get_paths().base_dir, allow_scanned_executables=True),
            manifest_path=REPO_ROOT / "bundled-resources.json",
            source_root=REPO_ROOT,
            owner_id=owner_id,
            conflict_policy="keep",
        )

    asyncio.run(_seed())


# ---------------------------------------------------------------------------
# Gateway driving helpers (shared-resource e2e style)
# ---------------------------------------------------------------------------


def _parse_sse(transcript: str) -> list[dict]:
    events: list[dict] = []
    for block in transcript.split("\n\n"):
        lines = [line for line in block.splitlines() if line.startswith("data: ")]
        name = next((line for line in block.splitlines() if line.startswith("event: ")), None)
        if name and lines:
            events.append(
                {
                    "event": name.removeprefix("event: ").strip(),
                    "data": json.loads(lines[0].removeprefix("data: ")),
                }
            )
    return events


def _drain_stream(response, *, timeout: float) -> str:
    """Consume the SSE body until ``event: end`` or fail past the deadline.

    A turn that outlives ``timeout`` raises (never silently passes): the
    response context closes, which cancels the run (``on_disconnect=cancel``).
    """
    deadline = time.monotonic() + timeout
    body = b""
    for chunk in response.iter_bytes():
        body += chunk
        if b"event: end" in body:
            break
        if time.monotonic() >= deadline:
            raise AssertionError(f"run turn did not finish within {timeout:.0f}s; last SSE bytes: {body[-2000:].decode('utf-8', errors='replace')!r}")
    return body.decode("utf-8", errors="replace")


def _run_turn(client: TestClient, thread_id: str, csrf: str, message: str, model_name: str) -> tuple[str, dict, str | None]:
    """Post one user message as a streamed run.

    Returns ``(run_id, run record, sse error name)``. ``error_name`` is None
    unless the graph aborted with an error event — only
    ``GraphRecursionError`` (per-run step budget) is tolerated by the caller;
    anything else fails immediately.
    """
    with client.stream(
        "POST",
        f"/api/threads/{thread_id}/runs/stream",
        json={
            "input": {"messages": [{"role": "user", "content": message}]},
            # The doc-generation turn legitimately chains hundreds of tool
            # steps (run7 exhausted 400 after present_files, while writing its
            # final chat message); the server clamps to
            # config.max_recursion_limit (1000).
            "config": {"recursion_limit": 1000},
            "context": {
                "agent_name": AGENT_SLUG,
                "model_name": model_name,
                "thinking_enabled": False,
                "is_plan_mode": False,
                "subagent_enabled": False,
            },
        },
        headers={"X-CSRF-Token": csrf},
    ) as stream:
        assert stream.status_code == 200, stream.read().decode()
        transcript = _drain_stream(stream, timeout=TURN_TIMEOUT_S)

    events = _parse_sse(transcript)
    event_names = [event["event"] for event in events]
    error_name = None
    if "error" in event_names:
        error_event = next(event for event in events if event["event"] == "error")
        error_name = str(error_event["data"].get("name") or "unknown")
        assert error_name == "GraphRecursionError", f"run stream errored ({error_name}); tail: {transcript[-4000:]!r}"
    assert event_names and event_names[-1] == "end", f"run stream never ended; tail: {transcript[-4000:]!r}"

    metadata = next(event["data"] for event in events if event["event"] == "metadata")
    run_id = metadata["run_id"]
    record = client.get(f"/api/threads/{thread_id}/runs/{run_id}", headers={"X-CSRF-Token": csrf})
    assert record.status_code == 200, record.text
    return run_id, record.json(), error_name


def _assert_turn_status_allowed(client: TestClient, thread_id: str, csrf: str, run_id: str, record: dict, turn: int, error_name: str | None) -> None:
    """Mid-flow runs may only fail through the delivery gate or the step budget.

    Two tolerated terminal states besides ``success``:

    - A scripted turn that writes progress.json and then ends on an
      ``ask_clarification`` card produced outputs without calling
      ``present_files`` in the same run, so the worker records the run as
      ``error`` ("Artifact delivery incomplete..."). Platform delivery
      verification semantics, not a flow failure — the conversation continues.
    - A ``GraphRecursionError`` abort (per-run step budget), already counted
      and capped by the caller.

    Any run that presented files (run.delivery event non-empty) and still
    errored for another reason, or errored in any other way, fails here.
    """
    status = record.get("status")
    if status == "success":
        return
    if error_name == "GraphRecursionError":
        return
    assert status == "error", f"turn {turn} run {run_id} has unexpected status {status!r}: {record}"

    events_response = client.get(
        f"/api/threads/{thread_id}/runs/{run_id}/events?event_types=run.delivery",
        headers={"X-CSRF-Token": csrf},
    )
    assert events_response.status_code == 200, events_response.text
    delivery_events = events_response.json()
    presented = [path for event in delivery_events for path in ((event.get("content") or {}).get("paths") or [])]
    assert not presented, f"turn {turn} run {run_id} presented {presented!r} but still ended in error: {record.get('metadata', {}).get('run_evidence', {}).get('tool_receipts')}"


def _thread_messages(client: TestClient, thread_id: str, csrf: str) -> list[dict]:
    response = client.get(f"/api/threads/{thread_id}/messages?limit=200", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    return response.json()


def _row_text(row: dict) -> str:
    content = row.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        inner = content.get("content")
        if isinstance(inner, str):
            return inner
        if isinstance(inner, list):
            return "".join(block.get("text", "") for block in inner if isinstance(block, dict))
    return ""


def _last_clarification_question(rows: list[dict]) -> str | None:
    for row in reversed(rows):
        content = row.get("content")
        if row.get("event_type") == "llm.tool.result" and isinstance(content, dict) and content.get("name") == "ask_clarification":
            return _row_text(row)
    return None


def _last_ai_text(rows: list[dict]) -> str:
    for row in reversed(rows):
        if row.get("event_type") in {"llm.ai.response", "ai_message"}:
            return _row_text(row)
    return ""


def _host_outputs_dir(thread_id: str, user_id: str) -> Path:
    """Host-side mount point of the sandbox's /mnt/user-data/outputs."""
    from deerflow.config.paths import get_paths

    return get_paths().sandbox_outputs_dir(thread_id, user_id=user_id)


def _read_stage(run_dir: Path) -> str | None:
    progress = run_dir / "progress.json"
    if not progress.is_file():
        return None
    try:
        return str(json.loads(progress.read_text(encoding="utf-8")).get("stage") or "")
    except (json.JSONDecodeError, OSError):
        return None


def _watch_stages(run_dir: Path, stop: threading.Event, observed: list[str]) -> None:
    """Record every distinct ``stage`` value progress.json passes through.

    A single turn may legally cross several phases before it ends on a
    clarification card, so per-turn snapshots can miss intermediate stages.
    The poller only reads the host-side outputs file — it never touches the
    app under test.
    """
    while not stop.is_set():
        stage = _read_stage(run_dir)
        if stage and (not observed or observed[-1] != stage):
            observed.append(stage)
        stop.wait(0.5)


def _flow_complete(run_dir: Path) -> bool:
    return (run_dir / "srs_document.docx").is_file() and (run_dir / "traceability-matrix.docx").is_file() and _read_stage(run_dir) in {"review", "complete"}


def _docx_text(path: Path) -> str:
    """De-tagged text of word/document.xml for containment checks.

    Strips every XML tag and matches the remaining text — an independent,
    looser check than the bundled validator (which pattern-matches the raw
    XML, tags included); it does not claim the validator's semantics, only
    orthogonal coverage of the rendered document body.
    """
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    return re.sub(r"<[^>]+>", "", xml)


def _install_srs_skill_for_user(tmp_dir: Path, user_id: str) -> None:
    """Install the bundled srs-writing Skill into the running user's skill storage.

    The bundled resource seed provisions the catalog Skill (canonical snapshot,
    prompt metadata), but the sandbox ``/mnt/skills`` projection reads the
    file-based user skill storage — so the skill must also be installed there.
    This is the platform install seam (``DeerFlowClient.install_skill`` and the
    skills UI install flow both land here) and it runs the real security scan
    on the archive.
    """
    from deerflow.config.app_config import get_app_config
    from deerflow.skills.storage import get_or_new_user_skill_storage

    skill_source = REPO_ROOT / "resources" / "skills" / AGENT_SLUG
    archive_path = tmp_dir / f"{AGENT_SLUG}.skill"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(skill_source.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(skill_source).as_posix())

    storage = get_or_new_user_skill_storage(user_id, app_config=get_app_config())
    result = storage.install_skill_from_archive(archive_path)
    assert result.get("success") is True, result
    assert result.get("skill_name") == AGENT_SLUG, result


# ---------------------------------------------------------------------------
# The acceptance test
# ---------------------------------------------------------------------------


def test_srs_writing_agent_six_phase_flow_real_llm(srs_llm_gateway: _Gateway, tmp_path: Path):
    """Six-phase srs-writing flow end to end over the gateway HTTP API."""
    app, _home, model_name = srs_llm_gateway
    flow_started = time.monotonic()

    with TestClient(app) as client:
        user_email = "srs-llm-e2e@example.com"
        csrf = register_user(client, email=user_email)
        user_id = auth_user_id(client)
        _seed_bundled_srs_resources(user_id)
        _install_srs_skill_for_user(tmp_path, user_id)

        thread_id = create_thread(client, csrf)
        upload = client.post(
            f"/api/threads/{thread_id}/uploads",
            files={"files": (TASKBOOK_FILENAME, TASKBOOK_MARKDOWN.encode("utf-8"), "text/markdown")},
            headers={"X-CSRF-Token": csrf},
        )
        assert upload.status_code == 200, upload.text

        outputs_dir = _host_outputs_dir(thread_id, user_id)
        run_dir = outputs_dir / OUTPUTS_SUBDIR

        # Scripted multi-turn conversation: the model paces the phases, every
        # ask_clarification card is answered with the same comprehensive reply.
        stages: list[str] = []
        run_ids: list[uuid.UUID | str] = []
        turn_notes: list[str] = []
        last_record: dict = {}
        recursion_aborts = 0
        flow_finished = False
        message = START_MESSAGE
        for turn in range(1, MAX_TURNS + 1):
            stop = threading.Event()
            watcher = threading.Thread(target=_watch_stages, args=(run_dir, stop, stages), daemon=True)
            watcher.start()
            try:
                run_id, record, error_name = _run_turn(client, thread_id, csrf, message, model_name)
            finally:
                stop.set()
                watcher.join(timeout=5)
            run_ids.append(run_id)
            last_record = record
            if error_name == "GraphRecursionError":
                # A per-run step budget abort; the thread checkpoint keeps the
                # conversation resumable, so budget at most one and continue.
                recursion_aborts += 1
                assert recursion_aborts <= 1, f"more than one turn hit the recursion limit; turn notes={turn_notes!r}"
            _assert_turn_status_allowed(client, thread_id, csrf, run_id, record, turn, error_name)

            rows = _thread_messages(client, thread_id, csrf)
            stage = _read_stage(run_dir)
            if stage and (not stages or stages[-1] != stage):
                stages.append(stage)
            question = _last_clarification_question(rows) or ""
            turn_notes.append(f"turn {turn}: status={record.get('status')} stage={stage or '-'} asked={question.strip().splitlines()[0][:80] if question.strip() else '-'}")

            if _flow_complete(run_dir) and record.get("status") == "success":
                # Only the *delivering* turn completes the flow: artifacts
                # on disk plus a run the delivery gate accepted. A turn
                # that produced artifacts but died before present_files
                # gets one more nudge instead of a false completion.
                flow_finished = True
                break
            message = CONFIRM_REPLY

        print("\n=== srs-writing real-LLM conversation ===")
        for note in turn_notes:
            print(f"  {note}")
        print(f"  elapsed: {time.monotonic() - flow_started:.0f}s")

        assert flow_finished, (
            f"flow did not complete within {MAX_TURNS} turns; stages={stages!r}; turn notes={turn_notes!r}; "
            f"progress.json={(run_dir / 'progress.json').read_text(encoding='utf-8') if (run_dir / 'progress.json').is_file() else 'missing'!r}; "
            f"outputs={sorted(p.name for p in run_dir.iterdir()) if run_dir.is_dir() else 'missing'!r}; "
            f"last AI text={_last_ai_text(_thread_messages(client, thread_id, csrf))[:500]!r}"
        )
        # The delivering turn presented the produced artifacts, so the delivery
        # gate must mark it success — the terminal run of the flow.
        assert last_record.get("status") == "success", f"final run status: {last_record}"

        final_text = _last_ai_text(_thread_messages(client, thread_id, csrf))

    # ------------------------------------------------------------------
    # 1. 阶段流转: canonical order, user-gated phases observed, finished.
    # ------------------------------------------------------------------
    assert stages, f"progress.json never appeared under {run_dir}"
    unknown_stages = [stage for stage in stages if stage not in STAGE_ORDER]
    assert not unknown_stages, f"unknown stage values {unknown_stages!r}; expected a subset of {STAGE_ORDER}"
    ranks = [STAGE_ORDER.index(stage) for stage in stages]
    assert ranks == sorted(ranks), f"stage regression in {stages!r}"
    assert stages[-1] in {"review", "complete"}, f"final stage is {stages[-1]!r} (stages={stages!r})"
    assert {"task_book_parsing", "requirement_analysis", "interactive_confirmation"} <= set(stages), f"user-gated phases missing from observed stages {stages!r}"

    # ------------------------------------------------------------------
    # 2. 进度文件更新: functions tracked, every decision terminal, exactly
    #    one rejection and it is the planted cloud-upload clause (F-4.2-*).
    # ------------------------------------------------------------------
    progress = json.loads((run_dir / "progress.json").read_text(encoding="utf-8"))
    function_ids = {str(function.get("id")) for function in progress.get("functions") or []}
    assert {FUNCTION_IDS[0], FUNCTION_IDS[1]} <= function_ids, f"function items missing: {function_ids!r}"

    requirements = progress.get("requirements") or []
    assert requirements, "progress.json records no requirements"
    assert all(str(requirement.get("status")) in TERMINAL_REQUIREMENT_STATUSES for requirement in requirements), f"non-terminal requirement decisions: {requirements!r}"
    rejected = [requirement for requirement in requirements if requirement.get("status") == "rejected"]
    assert len(rejected) == 1, f"expected exactly one rejected requirement, got: {rejected!r}"
    rejected_id = str(rejected[0].get("id"))
    assert re.fullmatch(r"F-4\.2-\d+", rejected_id), f"rejected {rejected_id!r} is not the planted F-4.2-* clause"

    # ------------------------------------------------------------------
    # 3. 产物生成: all four artifacts exist non-empty.
    # ------------------------------------------------------------------
    for artifact in ("srs_document.docx", "traceability-matrix.docx", "requirement-catalog.md", "progress.json"):
        path = run_dir / artifact
        assert path.is_file() and path.stat().st_size > 0, f"missing or empty artifact: {path}"

    # ------------------------------------------------------------------
    # 4. 校验器在挂载路径 exit 0: repo skill package AND the frozen
    #    run-skill-view copy actually mounted at /mnt/skills for the run.
    # ------------------------------------------------------------------
    repo_validator = REPO_ROOT / "resources" / "skills" / "srs-writing" / "scripts" / "validate_srs_outputs.py"
    repo_run = subprocess.run(
        [sys.executable, str(repo_validator), "--outputs-dir", str(outputs_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert repo_run.returncode == 0, f"repo validator failed:\n{repo_run.stdout}\n{repo_run.stderr}"

    from app.agentplatform.resources.canonical_sandbox import canonical_run_skill_view_path

    # Same layout as run preparation builds (paths.base_dir honors DEER_FLOW_HOME,
    # which the fixture points at the isolated home).
    skill_view = canonical_run_skill_view_path(str(run_ids[-1]))
    mounted_validator = skill_view / AGENT_SLUG / "scripts" / "validate_srs_outputs.py"
    assert mounted_validator.is_file(), f"run skill view is missing the bundled validator: {skill_view}"
    mounted_run = subprocess.run(
        [sys.executable, str(mounted_validator), "--outputs-dir", str(outputs_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert mounted_run.returncode == 0, f"mounted validator failed:\n{mounted_run.stdout}\n{mounted_run.stderr}"

    # ------------------------------------------------------------------
    # 5. 拒绝项不泄漏: rejected ID + wording absent from both .docx bodies,
    #    accepted IDs present (positive control), rejection recorded in the
    #    requirement catalog.
    # ------------------------------------------------------------------
    srs_text = _docx_text(run_dir / "srs_document.docx")
    matrix_text = _docx_text(run_dir / "traceability-matrix.docx")
    assert rejected_id not in srs_text, f"rejected {rejected_id} leaked into srs_document.docx"
    assert rejected_id not in matrix_text, f"rejected {rejected_id} leaked into traceability-matrix.docx"
    assert REJECTED_KEYWORD not in srs_text, "the rejected cloud-upload wording leaked into srs_document.docx"

    accepted_ids = [str(requirement.get("id")) for requirement in requirements if requirement.get("status") in {"accepted", "modified"}]
    assert accepted_ids, f"no accepted requirements to control against: {requirements!r}"
    assert any(accepted_id in srs_text for accepted_id in accepted_ids), f"positive control failed: no accepted ID {accepted_ids!r} appears in srs_document.docx"
    assert any(accepted_id in matrix_text for accepted_id in accepted_ids), f"positive control failed: no accepted ID {accepted_ids!r} appears in traceability-matrix.docx"

    catalog = (run_dir / "requirement-catalog.md").read_text(encoding="utf-8")
    assert rejected_id in catalog, f"rejected {rejected_id} is not recorded in requirement-catalog.md"

    assert final_text and "FAILED:" not in final_text, f"empty or failure-reporting final message: {final_text[:500]!r}"
