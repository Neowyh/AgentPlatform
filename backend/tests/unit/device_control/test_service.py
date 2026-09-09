from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agentplatform.rbac_models import UserModel
from app.device_control.models import DeviceStatus
from app.device_control.service import DeviceControlError, DeviceControlService
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        value.add(UserModel(id="owner", username="owner@example.com", role="user"))
        value.add(UserModel(id="other", username="other@example.com", role="user"))
        await value.commit()
        yield value
    await engine.dispose()


@pytest.mark.asyncio
async def test_pair_register_heartbeat_disconnect_and_revoke(session: AsyncSession) -> None:
    service = DeviceControlService(session)
    challenge = await service.create_pairing("owner")
    registered = await service.register_device(
        pairing_code=challenge.code,
        name="Laptop",
        public_key="ssh-ed25519 AAAA-device-public-key",
        protocol_version="1",
        runtime_version="0.1.0",
        capabilities=["echo", "echo"],
        policy_hash="policy-v1",
    )

    assert registered.device.owner_id == "owner"
    assert registered.device.status == DeviceStatus.PENDING
    assert registered.device.capabilities == ["echo"]

    with pytest.raises(DeviceControlError, match="confirmation is required"):
        await service.complete_registration(
            device_id=registered.device.id,
            public_key="ssh-ed25519 AAAA-device-public-key",
            claim_token=registered.claim_token,
        )

    await service.confirm_pairing(challenge.pairing_id, owner_id="owner", code=challenge.code)
    completed = await service.complete_registration(
        device_id=registered.device.id,
        public_key="ssh-ed25519 AAAA-device-public-key",
        claim_token=registered.claim_token,
    )

    online = await service.heartbeat(completed.device.id, completed.session_token)
    assert online.status == DeviceStatus.ONLINE
    assert online.last_seen is not None

    offline = await service.disconnect(completed.device.id, completed.session_token)
    assert offline.status == DeviceStatus.OFFLINE

    revoked = await service.revoke(completed.device.id, actor_id="owner", is_admin=False)
    assert revoked.status == DeviceStatus.REVOKED

    with pytest.raises(DeviceControlError, match="cannot connect"):
        await service.heartbeat(completed.device.id, completed.session_token)


@pytest.mark.asyncio
async def test_pairing_is_owner_scoped_and_replay_is_rejected(session: AsyncSession) -> None:
    service = DeviceControlService(session)
    challenge = await service.create_pairing("owner")
    await service.register_device(
        pairing_code=challenge.code,
        name="Laptop",
        public_key="ssh-ed25519 AAAA-device-public-key-2",
        protocol_version="1",
        runtime_version="0.1.0",
        capabilities=[],
        policy_hash=None,
    )

    with pytest.raises(DeviceControlError, match="already used"):
        await service.register_device(
            pairing_code=challenge.code,
            name="Other",
            public_key="ssh-ed25519 AAAA-device-public-key-3",
            protocol_version="1",
            runtime_version="0.1.0",
            capabilities=[],
            policy_hash=None,
        )


@pytest.mark.asyncio
async def test_non_owner_cannot_revoke_or_read_device(session: AsyncSession) -> None:
    service = DeviceControlService(session)
    challenge = await service.create_pairing("owner")
    registered = await service.register_device(
        pairing_code=challenge.code,
        name="Laptop",
        public_key="ssh-ed25519 AAAA-device-public-key-4",
        protocol_version="1",
        runtime_version="0.1.0",
        capabilities=[],
        policy_hash=None,
    )

    with pytest.raises(DeviceControlError, match="not available"):
        await service.confirm_pairing(challenge.pairing_id, owner_id="other", code=challenge.code)

    with pytest.raises(DeviceControlError, match="only the owner"):
        await service.revoke(registered.device.id, actor_id="other", is_admin=False)
    with pytest.raises(DeviceControlError, match="only the owner"):
        await service.get_device(registered.device.id, actor_id="other", is_admin=False)
