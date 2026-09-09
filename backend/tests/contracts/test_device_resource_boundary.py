from fastapi import FastAPI

from app.agentplatform.resource_models import ResourceType
from app.gateway.routers import devices


def test_device_is_not_a_resource_type_or_resource_route() -> None:
    assert "device" not in {resource_type.value for resource_type in ResourceType}
    assert all(not route.path.startswith("/api/resources") for route in devices.router.routes)


def test_device_router_owns_control_plane_paths() -> None:
    app = FastAPI()
    app.include_router(devices.router)
    paths = {route.path for route in app.routes}

    assert "/api/devices/pairing" in paths
    assert "/api/devices/register" in paths
    assert "/api/devices/{device_id}/heartbeat" in paths
    assert "/api/devices/{device_id}/revoke" in paths
