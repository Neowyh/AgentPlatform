"""Canonical Agent assembly adapter tests.

The adapter is the single Gateway-facing seam that binds one frozen canonical
resource closure into the DeerFlow lead assembly.  It must hand the frozen
inputs (identity, config, soul, skills, caller tool groups, resource
governance identity) to ``assemble_lead_agent`` and return a factory whose
graphs come from the DeerFlow assembly — the legacy harness factory is not
involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from agentplatform_extension.knowledge.scope import KnowledgeScope
from langchain_core.tools import BaseTool

from app.agentplatform.runtime_adapter import build_canonical_agent_factory


@dataclass(frozen=True)
class _Definition:
    resource_id: str
    version: int
    content_hash: str
    path: Path
    config: object
    soul: str


def test_canonical_factory_builds_through_deerflow_assembly(monkeypatch) -> None:
    captured: dict = {}

    def fake_assemble(config, *, app_config=None, frozen=None):
        captured.update(
            config=config,
            app_config=app_config,
            frozen=frozen,
        )
        return SimpleNamespace(graph="graph")

    monkeypatch.setattr(
        "app.agentplatform.runtime_adapter.assemble_lead_agent",
        fake_assemble,
    )

    definition = _Definition(
        resource_id="0f7d8709-0000-0000-0000-000000000001",
        version=3,
        content_hash="abc123",
        path=Path("/tmp/agent"),
        config=object(),
        soul="frozen soul",
    )
    skills = [object()]
    groups = frozenset({"files"})

    factory = build_canonical_agent_factory(
        definition,
        skills,
        runner_tool_groups=groups,
    )
    result = factory({"configurable": {}})

    assert result == "graph"
    frozen = captured["frozen"]
    assert frozen.agent_name == "0f7d8709-0000-0000-0000-000000000001"
    assert frozen.config is definition.config
    assert frozen.soul == "frozen soul"
    assert frozen.skills == skills
    assert frozen.runner_tool_groups == groups
    assert frozen.resource == {
        "resource_id": definition.resource_id,
        "version": 3,
        "content_hash": "abc123",
    }


def test_canonical_factory_binds_one_immutable_closure(monkeypatch) -> None:
    """Each factory call assembles from the same frozen closure object."""
    seen: list = []

    def fake_assemble(config, *, app_config=None, frozen=None):
        seen.append(frozen)
        return SimpleNamespace(graph=f"graph-{len(seen)}")

    monkeypatch.setattr(
        "app.agentplatform.runtime_adapter.assemble_lead_agent",
        fake_assemble,
    )

    definition = _Definition(
        resource_id="agent-1",
        version=1,
        content_hash="h",
        path=Path("/tmp/agent"),
        config=object(),
        soul="soul",
    )
    factory = build_canonical_agent_factory(definition, [], runner_tool_groups=None)

    first = factory({"configurable": {}})
    second = factory({"configurable": {}})

    assert first == "graph-1"
    assert second == "graph-2"
    assert seen[0] is seen[1]


def test_canonical_factory_scopes_tools_at_the_upstream_import_seam(monkeypatch) -> None:
    import deerflow.tools as deerflow_tools

    observed: list[list[object]] = []

    def available_tools(*args, **kwargs):
        tool = type("KnowledgeTool", (), {"name": "knowledge_search"})()
        return [tool]

    monkeypatch.setattr(deerflow_tools, "get_available_tools", available_tools)

    def fake_assemble(config, *, app_config=None, frozen=None):
        observed.append(deerflow_tools.get_available_tools())
        return SimpleNamespace(graph="graph")

    monkeypatch.setattr("app.agentplatform.runtime_adapter.assemble_lead_agent", fake_assemble)
    definition = _Definition("agent", 1, "hash", Path("/tmp/agent"), object(), "soul")

    factory = build_canonical_agent_factory(
        definition,
        [],
        runner_tool_groups=None,
        knowledge_scope=KnowledgeScope.from_bindings({"docs": "dataset"}),
    )
    factory({"configurable": {}})

    assert observed and observed[0][0].name == "knowledge_search"
    assert isinstance(observed[0][0], BaseTool)


def test_canonical_factory_does_not_expose_provider_dataset_ids_to_model(monkeypatch) -> None:
    captured: dict = {}

    def fake_assemble(config, *, app_config=None, frozen=None):
        captured["frozen"] = frozen
        return SimpleNamespace(graph="graph")

    monkeypatch.setattr("app.agentplatform.runtime_adapter.assemble_lead_agent", fake_assemble)
    definition = _Definition("agent", 1, "hash", Path("/tmp/agent"), object(), "soul")

    factory = build_canonical_agent_factory(
        definition,
        [],
        runner_tool_groups=None,
        knowledge_scope=KnowledgeScope.from_bindings({"docs": "opaque-dataset"}),
    )
    factory({"configurable": {}})

    resource = captured["frozen"].resource
    assert resource["knowledge_scope"] == {"logical_selectors": ["docs"]}
    assert "opaque-dataset" not in repr(resource)
