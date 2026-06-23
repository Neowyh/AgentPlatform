import type { Message } from "@langchain/langgraph-sdk";
import { expect, test } from "vitest";

import { enUS } from "@/core/i18n";
import {
  buildTokenDebugSteps,
  getTokenUsageViewPreset,
  tokenUsagePreferencesFromPreset,
} from "@/core/messages/usage-model";

test("maps token usage presets to persisted preferences", () => {
  expect(tokenUsagePreferencesFromPreset("off")).toEqual({
    headerTotal: false,
    inlineMode: "off",
  });
  expect(tokenUsagePreferencesFromPreset("summary")).toEqual({
    headerTotal: true,
    inlineMode: "off",
  });
  expect(tokenUsagePreferencesFromPreset("per_turn")).toEqual({
    headerTotal: true,
    inlineMode: "per_turn",
  });
  expect(tokenUsagePreferencesFromPreset("debug")).toEqual({
    headerTotal: true,
    inlineMode: "step_debug",
  });
});

test("derives the active preset from persisted preferences", () => {
  expect(
    getTokenUsageViewPreset({
      headerTotal: false,
      inlineMode: "off",
    }),
  ).toBe("off");

  expect(
    getTokenUsageViewPreset({
      headerTotal: true,
      inlineMode: "off",
    }),
  ).toBe("summary");

  expect(
    getTokenUsageViewPreset({
      headerTotal: true,
      inlineMode: "per_turn",
    }),
  ).toBe("per_turn");

  expect(
    getTokenUsageViewPreset({
      headerTotal: true,
      inlineMode: "step_debug",
    }),
  ).toBe("debug");
});

test("uses generic todo labels when backend attribution is absent", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "write_todos:1",
          name: "write_todos",
          args: {
            todos: [{ content: "Draft the plan", status: "in_progress" }],
          },
        },
      ],
      usage_metadata: {
        input_tokens: 100,
        output_tokens: 20,
        total_tokens: 120,
      },
    },
    {
      id: "tool-1",
      type: "tool",
      name: "write_todos",
      tool_call_id: "write_todos:1",
      content: "ok",
    },
    {
      id: "ai-2",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "write_todos:2",
          name: "write_todos",
          args: {
            todos: [{ content: "Draft the plan", status: "completed" }],
          },
        },
      ],
      usage_metadata: { input_tokens: 50, output_tokens: 10, total_tokens: 60 },
    },
    {
      id: "ai-3",
      type: "ai",
      content: "Here is the result",
      usage_metadata: { input_tokens: 40, output_tokens: 15, total_tokens: 55 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: "Update to-do list",
      sharedAttribution: false,
    }),
    expect.objectContaining({
      messageId: "ai-2",
      label: "Update to-do list",
      sharedAttribution: false,
    }),
    expect.objectContaining({
      messageId: "ai-3",
      label: "Final answer",
      sharedAttribution: false,
    }),
  ]);
});

test("marks multi-action AI steps as shared attribution", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "web_search:1",
          name: "web_search",
          args: { query: "LangGraph stream mode" },
        },
        {
          id: "write_todos:1",
          name: "write_todos",
          args: {
            todos: [
              {
                content: "Inspect stream mode handling",
                status: "in_progress",
              },
            ],
          },
        },
      ],
      usage_metadata: {
        input_tokens: 120,
        output_tokens: 30,
        total_tokens: 150,
      },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: "Step total",
      sharedAttribution: true,
      secondaryLabels: [
        'Search for "LangGraph stream mode"',
        "Update to-do list",
      ],
    }),
  ]);
});

test("prefers backend attribution metadata when available", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "write_todos:1",
          name: "write_todos",
          args: {
            todos: [
              {
                content: "Fallback label should not win",
                status: "in_progress",
              },
            ],
          },
        },
      ],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "todo_update",
          shared_attribution: false,
          actions: [{ kind: "todo_start", content: "Use backend attribution" }],
        },
      },
      usage_metadata: { input_tokens: 25, output_tokens: 5, total_tokens: 30 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: "Start To-do: Use backend attribution",
      sharedAttribution: false,
    }),
  ]);
});

test("falls back safely when attribution payload is malformed", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "web_search:1",
          name: "web_search",
          args: { query: "LangGraph stream mode" },
        },
      ],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          actions: { broken: true },
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: 'Search for "LangGraph stream mode"',
      sharedAttribution: false,
    }),
  ]);
});

test("ignores attribution actions that are not objects", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: true,
          actions: [
            null,
            "bad-action",
            { kind: "search", query: "valid search", ignored: "extra-field" },
          ],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: 'Search for "valid search"',
    }),
  ]);
});

test("ignores malformed attribution fields and falls back to message content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Real final answer",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: null,
          shared_attribution: null,
          tool_call_ids: [null, "tool-1", 123],
          actions: [{ query: "missing kind" }],
        },
      },
      usage_metadata: { input_tokens: 9, output_tokens: 3, total_tokens: 12 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: "Final answer",
      sharedAttribution: false,
    }),
  ]);
});

test("ignores unknown top-level attribution fields", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          unknown_field: "ignored",
          actions: [{ kind: "subagent", description: "Inspect the fix" }],
        },
      },
      usage_metadata: { input_tokens: 12, output_tokens: 4, total_tokens: 16 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: "Subagent: Inspect the fix",
      sharedAttribution: false,
    }),
  ]);
});

test("falls back to generic todo labels when backend attribution has no actions", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "write_todos:1",
          name: "write_todos",
          args: {
            todos: [{ content: "Clean up stale tasks", status: "in_progress" }],
          },
        },
      ],
      usage_metadata: {
        input_tokens: 100,
        output_tokens: 20,
        total_tokens: 120,
      },
    },
    {
      id: "ai-2",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "write_todos:2",
          name: "write_todos",
          args: {
            todos: [],
          },
        },
      ],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "todo_update",
          shared_attribution: false,
          actions: [],
        },
      },
      usage_metadata: { input_tokens: 30, output_tokens: 8, total_tokens: 38 },
    },
  ] as Message[];

  expect(buildTokenDebugSteps(messages, enUS)).toEqual([
    expect.objectContaining({
      messageId: "ai-1",
      label: "Update to-do list",
    }),
    expect.objectContaining({
      messageId: "ai-2",
      label: "Update to-do list",
      sharedAttribution: false,
    }),
  ]);
});

// ---------------------------------------------------------------------------
// buildTokenDebugSteps – additional coverage
// ---------------------------------------------------------------------------

test("skips non-AI messages", () => {
  const messages = [
    { id: "h-1", type: "human", content: "hello" },
    { id: "t-1", type: "tool", content: "result", tool_call_id: "tc-1" },
  ] as Message[];
  expect(buildTokenDebugSteps(messages, enUS)).toEqual([]);
});

test("uses message.id fallback when message.id is undefined", () => {
  const messages = [
    {
      id: undefined,
      type: "ai",
      content: "Final answer text",
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toHaveLength(1);
  expect(steps[0]!.id).toBe("token-step-0");
  expect(steps[0]!.messageId).toBe("token-step-0");
});

test("uses 'Thinking' label for AI message with no content and no attribution", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      usage_metadata: { input_tokens: 5, output_tokens: 1, total_tokens: 6 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Thinking",
      sharedAttribution: false,
    }),
  ]);
});

test("uses 'Thinking' label for AI message with undefined content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: undefined,
      tool_calls: [],
      usage_metadata: { input_tokens: 5, output_tokens: 1, total_tokens: 6 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Thinking",
      sharedAttribution: false,
    }),
  ]);
});

test("uses 'Final answer' label for AI message with content but no attribution or tool calls", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Here is my answer",
      tool_calls: [],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Final answer",
      sharedAttribution: false,
    }),
  ]);
});

test("uses 'Final answer' label for attribution with kind 'final_answer' and no actions", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Done",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "final_answer",
          shared_attribution: false,
          actions: [],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Final answer",
      sharedAttribution: false,
    }),
  ]);
});

test("uses 'Thinking' label for attribution with kind 'thinking' and no actions", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "thinking",
          shared_attribution: false,
          actions: [],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Thinking",
      sharedAttribution: false,
    }),
  ]);
});

test("describes web_search tool call with query", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "ws:1",
          name: "web_search",
          args: { query: "TypeScript generics" },
        },
      ],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: 'Search for "TypeScript generics"',
    }),
  ]);
});

test("describes image_search tool call with query", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        { id: "is:1", name: "image_search", args: { query: "cats" } },
      ],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: 'Search for "cats"',
    }),
  ]);
});

test("describes web_search tool call without query", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [{ id: "ws:1", name: "web_search", args: {} }],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: 'Use "web_search" tool',
    }),
  ]);
});

test("describes web_fetch tool call", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        { id: "wf:1", name: "web_fetch", args: { url: "http://example.com" } },
      ],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "View web page",
    }),
  ]);
});

test("describes present_files tool call", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        { id: "pf:1", name: "present_files", args: { filepaths: ["a.ts"] } },
      ],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Present files",
    }),
  ]);
});

test("describes ask_clarification tool call", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [{ id: "ac:1", name: "ask_clarification", args: {} }],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Need your help",
    }),
  ]);
});

test("describes task tool call with description", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "task:1",
          name: "task",
          args: { description: "Analyze the data" },
        },
      ],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Subagent: Analyze the data",
    }),
  ]);
});

test("describes task tool call without description", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [{ id: "task:1", name: "task", args: {} }],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Subagent: Subtask",
    }),
  ]);
});

test("describes generic tool with description arg", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [
        {
          id: "tool:1",
          name: "custom_tool",
          args: { description: "Do something special" },
        },
      ],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: "Do something special",
    }),
  ]);
});

test("describes generic tool without description arg", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [{ id: "tool:1", name: "custom_tool", args: {} }],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toEqual([
    expect.objectContaining({
      label: 'Use "custom_tool" tool',
    }),
  ]);
});

// ---------------------------------------------------------------------------
// Attribution action kinds
// ---------------------------------------------------------------------------

test("describes todo_start attribution with content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_start", content: "Research phase" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Start To-do: Research phase");
});

test("describes todo_start attribution without content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_start" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Update to-do list");
});

test("describes todo_complete attribution with content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_complete", content: "Write tests" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Complete To-do: Write tests");
});

test("describes todo_complete attribution without content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_complete" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Update to-do list");
});

test("describes todo_update attribution with content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_update", content: "Refactor code" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Update To-do: Refactor code");
});

test("describes todo_update attribution without content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_update" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Update to-do list");
});

test("describes todo_remove attribution with content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_remove", content: "Old task" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Remove To-do: Old task");
});

test("describes todo_remove attribution without content", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "todo_remove" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Update to-do list");
});

test("describes subagent attribution action", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "subagent_dispatch",
          shared_attribution: false,
          actions: [{ kind: "subagent", description: "Run code analysis" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Subagent: Run code analysis");
});

test("describes subagent attribution without description", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "subagent_dispatch",
          shared_attribution: false,
          actions: [{ kind: "subagent" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Subagent: Subtask");
});

test("describes search attribution with query", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "search", query: "React hooks patterns" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe('Search for "React hooks patterns"');
});

test("describes search attribution without query but with tool_name", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "search", tool_name: "brave_search" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe('Use "brave_search" tool');
});

test("describes search attribution without query and without tool_name", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "search" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe('Use "search" tool');
});

test("describes present_files attribution action", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "present_files" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Present files");
});

test("describes clarification attribution action", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "clarification" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Need your help");
});

test("describes tool attribution action", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [
            {
              kind: "tool",
              tool_name: "code_interpreter",
              description: "Run script",
            },
          ],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Run script");
});

test("describes tool attribution without description", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "tool", tool_name: "code_interpreter" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe('Use "code_interpreter" tool');
});

test("describes tool attribution without tool_name or description", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "tool" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe('Use "tool" tool');
});

// ---------------------------------------------------------------------------
// normalizeTokenUsageAttribution edge cases
// ---------------------------------------------------------------------------

test("ignores attribution when additional_kwargs is not an object", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      additional_kwargs: "not-an-object",
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Final answer");
});

test("ignores attribution when it is a string", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: "not-an-object",
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Final answer");
});

test("ignores attribution when it is an array", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: [{ kind: "thinking" }],
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Final answer");
});

test("returns null attribution when actions is not an array", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          kind: "thinking",
          actions: "not-an-array",
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  // attribution is null, falls back to tool calls/content
  expect(steps[0]!.label).toBe("Final answer");
});

test("normalizes version and shared_attribution from attribution", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 2,
          kind: "thinking",
          shared_attribution: true,
          tool_call_ids: ["tc-1", "tc-2"],
          actions: [],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  // attribution kind "thinking" with no actions -> "Thinking" label
  // sharedAttribution should be true (from attribution, though it only applies when actionLabels > 1)
  expect(steps[0]!.label).toBe("Thinking");
});

test("filters non-string tool_call_ids from attribution", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "thinking",
          shared_attribution: false,
          tool_call_ids: [123, null, "valid-id", ""],
          actions: [],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  // Should not throw, normalization filters invalid entries
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps).toHaveLength(1);
});

test("returns null when attribution object is null", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: null,
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Final answer");
});

test("returns null when additional_kwargs is missing", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.label).toBe("Final answer");
});

// ---------------------------------------------------------------------------
// describeAttributionAction – unknown kind falls through to default
// ---------------------------------------------------------------------------

test("ignores unknown attribution action kinds", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "Answer",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "unknown_kind" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as unknown as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  // Unknown action is filtered out (returns null), no valid labels
  // Falls back to content check
  expect(steps[0]!.label).toBe("Final answer");
});

// ---------------------------------------------------------------------------
// sharedAttribution with single action
// ---------------------------------------------------------------------------

test("sharedAttribution is false when single action is present", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          shared_attribution: false,
          actions: [{ kind: "search", query: "hello" }],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.sharedAttribution).toBe(false);
  expect(steps[0]!.secondaryLabels).toEqual([]);
  expect(steps[0]!.label).toBe('Search for "hello"');
});

test("sharedAttribution defaults to true when actionLabels.length > 1", () => {
  const messages = [
    {
      id: "ai-1",
      type: "ai",
      content: "",
      tool_calls: [],
      additional_kwargs: {
        token_usage_attribution: {
          version: 1,
          kind: "tool_batch",
          // shared_attribution not set (undefined)
          actions: [
            { kind: "search", query: "hello" },
            { kind: "present_files" },
          ],
        },
      },
      usage_metadata: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
    },
  ] as Message[];
  const steps = buildTokenDebugSteps(messages, enUS);
  expect(steps[0]!.sharedAttribution).toBe(true);
  expect(steps[0]!.label).toBe("Step total");
  expect(steps[0]!.secondaryLabels).toHaveLength(2);
});
