"""HTTP control-plane API for user-bound Local Runtime devices."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.agentplatform.rbac_models import UserModel, UserRole
from app.device_control.broker import DeviceBroker, DeviceConnection, get_device_broker
from app.device_control.models import DeviceModel
from app.device_control.protocol import MessageType, ProtocolCompatibility, ProtocolError, TaskEnvelope, load_public_key, negotiate_protocol
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
    pairing_id: str
    claim_token: str
    claim_expires_at: datetime


class DeviceRegistrationCompleteRequest(BaseModel):
    device_id: str = Field(min_length=1)
    public_key: str = Field(min_length=32)
    claim_token: str = Field(min_length=16)


class PairingConfirmRequest(BaseModel):
    code: str = Field(min_length=8)


class DeviceSessionResponse(BaseModel):
    device: dict
    session_id: str
    session_token: str
    session_expires_at: datetime


class DeviceHeartbeatRequest(BaseModel):
    capabilities: list[str] | None = None


class EchoTaskRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    tool_call_id: str = Field(min_length=1, max_length=128)
    value: object


class TaskResponse(BaseModel):
    task_id: str
    device_id: str
    session_id: str
    status: str
    run_id: str
    tool_call_id: str
    expires_at: datetime
    receipt: dict | None = None
    result: object = None
    error: str | None = None
    error_code: str | None = None

    @classmethod
    def from_record(cls, record) -> TaskResponse:
        return cls(
            task_id=record.task_id,
            device_id=record.device_id,
            session_id=record.session_id,
            status=record.status,
            run_id=record.run_id,
            tool_call_id=record.tool_call_id,
            expires_at=record.expires_at,
            receipt=record.receipt,
            result=record.result,
            error=record.error,
            error_code=record.error_code,
        )


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
    claim = await _run(lambda service: service.register_device(**payload.model_dump()))
    return DeviceRegisterResponse(device=DeviceResponse.from_model(claim.device).model_dump(), pairing_id=claim.pairing_id, claim_token=claim.claim_token, claim_expires_at=claim.claim_expires_at)


@router.post("/pairing/{pairing_id}/confirm", response_model=DeviceResponse)
async def confirm_pairing(pairing_id: str, payload: PairingConfirmRequest, current_user: UserModel = Depends(get_current_rbac_user)) -> DeviceResponse:
    device = await _run(lambda service: service.confirm_pairing(pairing_id, owner_id=str(current_user.id), code=payload.code))
    return DeviceResponse.from_model(device)


@router.post("/register/complete", response_model=DeviceSessionResponse)
async def complete_registration(payload: DeviceRegistrationCompleteRequest) -> DeviceSessionResponse:
    registered = await _run(lambda service: service.complete_registration(**payload.model_dump()))
    return DeviceSessionResponse(device=DeviceResponse.from_model(registered.device).model_dump(), session_id=registered.session_id, session_token=registered.session_token, session_expires_at=registered.session_expires_at)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(current_user: UserModel = Depends(get_current_rbac_user)) -> list[DeviceResponse]:
    owner_id = None if current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value} else str(current_user.id)
    devices = await _run(lambda service: service.list_devices(owner_id=owner_id))
    return [DeviceResponse.from_model(device) for device in devices]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, current_user: UserModel = Depends(get_current_rbac_user)) -> DeviceResponse:
    is_admin = current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value}
    device = await _run(lambda service: service.get_device(device_id, actor_id=str(current_user.id), is_admin=is_admin))
    return DeviceResponse.from_model(device)


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


@router.post("/{device_id}/tasks/echo", response_model=TaskResponse)
async def send_echo_task(device_id: str, payload: EchoTaskRequest, current_user: UserModel = Depends(get_current_rbac_user)) -> TaskResponse:
    is_admin = current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value}
    await _run(lambda service: service.get_device(device_id, actor_id=str(current_user.id), is_admin=is_admin))
    record = await get_device_broker().send_echo_task(device_id=device_id, run_id=payload.run_id, tool_call_id=payload.tool_call_id, value=payload.value)
    return TaskResponse.from_record(record)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, current_user: UserModel = Depends(get_current_rbac_user)) -> TaskResponse:
    broker = get_device_broker()
    try:
        record = broker.get_task(task_id)
    except ProtocolError:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "task id is unknown"})
    is_admin = current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value}
    await _run(lambda service: service.get_device(record.device_id, actor_id=str(current_user.id), is_admin=is_admin))
    return TaskResponse.from_record(record)


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str, current_user: UserModel = Depends(get_current_rbac_user)) -> TaskResponse:
    broker = get_device_broker()
    try:
        record = broker.get_task(task_id)
    except ProtocolError:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "task id is unknown"})
    is_admin = current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.DEPARTMENT_ADMIN.value}
    await _run(lambda service: service.get_device(record.device_id, actor_id=str(current_user.id), is_admin=is_admin))
    return TaskResponse.from_record(await broker.cancel_task(task_id))


@router.websocket("/ws")
async def device_websocket(websocket: WebSocket) -> None:
    """Accept only device-initiated, signed sessions."""
    await websocket.accept()
    connection: DeviceConnection | None = None
    broker: DeviceBroker = get_device_broker()
    try:
        hello = TaskEnvelope.model_validate_json(await websocket.receive_text())
        if hello.type != MessageType.HELLO:
            raise ProtocolError("HELLO_REQUIRED", "the first message must be hello")
        public_key_text = str(hello.payload.get("public_key", ""))
        public_key = load_public_key(public_key_text)
        hello.verify(public_key=public_key, expected_device_id=hello.device_id, expected_session_id=hello.session_id)
        compatibility = negotiate_protocol(str(hello.payload.get("protocol_version", "")))
        session_token = str(hello.payload.get("session_token", ""))
        sf = get_session_factory()
        if sf is None:
            raise ProtocolError("PERSISTENCE_UNAVAILABLE", "device persistence is unavailable")
        async with sf() as session:
            from app.device_control.service import DeviceControlService

            service = DeviceControlService(session)
            device, device_session = await service._authorized_session(hello.device_id, session_token)
            if device_session.id != hello.session_id or device.public_key != public_key_text:
                raise ProtocolError("SESSION_MISMATCH", "device session or public key does not match")
            if device.policy_hash is not None and hello.payload.get("policy_hash") != device.policy_hash:
                raise ProtocolError("POLICY_HASH_MISMATCH", "device policy hash does not match registration")
            if compatibility == ProtocolCompatibility.BLOCKED:
                device.status = "blocked"
                await session.commit()
                raise ProtocolError("PROTOCOL_BLOCKED", "device protocol is incompatible")
            await service.heartbeat(hello.device_id, session_token, capabilities=hello.payload.get("capabilities"))
            if compatibility == ProtocolCompatibility.OUTDATED:
                device.status = "outdated"
                await session.commit()
        connection = DeviceConnection(hello.device_id, hello.session_id, session_token, public_key, websocket)
        connection.tasks_allowed = compatibility == ProtocolCompatibility.COMPATIBLE
        await broker.attach(connection)
        while True:
            message = TaskEnvelope.model_validate_json(await websocket.receive_text())
            await broker.receive(connection, message)
            if message.type in {MessageType.HEARTBEAT, MessageType.CAPABILITY_UPDATE}:
                sf = get_session_factory()
                if sf is None:
                    raise ProtocolError("PERSISTENCE_UNAVAILABLE", "device persistence is unavailable")
                async with sf() as session:
                    from app.device_control.service import DeviceControlService

                    await DeviceControlService(session).heartbeat(
                        connection.device_id,
                        connection.session_token,
                        capabilities=message.payload.get("capabilities"),
                    )
    except WebSocketDisconnect:
        pass
    except (ProtocolError, DeviceControlError, ValueError):
        await websocket.close(code=4003, reason="device protocol rejected")
    finally:
        if connection is not None:
            await broker.detach(connection.device_id, connection.session_id)
