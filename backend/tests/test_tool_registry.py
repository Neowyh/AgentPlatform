"""Tests for ToolRegistry — registration, search, config update, and edge cases."""

from __future__ import annotations

from packages.harness.ideer.tools.registry import ToolInfo, ToolRegistry


class TestToolRegistry:
    """Tests for the ToolRegistry class."""

    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = ToolInfo(name="search", description="Search the web", group="core")
        reg.register(tool)
        assert reg.get("search") is tool

    def test_get_nonexistent_returns_none(self):
        reg = ToolRegistry()
        assert reg.get("missing") is None

    def test_register_overwrites_existing(self):
        reg = ToolRegistry()
        t1 = ToolInfo(name="tool1", description="v1", group="core")
        t2 = ToolInfo(name="tool1", description="v2", group="core")
        reg.register(t1)
        reg.register(t2)
        assert reg.get("tool1").description == "v2"

    def test_list_all(self):
        reg = ToolRegistry()
        reg.register(ToolInfo(name="a", description="A", group="core"))
        reg.register(ToolInfo(name="b", description="B", group="community"))
        all_tools = reg.list_all()
        assert len(all_tools) == 2
        assert {t.name for t in all_tools} == {"a", "b"}

    def test_list_by_group(self):
        reg = ToolRegistry()
        reg.register(ToolInfo(name="a", description="A", group="core"))
        reg.register(ToolInfo(name="b", description="B", group="community"))
        reg.register(ToolInfo(name="c", description="C", group="core"))
        core = reg.list_by_group("core")
        assert len(core) == 2
        assert {t.name for t in core} == {"a", "c"}

    def test_list_by_group_empty(self):
        reg = ToolRegistry()
        assert reg.list_by_group("nonexistent") == []

    def test_search_by_name(self):
        reg = ToolRegistry()
        reg.register(ToolInfo(name="read_document", description="Read docs", group="community"))
        reg.register(ToolInfo(name="code_interpreter", description="Run code", group="community"))
        results = reg.search("document")
        assert len(results) == 1
        assert results[0].name == "read_document"

    def test_search_by_description(self):
        reg = ToolRegistry()
        reg.register(ToolInfo(name="tool1", description="Analyze CSV files", group="community"))
        results = reg.search("csv")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        reg = ToolRegistry()
        reg.register(ToolInfo(name="MyTool", description="Desc", group="core"))
        assert len(reg.search("mytool")) == 1
        assert len(reg.search("MYTOOL")) == 1

    def test_search_no_match(self):
        reg = ToolRegistry()
        reg.register(ToolInfo(name="tool1", description="Desc", group="core"))
        assert reg.search("nonexistent") == []


class TestToolRegistryUpdateConfig:
    """Tests for ToolRegistry.update_config()."""

    def test_update_config_success(self):
        reg = ToolRegistry()
        tool = ToolInfo(
            name="t1",
            description="desc",
            group="core",
            configurable=True,
            config_schema={"properties": {"api_key": {"type": "string"}, "timeout": {"type": "integer"}}},
        )
        reg.register(tool)
        result = reg.update_config("t1", {"api_key": "abc123"})
        assert result is True
        assert tool.config["api_key"] == "abc123"

    def test_update_config_nonexistent_tool(self):
        reg = ToolRegistry()
        assert reg.update_config("missing", {"key": "val"}) is False

    def test_update_config_not_configurable(self):
        reg = ToolRegistry()
        tool = ToolInfo(name="t1", description="desc", group="core", configurable=False)
        reg.register(tool)
        assert reg.update_config("t1", {"key": "val"}) is False

    def test_update_config_unexpected_key_rejected(self):
        reg = ToolRegistry()
        tool = ToolInfo(
            name="t1",
            description="desc",
            group="core",
            configurable=True,
            config_schema={"properties": {"allowed_key": {"type": "string"}}},
        )
        reg.register(tool)
        result = reg.update_config("t1", {"bogus_key": "val"})
        assert result is False

    def test_update_config_no_schema_allows_any_key(self):
        reg = ToolRegistry()
        tool = ToolInfo(name="t1", description="desc", group="core", configurable=True, config_schema={})
        reg.register(tool)
        result = reg.update_config("t1", {"any_key": "val"})
        assert result is True


class TestToolInfo:
    """Tests for ToolInfo dataclass defaults."""

    def test_defaults(self):
        t = ToolInfo(name="t", description="d", group="g")
        assert t.requires_network is False
        assert t.configurable is False
        assert t.config_schema == {}
        assert t.param_schema == {}
        assert t.config == {}
