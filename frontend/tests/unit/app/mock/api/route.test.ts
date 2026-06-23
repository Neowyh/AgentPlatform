import { describe, test, expect, vi, beforeAll } from "vitest";

// Save original Response.json before mocking
const originalResponseJson = Response.json;

beforeAll(() => {
  // Response.json returns a real Response object in Node test env.
  // We intercept it to capture the parsed data for assertions.
  Response.json = vi.fn((data: unknown) => {
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof Response.json;
});

vi.mock("next/server", () => ({
  NextResponse: {
    json: vi.fn((data: unknown) => data),
  },
  NextRequest: class {},
}));

import { GET as GETMcpConfig } from "@/app/mock/api/mcp/config/route";
import { GET as GETModels } from "@/app/mock/api/models/route";
import { GET as GETSkills } from "@/app/mock/api/skills/route";

async function parseJsonResponse(response: Response) {
  return JSON.parse(await response.text());
}

describe("mock API route - mcp/config", () => {
  test("GET returns response with mcp_servers", async () => {
    const result = GETMcpConfig();
    const data = await parseJsonResponse(result);
    expect(data).toHaveProperty("mcp_servers");
    expect(typeof data.mcp_servers).toBe("object");
  });

  test("mcp_servers includes expected keys", async () => {
    const result = GETMcpConfig();
    const data = await parseJsonResponse(result);
    expect(data.mcp_servers).toHaveProperty("mcp-github-trending");
    expect(data.mcp_servers).toHaveProperty("context-7");
    expect(data.mcp_servers).toHaveProperty("feishu-importer");
  });

  test("each mcp server has enabled field", async () => {
    const result = GETMcpConfig();
    const data = await parseJsonResponse(result);
    for (const [_key, value] of Object.entries(data.mcp_servers)) {
      const server = value as Record<string, unknown>;
      expect(server).toHaveProperty("enabled");
      expect(typeof server.enabled).toBe("boolean");
    }
  });
});

describe("mock API route - models", () => {
  test("GET returns models array", async () => {
    const result = GETModels();
    const data = await parseJsonResponse(result);
    expect(data).toHaveProperty("models");
    expect(Array.isArray(data.models)).toBe(true);
  });

  test("models array is non-empty", async () => {
    const result = GETModels();
    const data = await parseJsonResponse(result);
    expect(data.models.length).toBeGreaterThan(0);
  });

  test("each model has required fields", async () => {
    const result = GETModels();
    const data = await parseJsonResponse(result);
    for (const m of data.models) {
      expect(typeof m.id).toBe("string");
      expect(typeof m.name).toBe("string");
      expect(typeof m.model).toBe("string");
      expect(typeof m.display_name).toBe("string");
      expect(typeof m.supports_thinking).toBe("boolean");
    }
  });
});

describe("mock API route - skills", () => {
  test("GET returns skills array", async () => {
    const result = GETSkills();
    const data = await parseJsonResponse(result);
    expect(data).toHaveProperty("skills");
    expect(Array.isArray(data.skills)).toBe(true);
  });

  test("skills array is non-empty", async () => {
    const result = GETSkills();
    const data = await parseJsonResponse(result);
    expect(data.skills.length).toBeGreaterThan(0);
  });

  test("each skill has required fields", async () => {
    const result = GETSkills();
    const data = await parseJsonResponse(result);
    for (const s of data.skills) {
      expect(typeof s.name).toBe("string");
      expect(typeof s.description).toBe("string");
      expect(s.license === null || typeof s.license === "string").toBe(true);
      expect(typeof s.category).toBe("string");
      expect(typeof s.enabled).toBe("boolean");
    }
  });

  test("deep-research skill is present", async () => {
    const result = GETSkills();
    const data = await parseJsonResponse(result);
    const names = data.skills.map((s: { name: string }) => s.name);
    expect(names).toContain("deep-research");
    expect(names).toContain("frontend-design");
  });
});
