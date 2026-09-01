import { beforeEach, describe, expect, test, vi } from "vitest";

describe("streams", () => {
  let warnUnsupportedStreamModes: typeof import("@/core/api/streams").warnUnsupportedStreamModes;
  let sanitizeRunStreamOptions: typeof import("@/core/api/streams").sanitizeRunStreamOptions;

  beforeEach(async () => {
    vi.resetModules();
    const mod = await import("@/core/api/streams");
    warnUnsupportedStreamModes = mod.warnUnsupportedStreamModes;
    sanitizeRunStreamOptions = mod.sanitizeRunStreamOptions;
  });

  test("warns once for unseen unsupported modes", () => {
    const warn = vi.fn();

    warnUnsupportedStreamModes(["foo", "bar"], warn);
    warnUnsupportedStreamModes(["foo", "baz"], warn);

    expect(warn).toHaveBeenCalledTimes(2);
    expect(warn).toHaveBeenNthCalledWith(
      1,
      "[ideer] Dropped unsupported LangGraph stream mode(s): foo, bar",
    );
    expect(warn).toHaveBeenNthCalledWith(
      2,
      "[ideer] Dropped unsupported LangGraph stream mode(s): baz",
    );
  });

  test("skips warning when every mode has already been seen", () => {
    const warn = vi.fn();

    warnUnsupportedStreamModes(["foo"], warn);
    warnUnsupportedStreamModes(["foo"], warn);

    expect(warn).toHaveBeenCalledOnce();
  });

  test("returns non-stream options unchanged", () => {
    const options = { threadId: "t1" };

    expect(sanitizeRunStreamOptions(null)).toBeNull();
    expect(sanitizeRunStreamOptions("value")).toBe("value");
    expect(sanitizeRunStreamOptions(options)).toBe(options);
    expect(sanitizeRunStreamOptions({ streamMode: undefined })).toEqual({
      streamMode: undefined,
    });
  });

  test("keeps supported stream modes unchanged", () => {
    const scalar = { streamMode: "updates" };
    const list = { streamMode: ["values", "messages", "custom"] };

    expect(sanitizeRunStreamOptions(scalar)).toBe(scalar);
    expect(sanitizeRunStreamOptions(list)).toBe(list);
  });

  test("throws on unsupported scalar and array stream modes", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(() => sanitizeRunStreamOptions({ streamMode: "tools" })).toThrow(
      /Unsupported stream mode\(s\): tools/,
    );
    expect(() =>
      sanitizeRunStreamOptions({
        streamMode: ["values", "tools", "events", "unknown"],
        recursionLimit: 10,
      }),
    ).toThrow(/tools, unknown/);

    expect(warn).toHaveBeenCalledTimes(2);
    expect(warn).toHaveBeenNthCalledWith(
      1,
      "[ideer] Dropped unsupported LangGraph stream mode(s): tools",
    );
    expect(warn).toHaveBeenNthCalledWith(
      2,
      "[ideer] Dropped unsupported LangGraph stream mode(s): unknown",
    );
    warn.mockRestore();
  });
});
