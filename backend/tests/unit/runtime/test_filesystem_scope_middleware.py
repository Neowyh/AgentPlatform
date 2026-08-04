from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from ideer.agents.middlewares.filesystem_scope_middleware import FilesystemScopeMiddleware


def _request(name: str, **args: str) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={"name": name, "id": "call-1", "args": args},
        tool=None,
        state={},
        runtime=MagicMock(),
    )


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("read_file", {"path": "/inputs/case/report.md"}),
        ("ls", {"path": "/inputs/case"}),
        ("glob", {"path": "/inputs/case", "pattern": "**/*.md"}),
        ("grep", {"path": "/inputs/case", "pattern": "failure"}),
        ("view_image", {"image_path": "/inputs/case/chart.png"}),
        ("write_file", {"path": "/outputs/evidence/table.json"}),
        ("str_replace", {"path": "/outputs/evidence/table.json"}),
    ],
)
def test_filesystem_scope_allows_paths_within_declared_roots(name: str, args: dict[str, str]) -> None:
    middleware = FilesystemScopeMiddleware(
        read_roots=["/inputs/case"],
        write_roots=["/outputs/evidence"],
    )
    expected = ToolMessage(content="ok", tool_call_id="call-1", name=name)

    assert middleware.wrap_tool_call(_request(name, **args), lambda _request: expected) is expected


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("read_file", {"path": "relative/report.md"}),
        ("read_file", {"path": "/inputs/case/../secret.md"}),
        ("read_file", {"path": "/inputs/case\\..\\secret.md"}),
        ("read_file", {"path": "/inputs/case-other/secret.md"}),
        ("read_file", {"path": "/outputs/evidence/table.json"}),
        ("write_file", {"path": "/inputs/case/report.md"}),
        ("view_image", {"image_path": "/inputs/case-other/chart.png"}),
    ],
)
def test_filesystem_scope_blocks_traversal_prefix_bypass_and_wrong_access(
    name: str,
    args: dict[str, str],
) -> None:
    middleware = FilesystemScopeMiddleware(
        read_roots=["/inputs/case"],
        write_roots=["/outputs/evidence"],
    )
    called = False

    def handler(_request: ToolCallRequest) -> ToolMessage:
        nonlocal called
        called = True
        return ToolMessage(content="unexpected", tool_call_id="call-1", name=name)

    result = middleware.wrap_tool_call(_request(name, **args), handler)

    assert called is False
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "outside declared" in str(result.content) or "absolute path" in str(result.content) or "traversal" in str(result.content)


@pytest.mark.asyncio
async def test_filesystem_scope_applies_to_async_calls_and_ignores_unmanaged_tools() -> None:
    middleware = FilesystemScopeMiddleware(read_roots=["/inputs/case"], write_roots=[])
    calls: list[str] = []

    async def handler(request: ToolCallRequest) -> ToolMessage:
        calls.append(str(request.tool_call["name"]))
        return ToolMessage(content="ok", tool_call_id="call-1", name=str(request.tool_call["name"]))

    denied = await middleware.awrap_tool_call(_request("read_file", path="/evidence/table.json"), handler)
    allowed = await middleware.awrap_tool_call(_request("present_files", path="/evidence/table.json"), handler)

    assert isinstance(denied, ToolMessage) and denied.status == "error"
    assert isinstance(allowed, ToolMessage) and allowed.status == "success"
    assert calls == ["present_files"]
