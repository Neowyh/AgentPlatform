"""Tests for lead_agent._resolve_requested_skills."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_skill(name: str, *, enabled: bool = True) -> MagicMock:
    skill = MagicMock()
    skill.name = name
    skill.enabled = enabled
    return skill


class TestResolveRequestedSkills:
    def test_returns_all_when_no_skill_name(self):
        from ideer.agents.lead_agent.agent import _resolve_requested_skills

        skills = [_make_skill("research"), _make_skill("web-search")]
        result = _resolve_requested_skills(skills, None)
        assert len(result) == 2

    def test_filters_to_single_skill(self):
        from ideer.agents.lead_agent.agent import _resolve_requested_skills

        skills = [_make_skill("research"), _make_skill("web-search")]
        result = _resolve_requested_skills(skills, "research")
        assert len(result) == 1
        assert result[0].name == "research"

    def test_returns_empty_when_skill_not_found(self):
        from ideer.agents.lead_agent.agent import _resolve_requested_skills

        skills = [_make_skill("research"), _make_skill("web-search")]
        result = _resolve_requested_skills(skills, "nonexistent")
        assert result == []

    def test_returns_empty_list_when_skills_empty(self):
        from ideer.agents.lead_agent.agent import _resolve_requested_skills

        result = _resolve_requested_skills([], "research")
        assert result == []
