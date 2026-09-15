"""Revision integrity status vocabulary shared across the knowledge domain."""

from __future__ import annotations

INTEGRITY_HEALTHY = "healthy"
INTEGRITY_UNVERIFIED = "unverified"
INTEGRITY_MISSING_PROVIDER_DATASET = "missing_provider_dataset"
INTEGRITY_DRIFTED = "drifted"

# Integrity statuses that disqualify a published revision from anchoring
# runs (LIVE resolution) or PINNED dependency declarations.
UNUSABLE_INTEGRITY = frozenset({INTEGRITY_DRIFTED, INTEGRITY_MISSING_PROVIDER_DATASET})
