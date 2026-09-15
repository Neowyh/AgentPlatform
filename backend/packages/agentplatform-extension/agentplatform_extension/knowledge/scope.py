"""Immutable extension-side projection of the control-plane KB scope."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeScope:
    """Logical selector to opaque provider dataset mapping for one Run."""

    bindings: tuple[tuple[str, str], ...] = ()
    ready_document_ids: tuple[tuple[str, tuple[str, ...]], ...] = ()
    retrieval_profiles: tuple[tuple[str, tuple[tuple[str, object], ...]], ...] = ()
    revision_metadata: tuple[tuple[str, tuple[tuple[str, object], ...]], ...] = ()

    @classmethod
    def from_bindings(
        cls,
        bindings: Mapping[str, str] | Iterable[tuple[str, str]],
        *,
        ready_document_ids: Mapping[str, Iterable[str]] | None = None,
        retrieval_profiles: Mapping[str, Mapping[str, object]] | None = None,
        revision_metadata: Mapping[str, Mapping[str, object]] | None = None,
    ) -> KnowledgeScope:
        values = dict(bindings)
        if any(not logical.strip() or not dataset.strip() for logical, dataset in values.items()):
            raise ValueError("knowledge scope selectors and dataset bindings must not be empty")
        documents = tuple(sorted((str(dataset), tuple(sorted({str(document_id) for document_id in ids}))) for dataset, ids in (ready_document_ids or {}).items()))
        profiles = tuple(sorted((str(dataset), tuple(sorted((str(key), value) for key, value in profile.items()))) for dataset, profile in (retrieval_profiles or {}).items()))
        revisions = tuple(sorted((str(dataset), tuple(sorted((str(key), value) for key, value in metadata.items()))) for dataset, metadata in (revision_metadata or {}).items()))
        return cls(tuple(sorted((str(logical), str(dataset)) for logical, dataset in values.items())), documents, profiles, revisions)

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

    def document_ids_for(self, dataset_id: str) -> tuple[str, ...] | None:
        for dataset, document_ids in self.ready_document_ids:
            if dataset == dataset_id:
                return document_ids
        return None

    def retrieval_profile_for(self, dataset_id: str) -> dict[str, object]:
        for dataset, profile in self.retrieval_profiles:
            if dataset == dataset_id:
                return dict(profile)
        return {}

    def revision_metadata_for(self, dataset_id: str) -> dict[str, object]:
        for dataset, metadata in self.revision_metadata:
            if dataset == dataset_id:
                return dict(metadata)
        return {}

    def intersect(self, other: KnowledgeScope) -> KnowledgeScope:
        allowed = other.dataset_allowlist | other.logical_selectors
        bindings = tuple((logical, dataset) for logical, dataset in self.bindings if logical in allowed or dataset in allowed)
        datasets = {dataset for _, dataset in bindings}
        return KnowledgeScope.from_bindings(
            bindings,
            ready_document_ids={dataset: ids for dataset, ids in self.ready_document_ids if dataset in datasets},
            retrieval_profiles={dataset: dict(profile) for dataset, profile in self.retrieval_profiles if dataset in datasets},
            revision_metadata={dataset: dict(metadata) for dataset, metadata in self.revision_metadata if dataset in datasets},
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "logical_selectors": sorted(self.logical_selectors),
            "dataset_allowlist": sorted(self.dataset_allowlist),
            "bindings": dict(self.bindings),
            "ready_document_ids": {dataset: list(ids) for dataset, ids in self.ready_document_ids},
            "retrieval_profiles": {dataset: dict(profile) for dataset, profile in self.retrieval_profiles},
            "revision_metadata": {dataset: dict(metadata) for dataset, metadata in self.revision_metadata},
        }

    def model_mapping(self) -> dict[str, object]:
        """Return the selector-only projection safe to expose to the model."""

        return {"logical_selectors": sorted(self.logical_selectors)}
