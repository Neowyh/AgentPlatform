from langchain_core.tools import StructuredTool

from ideer.tools.assembly import ToolSet, assemble_tools


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
