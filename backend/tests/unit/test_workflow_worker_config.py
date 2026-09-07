from app import workflow_worker


def test_workflow_worker_uses_deerflow_runtime_config():
    """Workflow execution receives the shared DeerFlow runtime schema."""

    assert workflow_worker.get_app_config.__module__ == "deerflow.config.app_config"
