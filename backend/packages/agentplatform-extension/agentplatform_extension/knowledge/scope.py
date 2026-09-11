"""Immutable extension-side projection of the control-plane KB scope."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeScope:
    """Logical selector to opaque provider dataset mapping for one Run."""

    bindings: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_bindings(cls, bindings: Mapping[str, str] | Iterable[tuple[str, str]]) -> KnowledgeScope:
        values = dict(bindings)
        if any(not logical.strip() or not dataset.strip() for logical, dataset in values.items()):
            raise ValueError("knowledge scope selectors and dataset bindings must not be empty")
        return cls(tuple(sorted((str(logical), str(dataset)) for logical, dataset in values.items())))

    @property
    def logical_selectors(self) -> frozenset[str]:
        return frozenset(logical for logical, _ in self.bindings)

    @property
    def dataset_allowlist(self) -> frozenset[str]:
        return frozenset(dataset for _, dataset in self.bindings)

    def resolve(self, logical_selector: str) -> str:
        for logical, dataset in self.bindings:
            if logical == logical_selector:
                return dataset
        raise KeyError(logical_selector)

    def intersect(self, other: KnowledgeScope) -> KnowledgeScope:
        allowed = other.dataset_allowlist | other.logical_selectors
        return KnowledgeScope.from_bindings((logical, dataset) for logical, dataset in self.bindings if logical in allowed or dataset in allowed)

    def as_mapping(self) -> dict[str, object]:
        return {"logical_selectors": sorted(self.logical_selectors), "dataset_allowlist": sorted(self.dataset_allowlist), "bindings": dict(self.bindings)}
