"""Control-plane calculation of the knowledge scope for a frozen Run."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def calculate_effective_knowledge_scope(
    resource_bindings: Mapping[str, str | None],
    *,
    caller_allowed: Iterable[str] | None = None,
    workflow_allowed: Iterable[str] | None = None,
    runtime_allowed: Iterable[str] | None = None,
    deployment_allowed: Iterable[str] | None = None,
) -> dict[str, str]:
    """Return logical KB → provider dataset bindings after all vetoes.

    ``None`` means that a layer has no additional restriction.  Empty sets
    remain empty: an empty allowlist is an intentional deny, not "all".
    Unbound KBs are omitted because they cannot be searched safely.
    """

    scope = {logical: dataset for logical, dataset in resource_bindings.items() if dataset}
    for restriction in (caller_allowed, workflow_allowed, runtime_allowed, deployment_allowed):
        if restriction is not None:
            allowed = set(restriction)
            scope = {logical: dataset for logical, dataset in scope.items() if logical in allowed or dataset in allowed}
    return dict(sorted(scope.items()))
