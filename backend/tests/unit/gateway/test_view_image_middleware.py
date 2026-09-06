"""Unit tests for ViewImageMiddleware.

Tests cover the middleware's ability to inject image details (including base64
payloads) as a HumanMessage before the next LLM call, triggered only when the
previous assistant turn contained `view_image` tool calls that have all been
completed with corresponding ToolMessages.

Covered behavior:
- `_get_last_assistant_message` returns the most recent AIMessage (or None).
- `_has_view_image_tool` only matches assistant messages with `view_image` tool calls.
- `_all_tools_completed` verifies every tool call id has a matching ToolMessage.
- `_create_image_details_message` produces correctly structured content blocks.
- `_should_inject_image_message` gates injection on all preconditions, including
  deduplication when an image-details message was already added.
- `_inject_image_message` returns a state update with a HumanMessage, or None
  when injection is not warranted.
- `before_model` and `abefore_model` expose the same behavior sync/async.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from deerflow.agents.middlewares.view_image_middleware import ViewImageMiddleware


def _view_image_call(call_id: str = "call_1", path: str = "/mnt/user-data/uploads/img.png") -> dict:
    return {"name": "view_image", "id": call_id, "args": {"image_path": path}}


def _other_tool_call(call_id: str = "call_other", name: str = "bash") -> dict:
    return {"name": name, "id": call_id, "args": {"command": "ls"}}


def _runtime() -> MagicMock:
    """Minimal Runtime stub. The middleware doesn't use it today, but the
    interface requires it."""
    return MagicMock()


class TestGetLastAssistantMessage:
    def test_returns_none_on_empty_list(self):
        mw = ViewImageMiddleware()
        assert mw._get_last_assistant_message([]) is None

    def test_returns_none_when_no_ai_message(self):
        mw = ViewImageMiddleware()
        messages = [
            SystemMessage(content="sys"),
            HumanMessage(content="hi"),
        ]
        assert mw._get_last_assistant_message(messages) is None

    def test_returns_most_recent_ai_message(self):
        mw = ViewImageMiddleware()
        older = AIMessage(content="older")
        newer = AIMessage(content="newer")
        messages = [HumanMessage(content="q"), older, HumanMessage(content="q2"), newer]
        assert mw._get_last_assistant_message(messages) is newer


class TestHasViewImageTool:
    def test_returns_false_when_tool_calls_attr_missing(self):
        """Exercise the `not hasattr(message, "tool_calls")` guard.

        AIMessage always has a `tool_calls` attribute, so we use a plain
        object that truly lacks the attribute to cover this branch.
        """
        mw = ViewImageMiddleware()
        msg = SimpleNamespace(content="just text")  # no tool_calls attribute
        assert not hasattr(msg, "tool_calls")  # precondition
        assert mw._has_view_image_tool(msg) is False

    def test_returns_false_when_ai_message_has_no_tool_calls(self):
        """AIMessage without tool_calls kwarg defaults to an empty list."""
        mw = ViewImageMiddleware()
        msg = AIMessage(content="just text")
        assert mw._has_view_image_tool(msg) is False

    def test_returns_false_when_tool_calls_empty(self):
        mw = ViewImageMiddleware()
        msg = AIMessage(content="", tool_calls=[])
        assert mw._has_view_image_tool(msg) is False

    def test_returns_true_when_view_image_present(self):
        mw = ViewImageMiddleware()
        msg = AIMessage(content="", tool_calls=[_view_image_call()])
        assert mw._has_view_image_tool(msg) is True

    def test_returns_true_when_view_image_mixed_with_others(self):
        mw = ViewImageMiddleware()
        msg = AIMessage(
            content="",
            tool_calls=[_other_tool_call(), _view_image_call(call_id="call_vi")],
        )
        assert mw._has_view_image_tool(msg) is True

    def test_returns_false_when_only_other_tools(self):
        mw = ViewImageMiddleware()
        msg = AIMessage(content="", tool_calls=[_other_tool_call()])
        assert mw._has_view_image_tool(msg) is False


class TestAllToolsCompleted:
    def test_returns_false_when_no_tool_calls(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[])
        assert mw._all_tools_completed([assistant], assistant) is False

    def test_returns_true_when_all_completed(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(
            content="",
            tool_calls=[_view_image_call("c1"), _view_image_call("c2", "/p2.png")],
        )
        messages = [
            assistant,
            ToolMessage(content="ok", tool_call_id="c1"),
            ToolMessage(content="ok", tool_call_id="c2"),
        ]
        assert mw._all_tools_completed(messages, assistant) is True

    def test_returns_false_when_some_tool_call_unanswered(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(
            content="",
            tool_calls=[_view_image_call("c1"), _view_image_call("c2", "/p2.png")],
        )
        messages = [assistant, ToolMessage(content="ok", tool_call_id="c1")]
        assert mw._all_tools_completed(messages, assistant) is False

    def test_returns_false_when_assistant_not_in_messages(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        # assistant is not part of the list, so messages.index() will raise and be caught
        messages = [HumanMessage(content="hi")]
        assert mw._all_tools_completed(messages, assistant) is False

    def test_ignores_tool_messages_before_assistant(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        # A stale ToolMessage with matching id appears BEFORE the assistant turn.
        # It should not count — only ToolMessages after the assistant close the call.
        messages = [
            ToolMessage(content="stale", tool_call_id="c1"),
            assistant,
        ]
        assert mw._all_tools_completed(messages, assistant) is False


class TestCreateImageDetailsMessage:
    def test_returns_placeholder_when_no_images(self):
        mw = ViewImageMiddleware()
        state = {"viewed_images": {}}
        blocks = mw._create_image_details_message(state)
        assert blocks == [{"type": "text", "text": "No images have been viewed."}]

    def test_returns_placeholder_when_state_missing_key(self):
        mw = ViewImageMiddleware()
        blocks = mw._create_image_details_message({})
        assert blocks == [{"type": "text", "text": "No images have been viewed."}]

    def test_builds_blocks_for_single_image(self, tmp_path):
        """Upstream reads image bytes from disk on-demand; state carries only the path."""
        mw = ViewImageMiddleware()
        png = tmp_path / "cat.png"
        png.write_bytes(b"\x89PNG-fake-bytes")

        state = {
            "viewed_images": {
                "/path/to/cat.png": {"mime_type": "image/png", "actual_path": str(png), "size": png.stat().st_size},
            }
        }
        blocks = mw._create_image_details_message(state)

        # header text + per-image description text + per-image image_url block
        assert len(blocks) == 3
        assert blocks[0] == {"type": "text", "text": "Here are the images you've viewed:"}
        assert blocks[1]["type"] == "text"
        assert "/path/to/cat.png" in blocks[1]["text"]
        assert "image/png" in blocks[1]["text"]
        assert blocks[2]["type"] == "image_url"
        assert blocks[2]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_builds_blocks_for_multiple_images(self, tmp_path):
        mw = ViewImageMiddleware()
        png = tmp_path / "a.png"
        png.write_bytes(b"\x89PNG-a")
        jpg = tmp_path / "b.jpg"
        jpg.write_bytes(b"\xff\xd8-jpeg")

        state = {
            "viewed_images": {
                "/a.png": {"mime_type": "image/png", "actual_path": str(png), "size": png.stat().st_size},
                "/b.jpg": {"mime_type": "image/jpeg", "actual_path": str(jpg), "size": jpg.stat().st_size},
            }
        }
        blocks = mw._create_image_details_message(state)

        # 1 header + (1 description + 1 image_url) per image = 5 blocks
        assert len(blocks) == 5
        image_url_blocks = [b for b in blocks if isinstance(b, dict) and b.get("type") == "image_url"]
        assert len(image_url_blocks) == 2
        urls = {b["image_url"]["url"] for b in image_url_blocks}
        assert any(url.startswith("data:image/png;base64,") for url in urls)
        assert any(url.startswith("data:image/jpeg;base64,") for url in urls)

    def test_notes_unavailable_file_instead_of_image_block(self, tmp_path):
        """A vanished or changed file degrades to a text note, never a stale image."""
        mw = ViewImageMiddleware()
        state = {
            "viewed_images": {
                "/gone.png": {"mime_type": "image/png", "actual_path": str(tmp_path / "missing.png"), "size": 10},
            }
        }
        blocks = mw._create_image_details_message(state)
        assert len(blocks) == 3
        assert blocks[2] == {"type": "text", "text": f"  (file unavailable or changed on disk: {tmp_path / 'missing.png'})"}

    def test_omits_image_block_without_actual_path(self):
        """Legacy state entries without actual_path render the description only."""
        mw = ViewImageMiddleware()
        state = {
            "viewed_images": {
                "/broken.png": {"base64": "", "mime_type": "image/png"},
            }
        }
        blocks = mw._create_image_details_message(state)
        # header + description only (no image_url since there is nothing to read)
        assert len(blocks) == 2
        assert all(not (isinstance(b, dict) and b.get("type") == "image_url") for b in blocks)

    def test_uses_unknown_mime_type_when_missing(self):
        mw = ViewImageMiddleware()
        state = {
            "viewed_images": {
                "/mystery.bin": {"base64": "XYZ"},  # no mime_type key
            }
        }
        blocks = mw._create_image_details_message(state)
        # The description block should mention unknown
        description_blocks = [b for b in blocks if b.get("type") == "text" and "/mystery.bin" in b.get("text", "")]
        assert len(description_blocks) == 1
        assert "unknown" in description_blocks[0]["text"]


class TestShouldInjectImageMessage:
    """Upstream takes the message list directly (state-independent check)."""

    def test_false_when_no_messages(self):
        mw = ViewImageMiddleware()
        assert mw._should_inject_image_message([]) is False

    def test_false_when_no_assistant_message(self):
        mw = ViewImageMiddleware()
        assert mw._should_inject_image_message([HumanMessage(content="hello")]) is False

    def test_false_when_no_view_image_tool_call(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_other_tool_call()])
        messages = [assistant, ToolMessage(content="ok", tool_call_id="call_other")]
        assert mw._should_inject_image_message(messages) is False

    def test_false_when_tool_not_completed(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        assert mw._should_inject_image_message([assistant]) is False

    def test_true_when_all_preconditions_met(self):
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        messages = [assistant, ToolMessage(content="ok", tool_call_id="c1")]
        assert mw._should_inject_image_message(messages) is True

    def test_false_when_already_injected(self):
        """If a HumanMessage with the recognized header is already present after
        the assistant turn, we must not inject a duplicate."""
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        already_injected = HumanMessage(content="Here are the images you've viewed: /img.png")
        messages = [
            assistant,
            ToolMessage(content="ok", tool_call_id="c1"),
            already_injected,
        ]
        assert mw._should_inject_image_message(messages) is False

    def test_false_when_already_injected_with_list_content(self):
        """Deduplication must recognize the real injected payload shape.

        The injected HumanMessage content is a *list* of dicts (text +
        image_url blocks), not a plain string; the check still detects the
        header via ``str(msg.content)``.
        """
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        already_injected = HumanMessage(content=[{"type": "text", "text": "Here are the images you've viewed:"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}])
        messages = [
            assistant,
            ToolMessage(content="ok", tool_call_id="c1"),
            already_injected,
        ]
        assert mw._should_inject_image_message(messages) is False

    def test_false_when_legacy_details_marker_present(self):
        """The middleware also recognizes the legacy 'Here are the details of the
        images you've viewed' marker as an already-injected signal."""
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        legacy = HumanMessage(content="Here are the details of the images you've viewed: ...")
        messages = [
            assistant,
            ToolMessage(content="ok", tool_call_id="c1"),
            legacy,
        ]
        assert mw._should_inject_image_message(messages) is False


class TestWrapModelCallInjection:
    """Upstream injects via wrap_model_call/_inject: the middleware owns the
    image context, drops stranded copies, and appends one rebuilt message."""

    def _make_request(self, messages, state=None):
        from langchain.agents.middleware import ModelRequest

        return ModelRequest(model=MagicMock(), messages=messages, state=state or {})

    def test_request_untouched_when_should_not_inject(self):
        mw = ViewImageMiddleware()
        request = self._make_request([HumanMessage(content="hi")])
        seen = {}

        def handler(req):
            seen["messages"] = req.messages
            return req

        mw.wrap_model_call(request, handler)
        assert seen["messages"] == [HumanMessage(content="hi")]

    def test_appends_image_context_human_message_when_ready(self, tmp_path):
        mw = ViewImageMiddleware()
        png = tmp_path / "img.png"
        png.write_bytes(b"\x89PNG-fake")
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        state = {
            "messages": [assistant, ToolMessage(content="ok", tool_call_id="c1")],
            "viewed_images": {
                "/img.png": {"mime_type": "image/png", "actual_path": str(png), "size": png.stat().st_size},
            },
        }
        request = self._make_request(list(state["messages"]), state=state)
        seen = {}

        def handler(req):
            seen["messages"] = req.messages
            return req

        mw.wrap_model_call(request, handler)

        injected = seen["messages"][-1]
        assert isinstance(injected, HumanMessage)
        assert injected.additional_kwargs.get("hide_from_ui") is True
        assert isinstance(injected.content, list)
        assert any(isinstance(b, dict) and b.get("type") == "image_url" for b in injected.content)

    def test_drops_stranded_copy_before_rebuilding(self, tmp_path):
        """A stale injected copy from an old checkpoint is dropped, not duplicated."""
        mw = ViewImageMiddleware()
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        stranded = mw._create_image_context_message([{"type": "text", "text": "Here are the images you've viewed:"}])
        state = {"messages": [assistant, ToolMessage(content="ok", tool_call_id="c1"), stranded], "viewed_images": {}}
        request = self._make_request(list(state["messages"]), state=state)
        seen = {}

        def handler(req):
            seen["messages"] = req.messages
            return req

        mw.wrap_model_call(request, handler)

        assert stranded not in seen["messages"]
        assert seen["messages"][-1] is not stranded

    @pytest.mark.anyio
    async def test_awrap_model_call_matches_sync_behavior(self, tmp_path):
        mw = ViewImageMiddleware()
        png = tmp_path / "img.png"
        png.write_bytes(b"\x89PNG-fake")
        assistant = AIMessage(content="", tool_calls=[_view_image_call("c1")])
        state = {
            "messages": [assistant, ToolMessage(content="ok", tool_call_id="c1")],
            "viewed_images": {
                "/img.png": {"mime_type": "image/png", "actual_path": str(png), "size": png.stat().st_size},
            },
        }
        request = self._make_request(list(state["messages"]), state=state)
        seen = {}

        async def handler(req):
            seen["messages"] = req.messages
            return req

        await mw.awrap_model_call(request, handler)

        injected = seen["messages"][-1]
        assert isinstance(injected, HumanMessage)
        assert injected.additional_kwargs.get("hide_from_ui") is True
