import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  exportThreadAsJSON,
  exportThreadAsMarkdown,
  formatThreadAsJSON,
  formatThreadAsMarkdown,
} from "@/core/threads/export";
import type { AgentThread } from "@/core/threads/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/core/messages/utils", () => ({
  extractContentFromMessage: vi.fn((msg: any) => {
    if (typeof msg.content === "string") return msg.content;
    if (Array.isArray(msg.content)) {
      const textPart = msg.content.find((p: any) => p.type === "text");
      return textPart?.text ?? "";
    }
    return "";
  }),
  extractReasoningContentFromMessage: vi.fn((msg: any) => {
    return msg.additional_kwargs?.reasoning_content ?? null;
  }),
  hasContent: vi.fn((msg: any) => {
    if (typeof msg.content === "string") return msg.content.length > 0;
    if (Array.isArray(msg.content)) return msg.content.length > 0;
    return false;
  }),
  hasToolCalls: vi.fn(
    (msg: any) =>
      msg.type === "ai" &&
      Array.isArray(msg.tool_calls) &&
      msg.tool_calls.length > 0,
  ),
  isHiddenFromUIMessage: vi.fn(
    (msg: any) => msg.additional_kwargs?.hide_from_ui === true,
  ),
  stripInternalMarkers: vi.fn((text: string) => text),
}));

vi.mock("@/core/threads/utils", () => ({
  titleOfThread: vi.fn((thread: any) => thread.values?.title ?? "Untitled"),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeThread(overrides: Record<string, unknown> = {}): AgentThread {
  return {
    thread_id: "thread-1",
    created_at: "2026-05-21T00:00:00Z",
    updated_at: "2026-05-21T00:00:00Z",
    metadata: { title: "Demo thread" },
    status: "idle",
    values: { title: "Demo thread", messages: [] },
    ...overrides,
  } as unknown as AgentThread;
}

function human(content: string, extra: Record<string, unknown> = {}): any {
  return {
    id: `h-${content}`,
    type: "human",
    content,
    ...extra,
  };
}

function ai(content: string, extra: Record<string, unknown> = {}): any {
  return {
    id: `a-${content}`,
    type: "ai",
    content,
    ...extra,
  };
}

function toolMsg(content: string): any {
  return {
    id: `t-${content}`,
    type: "tool",
    content,
    name: "task",
    tool_call_id: "call-1",
  };
}

// ---------------------------------------------------------------------------
// formatThreadAsMarkdown
// ---------------------------------------------------------------------------

describe("formatThreadAsMarkdown", () => {
  test("basic thread with human and AI messages produces markdown with title and sections", () => {
    const md = formatThreadAsMarkdown(makeThread(), [
      human("hello"),
      ai("hi there"),
    ]);
    expect(md).toContain("hello");
    expect(md).toContain("hi there");
    expect(md).toContain("## 🧑 User");
    expect(md).toContain("## 🤖 Assistant");
  });

  test("with includeReasoning: true includes thinking details block", () => {
    const message = ai("final answer", {
      additional_kwargs: { reasoning_content: "step-by-step reasoning" },
    });
    const md = formatThreadAsMarkdown(makeThread(), [message], {
      includeReasoning: true,
    });
    expect(md).toContain("step-by-step reasoning");
    expect(md).toContain("Thinking");
    expect(md).toContain("<details>");
  });

  test("with includeToolCalls: true includes tool call formatting", () => {
    const message = ai("ok", {
      tool_calls: [{ id: "1", name: "search", args: { query: "test" } }],
    });
    const md = formatThreadAsMarkdown(makeThread(), [message], {
      includeToolCalls: true,
    });
    expect(md).toContain("**Tool:**");
    expect(md).toContain("`search`");
  });

  test("with includeToolMessages: true tool messages pass filter but are not rendered in markdown", () => {
    // Tool messages pass the visibleMessages filter when includeToolMessages
    // is true, but the markdown rendering loop only handles "human" and "ai"
    // types, so tool message content does not appear in the output.
    const md = formatThreadAsMarkdown(
      makeThread(),
      [ai("delegating"), toolMsg("Task Succeeded. Result: kept")],
      { includeToolMessages: true },
    );
    expect(md).toContain("delegating");
    expect(md).not.toContain("kept");
  });

  test("hidden messages excluded by default", () => {
    const hidden = human("internal reminder", {
      additional_kwargs: { hide_from_ui: true },
    });
    const md = formatThreadAsMarkdown(makeThread(), [hidden, ai("public")]);
    expect(md).not.toContain("internal reminder");
    expect(md).toContain("public");
  });

  test("empty messages array produces just header", () => {
    const md = formatThreadAsMarkdown(makeThread(), []);
    expect(md).toContain("# Demo thread");
    // No User or Assistant sections
    expect(md).not.toContain("## User");
    expect(md).not.toContain("## Assistant");
  });

  test("tool messages excluded by default", () => {
    const md = formatThreadAsMarkdown(makeThread(), [
      ai("delegating"),
      toolMsg("confidential result"),
    ]);
    expect(md).not.toContain("confidential result");
  });

  test("does not emit reasoning by default", () => {
    const message = ai("answer", {
      additional_kwargs: { reasoning_content: "secret thought" },
    });
    const md = formatThreadAsMarkdown(makeThread(), [message]);
    expect(md).not.toContain("secret thought");
  });

  test("does not emit tool calls by default", () => {
    const message = ai("ok", {
      tool_calls: [{ id: "1", name: "task", args: {} }],
    });
    const md = formatThreadAsMarkdown(makeThread(), [message]);
    expect(md).not.toContain("**Tool:**");
  });

  test("uses Untitled when thread has no title", () => {
    const md = formatThreadAsMarkdown(makeThread({ values: {} }), [ai("hi")]);
    expect(md).toContain("# Untitled");
  });

  test("skips human message with empty content", () => {
    const md = formatThreadAsMarkdown(makeThread(), [human("")]);
    // Empty human message should not produce a User section
    expect(md).not.toContain("## 🧑 User");
  });

  test("skips AI message with empty content and no tool calls or reasoning", () => {
    const md = formatThreadAsMarkdown(makeThread(), [ai("")]);
    // Empty AI message should not produce an Assistant section
    expect(md).not.toContain("## 🤖 Assistant");
  });

  test("includes AI content only when hasContent returns true", () => {
    // The mock hasContent returns true for non-empty string content
    const md = formatThreadAsMarkdown(makeThread(), [ai("real content")]);
    expect(md).toContain("real content");
    expect(md).toContain("## 🤖 Assistant");
  });
});

// ---------------------------------------------------------------------------
// formatThreadAsJSON
// ---------------------------------------------------------------------------

describe("formatThreadAsJSON", () => {
  test("basic thread produces valid JSON with messages array", () => {
    const raw = formatThreadAsJSON(makeThread(), [human("hello"), ai("hi")]);
    const parsed = JSON.parse(raw);
    expect(parsed).toHaveProperty("title", "Demo thread");
    expect(parsed).toHaveProperty("thread_id", "thread-1");
    expect(parsed).toHaveProperty("messages");
    expect(Array.isArray(parsed.messages)).toBe(true);
    expect(parsed.messages.length).toBe(2);
  });

  test("with options includes reasoning and tool_calls", () => {
    const message = ai("answer", {
      additional_kwargs: { reasoning_content: "my reasoning" },
      tool_calls: [{ id: "1", name: "search", args: { q: "x" } }],
    });
    const raw = formatThreadAsJSON(makeThread(), [message], {
      includeReasoning: true,
      includeToolCalls: true,
    });
    const parsed = JSON.parse(raw);
    expect(parsed.messages[0]).toHaveProperty("reasoning", "my reasoning");
    expect(parsed.messages[0]).toHaveProperty("tool_calls");
    expect(raw).toContain('"search"');
  });

  test("messages with no content are filtered out", () => {
    // The mock extractContentFromMessage returns "" for empty strings,
    // and hasContent returns false, so the message gets filtered out.
    const raw = formatThreadAsJSON(makeThread(), [ai("", { id: "ai-empty" })]);
    const parsed = JSON.parse(raw);
    expect(parsed.messages).toHaveLength(0);
  });

  test("hidden messages are filtered out", () => {
    const raw = formatThreadAsJSON(makeThread(), [
      human("secret", { additional_kwargs: { hide_from_ui: true } }),
      ai("public"),
    ]);
    expect(raw).not.toContain("secret");
    const parsed = JSON.parse(raw);
    expect(parsed.messages).toHaveLength(1);
  });

  test("tool messages filtered by default", () => {
    const raw = formatThreadAsJSON(makeThread(), [
      ai("ok"),
      toolMsg("internal result"),
    ]);
    expect(raw).not.toContain("internal result");
  });

  test("includeToolMessages keeps tool messages", () => {
    const raw = formatThreadAsJSON(makeThread(), [toolMsg("result data")], {
      includeToolMessages: true,
    });
    const parsed = JSON.parse(raw);
    expect(parsed.messages.some((m: any) => m.type === "tool")).toBe(true);
    expect(raw).toContain("result data");
  });

  test("produces exported_at timestamp", () => {
    const raw = formatThreadAsJSON(makeThread(), []);
    const parsed = JSON.parse(raw);
    expect(parsed).toHaveProperty("exported_at");
    expect(typeof parsed.exported_at).toBe("string");
  });
});

// ---------------------------------------------------------------------------
// exportThreadAsMarkdown
// ---------------------------------------------------------------------------

describe("exportThreadAsMarkdown", () => {
  let createObjectURLSpy: ReturnType<typeof vi.fn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.fn>;
  let clickSpy: ReturnType<typeof vi.fn>;
  let capturedFilename: string;

  beforeEach(() => {
    createObjectURLSpy = vi.fn(() => "blob:mock-md-url");
    revokeObjectURLSpy = vi.fn();
    URL.createObjectURL = createObjectURLSpy as any;
    URL.revokeObjectURL = revokeObjectURLSpy as any;

    capturedFilename = "";
    clickSpy = vi.fn();

    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      if (tag === "a") {
        const anchor = originalCreateElement(tag);
        Object.defineProperty(anchor, "download", {
          get: () => capturedFilename,
          set: (val: string) => {
            capturedFilename = val;
          },
        });
        (anchor as HTMLElement).click = clickSpy as unknown as () => void;
        return anchor;
      }
      return originalCreateElement(tag);
    });
    vi.spyOn(document.body, "appendChild").mockImplementation(
      () => ({}) as unknown as Node,
    );
    vi.spyOn(document.body, "removeChild").mockImplementation(
      () => ({}) as unknown as Node,
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("creates blob, creates anchor, and clicks it", () => {
    const thread = makeThread({ values: { title: "Export Test" } });
    exportThreadAsMarkdown(thread, [human("hello"), ai("response")]);

    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    const blobArg = createObjectURLSpy.mock.calls[0]?.[0] as Blob;
    expect(blobArg).toBeInstanceOf(Blob);
    expect(capturedFilename).toBe("Export Test.md");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  test("sanitizes special characters in filename", () => {
    const thread = makeThread({ values: { title: "!@#$%^&*()" } });
    exportThreadAsMarkdown(thread, [human("q")]);
    expect(capturedFilename).toBe("conversation.md");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  test("uses Untitled for thread without title", () => {
    const thread = makeThread({ values: {} });
    exportThreadAsMarkdown(thread, [ai("answer")]);
    expect(capturedFilename).toBe("Untitled.md");
  });
});

// ---------------------------------------------------------------------------
// exportThreadAsJSON
// ---------------------------------------------------------------------------

describe("exportThreadAsJSON", () => {
  let createObjectURLSpy: ReturnType<typeof vi.fn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.fn>;
  let clickSpy: ReturnType<typeof vi.fn>;
  let capturedFilename: string;

  beforeEach(() => {
    createObjectURLSpy = vi.fn(() => "blob:mock-json-url");
    revokeObjectURLSpy = vi.fn();
    URL.createObjectURL = createObjectURLSpy as any;
    URL.revokeObjectURL = revokeObjectURLSpy as any;

    capturedFilename = "";
    clickSpy = vi.fn();

    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      if (tag === "a") {
        const anchor = originalCreateElement(tag);
        Object.defineProperty(anchor, "download", {
          get: () => capturedFilename,
          set: (val: string) => {
            capturedFilename = val;
          },
        });
        (anchor as HTMLElement).click = clickSpy as unknown as () => void;
        return anchor;
      }
      return originalCreateElement(tag);
    });
    vi.spyOn(document.body, "appendChild").mockImplementation(
      () => ({}) as unknown as Node,
    );
    vi.spyOn(document.body, "removeChild").mockImplementation(
      () => ({}) as unknown as Node,
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("creates blob with JSON content and clicks anchor", () => {
    const thread = makeThread({ values: { title: "JSON Export" } });
    exportThreadAsJSON(thread, [human("hello"), ai("response")]);

    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    const blobArg = createObjectURLSpy.mock.calls[0]?.[0] as Blob;
    expect(blobArg).toBeInstanceOf(Blob);
    expect(capturedFilename).toBe("JSON Export.json");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  test("sanitizes special characters in JSON filename", () => {
    const thread = makeThread({ values: { title: "!@#$%^&*()" } });
    exportThreadAsJSON(thread, [human("q")]);
    expect(capturedFilename).toBe("conversation.json");
  });

  test("uses Untitled for thread without title in JSON export", () => {
    const thread = makeThread({ values: {} });
    exportThreadAsJSON(thread, [ai("answer")]);
    expect(capturedFilename).toBe("Untitled.json");
  });
});
