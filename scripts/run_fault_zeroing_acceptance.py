#!/usr/bin/env python3
"""Run the three checked-in fault-zeroing cases through the production worker path."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.workflow_worker import execute_workflow_task
from ideer.config import get_app_config
from ideer.config.checkpointer_config import CheckpointerConfig
from ideer.config.paths import get_paths
from ideer.persistence.base import Base
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowWorker

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = REPO_ROOT / "docs" / "zero_agent_eval_cases"
WORKFLOW_PATH = REPO_ROOT / "workflows" / "fault-zeroing.yaml"
EXPECTED_OUTPUTS = (
    "fault_tree.json",
    "fault_tree.svg",
    "bottom_event_assessment.md",
    "analysis_process.svg",
    "zeroing_report.md",
)
ACTION_NODE_COUNT = 9


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, help="Owner of the installed fault-zeroing custom agent")
    return parser.parse_args()


def _stage_case(case_dir: Path, uploads_dir: Path) -> list[str]:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for source in sorted(case_dir.iterdir()):
        if not source.is_file() or source.name.endswith("_expected_analysis.md"):
            continue
        shutil.copy2(source, uploads_dir / source.name)
        staged.append(source.name)
    return staged


async def _run(user_id: str) -> dict:
    started_at = datetime.now(UTC)
    session_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    acceptance_dir = get_paths().base_dir / "acceptance" / "fault-zeroing" / session_id
    acceptance_dir.mkdir(parents=True, exist_ok=False)
    engine = create_async_engine(f"sqlite+aiosqlite:///{acceptance_dir / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    store = WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))

    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow_raw = yaml.safe_load(workflow_text)
    version = await store.save_definition(
        "fault-zeroing",
        workflow_raw,
        hashlib.sha256(workflow_text.encode()).hexdigest(),
        user_id,
    )
    config = get_app_config().model_copy(
        update={
            "checkpointer": CheckpointerConfig(
                type="sqlite",
                connection_string=str(acceptance_dir / "checkpoints.db"),
            )
        }
    )
    results: list[dict] = []
    try:
        for case_dir in sorted(CASES_ROOT.glob("case_*")):
            if not case_dir.is_dir():
                continue
            run_id = f"fz-{case_dir.name.split('_')[1]}-{session_id}-{uuid4().hex[:6]}"
            paths = get_paths()
            paths.ensure_thread_dirs(run_id, user_id=user_id)
            uploads_dir = paths.sandbox_uploads_dir(run_id, user_id=user_id)
            outputs_dir = paths.sandbox_outputs_dir(run_id, user_id=user_id)
            staged_files = _stage_case(case_dir, uploads_dir)
            if any(name.endswith("_expected_analysis.md") for name in staged_files):
                raise AssertionError(f"expected analysis leaked into runtime inputs for {case_dir.name}")
            problem_description = (case_dir / "00_problem_statement.md").read_text(encoding="utf-8")
            await store.create_run(
                run_id,
                "fault-zeroing",
                version.version,
                {
                    "upload_dir": "/mnt/user-data/uploads",
                    "problem_description": problem_description,
                    "output_base_dir": "/mnt/user-data/outputs",
                },
                user_id,
            )
            started = time.monotonic()

            async def execute(task) -> None:
                await execute_workflow_task(task, store=store, config=config)

            await WorkflowWorker(
                store,
                execute,
                worker_id=f"acceptance-{case_dir.name}",
                lease_seconds=config.workflow_runtime.lease_seconds,
                heartbeat_seconds=config.workflow_runtime.heartbeat_seconds,
                max_attempts=config.workflow_runtime.max_attempts,
            ).run_once()
            duration_seconds = round(time.monotonic() - started, 3)
            run = await store.get_run(run_id)
            events = await store.list_events(run_id)
            completed_nodes = [event.payload.get("node_id") for event in events if event.event_type == "node_completed"]
            artifacts = {name: str(outputs_dir / name) for name in EXPECTED_OUTPUTS}
            if run is None or run.status != "completed":
                raise RuntimeError(f"{case_dir.name} failed: {None if run is None else run.error}")
            if len(completed_nodes) != ACTION_NODE_COUNT or len(set(completed_nodes)) != ACTION_NODE_COUNT:
                raise AssertionError(f"{case_dir.name} completed nodes mismatch: {completed_nodes}")
            for name, raw_path in artifacts.items():
                path = Path(raw_path)
                if not path.is_file() or path.stat().st_size == 0:
                    raise AssertionError(f"{case_dir.name} missing or empty artifact: {name}")
            json.loads((outputs_dir / "fault_tree.json").read_text(encoding="utf-8"))
            results.append(
                {
                    "case": case_dir.name,
                    "run_id": run_id,
                    "definition_version": version.version,
                    "duration_seconds": duration_seconds,
                    "event_count": len(events),
                    "completed_nodes": completed_nodes,
                    "staged_inputs": staged_files,
                    "expected_analysis_provided": False,
                    "artifacts": artifacts,
                    "automated_checks": "passed",
                    "human_check": "pending",
                }
            )
    finally:
        await engine.dispose()

    summary = {
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "workflow": "fault-zeroing",
        "definition_version": version.version,
        "validator_run": False,
        "results": results,
    }
    record_path = acceptance_dir / "acceptance.json"
    record_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["record_path"] = str(record_path)
    return summary


def main() -> int:
    args = _parse_args()
    print(json.dumps(asyncio.run(_run(args.user_id)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
