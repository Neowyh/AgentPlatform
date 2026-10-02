import { beforeEach, describe, expect, test, vi } from "vitest";

const mockRedirect = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

// ADR-0007 direction: /workspace/agents/* is canonical; the pre-unification
// /workspace/capabilities/experts/* URLs redirect permanently into it.
import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";
import AgentsGalleryRedirectPage from "@/app/workspace/agents/page";
import ExpertChatRedirectPage from "@/app/workspace/capabilities/experts/[agent_name]/chats/[thread_id]/page";
import ExpertEditRedirectPage from "@/app/workspace/capabilities/experts/[agent_name]/edit/page";
import ExpertDetailRedirectPage from "@/app/workspace/capabilities/experts/[agent_name]/page";
import NewExpertRedirectPage from "@/app/workspace/capabilities/experts/new/page";
import ExpertGalleryRedirectPage from "@/app/workspace/capabilities/experts/page";

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

describe("bare /workspace/agents gallery redirect", () => {
  test("routes to the capability-center agents tab preserving query", async () => {
    await AgentsGalleryRedirectPage({
      searchParams: Promise.resolve({ mock: "true" }),
    } as never);
    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/capabilities/agents?mock=true",
    );
  });
});

describe("experts-to-agents permanent redirects", () => {
  test("experts gallery URL routes to the agents tab", async () => {
    await ExpertGalleryRedirectPage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/capabilities/agents");
  });

  test("experts creation URL redirects preserving the path", async () => {
    await NewExpertRedirectPage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/agents/new");
  });

  test("expert detail URL redirects to the agent detail", async () => {
    await ExpertDetailRedirectPage({
      params: Promise.resolve({ agent_name: "test-agent" }),
    } as never);
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/agents/test-agent");
  });

  test("expert edit URL redirects to the agent edit", async () => {
    await ExpertEditRedirectPage({
      params: Promise.resolve({ agent_name: "test-agent" }),
    } as never);
    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/agents/test-agent/edit",
    );
  });

  test("expert chat URL redirects preserving path and query", async () => {
    const params = Promise.resolve({
      agent_name: "test-agent",
      thread_id: "abc123",
    });

    await ExpertChatRedirectPage({
      params,
      searchParams: Promise.resolve({ mock: "true" }),
    } as never);

    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/agents/test-agent/chats/abc123?mock=true",
    );
  });

  test("expert chat URL without query has no search suffix", async () => {
    const params = Promise.resolve({
      agent_name: "test-agent",
      thread_id: "abc123",
    });

    await ExpertChatRedirectPage({
      params,
      searchParams: Promise.resolve({}),
    } as never);

    expect(mockRedirect).toHaveBeenCalledWith(
      "/workspace/agents/test-agent/chats/abc123",
    );
  });
});
