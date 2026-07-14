import { beforeEach, describe, expect, test } from "vitest";

import { GET, PUT } from "@/app/mock/api/mcp/config/route";

describe("mock MCP config route", () => {
  beforeEach(async () => {
    await PUT(
      new Request("http://localhost/api/mock/mcp/config", {
        method: "PUT",
        body: JSON.stringify({ mcp_servers: {} }),
      }) as never,
    );
  });

  test("returns the stored configuration", async () => {
    const response = GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ mcp_servers: {} });
  });

  test("persists configuration sent by PUT", async () => {
    const config = {
      mcp_servers: {
        demo: {
          enabled: false,
          type: "stdio",
          command: "demo",
          args: [],
          env: {},
          headers: {},
          description: "Demo server",
        },
      },
    };

    const response = await PUT(
      new Request("http://localhost/api/mock/mcp/config", {
        method: "PUT",
        body: JSON.stringify(config),
      }) as never,
    );

    await expect(response.json()).resolves.toEqual(config);
  });
});
