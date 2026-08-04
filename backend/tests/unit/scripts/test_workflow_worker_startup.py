"""Contract tests for automatic workflow-worker startup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_docker_dev_declares_a_workflow_worker_service() -> None:
    compose = _read("docker/docker-compose-dev.yaml")

    assert "  workflow-worker:" in compose
    assert 'dev-entrypoint.sh", "worker"' in compose
    assert "restart: unless-stopped" in compose


def test_intranet_compose_declares_a_workflow_worker_service() -> None:
    compose = _read("docker/docker-compose.intranet.yaml")

    assert "  workflow-worker:" in compose
    assert "python -m app.workflow_worker" in compose
    assert "restart: unless-stopped" in compose


def test_production_worker_has_the_same_runtime_inputs_as_gateway() -> None:
    compose = _read("docker/docker-compose.yaml")

    worker = compose.split("  workflow-worker:", 1)[1].split("  # ── Sandbox", 1)[0]
    assert "extensions_config.json" in worker
    assert "../skills:/app/skills:ro" in worker
    assert "WORKFLOW_WORKER_ID" in worker


def test_docker_dev_launcher_starts_the_workflow_worker() -> None:
    script = _read("scripts/docker.sh")

    assert 'services="frontend gateway workflow-worker nginx"' in script
    assert "workflow worker" in script.lower()


def test_makefile_exposes_workflow_worker_logs() -> None:
    makefile = _read("Makefile")

    assert "docker-logs-workflow-worker" in makefile


def test_local_browser_launcher_manages_a_workflow_worker_session() -> None:
    script = _read("scripts/run-local-services.sh")

    assert 'WORKFLOW_WORKER_SESSION="ideer-workflow-worker"' in script
    assert "python -m app.workflow_worker" in script
    assert "WORKFLOW_WORKER_SESSION" in script.split("stop_services()", 1)[1]


def test_unified_local_launcher_starts_and_stops_the_workflow_worker() -> None:
    script = _read("scripts/serve.sh")

    assert "workflow-worker" in script
    assert "python -m app.workflow_worker" in script
    assert "WORKFLOW_WORKER_PID_FILE" in script


def test_dev_entrypoint_can_run_the_workflow_worker_after_sync() -> None:
    script = _read("docker/dev-entrypoint.sh")

    assert '"${1:-gateway}"' in script
    assert "python -m app.workflow_worker" in script
