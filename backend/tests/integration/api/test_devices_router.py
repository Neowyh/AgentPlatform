import asyncio
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agentplatform.rbac_models import UserModel
from app.device_control.broker import get_device_broker
from app.device_control.protocol import MessageType, TaskEnvelope, public_key_text, sign_envelope
from app.gateway.authz import get_current_rbac_user
from app.gateway.routers import devices
from deerflow.persistence.base import Base

sys.path.insert(0, str(Path(__file__).parents[4] / "local-runtime"))
from core.transport import LocalRuntimeClient


@pytest_asyncio.fixture
async def device_factory(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(UserModel(id="owner", username="owner@example.com", role="user"))
        await session.commit()
    monkeypatch.setattr(devices, "get_session_factory", lambda: factory)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_device_http_gate_covers_pair_online_offline_revoke(device_factory) -> None:
    app = FastAPI()
    app.include_router(devices.router)
    owner = UserModel(id="owner", username="owner@example.com", role="user")
    app.dependency_overrides[get_current_rbac_user] = lambda: owner

    with TestClient(app) as client:
        pairing = client.post("/api/devices/pairing")
        assert pairing.status_code == 200
        challenge = pairing.json()

        registered = client.post(
            "/api/devices/register",
            json={
                "pairing_code": challenge["code"],
                "name": "Laptop",
                "public_key": "ssh-ed25519 AAAA-http-device-key",
                "protocol_version": "1",
                "runtime_version": "0.1.0",
                "capabilities": ["echo"],
            },
        )
        assert registered.status_code == 200
        registration = registered.json()
        device_id = registration["device"]["id"]
        assert "session_token" not in registration
        assert registration["device"]["status"] == "pending"

        confirmed = client.post(
            f"/api/devices/pairing/{challenge['pairing_id']}/confirm",
            json={"code": challenge["code"]},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["id"] == device_id

        completed = client.post(
            "/api/devices/register/complete",
            json={
                "device_id": device_id,
                "public_key": "ssh-ed25519 AAAA-http-device-key",
                "claim_token": registration["claim_token"],
            },
        )
        assert completed.status_code == 200
        token = completed.json()["session_token"]

        detail = client.get(f"/api/devices/{device_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == device_id

        online = client.post(f"/api/devices/{device_id}/heartbeat", headers={"X-Device-Session": token}, json={})
        assert online.status_code == 200
        assert online.json()["status"] == "online"

        offline = client.post(f"/api/devices/{device_id}/disconnect", headers={"X-Device-Session": token})
        assert offline.status_code == 200
        assert offline.json()["status"] == "offline"

        revoked = client.post(f"/api/devices/{device_id}/revoke")
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"

        denied = client.post(f"/api/devices/{device_id}/heartbeat", headers={"X-Device-Session": token}, json={})
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "DEVICE_REVOKED"


@pytest.mark.asyncio
async def test_websocket_device_initiates_and_receives_signed_echo_receipt(device_factory) -> None:
    app = FastAPI()
    app.include_router(devices.router)
    owner = UserModel(id="owner", username="owner@example.com", role="user")
    app.dependency_overrides[get_current_rbac_user] = lambda: owner
    broker = get_device_broker()
    broker.connections.clear()
    broker.tasks.clear()
    device_key = Ed25519PrivateKey.generate()

    with TestClient(app) as client:
        pairing = client.post("/api/devices/pairing").json()
        registered = client.post(
            "/api/devices/register",
            json={
                "pairing_code": pairing["code"],
                "name": "Broker laptop",
                "public_key": public_key_text(device_key.public_key()),
                "protocol_version": "1",
                "runtime_version": "0.1.0",
                "capabilities": ["echo"],
            },
        ).json()
        device = registered["device"]
        confirmed = client.post(
            f"/api/devices/pairing/{pairing['pairing_id']}/confirm",
            json={"code": pairing["code"]},
        )
        assert confirmed.status_code == 200
        completed = client.post(
            "/api/devices/register/complete",
            json={
                "device_id": device["id"],
                "public_key": public_key_text(device_key.public_key()),
                "claim_token": registered["claim_token"],
            },
        ).json()
        session_id = completed["session_id"]
        token = completed["session_token"]

        with client.websocket_connect("/api/devices/ws") as websocket:
            hello = sign_envelope(
                private_key=device_key,
                message_type=MessageType.HELLO,
                device_id=device["id"],
                session_id=session_id,
                payload={
                    "session_token": token,
                    "public_key": public_key_text(device_key.public_key()),
                    "protocol_version": "1",
                    "runtime_version": "0.1.0",
                    "capabilities": ["echo"],
                },
            )
            websocket.send_text(hello.model_dump_json(by_alias=True))
            server_hello = TaskEnvelope.model_validate_json(websocket.receive_text())
            assert server_hello.type == MessageType.HELLO

            dispatched = client.post(
                f"/api/devices/{device['id']}/tasks/echo",
                json={"run_id": "run-echo", "tool_call_id": "tool-echo", "value": "hello"},
            ).json()
            task = TaskEnvelope.model_validate_json(websocket.receive_text())
            task.verify(public_key=broker.server_private_key.public_key(), expected_device_id=device["id"], expected_session_id=session_id)
            assert task.task_id == dispatched["task_id"]

            for message_type, payload in (
                (MessageType.TASK_ACK, {"accepted": True}),
                (MessageType.TASK_PROGRESS, {"fraction": 1.0}),
                (MessageType.TASK_RESULT, {"receipt": {"status": "completed", "task_id": task.task_id}}),
            ):
                response = sign_envelope(
                    private_key=device_key,
                    message_type=message_type,
                    device_id=device["id"],
                    session_id=session_id,
                    task_id=task.task_id,
                    payload=payload,
                )
                websocket.send_text(response.model_dump_json(by_alias=True))

            status = client.get(f"/api/devices/tasks/{task.task_id}")
            assert status.status_code == 200
            assert status.json()["status"] == "completed"
            assert status.json()["receipt"]["task_id"] == task.task_id


@pytest.mark.asyncio
async def test_local_runtime_client_completes_echo_through_temporary_service(device_factory) -> None:
    app = FastAPI()
    app.include_router(devices.router)
    owner = UserModel(id="owner", username="owner@example.com", role="user")
    app.dependency_overrides[get_current_rbac_user] = lambda: owner
    broker = get_device_broker()
    broker.connections.clear()
    broker.tasks.clear()
    device_key = Ed25519PrivateKey.generate()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    server_task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started and server.servers:
                break
            await asyncio.sleep(0.01)
        assert server.started and server.servers
        port = server.servers[0].sockets[0].getsockname()[1]

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            pairing = (await client.post("/api/devices/pairing")).json()
            registered = (
                await client.post(
                    "/api/devices/register",
                    json={
                        "pairing_code": pairing["code"],
                        "name": "Local runtime",
                        "public_key": public_key_text(device_key.public_key()),
                        "protocol_version": "1",
                        "runtime_version": "0.1.0",
                        "capabilities": ["echo"],
                    },
                )
            ).json()
            device = registered["device"]
            assert (await client.post(f"/api/devices/pairing/{pairing['pairing_id']}/confirm", json={"code": pairing["code"]})).status_code == 200
            completed = (
                await client.post(
                    "/api/devices/register/complete",
                    json={
                        "device_id": device["id"],
                        "public_key": public_key_text(device_key.public_key()),
                        "claim_token": registered["claim_token"],
                    },
                )
            ).json()
            runtime = LocalRuntimeClient(
                server_url=f"ws://127.0.0.1:{port}/api/devices/ws",
                device_id=device["id"],
                session_token=completed["session_token"],
                session_id=completed["session_id"],
                private_key=device_key,
            )
            runtime_task = asyncio.create_task(runtime.run())
            for _ in range(100):
                if device["id"] in broker.connections:
                    break
                await asyncio.sleep(0.01)
            if runtime_task.done():
                runtime_task.result()
            assert device["id"] in broker.connections

            dispatched = await client.post(
                f"/api/devices/{device['id']}/tasks/echo",
                json={"run_id": "runtime-run", "tool_call_id": "runtime-tool", "value": "hello"},
            )
            assert dispatched.status_code == 200
            task_id = dispatched.json()["task_id"]
            for _ in range(100):
                status = (await client.get(f"/api/devices/tasks/{task_id}")).json()
                if status["status"] == "completed":
                    break
                await asyncio.sleep(0.01)
            assert status["status"] == "completed"
            assert status["receipt"]["status"] == "completed"
            runtime.connection and await runtime.connection.close()
            await asyncio.wait_for(runtime_task, timeout=1)
    finally:
        server.should_exit = True
        await asyncio.wait_for(server_task, timeout=5)


@pytest.mark.asyncio
async def test_local_runtime_completes_mcp_task_through_broker_with_receipt(device_factory, tmp_path: Path) -> None:
    """M9 gate: a configured stdio MCP server is reached only via Server task → Local Runtime → local MCP."""
    sys.path.insert(0, str(Path(__file__).parents[4] / "local-runtime"))
    from core.mcp import LocalMCPService, MCPSpec, MCPSupervisor
    from core.policy import LocalPolicy
    from core.transport import LocalRuntimeClient as RuntimeClient

    fixture_server = Path(__file__).parents[4] / "local-runtime" / "tests" / "fixtures" / "filesystem_mcp_server.py"
    (tmp_path / "hello.txt").write_text("mcp over the broker", encoding="utf-8")

    app = FastAPI()
    app.include_router(devices.router)
    owner = UserModel(id="owner", username="owner@example.com", role="user")
    app.dependency_overrides[get_current_rbac_user] = lambda: owner
    broker = get_device_broker()
    broker.connections.clear()
    broker.tasks.clear()
    device_key = Ed25519PrivateKey.generate()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    server_task = asyncio.create_task(server.serve())
    supervisor = MCPSupervisor(
        [
            MCPSpec(
                name="fs",
                transport="stdio",
                command=(sys.executable, str(fixture_server)),
                env={"MCP_ROOT": str(tmp_path)},
                tool_timeout_seconds=10,
                start_timeout_seconds=10,
            )
        ]
    )
    try:
        for _ in range(100):
            if server.started and server.servers:
                break
            await asyncio.sleep(0.01)
        assert server.started and server.servers
        port = server.servers[0].sockets[0].getsockname()[1]
        await supervisor.start_all()

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            pairing = (await client.post("/api/devices/pairing")).json()
            registered = (
                await client.post(
                    "/api/devices/register",
                    json={
                        "pairing_code": pairing["code"],
                        "name": "MCP runtime",
                        "public_key": public_key_text(device_key.public_key()),
                        "protocol_version": "1",
                        "runtime_version": "0.1.0",
                        "capabilities": ["echo"],
                    },
                )
            ).json()
            device = registered["device"]
            assert (await client.post(f"/api/devices/pairing/{pairing['pairing_id']}/confirm", json={"code": pairing["code"]})).status_code == 200
            completed = (
                await client.post(
                    "/api/devices/register/complete",
                    json={
                        "device_id": device["id"],
                        "public_key": public_key_text(device_key.public_key()),
                        "claim_token": registered["claim_token"],
                    },
                )
            ).json()
            runtime = RuntimeClient(
                server_url=f"ws://127.0.0.1:{port}/api/devices/ws",
                device_id=device["id"],
                session_token=completed["session_token"],
                session_id=completed["session_id"],
                private_key=device_key,
                mcp_service=LocalMCPService(
                    supervisor,
                    policy=LocalPolicy(),
                ),
            )
            runtime_task = asyncio.create_task(runtime.run())
            for _ in range(100):
                if device["id"] in broker.connections:
                    break
                await asyncio.sleep(0.01)
            if runtime_task.done():
                runtime_task.result()
            assert device["id"] in broker.connections

            for _ in range(100):
                capabilities = (await client.get(f"/api/devices/{device['id']}")).json()["capabilities"]
                if "local.mcp.fs.read_file" in capabilities:
                    break
                await asyncio.sleep(0.01)
            assert "local.mcp.fs.read_file" in capabilities

            dispatched = await client.post(
                f"/api/devices/{device['id']}/tasks/local",
                json={
                    "run_id": "mcp-run",
                    "tool_call_id": "mcp-tool-call",
                    "operation": "local.mcp.fs.read_file",
                    "payload": {"arguments": {"path": "hello.txt"}},
                },
            )
            assert dispatched.status_code == 200
            task_id = dispatched.json()["task_id"]

            status = (await client.get(f"/api/devices/tasks/{task_id}")).json()
            for _ in range(300):
                status = (await client.get(f"/api/devices/tasks/{task_id}")).json()
                if status["status"] == "consent_required":
                    break
                await asyncio.sleep(0.01)
            assert status["status"] == "consent_required"

            decided = await client.post(
                f"/api/devices/tasks/{task_id}/consent",
                json={"approved": True, "actor_id": "owner@example.com"},
            )
            assert decided.status_code == 200

            for _ in range(300):
                status = (await client.get(f"/api/devices/tasks/{task_id}")).json()
                if status["status"] in {"completed", "failed", "timed_out"}:
                    break
                await asyncio.sleep(0.01)
            assert status["status"] == "completed", status
            receipt = status["receipt"]
            assert receipt["capability"] == "local.mcp.fs.read_file"
            assert receipt["status"] == "completed"
            assert receipt["consent_decision"] == "approved"
            assert status["result"]["content"][0]["text"] == "mcp over the broker"
            assert status["result"]["status"] == "completed"

            runtime.connection and await runtime.connection.close()
            await asyncio.wait_for(runtime_task, timeout=1)
    finally:
        await supervisor.stop_all()
        server.should_exit = True
        await asyncio.wait_for(server_task, timeout=5)
