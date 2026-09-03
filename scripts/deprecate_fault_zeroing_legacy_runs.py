#!/usr/bin/env python3
"""Explicitly terminate queued/paused legacy fault-zeroing runs (ticket 06).

After the canonical bundled-resource cutover, legacy (name+version) fault-zeroing
runs that are still queued or paused are terminated with a stable reason code
instead of being silently re-interpreted under the new semantics.  Completed,
failed and cancelled runs stay readable.

Usage (inside the backend environment):

    PYTHONPATH=. uv run python scripts/deprecate_fault_zeroing_legacy_runs.py \
        --db backend/.ideer/data/ideer.db
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_store(db_path: Path):
    from ideer.persistence import engine as persistence_engine
    from ideer.workflows.v2.store import WorkflowV2Store

    persistence_engine.init_engine(f"sqlite+aiosqlite:///{db_path}")
    return WorkflowV2Store(persistence_engine.get_session_factory())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Terminate queued/paused legacy fault-zeroing runs."
    )
    parser.add_argument(
        "--db",
        default=str(REPO_ROOT / "backend" / ".ideer" / "data" / "ideer.db"),
        help="Path to the ideer.sqlite database.",
    )
    args = parser.parse_args(argv)

    try:
        from ideer.fault_zeroing.legacy import terminate_legacy_runs
    except ImportError:
        print(
            "ideer package unavailable; run this script with the backend "
            "environment (PYTHONPATH=backend/packages/harness)",
            file=sys.stderr,
        )
        return 2

    store = _build_store(Path(args.db))
    report = asyncio.run(terminate_legacy_runs(store))

    print(f"terminated runs: {len(report.terminated_run_ids)}")
    for run_id in report.terminated_run_ids:
        print(f"- {run_id}")
    print(f"untouched runs: {len(report.untouched_run_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
