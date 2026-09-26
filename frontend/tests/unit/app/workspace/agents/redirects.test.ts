import { beforeEach, describe, expect, test, vi } from "vitest";

const mockRedirect = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

// Server components are async; render() handles promise-returning children.
import AgentChatRedirectPage from "@/app/workspace/agents/[agent_name]/chats/[thread_id]/page";
import NewAgentPage from "@/app/workspace/agents/new/page";
import AgentsPage from "@/app/workspace/agents/page";

beforeEach(() => {
  mockRedirect.mockClear();
});

describe("legacy /workspace/agents redirects", () => {
  test("gallery URL redirects to the capability center expert tab", () => {
    AgentsPage();
    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts",
    );
  });

  test("legacy creation URL redirects to the capability center creation page", () => {
    NewAgentPage();
    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/new",
    );
  });

  test("legacy expert chat URL redirects preserving path and query", async () => {
    const params = Promise.resolve({
      agent_name: "test-agent",
      thread_id: "abc123",
    });
    const searchParams = Promise.resolve({ mock: "true" });

    await AgentChatRedirectPage({ params, searchParams } as never);

    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/test-agent/chats/abc123?mock=true",
    );
  });

  test("legacy expert chat URL without query has no search suffix", async () => {
    const params = Promise.resolve({
      agent_name: "test-agent",
      thread_id: "abc123",
    });
    const searchParams = Promise.resolve({});

    await AgentChatRedirectPage({ params, searchParams } as never);

    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/test-agent/chats/abc123",
    );
  });

  test("repeated query keys are preserved as repeated parameters", async () => {
    const params = Promise.resolve({
      agent_name: "test-agent",
      thread_id: "abc123",
    });
    const searchParams = Promise.resolve({ tag: ["a", "b"] });

    await AgentChatRedirectPage({ params, searchParams } as never);

    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/test-agent/chats/abc123?tag=a&tag=b",
    );
  });
});
