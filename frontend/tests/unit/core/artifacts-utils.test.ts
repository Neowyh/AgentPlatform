import { describe, expect, test } from "vitest";

import { urlOfArtifact } from "@/core/artifacts/utils";

describe("urlOfArtifact", () => {
  test("normalizes mock artifact paths with or without a leading slash", () => {
    const withLeadingSlash = urlOfArtifact({
      filepath: "/mnt/user-data/outputs/fault_tree.json",
      threadId: "thread-1",
      isMock: true,
    });
    const withoutLeadingSlash = urlOfArtifact({
      filepath: "mnt/user-data/outputs/fault_tree.json",
      threadId: "thread-1",
      isMock: true,
    });

    expect(withLeadingSlash).toBe(
      "/mock/api/threads/thread-1/artifacts/mnt/user-data/outputs/fault_tree.json",
    );
    expect(withoutLeadingSlash).toBe(withLeadingSlash);
  });

  test("keeps download query strings on mock artifact URLs", () => {
    expect(
      urlOfArtifact({
        filepath: "/mnt/user-data/outputs/fault_tree.svg",
        threadId: "thread-1",
        isMock: true,
        download: true,
      }),
    ).toBe(
      "/mock/api/threads/thread-1/artifacts/mnt/user-data/outputs/fault_tree.svg?download=true",
    );
  });

  test("normalizes production artifact paths", () => {
    expect(
      urlOfArtifact({
        filepath: "mnt/user-data/outputs/fault_tree.json",
        threadId: "thread-1",
      }),
    ).toBe(
      "/api/threads/thread-1/artifacts/mnt/user-data/outputs/fault_tree.json",
    );
  });
});
