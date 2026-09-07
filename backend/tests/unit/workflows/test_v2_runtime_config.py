from deerflow.config.app_config import AppConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.config.workflow_runtime_config import WorkflowRuntimeConfig
from deerflow.config.workflow_runtime_config import WorkflowRuntimeConfig as DeerFlowWorkflowRuntimeConfig


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


def test_agentplatform_compatibility_import_uses_deerflow_schema() -> None:
    assert WorkflowRuntimeConfig is DeerFlowWorkflowRuntimeConfig


def test_deerflow_app_config_exposes_workflow_runtime_defaults() -> None:
    config = AppConfig(sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"))

    assert config.workflow_runtime.max_attempts == 3
