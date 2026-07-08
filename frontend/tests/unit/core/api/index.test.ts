import { describe, expect, test } from "vitest";

import * as api from "@/core/api";

describe("api index", () => {
  test("re-exports api-client", () => {
    expect(api).toBeDefined();
  });

  test("exports getAPIClient", () => {
    expect(api).toHaveProperty("getAPIClient");
  });

  test("getAPIClient is a function", () => {
    expect(typeof api.getAPIClient).toBe("function");
  });
});
