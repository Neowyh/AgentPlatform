"""Tests for tool_policy — skill-based tool filtering logic.

Covers:
- allowed_tool_names_for_skills: union computation, None/legacy behavior, edge cases
- filter_tools_by_skill_allowed_tools: end-to-end filtering with mock tools
- Security edge cases and adversarial boundary tests
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from ideer.skills.tool_policy import (
    allowed_tool_names_for_skills,
    filter_tools_by_skill_allowed_tools,
)
from ideer.skills.types import Skill, SkillCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_SKILL_DIR = Path("/tmp/skills/test-skill")
_MINIMAL_SKILL_FILE = _MINIMAL_SKILL_DIR / "SKILL.md"


def _make_skill(name: str = "test-skill", allowed_tools: list[str] | None = None) -> Skill:
    return Skill(
        name=name,
        description="A test skill",
        license=None,
        skill_dir=_MINIMAL_SKILL_DIR,
        skill_file=_MINIMAL_SKILL_FILE,
        relative_path=Path("."),
        category=SkillCategory.PUBLIC,
        allowed_tools=allowed_tools,
    )


def _make_tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


# ---------------------------------------------------------------------------
# allowed_tool_names_for_skills
# ---------------------------------------------------------------------------


class TestAllowedToolNamesForSkills:
    """Unit tests for the allowed_tool_names_for_skills function."""

    def test_empty_skills_returns_none(self):
        """Empty skill list → None (legacy allow-all)."""
        assert allowed_tool_names_for_skills([]) is None

    def test_no_explicit_declarations_returns_none(self):
        """All skills have allowed_tools=None → None (legacy allow-all)."""
        skills = [
            _make_skill("s1", allowed_tools=None),
            _make_skill("s2", allowed_tools=None),
        ]
        assert allowed_tool_names_for_skills(skills) is None

    def test_single_skill_explicit_declaration(self):
        """One skill declares allowed_tools → that set is returned."""
        skills = [_make_skill("s1", allowed_tools=["read", "search"])]
        result = allowed_tool_names_for_skills(skills)
        assert result == {"read", "search"}

    def test_union_of_multiple_skills(self):
        """Multiple skills with allowed_tools → union."""
        skills = [
            _make_skill("s1", allowed_tools=["read", "search"]),
            _make_skill("s2", allowed_tools=["search", "write"]),
        ]
        result = allowed_tool_names_for_skills(skills)
        assert result == {"read", "search", "write"}

    def test_mixed_explicit_and_none_skills(self):
        """Skills with allowed_tools=None do not dilute explicit declarations."""
        skills = [
            _make_skill("s1", allowed_tools=None),
            _make_skill("s2", allowed_tools=["bash"]),
            _make_skill("s3", allowed_tools=None),
        ]
        result = allowed_tool_names_for_skills(skills)
        assert result == {"bash"}

    def test_empty_allowed_tools_list(self):
        """A skill with allowed_tools=[] contributes nothing but triggers declaration."""
        skills = [
            _make_skill("s1", allowed_tools=[]),
            _make_skill("s2", allowed_tools=None),
        ]
        # s1 declares (even though empty), so has_explicit_declaration=True
        # s2 has None so contributes nothing
        result = allowed_tool_names_for_skills(skills)
        assert result == set()

    def test_empty_allowed_tools_blocks_none_skill(self):
        """When any skill declares allowed_tools (even empty), legacy allow-all is disabled."""
        skills = [
            _make_skill("s1", allowed_tools=None),
            _make_skill("s2", allowed_tools=[]),
        ]
        result = allowed_tool_names_for_skills(skills)
        # s2 declares, so has_explicit_declaration=True
        # Neither skill contributes tools → empty set
        assert result == set()

    def test_duplicate_tool_names_deduplicated(self):
        """Union deduplicates tool names across skills."""
        skills = [
            _make_skill("s1", allowed_tools=["bash", "bash", "read"]),
            _make_skill("s2", allowed_tools=["bash"]),
        ]
        result = allowed_tool_names_for_skills(skills)
        assert result == {"bash", "read"}

    def test_single_empty_declaration_blocks_all(self):
        """A single skill with empty allowed_tools yields empty set."""
        skills = [_make_skill("s1", allowed_tools=[])]
        result = allowed_tool_names_for_skills(skills)
        assert result == set()

    def test_logging_on_empty_allowed_tools(self, caplog):
        """A skill with allowed_tools=[] emits an INFO log."""
        skills = [_make_skill("s1", allowed_tools=[])]
        with caplog.at_level(logging.INFO, logger="ideer.skills.tool_policy"):
            allowed_tool_names_for_skills(skills)
        assert "declared empty allowed-tools" in caplog.text

    def test_allowed_tools_with_empty_string(self):
        """A skill with allowed_tools=[""] triggers declaration but only matches empty-name tools."""
        skills = [_make_skill("s1", allowed_tools=[""])]
        result = allowed_tool_names_for_skills(skills)
        assert result is not None
        assert result == {""}

    def test_allowed_tools_case_sensitive(self):
        """Tool name matching is case-sensitive: 'Read' != 'read'."""
        skills = [_make_skill("s1", allowed_tools=["Read"])]
        result = allowed_tool_names_for_skills(skills)
        assert result == {"Read"}
        # "read" (lowercase) should NOT be in the set
        assert "read" not in result


# ---------------------------------------------------------------------------
# filter_tools_by_skill_allowed_tools
# ---------------------------------------------------------------------------


class TestFilterToolsBySkillAllowedTools:
    """End-to-end tests for filter_tools_by_skill_allowed_tools."""

    def test_no_skills_returns_all_tools(self):
        """Empty skill list → all tools pass through."""
        tools = [_make_tool("a"), _make_tool("b")]
        result = filter_tools_by_skill_allowed_tools(tools, [])
        assert [t.name for t in result] == ["a", "b"]

    def test_no_explicit_declarations_returns_all_tools(self):
        """Skills with allowed_tools=None → all tools pass through."""
        tools = [_make_tool("a"), _make_tool("b")]
        skills = [_make_skill("s1", allowed_tools=None)]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert [t.name for t in result] == ["a", "b"]

    def test_filters_to_allowed_tools(self):
        """Only tools in the allowed set pass through."""
        tools = [_make_tool("read"), _make_tool("write"), _make_tool("bash")]
        skills = [_make_skill("s1", allowed_tools=["read", "bash"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert [t.name for t in result] == ["read", "bash"]

    def test_no_tools_match_allowed(self):
        """If no tool name is in the allowed set, result is empty."""
        tools = [_make_tool("x"), _make_tool("y")]
        skills = [_make_skill("s1", allowed_tools=["z"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert result == []

    def test_empty_tools_list(self):
        """Empty tool list always returns empty, regardless of policy."""
        skills = [_make_skill("s1", allowed_tools=["read"])]
        result = filter_tools_by_skill_allowed_tools([], skills)
        assert result == []

    def test_empty_allowed_tools_blocks_everything(self):
        """A skill with allowed_tools=[] → nothing passes through."""
        tools = [_make_tool("a"), _make_tool("b")]
        skills = [_make_skill("s1", allowed_tools=[])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert result == []

    def test_tool_not_in_any_skill_declared_list(self):
        """Tools not mentioned in any skill's allowed_tools are excluded."""
        tools = [_make_tool("secret_tool"), _make_tool("read")]
        skills = [_make_skill("s1", allowed_tools=["read"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert len(result) == 1
        assert result[0].name == "read"

    def test_multiple_skills_union_filter(self):
        """Union of allowed tools from multiple skills determines the filter."""
        tools = [_make_tool("a"), _make_tool("b"), _make_tool("c"), _make_tool("d")]
        skills = [
            _make_skill("s1", allowed_tools=["a", "b"]),
            _make_skill("s2", allowed_tools=["c"]),
        ]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert [t.name for t in result] == ["a", "b", "c"]

    def test_preserves_tool_object_identity(self):
        """Returned tools are the same objects as the input."""
        tools = [_make_tool("read"), _make_tool("write")]
        skills = [_make_skill("s1", allowed_tools=["read"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert result[0] is tools[0]

    def test_filter_respects_any_named_tool_protocol(self):
        """Works with any object that has a .name attribute (NamedTool protocol)."""
        tools = [SimpleNamespace(name="x"), SimpleNamespace(name="y")]
        skills = [_make_skill("s1", allowed_tools=["x"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert len(result) == 1
        assert result[0].name == "x"

    def test_empty_both_returns_empty(self):
        """Empty tools + empty skills → empty list."""
        result = filter_tools_by_skill_allowed_tools([], [])
        assert result == []

    def test_duplicate_tool_names_preserved(self):
        """Tools with duplicate names both pass the filter (no dedup on tools)."""
        tools = [_make_tool("read"), _make_tool("read")]
        skills = [_make_skill("s1", allowed_tools=["read"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert len(result) == 2
        assert all(t.name == "read" for t in result)

    def test_case_sensitive_filtering(self):
        """Filter matching is case-sensitive: 'Read' in allowed doesn't match 'read' tool."""
        tools = [_make_tool("read"), _make_tool("Read")]
        skills = [_make_skill("s1", allowed_tools=["Read"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert len(result) == 1
        assert result[0].name == "Read"

    def test_empty_string_tool_name_matches_only_empty(self):
        """A tool with empty name only matches allowed_tools=[""]."""
        tools = [_make_tool(""), _make_tool("read")]
        skills = [_make_skill("s1", allowed_tools=[""])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert len(result) == 1
        assert result[0].name == ""


# ---------------------------------------------------------------------------
# Security edge cases
# ---------------------------------------------------------------------------


class TestToolPolicySecurity:
    """Security-focused tests for tool policy logic."""

    def test_empty_allowed_list_is_not_treated_as_allow_all(self):
        """An empty allowed_tools=[] means zero tools, not legacy allow-all."""
        skills = [_make_skill("s1", allowed_tools=[])]
        result = allowed_tool_names_for_skills(skills)
        assert result is not None  # Must NOT be None (which means allow-all)
        assert result == set()

    def test_none_skill_does_not_re_enable_allow_all_after_explicit(self):
        """Once one skill declares, a later skill with None cannot restore legacy."""
        skills = [
            _make_skill("s1", allowed_tools=["read"]),
            _make_skill("s2", allowed_tools=None),
        ]
        result = allowed_tool_names_for_skills(skills)
        # Only "read" is allowed; s2 does not re-enable all tools
        assert result == {"read"}

    def test_single_restriction_applies(self):
        """Even a single skill restricting tools is enforced."""
        tools = [_make_tool("read"), _make_tool("bash"), _make_tool("rm")]
        skills = [_make_skill("s1", allowed_tools=["read"])]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert [t.name for t in result] == ["read"]

    def test_unrestricted_tools_not_leaked(self):
        """Tools not in any allow-list are never included."""
        sensitive_tools = ["rm", "sudo", "drop_table"]
        all_tools = [_make_tool(n) for n in ["read"] + sensitive_tools]
        skills = [_make_skill("s1", allowed_tools=["read"])]
        result = filter_tools_by_skill_allowed_tools(all_tools, skills)
        assert len(result) == 1
        assert result[0].name == "read"
        assert {t.name for t in result}.isdisjoint(set(sensitive_tools))

    def test_only_relevant_skill_contributes(self):
        """Skills with allowed_tools=None don't add tools that bypass restrictions."""
        tools = [_make_tool("a"), _make_tool("b"), _make_tool("c")]
        skills = [
            _make_skill("s1", allowed_tools=None),
            _make_skill("s2", allowed_tools=["a"]),
        ]
        result = filter_tools_by_skill_allowed_tools(tools, skills)
        assert [t.name for t in result] == ["a"]
        # s1 should NOT cause all tools to pass through
        assert len(result) != len(tools)
