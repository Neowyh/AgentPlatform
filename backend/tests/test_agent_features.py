"""Tests for ideer.agents.features — RuntimeFeatures dataclass and Next/Prev decorators."""

from __future__ import annotations

import pytest
from langchain.agents.middleware import AgentMiddleware

from ideer.agents.features import Next, Prev, RuntimeFeatures

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeMiddleware(AgentMiddleware):
    """Minimal concrete middleware for testing."""

    name = "fake"


class _AnotherMiddleware(AgentMiddleware):
    name = "another"


# ---------------------------------------------------------------------------
# RuntimeFeatures — default values
# ---------------------------------------------------------------------------


class TestRuntimeFeaturesDefaults:
    """Each flag must have the documented default."""

    def test_sandbox_defaults_true(self):
        assert RuntimeFeatures().sandbox is True

    def test_memory_defaults_false(self):
        assert RuntimeFeatures().memory is False

    def test_summarization_defaults_false(self):
        assert RuntimeFeatures().summarization is False

    def test_subagent_defaults_false(self):
        assert RuntimeFeatures().subagent is False

    def test_vision_defaults_false(self):
        assert RuntimeFeatures().vision is False

    def test_auto_title_defaults_false(self):
        assert RuntimeFeatures().auto_title is False

    def test_guardrail_defaults_false(self):
        assert RuntimeFeatures().guardrail is False

    def test_loop_detection_defaults_true(self):
        assert RuntimeFeatures().loop_detection is True

    def test_default_construction_has_all_flags(self):
        features = RuntimeFeatures()
        expected_flags = {
            "sandbox",
            "memory",
            "summarization",
            "subagent",
            "vision",
            "auto_title",
            "guardrail",
            "loop_detection",
        }
        assert set(features.__dataclass_fields__) == expected_flags


# ---------------------------------------------------------------------------
# RuntimeFeatures — bool values
# ---------------------------------------------------------------------------


class TestRuntimeFeaturesBoolValues:
    """Flags can be set to True or False explicitly."""

    def test_enable_memory(self):
        f = RuntimeFeatures(memory=True)
        assert f.memory is True

    def test_disable_sandbox(self):
        f = RuntimeFeatures(sandbox=False)
        assert f.sandbox is False

    def test_enable_subagent(self):
        f = RuntimeFeatures(subagent=True)
        assert f.subagent is True

    def test_enable_vision(self):
        f = RuntimeFeatures(vision=True)
        assert f.vision is True

    def test_enable_auto_title(self):
        f = RuntimeFeatures(auto_title=True)
        assert f.auto_title is True

    def test_disable_loop_detection(self):
        f = RuntimeFeatures(loop_detection=False)
        assert f.loop_detection is False


# ---------------------------------------------------------------------------
# RuntimeFeatures — AgentMiddleware values
# ---------------------------------------------------------------------------


class TestRuntimeFeaturesMiddlewareValues:
    """Flags accept an AgentMiddleware instance as a custom implementation."""

    def test_sandbox_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(sandbox=mw)
        assert f.sandbox is mw

    def test_memory_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(memory=mw)
        assert f.memory is mw

    def test_guardrail_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(guardrail=mw)
        assert f.guardrail is mw

    def test_summarization_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(summarization=mw)
        assert f.summarization is mw

    def test_loop_detection_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(loop_detection=mw)
        assert f.loop_detection is mw

    def test_subagent_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(subagent=mw)
        assert f.subagent is mw

    def test_vision_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(vision=mw)
        assert f.vision is mw

    def test_auto_title_with_custom_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(auto_title=mw)
        assert f.auto_title is mw


# ---------------------------------------------------------------------------
# RuntimeFeatures — combinations
# ---------------------------------------------------------------------------


class TestRuntimeFeaturesCombinations:
    """Multiple flags can be configured independently."""

    def test_all_enabled_with_bools(self):
        f = RuntimeFeatures(
            sandbox=True,
            memory=True,
            summarization=False,  # no built-in default, keep False
            subagent=True,
            vision=True,
            auto_title=True,
            guardrail=False,  # no built-in default, keep False
            loop_detection=True,
        )
        assert f.sandbox is True
        assert f.memory is True
        assert f.subagent is True
        assert f.vision is True
        assert f.auto_title is True
        assert f.loop_detection is True
        assert f.summarization is False
        assert f.guardrail is False

    def test_mixed_bool_and_middleware(self):
        mw = _FakeMiddleware()
        f = RuntimeFeatures(
            sandbox=False,
            memory=mw,
            subagent=True,
            vision=mw,
        )
        assert f.sandbox is False
        assert f.memory is mw
        assert f.subagent is True
        assert f.vision is mw

    def test_all_defaults_are_independent(self):
        """Changing one flag doesn't affect others."""
        base = RuntimeFeatures()
        toggled = RuntimeFeatures(memory=True)
        assert base.memory is False
        assert toggled.memory is True
        assert toggled.sandbox is True  # unchanged


# ---------------------------------------------------------------------------
# RuntimeFeatures — dataclass properties
# ---------------------------------------------------------------------------


class TestRuntimeFeaturesDataclassBehavior:
    """Standard dataclass behavior: equality, repr, immutability."""

    def test_equality(self):
        a = RuntimeFeatures()
        b = RuntimeFeatures()
        assert a == b

    def test_inequality(self):
        a = RuntimeFeatures(memory=True)
        b = RuntimeFeatures(memory=False)
        assert a != b

    def test_repr_contains_class_name(self):
        r = repr(RuntimeFeatures())
        assert "RuntimeFeatures" in r

    def test_fields_are_settable(self):
        f = RuntimeFeatures()
        f.memory = True
        assert f.memory is True


# ---------------------------------------------------------------------------
# Next decorator
# ---------------------------------------------------------------------------


class TestNextDecorator:
    """@Next(anchor) sets _next_anchor on the decorated class."""

    def test_sets_next_anchor(self):
        @Next(_FakeMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert _Target._next_anchor is _FakeMiddleware

    def test_raises_on_non_class(self):
        with pytest.raises(TypeError, match="@Next expects an AgentMiddleware subclass"):
            Next("not-a-class")

    def test_raises_on_non_middleware_class(self):
        class _NotMiddleware:
            pass

        with pytest.raises(TypeError, match="@Next expects an AgentMiddleware subclass"):
            Next(_NotMiddleware)

    def test_raises_on_instance(self):
        with pytest.raises(TypeError, match="@Next expects an AgentMiddleware subclass"):
            Next(_FakeMiddleware())

    def test_returns_decorated_class_unchanged(self):
        @Next(_FakeMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert issubclass(_Target, AgentMiddleware)
        assert _Target.name == "target"

    def test_different_anchors(self):
        @Next(_FakeMiddleware)
        class _A(AgentMiddleware):
            name = "a"

        @Next(_AnotherMiddleware)
        class _B(AgentMiddleware):
            name = "b"

        assert _A._next_anchor is _FakeMiddleware
        assert _B._next_anchor is _AnotherMiddleware


# ---------------------------------------------------------------------------
# Prev decorator
# ---------------------------------------------------------------------------


class TestPrevDecorator:
    """@Prev(anchor) sets _prev_anchor on the decorated class."""

    def test_sets_prev_anchor(self):
        @Prev(_FakeMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert _Target._prev_anchor is _FakeMiddleware

    def test_raises_on_non_class(self):
        with pytest.raises(TypeError, match="@Prev expects an AgentMiddleware subclass"):
            Prev("not-a-class")

    def test_raises_on_non_middleware_class(self):
        class _NotMiddleware:
            pass

        with pytest.raises(TypeError, match="@Prev expects an AgentMiddleware subclass"):
            Prev(_NotMiddleware)

    def test_raises_on_instance(self):
        with pytest.raises(TypeError, match="@Prev expects an AgentMiddleware subclass"):
            Prev(_FakeMiddleware())

    def test_returns_decorated_class_unchanged(self):
        @Prev(_FakeMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert issubclass(_Target, AgentMiddleware)
        assert _Target.name == "target"

    def test_different_anchors(self):
        @Prev(_FakeMiddleware)
        class _A(AgentMiddleware):
            name = "a"

        @Prev(_AnotherMiddleware)
        class _B(AgentMiddleware):
            name = "b"

        assert _A._prev_anchor is _FakeMiddleware
        assert _B._prev_anchor is _AnotherMiddleware


# ---------------------------------------------------------------------------
# Next + Prev combined
# ---------------------------------------------------------------------------


class TestNextPrevCombined:
    """Both decorators can be applied to the same class."""

    def test_both_anchors_set(self):
        @Next(_FakeMiddleware)
        @Prev(_AnotherMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert _Target._next_anchor is _FakeMiddleware
        assert _Target._prev_anchor is _AnotherMiddleware

    def test_order_independence(self):
        @Prev(_AnotherMiddleware)
        @Next(_FakeMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert _Target._next_anchor is _FakeMiddleware
        assert _Target._prev_anchor is _AnotherMiddleware


# ---------------------------------------------------------------------------
# Edge cases — falsy non-type inputs to Next / Prev
# ---------------------------------------------------------------------------


class TestDecoratorFalsyInputs:
    """Falsy non-type values should be rejected by Next and Prev."""

    @pytest.mark.parametrize("bad_input", [None, 0, [], "", {}, set()])
    def test_next_rejects_falsy_inputs(self, bad_input):
        with pytest.raises(TypeError, match="@Next expects an AgentMiddleware subclass"):
            Next(bad_input)

    @pytest.mark.parametrize("bad_input", [None, 0, [], "", {}, set()])
    def test_prev_rejects_falsy_inputs(self, bad_input):
        with pytest.raises(TypeError, match="@Prev expects an AgentMiddleware subclass"):
            Prev(bad_input)


# ---------------------------------------------------------------------------
# Edge cases — same decorator applied twice
# ---------------------------------------------------------------------------


class TestDecoratorDoubleApplication:
    """Applying the same decorator twice should overwrite the first anchor."""

    def test_next_twice_overwrites(self):
        """Python decorators apply bottom-up, so the outermost wins."""

        @Next(_FakeMiddleware)
        @Next(_AnotherMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert _Target._next_anchor is _FakeMiddleware

    def test_prev_twice_overwrites(self):
        """Python decorators apply bottom-up, so the outermost wins."""

        @Prev(_FakeMiddleware)
        @Prev(_AnotherMiddleware)
        class _Target(AgentMiddleware):
            name = "target"

        assert _Target._prev_anchor is _FakeMiddleware


# ---------------------------------------------------------------------------
# Edge cases — RuntimeFeatures invalid inputs
# ---------------------------------------------------------------------------


class TestRuntimeFeaturesInvalidInputs:
    """RuntimeFeatures should raise on invalid constructor arguments."""

    def test_unknown_field_raises(self):
        with pytest.raises(TypeError):
            RuntimeFeatures(nonexistent=True)

    def test_invalid_type_not_enforced(self):
        """Python dataclasses don't enforce type hints at runtime.

        This documents that ``memory="yes"`` is accepted silently —
        type safety depends on external checkers (mypy, pyright).
        """
        f = RuntimeFeatures(memory="yes")
        assert f.memory == "yes"

    def test_summarization_true_accepted(self):
        """Literal[False] type hint is not enforced at runtime."""
        f = RuntimeFeatures(summarization=True)
        assert f.summarization is True

    def test_guardrail_true_accepted(self):
        """Literal[False] type hint is not enforced at runtime."""
        f = RuntimeFeatures(guardrail=True)
        assert f.guardrail is True
