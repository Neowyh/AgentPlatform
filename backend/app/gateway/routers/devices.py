"""HTTP control-plane API for user-bound Local Runtime devices."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.agentplatform.rbac_models import UserModel, UserRole
from app.device_control.models import DeviceModel
from app.device_control.service import DeviceControlError, DeviceControlService
from app.gateway.authz import get_current_rbac_user
from deerflow.persistence.engine import get_session_factory

router = APIRouter(prefix="/api/devices", tags=["devices"])


class PairingCreateResponse(BaseModel):
    pairing_id: str
    code: str
    pairing_url: str
    expires_at: datetime


class DeviceRegisterRequest(BaseModel):
    pairing_code: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    public_key: str = Field(min_length=32)
    protocol_version: str = Field(min_length=1, max_length=32)
    runtime_version: str = Field(min_length=1, max_length=64)
    capabilities: list[str] = Field(default_factory=list)
    policy_hash: str | None = Field(default=None, max_length=128)


class DeviceRegisterResponse(BaseModel):
    device: dict
    session_token: str
    session_expires_at: datetime


class DeviceHeartbeatRequest(BaseModel):
    capabilities: list[str] | None = None


class DeviceResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    status: str
    protocol_version: str
    runtime_version: str
    capabilities: list[str]
    policy_hash: str | None
    last_seen: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, device: DeviceModel) -> DeviceResponse:
        return cls(
            id=device.id,
            owner_id=device.owner_id,
            name=device.name,
            status=device.status,
            protocol_version=device.protocol_version,
            runtime_version=device.runtime_version,
            capabilities=list(device.capabilities or []),
            policy_hash=device.policy_hash,
            last_seen=device.last_seen,
            created_at=device.created_at,
        )


async def _run(operation):
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=503, detail="device persistence is unavailable")
    async with sf() as session:
        try:
            return await operation(DeviceControlService(session))
        except DeviceControlError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/pairing", response_model=PairingCreateResponse)
async def create_pairing(current_user: UserModel = Depends(get_current_rbac_user)) -> PairingCreateResponse:
    challenge = await _run(lambda service: service.create_pairing(str(current_user.id)))
    return PairingCreateResponse(
        pairing_id=challenge.pairing_id,
        code=challenge.code,
        pairing_url=challenge.pairing_url,
        expires_at=challenge.expires_at,
    )


@router.post("/register", response_model=DeviceRegisterResponse)
async def register_device(payload: DeviceRegisterRequest) -> DeviceRegisterResponse:
    registered = await _run(lambda service: service.register_device(**payload.model_dump()))
    return DeviceRegisterResponse(device=DeviceResponse.from_model(registered.device).model_dump(), session_token=registered.session_token, session_expires_at=registered.session_expires_at)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(current_user: UserModel = Depends(get_current_rbac_user)) -> list[DeviceResponse]:
    owner_id = None if current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value} else str(current_user.id)
    devices = await _run(lambda service: service.list_devices(owner_id=owner_id))
    return [DeviceResponse.from_model(device) for device in devices]


@router.post("/{device_id}/heartbeat", response_model=DeviceResponse)
async def heartbeat(device_id: str, payload: DeviceHeartbeatRequest, x_device_session: str | None = Header(default=None)) -> DeviceResponse:
    if not x_device_session:
        raise HTTPException(status_code=401, detail={"code": "DEVICE_SESSION_INVALID", "message": "device session header required"})
    device = await _run(lambda service: service.heartbeat(device_id, x_device_session, capabilities=payload.capabilities))
    return DeviceResponse.from_model(device)


@router.post("/{device_id}/disconnect", response_model=DeviceResponse)
async def disconnect(device_id: str, x_device_session: str | None = Header(default=None)) -> DeviceResponse:
    if not x_device_session:
        raise HTTPException(status_code=401, detail={"code": "DEVICE_SESSION_INVALID", "message": "device session header required"})
    device = await _run(lambda service: service.disconnect(device_id, x_device_session))
    return DeviceResponse.from_model(device)


@router.post("/{device_id}/revoke", response_model=DeviceResponse)
async def revoke_device(device_id: str, current_user: UserModel = Depends(get_current_rbac_user)) -> DeviceResponse:
    is_admin = current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value}
    device = await _run(lambda service: service.revoke(device_id, actor_id=str(current_user.id), is_admin=is_admin))
    return DeviceResponse.from_model(device)
