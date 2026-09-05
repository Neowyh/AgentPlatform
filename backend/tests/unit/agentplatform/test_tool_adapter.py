from __future__ import annotations

from app.agentplatform import tool_adapter


def test_tool_adapter_delegates_to_deerflow_factory(monkeypatch) -> None:
    sentinel = [object()]
    calls = {}

    def fake_factory(**kwargs):
        calls.update(kwargs)
        return sentinel

    monkeypatch.setattr(tool_adapter, "_get_available_tools", fake_factory)

    assert tool_adapter.get_available_tools(groups=["sandbox"], include_mcp=False) is sentinel
    assert calls == {"groups": ["sandbox"], "include_mcp": False}
