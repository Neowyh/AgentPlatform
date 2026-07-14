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
  steps?: { id: string; type: string; agent?: string; prompt?: string }[];
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

export type MockAPIOptions = {
  threads?: MockThread[];
  agents?: MockAgent[];
  artifacts?: Record<string, MockArtifact>;
  workflows?: MockWorkflow[];
  skills?: MockSkill[];
  users?: MockUser[];
  departments?: MockDepartment[];
  tools?: MockTool[];
  memory?: MockMemory;
  auditLogs?: MockAuditLog[];
  mcpConfig?: MockMCPConfig;
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
  const skills = options?.skills ?? [];
  const users = options?.users ?? [];
  const departments = options?.departments ?? [];
  const tools = options?.tools ?? [];
  const memory = options?.memory ?? DEFAULT_MOCK_MEMORY;
  const auditLogs = options?.auditLogs ?? [];
  const mcpConfig = options?.mcpConfig ?? { mcp_servers: {} };

  // ── Auth endpoints (defense-in-depth for IDEER_AUTH_DISABLED mode) ──

  void page.route("**/api/v1/auth/me", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "e2e-user",
          email: "e2e@test.local",
          system_role: "super_admin",
          needs_setup: false,
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/v1/auth/setup-status", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ needs_setup: false }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/v1/auth/logout", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      });
    }
    return route.fallback();
  });

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

  // Thread state — getState for individual thread
  void page.route(
    /\/(?:api\/langgraph|mock\/api)\/threads\/[^/]+\/state$/,
    (route) => {
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

  // Individual agent — agent chat page, CRUD, export/import
  void page.route(/\/api\/agents\/check/, (route) => {
    if (route.request().method() === "GET") {
      const url = new URL(route.request().url());
      const name = url.searchParams.get("name") ?? "";
      const exists = agents.some((a) => a.name === name);
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ available: !exists, name }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/agents/import", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: "imported-agent",
          description: "An imported agent",
        }),
      });
    }
    return route.fallback();
  });

  void page.route("**/api/agents/*", (route) => {
    const method = route.request().method();
    const url = route.request().url();

    if (url.includes("/api/agents/check")) {
      return route.fallback();
    }

    if (method === "GET") {
      // Export endpoint
      if (url.includes("/export")) {
        return route.fulfill({
          status: 200,
          contentType: "application/zip",
          headers: {
            "Content-Disposition": 'attachment; filename="agent.zip"',
          },
          body: Buffer.from("fake-zip-content"),
        });
      }
      const agent = agents.find((a) => url.endsWith(`/api/agents/${a.name}`));
      if (agent) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(agent),
        });
      }
    }

    if (method === "PUT") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ name: "updated-agent", description: "Updated" }),
      });
    }

    if (method === "DELETE") {
      return route.fulfill({ status: 204 });
    }

    return route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Agent not found" }),
    });
  });

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

    // Run status polling
    if (method === "GET" && url.includes("/runs/")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
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
        }),
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
              `name: ${wf.name}\ndescription: ""\nversion: "1.0"\ninputs: {}\nsteps:\n  - id: step1\n    type: agent\n    agent: ""\n    prompt: ""`,
            steps: wf.steps ?? [
              { id: "step1", type: "agent", agent: "", prompt: "" },
            ],
            steps_count: (wf.steps ?? []).length || 1,
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
          yaml_content: `name: ${wfName ?? "workflow"}\ndescription: "A workflow"\nversion: "1.0"\ninputs: {}\nsteps:\n  - id: step1\n    type: agent\n    agent: test-agent\n    prompt: "Hello"`,
          steps: [
            {
              id: "step1",
              type: "agent",
              agent: "test-agent",
              prompt: "Hello",
            },
          ],
          steps_count: 1,
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
            content: "Hello from iDeer!",
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
