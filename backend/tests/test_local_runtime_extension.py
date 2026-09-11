from datetime import UTC, datetime

import pytest
from agentplatform_extension.local_runtime import (
    DeviceRoute,
    LocalAuthorization,
    LocalExecutionReceipt,
    LocalToolExecutor,
    LocalToolProvenance,
    RunDeviceRouter,
    assemble_local_tools,
    child_authorization,
    filter_local_tools,
    local_tool_names,
)


def _authorization() -> LocalAuthorization:
    values = frozenset({"local.files.read", "local.python"})
    return LocalAuthorization(*(values,) * 6, device_online=True)


def test_tools_are_hidden_when_device_is_offline_and_intersection_is_strict() -> None:
    auth = _authorization()
    assert {tool.name for tool in assemble_local_tools(auth)} == {"local.files.read", "local.python"}
    assert assemble_local_tools(LocalAuthorization()) == ()


def test_route_is_frozen_and_child_cannot_expand_capabilities() -> None:
    router = RunDeviceRouter()
    router.freeze(DeviceRoute("raw-device-id"))
    try:
        router.freeze(DeviceRoute("other-device"))
    except RuntimeError:
        pass
    else:
        raise AssertionError("route must be frozen")
    assert child_authorization(_authorization(), {"local.python", "local.files.write"}).effective == {"local.python"}


def test_local_filter_preserves_server_tools_and_drops_unauthorized_local_tools() -> None:
    tools = (*assemble_local_tools(_authorization()),)
    tools += (type(tools[0])("server.tool", "server"),)

    filtered = filter_local_tools(tools, LocalAuthorization())

    assert [tool.name for tool in filtered] == ["server.tool"]


def test_local_tool_names_are_assembly_safe() -> None:
    assert local_tool_names(LocalAuthorization()) == frozenset()
    assert local_tool_names(_authorization()) == frozenset({"local.files.read", "local.python"})


def test_local_execution_receipt_is_nested_under_tool_receipt() -> None:
    receipt = LocalExecutionReceipt(
        capability="local.python",
        request_hash="a" * 64,
        policy_version="policy-1",
        consent_decision="allow",
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        runtime_version="1.0.0",
    )
    from agentplatform_extension.local_runtime.receipts import tool_receipt_from_local

    value = tool_receipt_from_local(receipt.as_mapping(), tool_call_id="call-1")
    assert value["tool_name"] == "local.python"
    assert value["local_execution_receipt"]["request_hash"] == "a" * 64
    assert value["tool_call_id"] == "call-1"


def test_local_provenance_binds_run_and_tool_call_without_device_identity() -> None:
    value = LocalToolProvenance("run-1", "thread-1", "call-1", "local.python").as_mapping()
    assert value == {
        "run_id": "run-1",
        "thread_id": "thread-1",
        "tool_call_id": "call-1",
        "capability": "local.python",
    }
    assert "device_id" not in value


@pytest.mark.asyncio
async def test_local_tool_executor_uses_frozen_route_and_records_receipt() -> None:
    auth = LocalAuthorization.from_capabilities({"local.python"}, device_online=True)
    route = RunDeviceRouter(DeviceRoute("device-secret"))
    calls = []
    receipt = {"capability": "local.python", "status": "completed"}

    async def sender(device_id, capability, payload):
        calls.append((device_id, capability, payload))
        return type("Result", (), {"receipt": receipt})()

    recorded = []
    executor = LocalToolExecutor(auth, route, sender, receipt_sink=recorded.append)
    await executor.invoke("local.python", {"script": "print(1)"})

    assert calls == [("device-secret", "local.python", {"script": "print(1)"})]
    assert recorded == [receipt]
    assert "device-secret" not in str(calls[0][2])


@pytest.mark.asyncio
async def test_local_tool_executor_rejects_unauthorized_capability_before_routing() -> None:
    route = RunDeviceRouter(DeviceRoute("device-secret"))

    async def sender(*args):
        raise AssertionError("unauthorized local task was routed")

    executor = LocalToolExecutor(LocalAuthorization(), route, sender)
    with pytest.raises(PermissionError):
        await executor.invoke("local.python", {})
