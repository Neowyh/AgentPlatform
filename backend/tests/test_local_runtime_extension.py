from agentplatform_extension.local_runtime import (
    DeviceRoute,
    LocalAuthorization,
    RunDeviceRouter,
    assemble_local_tools,
    child_authorization,
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
