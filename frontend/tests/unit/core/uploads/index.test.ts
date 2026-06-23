import { describe, expect, test } from "vitest";

import * as uploadsIndex from "@/core/uploads/index";

describe("uploads index", () => {
  test("re-exports api functions", () => {
    expect(uploadsIndex).toHaveProperty("uploadFiles");
    expect(uploadsIndex).toHaveProperty("listUploadedFiles");
    expect(uploadsIndex).toHaveProperty("deleteUploadedFile");
  });

  test("re-exports hooks", () => {
    expect(uploadsIndex).toHaveProperty("useUploadFiles");
    expect(uploadsIndex).toHaveProperty("useUploadedFiles");
  });

  test("re-exports file validation", () => {
    expect(uploadsIndex).toHaveProperty("isLikelyMacOSAppBundle");
    expect(uploadsIndex).toHaveProperty("splitUnsupportedUploadFiles");
  });
});
