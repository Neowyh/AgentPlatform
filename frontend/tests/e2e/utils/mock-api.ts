/**
 * Shared mock helpers for E2E tests.
 *
 * Intercepts all LangGraph / Backend API endpoints so tests can run without
 * a real backend.  Each test file imports `mockLangGraphAPI` and
 * `handleRunStream` from here.
 */

import type { Page, Route } from "@playwright/test";

// ---------------------------------------------------------------------------
// Constants — deterministic IDs used across tests
// ---------------------------------------------------------------------------

export const MOCK_THREAD_ID = "00000000-0000-0000-0000-000000000001";
export const MOCK_THREAD_ID_2 = "00000000-0000-0000-0000-000000000002";
export const MOCK_RUN_ID = "00000000-0000-0000-0000-000000000099";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MockThread = {
  thread_id: string;
  title?: string;
  updated_at?: string;
  agent_name?: string;
  messages?: unknown[];
  artifacts?: string[];
};

export type MockAgent = {
  name: string;
  description?: string;
  system_prompt?: string;
};

export type MockArtifact = {
  body: string;
  contentType?: string;
  headers?: Record<string, string>;
};

export type MockAPIOptions = {
  threads?: MockThread[];
  agents?: MockAgent[];
  artifacts?: Record<string, MockArtifact>;
};

function normalizeArtifactPath(filepath: string) {
  return filepath.startsWith("/") ? filepath : `/${filepath}`;
}

function contentTypeOfArtifact(filepath: string) {
  if (filepath.endsWith(".json")) {
    return "application/json";
  }
  if (filepath.endsWith(".svg")) {
    return "image/svg+xml";
  }
  if (filepath.endsWith(".md") || filepath.endsWith(".txt")) {
    return "text/plain; charset=utf-8";
  }
  return "application/octet-stream";
}

function artifactPathFromMockURL(url: string) {
  const pathname = new URL(url).pathname;
  const marker = "/artifacts/";
  const markerIndex = pathname.indexOf(marker);
  if (markerIndex < 0) {
    return null;
  }
  return normalizeArtifactPath(
    decodeURIComponent(pathname.slice(markerIndex + marker.length)),
  );
}

// ---------------------------------------------------------------------------
// mockLangGraphAPI
// ---------------------------------------------------------------------------

/**
 * Mock all LangGraph API endpoints that the frontend calls on page load and
 * during message sending.  Without these mocks the pages would hang waiting
 * for a real backend.
 */
export function mockLangGraphAPI(page: Page, options?: MockAPIOptions) {
  const threads = options?.threads ?? [];
  const agents = options?.agents ?? [];
  const artifacts = options?.artifacts ?? {};

  // Thread search — sidebar thread list & chats list page
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/search$/,
    (route) => {
      const body = threads.map((t) => ({
        thread_id: t.thread_id,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: t.updated_at ?? "2025-01-01T00:00:00Z",
        metadata: t.agent_name ? { agent_name: t.agent_name } : {},
        status: "idle",
        values: { title: t.title ?? "Untitled" },
      }));
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    },
  );

  // Thread create — called when user sends first message in a new chat
  void page.route(/\/(?:api\/langgraph|mock\/api)\/threads$/, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: MOCK_THREAD_ID,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: {},
          status: "idle",
          values: {},
        }),
      });
    }
    return route.fallback();
  });

  // Thread update (PATCH) — metadata update after creation
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/[^/]+$/,
    (route) => {
      if (route.request().method() === "PATCH") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ thread_id: MOCK_THREAD_ID }),
        });
      }
      return route.fallback();
    },
  );

  // Thread history — useStream fetches state history on mount
  void page.route("**/api/langgraph/threads/*/history", (route) => {
    const url = route.request().url();

    // For threads that exist in our mock data, return history with messages
    const matchingThread = threads.find((t) => url.includes(t.thread_id));
    if (matchingThread) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            values: {
              title: matchingThread.title ?? "Untitled",
              messages: matchingThread.messages ?? [
                {
                  type: "human",
                  id: `msg-human-${matchingThread.thread_id}`,
                  content: [{ type: "text", text: "Previous question" }],
                },
                {
                  type: "ai",
                  id: `msg-ai-${matchingThread.thread_id}`,
                  content: `Response in thread ${matchingThread.title ?? matchingThread.thread_id}`,
                },
              ],
              artifacts: matchingThread.artifacts ?? [],
            },
            next: [],
            metadata: {},
            created_at: "2025-01-01T00:00:00Z",
            parent_config: null,
          },
        ]),
      });
    }

    // New threads — empty history
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "[]",
    });
  });

  // Thread state — getState for individual thread
  void page.route("**/api/langgraph/threads/*/state", (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const matchingThread = threads.find((t) => url.includes(t.thread_id));
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          values: {
            title: matchingThread?.title ?? "Untitled",
            messages: matchingThread
              ? (matchingThread.messages ?? [
                  {
                    type: "human",
                    id: `msg-human-${matchingThread.thread_id}`,
                    content: [{ type: "text", text: "Previous question" }],
                  },
                  {
                    type: "ai",
                    id: `msg-ai-${matchingThread.thread_id}`,
                    content: `Response in thread ${matchingThread.title ?? matchingThread.thread_id}`,
                  },
                ])
              : [],
            artifacts: matchingThread?.artifacts ?? [],
          },
          next: [],
          metadata: {},
          created_at: "2025-01-01T00:00:00Z",
        }),
      });
    }
    return route.fallback();
  });

  // The URL carries a query string (e.g. `?limit=10&offset=0`), which Playwright
  // glob `*` does NOT cross, so we match with a regex anchored to `/runs`
  // followed by `?` or end-of-string.  This must NOT match `/runs/stream`.
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/[^/]+\/runs(\?|$)/,
    (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "[]",
        });
      }
      return route.fallback();
    },
  );

  void page.route(
    /\/api\/threads\/([^/]+)\/runs\/([^/]+)\/messages/,
    (route) => {
      if (route.request().method() === "GET") {
        const url = route.request().url();
        const matchingThread = threads.find((t) =>
          url.includes(`/api/threads/${t.thread_id}/runs/`),
        );
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: (matchingThread?.messages ?? []).map((message, index) => ({
              run_id: `run-${matchingThread?.thread_id ?? "unknown"}`,
              content: message,
              metadata: { caller: "lead_agent" },
              created_at: `2025-01-01T00:00:${String(index).padStart(2, "0")}Z`,
            })),
            hasMore: false,
          }),
        });
      }
      return route.fallback();
    },
  );

  // Run stream — returns a minimal SSE response with an AI message
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/runs\/stream$/,
    handleRunStream,
  );
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/[^/]+\/runs\/stream$/,
    handleRunStream,
  );

  // Mock-mode artifact content — mirrors /mock/api/threads/:id/artifacts/*
  // without shadowing Next.js demo fixtures that are not explicitly provided.
  void page.route(/\/mock\/api\/threads\/[^/]+\/artifacts\//, (route) => {
    const url = route.request().url();
    const artifactPath = artifactPathFromMockURL(url);
    const artifact = artifactPath ? artifacts[artifactPath] : undefined;
    if (!artifact || !artifactPath) {
      return route.fallback();
    }

    const requestURL = new URL(url);
    const headers = {
      ...(artifact.headers ?? {}),
    };
    if (requestURL.searchParams.get("download") === "true") {
      headers["Content-Disposition"] =
        `attachment; filename="${artifactPath.split("/").at(-1) ?? "artifact"}"`;
    }

    return route.fulfill({
      status: 200,
      contentType: artifact.contentType ?? contentTypeOfArtifact(artifactPath),
      headers,
      body: artifact.body,
    });
  });

  // Models list — model picker dropdown
  void page.route("**/api/models", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          models: [],
          token_usage: { enabled: false },
        }),
      });
    }
    return route.fallback();
  });

  // Follow-up suggestions — input box auto-suggest after AI response
  void page.route("**/api/threads/*/suggestions", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ suggestions: [] }),
      });
    }
    return route.fallback();
  });

  // Agents list — sidebar & gallery page
  void page.route("**/api/agents", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ agents }),
      });
    }
    return route.fallback();
  });

  // Individual agent — agent chat page
  void page.route("**/api/agents/*", (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const agent = agents.find((a) => url.endsWith(`/api/agents/${a.name}`));
      if (agent) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(agent),
        });
      }
    }
    return route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Agent not found" }),
    });
  });
}

// ---------------------------------------------------------------------------
// handleRunStream
// ---------------------------------------------------------------------------

/**
 * Build a minimal SSE stream that the LangGraph SDK can parse.
 * The stream returns a single AI message: "Hello from DeerFlow!".
 */
export function handleRunStream(route: Route) {
  const events = [
    {
      event: "metadata",
      data: { run_id: MOCK_RUN_ID, thread_id: MOCK_THREAD_ID },
    },
    {
      event: "values",
      data: {
        messages: [
          {
            type: "human",
            id: "msg-human-1",
            content: [{ type: "text", text: "Hello" }],
          },
          {
            type: "ai",
            id: "msg-ai-1",
            content: "Hello from DeerFlow!",
          },
        ],
      },
    },
    { event: "end", data: {} },
  ];

  const body = events
    .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
    .join("");

  return route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body,
  });
}
