import { describe, test, expect, vi, beforeEach, type Mock } from "vitest";

describe("stream-mode", () => {
  // Use fresh module imports in each test to reset the module-level
  // `warnedUnsupportedStreamModes` Set so tests are fully isolated.
  let warnUnsupportedStreamModes: typeof import("@/core/api/stream-mode").warnUnsupportedStreamModes;
  let sanitizeRunStreamOptions: typeof import("@/core/api/stream-mode").sanitizeRunStreamOptions;

  beforeEach(async () => {
    vi.resetModules();
    const mod = await import("@/core/api/stream-mode");
    warnUnsupportedStreamModes = mod.warnUnsupportedStreamModes;
    sanitizeRunStreamOptions = mod.sanitizeRunStreamOptions;
  });

  // ---------------------------------------------------------------------------
  // warnUnsupportedStreamModes
  // ---------------------------------------------------------------------------

  describe("warnUnsupportedStreamModes", () => {
    test("invokes warn callback with each unseen unsupported mode", () => {
      const warn = vi.fn();
      warnUnsupportedStreamModes(["foo", "bar"], warn);

      expect(warn).toHaveBeenCalledOnce();
      expect(warn).toHaveBeenCalledWith(
        "[ideer] Dropped unsupported LangGraph stream mode(s): foo, bar",
      );
    });

    test("suppresses repeat warnings for modes already seen", () => {
      const warn = vi.fn();
      warnUnsupportedStreamModes(["alpha"], warn);
      warnUnsupportedStreamModes(["alpha"], warn);

      // Only the first call should invoke the warn callback.
      expect(warn).toHaveBeenCalledOnce();
    });

    test("only warns about unseen modes when mixed with already-seen modes", () => {
      const warn = vi.fn();
      warnUnsupportedStreamModes(["alpha", "beta"], warn);
      warnUnsupportedStreamModes(["alpha", "gamma"], warn);

      expect(warn).toHaveBeenCalledTimes(2);
      // Second call should only contain "gamma" (alpha was already seen).
      expect(warn).toHaveBeenLastCalledWith(
        "[ideer] Dropped unsupported LangGraph stream mode(s): gamma",
      );
    });

    test("returns early without calling warn when all modes were already seen", () => {
      const warn = vi.fn();
      warnUnsupportedStreamModes(["x"], warn);
      warnUnsupportedStreamModes(["x"], warn);

      expect(warn).toHaveBeenCalledOnce();
    });

    test("defaults to console.warn when no warn callback is provided", () => {
      const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
      warnUnsupportedStreamModes(["unsupported_mode"]);

      expect(spy).toHaveBeenCalledOnce();
      expect(spy).toHaveBeenCalledWith(
        "[ideer] Dropped unsupported LangGraph stream mode(s): unsupported_mode",
      );
      spy.mockRestore();
    });

    test("handles empty modes array without calling warn", () => {
      const warn = vi.fn();
      warnUnsupportedStreamModes([], warn);

      expect(warn).not.toHaveBeenCalled();
    });
  });

  // ---------------------------------------------------------------------------
  // sanitizeRunStreamOptions
  // ---------------------------------------------------------------------------

  describe("sanitizeRunStreamOptions", () => {
    test("returns non-object inputs unchanged (number)", () => {
      expect(sanitizeRunStreamOptions(42 as unknown)).toBe(42);
    });

    test("returns non-object inputs unchanged (string)", () => {
      expect(sanitizeRunStreamOptions("hello" as unknown)).toBe("hello");
    });

    test("returns non-object inputs unchanged (boolean)", () => {
      expect(sanitizeRunStreamOptions(false as unknown)).toBe(false);
    });

    test("returns null input unchanged", () => {
      expect(sanitizeRunStreamOptions(null)).toBeNull();
    });

    test("returns object without streamMode property unchanged", () => {
      const options = { threadId: "abc", streamSubgraphs: true };
      expect(sanitizeRunStreamOptions(options)).toBe(options);
    });

    test("returns object unchanged when streamMode is null", () => {
      const options = { streamMode: null };
      expect(sanitizeRunStreamOptions(options)).toBe(options);
    });

    test("returns object unchanged when streamMode is undefined", () => {
      const options = { streamMode: undefined };
      expect(sanitizeRunStreamOptions(options)).toBe(options);
    });

    // -- All modes supported (no filtering needed) ----------------------------

    test("returns options unchanged when all array stream modes are supported", () => {
      const options = {
        streamMode: ["values", "messages", "updates"] as string[],
      };
      expect(sanitizeRunStreamOptions(options)).toBe(options);
    });

    test("returns options unchanged when scalar stream mode is supported", () => {
      const options = { streamMode: "events" as string };
      expect(sanitizeRunStreamOptions(options)).toBe(options);
    });

    // -- Filtering unsupported modes ------------------------------------------

    test("drops unsupported stream modes from array payloads", () => {
      const sanitized = sanitizeRunStreamOptions({
        streamMode: [
          "values",
          "messages-tuple",
          "custom",
          "updates",
          "events",
          "tools",
        ],
      });

      expect(sanitized.streamMode).toEqual([
        "values",
        "messages-tuple",
        "custom",
        "updates",
        "events",
      ]);
    });

    test("drops unsupported stream modes from scalar payloads", () => {
      const sanitized = sanitizeRunStreamOptions({
        streamMode: "tools",
      });

      expect(sanitized.streamMode).toBeUndefined();
    });

    test("removes all modes when every requested mode is unsupported", () => {
      const sanitized = sanitizeRunStreamOptions({
        streamMode: ["alpha", "beta"],
      });

      expect(sanitized.streamMode).toEqual([]);
    });

    test("preserves sibling properties when filtering", () => {
      const sanitized = sanitizeRunStreamOptions({
        threadId: "t1",
        streamMode: ["values", "unknown_mode"],
        recursionLimit: 25,
      });

      expect(sanitized).toEqual({
        threadId: "t1",
        streamMode: ["values"],
        recursionLimit: 25,
      });
    });

    test("warns about dropped modes via warnUnsupportedStreamModes", () => {
      const warn = vi.fn();
      // We need to exercise the warn path — sanitizeRunStreamOptions internally
      // calls warnUnsupportedStreamOptions with default console.warn.
      // We spy on console.warn to observe the side-effect.
      const spy = vi.spyOn(console, "warn").mockImplementation(() => {});

      sanitizeRunStreamOptions({
        streamMode: ["values", "bad_mode"],
      });

      expect(spy).toHaveBeenCalledOnce();
      expect(spy).toHaveBeenCalledWith(
        "[ideer] Dropped unsupported LangGraph stream mode(s): bad_mode",
      );
      spy.mockRestore();
    });

    test("handles every supported mode type in array", () => {
      const allSupported = [
        "values",
        "messages",
        "messages-tuple",
        "updates",
        "events",
        "debug",
        "tasks",
        "checkpoints",
        "custom",
      ];
      const options = { streamMode: allSupported };
      // All are supported — should return the same reference.
      expect(sanitizeRunStreamOptions(options)).toBe(options);
    });

    // -- Duplicate warning suppression across calls ---------------------------

    test("suppresses duplicate warnings for the same unsupported mode", () => {
      const spy = vi.spyOn(console, "warn").mockImplementation(() => {});

      sanitizeRunStreamOptions({ streamMode: "bad_mode" });
      sanitizeRunStreamOptions({ streamMode: "bad_mode" });

      // warnUnsupportedStreamModes is called each time, but the second call
      // should be a no-op because "bad_mode" was already seen.
      expect(spy).toHaveBeenCalledOnce();
      spy.mockRestore();
    });

    test("warns separately for different unsupported modes across calls", () => {
      const spy = vi.spyOn(console, "warn").mockImplementation(() => {});

      sanitizeRunStreamOptions({ streamMode: "bad_a" });
      sanitizeRunStreamOptions({ streamMode: "bad_b" });

      expect(spy).toHaveBeenCalledTimes(2);
      spy.mockRestore();
    });
  });
});
