"""Declared result contracts: loading and runtime enforcement.

A workflow definition may declare a top-level ``result_contract`` naming an
importable ``<module>:<function>`` validator.  After the graph succeeds, the
runner loads and calls the validator with the run's artifact root directory
and the persisted run snapshot; a non-empty violation list turns the run
into a ``failed`` terminal state before it is written.  The engine knows
nothing about what the artifacts mean — the validator carries the semantics
(fail-closed: a validator that cannot be loaded or that raises fails the run).
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from typing import Any

from deerflow.config.paths import VIRTUAL_PATH_PREFIX

from .errors import (
    WorkflowResultContractValidatorError,
    WorkflowResultContractViolation,
    WorkflowRunError,
)
from .file_roots import render_roots
from .schema import WorkflowV2

# ``<module>:<function>`` with dotted Python identifiers on both sides.
_VALIDATOR_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$")


def load_result_contract_validator(validator: str) -> Callable[..., Any]:
    """Import and return a declared ``<module>:<function>`` validator.

    Raises ``ValueError`` for a malformed path or a non-callable target and
    ``ModuleNotFoundError``/``ImportError`` for an unimportable module, so
    static parsing and the runtime gate share one loading rule.
    """
    if not _VALIDATOR_PATH.fullmatch(validator):
        raise ValueError(f"result_contract.validator must be '<module>:<function>': '{validator}'")
    module_name, function_name = validator.rsplit(":", 1)
    module = importlib.import_module(module_name)
    attribute = getattr(module, function_name, None)
    if not callable(attribute):
        raise ValueError(f"result_contract.validator is not callable: '{validator}'")
    return attribute


def _common_virtual_parent(roots: list[str]) -> str | None:
    """Longest common virtual ancestor directory of the given write roots.

    Every root is reduced to its directory part first (file roots to their
    parent, directory roots — trailing ``/`` — to themselves), then the
    longest common leading path segments are kept.
    """
    dirs: list[list[str]] = []
    for root in roots:
        normalized = root.rstrip("/")
        segments = normalized.split("/") if root.endswith("/") else normalized.rsplit("/", 1)[0].split("/")
        dirs.append(segments)
    if not dirs:
        return None
    common = dirs[0]
    for other in dirs[1:]:
        shared: list[str] = []
        for left, right in zip(common, other):
            if left != right:
                break
            shared.append(left)
        common = shared
    return "/".join(common) or None


def run_artifact_root(
    workflow: WorkflowV2,
    *,
    run_inputs: dict[str, Any],
    run_snapshot: Any,
    resolver: Callable[[str], str | None],
) -> str:
    """Host path of the directory a declared validator should judge.

    Derived from the run's own declared write roots rendered against the
    final run snapshot: their common virtual ancestor, resolved to a host
    path.  Falls back to the run's standard outputs root when the definition
    declares no resolvable write roots.  The engine never learns what the
    artifacts mean.
    """
    snapshot = run_snapshot if isinstance(run_snapshot, dict) else {}
    state = {
        "inputs": run_inputs or {},
        "state": snapshot.get("state", {}),
        "outputs": snapshot.get("outputs", {}),
    }
    write_roots: list[str] = []
    for node in workflow.nodes:
        if node.type != "action" or node.action is None or node.action.file_access is None:
            continue
        rendered = render_roots({"write": node.action.file_access.write}, state)
        write_roots.extend(rendered.get("write", []))
    common = _common_virtual_parent(write_roots)
    host = resolver(common) if common else None
    if host is None:
        host = resolver(f"{VIRTUAL_PATH_PREFIX}/outputs")
    return host or ""


def enforce_result_contract(
    workflow: WorkflowV2,
    *,
    run_inputs: dict[str, Any],
    run_snapshot: Any,
    resolver: Callable[[str], str | None],
) -> WorkflowRunError | None:
    """Evaluate a declared result contract after graph success.

    Returns ``None`` when the workflow declares no contract or the validator
    passes.  Otherwise returns the structured run error the caller must emit
    and raise, so the run ends ``failed`` with the violation summary on the
    run record.  A validator that cannot be loaded, that raises, or that
    returns a malformed result fails the run closed.
    """
    spec = workflow.result_contract
    if spec is None:
        return None
    try:
        validator = load_result_contract_validator(spec.validator)
        outputs_dir = run_artifact_root(workflow, run_inputs=run_inputs, run_snapshot=run_snapshot, resolver=resolver)
        violations = validator(outputs_dir, run_snapshot)
    except Exception as exc:
        return WorkflowResultContractValidatorError(spec.validator, str(exc))
    if violations is None or violations == []:
        return None
    if not isinstance(violations, list) or not all(isinstance(item, str) for item in violations):
        return WorkflowResultContractValidatorError(
            spec.validator,
            f"validator returned a non-list result: {type(violations).__name__}",
        )
    return WorkflowResultContractViolation(violations)
