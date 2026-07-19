from ideer.config.workflow_runtime_config import WorkflowRuntimeConfig


def test_workflow_runtime_config_has_safe_phase_two_defaults() -> None:
    config = WorkflowRuntimeConfig()

    assert config.user_concurrency == 3
    assert config.department_concurrency == 10
    assert config.max_parallel_actions == 3
    assert config.node_timeout_seconds == 900
    assert config.max_events_per_run == 10_000
    assert config.lease_seconds == 30
    assert config.heartbeat_seconds == 10
    assert config.max_attempts == 3
