"""Device control-plane operations shared by HTTP and the future broker."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    DeviceModel,
    DeviceSessionModel,
    DeviceStatus,
    PairingSessionModel,
    PairingStatus,
)
from .pairing import (
    PairingError,
    consume_pairing_code,
    hash_secret,
    new_pairing_code,
    validate_device_transition,
)

PAIRING_TTL = timedelta(minutes=10)
DEVICE_SESSION_TTL = timedelta(hours=1)
DEVICE_CLAIM_TTL = timedelta(minutes=10)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class DeviceControlError(PairingError):
    """A typed control-plane rejection that the router can expose safely."""

    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class PairingChallenge:
    pairing_id: str
    code: str
    pairing_url: str
    expires_at: datetime


@dataclass(frozen=True)
class RegisteredDevice:
    device: DeviceModel
    session_id: str
    session_token: str
    session_expires_at: datetime


@dataclass(frozen=True)
class DeviceClaim:
    device: DeviceModel
    pairing_id: str
    claim_token: str
    claim_expires_at: datetime


class DeviceControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pairing(
        self, owner_id: str, *, base_url: str = "/device-pair"
    ) -> PairingChallenge:
        code, digest = new_pairing_code()
        pairing_id = str(uuid4())
        expires_at = datetime.now(UTC) + PAIRING_TTL
        self.session.add(
            PairingSessionModel(
                id=pairing_id,
                owner_id=owner_id,
                code_digest=digest,
                status=PairingStatus.OPEN,
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        return PairingChallenge(pairing_id, code, f"{base_url}?code={code}", expires_at)

    async def register_device(
        self,
        *,
        pairing_code: str,
        name: str,
        public_key: str,
        protocol_version: str,
        runtime_version: str,
        capabilities: list[str],
        policy_hash: str | None,
    ) -> DeviceClaim:
        pairing = (
            await self.session.execute(
                select(PairingSessionModel)
                .where(PairingSessionModel.code_digest == hash_secret(pairing_code))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if pairing is None:
            raise DeviceControlError("PAIRING_INVALID", "pairing code invalid", 400)
        try:
            consume_pairing_code(
                pairing.code_digest,
                pairing_code,
                expires_at=pairing.expires_at,
                consumed=pairing.status != PairingStatus.OPEN,
            )
        except PairingError as exc:
            code = (
                "PAIRING_EXPIRED"
                if "expired" in str(exc)
                else "PAIRING_ALREADY_USED"
                if "already used" in str(exc)
                else "PAIRING_INVALID"
            )
            raise DeviceControlError(
                code, str(exc), 409 if code != "PAIRING_INVALID" else 400
            ) from exc

        device = DeviceModel(
            id=str(uuid4()),
            owner_id=pairing.owner_id,
            name=name,
            public_key=public_key,
            status=DeviceStatus.PENDING,
            protocol_version=protocol_version,
            runtime_version=runtime_version,
            capabilities=sorted(set(capabilities)),
            policy_hash=policy_hash,
        )
        claim_token = secrets.token_urlsafe(32)
        claim_expires_at = datetime.now(UTC) + DEVICE_CLAIM_TTL
        self.session.add(device)
        pairing.status = PairingStatus.CLAIMED
        pairing.claimed_at = datetime.now(UTC)
        pairing.claim_token_digest = hash_secret(claim_token)
        pairing.claim_expires_at = claim_expires_at
        pairing.device_id = device.id
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DeviceControlError(
                "DEVICE_ALREADY_REGISTERED",
                "device name or public key is already registered",
                409,
            ) from exc
        await self.session.refresh(device)
        return DeviceClaim(device, pairing.id, claim_token, claim_expires_at)

    async def confirm_pairing(
        self, pairing_id: str, *, owner_id: str, code: str
    ) -> DeviceModel:
        pairing = (
            await self.session.execute(
                select(PairingSessionModel)
                .where(PairingSessionModel.id == pairing_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if pairing is None or pairing.owner_id != owner_id:
            raise DeviceControlError(
                "PAIRING_NOT_FOUND", "pairing challenge is not available", 404
            )
        if pairing.status != PairingStatus.CLAIMED:
            raise DeviceControlError(
                "PAIRING_NOT_CONFIRMABLE",
                "pairing challenge is not waiting for confirmation",
                409,
            )
        try:
            consume_pairing_code(
                pairing.code_digest, code, expires_at=pairing.expires_at, consumed=False
            )
        except PairingError as exc:
            code_name = (
                "PAIRING_EXPIRED" if "expired" in str(exc) else "PAIRING_INVALID"
            )
            raise DeviceControlError(
                code_name, str(exc), 409 if code_name == "PAIRING_EXPIRED" else 400
            ) from exc
        device = await self._get_device(pairing.device_id or "")
        pairing.status = PairingStatus.CONFIRMED
        pairing.confirmed_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def complete_registration(
        self, *, device_id: str, public_key: str, claim_token: str
    ) -> RegisteredDevice:
        pairing = (
            await self.session.execute(
                select(PairingSessionModel)
                .where(PairingSessionModel.device_id == device_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if pairing is None or pairing.status != PairingStatus.CONFIRMED:
            raise DeviceControlError(
                "PAIRING_NOT_CONFIRMED",
                "owner confirmation is required before registration",
                409,
            )
        if pairing.claim_expires_at is None or _as_utc(
            pairing.claim_expires_at
        ) <= datetime.now(UTC):
            pairing.status = PairingStatus.EXPIRED
            await self.session.commit()
            raise DeviceControlError("PAIRING_EXPIRED", "device claim expired", 409)
        if pairing.claim_token_digest != hash_secret(claim_token):
            raise DeviceControlError(
                "PAIRING_CLAIM_INVALID", "device claim token is invalid", 401
            )
        device = await self._get_device(device_id)
        if device.public_key != public_key:
            raise DeviceControlError(
                "DEVICE_KEY_MISMATCH", "device public key does not match the claim", 401
            )
        token = secrets.token_urlsafe(32)
        session_expires_at = datetime.now(UTC) + DEVICE_SESSION_TTL
        session_id = str(uuid4())
        self.session.add(
            DeviceSessionModel(
                id=session_id,
                device_id=device.id,
                token_digest=hash_secret(token),
                expires_at=session_expires_at,
            )
        )
        pairing.status = PairingStatus.COMPLETED
        pairing.claim_token_digest = None
        await self.session.commit()
        return RegisteredDevice(device, session_id, token, session_expires_at)

    async def list_devices(self, *, owner_id: str | None = None) -> list[DeviceModel]:
        stmt = select(DeviceModel).order_by(DeviceModel.created_at.desc())
        if owner_id is not None:
            stmt = stmt.where(DeviceModel.owner_id == owner_id)
        return list((await self.session.execute(stmt)).scalars())

    async def get_device(
        self, device_id: str, *, actor_id: str, is_admin: bool
    ) -> DeviceModel:
        device = await self._get_device(device_id)
        if not is_admin and device.owner_id != actor_id:
            raise DeviceControlError(
                "DEVICE_FORBIDDEN",
                "only the owner or an administrator may view this device",
                403,
            )
        return device

    async def heartbeat(
        self,
        device_id: str,
        token: str,
        *,
        capabilities: list[str] | None = None,
        policy_hash: str | None = None,
    ) -> DeviceModel:
        device = await self._get_device(device_id)
        if device.status in {DeviceStatus.REVOKED, DeviceStatus.BLOCKED}:
            raise DeviceControlError(
                "DEVICE_REVOKED"
                if device.status == DeviceStatus.REVOKED
                else "DEVICE_BLOCKED",
                "device cannot connect",
                403,
            )
        _device, device_session = await self._authorized_session(device_id, token)
        now = datetime.now(UTC)
        if DeviceStatus(device.status) != DeviceStatus.ONLINE:
            validate_device_transition(device.status, DeviceStatus.ONLINE)
            device.status = DeviceStatus.ONLINE
        device.last_seen = now
        device_session.last_seen = now
        if capabilities is not None:
            device.capabilities = sorted(set(capabilities))
        if policy_hash is not None:
            device.policy_hash = policy_hash
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def disconnect(self, device_id: str, token: str) -> DeviceModel:
        device, device_session = await self._authorized_session(device_id, token)
        if DeviceStatus(device.status) == DeviceStatus.ONLINE:
            validate_device_transition(device.status, DeviceStatus.OFFLINE)
            device.status = DeviceStatus.OFFLINE
        device_session.disconnected_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def revoke(
        self, device_id: str, *, actor_id: str, is_admin: bool
    ) -> DeviceModel:
        device = await self._get_device(device_id)
        if device.owner_id != actor_id and not is_admin:
            raise DeviceControlError(
                "DEVICE_FORBIDDEN",
                "only the owner or an administrator may revoke this device",
                403,
            )
        if DeviceStatus(device.status) != DeviceStatus.REVOKED:
            validate_device_transition(device.status, DeviceStatus.REVOKED)
            device.status = DeviceStatus.REVOKED
            device.revoked_at = datetime.now(UTC)
        await self.session.execute(
            DeviceSessionModel.__table__.update()
            .where(DeviceSessionModel.device_id == device_id)
            .values(disconnected_at=datetime.now(UTC))
        )
        await self.session.commit()
        await self.session.refresh(device)
        return device

    async def _get_device(self, device_id: str) -> DeviceModel:
        device = (
            await self.session.execute(
                select(DeviceModel).where(DeviceModel.id == device_id)
            )
        ).scalar_one_or_none()
        if device is None:
            raise DeviceControlError("DEVICE_NOT_FOUND", "device not found", 404)
        return device

    async def _authorized_session(
        self, device_id: str, token: str
    ) -> tuple[DeviceModel, DeviceSessionModel]:
        device = await self._get_device(device_id)
        device_session = (
            await self.session.execute(
                select(DeviceSessionModel).where(
                    DeviceSessionModel.device_id == device_id,
                    DeviceSessionModel.token_digest == hash_secret(token),
                    DeviceSessionModel.disconnected_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        expires_at = (
            device_session.expires_at.replace(tzinfo=UTC)
            if device_session is not None and device_session.expires_at.tzinfo is None
            else device_session.expires_at
            if device_session is not None
            else None
        )
        if device_session is None or expires_at <= datetime.now(UTC):
            raise DeviceControlError(
                "DEVICE_SESSION_INVALID", "device session invalid or expired", 401
            )
        return device, device_session
