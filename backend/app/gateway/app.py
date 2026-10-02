import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from deerflow_extension_api import EXTENSION_PRINCIPAL_RESOLVER_KEY, ExtensionPrincipal
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import deerflow.extensions as deerflow_extensions
from app.gateway.auth_middleware import AuthMiddleware

# Alias legacy IDEER_* deployment env names before any config resolution.
from app.gateway.compat_env import apply_legacy_env_aliases  # noqa: F401
from app.gateway.config import get_gateway_config
from app.gateway.csrf_middleware import (
    CORS_EXPOSED_HEADERS,
    CSRFMiddleware,
    get_configured_cors_origins,
)
from app.gateway.deps import langgraph_runtime
from app.gateway.error_codes import ApiException
from app.gateway.routers import (
    admin,
    admin_knowledge,
    admin_skill_applications,
    artifacts,
    assistants_compat,
    audit_logs,
    auth,
    automations,
    channels,
    devices,
    features,
    feedback,
    input_polish,
    integrations,
    knowledge_tests,
    mcp,
    mcp_tasks,
    memory,
    models,
    project_documents,
    project_thread_files,
    projects,
    resources,
    runs,
    scheduled_tasks,
    skills,
    subagent_batches,
    suggestions,
    thread_runs,
    threads,
    tools,
    trash,
    uploads,
    user_preferences,
    visibility_applications,
)
from app.gateway.trace_middleware import TraceMiddleware
from deerflow.config import app_config as deerflow_app_config
from deerflow.config.app_config import apply_logging_level
from deerflow.extensions.gateway import include_contributed_routers
from deerflow.tracing import setup_monocle_tracing_if_enabled

AppConfig = deerflow_app_config.AppConfig
get_app_config = deerflow_app_config.get_app_config

# Default logging; lifespan overrides from config.yaml log_level.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Upper bound (seconds) each lifespan shutdown hook is allowed to run.
# Bounds worker exit time so uvicorn's reload supervisor does not keep
# firing signals into a worker that is stuck waiting for shutdown cleanup.
_SHUTDOWN_HOOK_TIMEOUT_SECONDS = 5.0


def _extension_principal(request: Request) -> ExtensionPrincipal | None:
    """Project the authenticated Gateway caller into the extension contract."""
    state = getattr(request, "state", None)
    user = getattr(state, "user", None)
    if user is None:
        return None

    from app.gateway.auth_disabled import AUTH_SOURCE_INTERNAL, AUTH_SOURCE_PAT

    source = getattr(state, "auth_source", None)
    role = getattr(user, "system_role", None)
    roles = (str(role),) if role else ()
    is_pat = source == AUTH_SOURCE_PAT
    return ExtensionPrincipal(
        user_id=str(getattr(user, "id", "")),
        is_admin=bool(role == "admin" and not is_pat),
        is_internal=bool(source == AUTH_SOURCE_INTERNAL),
        roles=() if is_pat and role == "admin" else roles,
    )


def _configure_extensions(app: FastAPI) -> None:
    """Load configured extensions and mount their contributions after host routes."""
    try:
        config = get_app_config()
    except FileNotFoundError:
        raw_specs = []
    else:
        raw_specs = getattr(config, "plugins", []) or []

    from deerflow.extensions.loader import ExtensionSpec

    specs = [spec if isinstance(spec, ExtensionSpec) else ExtensionSpec.model_validate(spec) for spec in raw_specs]

    try:
        loaded, diagnostics = deerflow_extensions.load_extensions(specs)
    except deerflow_extensions.ExtensionLoadError:
        raise
    except Exception:
        logger.exception("Extension loading failed; continuing without extensions")
        loaded, diagnostics = deerflow_extensions.EMPTY_EXTENSIONS, []

    deerflow_extensions.set_loaded_extensions(loaded)
    live_diagnostics = deerflow_extensions.initialize_runtime_diagnostics(list(diagnostics))
    app.state.extensions = loaded
    app.state.extension_diagnostics = live_diagnostics
    setattr(app.state, EXTENSION_PRINCIPAL_RESOLVER_KEY, _extension_principal)
    deerflow_extensions.record_runtime_diagnostics(include_contributed_routers(app, loaded))


async def _ensure_admin_user(app: FastAPI) -> None:
    """Startup hook: handle first boot and migrate orphan threads otherwise.

    After admin creation, migrate orphan threads from the LangGraph
    store (metadata.user_id unset) to the admin account. This is the
    "no-auth → with-auth" upgrade path: users who ran iDeer without
    authentication have existing LangGraph thread data that needs an
    owner assigned.
        First boot (no admin exists):
            - Does NOT create any user accounts automatically.
            - The operator must visit ``/setup`` to create the first admin.

    Subsequent boots (admin already exists):
      - Runs the one-time "no-auth → with-auth" orphan thread migration for
        existing LangGraph thread metadata that has no user_id.

    No SQL persistence migration is needed: the four user_id columns
    (threads_meta, runs, run_events, feedback) only come into existence
    alongside the auth module via create_all, so freshly created tables
    never contain NULL-owner rows.
    """
    from sqlalchemy import select

    from app.agentplatform.rbac_models import UserModel, UserRole
    from deerflow.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is None:
        return

    async with sf() as session:
        stmt = (
            select(UserModel)
            .where(
                UserModel.role == UserRole.SUPER_ADMIN,
                UserModel.disabled.is_not(True),
            )
            .limit(1)
        )
        admin_user = (await session.execute(stmt)).scalar_one_or_none()

    if admin_user is None:
        logger.info("=" * 60)
        logger.info("  First boot detected — no active super_admin account exists.")
        logger.info("  Visit /setup to complete admin account creation.")
        logger.info("=" * 60)
        return

    # Admin already exists — run orphan thread migration for any
    # LangGraph thread metadata that pre-dates the auth module.
    admin_id = str(admin_user.id)

    # LangGraph store orphan migration — non-fatal.
    # This covers the "no-auth → with-auth" upgrade path for users
    # whose existing LangGraph thread metadata has no user_id set.
    store = getattr(app.state, "store", None)
    if store is not None:
        try:
            migrated = await _migrate_orphaned_threads(store, admin_id)
            if migrated:
                logger.info("Migrated %d orphan LangGraph thread(s) to admin", migrated)
        except Exception:
            logger.exception("LangGraph thread migration failed (non-fatal)")


async def _iter_store_items(store, namespace, *, page_size: int = 500):
    """Paginated async iterator over a LangGraph store namespace.

    Replaces the old hardcoded ``limit=1000`` call with a cursor-style
    loop so that environments with more than one page of orphans do
    not silently lose data. Terminates when a page is empty OR when a
    short page arrives (indicating the last page).
    """
    offset = 0
    while True:
        batch = await store.asearch(namespace, limit=page_size, offset=offset)
        if not batch:
            return
        for item in batch:
            yield item
        if len(batch) < page_size:
            return
        offset += page_size


async def _migrate_orphaned_threads(store, admin_user_id: str) -> int:
    """Migrate LangGraph store threads with no user_id to the given admin.

    Uses cursor pagination so all orphans are migrated regardless of
    count. Returns the number of rows migrated.
    """
    migrated = 0
    async for item in _iter_store_items(store, ("threads",)):
        metadata = item.value.get("metadata", {})
        if not metadata.get("user_id"):
            metadata["user_id"] = admin_user_id
            item.value["metadata"] = metadata
            await store.aput(("threads",), item.key, item.value)
            migrated += 1
    return migrated


async def _reconcile_workflow_and_agent_metadata() -> None:
    """Startup hook: backfill resource_metadata for workflow/agent definitions lacking one.

    Uses the first active super_admin as the fallback owner. Idempotent —
    existing metadata records are never touched.
    """
    from sqlalchemy import select

    from app.agentplatform.rbac_models import UserModel, UserRole
    from deerflow.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is None:
        return

    async with sf() as session:
        stmt = (
            select(UserModel)
            .where(
                UserModel.role == UserRole.SUPER_ADMIN,
                UserModel.disabled.is_not(True),
            )
            .limit(1)
        )
        admin_user = (await session.execute(stmt)).scalar_one_or_none()

    if admin_user is None:
        logger.info("No active super_admin found; skipping resource_metadata reconciliation")
        return

    admin_id = str(admin_user.id)
    await _reconcile_workflow_metadata(sf, admin_id)
    await _reconcile_agent_metadata(sf, admin_id)


async def _seed_bundled_resources() -> None:
    """Provision manifest resources once an active super admin exists."""
    from sqlalchemy import select

    from app.agentplatform.rbac_models import UserModel, UserRole
    from app.agentplatform.resource_runtime import ResourceStorage, seed_bundled_resources
    from deerflow.config.paths import get_paths
    from deerflow.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is None:
        return
    async with sf() as session:
        admin = (await session.execute(select(UserModel.id).where(UserModel.role == UserRole.SUPER_ADMIN, UserModel.disabled.is_not(True)).limit(1))).scalar_one_or_none()
    if admin is None:
        logger.info("No active super_admin found; skipping bundled resource seed")
        return
    repo_root = Path(__file__).resolve().parents[3]
    await seed_bundled_resources(
        sf,
        ResourceStorage(get_paths().base_dir, allow_scanned_executables=True),
        manifest_path=repo_root / "bundled-resources.json",
        source_root=repo_root,
        owner_id=str(admin),
        conflict_policy="keep",
    )


async def _resolve_resource_owner(sf, raw_owner: str | None) -> tuple[str | None, str | None]:
    """Resolve a raw owner reference to a valid ``(owner_id, department_id)`` pair.

    Accepts either a ``users_ext.id`` (UUID) or a ``users_ext.username`` (email).
    Returns ``(None, None)`` when the reference is ``system``, empty, or cannot
    be matched to an existing user — callers then fall back to the super_admin.
    """
    from sqlalchemy import or_, select

    from app.agentplatform.rbac_models import UserModel

    if not raw_owner or raw_owner == "system":
        return None, None
    try:
        async with sf() as session:
            row = (await session.execute(select(UserModel).where(or_(UserModel.id == raw_owner, UserModel.username == raw_owner)))).scalar_one_or_none()
    except Exception as e:
        logger.warning("Failed to resolve resource owner '%s': %s", raw_owner, e)
        return None, None
    if row is None:
        return None, None
    department_id = str(row.department_id) if row.department_id else None
    return str(row.id), department_id


async def _reconcile_workflow_metadata(sf, admin_id: str) -> None:
    """Startup hook: create resource_metadata for workflow definitions lacking one.

    Enumerates the latest definition of every workflow and backfills a private
    metadata record owned by the definition's creator (falling back to the
    super_admin when creator resolution fails). Idempotent — existing records
    are never touched.
    """
    from app.agentplatform.workflow_runtime import WorkflowV2Store
    from app.gateway.utils import ResourceMetadataStore

    try:
        definitions, _ = await WorkflowV2Store(sf).list_latest_definitions(limit=100_000, offset=0)
    except Exception as e:
        logger.warning("Failed to enumerate workflow definitions for reconciliation: %s", e)
        return

    store = ResourceMetadataStore("workflow")
    reconciled = 0
    for definition in definitions:
        if await store.load_meta(definition.workflow_name):
            continue
        owner_id, dept_id = await _resolve_resource_owner(sf, definition.created_by)
        if await store.save_meta(
            definition.workflow_name,
            {"owner_id": owner_id or admin_id, "department_id": dept_id, "visibility": "private"},
        ):
            reconciled += 1

    if reconciled:
        logger.info("Reconciled %d workflow(s) — created missing resource_metadata records", reconciled)


async def _reconcile_agent_metadata(sf, admin_id: str) -> None:
    """Startup hook: create resource_metadata for catalog agents lacking one.

    Reads active agent resources from the catalog and backfills a metadata
    record owned by the resource owner (falling back to the super_admin).
    Visibility mirrors the catalog resource. Idempotent — existing records
    are never touched.
    """
    from sqlalchemy import select

    from app.agentplatform.resource_models import Resource
    from app.gateway.utils import ResourceMetadataStore

    store = ResourceMetadataStore("agent")
    reconciled = 0
    async with sf() as session:
        rows = list(
            (
                await session.execute(
                    select(Resource).where(
                        Resource.type == "agent",
                        Resource.lifecycle_status == "active",
                    )
                )
            ).scalars()
        )
    for row in rows:
        if await store.load_meta(row.id):
            continue
        owner_id = None
        dept_id = None
        if row.owner_id:
            owner_id, dept_id = await _resolve_resource_owner(sf, row.owner_id)
        if await store.save_meta(
            row.id,
            {
                "owner_id": owner_id or admin_id,
                "department_id": dept_id,
                "visibility": row.visibility,
            },
        ):
            reconciled += 1

    if reconciled:
        logger.info("Reconciled %d agent(s) — created missing resource_metadata records", reconciled)


async def _reconcile_canonical_resource_storage() -> None:
    """Fail startup on broken DB pointers and report recoverable orphan files."""

    from app.agentplatform.resource_runtime import ResourceStorage, reconcile_catalog_storage
    from deerflow.config.paths import get_paths
    from deerflow.persistence.engine import get_session_factory

    session_factory = get_session_factory()
    if session_factory is None:
        return
    async with session_factory() as session:
        report = await reconcile_catalog_storage(session, ResourceStorage(get_paths().base_dir))
    orphans = {
        "unreferenced_versions": report.unreferenced_versions,
        "orphan_staging": report.orphan_staging,
        "orphan_drafts": report.orphan_drafts,
    }
    if any(orphans.values()):
        logger.warning("Canonical resource storage has recoverable orphans; no files were removed: %s", orphans)


async def _knowledge_reconciliation_loop() -> None:
    """Run read-only published-revision reconciliation on a fixed interval."""

    from app.agentplatform.knowledge.ragflow import configured_ragflow_provider
    from app.agentplatform.knowledge.reconciliation import (
        configured_interval_seconds,
        run_reconciliation,
    )
    from deerflow.persistence.engine import get_session_factory

    while True:
        interval = configured_interval_seconds()
        if interval <= 0:
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(interval)
        provider = configured_ragflow_provider()
        session_factory = get_session_factory()
        if provider is None or session_factory is None:
            continue
        try:
            await run_reconciliation(session_factory, provider=provider, trigger="scheduled")
        except Exception:
            logger.exception("Knowledge reconciliation pass failed (non-fatal)")


async def _run_startup_trash_sweep(app: FastAPI, startup_config) -> None:
    """One trash retention sweep at gateway startup (Phase-2 spec §8.3).

    Runs beside the lazy trigger on the trash listing — no daemon, no
    scheduler (§15.9). Sweeps every user (``user_id=None``) with the
    configured retention window, including the full reconciliation. A sweep
    failure is logged and never blocks gateway readiness; the lifespan runs
    this as a background task and awaits it (bounded) on shutdown, cancelling
    it when the budget runs out.
    """
    try:
        from deerflow.config.paths import get_paths
        from deerflow.config.projects_config import ProjectsConfig
        from deerflow.projects.trash import run_trash_retention_sweep

        project_document_repo = getattr(app.state, "project_document_repo", None)
        if project_document_repo is None:
            return
        projects_config = getattr(startup_config, "projects", None)
        retention_days = projects_config.trash_retention_days if projects_config is not None else ProjectsConfig().trash_retention_days
        sweep_report = await run_trash_retention_sweep(project_document_repo, get_paths(), retention_days=retention_days, user_id=None)
        if sweep_report.purged or sweep_report.orphans_removed or sweep_report.staging_removed or sweep_report.content_missing:
            logger.info(
                "Trash retention sweep: purged=%d failures=%d orphans=%d staging=%d content_missing=%d",
                sweep_report.purged,
                sweep_report.purge_failures,
                sweep_report.orphans_removed,
                sweep_report.staging_removed,
                len(sweep_report.content_missing),
            )
    except Exception:
        logger.warning("Trash retention sweep skipped", exc_info=True)


async def _shutdown_startup_trash_sweep(app: FastAPI) -> None:
    """Bounded shutdown wait for the background startup sweep (§8.3).

    Waits ``_SHUTDOWN_HOOK_TIMEOUT_SECONDS`` for an in-flight sweep and
    cancels it when the budget runs out. The shield keeps that wait bounded
    without killing the sweep, so an overrun must be cancelled here: the
    all-users reconciliation reads through the document repo and the DB
    engine, and leaving it running would have it walk rows and files while
    the teardown below disposes both underneath it.
    """
    task = getattr(app.state, "startup_trash_sweep_task", None)
    if task is None or task.done():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=_SHUTDOWN_HOOK_TIMEOUT_SECONDS)
    except TimeoutError:
        # Cancellation lands at the sweep's next await; ``_run_startup_trash_sweep``
        # only catches ``Exception``, so ``CancelledError`` propagates. A
        # ``cancel()`` that returns False means the sweep finished inside the
        # window between the deadline firing and this call — report that as
        # the late finish it is, not as a cancellation that never happened.
        cancelled = task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        if cancelled:
            logger.warning(
                "Startup trash sweep exceeded %.1fs during shutdown; cancelled and proceeding with worker exit.",
                _SHUTDOWN_HOOK_TIMEOUT_SECONDS,
            )
        else:
            logger.info(
                "Startup trash sweep finished just after the %.1fs shutdown budget; proceeding with worker exit.",
                _SHUTDOWN_HOOK_TIMEOUT_SECONDS,
            )
    except Exception:
        logger.exception("Startup trash sweep failed during shutdown")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""

    # Load config and check necessary environment variables at startup.
    # `startup_config` is a local snapshot used only for one-shot bootstrap
    # work (logging level, langgraph_runtime engines, channels). Request-time
    # config resolution always routes through `get_app_config()` in
    # `app/gateway/deps.py::get_config()` so `config.yaml` edits become
    # visible without a process restart. We deliberately do NOT cache this
    # snapshot on `app.state` to keep that contract enforceable.
    try:
        startup_config = get_app_config()
        from deerflow.config.subagent_batches_config import SubagentBatchesConfig
        from deerflow.config.subagent_runtime_config import SubagentRuntimeConfig
        from deerflow.subagents.capacity import configure_subagent_execution_capacity

        subagent_runtime_config = getattr(startup_config, "subagent_runtime", None)
        if not isinstance(subagent_runtime_config, SubagentRuntimeConfig):
            subagent_runtime_config = SubagentRuntimeConfig()
        subagent_batches_config = getattr(startup_config, "subagent_batches", None)
        if not isinstance(subagent_batches_config, SubagentBatchesConfig):
            subagent_batches_config = SubagentBatchesConfig()
        configure_subagent_execution_capacity(subagent_runtime_config)
        apply_logging_level(startup_config.log_level)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration during gateway startup: {e}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e
    config = get_gateway_config()
    logger.info(f"Starting API Gateway on {config.host}:{config.port}")

    try:
        setup_monocle_tracing_if_enabled()
    except Exception:
        logger.exception("Monocle tracing setup failed; continuing without tracing")

    # Initialize LangGraph runtime components (StreamBridge, RunManager, checkpointer, store)
    async with langgraph_runtime(app, startup_config):
        logger.info("LangGraph runtime initialised")
        from app.agentplatform.knowledge.worker import KnowledgeWorker

        knowledge_worker = KnowledgeWorker()
        knowledge_worker.start()
        app.state.knowledge_worker_available = True
        try:
            from app.agentplatform.knowledge.ragflow import configured_ragflow_provider

            app.state.knowledge_provider_available = configured_ragflow_provider() is not None
        except Exception:
            app.state.knowledge_provider_available = False

        # Check admin bootstrap state and migrate orphan threads after admin exists.
        # Must run AFTER langgraph_runtime so app.state.store is available for thread migration
        await _ensure_admin_user(app)

        # Detection only: startup must never remove user state automatically.
        try:
            from app.gateway.user_deletion import report_user_state_anomalies
            from deerflow.config.paths import get_paths

            await report_user_state_anomalies(get_paths())
        except Exception:
            logger.exception("User-state anomaly audit failed (non-fatal)")

        # Reconcile workflow/agent resource_metadata for definitions lacking a
        # DB record. Must run AFTER _ensure_admin_user so the super_admin ID
        # is available as the fallback owner.
        try:
            await _reconcile_workflow_and_agent_metadata()
        except Exception:
            logger.exception("Skill metadata reconciliation failed (non-fatal)")

        try:
            await _seed_bundled_resources()
        except Exception:
            logger.exception("Bundled resource seed failed (non-fatal)")

        # Published catalog pointers must be usable before the gateway accepts
        # runs. Orphan files are only reported; startup never deletes them.
        await _reconcile_canonical_resource_storage()

        # Phase-2 trash tier (§8.3): one retention sweep at startup, beside
        # the lazy trigger on the trash listing — no daemon, no scheduler.
        # Runs after langgraph_runtime so app.state.project_document_repo is
        # available. The per-user reconciliation walks every row and file, so
        # it is scheduled as a background task: gateway readiness never waits
        # on it, a failure is logged by the task itself, and shutdown awaits
        # the in-flight sweep (bounded, cancelled on overrun) before the
        # runtime is torn down.
        app.state.startup_trash_sweep_task = asyncio.create_task(_run_startup_trash_sweep(app, startup_config))

        try:
            from app.gateway.services import launch_scheduled_thread_run
            from app.scheduler import ScheduledTaskService

            if getattr(app.state, "scheduled_task_repo", None) is not None and getattr(app.state, "scheduled_task_run_repo", None) is not None:
                scheduled_task_service = ScheduledTaskService(
                    task_repo=app.state.scheduled_task_repo,
                    task_run_repo=app.state.scheduled_task_run_repo,
                    launch_run=lambda **kwargs: launch_scheduled_thread_run(app=app, **kwargs),
                    poll_interval_seconds=startup_config.scheduler.poll_interval_seconds,
                    lease_seconds=startup_config.scheduler.lease_seconds,
                    max_concurrent_runs=startup_config.scheduler.max_concurrent_runs,
                    queue_timeout_seconds=startup_config.scheduler.queue_timeout_seconds,
                    multi_instance=startup_config.scheduler.multi_instance,
                    run_lease_grace_seconds=startup_config.run_ownership.grace_seconds,
                )
                app.state.scheduled_task_service = scheduled_task_service
                if startup_config.scheduler.enabled:
                    await scheduled_task_service.start()
        except Exception:
            logger.exception("Failed to initialize scheduled task service")
            # If an enabled scheduler rejects start(), keep that rejection as a
            # lifespan failure instead of exposing a half-started service.
            if startup_config.scheduler.enabled:
                raise

        # Start IM channel service only after scheduler recovery succeeds, so a
        # fail-closed scheduler startup cannot strand channel-owned tasks before
        # the lifespan reaches its normal shutdown boundary.
        try:
            from app.channels.service import start_channel_service

            # Closure over `app` (mirrors ScheduledTaskService's `launch_run`
            # above) rather than resolving `app.state.stream_bridge` here
            # directly: `stream_bridge` is a STARTUP_ONLY_FIELDS singleton set
            # once, above, by `langgraph_runtime(app, startup_config)`, so
            # either shape is safe by construction — the closure is just the
            # more defensive/consistent-with-precedent form, and it is what
            # ChannelManager's follow-up-drain watcher (issue #4121 Slice 2)
            # uses to reach the same StreamBridge every other run consumer
            # goes through `get_stream_bridge(request)` for.
            channel_service = await start_channel_service(
                startup_config,
                get_stream_bridge=lambda: getattr(app.state, "stream_bridge", None),
            )
            logger.info("Channel service started: %s", channel_service.get_status())
        except Exception:
            logger.exception("No IM channels configured or channel service failed to start")

        from app.gateway.services import launch_mcp_task_notification_run
        from app.mcp_tasks import McpTaskService
        from deerflow.config.extensions_config import ExtensionsConfig
        from deerflow.config.mcp_tasks_config import McpTasksConfig
        from deerflow.mcp.task_tool_caller import McpTaskToolCaller
        from deerflow.mcp.tasks import (
            ORDINARY_MCP_TASK_DRIVER,
            McpTaskDriverRegistry,
            OrdinaryMcpTaskDriver,
        )
        from deerflow.mcp.tasks.runtime import (
            configured_task_toolset_count,
            set_mcp_task_config_snapshot,
            set_mcp_task_submitter,
            validate_mcp_task_runtime_configuration,
        )

        task_extensions_config = ExtensionsConfig.from_file()
        mcp_tasks_config = getattr(startup_config, "mcp_tasks", McpTasksConfig())
        mcp_task_repo = getattr(app.state, "mcp_task_repo", None)
        app.state.mcp_tasks_available = False
        set_mcp_task_submitter(None)
        set_mcp_task_config_snapshot(task_extensions_config)
        validate_mcp_task_runtime_configuration(
            mcp_tasks_config=mcp_tasks_config,
            extensions_config=task_extensions_config,
            repository_available=mcp_task_repo is not None,
        )
        if mcp_task_repo is not None:
            mcp_task_drivers = McpTaskDriverRegistry()
            if configured_task_toolset_count(task_extensions_config):
                mcp_task_drivers.register(
                    ORDINARY_MCP_TASK_DRIVER,
                    OrdinaryMcpTaskDriver(McpTaskToolCaller(task_extensions_config)),
                )
            mcp_task_service = McpTaskService(
                repository=mcp_task_repo,
                drivers=mcp_task_drivers,
                poll_interval_seconds=mcp_tasks_config.poll_interval_seconds,
                lease_seconds=mcp_tasks_config.lease_seconds,
                max_concurrent_polls=mcp_tasks_config.max_concurrent_polls,
                max_poll_backoff_seconds=mcp_tasks_config.max_poll_backoff_seconds,
                input_required_poll_interval_seconds=mcp_tasks_config.input_required_poll_interval_seconds,
                tracking_degraded_after_errors=mcp_tasks_config.tracking_degraded_after_errors,
                max_result_bytes=mcp_tasks_config.max_result_bytes,
                result_preview_max_chars=mcp_tasks_config.result_preview_max_chars,
                launch_notification=lambda **kwargs: launch_mcp_task_notification_run(app=app, **kwargs),
                get_run=lambda run_id, **kwargs: app.state.run_manager.get(
                    run_id,
                    raise_on_store_error=True,
                    **kwargs,
                ),
            )
            app.state.mcp_task_drivers = mcp_task_drivers
            app.state.mcp_task_service = mcp_task_service
            if mcp_tasks_config.enabled:
                await mcp_task_service.start()
                set_mcp_task_submitter(mcp_task_service)
                app.state.mcp_tasks_available = True

        from app.subagent_batches import SubagentBatchService
        from deerflow.subagents.batch_runtime import set_subagent_batch_submitter

        batch_repo = getattr(app.state, "subagent_batch_repo", None)
        app.state.subagent_batches_available = False
        set_subagent_batch_submitter(None)
        if subagent_batches_config.enabled and batch_repo is None:
            raise RuntimeError("subagent_batches.enabled requires database.backend sqlite or postgres")
        if batch_repo is not None:
            batch_service = SubagentBatchService(
                repository=batch_repo,
                config=subagent_batches_config,
                runtime_config=subagent_runtime_config,
            )
            app.state.subagent_batch_service = batch_service
            if subagent_batches_config.enabled:
                await batch_service.start()
                set_subagent_batch_submitter(batch_service)
                app.state.subagent_batches_available = True

        # Periodic published-revision reconciliation (read-only, ticket 05).
        # Disabled unless knowledge.reconciliation_interval_seconds > 0.
        reconciliation_task = asyncio.create_task(_knowledge_reconciliation_loop())

        yield

        reconciliation_task.cancel()
        await _shutdown_startup_trash_sweep(app)
        try:
            await reconciliation_task
        except asyncio.CancelledError:
            pass

        # Stop channel service on shutdown (bounded to prevent worker hang)
        try:
            from app.channels.service import stop_channel_service

            await asyncio.wait_for(
                stop_channel_service(),
                timeout=_SHUTDOWN_HOOK_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "Channel service shutdown exceeded %.1fs; proceeding with worker exit.",
                _SHUTDOWN_HOOK_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Failed to stop channel service")
        await knowledge_worker.stop()
        app.state.knowledge_worker_available = False

        # Upstream v2.1.0: the frozen MCP task-server snapshot is owned by one
        # Gateway process lifetime. Clearing it here keeps tool discovery and
        # background calls from validating against a stale process's config
        # after a hot restart inside the same interpreter.
        from deerflow.mcp.tasks.runtime import set_mcp_task_config_snapshot

        set_mcp_task_config_snapshot(None)

    logger.info("Shutting down API Gateway")


def _http_exception_payload(exc: HTTPException, *, include_auth_details: bool = False) -> dict:
    """Build the response body for an HTTPException.

    Structured dict details (e.g. visibility closure violations carrying
    ``code``/``message``/``violations``) keep the envelope but pass through
    as the ``detail`` field so clients can render localized, actionable
    errors. Plain string details keep the legacy envelope verbatim.
    """
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("code") in {
        "visibility_closure_violation",
        "skill_outside_agent_closure",
        "token_expired",
        "token_invalid",
        "not_authenticated",
        "email_already_exists",
        "user_disabled",
        "system_already_initialized",
        "registration_disabled",
    }:
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": (
                    f"{detail['code']}: {detail.get('message', '')}"
                    if detail.get("code")
                    in {
                        "system_already_initialized",
                        "email_already_exists",
                    }
                    else detail.get("message", "")
                ),
            },
            "detail": detail,
        }
    if (
        include_auth_details
        and isinstance(detail, dict)
        and detail.get("code")
        in {
            "invalid_credentials",
            "token_expired",
            "token_invalid",
            "not_authenticated",
            "email_already_exists",
            "user_disabled",
        }
    ):
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"{detail['code']}: {detail.get('message', '')}",
            },
            "detail": detail,
        }
    return {
        "success": False,
        "data": None,
        "error": {"code": "INTERNAL_ERROR", "message": str(detail)},
        "detail": str(detail),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for structured error responses."""

    @app.exception_handler(ApiException)
    async def api_exception_handler(_request: Request, exc: ApiException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {"code": exc.code, "message": exc.message},
                "detail": exc.message,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_http_exception_payload(exc, include_auth_details=True),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Return only a sanitized projection (loc/msg/type) — never the raw
        # pydantic repr, which may leak internal model paths and payloads.
        issues = [
            {
                "loc": [str(item) for item in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        # Authentication request models historically expose FastAPI's
        # validation status (422).  Keep the gateway's sanitized 400 envelope
        # for other APIs while preserving that public auth contract.
        status_code = 422 if _request.url.path.startswith("/api/v1/auth/") else 400
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_REQUEST_BODY",
                    "message": "请求体格式不合法",
                    "issues": issues,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Safety net for any unhandled exception: log the full traceback with a
        # correlation id, but return a generic envelope so internal details
        # (stack traces, model paths, payloads) never reach the client.
        request_id = uuid.uuid4().hex[:12]
        logger.exception(
            "Unhandled exception (request_id=%s, method=%s, path=%s): %s",
            request_id,
            request.method,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": request_id},
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                    "request_id": request_id,
                },
            },
        )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    config = get_gateway_config()
    docs_url = "/docs" if config.enable_docs else None
    redoc_url = "/redoc" if config.enable_docs else None
    openapi_url = "/openapi.json" if config.enable_docs else None

    app = FastAPI(
        title="iDeer API Gateway",
        description="""
## iDeer API Gateway

API Gateway for iDeer - A LangGraph-based AI agent backend with sandbox execution capabilities.

### Features

- **Models Management**: Query and retrieve available AI models
- **MCP Configuration**: Manage Model Context Protocol (MCP) server configurations
- **Memory Management**: Access and manage global memory data for personalized conversations
- **Skills Management**: Query and manage skills and their enabled status
- **Artifacts**: Access thread artifacts and generated files
- **Health Monitoring**: System health check endpoints

### Architecture

LangGraph-compatible requests are routed through nginx to this gateway.
This gateway provides runtime endpoints for agent runs plus custom endpoints for models, MCP configuration, skills, and artifacts.
        """,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        openapi_tags=[
            {
                "name": "models",
                "description": "Operations for querying available AI models and their configurations",
            },
            {
                "name": "mcp",
                "description": "Manage Model Context Protocol (MCP) server configurations",
            },
            {
                "name": "memory",
                "description": "Access and manage global memory data for personalized conversations",
            },
            {
                "name": "skills",
                "description": "Manage skills and their configurations",
            },
            {
                "name": "artifacts",
                "description": "Access and download thread artifacts and generated files",
            },
            {
                "name": "uploads",
                "description": "Upload and manage user files for threads",
            },
            {
                "name": "threads",
                "description": "Manage iDeer thread-local filesystem data",
            },
            {
                "name": "agents",
                "description": "Create and manage custom agents with per-agent config and prompts",
            },
            {
                "name": "suggestions",
                "description": "Generate follow-up question suggestions for conversations",
            },
            {
                "name": "channels",
                "description": "Manage IM channel integrations (Feishu, Slack, Telegram)",
            },
            {
                "name": "assistants-compat",
                "description": "LangGraph Platform-compatible assistants API (stub)",
            },
            {
                "name": "runs",
                "description": "LangGraph Platform-compatible runs lifecycle (create, stream, cancel)",
            },
            {
                "name": "health",
                "description": "Health check and system status endpoints",
            },
            {
                "name": "admin",
                "description": "Admin management APIs for users, departments, and system configuration",
            },
            {
                "name": "audit",
                "description": "Audit log query APIs for tracking key operations",
            },
            {
                "name": "tools",
                "description": "Tool management APIs for listing, testing, and configuring tools",
            },
            {
                "name": "workflows",
                "description": "Workflow management APIs for creating, running, and monitoring YAML-based workflows",
            },
            {
                "name": "visibility-applications",
                "description": "Unified approval workflow for resource visibility changes across all resource types",
            },
        ],
    )

    # --- Global exception handlers for structured error responses ---
    register_exception_handlers(app)

    # Auth: reject unauthenticated requests to non-public paths (fail-closed safety net)
    app.add_middleware(AuthMiddleware)

    # Bind and expose a trace ID on every HTTP response, including streaming
    # responses and errors.
    app.add_middleware(TraceMiddleware)

    # CSRF: Double Submit Cookie pattern for state-changing requests
    app.add_middleware(CSRFMiddleware)

    # CORS: the unified nginx endpoint is same-origin by default. Split-origin
    # browser clients must opt in with this explicit Gateway allowlist so CORS
    # and CSRF origin checks share the same source of truth.
    cors_origins = sorted(get_configured_cors_origins())
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=list(CORS_EXPOSED_HEADERS),
        )

    # Include routers
    # Models API is mounted at /api/models
    app.include_router(models.router)

    # UUID-first canonical Skill, Agent, and Workflow resources API
    app.include_router(resources.router)

    # KnowledgeBase management retrieval tests share the /api/resources prefix
    app.include_router(knowledge_tests.router)

    # Automations API is mounted at /api/automations
    app.include_router(automations.router)

    # MCP API is mounted at /api/mcp
    app.include_router(mcp.router)

    # Thread-scoped durable MCP task API
    app.include_router(mcp_tasks.router)

    # Memory API is mounted at /api/memory
    app.include_router(memory.router)

    # Admin Skill Applications API is mounted at /api/admin/skill-applications
    app.include_router(admin_skill_applications.router)

    # Artifacts API is mounted at /api/threads/{thread_id}/artifacts
    app.include_router(artifacts.router)

    # Uploads API is mounted at /api/threads/{thread_id}/uploads
    app.include_router(uploads.router)

    # Thread cleanup API is mounted at /api/threads/{thread_id}
    app.include_router(threads.router)

    # Projects API is mounted at /api/projects (v2.1.0 convergence). The
    # scheduled-tasks router stays at its local mount position below, and the
    # upstream agents/subagents routers are deliberately NOT mounted: local
    # baseline keeps agent management behind the enterprise experts entries
    # (ledger D4), so their API surface is not newly exposed by this merge.
    app.include_router(projects.router)
    # Project document shelf API is mounted at /api/projects/{id}/documents
    app.include_router(project_documents.router)
    # Project conversation-files view is mounted at /api/projects/{id}/thread-files
    app.include_router(project_thread_files.router)
    # Trash API is mounted at /api/trash
    app.include_router(trash.router)
    # Suggestions API is mounted at /api/threads/{thread_id}/suggestions
    app.include_router(suggestions.router)

    # Channels API is mounted at /api/channels
    app.include_router(channels.router)

    # Device control-plane API is mounted at /api/devices.
    app.include_router(devices.router)

    # Assistants compatibility API (LangGraph Platform stub)
    app.include_router(assistants_compat.router)

    # Auth API is mounted at /api/v1/auth
    app.include_router(auth.router)
    app.include_router(user_preferences.router)

    # Feedback API is mounted at /api/threads/{thread_id}/runs/{run_id}/feedback
    app.include_router(feedback.router)

    # Thread Runs API (LangGraph Platform-compatible runs lifecycle)
    app.include_router(thread_runs.router)

    # Durable subagent batch progress and control API
    app.include_router(subagent_batches.router)

    # Stateless Runs API (stream/wait without a pre-existing thread)
    app.include_router(runs.router)

    # Admin API is mounted at /api/admin
    app.include_router(admin.router)

    # Audit Logs API is mounted at /api/admin/audit-logs
    app.include_router(audit_logs.router)
    app.include_router(admin_knowledge.router)

    # Tools API is mounted at /api/tools
    app.include_router(tools.router)

    # Visibility Applications API is mounted at /api/visibility-applications
    app.include_router(visibility_applications.router)

    # Upstream convergence routers: the frontend entries that ship with the
    # merged tree call these, so mount them exactly like deerflow main does.
    app.include_router(features.router)

    # Upstream v2.1.0: the merged capabilities skills tab mounts the upstream
    # SkillGallery/SkillExportDialog, whose enable/export calls target
    # /api/skills/custom*. Mount the skills router so the shipped UI resolves
    # (AuthMiddleware + authz route permissions guard it like every router).
    app.include_router(skills.router)

    # Integrations API is mounted at /api/integrations
    app.include_router(integrations.router)

    # Scheduled Tasks API is mounted at /api/scheduled-tasks
    app.include_router(scheduled_tasks.router)

    # Input Polish API is mounted at /api/input-polish
    app.include_router(input_polish.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Service health status information.
        """
        return {"status": "healthy", "service": "deer-flow-gateway"}

    # Extension routes are deliberately mounted after every host route so a
    # plugin can never shadow a canonical Gateway endpoint.
    _configure_extensions(app)

    return app


# Create app instance for uvicorn
app = create_app()
