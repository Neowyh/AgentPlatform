"""Tests for app.channels.commands module.

Covers:
- KNOWN_CHANNEL_COMMANDS constant type and membership
- Immutability of the frozenset
- Presence / absence of every expected command
- All elements are strings starting with '/'
- Module-level import behaviour
"""

from __future__ import annotations

import pytest

from app.channels.commands import KNOWN_CHANNEL_COMMANDS

# ---------------------------------------------------------------------------
# Expected canonical set
# ---------------------------------------------------------------------------

EXPECTED_COMMANDS: frozenset[str] = frozenset(
    {
        "/bootstrap",
        "/new",
        "/status",
        "/models",
        "/memory",
        "/help",
    }
)


# ---------------------------------------------------------------------------
# Type & structure
# ---------------------------------------------------------------------------


class TestTypeAndStructure:
    """Verify the fundamental type and structure of the constant."""

    def test_is_frozenset(self):
        assert isinstance(KNOWN_CHANNEL_COMMANDS, frozenset)

    def test_contains_exactly_six_commands(self):
        assert len(KNOWN_CHANNEL_COMMANDS) == 6

    def test_all_elements_are_strings(self):
        for cmd in KNOWN_CHANNEL_COMMANDS:
            assert isinstance(cmd, str), f"{cmd!r} is not a str"

    def test_all_elements_start_with_slash(self):
        for cmd in KNOWN_CHANNEL_COMMANDS:
            assert cmd.startswith("/"), f"{cmd!r} does not start with '/'"

    def test_all_elements_are_lowercase(self):
        for cmd in KNOWN_CHANNEL_COMMANDS:
            assert cmd == cmd.lower(), f"{cmd!r} is not lowercase"

    def test_no_empty_strings(self):
        assert "" not in KNOWN_CHANNEL_COMMANDS

    def test_no_whitespace_only_strings(self):
        for cmd in KNOWN_CHANNEL_COMMANDS:
            assert cmd.strip() == cmd, f"{cmd!r} contains leading/trailing whitespace"


# ---------------------------------------------------------------------------
# Exact membership
# ---------------------------------------------------------------------------


class TestExactMembership:
    """Ensure the set matches the expected canonical commands exactly."""

    def test_matches_expected_set(self):
        assert KNOWN_CHANNEL_COMMANDS == EXPECTED_COMMANDS

    def test_contains_bootstrap(self):
        assert "/bootstrap" in KNOWN_CHANNEL_COMMANDS

    def test_contains_new(self):
        assert "/new" in KNOWN_CHANNEL_COMMANDS

    def test_contains_status(self):
        assert "/status" in KNOWN_CHANNEL_COMMANDS

    def test_contains_models(self):
        assert "/models" in KNOWN_CHANNEL_COMMANDS

    def test_contains_memory(self):
        assert "/memory" in KNOWN_CHANNEL_COMMANDS

    def test_contains_help(self):
        assert "/help" in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_quit(self):
        assert "/quit" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_exit(self):
        assert "/exit" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_clear(self):
        assert "/clear" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_stop(self):
        assert "/stop" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_empty_command(self):
        assert "/" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_command_without_slash(self):
        assert "help" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_uppercase_variant(self):
        assert "/HELP" not in KNOWN_CHANNEL_COMMANDS

    def test_does_not_contain_mixed_case_variant(self):
        assert "/Help" not in KNOWN_CHANNEL_COMMANDS


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    """Verify that the frozenset cannot be mutated."""

    def test_cannot_add_element(self):
        with pytest.raises(AttributeError):
            KNOWN_CHANNEL_COMMANDS.add("/new_command")  # type: ignore[attr-defined]

    def test_cannot_remove_element(self):
        with pytest.raises(AttributeError):
            KNOWN_CHANNEL_COMMANDS.remove("/help")  # type: ignore[attr-defined]

    def test_cannot_discard_element(self):
        with pytest.raises(AttributeError):
            KNOWN_CHANNEL_COMMANDS.discard("/help")  # type: ignore[attr-defined]

    def test_cannot_update(self):
        with pytest.raises(AttributeError):
            KNOWN_CHANNEL_COMMANDS.update({"/extra"})  # type: ignore[attr-defined]

    def test_cannot_clear(self):
        with pytest.raises(AttributeError):
            KNOWN_CHANNEL_COMMANDS.clear()  # type: ignore[attr-defined]

    def test_subtract_returns_new_set(self):
        result = KNOWN_CHANNEL_COMMANDS - {"/help"}
        assert "/help" not in result
        # Original is unchanged
        assert "/help" in KNOWN_CHANNEL_COMMANDS

    def test_union_returns_new_set(self):
        result = KNOWN_CHANNEL_COMMANDS | {"/extra"}
        assert "/extra" in result
        # Original is unchanged
        assert "/extra" not in KNOWN_CHANNEL_COMMANDS

    def test_intersection_returns_new_set(self):
        result = KNOWN_CHANNEL_COMMANDS & {"/help", "/new"}
        assert result == {"/help", "/new"}
        assert len(KNOWN_CHANNEL_COMMANDS) == 6

    def test_symmetric_difference_returns_new_set(self):
        result = KNOWN_CHANNEL_COMMANDS ^ {"/help", "/extra"}
        assert "/help" not in result
        assert "/extra" in result
        assert len(KNOWN_CHANNEL_COMMANDS) == 6


# ---------------------------------------------------------------------------
# Set operations (read-only)
# ---------------------------------------------------------------------------


class TestSetOperations:
    """Verify read-only set operations work correctly."""

    def test_issubset_of_larger_set(self):
        larger = EXPECTED_COMMANDS | {"/extra"}
        assert KNOWN_CHANNEL_COMMANDS.issubset(larger)

    def test_issuperset_of_smaller_set(self):
        smaller = frozenset({"/help", "/new"})
        assert KNOWN_CHANNEL_COMMANDS.issuperset(smaller)

    def test_is_disjoint_with_unrelated_set(self):
        unrelated = frozenset({"/quit", "/exit"})
        assert KNOWN_CHANNEL_COMMANDS.isdisjoint(unrelated)

    def test_copy_returns_equal_set(self):
        copy = KNOWN_CHANNEL_COMMANDS.copy()
        assert copy == KNOWN_CHANNEL_COMMANDS
        # frozenset is immutable, .copy() may return the same object
        assert copy is KNOWN_CHANNEL_COMMANDS

    def test_iteration_yields_all_elements(self):
        collected = set()
        for cmd in KNOWN_CHANNEL_COMMANDS:
            collected.add(cmd)
        assert collected == EXPECTED_COMMANDS

    def test_len_matches_iteration(self):
        count = sum(1 for _ in KNOWN_CHANNEL_COMMANDS)
        assert count == len(KNOWN_CHANNEL_COMMANDS)

    def test_hash_is_stable(self):
        h1 = hash(KNOWN_CHANNEL_COMMANDS)
        h2 = hash(KNOWN_CHANNEL_COMMANDS)
        assert h1 == h2

    def test_repr_contains_frozenset(self):
        r = repr(KNOWN_CHANNEL_COMMANDS)
        assert "frozenset" in r

    def test_str_representation(self):
        s = str(KNOWN_CHANNEL_COMMANDS)
        assert "/help" in s
        assert "/new" in s


# ---------------------------------------------------------------------------
# Membership lookup performance (O(1))
# ---------------------------------------------------------------------------


class TestMembershipLookup:
    """Verify fast membership checks work for all commands."""

    @pytest.mark.parametrize(
        "command",
        sorted(EXPECTED_COMMANDS),
    )
    def test_command_in_set(self, command: str):
        assert command in KNOWN_CHANNEL_COMMANDS

    @pytest.mark.parametrize(
        "command",
        ["/quit", "/exit", "/clear", "/stop", "/", "help", "/HELP", "", "/unknown"],
    )
    def test_unknown_command_not_in_set(self, command: str):
        assert command not in KNOWN_CHANNEL_COMMANDS


# ---------------------------------------------------------------------------
# Import behaviour
# ---------------------------------------------------------------------------


class TestImportBehaviour:
    """Verify the module can be imported and re-imported idempotently."""

    def test_import_succeeds(self):
        import app.channels.commands

        assert hasattr(app.channels.commands, "KNOWN_CHANNEL_COMMANDS")

    def test_reimport_returns_same_object(self):
        import importlib

        import app.channels.commands

        first = app.channels.commands.KNOWN_CHANNEL_COMMANDS
        mod = importlib.reload(app.channels.commands)
        second = mod.KNOWN_CHANNEL_COMMANDS
        # After reload a new frozenset is created; verify equivalence not identity
        assert first == second

    def test_import_from_module(self):
        from app.channels import commands

        assert commands.KNOWN_CHANNEL_COMMANDS == EXPECTED_COMMANDS

    def test_direct_attribute_access(self):
        import app.channels.commands as cmds

        assert cmds.KNOWN_CHANNEL_COMMANDS == EXPECTED_COMMANDS


# ---------------------------------------------------------------------------
# Cross-consumer consistency
# ---------------------------------------------------------------------------


class TestCrossConsumerConsistency:
    """Ensure consumers that reference commands stay in sync."""

    def test_feishu_parser_uses_same_set(self):
        """Feishu channel parser should recognise all known commands."""
        import inspect

        import app.channels.feishu as feishu_mod

        # KNOWN_CHANNEL_COMMANDS is used in the module-level _is_feishu_command
        source = inspect.getsource(feishu_mod)
        assert "KNOWN_CHANNEL_COMMANDS" in source

    def test_manager_uses_same_set(self):
        """ChannelManager should reference KNOWN_CHANNEL_COMMANDS."""
        import inspect

        from app.channels.manager import ChannelManager

        source = inspect.getsource(ChannelManager)
        assert "KNOWN_CHANNEL_COMMANDS" in source

    def test_dingtalk_uses_same_set(self):
        """DingTalk channel should reference KNOWN_CHANNEL_COMMANDS."""
        import inspect

        import app.channels.dingtalk as dingtalk_mod

        # KNOWN_CHANNEL_COMMANDS is used in the module-level _is_dingtalk_command
        source = inspect.getsource(dingtalk_mod)
        assert "KNOWN_CHANNEL_COMMANDS" in source


# ---------------------------------------------------------------------------
# Uniqueness / no duplicates (inherent to frozenset, but explicit test)
# ---------------------------------------------------------------------------


class TestUniqueness:
    """Frozensets guarantee uniqueness; verify it explicitly."""

    def test_no_duplicate_elements(self):
        """A frozenset inherently has no duplicates — verify len matches."""
        elements = list(KNOWN_CHANNEL_COMMANDS)
        assert len(elements) == len(set(elements))

    def test_unique_slash_prefix_variants(self):
        """Ensure commands are distinct (e.g. /new vs /new_something)."""
        commands = sorted(KNOWN_CHANNEL_COMMANDS)
        for i in range(len(commands) - 1):
            assert commands[i] != commands[i + 1]
            # Also ensure no command is a prefix of another (except '/')
            assert not commands[i + 1].startswith(commands[i] + "_")
