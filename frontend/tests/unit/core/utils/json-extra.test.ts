import { describe, expect, test, vi } from "vitest";

// Mock best-effort-json-parser to throw for specific inputs
vi.mock("best-effort-json-parser", () => ({
  parse: vi.fn((json: string) => {
    if (json === "<<FORCE_THROW>>") {
      throw new SyntaxError("Unexpected token");
    }
    // Use real JSON.parse for normal inputs
    return JSON.parse(json);
  }),
}));

import { tryParseJSON } from "@/core/utils/json";
import { parse } from "best-effort-json-parser";

describe("tryParseJSON - catch block coverage", () => {
  test("returns undefined when parse throws", () => {
    const result = tryParseJSON("<<FORCE_THROW>>");
    expect(result).toBeUndefined();
    expect(parse).toHaveBeenCalledWith("<<FORCE_THROW>>");
  });

  test("returns undefined for other throwing inputs", () => {
    vi.mocked(parse).mockImplementationOnce(() => {
      throw new Error("some other error");
    });
    const result = tryParseJSON("anything");
    expect(result).toBeUndefined();
  });
});
