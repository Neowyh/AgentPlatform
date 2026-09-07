"""Memory API router for retrieving and managing global memory data."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agentplatform.memory_adapter import (
    clear_memory_data,
    create_memory_fact,
    delete_memory_fact,
    get_memory_data,
    import_memory_data,
    reload_memory_data,
    update_memory_fact,
)
from app.agentplatform.rbac_models import UserModel, UserRole
from app.gateway.authz import get_current_rbac_user, require_role
from deerflow.agents.memory import MemoryConflictError, MemoryCorruptionError
from deerflow.config.memory_config import get_memory_config
from deerflow.runtime.user_context import get_effective_user_id

router = APIRouter(prefix="/api", tags=["memory"])


class ContextSection(BaseModel):
    """Model for context sections (user and history)."""

    summary: str = Field(default="", description="Summary content")
    updatedAt: str = Field(default="", description="Last update timestamp")


class UserContext(BaseModel):
    """Model for user context."""

    workContext: ContextSection = Field(default_factory=ContextSection)
    personalContext: ContextSection = Field(default_factory=ContextSection)
    topOfMind: ContextSection = Field(default_factory=ContextSection)


class HistoryContext(BaseModel):
    """Model for history context."""

    recentMonths: ContextSection = Field(default_factory=ContextSection)
    earlierContext: ContextSection = Field(default_factory=ContextSection)
    longTermBackground: ContextSection = Field(default_factory=ContextSection)


class Fact(BaseModel):
    """Model for a memory fact."""

    id: str = Field(..., description="Unique identifier for the fact")
    content: str = Field(..., description="Fact content")
    category: str = Field(default="context", description="Fact category")
    confidence: float = Field(default=0.5, description="Confidence score (0-1)")
    createdAt: str = Field(default="", description="Creation timestamp")
    source: str = Field(default="unknown", description="Source thread ID")
    sourceError: str | None = Field(default=None, description="Optional description of the prior mistake or wrong approach")


class MemoryResponse(BaseModel):
    """Response model for memory data."""

    version: str = Field(default="1.0", description="Memory schema version")
    lastUpdated: str = Field(default="", description="Last update timestamp")
    user: UserContext = Field(default_factory=UserContext)
    history: HistoryContext = Field(default_factory=HistoryContext)
    facts: list[Fact] = Field(default_factory=list)


def _map_memory_fact_value_error(exc: ValueError) -> HTTPException:
    """Convert updater validation errors into stable API responses."""
    if exc.args and exc.args[0] == "confidence":
        detail = "Invalid confidence value; must be between 0 and 1."
    else:
        detail = "Memory fact content cannot be empty."
    return HTTPException(status_code=400, detail=detail)


def _memory_not_supported(operation: str) -> HTTPException:
    """Expose an unsupported optional MemoryManager capability as HTTP 501."""
    return HTTPException(
        status_code=501,
        detail=f"Memory operation '{operation}' is not supported by the configured backend.",
    )


class FactCreateRequest(BaseModel):
    """Request model for creating a memory fact."""

    content: str = Field(..., min_length=1, description="Fact content")
    category: str = Field(default="context", description="Fact category")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score (0-1)")


class FactPatchRequest(BaseModel):
    """PATCH request model that preserves existing values for omitted fields."""

    content: str | None = Field(default=None, min_length=1, description="Fact content")
    category: str | None = Field(default=None, description="Fact category")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Confidence score (0-1)")


class MemoryConfigResponse(BaseModel):
    """DeerFlow memory configuration with legacy display fields preserved."""

    enabled: bool = Field(..., description="Whether memory is enabled")
    mode: str = Field(default="middleware", description="Memory operation mode")
    injection_enabled: bool = Field(..., description="Whether memory injection is enabled")
    shutdown_flush_timeout_seconds: float = Field(default=30.0, description="Shutdown flush budget")
    manager_class: str = Field(default="deermem", description="Configured memory backend")
    backend_config: dict[str, Any] = Field(default_factory=dict, description="Backend-private memory configuration")
    # Deprecated display fields retained for older clients. They are derived
    # from backend_config when using the DeerFlow schema.
    storage_path: str | None = Field(default=None, description="Legacy memory storage root")
    debounce_seconds: int | None = Field(default=None, description="Legacy debounce setting")
    max_facts: int | None = Field(default=None, description="Legacy maximum fact count")
    fact_confidence_threshold: float | None = Field(default=None, description="Legacy fact confidence threshold")
    max_injection_tokens: int | None = Field(default=None, description="Legacy injection token budget")


class MemoryStatusResponse(BaseModel):
    """Response model for memory status."""

    config: MemoryConfigResponse
    data: MemoryResponse


def _memory_config_response(config: Any) -> MemoryConfigResponse:
    """Normalize DeerFlow and legacy config objects at the HTTP boundary."""
    values = vars(config)
    backend_config = dict(values.get("backend_config") or {})
    return MemoryConfigResponse(
        enabled=bool(values.get("enabled", True)),
        mode=str(values.get("mode", "middleware")),
        injection_enabled=bool(values.get("injection_enabled", True)),
        shutdown_flush_timeout_seconds=float(values.get("shutdown_flush_timeout_seconds", 30.0)),
        manager_class=str(values.get("manager_class", "deermem")),
        backend_config=backend_config,
        storage_path=backend_config.get("storage_path", values.get("storage_path")),
        debounce_seconds=backend_config.get("debounce_seconds", values.get("debounce_seconds")),
        max_facts=backend_config.get("max_facts", values.get("max_facts")),
        fact_confidence_threshold=backend_config.get("fact_confidence_threshold", values.get("fact_confidence_threshold")),
        max_injection_tokens=backend_config.get("max_injection_tokens", values.get("max_injection_tokens")),
    )


@router.get(
    "/memory",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Get Memory Data",
    description="Retrieve the current global memory data including user context, history, and facts.",
)
async def get_memory() -> MemoryResponse:
    """Get the current global memory data.

    Returns:
        The current memory data with user context, history, and facts.

    Example Response:
        ```json
        {
            "version": "1.0",
            "lastUpdated": "2024-01-15T10:30:00Z",
            "user": {
                "workContext": {"summary": "Working on iDeer project", "updatedAt": "..."},
                "personalContext": {"summary": "Prefers concise responses", "updatedAt": "..."},
                "topOfMind": {"summary": "Building memory API", "updatedAt": "..."}
            },
            "history": {
                "recentMonths": {"summary": "Recent development activities", "updatedAt": "..."},
                "earlierContext": {"summary": "", "updatedAt": ""},
                "longTermBackground": {"summary": "", "updatedAt": ""}
            },
            "facts": [
                {
                    "id": "fact_abc123",
                    "content": "User prefers TypeScript over JavaScript",
                    "category": "preference",
                    "confidence": 0.9,
                    "createdAt": "2024-01-15T10:30:00Z",
                    "source": "thread_xyz"
                }
            ]
        }
        ```
    """
    try:
        memory_data = get_memory_data(user_id=get_effective_user_id())
    except MemoryCorruptionError as exc:
        raise HTTPException(status_code=500, detail="Stored memory data is corrupted.") from exc
    except NotImplementedError as exc:
        raise _memory_not_supported("read") from exc
    return MemoryResponse(**memory_data)


@router.post(
    "/memory/reload",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Reload Memory Data",
    description="Reload memory data from the storage file, refreshing the in-memory cache.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def reload_memory(
    current_user: UserModel = Depends(get_current_rbac_user),
) -> MemoryResponse:
    """Reload memory data from file.

    This forces a reload of the memory data from the storage file,
    useful when the file has been modified externally.

    Returns:
        The reloaded memory data.
    """
    try:
        memory_data = reload_memory_data(user_id=get_effective_user_id())
    except NotImplementedError as exc:
        raise _memory_not_supported("reload") from exc
    return MemoryResponse(**memory_data)


@router.delete(
    "/memory",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Clear All Memory Data",
    description="Delete all saved memory data and reset the memory structure to an empty state.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def clear_memory(
    current_user: UserModel = Depends(get_current_rbac_user),
) -> MemoryResponse:
    """Clear all persisted memory data."""
    try:
        memory_data = clear_memory_data(user_id=get_effective_user_id())
    except NotImplementedError as exc:
        raise _memory_not_supported("clear") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to clear memory data.") from exc

    return MemoryResponse(**memory_data)


@router.post(
    "/memory/facts",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Create Memory Fact",
    description="Create a single saved memory fact manually.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def create_memory_fact_endpoint(
    request: FactCreateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> MemoryResponse:
    """Create a single fact manually."""
    try:
        memory_data = create_memory_fact(
            content=request.content,
            category=request.category,
            confidence=request.confidence,
            user_id=get_effective_user_id(),
        )
    except ValueError as exc:
        raise _map_memory_fact_value_error(exc) from exc
    except MemoryConflictError as exc:
        raise HTTPException(status_code=409, detail="Memory changed concurrently; reload and retry.") from exc
    except NotImplementedError as exc:
        raise _memory_not_supported("create_fact") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to create memory fact.") from exc

    return MemoryResponse(**memory_data)


@router.delete(
    "/memory/facts/{fact_id}",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Delete Memory Fact",
    description="Delete a single saved memory fact by its fact id.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def delete_memory_fact_endpoint(
    fact_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> MemoryResponse:
    """Delete a single fact from memory by fact id."""
    try:
        memory_data = delete_memory_fact(fact_id, user_id=get_effective_user_id())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Memory fact '{fact_id}' not found.") from exc
    except NotImplementedError as exc:
        raise _memory_not_supported("delete_fact") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to delete memory fact.") from exc

    return MemoryResponse(**memory_data)


@router.patch(
    "/memory/facts/{fact_id}",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Patch Memory Fact",
    description="Partially update a single saved memory fact by its fact id while preserving omitted fields.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_memory_fact_endpoint(
    fact_id: str,
    request: FactPatchRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> MemoryResponse:
    """Partially update a single fact manually."""
    try:
        memory_data = update_memory_fact(
            fact_id=fact_id,
            content=request.content,
            category=request.category,
            confidence=request.confidence,
            user_id=get_effective_user_id(),
        )
    except ValueError as exc:
        raise _map_memory_fact_value_error(exc) from exc
    except MemoryConflictError as exc:
        raise HTTPException(status_code=409, detail="Memory changed concurrently; reload and retry.") from exc
    except NotImplementedError as exc:
        raise _memory_not_supported("update_fact") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Memory fact '{fact_id}' not found.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to update memory fact.") from exc

    return MemoryResponse(**memory_data)


@router.get(
    "/memory/export",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Export Memory Data",
    description="Export the current global memory data as JSON for backup or transfer.",
)
async def export_memory() -> MemoryResponse:
    """Export the current memory data."""
    try:
        memory_data = get_memory_data(user_id=get_effective_user_id())
    except MemoryCorruptionError as exc:
        raise HTTPException(status_code=500, detail="Stored memory data is corrupted.") from exc
    except NotImplementedError as exc:
        raise _memory_not_supported("export") from exc
    return MemoryResponse(**memory_data)


@router.post(
    "/memory/import",
    response_model=MemoryResponse,
    response_model_exclude_none=True,
    summary="Import Memory Data",
    description="Import and overwrite the current global memory data from a JSON payload.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def import_memory(
    request: MemoryResponse,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> MemoryResponse:
    """Import and persist memory data."""
    try:
        memory_data = import_memory_data(request.model_dump(), user_id=get_effective_user_id())
    except NotImplementedError as exc:
        raise _memory_not_supported("import") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to import memory data.") from exc

    return MemoryResponse(**memory_data)


@router.get(
    "/memory/config",
    response_model=MemoryConfigResponse,
    summary="Get Memory Configuration",
    description="Retrieve the current memory system configuration.",
)
async def get_memory_config_endpoint() -> MemoryConfigResponse:
    """Get the memory system configuration.

    Returns:
        The current memory configuration settings.

    Example Response:
        ```json
        {
            "enabled": true,
            "storage_path": ".ideer/memory.json",
            "debounce_seconds": 30,
            "max_facts": 100,
            "fact_confidence_threshold": 0.7,
            "injection_enabled": true,
            "max_injection_tokens": 2000
        }
        ```
    """
    config = get_memory_config()
    return _memory_config_response(config)


@router.get(
    "/memory/status",
    response_model=MemoryStatusResponse,
    response_model_exclude_none=True,
    summary="Get Memory Status",
    description="Retrieve both memory configuration and current data in a single request.",
)
async def get_memory_status() -> MemoryStatusResponse:
    """Get the memory system status including configuration and data.

    Returns:
        Combined memory configuration and current data.
    """
    config = get_memory_config()
    try:
        memory_data = get_memory_data(user_id=get_effective_user_id())
    except MemoryCorruptionError as exc:
        raise HTTPException(status_code=500, detail="Stored memory data is corrupted.") from exc
    except NotImplementedError as exc:
        raise _memory_not_supported("status") from exc

    return MemoryStatusResponse(
        config=_memory_config_response(config),
        data=MemoryResponse(**memory_data),
    )
