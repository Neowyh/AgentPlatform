import { describe, expect, test, vi } from "vitest";

import {
  pathOfThread,
  textOfMessage,
  titleOfThread,
} from "@/core/threads/utils";

// ---------------------------------------------------------------------------
// pathOfThread
// ---------------------------------------------------------------------------

describe("pathOfThread", () => {
  test("string thread ID with no context returns standard chat path", () => {
    expect(pathOfThread("thread-123")).toBe("/workspace/chats/thread-123");
  });

  test("string thread ID with context having agent_name returns agent chat path", () => {
    expect(pathOfThread("thread-123", { agent_name: "researcher" })).toBe(
      "/workspace/capabilities/experts/researcher/chats/thread-123",
    );
  });

  test("object thread with thread_id and context.agent_name uses context.agent_name", () => {
    expect(
      pathOfThread({
        thread_id: "thread-123",
        context: { agent_name: "analyst" },
      }),
    ).toBe("/workspace/capabilities/experts/analyst/chats/thread-123");
  });

  test("object thread with no context but metadata.agent_name uses metadata.agent_name", () => {
    expect(
      pathOfThread({
        thread_id: "thread-456",
        metadata: { agent_name: "coder" },
      }),
    ).toBe("/workspace/capabilities/experts/coder/chats/thread-456");
  });

  test("object thread with context.agent_name and metadata.agent_name prefers context.agent_name", () => {
    expect(
      pathOfThread({
        thread_id: "thread-789",
        context: { agent_name: "from-context" },
        metadata: { agent_name: "from-metadata" },
      }),
    ).toBe("/workspace/capabilities/experts/from-context/chats/thread-789");
  });

  test("agent name with special characters is URL-encoded", () => {
    expect(pathOfThread("thread-abc", { agent_name: "ops agent" })).toBe(
      "/workspace/capabilities/experts/ops%20agent/chats/thread-abc",
    );
  });

  test("object thread with no agent context returns standard chat path", () => {
    expect(pathOfThread({ thread_id: "thread-no-agent" })).toBe(
      "/workspace/chats/thread-no-agent",
    );
  });

  test("metadata.agent_name with non-string value is ignored", () => {
    expect(
      pathOfThread({
        thread_id: "thread-100",
        metadata: { agent_name: 42 },
      } as any),
    ).toBe("/workspace/chats/thread-100");
  });
});

// ---------------------------------------------------------------------------
// textOfMessage
// ---------------------------------------------------------------------------

describe("textOfMessage", () => {
  test("message with string content returns the string", () => {
    const message = { content: "hello world" } as any;
    expect(textOfMessage(message)).toBe("hello world");
  });

  test("message with array content containing text parts returns first text part", () => {
    const message = {
      content: [
        { type: "image_url", image_url: { url: "http://example.com/img.png" } },
        { type: "text", text: "describe this" },
      ],
    } as any;
    expect(textOfMessage(message)).toBe("describe this");
  });

  test("message with array content with no text parts returns null", () => {
    const message = {
      content: [
        { type: "image_url", image_url: { url: "http://example.com/img.png" } },
      ],
    } as any;
    expect(textOfMessage(message)).toBeNull();
  });

  test("message with empty string content returns the empty string", () => {
    const message = { content: "" } as any;
    expect(textOfMessage(message)).toBe("");
  });

  test("message with null content returns null", () => {
    const message = { content: null } as any;
    expect(textOfMessage(message)).toBeNull();
  });

  test("message with multiple text parts returns first text part", () => {
    const message = {
      content: [
        { type: "text", text: "first" },
        { type: "text", text: "second" },
      ],
    } as any;
    expect(textOfMessage(message)).toBe("first");
  });

  test("message with empty array content returns null", () => {
    const message = { content: [] } as any;
    expect(textOfMessage(message)).toBeNull();
  });

  test("message with non-string non-array content returns null", () => {
    const message = { content: 123 } as any;
    expect(textOfMessage(message)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// titleOfThread
// ---------------------------------------------------------------------------

describe("titleOfThread", () => {
  test("thread with values.title returns title", () => {
    const thread = { values: { title: "My Thread" } } as any;
    expect(titleOfThread(thread)).toBe("My Thread");
  });

  test("thread without values.title returns Untitled", () => {
    const thread = { values: {} } as any;
    expect(titleOfThread(thread)).toBe("Untitled");
  });

  test("thread with values but no title returns Untitled", () => {
    const thread = {} as any;
    expect(titleOfThread(thread)).toBe("Untitled");
  });
});
