import pytest

from ideer.mcp.connector import McpConnector


class _Tool:
    name = "echo"

    async def ainvoke(self, arguments):
        return arguments["value"]


class _Backend:
    async def tools(self):
        return [_Tool()]


@pytest.mark.asyncio
async def test_connector_discovers_once_and_invokes_by_name():
    connector = McpConnector(_Backend())

    assert [tool.name for tool in await connector.tools()] == ["echo"]
    assert await connector.call("echo", {"value": "ok"}) == "ok"


@pytest.mark.asyncio
async def test_connector_rejects_unknown_tool():
    connector = McpConnector(_Backend())

    with pytest.raises(KeyError, match="Unknown MCP tool"):
        await connector.call("missing")
