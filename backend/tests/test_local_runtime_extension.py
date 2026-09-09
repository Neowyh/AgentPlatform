from agentplatform_extension.local_runtime import (
    DeviceRoute,
    LocalAuthorization,
    RunDeviceRouter,
    assemble_local_tools,
    child_authorization,
    filter_local_tools,
)


def _authorization() -> LocalAuthorization:
    values = frozenset({"local.files.list", "local.files.read"})
    return LocalAuthorization(*(values,) * 6, device_online=True)


def test_tools_are_hidden_when_device_is_offline_and_intersection_is_strict() -> None:
    auth = _authorization()
    assert {tool.name for tool in assemble_local_tools(auth)} == {"local.files.list", "local.files.read"}
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
    assert child_authorization(_authorization(), {"local.python", "local.files.write"}).effective == set()


def test_local_filter_preserves_server_tools_and_drops_unauthorized_local_tools() -> None:
    tools = (*assemble_local_tools(_authorization()),)
    tools += (type(tools[0])("server.tool", "server"),)

    filtered = filter_local_tools(tools, LocalAuthorization())

    assert [tool.name for tool in filtered] == ["server.tool"]
