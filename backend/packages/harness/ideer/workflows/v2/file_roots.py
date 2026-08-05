"""Shared helpers for workflow file_access root validation and artifact checks.

Workflow definitions declare ``file_access`` roots as virtual paths
(``/mnt/user-data``, ``/mnt/skills``, ``/mnt/acp-workspace`` or custom mount
container paths).  These helpers centralise the rules shared by:

- A: gateway start-up validation (reject host paths before a run is created)
- B: input root pre-flight (a run whose read-only input roots are missing or
  empty fails fast instead of producing garbage downstream)
- C: node artifact verification (a node that declared write roots must
  actually produce data, otherwise the run pauses for manual intervention)
- D: run artifact listing (resolve the declared output base directory)
- E: cross-node state hand-off (each node's result is materialized to a file
  under the run workspace so downstream nodes can read it on demand)

The allowlist here mirrors ``ideer.sandbox.tools.validate_local_tool_path``
so the DSL, the sandbox and the verification layer all agree on one rule set.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ideer.config.paths import VIRTUAL_PATH_PREFIX, get_paths
from ideer.sandbox.tools import (
    _get_custom_mounts,
    _get_skills_container_path,
    _get_skills_host_path,
)

_ACP_WORKSPACE_PREFIX = "/mnt/acp-workspace"

_STATE_DIR_REL = ".workflow/state"
_LOG_DIR_REL = ".workflow/logs"

_PLACEHOLDER_MARKERS = ("file_missing", "占位", "placeholder")


def workflow_state_root() -> str:
    """Virtual root where each node's state output is materialized."""
    return f"{VIRTUAL_PATH_PREFIX}/workspace/{_STATE_DIR_REL}"


def workflow_log_root() -> str:
    """Virtual root where the per-run run record (JSONL/Markdown) is written."""
    return f"{VIRTUAL_PATH_PREFIX}/workspace/{_LOG_DIR_REL}"


def workflow_record_path(extension: str) -> str:
    """Virtual path of the run record file for ``jsonl`` or ``md``."""
    return f"{workflow_log_root()}/run_record.{extension}"


def workflow_state_path(key: str, *, structured: bool) -> str:
    """Virtual path of the materialized state file for one state key."""
    suffix = ".json" if structured else ".md"
    return f"{workflow_state_root()}/{key}{suffix}"


def materialize_state(key: str, value: Any, resolver: Callable[[str], str | None]) -> str | None:
    """Write a node's state output to the run workspace; return its virtual path.

    String values are stored as markdown text (``<key>.md``); dict/list values
    are JSON-serialized (``<key>.json``).  Returns ``None`` when the workspace
    cannot be resolved (e.g. sandbox disabled), so callers degrade gracefully.
    """
    structured = isinstance(value, (dict, list))
    virtual = workflow_state_path(key, structured=structured)
    host = resolver(virtual)
    if host is None:
        return None
    path = Path(host)
    path.parent.mkdir(parents=True, exist_ok=True)
    if structured:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text(str(value), encoding="utf-8")
    return virtual


def render_template(value: Any, state: dict[str, Any]) -> Any:
    """Render ``{{...}}`` template references against the graph state."""
    if isinstance(value, dict):
        return {key: render_template(item, state) for key, item in value.items()}
    if isinstance(value, list):
        return [render_template(item, state) for item in value]
    if not isinstance(value, str) or "{{" not in value:
        return value
    result = value
    while "{{" in result:
        start = result.index("{{")
        end = result.index("}}", start)
        path = result[start + 2 : end].strip()
        replacement = lookup_path(path, state)
        if replacement is None:
            # Unpopulated state leaves the template verbatim so callers can
            # skip it (e.g. start-up validation) instead of rendering "None".
            break
        result = result[:start] + str(replacement) + result[end + 2 :]
    return result


def lookup_path(path: str, state: dict[str, Any]) -> Any:
    current: Any = state
    for part in path.removeprefix("$.").split("."):
        current = current[part]
    return current


def render_roots(file_access: dict[str, list[str]] | None, state: dict[str, Any]) -> dict[str, list[str]] | None:
    """Render file_access roots, keeping unresolvable templates untouched.

    Templates referencing ``state`` values that are not yet populated (e.g.
    during gateway start-up validation) are kept verbatim so they are skipped
    by ``validate_roots`` and only checked at runtime.
    """
    if file_access is None:
        return None
    rendered: dict[str, list[str]] = {}
    for key in ("read", "write"):
        roots = []
        for root in file_access.get(key, []):
            try:
                roots.append(render_template(root, state))
            except (KeyError, IndexError, TypeError):
                roots.append(root)
        rendered[key] = roots
    return rendered


def _is_allowed_root(path: str, *, write: bool) -> bool:
    """Prefix allowlist check mirroring validate_local_tool_path semantics."""
    if path == VIRTUAL_PATH_PREFIX or path.startswith(f"{VIRTUAL_PATH_PREFIX}/"):
        return True
    skills_prefix = _get_skills_container_path()
    if skills_prefix and (path == skills_prefix or path.startswith(f"{skills_prefix}/")):
        return not write
    if path == _ACP_WORKSPACE_PREFIX or path.startswith(f"{_ACP_WORKSPACE_PREFIX}/"):
        return not write
    for mount in _get_custom_mounts():
        if path == mount.container_path or path.startswith(f"{mount.container_path}/"):
            return not (write and mount.read_only)
    return False


def path_within_root(path: str, root: str) -> bool:
    """True when ``path`` equals ``root`` or sits directly under it."""
    base = root.rstrip("/")
    return path.rstrip("/") == base or path.startswith(base + "/")


def validate_roots(file_access: dict[str, list[str]] | None) -> list[str]:
    """Return the roots that are not permitted; empty list means valid."""
    if file_access is None:
        return []
    invalid: list[str] = []
    for key in ("read", "write"):
        for root in file_access.get(key, []):
            if "{{" in root:
                continue  # resolved and validated at runtime
            if not _is_allowed_root(root, write=key == "write"):
                invalid.append(f"{key}:{root}")
    return invalid


def validate_workflow_roots(nodes: list[Any], inputs: dict[str, Any]) -> list[str]:
    """Return every invalid file_access root across a workflow definition.

    ``inputs`` holds the submitted run inputs; roots templated on ``state``
    values are only resolvable at runtime and are skipped here.
    """
    state = {"inputs": inputs, "state": {}, "outputs": {}}
    invalid: list[str] = []
    for node in nodes:
        action = getattr(node, "action", None)
        if getattr(node, "type", None) != "action" or action is None or action.file_access is None:
            continue
        rendered = render_roots(action.file_access.model_dump(), state)
        for root in validate_roots(rendered):
            invalid.append(f"node '{node.id}': {root}")
    return invalid


def make_host_resolver(run_id: str, user_id: str | None) -> Callable[[str], str | None]:
    """Build a virtual-path -> host-path resolver for one workflow run.

    Mirrors the mappings the local sandbox derives from thread data
    (``thread_data_middleware`` + ``replace_virtual_path``) without requiring
    an agent runtime: workflow agents run with ``thread_id == run_id``.
    """
    paths = get_paths()
    mappings: dict[str, str] = {
        f"{VIRTUAL_PATH_PREFIX}/workspace": str(paths.sandbox_work_dir(run_id, user_id=user_id)),
        f"{VIRTUAL_PATH_PREFIX}/uploads": str(paths.sandbox_uploads_dir(run_id, user_id=user_id)),
        f"{VIRTUAL_PATH_PREFIX}/outputs": str(paths.sandbox_outputs_dir(run_id, user_id=user_id)),
    }

    def resolve(path: str) -> str | None:
        candidates: list[tuple[int, str, str]] = []
        for virtual_base, actual_base in mappings.items():
            if path == virtual_base or path.startswith(f"{virtual_base}/"):
                candidates.append((len(virtual_base), actual_base, virtual_base))
        skills_prefix = _get_skills_container_path()
        if skills_prefix and (path == skills_prefix or path.startswith(f"{skills_prefix}/")):
            skills_host = _get_skills_host_path()
            if skills_host:
                candidates.append((len(skills_prefix), skills_host, skills_prefix))
        for mount in _get_custom_mounts():
            if path == mount.container_path or path.startswith(f"{mount.container_path}/"):
                candidates.append((len(mount.container_path), mount.host_path, mount.container_path))
        if not candidates:
            return None
        _, actual_base, virtual_base = max(candidates, key=lambda item: item[0])
        rest = path[len(virtual_base) :].lstrip("/")
        if not rest:
            return actual_base.rstrip("/")
        separator = "\\" if "\\" in actual_base and "/" not in actual_base else "/"
        return f"{actual_base.rstrip('/\\')}{separator}{rest}"

    return resolve


def missing_written_artifacts(write_roots: list[str], resolver: Callable[[str], str | None]) -> list[str]:
    """Return the declared write roots that produced no usable data.

    File roots must exist and be non-empty; JSON file roots must also parse
    and must not contain placeholder markers (agents sometimes write a
    ``{"status": "file_missing"}`` stub instead of failing).  Directory roots
    (trailing ``/``) must exist.  Roots that cannot be resolved are reported
    as missing so a misconfigured definition fails loudly instead of silently
    passing.
    """
    missing: list[str] = []
    for root in write_roots:
        host = resolver(root)
        if host is None:
            missing.append(root)
            continue
        path = Path(host)
        if root.endswith("/"):
            if not path.is_dir():
                missing.append(root)
            continue
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(root)
            continue
        if _is_placeholder_output(path):
            missing.append(root)
    return missing


def _is_placeholder_output(path: Path) -> bool:
    """True when a file exists but looks like a fabricated placeholder.

    JSON outputs must parse; any output containing a placeholder marker
    (``file_missing``, ``占位``, ``placeholder``) is treated as missing so a
    stubbed result cannot silently poison downstream nodes.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return True
    lowered = text.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return True
    if path.name.endswith(".json"):
        try:
            json.loads(text)
        except json.JSONDecodeError:
            return True
    return False


def _is_input_read_root(path: str) -> bool:
    """True when a read root carries user-provided input data.

    Only these roots are pre-flighted for existence: user uploads and
    read-only custom mounts.  Writable areas (outputs, workspace) hold
    artifacts produced by earlier nodes that legitimately do not exist yet,
    so they are never checked up front.
    """
    if path == f"{VIRTUAL_PATH_PREFIX}/uploads" or path.startswith(f"{VIRTUAL_PATH_PREFIX}/uploads/"):
        return True
    for mount in _get_custom_mounts():
        if mount.read_only and (path == mount.container_path or path.startswith(f"{mount.container_path}/")):
            return True
    return False


def validate_read_roots(nodes: list[Any], inputs: dict[str, Any], resolver: Callable[[str], str | None]) -> list[str]:
    """Return the input read roots that are missing or empty.

    A node declaring read access to an input root that does not exist (or is
    empty) would produce garbage downstream, so runs fail fast instead.
    Uploads under ``/mnt/user-data/uploads`` may not have their run-scoped
    directory initialized yet, so only an already-existing host path is
    checked for emptiness; read-only mounts are always checked.
    """
    state = {"inputs": inputs, "state": {}, "outputs": {}}
    missing: list[str] = []
    for node in nodes:
        action = getattr(node, "action", None)
        if getattr(node, "type", None) != "action" or action is None or action.file_access is None:
            continue
        rendered = render_roots(action.file_access.model_dump(), state)
        for root in rendered.get("read", []):
            if "{{" in root or not _is_input_read_root(root):
                continue
            host = resolver(root)
            if host is None:
                continue  # no host mapping (e.g. skills not installed) — framework-managed
            path = Path(host)
            if not path.exists():
                if root.startswith(f"{VIRTUAL_PATH_PREFIX}/uploads"):
                    continue  # run-scoped uploads dir may not be initialized yet
                missing.append(f"node '{node.id}': {root}")
                continue
            if path.is_dir():
                if not any(path.iterdir()):
                    missing.append(f"node '{node.id}': {root}")
            elif path.stat().st_size == 0:
                missing.append(f"node '{node.id}': {root}")
    return missing


def collect_artifacts(write_roots: list[str], resolver: Callable[[str], str | None]) -> list[dict[str, Any]]:
    """List the files produced under the declared write roots.

    Returns ``{"path", "size", "modified"}`` entries whose ``path`` is the
    virtual (sandbox) path, so callers never see host paths.  Directory roots
    are expanded recursively; unresolvable roots are skipped.
    """
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append(file_path: Path, virtual: str) -> None:
        key = str(file_path)
        if key in seen:
            return
        seen.add(key)
        stat = file_path.stat()
        artifacts.append({"path": virtual, "size": stat.st_size, "modified": int(stat.st_mtime)})

    for root in write_roots:
        host = resolver(root)
        if host is None:
            continue
        path = Path(host)
        root_base = Path(host).resolve()
        virtual_base = root.rstrip("/")
        if path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if not file_path.is_file():
                    continue
                relative = file_path.resolve().relative_to(root_base).as_posix()
                append(file_path, f"{virtual_base}/{relative}")
        elif path.is_file():
            append(path, virtual_base)
    artifacts.sort(key=lambda item: item["path"])
    return artifacts
