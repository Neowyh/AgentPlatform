import { describe, expect, test } from "vitest";

import * as todosIndex from "@/core/todos/index";

describe("todos index", () => {
  test("re-exports Todo type", () => {
    expect(todosIndex).toBeDefined();
  });
});
