"""Extra coverage tests for lead_agent/prompt.py missed lines.

Targets: 49-51, 70-71, 126-127, 146->149, 170, 206->201, 570-572, 577, 583,
         589-591, 603->609, 649, 654, 661-664, 697-702, 709-714, 720-725, 748-750
"""

import threading
from types import SimpleNamespace
from unittest.mock import patch

from ideer.agents.lead_agent import prompt as prompt_module


def _set_skills_cache_state(*, skills=None, active=False, version=0):
    prompt_module._get_cached_skills_prompt_section.cache_clear()
    with prompt_module._enabled_skills_lock:
        prompt_module._enabled_skills_cache = skills
        prompt_module._enabled_skills_by_config_cache.clear()
        prompt_module._enabled_skills_refresh_active = active
        prompt_module._enabled_skills_refresh_version = version
        prompt_module._enabled_skills_refresh_event.clear()


# --- Lines 49-51: _start_enabled_skills_refresh_thread ---


def test_start_enabled_skills_refresh_thread():
    """Lines 49-51: _start_enabled_skills_refresh_thread starts a daemon thread."""
    started = threading.Event()

    def patched_worker():
        started.set()
        # Don't actually run the full worker to avoid side effects

    with patch.object(prompt_module, "_refresh_enabled_skills_cache_worker", patched_worker):
        prompt_module._start_enabled_skills_refresh_thread()
        assert started.wait(timeout=2)


# --- Lines 70-71: _refresh_enabled_skills_cache_worker exception ---


def test_refresh_worker_handles_exception():
    """Lines 70-71: Worker handles exception from load_skills gracefully."""
    _set_skills_cache_state()
    try:
        with patch.object(prompt_module, "_load_enabled_skills_sync", side_effect=RuntimeError("load failed")):
            # Run the worker directly (not in a thread) for deterministic test
            with prompt_module._enabled_skills_lock:
                prompt_module._enabled_skills_refresh_active = True
                prompt_module._enabled_skills_refresh_version = 0

            prompt_module._refresh_enabled_skills_cache_worker()

        # Worker should have set cache to empty list despite exception
        with prompt_module._enabled_skills_lock:
            assert prompt_module._enabled_skills_cache == []
            assert prompt_module._enabled_skills_refresh_active is False
    finally:
        _set_skills_cache_state()


# --- Lines 126-127: get_cached_enabled_skills cache miss ---


def test_get_cached_enabled_skills_returns_empty_on_miss():
    """Lines 126-127: Returns empty list on cache miss and triggers refresh."""
    _set_skills_cache_state()
    try:
        with patch.object(prompt_module, "_ensure_enabled_skills_cache") as mock_ensure:
            result = prompt_module.get_cached_enabled_skills()
        assert result == []
        mock_ensure.assert_called_once()
    finally:
        _set_skills_cache_state()


# --- Line 170: _build_skill_evolution_section disabled ---


def test_build_skill_evolution_section_disabled():
    """Line 170: Returns empty string when skill evolution is disabled."""
    result = prompt_module._build_skill_evolution_section(False)
    assert result == ""


def test_build_skill_evolution_section_enabled():
    """Returns non-empty string when skill evolution is enabled."""
    result = prompt_module._build_skill_evolution_section(True)
    assert "Skill Self-Evolution" in result


# --- Lines 570-591: _get_memory_context ---


def test_get_memory_context_returns_empty_when_disabled(monkeypatch):
    """Lines 576-577: Returns empty when memory is disabled."""
    config = SimpleNamespace(memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000))
    result = prompt_module._get_memory_context(app_config=config)
    assert result == ""


def test_get_memory_context_returns_empty_when_injection_disabled(monkeypatch):
    """Line 577: Returns empty when injection is disabled."""
    config = SimpleNamespace(memory=SimpleNamespace(enabled=True, injection_enabled=False, max_injection_tokens=2000))
    result = prompt_module._get_memory_context(app_config=config)
    assert result == ""


def test_get_memory_context_returns_empty_when_no_content(monkeypatch):
    """Lines 589-591: Returns empty when memory content is empty."""
    config = SimpleNamespace(memory=SimpleNamespace(enabled=True, injection_enabled=True, max_injection_tokens=2000))

    monkeypatch.setattr("ideer.runtime.user_context.get_effective_user_id", lambda: "u1")
    monkeypatch.setattr("ideer.agents.memory.get_memory_data", lambda *a, **kw: {})
    monkeypatch.setattr("ideer.agents.memory.format_memory_for_injection", lambda *a, **kw: "")

    result = prompt_module._get_memory_context("agent1", app_config=config)
    assert result == ""


def test_get_memory_context_returns_content(monkeypatch):
    """Lines 583-588: Returns memory wrapped in XML tags."""
    config = SimpleNamespace(memory=SimpleNamespace(enabled=True, injection_enabled=True, max_injection_tokens=1000))

    monkeypatch.setattr("ideer.runtime.user_context.get_effective_user_id", lambda: "u1")
    monkeypatch.setattr("ideer.agents.memory.get_memory_data", lambda *a, **kw: {"facts": []})
    monkeypatch.setattr("ideer.agents.memory.format_memory_for_injection", lambda *a, **kw: "User likes Python")

    result = prompt_module._get_memory_context("agent1", app_config=config)
    assert "<memory>" in result
    assert "User likes Python" in result


def test_get_memory_context_handles_exception(monkeypatch):
    """Lines 589-591: Returns empty on exception."""
    config = SimpleNamespace(memory=SimpleNamespace(enabled=True, injection_enabled=True, max_injection_tokens=1000))

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr("ideer.runtime.user_context.get_effective_user_id", boom)

    result = prompt_module._get_memory_context(app_config=config)
    assert result == ""


# --- Lines 649, 654: get_skills_prompt_section edge cases ---


def test_get_skills_prompt_section_returns_empty_when_no_skills_and_no_evolution(monkeypatch):
    """Lines 649: Returns empty when no skills and no evolution."""
    config = SimpleNamespace(
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(prompt_module, "get_enabled_skills_for_config", lambda *a, **kw: [])

    result = prompt_module.get_skills_prompt_section(app_config=config)
    assert result == ""


# --- Lines 661-664: get_agent_soul ---


def test_get_agent_soul_returns_empty_for_none():
    """Lines 661-664: Returns empty for None agent_name."""
    with patch("ideer.agents.lead_agent.prompt.load_agent_soul", return_value=""):
        result = prompt_module.get_agent_soul(None)
    assert result == ""


def test_get_agent_soul_returns_soul_content():
    """Lines 661-664: Returns formatted soul for valid agent."""
    with patch("ideer.agents.lead_agent.prompt.load_agent_soul", return_value="I am helpful"):
        result = prompt_module.get_agent_soul("my-agent")
    assert "<soul>" in result
    assert "I am helpful" in result


def test_get_agent_soul_forwards_user_id_to_owner_directory():
    """A shared agent's SOUL is read from the declaring owner's directory."""
    with patch("ideer.agents.lead_agent.prompt.load_agent_soul") as mock_soul:
        mock_soul.return_value = "owner soul"
        result = prompt_module.get_agent_soul("my-agent", user_id="owner-1")
    mock_soul.assert_called_once_with("my-agent", user_id="owner-1")
    assert "owner soul" in result


def test_apply_prompt_template_shared_agent_uses_owner_soul_and_skips_self_update(monkeypatch):
    """Shared agents load SOUL from the owner and get no self-update section."""
    seen = {}

    def fake_soul(agent_name=None, *, user_id=None):
        seen["user_id"] = user_id
        return "<soul>shared</soul>"

    monkeypatch.setattr(prompt_module, "get_agent_soul", fake_soul)
    monkeypatch.setattr(prompt_module, "get_skills_prompt_section", lambda *a, **kw: "")
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda *a, **kw: "")
    monkeypatch.setattr(prompt_module, "_build_acp_section", lambda *a, **kw: "")
    monkeypatch.setattr(prompt_module, "_build_custom_mounts_section", lambda *a, **kw: "")

    result = prompt_module.apply_prompt_template(agent_name="my-agent", agent_user_id="owner-1")

    assert seen["user_id"] == "owner-1"
    assert "<soul>shared</soul>" in result
    assert "<self_update>" not in result


# --- Lines 697-702: get_deferred_tools_prompt_section ---


def test_get_deferred_tools_prompt_section_returns_empty_when_disabled():
    """Lines 697-702: Returns empty when tool_search is disabled."""
    config = SimpleNamespace(tool_search=SimpleNamespace(enabled=False))
    result = prompt_module.get_deferred_tools_prompt_section(app_config=config)
    assert result == ""


def test_get_deferred_tools_prompt_section_returns_empty_when_no_registry():
    """Lines 709-712: Returns empty when registry is empty."""
    config = SimpleNamespace(tool_search=SimpleNamespace(enabled=True))
    with patch("ideer.tools.builtins.tool_search.get_deferred_registry", return_value=None):
        result = prompt_module.get_deferred_tools_prompt_section(app_config=config)
    assert result == ""


def test_get_deferred_tools_prompt_section_returns_names():
    """Lines 713-714: Returns tool names when registry has entries."""
    config = SimpleNamespace(tool_search=SimpleNamespace(enabled=True))
    entry = SimpleNamespace(name="my_tool")
    with patch("ideer.tools.builtins.tool_search.get_deferred_registry", return_value=SimpleNamespace(entries=[entry])):
        result = prompt_module.get_deferred_tools_prompt_section(app_config=config)
    assert "my_tool" in result


# --- Lines 709-714: _build_acp_section ---


def test_build_acp_section_returns_empty_when_no_agents():
    """Lines 729-730: Returns empty when no ACP agents configured."""
    config = SimpleNamespace(acp_agents={})
    result = prompt_module._build_acp_section(app_config=config)
    assert result == ""


def test_build_acp_section_returns_section_when_agents_configured():
    """Lines 732-738: Returns ACP section when agents are configured."""
    config = SimpleNamespace(acp_agents={"codex": object()})
    result = prompt_module._build_acp_section(app_config=config)
    assert "ACP Agent Tasks" in result


# --- Lines 720-725: _build_custom_mounts_section ---


def test_build_custom_mounts_section_returns_empty_when_no_mounts():
    """Lines 756-757: Returns empty when no mounts configured."""
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=[]))
    result = prompt_module._build_custom_mounts_section(app_config=config)
    assert result == ""


def test_build_custom_mounts_section_returns_empty_when_mounts_none():
    """Returns empty when mounts is None."""
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=None))
    result = prompt_module._build_custom_mounts_section(app_config=config)
    assert result == ""


def test_build_custom_mounts_section_lists_mounts():
    """Lines 760-765: Lists configured mounts."""
    mounts = [
        SimpleNamespace(container_path="/data", read_only=True),
        SimpleNamespace(container_path="/workspace", read_only=False),
    ]
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=mounts))
    result = prompt_module._build_custom_mounts_section(app_config=config)
    assert "/data" in result
    assert "read-only" in result
    assert "/workspace" in result
    assert "read-write" in result


# --- Lines 748-750: _build_custom_mounts_section exception path ---


def test_build_custom_mounts_section_handles_exception():
    """Lines 748-750: Returns empty on exception from get_app_config."""
    with patch("ideer.config.get_app_config", side_effect=RuntimeError("no config")):
        result = prompt_module._build_custom_mounts_section()
    assert result == ""


# --- _skill_mutability_label ---


def test_skill_mutability_label():
    """_skill_mutability_label returns correct labels."""
    from ideer.skills.types import SkillCategory

    assert prompt_module._skill_mutability_label(SkillCategory.CUSTOM) == "[custom, editable]"
    assert prompt_module._skill_mutability_label("other") == "[built-in]"


# --- Lines 70-71: refresh worker version mismatch ---


def test_refresh_worker_loops_on_version_mismatch():
    """Lines 70-71: Worker loops when version changes during loading."""
    _set_skills_cache_state()
    try:
        call_count = 0

        def fake_load():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate version change while loading
                with prompt_module._enabled_skills_lock:
                    prompt_module._enabled_skills_refresh_version += 1
                return ["stale-skill"]
            return ["fresh-skill"]

        with patch.object(prompt_module, "_load_enabled_skills_sync", side_effect=fake_load):
            with prompt_module._enabled_skills_lock:
                prompt_module._enabled_skills_refresh_active = True
                prompt_module._enabled_skills_refresh_version = 0

            prompt_module._refresh_enabled_skills_cache_worker()

        # Should have called load twice (first time version mismatch, second time success)
        assert call_count == 2
        with prompt_module._enabled_skills_lock:
            assert prompt_module._enabled_skills_cache == ["fresh-skill"]
    finally:
        _set_skills_cache_state()


# --- Lines 570-572: _get_memory_context with app_config=None ---


def test_get_memory_context_with_global_config(monkeypatch):
    """Lines 570-572: Uses global config when app_config is None."""
    from ideer.config.memory_config import MemoryConfig

    mem_config = MemoryConfig(enabled=True, injection_enabled=True, max_injection_tokens=500)

    monkeypatch.setattr("ideer.config.memory_config.get_memory_config", lambda: mem_config)
    monkeypatch.setattr("ideer.runtime.user_context.get_effective_user_id", lambda: "u1")
    monkeypatch.setattr("ideer.agents.memory.get_memory_data", lambda *a, **kw: {"facts": []})
    monkeypatch.setattr("ideer.agents.memory.format_memory_for_injection", lambda *a, **kw: "global memory")

    result = prompt_module._get_memory_context("agent1")
    assert "<memory>" in result
    assert "global memory" in result


# --- Lines 649: get_skills_prompt_section with available_skills filter ---


def test_get_skills_prompt_section_returns_empty_when_no_matching_skills(monkeypatch, tmp_path):
    """Line 649: Returns empty when available_skills filter matches no skills."""
    from ideer.skills.types import Skill, SkillCategory

    skill_dir = tmp_path / "skill"
    skill = Skill(
        name="my-skill",
        description="A skill",
        license="MIT",
        skill_dir=skill_dir,
        skill_file=skill_dir / "SKILL.md",
        relative_path=skill_dir.relative_to(tmp_path),
        category=SkillCategory.CUSTOM,
        enabled=True,
    )

    config = SimpleNamespace(
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(prompt_module, "get_enabled_skills_for_config", lambda *a, **kw: [skill])

    # Filter for a skill that doesn't exist
    result = prompt_module.get_skills_prompt_section(available_skills={"nonexistent-skill"}, app_config=config)
    assert result == ""


# --- Line 654: get_skills_prompt_section with empty skill_signature ---


def test_get_skills_prompt_section_returns_empty_when_signature_empty_and_key_not_none(monkeypatch):
    """Line 654: Returns empty when skill_signature is empty but available_key is not None."""
    config = SimpleNamespace(
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(prompt_module, "get_enabled_skills_for_config", lambda *a, **kw: [])

    result = prompt_module.get_skills_prompt_section(available_skills={"some-skill"}, app_config=config)
    assert result == ""


# --- Lines 697-702: get_deferred_tools_prompt_section with global config ---


def test_get_deferred_tools_prompt_section_with_global_config(monkeypatch):
    """Lines 697-702: Uses global config when app_config is None."""
    config = SimpleNamespace(tool_search=SimpleNamespace(enabled=False))

    def fake_get_app_config():
        return config

    monkeypatch.setattr("ideer.config.get_app_config", fake_get_app_config)
    result = prompt_module.get_deferred_tools_prompt_section()
    assert result == ""


# --- Lines 720-725: _build_custom_mounts_section with global config ---


def test_build_custom_mounts_section_with_global_config(monkeypatch):
    """Lines 720-725: Uses global config when app_config is None."""
    config = SimpleNamespace(sandbox=SimpleNamespace(mounts=[SimpleNamespace(container_path="/data", read_only=True)]))

    def fake_get_app_config():
        return config

    monkeypatch.setattr("ideer.config.get_app_config", fake_get_app_config)
    result = prompt_module._build_custom_mounts_section()
    assert "/data" in result
    assert "read-only" in result
