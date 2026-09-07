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
export const MOCK_SIDECAR_THREAD_ID = "00000000-0000-0000-0000-000000000002";
export const THREAD_PINNED_METADATA_KEY = "deerflow_pinned";
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
  metadata?: Record<string, unknown>;
};

export type MockAgent = {
  name: string;
  description?: string;
  system_prompt?: string;
  model?: string | null;
  tool_groups?: string[] | null;
  skills?: string[] | null;
  soul?: string | null;
  read_only?: boolean;
};

export type MockArtifact = {
  body: string;
  contentType?: string;
  headers?: Record<string, string>;
};

export type MockWorkflow = {
  name: string;
  description?: string;
  version?: string;
  yaml_content?: string;
  steps?: {
    id: string;
    type: string;
    action?: { kind: string; name: string; params?: Record<string, unknown> };
    agent?: string;
    prompt?: string;
  }[];
  nodes?: {
    id: string;
    type: string;
    action?: { kind: string; name: string; params?: Record<string, unknown> };
    agent?: string;
    prompt?: string;
  }[];
  edges?: { from: string; to: string }[];
  inputs?: Record<
    string,
    {
      type: string;
      required?: boolean;
      default?: unknown;
      description?: string;
    }
  >;
};

export type MockSkill = {
  name: string;
  description?: string;
  category: "public" | "custom";
  license?: string | null;
  enabled: boolean;
};

const DEFAULT_SKILLS: MockSkill[] = [
  {
    name: "data-analysis",
    description: "Analyze structured data and produce charts.",
    category: "public",
    enabled: true,
  },
  {
    name: "frontend-design",
    description: "Create polished frontend interfaces.",
    category: "public",
    enabled: true,
  },
  {
    name: "disabled-skill",
    description: "Hidden from slash autocomplete.",
    category: "public",
    enabled: false,
  },
];

// Latest goal set through the mock `/goal` endpoint. Module scope so the
// run-stream builder can re-emit it in thread values.
let latestGoal: unknown = null;

export type MockUser = {
  id: string;
  username: string;
  email?: string;
  department_id?: string | null;
  department_name?: string;
  role: string;
  disabled?: boolean;
  created_at?: string;
  last_login?: string;
};

export type MockDepartment = {
  id: string;
  name: string;
  description?: string;
  member_count?: number;
  agent_count?: number;
  skill_count?: number;
  created_at?: string;
};

export type MockTool = {
  name: string;
  group?: string;
  description?: string;
  requires_network?: boolean;
};

export type MockMemory = {
  version: string;
  lastUpdated: string;
  user: {
    workContext: { summary: string; updatedAt: string };
    personalContext: { summary: string; updatedAt: string };
    topOfMind: { summary: string; updatedAt: string };
  };
  history: {
    recentMonths: { summary: string; updatedAt: string };
    earlierContext: { summary: string; updatedAt: string };
    longTermBackground: { summary: string; updatedAt: string };
  };
  facts: {
    id: string;
    content: string;
    category: string;
    confidence: number;
    createdAt: string;
    source: string;
  }[];
};

export const DEFAULT_MOCK_MEMORY: MockMemory = {
  version: "1.0",
  lastUpdated: "2025-06-15T00:00:00Z",
  user: {
    workContext: {
      summary: "E2E test user context",
      updatedAt: "2025-06-15T00:00:00Z",
    },
    personalContext: {
      summary: "E2E test personal context",
      updatedAt: "2025-06-15T00:00:00Z",
    },
    topOfMind: {
      summary: "E2E test top of mind",
      updatedAt: "2025-06-15T00:00:00Z",
    },
  },
  history: {
    recentMonths: {
      summary: "Recent months context",
      updatedAt: "2025-06-15T00:00:00Z",
    },
    earlierContext: {
      summary: "Earlier context",
      updatedAt: "2025-06-15T00:00:00Z",
    },
    longTermBackground: {
      summary: "Long term background",
      updatedAt: "2025-06-15T00:00:00Z",
    },
  },
  facts: [
    {
      id: "fact-1",
      content: "Test memory fact for E2E",
      category: "context",
      confidence: 0.9,
      createdAt: "2025-06-15T00:00:00Z",
      source: "manual",
    },
  ],
};

export type MockAuditLog = {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
};

export type MockMCPConfig = {
  mcp_servers: Record<
    string,
    {
      enabled: boolean;
      type: "stdio" | "sse" | "http";
      command?: string;
      args?: string[];
      env?: Record<string, string>;
      url?: string;
      headers?: Record<string, string>;
      description: string;
    }
  >;
};

export type MockWorkflowRun = {
  run_id: string;
  workflow: string;
  status: string;
  definition_version?: number;
  error?: string | null;
  steps?: Record<
    string,
    {
      status: string;
      output?: unknown;
      error?: string | null;
      retries?: number;
      started_at?: string | null;
      finished_at?: string | null;
    }
  >;
  action_tokens?: Record<string, string>;
  action_progress?: Record<string, unknown>;
  events?: Array<{
    seq: number;
    type: string;
    payload: Record<string, unknown>;
  }>;
  artifacts?: Array<{ path: string; size: number }>;
  artifactContents?: Record<string, string>;
  record?: { md?: string; jsonl?: string };
};

export type MockScheduledTask = {
  id: string;
  thread_id: string;
  title: string;
  prompt: string;
  schedule_type: "cron" | "interval" | "once";
  schedule_spec: {
    cron?: string;
    interval_seconds?: number;
    at?: string;
  } & Record<string, unknown>;
  timezone: string;
  status: "enabled" | "paused";
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_id: string | null;
  last_error: string | null;
  run_count: number;
  last_thread_id?: string | null;
  context_mode?: string;
  created_at: string;
  updated_at: string;
};

export type MockAPIOptions = {
  threads?: MockThread[];
  agents?: MockAgent[];
  artifacts?: Record<string, MockArtifact>;
  workflows?: MockWorkflow[];
  workflowRuns?: Record<string, MockWorkflowRun>;
  skills?: MockSkill[];
  users?: MockUser[];
  departments?: MockDepartment[];
  tools?: MockTool[];
  memory?: MockMemory;
  auditLogs?: MockAuditLog[];
  resources?: MockAdminResource[];
  mcpConfig?: MockMCPConfig;
  scheduledTasks?: MockScheduledTask[];
  features?: Record<string, boolean>;
  createdThreadMessages?: unknown[];
  runStreamHandler?: (route: Route) => unknown;
  systemRole?: string;
};

export type MockAdminResource = {
  id: string;
  resource_type: string;
  resource_type_label: string;
  resource_id: string;
  visibility: string;
  owner_id?: string | null;
  owner_username?: string | null;
  department_id?: string | null;
  lifecycle_status?: string | null;
  created_at?: string | null;
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
  const workflows = options?.workflows ?? [];
  const workflowRuns = options?.workflowRuns ?? {};
  const skills = options?.skills ?? DEFAULT_SKILLS;
  const users = options?.users ?? [];
  const departments = options?.departments ?? [];
  const tools = options?.tools ?? [];
  const memory = options?.memory ?? DEFAULT_MOCK_MEMORY;
  const auditLogs = options?.auditLogs ?? [];
  const runStreamHandler = options?.runStreamHandler;
  const createdThreadMessages = options?.createdThreadMessages;
  const features = options?.features;
  const resources = options?.resources ?? [];
  const systemRole = options?.systemRole ?? "super_admin";
  const mcpConfig = options?.mcpConfig ?? { mcp_servers: {} };
  const scheduledTasks = options?.scheduledTasks ?? [];

  // ── Auth endpoints (defense-in-depth for IDEER_AUTH_DISABLED mode) ──

  void page.route("**/api/v1/auth/me**", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "e2e-user",
          email: "e2e@test.local",
          system_role: systemRole,
          needs_setup: false,
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/v1/auth/setup-status**", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ needs_setup: false }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/v1/auth/logout**", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      });
    }
    return route.fallback();
  });

  // Threads created at runtime (e.g. sidecar threads via the gateway create)
  // join thread search results without shadowing a seeded thread with the
  // same id, whose content other assertions may still navigate to.
  const createdThreads: MockThread[] = [];

  // Thread search — sidebar thread list & chats list page
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/search$/,
    (route) => {
      // Honor the limit/offset pagination contract of POST /threads/search so
      // useInfiniteThreads actually pages (a full dump would make the first
      // page contain every thread and the second fetch a no-op).
      const request = route.request().postDataJSON() as {
        limit?: number;
        offset?: number;
      } | null;
      const offset = Math.max(0, request?.offset ?? 0);
      const limit =
        request?.limit === undefined
          ? threads.length
          : Math.max(0, request.limit);
      // The gateway keeps pinned threads in the first page regardless of
      // recency, so the mock sorts them before slicing. Threads created at
      // runtime (e.g. sidecar threads) join the seeded pool for search.
      const allThreads = [...threads, ...createdThreads];
      const isPinned = (t: (typeof allThreads)[number]) =>
        t.metadata?.[THREAD_PINNED_METADATA_KEY] === true;
      const orderedThreads = [...allThreads].sort(
        (a, b) =>
          Number(isPinned(b)) - Number(isPinned(a)) ||
          Date.parse(b.updated_at ?? "0") - Date.parse(a.updated_at ?? "0"),
      );
      const body = orderedThreads.slice(offset, offset + limit).map((t) => ({
        thread_id: t.thread_id,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: t.updated_at ?? "2025-01-01T00:00:00Z",
        metadata: {
          ...(t.metadata ?? {}),
          ...(t.agent_name ? { agent_name: t.agent_name } : {}),
        },
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

  // Gateway thread create — used by the sidecar flow (POST /api/threads with
  // deerflow_sidecar metadata). Responds with the deterministic sidecar id so
  // specs can route the sidecar thread's state/history/stream endpoints.
  void page.route("**/api/threads", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    const body = route.request().postDataJSON() as {
      metadata?: Record<string, unknown>;
    } | null;
    const created: MockThread = {
      thread_id: MOCK_SIDECAR_THREAD_ID,
      title: "Side chat",
      updated_at: new Date().toISOString(),
      metadata: body?.metadata ?? {},
      messages: [],
    };
    createdThreads.push(created);
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: created.thread_id,
        created_at: new Date().toISOString(),
        updated_at: created.updated_at,
        metadata: created.metadata,
        status: "idle",
        values: { title: created.title },
      }),
    });
  });

  // Thread update (PATCH) — metadata update after creation.
  // The metadata patch must be written back into the seeded thread so a
  // refetch (the pin mutation invalidates the thread queries) still sees it.
  void page.route(/\/threads\/([^/]+)$/, (route) => {
    if (route.request().method() === "GET") {
      const url = new URL(route.request().url());
      const threadId = decodeURIComponent(url.pathname.split("/").pop() ?? "");
      const seeded = threads.find((t) => t.thread_id === threadId);
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: threadId,
          created_at: "2025-01-01T00:00:00Z",
          updated_at: seeded?.updated_at ?? "2025-01-01T00:00:00Z",
          metadata: seeded?.metadata ?? {},
          status: "idle",
          values: { title: seeded?.title ?? "Untitled" },
        }),
      });
    }
    if (route.request().method() === "PATCH") {
      const url = new URL(route.request().url());
      const threadId = decodeURIComponent(url.pathname.split("/").pop() ?? "");
      const body = route.request().postDataJSON() as {
        metadata?: Record<string, unknown>;
      } | null;
      const seeded = threads.find((t) => t.thread_id === threadId);
      if (seeded) {
        seeded.metadata = {
          ...(seeded.metadata ?? {}),
          ...(body?.metadata ?? {}),
        };
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: threadId,
          metadata: { ...(seeded?.metadata ?? {}), ...(body?.metadata ?? {}) },
        }),
      });
    }
    if (route.request().method() === "DELETE") {
      const url = new URL(route.request().url());
      const threadId = decodeURIComponent(url.pathname.split("/").pop() ?? "");
      // Mirror the gateway's `require_existing=True` ownership guard: deleting
      // an already-removed thread 404s. `useDeleteThread` first deletes via the
      // LangGraph route (which drops the thread_meta row) and then hits the
      // gateway route, so this reproduces the real double-delete 404 the
      // frontend must treat as idempotent success.
      const index = threads.findIndex((t) => t.thread_id === threadId);
      if (index < 0) {
        return route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: `Thread ${threadId} not found` }),
        });
      }
      threads.splice(index, 1);
      return route.fulfill({ status: 204 });
    }
    return route.fallback();
  });

  // Branch from turn — creates a child thread that copies the parent's
  // messages and links it through branch metadata, mirroring the gateway's
  // POST /threads/{id}/branches so the sidebar renders the branch lineage.
  void page.route(/\/api\/threads\/([^/]+)\/branches$/, (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    const url = new URL(route.request().url());
    const threadId = decodeURIComponent(url.pathname.split("/")[3] ?? "");
    const parent = threads.find((t) => t.thread_id === threadId);
    const body = route.request().postDataJSON() as {
      message_id?: string;
      message_ids?: string[];
    } | null;
    const branchedFromMessageId = body?.message_id ?? "";
    const branchThreadId = MOCK_THREAD_ID_2;
    if (!threads.some((t) => t.thread_id === branchThreadId)) {
      threads.push({
        thread_id: branchThreadId,
        title: `${parent?.title ?? "Untitled"} (2)`,
        updated_at: new Date().toISOString(),
        metadata: {
          deerflow_branch: true,
          branch_parent_thread_id: threadId,
          branched_from_message_id: branchedFromMessageId,
        },
        messages: parent?.messages ?? [],
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: branchThreadId,
        parent_thread_id: threadId,
        parent_checkpoint_id: "mock-checkpoint",
        branched_from_message_id: branchedFromMessageId,
        workspace_clone_mode: "none",
      }),
    });
  });

  // Thread history — useStream fetches state history on mount
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/[^/]+\/history$/,
    (route) => {
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
    },
  );

  // Thread state — getState for individual thread; POST is updateState
  // (e.g. the rename flow) and must write the new values back into the seed
  // so post-invalidation refetches observe them.
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/([^/]+)\/state$/,
    (route) => {
      if (route.request().method() === "POST") {
        const url = new URL(route.request().url());
        const threadId = decodeURIComponent(
          url.pathname.split("/").at(-2) ?? "",
        );
        const body = route.request().postDataJSON() as {
          values?: { title?: string };
        } | null;
        const seeded = threads.find((t) => t.thread_id === threadId);
        if (seeded && body?.values?.title) {
          seeded.title = body.values.title;
        }
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ values: body?.values ?? {} }),
        });
      }
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
    },
  );

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
        if (!matchingThread && createdThreadMessages) {
          // Messages of a thread created earlier in the same spec run.
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              data: createdThreadMessages.map((message, index) => ({
                run_id: "run-created-thread",
                content: message,
                metadata: { caller: "lead_agent" },
                created_at: `2025-01-01T00:00:${String(index).padStart(2, "0")}Z`,
              })),
              hasMore: false,
            }),
          });
        }
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

  // Scheduled tasks — sidebar link + scheduled-tasks page reads these.
  const scheduledTasksState = [...scheduledTasks];
  void page.route("**/api/scheduled-tasks**", (route) => {
    const method = route.request().method();
    const url = route.request().url();
    if (method === "GET" && !/scheduled-tasks\/[^/?]+\//.test(url)) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(scheduledTasksState),
      });
    }
    if (
      method === "POST" &&
      !/scheduled-tasks\/[^/?]+\/(pause|resume|trigger)/.test(url)
    ) {
      const body =
        (route.request().postDataJSON() as Record<string, unknown> | null) ??
        {};
      const created: MockScheduledTask = {
        id: `created-${scheduledTasksState.length + 1}`,
        thread_id: (body.thread_id as string) ?? MOCK_THREAD_ID,
        title: (body.title as string) ?? "",
        prompt: (body.prompt as string) ?? "",
        schedule_type:
          (body.schedule_type as MockScheduledTask["schedule_type"]) ?? "once",
        schedule_spec:
          (body.schedule_spec as MockScheduledTask["schedule_spec"]) ?? {},
        timezone: (body.timezone as string) ?? "UTC",
        status: "enabled",
        next_run_at: null,
        last_run_at: null,
        last_run_id: null,
        last_thread_id: null,
        last_error: null,
        run_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      scheduledTasksState.push(created);
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(created),
      });
    }
    return route.fallback();
  });
  void page.route("**/api/scheduled-tasks/*", (route) => {
    const method = route.request().method();
    const url = route.request().url();
    const taskId = /scheduled-tasks\/([^/?]+)/.exec(url)?.[1];
    const task = scheduledTasksState.find((t) => t.id === taskId);
    if (method === "PATCH" && task) {
      const patch =
        (route.request().postDataJSON() as Record<string, unknown> | null) ??
        {};
      Object.assign(task, patch, { updated_at: new Date().toISOString() });
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(task),
      });
    }
    if (method === "DELETE" && task) {
      scheduledTasksState.splice(scheduledTasksState.indexOf(task), 1);
      return route.fulfill({ status: 204 });
    }
    return route.fallback();
  });
  for (const action of ["pause", "resume", "trigger"] as const) {
    void page.route(`**/api/scheduled-tasks/*/${action}`, (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      const url = route.request().url();
      const taskId = /scheduled-tasks\/([^/?]+)\//.exec(url)?.[1];
      const task = scheduledTasksState.find((t) => t.id === taskId);
      if (!task) return route.fulfill({ status: 404 });
      if (action === "pause") task.status = "paused";
      if (action === "resume") task.status = "enabled";
      if (action === "trigger") {
        task.last_run_at = new Date().toISOString();
        task.run_count += 1;
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(task),
      });
    });
  }
  void page.route("**/api/scheduled-tasks/*/runs**", (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const taskId = /scheduled-tasks\/([^/?]+)\/runs/.exec(url)?.[1];
      const task = scheduledTasksState.find((t) => t.id === taskId);
      const runs = task?.last_run_at
        ? [
            {
              id: `run-${task.id}`,
              task_id: task.id,
              thread_id: task.thread_id,
              status: "success",
              trigger: "manual",
              started_at: task.last_run_at,
              finished_at: task.last_run_at,
              error: null,
            },
          ]
        : [];
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(runs),
      });
    }
    return route.fallback();
  });
  // Goal continuation state — `/goal <objective>` stores a per-thread goal.
  // The run stream re-emits it in thread values (useStream drops the local
  // optimistic override once the thread is created).
  const threadGoals: Record<string, { goal: unknown } | { goal: null }> = {};
  void page.route("**/api/threads/*/goal", (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const threadId = url.pathname.split("/")[4] ?? "";
    if (request.method() === "PUT") {
      const body = request.postDataJSON() as { objective?: string };
      latestGoal = {
        objective: body.objective ?? "",
        status: "active",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        continuation_count: 0,
        max_continuations: 3,
        no_progress_count: 0,
        max_no_progress_continuations: 2,
      };
      threadGoals[threadId] = { goal: latestGoal };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(threadGoals[threadId]),
      });
    }
    if (request.method() === "DELETE") {
      latestGoal = null;
      threadGoals[threadId] = { goal: null };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ goal: null }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(threadGoals[threadId] ?? { goal: null }),
    });
  });
  // Gateway-enforced upload limits surface on the attachment tooltip.
  void page.route("**/api/threads/*/uploads/limits", (route) => {
    if (route.request().method() !== "GET") {
      return route.fallback();
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        max_files: 10,
        max_file_size: 50 * 1024 * 1024,
        max_total_size: 100 * 1024 * 1024,
      }),
    });
  });

  // ── Lark / Feishu CLI integration ───────────────────────────
  // Mirrors the gateway contract: status probes, skill-pack install, app
  // configuration (config/start + config/complete), and user authorization
  // (auth/start + auth/complete). Generation values round-trip so the UI's
  // generation-chaining assertions observe a realistic handshake.
  let larkIntegrationStatus = {
    installed: false,
    version: "v1.0.65",
    manifest_version: null as string | null,
    latest_available_version: "v1.0.65" as string | null,
    runtime_version_mismatch: false,
    app_configured: false,
    app_id: null as string | null,
    app_brand: null as string | null,
    skills_expected: 27,
    skills_installed: 0,
    installed_skills: [] as string[],
    enabled_skills: [] as string[],
    install_path: "/tmp/deer-flow/integrations/skills/lark-cli",
    cli: {
      available: false,
      path: null as string | null,
      version: null as string | null,
      error: "lark-cli is not on PATH" as string | null,
    },
    auth: {
      status: "unavailable",
      message: "lark-cli is not installed on the Gateway" as string | null,
      user: null as string | null,
      verified: false,
    },
    sandbox_runtime_mode: "none" as
      | "none"
      | "gateway-download"
      | "init-container",
    sandbox_runtime_ready: false,
    sandbox_runtime_detail: null as string | null,
  };
  void page.route("**/api/integrations/lark/status", (route) => {
    if (route.request().method() !== "GET") {
      return route.fallback();
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(larkIntegrationStatus),
    });
  });
  void page.route("**/api/integrations/lark/install", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    larkIntegrationStatus = {
      ...larkIntegrationStatus,
      installed: true,
      manifest_version: "v1.0.65",
      skills_installed: 3,
      installed_skills: ["lark-doc", "lark-im", "lark-shared"],
      enabled_skills: ["lark-doc", "lark-im", "lark-shared"],
      cli: {
        available: true,
        path: "/usr/bin/lark-cli",
        version: "lark-cli version v1.0.65",
        error: null,
      },
      auth: {
        status: "not_configured",
        message: "Lark app is not configured",
        user: null,
        verified: false,
      },
      sandbox_runtime_mode: "init-container",
      sandbox_runtime_ready: true,
      sandbox_runtime_detail: null,
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        installed_skills: ["lark-doc", "lark-im", "lark-shared"],
        message: "Installed 3 Lark/Feishu skills.",
        status: larkIntegrationStatus,
      }),
    });
  });
  void page.route("**/api/integrations/lark/config/start", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        verification_url: "https://open.feishu.cn/page/cli?user_code=config",
        device_code: "mock-config-device-code",
        generation: "config-generation",
        expires_in: 600,
        interval: 5,
        user_code: "config",
        brand: "feishu",
      }),
    });
  });
  void page.route("**/api/integrations/lark/config/complete", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    const body = route.request().postDataJSON() as { generation?: string };
    larkIntegrationStatus = {
      ...larkIntegrationStatus,
      app_configured: true,
      app_id: "cli_mock",
      app_brand: "feishu",
      auth: {
        status: "not_authorized",
        message: "Lark user authorization is not configured",
        user: null,
        verified: false,
      },
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        message: "Lark/Feishu connection setup completed.",
        generation: body.generation ?? "config-generation",
        status: larkIntegrationStatus,
      }),
    });
  });
  void page.route("**/api/integrations/lark/auth/start", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    const body = route.request().postDataJSON() as { generation?: string };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        verification_url: "https://open.feishu.cn/auth/mock-device",
        device_code: "mock-device-code",
        generation: body.generation ?? "auth-generation",
        expires_in: 600,
        user_code: null,
        hint: null,
      }),
    });
  });
  void page.route("**/api/integrations/lark/auth/complete", (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    const body = route.request().postDataJSON() as { generation?: string };
    larkIntegrationStatus = {
      ...larkIntegrationStatus,
      auth: {
        status: "authenticated",
        message: "Lark/Feishu authorization is live-verified.",
        user: "Alice",
        verified: true,
      },
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        message: "Lark/Feishu authorization completed.",
        generation: body.generation ?? "auth-generation",
        status: larkIntegrationStatus,
      }),
    });
  });
  void page.route("**/api/threads/*/scheduled-tasks**", (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const threadId = /threads\/([^/]+)\/scheduled-tasks/.exec(url)?.[1] ?? "";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          scheduledTasks.filter((t) => t.thread_id === threadId),
        ),
      });
    }
    return route.fallback();
  });

  // Feature flags — capability center reads these on load. Default enables
  // the runtime features the workspace UI expects (mcp tasks, browser control).
  // Specs may pass either the flat flags (mcpTasksEnabled) or the gateway's
  // nested shape (mcp_tasks.enabled); normalize to the nested wire format.
  const flat = features ?? {};
  const effectiveFeatures = {
    mcp_tasks: { enabled: flat.mcpTasksEnabled ?? true },
    browser_control: { enabled: flat.browserControlEnabled ?? false },
    agents_api: { enabled: flat.agentsApiEnabled ?? true },
    ...((flat as Record<string, unknown>).mcp_tasks
      ? { mcp_tasks: (flat as Record<string, unknown>).mcp_tasks }
      : {}),
  };
  void page.route("**/api/features", (route) => {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(effectiveFeatures),
    });
  });

  // Run stream — returns a minimal SSE response with an AI message. A spec
  // can take over the stream entirely via `runStreamHandler` (e.g. proxying
  // to a mock stream server).
  const runStreamRoute = (route: Route) => {
    if (runStreamHandler) {
      return runStreamHandler(route);
    }
    return handleRunStream(route);
  };
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/runs\/stream$/,
    runStreamRoute,
  );
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/[^/]+\/runs\/stream$/,
    runStreamRoute,
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

  // ── Canonical catalog ──────────────────────────────────────────

  const canonicalResourceOf = (
    type: "agent" | "workflow" | "skill",
    item: { name: string },
    canModify = true,
  ) => ({
    id: `00000000-0000-0000-0000-${`${type}-${item.name}`.slice(-12).padStart(12, "0")}`,
    type,
    slug: item.name,
    display_name: item.name,
    owner_id: "e2e-user",
    visibility: "public",
    scope_department_id: null,
    latest_version: 1,
    draft_revision: 1,
    system_owned: false,
    can_modify: canModify,
  });

  const canonicalPublished = (
    type: "agent" | "workflow" | "skill",
    resource: ReturnType<typeof canonicalResourceOf>,
  ) => {
    if (type === "workflow") {
      const wf = workflows.find((w) => w.name === resource.slug);
      const nodes = wf?.nodes ??
        wf?.steps ?? [
          {
            id: "start",
            type: "action",
            action: { kind: "agent", name: "my-agent", params: { prompt: "" } },
          },
        ];
      return {
        resource,
        version: { version: 1 },
        content: {
          schema_version: 2,
          name: resource.slug,
          description: wf?.description ?? "",
          inputs: wf?.inputs ?? {},
          state: {},
          entrypoint: "start",
          nodes,
          edges: wf?.edges ?? [],
        },
        yaml_content:
          wf?.yaml_content ??
          `schema_version: 2\nname: ${resource.slug}\ndescription: ""\ninputs: {}\nstate: {}\nentrypoint: start\nnodes:\n  - id: step1\n    type: action\n    action:\n      kind: run_workflow\n      name: ${resource.slug}\n      params: {}\n`,
      };
    }
    if (type === "agent") {
      const agent = agents.find((a) => a.name === resource.slug);
      return {
        resource,
        version: { version: 1 },
        content: {
          config: {
            description: agent?.description ?? "",
            model: agent?.model ?? null,
            // Preserve null: the gateway publishes unrestricted agents with
            // no tool_groups, and `[]` means "no groups allowed" downstream.
            tool_groups: agent?.tool_groups ?? null,
            skills: agent?.skills ?? [],
          },
          soul: agent?.soul ?? agent?.system_prompt ?? "",
        },
      };
    }
    return { resource, version: { version: 1 }, content: {} };
  };

  // Canonical catalog list — single source of truth for agents/workflows/skills
  void page.route(/\/api\/resources\?.*/, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (
      request.method() === "GET" &&
      url.pathname.endsWith("/api/resources") &&
      ["agent", "skill", "workflow"].includes(
        url.searchParams.get("type") ?? "",
      )
    ) {
      const type = url.searchParams.get("type") as
        | "agent"
        | "workflow"
        | "skill";
      const items =
        type === "agent"
          ? agents.map((a) => canonicalResourceOf("agent", a))
          : type === "workflow"
            ? workflows.map((w) => canonicalResourceOf("workflow", w))
            : skills.map((s) =>
                canonicalResourceOf("skill", s, s.category === "custom"),
              );
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items, total: items.length }),
      });
    }
    return route.fallback();
  });

  // Agent name check via deterministic alias endpoint
  void page.route(/\/api\/resources\/aliases\/agent\/[^/?]+/, (route) => {
    const url = new URL(route.request().url());
    const name = decodeURIComponent(url.pathname.split("/aliases/agent/")[1]!);
    const exists = agents.some((a) => a.name === name);
    return route.fulfill({
      status: exists ? 200 : 404,
      contentType: "application/json",
      body: exists
        ? JSON.stringify(
            canonicalResourceOf("agent", agents.find((a) => a.name === name)!),
          )
        : JSON.stringify({ detail: "Alias not found" }),
    });
  });

  // Published canonical detail (agent / workflow)
  void page.route(/\/api\/resources\/[^/?]+\/published/, (route) => {
    const url = new URL(route.request().url());
    const id = url.pathname.split("/api/resources/")[1]!.split("/")[0]!;
    const agent =
      agents.find((a) => canonicalResourceOf("agent", a).id === id) ??
      agents.find((a) => a.name === id);
    const wf =
      workflows.find((w) => canonicalResourceOf("workflow", w).id === id) ??
      workflows.find((w) => w.name === id);
    if (agent) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          canonicalPublished("agent", canonicalResourceOf("agent", agent)),
        ),
      });
    }
    if (wf) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          canonicalPublished("workflow", canonicalResourceOf("workflow", wf)),
        ),
      });
    }
    // Fallback: unknown name/id resolves to a default workflow detail
    // (mirrors the legacy mock's "empty list falls back to valid v2 detail")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        canonicalPublished(
          "workflow",
          canonicalResourceOf("workflow", { name: id }),
        ),
      ),
    });
  });

  // Canonical resource creation (agents / workflows / skills)
  void page.route("**/api/resources", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON() as {
      type: string;
      slug?: string;
    };
    const name = body.slug ?? body.type;
    const resource = canonicalResourceOf(
      (["agent", "workflow", "skill"].includes(body.type)
        ? body.type
        : "workflow") as "agent" | "workflow" | "skill",
      { name },
    );
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(resource),
    });
  });

  // Agent draft / publish / archive / favorite / export / import
  void page.route("**/api/resources/import/agent", (route) => {
    if (route.request().method() === "POST") {
      const name = "imported-agent";
      const resource = canonicalResourceOf("agent", { name });
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(resource),
      });
    }
    return route.fallback();
  });

  void page.route(/\/api\/resources\/[^/?]+\/export/, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/zip",
        headers: {
          "Content-Disposition": 'attachment; filename="agent.zip"',
        },
        body: Buffer.from("fake-zip-content"),
      });
    }
    return route.fallback();
  });

  void page.route(/\/api\/resources\/[^/?]+\/agent-draft/, (route) => {
    if (route.request().method() === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ revision: 2 }),
      });
    }
    return route.fallback();
  });

  void page.route(/\/api\/resources\/[^/?]+\/workflow-draft/, (route) => {
    if (route.request().method() === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ revision: 2 }),
      });
    }
    return route.fallback();
  });

  void page.route(/\/api\/resources\/[^/?]+\/publish/, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: 1 }),
      });
    }
    return route.fallback();
  });

  void page.route(/\/api\/resources\/[^/?]+\/archive/, (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ lifecycle_status: "archived" }),
      });
    }
    return route.fallback();
  });

  void page.route(/\/api\/resources\/[^/?]+\/favorite/, (route) => {
    const method = route.request().method();
    if (method === "POST" || method === "DELETE") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          is_favorited: method === "POST",
        }),
      });
    }
    return route.fallback();
  });

  // Canonical workflow run operations
  void page.route(/\/api\/resources\/[^/?]+\/workflow-runs/, (route) => {
    const method = route.request().method();
    if (method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: MOCK_RUN_ID,
          status: "running",
          workflow: "test-workflow",
        }),
      });
    }
    if (method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          runs: Object.values(workflowRuns),
          total: Object.keys(workflowRuns).length,
          limit: 50,
          offset: 0,
        }),
      });
    }
    return route.fallback();
  });

  void page.route(
    /\/api\/resources\/[^/?]+\/workflow-runs\/[^/?]+/,
    (route) => {
      const method = route.request().method();
      const url = new URL(route.request().url());
      const runId = url.pathname.split("/workflow-runs/")[1]!.split("/")[0]!;
      const run = workflowRuns[runId];

      if (
        method === "GET" &&
        !url.pathname.includes("/artifacts") &&
        !url.pathname.includes("/record") &&
        !url.pathname.includes("/events") &&
        !url.pathname.includes("/commands")
      ) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            run ?? {
              run_id: MOCK_RUN_ID,
              workflow: "test-workflow",
              status: "completed",
              current_step: null,
              error: null,
              steps: {
                step1: {
                  status: "completed",
                  output: "done",
                  error: null,
                  retries: 0,
                  started_at: "2025-01-01T00:00:00Z",
                  finished_at: "2025-01-01T00:00:01Z",
                },
              },
            },
          ),
        });
      }
      return route.fallback();
    },
  );

  // Canonical run artifacts list
  void page.route(
    /\/api\/resources\/[^/?]+\/workflow-runs\/[^/?]+\/artifacts/,
    (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const url = new URL(route.request().url());
      const runId = url.pathname.split("/workflow-runs/")[1]!.split("/")[0]!;
      const run = workflowRuns[runId];
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: run?.run_id ?? MOCK_RUN_ID,
          workflow: run?.workflow ?? "test-workflow",
          artifacts: run?.artifacts ?? [],
        }),
      });
    },
  );

  // Canonical run artifact content
  void page.route(
    /\/api\/resources\/[^/?]+\/workflow-runs\/[^/?]+\/artifacts\/content\?/,
    (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const url = new URL(route.request().url());
      const runId = url.pathname.split("/workflow-runs/")[1]!.split("/")[0]!;
      const run = workflowRuns[runId];
      const path = url.searchParams.get("path") ?? "";
      const content = run?.artifactContents?.[path];
      return route.fulfill({
        status: 200,
        contentType: contentTypeOfArtifact(path),
        body: content ?? "",
      });
    },
  );

  // Canonical run record download
  void page.route(
    /\/api\/resources\/[^/?]+\/workflow-runs\/[^/?]+\/record/,
    (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const url = new URL(route.request().url());
      const runId = url.pathname.split("/workflow-runs/")[1]!.split("/")[0]!;
      const run = workflowRuns[runId];
      const format = url.searchParams.get("format") ?? "md";
      const record = run?.record?.[format as "md" | "jsonl"];
      return route.fulfill({
        status: 200,
        contentType:
          format === "jsonl"
            ? "application/x-ndjson"
            : "text/markdown; charset=utf-8",
        body: record ?? "",
      });
    },
  );

  // Canonical run events SSE stream
  void page.route(
    /\/api\/resources\/[^/?]+\/workflow-runs\/[^/?]+\/events/,
    (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      const url = new URL(route.request().url());
      const runId = url.pathname.split("/workflow-runs/")[1]!.split("/")[0]!;
      const run = workflowRuns[runId];
      const events = run?.events ?? [];
      const afterSeq = Number(url.searchParams.get("after_seq") ?? "0");
      const pending = events.filter((e) => e.seq > afterSeq);
      const body = pending
        .map(
          (e) =>
            `id: ${e.seq}\nevent: ${e.type}\ndata: ${JSON.stringify(e.payload)}\n\n`,
        )
        .join("");
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    },
  );

  // Canonical run commands (resume / cancel)
  void page.route(
    /\/api\/resources\/[^/?]+\/workflow-runs\/[^/?]+\/commands/,
    (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          command_id: "mock-command-id",
          run_id: MOCK_RUN_ID,
          accepted: true,
        }),
      });
    },
  );

  // ── Workflow CRUD + Run ─────────────────────────────────────────

  void page.route("**/api/workflows", (route) => {
    const method = route.request().method();
    if (method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ workflows, total: workflows.length }),
      });
    }
    if (method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: "new-workflow",
          description: "",
          version: "1.0",
          steps_count: 1,
          inputs: {},
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/workflows/*/runs/*", (route) => {
    const method = route.request().method();
    const url = route.request().url();
    const runId = url.split("/runs/")[1]?.split("?")[0];
    const run = runId ? workflowRuns[runId] : undefined;

    // Run status GET
    if (method === "GET" && url.includes("/runs/")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          run ?? {
            run_id: "mock-run-id",
            workflow: "test-workflow",
            status: "completed",
            current_step: null,
            error: null,
            steps: {
              step1: {
                status: "completed",
                output: "done",
                error: null,
                retries: 0,
                started_at: "2025-01-01T00:00:00Z",
                finished_at: "2025-01-01T00:00:01Z",
              },
            },
          },
        ),
      });
    }

    // Submit review
    if (method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, run_id: "mock-run-id" }),
      });
    }

    return route.fallback();
  });

  // Run artifacts list
  void page.route("**/api/workflows/*/runs/*/artifacts", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const runId = route.request().url().split("/runs/")[1]?.split("/")[0];
    const run = runId ? workflowRuns[runId] : undefined;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: run?.run_id ?? "mock-run-id",
        workflow: run?.workflow ?? "test-workflow",
        artifacts: run?.artifacts ?? [],
      }),
    });
  });

  // Run artifact content
  void page.route("**/api/workflows/*/runs/*/artifacts/content*", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const url = new URL(route.request().url());
    const runId = url.pathname.split("/runs/")[1]?.split("/")[0];
    const run = runId ? workflowRuns[runId] : undefined;
    const path = url.searchParams.get("path") ?? "";
    const content = run?.artifactContents?.[path];
    return route.fulfill({
      status: 200,
      contentType: contentTypeOfArtifact(path),
      body: content ?? "",
    });
  });

  // Run record download (jsonl / md)
  void page.route("**/api/workflows/*/runs/*/record*", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const url = new URL(route.request().url());
    const runId = url.pathname.split("/runs/")[1]?.split("/")[0];
    const run = runId ? workflowRuns[runId] : undefined;
    const format = url.searchParams.get("format") ?? "md";
    const record = run?.record?.[format as "md" | "jsonl"];
    return route.fulfill({
      status: 200,
      contentType:
        format === "jsonl"
          ? "application/x-ndjson"
          : "text/markdown; charset=utf-8",
      body: record ?? "",
    });
  });

  // Run events SSE stream (terminal events close the EventSource)
  void page.route("**/api/workflows/*/runs/*/events*", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const url = new URL(route.request().url());
    const runId = url.pathname.split("/runs/")[1]?.split("/")[0];
    const run = runId ? workflowRuns[runId] : undefined;
    const events = run?.events ?? [];
    const afterSeq = Number(url.searchParams.get("after_seq") ?? "0");
    const pending = events.filter((e) => e.seq > afterSeq);
    const body = pending
      .map(
        (e) =>
          `id: ${e.seq}\nevent: ${e.type}\ndata: ${JSON.stringify(e.payload)}\n\n`,
      )
      .join("");
    return route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body,
    });
  });

  // Workflow run commands (resume / cancel)
  void page.route("**/api/workflows/*/runs/*/commands", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        command_id: "mock-command-id",
        run_id: "mock-run-id",
        accepted: true,
      }),
    });
  });

  void page.route("**/api/workflows/*/run", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "mock-run-id",
          status: "running",
          workflow: "test-workflow",
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/workflows/*", (route) => {
    const method = route.request().method();
    const url = route.request().url();
    const wfName = url
      .split("/api/workflows/")[1]
      ?.split("/")[0]
      ?.split("?")[0];
    const wf = workflows.find((w) => w.name === wfName);

    if (method === "GET") {
      if (wf) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            name: wf.name,
            description: wf.description ?? "",
            version: wf.version ?? "1.0",
            yaml_content:
              wf.yaml_content ??
              `schema_version: 2\nname: ${wf.name}\ndescription: ""\ninputs: {}\nstate: {}\nentrypoint: start\nnodes:\n  - id: start\n    type: action\n    action:\n      kind: agent\n      name: my-agent\n      params:\n        prompt: ""\nedges: []`,
            nodes: wf.nodes ?? [
              {
                id: "start",
                type: "action",
                action: {
                  kind: "agent",
                  name: "my-agent",
                  params: { prompt: "" },
                },
              },
            ],
            steps: wf.nodes ?? [
              {
                id: "start",
                type: "action",
                action: {
                  kind: "agent",
                  name: "my-agent",
                  params: { prompt: "" },
                },
              },
            ],
            steps_count: (wf.nodes ?? []).length || 1,
            edges: wf.edges ?? [],
            inputs: wf.inputs ?? {},
          }),
        });
      }
      // Default workflow detail for any name
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: wfName ?? "workflow",
          description: "A workflow",
          version: "1.0",
          yaml_content: `schema_version: 2\nname: ${wfName ?? "workflow"}\ndescription: "A workflow"\ninputs: {}\nstate: {}\nentrypoint: start\nnodes:\n  - id: start\n    type: action\n    action:\n      kind: agent\n      name: test-agent\n      params:\n        prompt: "Hello"\nedges: []`,
          nodes: [
            {
              id: "start",
              type: "action",
              action: {
                kind: "agent",
                name: "test-agent",
                params: { prompt: "Hello" },
              },
            },
          ],
          steps: [
            {
              id: "start",
              type: "action",
              action: {
                kind: "agent",
                name: "test-agent",
                params: { prompt: "Hello" },
              },
            },
          ],
          steps_count: 1,
          edges: [],
          inputs: {},
        }),
      });
    }

    if (method === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: wfName ?? "workflow",
          description: "Updated",
          version: "1.0",
          steps_count: 1,
          inputs: {},
        }),
      });
    }

    if (method === "DELETE") {
      return route.fulfill({ status: 204 });
    }

    return route.fallback();
  });

  // ── Skills ──────────────────────────────────────────────────────

  void page.route("**/api/skills/install", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          skill_name: "installed-skill",
          message: "Skill installed successfully",
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/skills/*", (route) => {
    const method = route.request().method();
    if (method === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ name: "updated-skill", enabled: true }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/skills", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ skills }),
      });
    }
    return route.fallback();
  });

  // ── Admin ───────────────────────────────────────────────────────

  void page.route("**/api/admin/stats", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_users: users.length || 5,
          total_departments: departments.length || 2,
          total_agents: agents.length || 3,
          total_skills: skills.length || 10,
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/admin/users", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users,
          total: users.length,
          limit: 50,
          offset: 0,
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/admin/users/*", (route) => {
    const method = route.request().method();
    if (method === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          username: "updated-user",
          system_role: "user",
        }),
      });
    }
    if (method === "DELETE") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          user_id: "user-1",
          resource_strategy: "soft_delete",
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/admin/departments", (route) => {
    const method = route.request().method();
    if (method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ departments, total: departments.length }),
      });
    }
    if (method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "new-dept",
          name: "New Department",
          description: "",
          member_count: 0,
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/admin/departments/*", (route) => {
    const method = route.request().method();
    if (method === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "dept-1", name: "Updated Dept" }),
      });
    }
    if (method === "DELETE") {
      return route.fulfill({ status: 204 });
    }
    return route.fallback();
  });

  // ── Tools ───────────────────────────────────────────────────────

  void page.route("**/api/tools/*/test", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, output: "Test completed" }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/tools/*", (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const toolName = url.split("/api/tools/")[1]?.split("?")[0];
      const tool = tools.find((t) => t.name === toolName);
      if (tool) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(tool),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: toolName ?? "tool",
          description: "A tool",
          group: "default",
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/tools", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ tools, total: tools.length }),
      });
    }
    return route.fallback();
  });

  // ── Memory ─────────────────────────────────────────────────────

  void page.route("**/api/memory", (route) => {
    const method = route.request().method();
    if (method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(memory),
      });
    }
    if (method === "DELETE") {
      // Clear memory — return empty memory
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...memory,
          facts: [],
          user: {
            ...memory.user,
            workContext: {
              summary: "",
              updatedAt: memory.user.workContext.updatedAt,
            },
            personalContext: {
              summary: "",
              updatedAt: memory.user.personalContext.updatedAt,
            },
            topOfMind: {
              summary: "",
              updatedAt: memory.user.topOfMind.updatedAt,
            },
          },
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/memory/facts", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(memory),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/memory/facts/*", (route) => {
    const method = route.request().method();
    if (method === "PATCH" || method === "DELETE") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(memory),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/memory/export", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(memory),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/memory/import", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(memory),
      });
    }
    return route.fallback();
  });

  // ── Admin Resources (canonical lifecycle) ───────────────────

  void page.route("**/api/admin/resources*", (route) => {
    if (route.request().method() === "GET") {
      const url = new URL(route.request().url());
      const resourceType = url.searchParams.get("resource_type");
      const limit = Number(url.searchParams.get("limit") ?? "50");
      const offset = Number(url.searchParams.get("offset") ?? "0");

      let filtered = resources;
      if (resourceType)
        filtered = filtered.filter((r) => r.resource_type === resourceType);

      const items = filtered.slice(offset, offset + limit);

      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          resources: items,
          total: filtered.length,
          limit,
          offset,
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/resources/*/archive", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/resources/*/suspend", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/resources/*/restore", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    }
    return route.fallback();
  });

  // ── Audit Logs ──────────────────────────────────────────────

  void page.route("**/api/admin/audit-logs*", (route) => {
    if (route.request().method() === "GET") {
      const url = new URL(route.request().url());
      const page_num = Number(url.searchParams.get("page") ?? "1");
      const pageSize = Number(url.searchParams.get("page_size") ?? "20");
      const actorId = url.searchParams.get("actor_id");
      const action = url.searchParams.get("action");
      const resourceType = url.searchParams.get("resource_type");

      let filtered = auditLogs;
      if (actorId) filtered = filtered.filter((l) => l.actor_id === actorId);
      if (action && action !== "all")
        filtered = filtered.filter((l) => l.action === action);
      if (resourceType && resourceType !== "all")
        filtered = filtered.filter((l) => l.resource_type === resourceType);

      const start = (page_num - 1) * pageSize;
      const items = filtered.slice(start, start + pageSize);

      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items,
          total: filtered.length,
          page: page_num,
          page_size: pageSize,
        }),
      });
    }
    return route.fallback();
  });

  // ── MCP Config ──────────────────────────────────────────────

  void page.route("**/api/mcp/config", (route) => {
    const method = route.request().method();
    if (method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mcpConfig),
      });
    }
    if (method === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "{}",
      });
    }
    return route.fallback();
  });
}

// ---------------------------------------------------------------------------
// handleRunStream
// ---------------------------------------------------------------------------

/**
 * Build a minimal SSE stream that the LangGraph SDK can parse.
 * The stream returns a single AI message: "Hello from iDeer!".
 */
export function handleRunStream(
  route: Route,
  _data?: unknown,
  _extra?: unknown,
  overrides?: {
    responseMessage?: Record<string, unknown>;
    messageMetadata?: Record<string, unknown>;
  },
) {
  const aiMessage = overrides?.responseMessage ?? {
    type: "ai",
    id: "msg-ai-1",
    content: "Hello from iDeer!",
  };
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
            ...aiMessage,
            metadata: overrides?.messageMetadata,
          },
        ],
      },
    },
    ...(latestGoal !== null
      ? [
          {
            event: "updates",
            data: { model: { goal: latestGoal } },
          } as const,
        ]
      : []),
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
