from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agentplatform.rbac_models import UserModel
from app.gateway.authz import get_current_rbac_user
from app.gateway.routers import devices
from deerflow.persistence.base import Base


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
        token = registration["session_token"]
        assert registration["device"]["status"] == "pending"

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
