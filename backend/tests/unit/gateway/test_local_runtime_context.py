import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.device_control.broker import DeviceBroker, DeviceConnection
from app.gateway.run_preparation import _bind_local_runtime_context


class _Socket:
    async def send_text(self, data: str) -> None:
        pass

    async def close(self, code: int = 1000, reason: str = "") -> None:
        pass


def _connection(
    *, allowed: bool = True, owner_id: str | None = None
) -> DeviceConnection:
    key = Ed25519PrivateKey.generate()
    return DeviceConnection(
        "device-context",
        "session-context",
        "token",
        key.public_key(),
        _Socket(),
        tasks_allowed=allowed,
        capabilities=frozenset({"local.mcp.fs.read_file"}),
        tool_descriptors={
            "local.mcp.fs.read_file": {
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
                "schema_hash": "schema-1",
            }
        },
        owner_id=owner_id,
    )


def test_local_context_uses_authenticated_connection_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.device_control import broker as broker_module

    broker = DeviceBroker()
    broker.connections["device-context"] = _connection()
    monkeypatch.setattr(broker_module, "get_device_broker", lambda: broker)
    context = {
        "local_device_id": "device-context",
        "local_authorization": {
            "device_online": False,
            "device_capabilities": ["forged"],
            "agent_capabilities": ["local.mcp.fs.read_file"],
        },
        "local_tool_descriptors": {"forged": {}},
    }

    _bind_local_runtime_context(context)

    assert context["local_authorization"]["device_online"] is True
    assert context["local_authorization"]["device_capabilities"] == [
        "local.mcp.fs.read_file"
    ]
    assert set(context["local_tool_descriptors"]) == {"local.mcp.fs.read_file"}


def test_local_context_rejects_missing_or_outdated_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.device_control import broker as broker_module

    broker = DeviceBroker()
    monkeypatch.setattr(broker_module, "get_device_broker", lambda: broker)
    context = {
        "local_device_id": "missing",
        "local_authorization": {"device_online": True},
    }
    with pytest.raises(Exception, match="offline or unavailable"):
        _bind_local_runtime_context(context)
    broker.connections["missing"] = _connection(allowed=False)
    with pytest.raises(Exception, match="offline or unavailable"):
        _bind_local_runtime_context(context)


def test_local_context_rejects_a_device_owned_by_another_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.device_control import broker as broker_module

    broker = DeviceBroker()
    broker.connections["device-context"] = _connection(owner_id="owner-a")
    monkeypatch.setattr(broker_module, "get_device_broker", lambda: broker)
    context = {
        "local_device_id": "device-context",
        "local_authorization": {"agent_capabilities": ["local.mcp.fs.read_file"]},
    }
    with pytest.raises(Exception, match="owned by another user"):
        _bind_local_runtime_context(context, caller_id="owner-b")
