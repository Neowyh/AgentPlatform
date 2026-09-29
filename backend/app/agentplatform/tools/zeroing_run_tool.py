"""Chat-loop bridge tools for the Fault-zeroing Execution Kernel (ticket 04).

Real analysis requests raised inside the fault-zeroing Expert closure are
promoted into canonical kernel Runs instead of an inline chat answer:

- ``start_zeroing_run`` — materializes the declared evidence (thread uploads
  and the Thread-private Code Evidence Package) into the Run workspace, then
  starts the Run through the same kernel canonical creation path the gateway
  uses (ticket 03).  Double-missing evidence never creates a Run — the model
  answers with an ``ask_clarification`` guidance card instead; a single
  missing side parks a paused Run whose missing-side information and input
  snapshot hash come back to the model for the three-choice confirmation.
- ``confirm_zeroing_run`` — forwards the user's “continue with the missing
  side” choice to the kernel's evidence confirmation (hash-bound, so material
  added after the pause forces re-confirmation instead of silently continuing).
- ``check_zeroing_run`` — durable completion awareness without any long-lived
  task: the model polls it on follow-up turns.  A completed Run has its five
  Result Contract artifacts copied into the chat thread outputs and presented
  through the artifacts channel (the ``present_files`` semantics); a contract
  violation comes back with the violation summary and the surviving artifacts
  remain presentable.

Availability is closed to the fault-zeroing Expert closure: the tools reject
any run whose context does not carry the fault-zeroing agent identity (or an
active fault-zeroing skill), and every kernel call keeps the gateway's RBAC
chain (visible + use-authorized workflow resource) — no bypass.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Any

from langchain.tools import InjectedToolCallId, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agentplatform.code_evidence import PackageManifest, package_root
from app.agentplatform.fault_zeroing.contract import REQUIRED_OUTPUTS
from app.agentplatform.fault_zeroing.kernel import (
    ConfirmationStaleError,
    EvidenceIntakeRejected,
    FaultZeroingKernel,
    RunNotFoundError,
)
from app.agentplatform.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceError,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
)
from app.agentplatform.workflows.v2.store import WorkflowV2Store
from deerflow.config.paths import VIRTUAL_PATH_PREFIX, get_paths
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)

ZEROING_WORKFLOW_SLUG = "fault-zeroing"
ZEROING_CLOSURE_NAME = "fault-zeroing"
RUN_DETAIL_URL_TEMPLATE = "/workspace/workflows/{resource_id}/runs/{run_id}"

_GUIDANCE_NEXT_ACTION = "请调用 ask_clarification 向用户提供引导卡片，说明发起归零分析需要的材料（问题描述，以及可选的文档附件与代码证据包），不要创建 Run。"
_THREE_CHOICE_NEXT_ACTION = "请调用 ask_clarification 向用户呈现三选一：补传缺失材料后重新发起 / 在缺失该侧证据的情况下继续（调用 confirm_zeroing_run）/ 停止（放弃本次 Run，不确认即可）。"


class _MaterializationError(ValueError):
    """Declared evidence cannot be materialized into the Run workspace."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _session_factory():
    """DB session factory seam (monkeypatched in tests)."""

    from deerflow.persistence.engine import get_session_factory

    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("resource persistence is unavailable")
    return factory


def _get_app_config():
    from deerflow.config import get_app_config

    return get_app_config()


def _workflow_runtime():
    return _get_app_config().workflow_runtime


def _tool_result(tool_call_id: str, payload: dict[str, Any], *, artifacts: list[str] | None = None) -> Command:
    update: dict[str, Any] = {"messages": [ToolMessage(json.dumps(payload, ensure_ascii=False), tool_call_id=tool_call_id)]}
    if artifacts:
        # Same state channel as present_files: the reducer merges and the
        # client renders the files from the thread outputs directory.
        update["artifacts"] = artifacts
    return Command(update=update)


def _tool_error(tool_call_id: str, reason_code: str, message: str, **extra: Any) -> Command:
    return _tool_result(tool_call_id, {"created": False, "reason_code": reason_code, "error": message, **extra})


def _get_thread_id(runtime: Runtime) -> str | None:
    thread_id = runtime.context.get("thread_id") if runtime.context else None
    if thread_id:
        return thread_id
    runtime_config = getattr(runtime, "config", None) or {}
    return runtime_config.get("configurable", {}).get("thread_id")


def _closure_entry(runtime: Runtime) -> str | None:
    """Kernel entry label when this run belongs to the zeroing closure.

    The fault-zeroing Expert identity maps to ``expert``; an active
    fault-zeroing skill outside the Expert (Task-Chip / slash activation)
    maps to ``skill``.  Anything else is outside the closure.
    """

    context = getattr(runtime, "context", None) or {}
    agent_name = str(context.get("agent_name") or "").strip().lower()
    if agent_name == ZEROING_CLOSURE_NAME:
        return "expert"
    skill_name = str(context.get("skill_name") or "").strip().lower()
    skill_names = {str(name).strip().lower() for name in (context.get("skill_names") or [])}
    if skill_name == ZEROING_CLOSURE_NAME or ZEROING_CLOSURE_NAME in skill_names:
        return "skill"
    return None


def _resource_actor(runtime: Runtime) -> ResourceActor:
    """Actor for the RBAC chain, mirroring the gateway's ``_resource_actor``."""

    context = getattr(runtime, "context", None) or {}
    role = str(context.get("user_role") or "viewer")
    permissions = {ResourceAction.READ}
    if role in {"user", "department_admin", "super_admin"}:
        permissions.update({ResourceAction.USE, ResourceAction.WRITE})
    if role in {"department_admin", "super_admin"}:
        permissions.add(ResourceAction.APPROVE)
    if role == "super_admin":
        permissions.update(ResourceAction)
    authz = context.get("authz_attributes")
    department_id = str(authz.get("department_id")) if isinstance(authz, dict) and authz.get("department_id") is not None else None
    return ResourceActor(
        user_id=resolve_runtime_user_id(runtime),
        department_id=department_id,
        role=role,
        permissions=frozenset(permissions),
        tool_groups=None,
    )


async def _resolve_zeroing_workflow(actor: ResourceActor) -> tuple[Any, dict[str, Any]]:
    """RBAC-checked fault-zeroing workflow lookup (visible + use-authorized)."""

    from sqlalchemy import select

    from app.agentplatform.resource_models import ResourceVersion

    factory = _session_factory()
    async with factory() as session:
        service = ResourceService(session, actor)
        resource = await service.resolve_legacy_alias("workflow", ZEROING_WORKFLOW_SLUG)
        resource = await service.resolve_for_use(resource.id)
        version = (
            await session.execute(
                select(ResourceVersion).where(
                    ResourceVersion.resource_id == resource.id,
                    ResourceVersion.version == resource.latest_version,
                )
            )
        ).scalar_one_or_none()
        content = version.content if version is not None else None
        return resource, content if isinstance(content, dict) else {}


def _resolve_upload_source(thread_uploads_dir: Path, declared: str) -> Path:
    """Resolve one declared upload to a file inside the thread uploads dir."""

    declared = (declared or "").strip()
    if not declared:
        raise _MaterializationError("upload_path_rejected", "上传路径为空")
    if declared.startswith(f"{VIRTUAL_PATH_PREFIX}/"):
        relative = declared[len(VIRTUAL_PATH_PREFIX) + 1 :]
    elif declared.isidentifier() or ("/" not in declared and "\\" not in declared):
        relative = f"uploads/{declared}"
    else:
        raise _MaterializationError("upload_path_rejected", f"上传路径必须是文件名或 /mnt/user-data/uploads/... 虚拟路径: {declared}")
    if relative.startswith("uploads/"):
        relative = relative[len("uploads/") :]
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise _MaterializationError("upload_path_rejected", f"上传路径不合法: {declared}")
    candidate = (thread_uploads_dir / relative).resolve()
    try:
        candidate.relative_to(thread_uploads_dir.resolve())
    except ValueError as exc:
        raise _MaterializationError("upload_path_rejected", f"上传路径超出本会话 uploads 目录: {declared}") from exc
    if not candidate.is_file():
        raise _MaterializationError("upload_path_rejected", f"上传文件不存在: {declared}")
    return candidate


def _materialize_uploads(thread_id: str, user_id: str, upload_paths: list[str], run_id: str) -> None:
    """Copy declared thread uploads into the Run workspace (Run 自包含)."""

    paths = get_paths()
    thread_uploads_dir = paths.sandbox_uploads_dir(thread_id, user_id=user_id)
    run_uploads_dir = paths.sandbox_uploads_dir(run_id, user_id=user_id)
    run_uploads_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for declared in upload_paths:
        source = _resolve_upload_source(thread_uploads_dir, declared)
        target = run_uploads_dir / source.name
        if target.name in seen:
            target = run_uploads_dir / f"{source.stem}-{uuid.uuid4().hex[:8]}{source.suffix}"
        seen.add(target.name)
        shutil.copyfile(source, target)


def _materialize_code_package(thread_id: str, user_id: str, code_package_id: str, run_id: str) -> PackageManifest:
    """Re-bind one Thread-private Code Evidence Package into the Run workspace."""

    manifest_path = package_root(thread_id, code_package_id, user_id=user_id) / "manifest.json"
    try:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _MaterializationError("code_package_not_found", f"本会话不存在该代码证据包: {code_package_id}") from exc
    if not isinstance(source_manifest, dict):
        raise _MaterializationError("code_package_not_found", f"本会话不存在该代码证据包: {code_package_id}")
    new_package_id = uuid.uuid4().hex
    target_root = package_root(run_id, new_package_id, user_id=user_id)
    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package_root(thread_id, code_package_id, user_id=user_id) / "source", target_root / "source")
    manifest = PackageManifest(
        package_id=new_package_id,
        original_filename=str(source_manifest.get("original_filename", "")),
        accepted=tuple(source_manifest.get("accepted", ())),
        excluded=tuple(source_manifest.get("excluded", ())),
        rejected=tuple(source_manifest.get("rejected", ())),
        compressed_size=int(source_manifest.get("compressed_size", 0)),
        expanded_size=int(source_manifest.get("expanded_size", 0)),
    )
    (target_root / "manifest.json").write_text(json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _discard_run_user_data(run_id: str, user_id: str) -> None:
    shutil.rmtree(get_paths().thread_dir(run_id, user_id=user_id) / "user-data", ignore_errors=True)


@tool("start_zeroing_run", parse_docstring=True)
async def start_zeroing_run_tool(
    runtime: Runtime,
    problem_description: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    upload_paths: list[str] | None = None,
    code_package_id: str | None = None,
) -> Command:
    """Promote a real fault-zeroing analysis request into a formal kernel Run.

    Use this tool ONLY when the user asks for an actual fault-zeroing analysis
    (故障归零分析). Concept explanations, method Q&A and report wording edits
    stay ordinary conversation — never start a Run for them.

    The declared evidence is materialized into the Run workspace, so the Run is
    self-contained. Outcomes:

    - Both evidence sides present: the Run is queued immediately; report the
      returned ``detail_url`` so the user can follow progress, and call
      ``check_zeroing_run`` later to deliver the artifacts.
    - One evidence side missing: the Run is parked (``status: paused``). Pass
      the returned missing-side information and choices to the user through
      ``ask_clarification`` (补传 / 缺侧继续 / 停止). If the user chooses to
      continue, call ``confirm_zeroing_run`` with the returned
      ``input_snapshot_hash``.
    - No usable evidence (empty description): nothing is created; answer with
      an ``ask_clarification`` guidance card per ``next_action``.

    Args:
        problem_description: The problem / top-event description from the user. Required and non-empty.
        upload_paths: Optional list of this thread's uploaded evidence files (names or /mnt/user-data/uploads/... paths) to materialize into the Run.
        code_package_id: Optional Code Evidence Package id of this thread to materialize into the Run.
    """
    return await _start_zeroing_run(
        runtime,
        problem_description=problem_description,
        upload_paths=upload_paths or [],
        code_package_id=code_package_id,
        tool_call_id=tool_call_id,
    )


async def _start_zeroing_run(
    runtime: Runtime,
    *,
    problem_description: str,
    upload_paths: list[str],
    code_package_id: str | None,
    tool_call_id: str,
) -> Command:
    entry = _closure_entry(runtime)
    if entry is None:
        return _tool_error(tool_call_id, "zeroing_closure_required", "start_zeroing_run 仅对归零排故 Expert 闭包可用")

    description = (problem_description or "").strip()
    if not description:
        # 参数校验即“描述缺失”的双缺分支：不创建 Run，转引导卡片。
        return _tool_error(tool_call_id, "intake_evidence_missing_both", "问题描述为空，无法发起归零 Run", next_action=_GUIDANCE_NEXT_ACTION)

    thread_id = _get_thread_id(runtime)
    if not thread_id:
        return _tool_error(tool_call_id, "thread_context_missing", "当前会话缺少 thread 上下文，无法发起归零 Run")
    user_id = resolve_runtime_user_id(runtime)

    run_id = str(uuid.uuid4())
    try:
        actor = _resource_actor(runtime)
        resource, definition = await _resolve_zeroing_workflow(actor)
        if definition.get("result_contract") is None:
            return _tool_error(
                tool_call_id,
                "result_contract_undeclared",
                f"工作流 {ZEROING_WORKFLOW_SLUG} 未声明 Result Contract，拒绝经聊天入口发起",
            )

        upload_dir = ""
        if upload_paths:
            _materialize_uploads(thread_id, user_id, upload_paths, run_id)
            upload_dir = f"{VIRTUAL_PATH_PREFIX}/uploads"
        code_package_source = ""
        if code_package_id:
            code_package_source = _materialize_code_package(thread_id, user_id, code_package_id, run_id).source_virtual_path

        limits = _workflow_runtime()
        result = await FaultZeroingKernel(WorkflowV2Store(_session_factory())).start_run(
            workflow_name=str(resource.slug),
            definition_version=int(resource.latest_version),
            inputs={
                "problem_description": description,
                "upload_dir": upload_dir,
                "code_package_source": code_package_source,
            },
            created_by=user_id,
            run_id=run_id,
            workflow_resource_id=str(resource.id),
            actor=actor,
            entry=entry,
            user_concurrency=limits.user_concurrency,
            department_concurrency=limits.department_concurrency,
        )
    except EvidenceIntakeRejected as exc:
        _discard_run_user_data(run_id, user_id)
        return _tool_error(
            tool_call_id,
            exc.reason_code,
            "缺少全部证据侧，无法发起归零 Run",
            missing_evidence_sides=list(exc.decision.missing),
            next_action=_GUIDANCE_NEXT_ACTION,
        )
    except (ResourceNotFound, ResourcePermissionDenied) as exc:
        return _tool_error(tool_call_id, "workflow_not_usable", f"归零工作流不可用或无使用权限：{exc}")
    except ResourceError as exc:
        return _tool_error(tool_call_id, "workflow_not_usable", f"归零工作流不可用：{exc}")
    except _MaterializationError as exc:
        _discard_run_user_data(run_id, user_id)
        # 证据物化失败 = 到达 intake 前的双缺场景：转引导卡片，不创建 Run。
        return _tool_error(tool_call_id, exc.reason_code, str(exc), next_action=_GUIDANCE_NEXT_ACTION)
    except (ValueError, OSError) as exc:
        _discard_run_user_data(run_id, user_id)
        return _tool_error(tool_call_id, "evidence_materialization_failed", f"证据物化失败：{exc}", next_action=_GUIDANCE_NEXT_ACTION)
    except RuntimeError as exc:
        if str(exc) in {"workflow_user_concurrency_exceeded", "workflow_department_concurrency_exceeded"}:
            return _tool_error(tool_call_id, str(exc), "并发运行的归零工作流数量已达上限，请稍后再试")
        _discard_run_user_data(run_id, user_id)
        raise

    detail_url = RUN_DETAIL_URL_TEMPLATE.format(resource_id=resource.id, run_id=result.run_id)
    payload: dict[str, Any] = {
        "created": True,
        "run_id": result.run_id,
        "status": result.status,
        "reason_code": result.reason_code,
        "missing_evidence_sides": list(result.intake.missing),
        "input_snapshot_hash": result.intake.input_snapshot_hash,
        "detail_url": detail_url,
    }
    if result.status == "paused":
        payload["next_action"] = _THREE_CHOICE_NEXT_ACTION
    else:
        payload["next_action"] = "请告知用户归零分析已发起，可随时查看进度；稍后调用 check_zeroing_run 查询结果并回传产物。"
    return _tool_result(tool_call_id, payload)


@tool("confirm_zeroing_run", parse_docstring=True)
async def confirm_zeroing_run_tool(
    runtime: Runtime,
    run_id: str,
    input_snapshot_hash: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Resume a paused fault-zeroing Run after the user accepts the missing evidence side.

    Call this only after the user picked “在缺失该侧证据的情况下继续” from the
    clarification card, passing back the ``input_snapshot_hash`` that
    ``start_zeroing_run`` returned. If material changed after the pause the
    kernel rejects the confirmation and the user must choose again.

    Args:
        run_id: The paused Run id returned by start_zeroing_run.
        input_snapshot_hash: The hash captured at pause time (echo it unchanged).
    """
    entry = _closure_entry(runtime)
    if entry is None:
        return _tool_error(tool_call_id, "zeroing_closure_required", "confirm_zeroing_run 仅对归零排故 Expert 闭包可用")
    user_id = resolve_runtime_user_id(runtime)
    store = WorkflowV2Store(_session_factory())
    kernel = FaultZeroingKernel(store)
    run = await store.get_run(run_id)
    if run is None:
        return _tool_error(tool_call_id, "run_not_found", f"归零 Run 不存在: {run_id}")
    if str(run.created_by) != str(user_id) and _resource_actor(runtime).role != "super_admin":
        return _tool_error(tool_call_id, "run_not_accessible", "无权限操作该归零 Run")

    try:
        confirmation = await kernel.confirm_evidence(
            run_id,
            payload={"input_snapshot_hash": input_snapshot_hash},
            confirmed_by=user_id,
        )
    except ConfirmationStaleError as exc:
        reconfirm = exc.reason_code == "intake_snapshot_changed"
        payload: dict[str, Any] = {
            "confirmed": False,
            "reconfirm_required": reconfirm,
            "reason_code": exc.reason_code,
            "error": "确认时的输入快照与暂停时不一致：材料已变化，需要重新确认" if reconfirm else f"确认被拒绝: {exc}",
        }
        if reconfirm:
            payload["next_action"] = _THREE_CHOICE_NEXT_ACTION
        return _tool_result(tool_call_id, payload)
    except RunNotFoundError:
        return _tool_error(tool_call_id, "run_not_found", f"归零 Run 不存在: {run_id}")

    return _tool_result(
        tool_call_id,
        {
            "confirmed": True,
            "run_id": run_id,
            "status": "queued",
            "missing_evidence_sides": confirmation["missing_evidence_sides"],
            "input_snapshot_hash": confirmation["input_snapshot_hash"],
            "detail_url": await _detail_url_for(store, run_id),
            "next_action": "请告知用户归零分析已恢复执行；稍后调用 check_zeroing_run 查询结果并回传产物。",
        },
    )


async def _detail_url_for(store: WorkflowV2Store, run_id: str) -> str:
    run = await store.get_run(run_id)
    resource_id = str(run.workflow_resource_id) if run is not None and run.workflow_resource_id else ZEROING_WORKFLOW_SLUG
    return RUN_DETAIL_URL_TEMPLATE.format(resource_id=resource_id, run_id=run_id)


@tool("check_zeroing_run", parse_docstring=True)
async def check_zeroing_run_tool(
    runtime: Runtime,
    run_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Check a fault-zeroing Run's progress and bridge finished artifacts into this chat.

    Call this when the user asks about progress or results, and after you
    started a Run. On completion the five Result Contract artifacts are copied
    into this thread's outputs and presented automatically. On a contract
    violation the violation summary comes back and the surviving artifacts
    stay presentable.

    Args:
        run_id: The Run id returned by start_zeroing_run.
    """
    entry = _closure_entry(runtime)
    if entry is None:
        return _tool_error(tool_call_id, "zeroing_closure_required", "check_zeroing_run 仅对归零排故 Expert 闭包可用")
    user_id = resolve_runtime_user_id(runtime)
    thread_id = _get_thread_id(runtime)
    store = WorkflowV2Store(_session_factory())
    run = await store.get_run(run_id)
    if run is None:
        return _tool_error(tool_call_id, "run_not_found", f"归零 Run 不存在: {run_id}")
    if str(run.created_by) != str(user_id) and _resource_actor(runtime).role != "super_admin":
        return _tool_error(tool_call_id, "run_not_accessible", "无权限查看该归零 Run")

    detail_url = await _detail_url_for(store, run_id)
    if run.status == "paused":
        intake = run.snapshot.get("evidence_intake") if isinstance(run.snapshot, dict) else None
        missing = list(intake.get("missing", [])) if isinstance(intake, dict) else []
        return _tool_result(
            tool_call_id,
            {
                "run_id": run_id,
                "status": "paused",
                "missing_evidence_sides": missing,
                "detail_url": detail_url,
                "next_action": _THREE_CHOICE_NEXT_ACTION,
            },
        )
    if run.status in {"queued", "running"}:
        return _tool_result(
            tool_call_id,
            {
                "run_id": run_id,
                "status": run.status,
                "detail_url": detail_url,
                "next_action": "分析仍在进行中；请把详情链接告诉用户，稍后再调用 check_zeroing_run。",
            },
        )
    if run.status not in {"completed", "failed"} or not thread_id:
        return _tool_error(tool_call_id, "run_not_bridgable", f"归零 Run 状态当前不可回桥: {run.status}")

    # Terminal: bridge the artifacts into the chat thread (契约违规同样可取).
    paths = get_paths()
    run_outputs_dir = paths.sandbox_outputs_dir(run_id, user_id=str(run.created_by))
    thread_outputs_dir = paths.sandbox_outputs_dir(thread_id, user_id=user_id)
    thread_outputs_dir.mkdir(parents=True, exist_ok=True)
    presented: list[str] = []
    for name in REQUIRED_OUTPUTS:
        source = run_outputs_dir / name
        if source.is_file():
            shutil.copyfile(source, thread_outputs_dir / name)
            presented.append(f"{VIRTUAL_PATH_PREFIX}/outputs/{name}")

    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": run.status,
        "detail_url": detail_url,
        "presented": presented,
    }
    if run.status == "failed":
        payload["error_summary"] = run.error or "归零 Run 失败（无错误摘要）"
        payload["next_action"] = "契约校验未通过：请把违规摘要告诉用户；产物链接仍可查看，用户可修正材料后重新发起。"
    else:
        payload["next_action"] = "归零分析已完成，五件套产物已送回会话展示。"
    return _tool_result(tool_call_id, payload, artifacts=presented or None)


zeroing_run_tools = [start_zeroing_run_tool, confirm_zeroing_run_tool, check_zeroing_run_tool]
