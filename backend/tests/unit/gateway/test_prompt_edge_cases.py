"""Tests targeting uncovered conditional branches in deerflow.agents.lead_agent.prompt.

Each test function is named after the line range it covers.
"""

from types import SimpleNamespace

from deerflow.agents.lead_agent import prompt as prompt_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_skills_cache_state(*, skills=None, active=False, version=0):
    """Reset module-level cache globals to a known state."""
    prompt_module._get_cached_skills_prompt_section.cache_clear()
    with prompt_module._enabled_skills_lock:
        prompt_module._enabled_skills_cache = skills
        prompt_module._enabled_skills_by_config_cache.clear()
        prompt_module._enabled_skills_refresh_active = active
        prompt_module._enabled_skills_refresh_version = version
        prompt_module._enabled_skills_refresh_event.clear()


# ---------------------------------------------------------------------------
# Lines 49-51 – _refresh_enabled_skills_cache_worker exception branch
# ---------------------------------------------------------------------------


class TestRefreshWorkerExceptionBranch:
    """Cover the ``except Exception`` block in _refresh_enabled_skills_cache_worker."""

    def test_worker_catches_load_exception_and_keeps_cache(self, monkeypatch):
        """Upstream: on load failure the worker keeps the cache untouched (stays
        None), clears the refresh flag, and converges on the first iteration."""
        _set_skills_cache_state()

        monkeypatch.setattr(
            prompt_module,
            "_load_enabled_skills_sync",
            lambda: (_ for _ in ()).throw(RuntimeError("simulated I/O failure")),
        )
        # Prevent version bump so the worker converges on the first iteration.
        monkeypatch.setattr(
            prompt_module,
            "_enabled_skills_refresh_version",
            0,
        )

        prompt_module._refresh_enabled_skills_cache_worker()

        with prompt_module._enabled_skills_lock:
            assert prompt_module._enabled_skills_cache is None
            assert prompt_module._enabled_skills_refresh_active is False

    def test_worker_populates_cache_on_success(self, monkeypatch):
        """Normal (non-exception) path: cache receives the loaded skills."""
        _set_skills_cache_state()

        sentinel = [SimpleNamespace(name="skill-a")]
        monkeypatch.setattr(
            prompt_module,
            "_load_enabled_skills_sync",
            lambda: list(sentinel),
        )

        prompt_module._refresh_enabled_skills_cache_worker()

        with prompt_module._enabled_skills_lock:
            assert [s.name for s in prompt_module._enabled_skills_cache] == ["skill-a"]


# ---------------------------------------------------------------------------
# Lines 70-71 – _ensure_enabled_skills_cache early-return when cache exists
# ---------------------------------------------------------------------------


class TestEnsureCacheEarlyReturn:
    """Cover the branch where the cache is already populated."""

    def test_returns_immediately_when_cache_populated(self):
        """If _enabled_skills_cache is not None, the event is set immediately."""
        fake_skills = [SimpleNamespace(name="cached")]
        _set_skills_cache_state(skills=fake_skills)

        event = prompt_module._ensure_enabled_skills_cache()

        # The event should be set (the cache was already warm).
        assert event.is_set()
        # No new worker thread should have been started.
        with prompt_module._enabled_skills_lock:
            assert prompt_module._enabled_skills_refresh_active is False


# ---------------------------------------------------------------------------
# Lines 126-127 – get_cached_enabled_skills cache-miss path
# ---------------------------------------------------------------------------


class TestGetCachedEnabledSkillsMiss:
    """Cover the branch where the cache is None and a background refresh is triggered."""

    def test_returns_empty_list_and_primes_cache(self):
        """On cache miss, returns [] and kicks off a refresh thread."""
        _set_skills_cache_state()

        result = prompt_module.get_cached_enabled_skills()

        assert result == []
        # After the call the background worker should be active.
        # We just verify the function returned an empty list without blocking.


# ---------------------------------------------------------------------------
# Lines 570-572 – _get_memory_context global config fallback
# ---------------------------------------------------------------------------


class TestGetMemoryContextGlobalConfig:
    """Cover the branch where app_config is None and the global memory config is used."""

    def test_uses_global_memory_config_when_app_config_is_none(self, monkeypatch):
        """Upstream loads memory via the pluggable MemoryManager when no explicit config is given."""
        mem_config = SimpleNamespace(
            enabled=True,
            injection_enabled=True,
            max_injection_tokens=4096,
        )
        manager = SimpleNamespace(get_context=lambda *, user_id, agent_name: "global-memory-text")
        monkeypatch.setattr(
            "deerflow.config.memory_config.get_memory_config",
            lambda: mem_config,
        )
        monkeypatch.setattr(
            "deerflow.agents.memory.get_memory_manager",
            lambda: manager,
        )

        ctx = prompt_module._get_memory_context(agent_name="test-agent", app_config=None, user_id="u-1")

        assert "<memory>" in ctx
        assert "global-memory-text" in ctx

    def test_returns_empty_when_memory_disabled_globally(self, monkeypatch):
        mem_config = SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=100)
        monkeypatch.setattr(
            "deerflow.config.memory_config.get_memory_config",
            lambda: mem_config,
        )

        ctx = prompt_module._get_memory_context(agent_name=None, app_config=None)
        assert ctx == ""


# ---------------------------------------------------------------------------
# Line 654 – get_skills_prompt_section empty signature with available_key
# ---------------------------------------------------------------------------


class TestGetSkillsPromptSectionEmptySignature:
    """Cover the branch where skill_signature is empty but available_key is not None."""

    def _patch_world(self, monkeypatch, skills):
        monkeypatch.setattr(
            prompt_module,
            "get_enabled_skills_for_config",
            lambda app_config=None, user_id=None: list(skills),
        )
        monkeypatch.setattr(
            prompt_module,
            "get_or_new_skill_storage",
            lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only: list(skills)),
        )
        monkeypatch.setattr(
            "deerflow.config.get_app_config",
            lambda: SimpleNamespace(
                skills=SimpleNamespace(container_path="/mnt/skills"),
                skill_evolution=SimpleNamespace(enabled=False),
            ),
        )
        prompt_module._get_cached_skills_prompt_section.cache_clear()

    def test_returns_empty_when_no_skills_match_available_key(self, monkeypatch):
        """When there are no skills but available_skills is a non-empty set, return ''."""
        self._patch_world(monkeypatch, [])

        result = prompt_module.get_skills_prompt_section(
            available_skills={"nonexistent-skill"},
        )
        assert result == ""

    def test_returns_empty_when_skills_exist_but_none_in_available_set(self, monkeypatch):
        """Skills are loaded but none match the available_skills filter -> empty signature."""
        skill = SimpleNamespace(
            name="real-skill",
            description="desc",
            category="builtin",
            enabled=True,
            get_container_file_path=lambda base: f"{base}/real-skill/SKILL.md",
        )
        self._patch_world(monkeypatch, [skill])

        # available_skills does NOT contain "real-skill"
        result = prompt_module.get_skills_prompt_section(
            available_skills={"other-skill"},
        )
        assert result == ""


# ---------------------------------------------------------------------------
# get_deferred_tools_prompt_section — empty deferred set
# ---------------------------------------------------------------------------


class TestGetDeferredToolsPromptSectionException:
    """Upstream renders from an explicit deferred-name set with no config I/O,
    so there is no config-load failure branch to cover; empty set -> empty."""

    def test_returns_empty_string_on_empty_deferred_names(self):
        result = prompt_module.get_deferred_tools_prompt_section(deferred_names=frozenset())
        assert result == ""


# ---------------------------------------------------------------------------
# Lines 724-725 – _build_acp_section exception branch
# ---------------------------------------------------------------------------


class TestBuildAcpSectionException:
    """Cover the except block when get_acp_agents() raises."""

    def test_returns_empty_string_on_acp_agents_load_failure(self, monkeypatch):
        def raise_acp():
            raise RuntimeError("acp agents unavailable")

        monkeypatch.setattr("deerflow.config.acp_config.get_acp_agents", raise_acp)

        result = prompt_module._build_acp_section(app_config=None)
        assert result == ""


# ---------------------------------------------------------------------------
# Lines 748-750 – _build_custom_mounts_section exception branch
# ---------------------------------------------------------------------------


class TestBuildCustomMountsSectionException:
    """Cover the except block when get_app_config() raises."""

    def test_returns_empty_string_and_logs_on_config_failure(self, monkeypatch, caplog):
        def raise_config():
            raise RuntimeError("config broken")

        monkeypatch.setattr("deerflow.config.get_app_config", raise_config)

        with caplog.at_level("ERROR"):
            result = prompt_module._build_custom_mounts_section(app_config=None)

        assert result == ""
        assert "Failed to load configured sandbox mounts" in caplog.text
