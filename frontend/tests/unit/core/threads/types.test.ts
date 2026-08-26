import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, it } from "vitest";

import type {
  AgentThreadContext,
  AgentThreadState,
  RunMessage,
  ThreadTokenUsageResponse,
} from "@/core/threads/types";

describe("AgentThreadState", () => {
  it("can be constructed with required fields", () => {
    const state: AgentThreadState = {
      title: "Test Thread",
      messages: [],
      artifacts: [],
    };
    expect(state.title).toBe("Test Thread");
    expect(state.messages).toEqual([]);
    expect(state.artifacts).toEqual([]);
  });

  it("handles optional todos field", () => {
    const state: AgentThreadState = {
      title: "Test Thread",
      messages: [],
      artifacts: [],
      todos: [],
    };
    expect(state.todos).toEqual([]);
  });
});

describe("AgentThreadContext", () => {
  it("can be constructed with required fields", () => {
    const ctx: AgentThreadContext = {
      thread_id: "thread-1",
      model_name: "gpt-4",
      thinking_enabled: false,
      is_plan_mode: true,
      subagent_enabled: false,
    };
    expect(ctx.thread_id).toBe("thread-1");
    expect(ctx.is_plan_mode).toBe(true);
  });

  it("handles optional reasoning fields", () => {
    const ctx: AgentThreadContext = {
      thread_id: "thread-2",
      model_name: undefined,
      thinking_enabled: true,
      is_plan_mode: false,
      subagent_enabled: true,
      reasoning_effort: "high",
      agent_name: "assistant",
    };
    expect(ctx.model_name).toBeUndefined();
    expect(ctx.reasoning_effort).toBe("high");
    expect(ctx.agent_name).toBe("assistant");
  });

  it("accepts all reasoning_effort values", () => {
    const efforts: Array<AgentThreadContext["reasoning_effort"]> = [
      "minimal",
      "low",
      "medium",
      "high",
    ];
    for (const effort of efforts) {
      const ctx: AgentThreadContext = {
        thread_id: "t-1",
        model_name: undefined,
        thinking_enabled: false,
        is_plan_mode: false,
        subagent_enabled: false,
        reasoning_effort: effort,
      };
      expect(ctx.reasoning_effort).toBe(effort);
    }
  });
});

describe("RunMessage", () => {
  it("can be constructed with metadata", () => {
    const msg: RunMessage = {
      run_id: "run-1",
      seq: 1,
      content: { type: "human", content: "Hello" } as Message,
      metadata: { caller: "lead_agent" },
      created_at: "2024-01-01T00:00:00Z",
    };
    expect(msg.run_id).toBe("run-1");
    expect(msg.metadata.caller).toBe("lead_agent");
  });
});

describe("ThreadTokenUsageResponse", () => {
  it("can be constructed with nested by_model and by_caller", () => {
    const usage: ThreadTokenUsageResponse = {
      thread_id: "thread-1",
      total_tokens: 1000,
      total_input_tokens: 600,
      total_output_tokens: 400,
      total_runs: 5,
      by_model: {
        "gpt-4": { tokens: 800, runs: 3 },
        "claude-3": { tokens: 200, runs: 2 },
      },
      by_caller: {
        lead_agent: 600,
        subagent: 300,
        middleware: 100,
      },
    };
    expect(usage.total_tokens).toBe(1000);
    expect(Object.keys(usage.by_model)).toHaveLength(2);
    expect(usage.by_caller.lead_agent).toBe(600);
  });
});
