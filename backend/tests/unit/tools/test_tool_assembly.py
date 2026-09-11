from langchain_core.tools import StructuredTool

from app.agentplatform.tools.assembly import ToolSet, assemble_tools


def _tool(name: str):
    def invoke() -> str:
        """Return the fixture tool name."""
        return name

    return StructuredTool.from_function(invoke, name=name)


def test_assemble_tools_returns_explicit_deduplicated_active_and_deferred_sets():
    result = assemble_tools(
        [_tool("active"), _tool("deferred"), _tool("deferred")],
        deferred_names=["deferred"],
    )

    assert isinstance(result, ToolSet)
    assert [tool.name for tool in result.active] == ["active"]
    assert [tool.name for tool in result.deferred] == ["deferred"]
    assert result.deferred_names == frozenset({"deferred"})


def test_assemble_tools_filters_tools_not_in_the_effective_capability_set():
    result = assemble_tools(
        [_tool("local.files.read"), _tool("local.python"), _tool("builtin")],
        allowed_names={"local.files.read", "builtin"},
    )

    assert [tool.name for tool in result.active] == ["local.files.read", "builtin"]


def test_assemble_tools_applies_local_visibility_without_filtering_server_tools():
    result = assemble_tools(
        [_tool("local.files.read"), _tool("local.python"), _tool("builtin")],
        local_allowed_names={"local.files.read"},
    )

    assert [tool.name for tool in result.active] == ["local.files.read", "builtin"]
