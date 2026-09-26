import { beforeEach, describe, expect, test, vi } from "vitest";

const mockRedirect = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

// Server components are async; render() handles promise-returning children.
import AgentChatRedirectPage from "@/app/workspace/agents/[agent_name]/chats/[thread_id]/page";
import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";
import NewAgentPage from "@/app/workspace/agents/new/page";
import AgentsPage from "@/app/workspace/agents/page";

beforeEach(() => {
  mockRedirect.mockClear();
});

describe("legacyRedirectTarget", () => {
  test("appends nothing when search params are empty", () => {
    expect(legacyRedirectTarget("/workspace/x", {})).toBe("/workspace/x");
  });

  test("appends a single string parameter", () => {
    expect(legacyRedirectTarget("/workspace/x", { mock: "true" })).toBe(
      "/workspace/x?mock=true",
    );
  });

  test("encodes values and joins multiple keys", () => {
    expect(
      legacyRedirectTarget("/workspace/x", { mock: "true", q: "a b" }),
    ).toBe("/workspace/x?mock=true&q=a+b");
  });

  test("preserves repeated keys as repeated parameters", () => {
    expect(legacyRedirectTarget("/workspace/x", { tag: ["a", "b"] })).toBe(
      "/workspace/x?tag=a&tag=b",
    );
  });

  test("ignores undefined entries", () => {
    expect(legacyRedirectTarget("/workspace/x", { next: undefined })).toBe(
      "/workspace/x",
    );
  });
});

describe("legacy /workspace/agents redirects", () => {
  test("gallery URL redirects preserving path and query", async () => {
    await AgentsPage({
      searchParams: Promise.resolve({ mock: "true" }),
    } as never);
    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts?mock=true",
    );
  });

  test("legacy creation URL redirects preserving path and query", async () => {
    await NewAgentPage({
      searchParams: Promise.resolve({ mock: "true" }),
    } as never);
    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/experts/new?mock=true",
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
