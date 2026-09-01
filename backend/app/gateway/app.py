import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.gateway.auth_middleware import AuthMiddleware
from app.gateway.config import get_gateway_config
from app.gateway.csrf_middleware import CSRFMiddleware, get_configured_cors_origins
from app.gateway.deps import langgraph_runtime
from app.gateway.error_codes import ApiException
from app.gateway.routers import (
    admin,
    admin_skill_applications,
    artifacts,
    assistants_compat,
    audit_logs,
    auth,
    automations,
    channels,
    feedback,
    mcp,
    memory,
    models,
    resources,
    runs,
    suggestions,
    thread_runs,
    threads,
    tools,
    uploads,
    visibility_applications,
)
from ideer.config import app_config as ideer_app_config
from ideer.config.app_config import apply_logging_level

AppConfig = ideer_app_config.AppConfig
get_app_config = ideer_app_config.get_app_config

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

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel, UserRole

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

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel, UserRole

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

    from ideer.config.paths import get_paths
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel, UserRole
    from ideer.resources.bundled import seed_bundled_resources
    from ideer.resources.storage import ResourceStorage

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

    from ideer.persistence.models.user import UserModel

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
    from app.gateway.utils import ResourceMetadataStore
    from ideer.workflows.v2.store import WorkflowV2Store

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

    from app.gateway.utils import ResourceMetadataStore
    from ideer.persistence.models.resource_catalog import Resource

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

    from ideer.config.paths import get_paths
    from ideer.persistence.engine import get_session_factory
    from ideer.resources.reconciliation import reconcile_catalog_storage
    from ideer.resources.storage import ResourceStorage

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
        apply_logging_level(startup_config.log_level)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration during gateway startup: {e}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e
    config = get_gateway_config()
    logger.info(f"Starting API Gateway on {config.host}:{config.port}")

    # Initialize LangGraph runtime components (StreamBridge, RunManager, checkpointer, store)
    async with langgraph_runtime(app, startup_config):
        logger.info("LangGraph runtime initialised")

        # Check admin bootstrap state and migrate orphan threads after admin exists.
        # Must run AFTER langgraph_runtime so app.state.store is available for thread migration
        await _ensure_admin_user(app)

        # Detection only: startup must never remove user state automatically.
        try:
            from app.gateway.user_deletion import report_user_state_anomalies
            from ideer.config.paths import get_paths

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

        # Start IM channel service if any channels are configured
        try:
            from app.channels.service import start_channel_service

            channel_service = await start_channel_service(startup_config)
            logger.info("Channel service started: %s", channel_service.get_status())
        except Exception:
            logger.exception("No IM channels configured or channel service failed to start")

        yield

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

    logger.info("Shutting down API Gateway")


def _http_exception_payload(exc: HTTPException) -> dict:
    """Build the response body for an HTTPException.

    Structured dict details (e.g. visibility closure violations carrying
    ``code``/``message``/``violations``) keep the envelope but pass through
    as the ``detail`` field so clients can render localized, actionable
    errors. Plain string details keep the legacy envelope verbatim.
    """
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("code") == "visibility_closure_violation":
        return {
            "success": False,
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": detail.get("message", "")},
            "detail": detail,
        }
    return {
        "success": False,
        "data": None,
        "error": {"code": "INTERNAL_ERROR", "message": str(detail)},
        "detail": str(detail),
    }


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
            content=_http_exception_payload(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "data": None,
                "error": {"code": "INVALID_REQUEST_BODY", "message": str(exc)},
            },
        )

    # Auth: reject unauthenticated requests to non-public paths (fail-closed safety net)
    app.add_middleware(AuthMiddleware)

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
        )

    # Include routers
    # Models API is mounted at /api/models
    app.include_router(models.router)

    # UUID-first canonical Skill, Agent, and Workflow resources API
    app.include_router(resources.router)

    # Automations API is mounted at /api/automations
    app.include_router(automations.router)

    # MCP API is mounted at /api/mcp
    app.include_router(mcp.router)

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

    # Suggestions API is mounted at /api/threads/{thread_id}/suggestions
    app.include_router(suggestions.router)

    # Channels API is mounted at /api/channels
    app.include_router(channels.router)

    # Assistants compatibility API (LangGraph Platform stub)
    app.include_router(assistants_compat.router)

    # Auth API is mounted at /api/v1/auth
    app.include_router(auth.router)

    # Feedback API is mounted at /api/threads/{thread_id}/runs/{run_id}/feedback
    app.include_router(feedback.router)

    # Thread Runs API (LangGraph Platform-compatible runs lifecycle)
    app.include_router(thread_runs.router)

    # Stateless Runs API (stream/wait without a pre-existing thread)
    app.include_router(runs.router)

    # Admin API is mounted at /api/admin
    app.include_router(admin.router)

    # Audit Logs API is mounted at /api/admin/audit-logs
    app.include_router(audit_logs.router)

    # Tools API is mounted at /api/tools
    app.include_router(tools.router)

    # Visibility Applications API is mounted at /api/visibility-applications
    app.include_router(visibility_applications.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Service health status information.
        """
        return {"status": "healthy", "service": "ideer-gateway"}

    return app


# Create app instance for uvicorn
app = create_app()
