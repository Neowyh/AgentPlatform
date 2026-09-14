"""M8-04 discipline applied to ``local.mcp.<server>.<tool>`` projections.

The projected MCP tools enter the model tool list through the same six-factor
trim, frozen device route, and receipt chain as ``local.files.*`` and
``local.python``. MCP-specific failures stay structured: timeout, server
crash, and schema/tool loss are distinguishable and never masquerade as
success.
"""

from datetime import UTC, datetime

import pytest
from agentplatform_extension.evidence import AuthorizationContext, RunEvidenceBinding, bind_run_evidence, current_run_evidence
from agentplatform_extension.local_runtime import (
    DeviceRoute,
    LocalAuthorization,
    LocalExecutionReceipt,
    LocalToolExecutor,
    RunDeviceRouter,
    assemble_local_tools,
    child_authorization,
    filter_local_tools,
    is_local_mcp_capability,
    local_tool_names,
)
from agentplatform_extension.local_runtime.receipts import tool_receipt_from_local

GIT_STATUS = "local.mcp.git.status"
FS_READ = "local.mcp.fs.read_file"


def _authorization(*names: str, device_online: bool = True) -> LocalAuthorization:
    values = frozenset(names) or frozenset({GIT_STATUS, FS_READ})
    return LocalAuthorization(*(values,) * 6, device_online=device_online)


# ---------------------------------------------------------------------------
# Projection into the model tool list


def test_projected_mcp_tools_follow_the_six_factors() -> None:
    tools = {tool.name for tool in assemble_local_tools(_authorization())}
    assert tools == {GIT_STATUS, FS_READ}
    assert local_tool_names(_authorization()) == frozenset({GIT_STATUS, FS_READ})
    for tool in assemble_local_tools(_authorization()):
        assert tool.description


def test_mcp_projection_requires_every_authorization_factor() -> None:
    full = _authorization()

    def without(source: str) -> LocalAuthorization:
        return LocalAuthorization(
            agent_capabilities=full.agent_capabilities - {GIT_STATUS} if source == "agent" else full.agent_capabilities,
            caller_capabilities=full.caller_capabilities - {GIT_STATUS} if source == "caller" else full.caller_capabilities,
            device_capabilities=full.device_capabilities - {GIT_STATUS} if source == "device" else full.device_capabilities,
            local_policy_capabilities=full.local_policy_capabilities - {GIT_STATUS} if source == "policy" else full.local_policy_capabilities,
            workflow_capabilities=full.workflow_capabilities - {GIT_STATUS} if source == "workflow" else full.workflow_capabilities,
            platform_capabilities=full.platform_capabilities - {GIT_STATUS} if source == "platform" else full.platform_capabilities,
            device_online=True,
        )

    for source in ("agent", "caller", "device", "policy", "workflow", "platform"):
        assert GIT_STATUS not in local_tool_names(without(source)), source
    assert FS_READ in local_tool_names(without("caller"))


def test_offline_device_projects_nothing() -> None:
    assert assemble_local_tools(_authorization(device_online=False)) == ()


def test_withdrawn_capability_disappears_and_returns_with_reenable() -> None:
    # The device withdraws the projection when a server is disabled or crashed
    # (CAPABILITY_UPDATE), and re-announces it after re-enable.
    enabled = _authorization()
    withdrawn = LocalAuthorization(
        agent_capabilities=enabled.agent_capabilities,
        caller_capabilities=enabled.caller_capabilities,
        device_capabilities=enabled.device_capabilities - {GIT_STATUS},
        local_policy_capabilities=enabled.local_policy_capabilities,
        workflow_capabilities=enabled.workflow_capabilities,
        platform_capabilities=enabled.platform_capabilities,
        device_online=True,
    )
    assert GIT_STATUS in local_tool_names(enabled)
    assert GIT_STATUS not in local_tool_names(withdrawn)
    assert GIT_STATUS in local_tool_names(enabled)


def test_filter_keeps_projected_mcp_tools_and_server_tools() -> None:
    tools = (*assemble_local_tools(_authorization()),)
    tools += (type(tools[0])("server.tool", "server"),)
    filtered = filter_local_tools(tools, _authorization())
    assert [tool.name for tool in filtered] == sorted([GIT_STATUS, FS_READ]) + ["server.tool"]


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (GIT_STATUS, True),
        ("local.mcp.fs.read_file", True),
        ("local.mcp.git", False),
        ("local.mcp.", False),
        ("local.mcp.has space/tool", False),
        ("local.python", False),
        ("local.files.read", False),
        ("", False),
    ),
)
def test_capability_shape_validation(value: str, expected: bool) -> None:
    assert is_local_mcp_capability(value) is expected


# ---------------------------------------------------------------------------
# Dispatch through the frozen route


def _receipt(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "capability": GIT_STATUS,
        "status": "completed",
        "payload_hash": "a" * 64,
        "result_hash": "b" * 64,
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_mcp_executor_dispatches_through_frozen_route_and_records_receipt() -> None:
    auth = _authorization()
    route = RunDeviceRouter(DeviceRoute("device-secret"))
    calls = []

    async def sender(device_id, capability, payload):
        calls.append((device_id, capability, payload))
        return type("Result", (), {"receipt": _receipt(), "value": {"status": "completed"}})()

    recorded = []
    executor = LocalToolExecutor(auth, route, sender, receipt_sink=recorded.append)
    result = await executor.invoke(GIT_STATUS, {"arguments": {"path": "."}, "tool_call_id": "call-1"})

    assert calls == [("device-secret", GIT_STATUS, {"arguments": {"path": "."}, "tool_call_id": "call-1"})]
    assert result.value == {"status": "completed"}
    assert recorded == [_receipt()]
    assert "device-secret" not in str(calls[0][2])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "capability",
    ("local.mcp.git", "local.mcp.", "local.mcp.has space/tool"),
)
async def test_mcp_executor_rejects_malformed_capability_before_routing(
    capability: str,
) -> None:
    route = RunDeviceRouter(DeviceRoute("device-secret"))

    async def sender(*args):
        raise AssertionError("malformed capability was routed")

    executor = LocalToolExecutor(_authorization(capability), route, sender)
    with pytest.raises(ValueError):
        await executor.invoke(capability, {})


@pytest.mark.asyncio
async def test_mcp_executor_rejects_unauthorized_capability_before_routing() -> None:
    route = RunDeviceRouter(DeviceRoute("device-secret"))

    async def sender(*args):
        raise AssertionError("unauthorized MCP task was routed")

    executor = LocalToolExecutor(LocalAuthorization(), route, sender)
    with pytest.raises(PermissionError):
        await executor.invoke(GIT_STATUS, {})


# ---------------------------------------------------------------------------
# Structured failure semantics


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "status"),
    (
        ("MCP_TIMEOUT", "timed_out"),
        ("SERVER_CRASHED", "failed"),
        ("TOOL_NOT_FOUND", "failed"),
        ("SECRET_UNAVAILABLE", "failed"),
    ),
)
async def test_mcp_failures_are_structured_distinguishable_and_recorded(
    code: str,
    status: str,
) -> None:
    auth = _authorization()
    route = RunDeviceRouter(DeviceRoute("device-secret"))
    receipt = _receipt(status=status)
    result_value = {"status": status, "error_code": code, "message": f"device reported {code}"}

    async def sender(device_id, capability, payload):
        return type("Result", (), {"receipt": receipt, "value": result_value})()

    recorded = []
    executor = LocalToolExecutor(auth, route, sender, receipt_sink=recorded.append)
    result = await executor.invoke(GIT_STATUS, {"arguments": {}, "tool_call_id": "call-1"})

    # No exception masquerading as success and no fake completion: the
    # structured value and its receipt travel together.
    assert result.value["status"] == status
    assert result.value["status"] != "completed"
    assert result.value["error_code"] == code
    assert recorded == [receipt]
    assert recorded[0]["status"] == status


# ---------------------------------------------------------------------------
# Receipt chain and boundaries


def test_mcp_receipt_enters_the_tool_receipt_chain_with_hashes() -> None:
    receipt = LocalExecutionReceipt(
        capability=GIT_STATUS,
        request_hash="a" * 64,
        policy_version="policy-1",
        consent_decision="allow",
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        runtime_version="1.0.0",
    )
    value = tool_receipt_from_local(receipt.as_mapping(), tool_call_id="call-1")
    assert value["tool_name"] == GIT_STATUS
    assert value["local_execution_receipt"]["request_hash"] == "a" * 64
    assert value["tool_call_id"] == "call-1"


def test_subagent_delegation_cannot_expand_mcp_capabilities() -> None:
    parent = _authorization()
    child = child_authorization(parent, {GIT_STATUS, "local.python", "local.files.write"})
    assert child.effective == {GIT_STATUS}
    grandchild = child_authorization(child, {GIT_STATUS, FS_READ})
    assert grandchild.effective == {GIT_STATUS}


def test_run_snapshot_narrowing_covers_mcp_capabilities() -> None:
    from agentplatform_extension.local_runtime import RunAuthorizationSnapshot

    snapshot = RunAuthorizationSnapshot("run", "thread", "device", "policy-1", _authorization())
    narrowed = LocalAuthorization(*(frozenset({GIT_STATUS}),) * 6, device_online=True)
    snapshot.validate(narrowed, device_id="device")
    with pytest.raises(PermissionError):
        snapshot.validate(_authorization(), device_id="other-device")


@pytest.mark.asyncio
async def test_mcp_receipts_reach_run_evidence_through_the_default_sink() -> None:
    auth = _authorization()
    route = RunDeviceRouter(DeviceRoute("device-secret"))

    async def sender(*args):
        return type("Result", (), {"receipt": _receipt()})()

    binding = RunEvidenceBinding(
        snapshots=(),
        authorization=AuthorizationContext("caller", "agent", "policy-1"),
    )
    with bind_run_evidence(binding):
        await LocalToolExecutor(auth, route, sender).invoke(GIT_STATUS, {"tool_call_id": "call-1"})
        assert current_run_evidence().tool_receipts[0]["tool_call_id"] == "call-1"
        assert current_run_evidence().tool_receipts[0]["tool_name"] == GIT_STATUS
