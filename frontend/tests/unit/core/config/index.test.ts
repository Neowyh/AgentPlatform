import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// Mutable env mock — individual tests assign values before importing the module.
const envMock: Record<string, string | undefined> = {};

vi.mock("@/env", () => ({
  get env() {
    return envMock;
  },
}));

// Track whether we added `window` ourselves so we can clean it up.
const hadWindow = "window" in globalThis;
const hadDocument = "document" in globalThis;

// We re-import after every env mutation so the module reads fresh values.
let getBackendBaseURL: typeof import("@/core/config/index").getBackendBaseURL;
let getLangGraphBaseURL: typeof import("@/core/config/index").getLangGraphBaseURL;

async function importConfig() {
  // Bust the module cache so the mock `env` getter is re-evaluated.
  const mod = await import("@/core/config/index");
  getBackendBaseURL = mod.getBackendBaseURL;
  getLangGraphBaseURL = mod.getLangGraphBaseURL;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Set `window.location.origin` in jsdom. */
function setWindowOrigin(origin: string) {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { origin },
    writable: true,
  });
}

/** Simulate SSR by removing `window` from the global scope. */
function removeWindow() {
  // @ts-expect-error — deliberate deletion for SSR simulation
  delete globalThis.window;
}

/** Restore `window` to its original state. */
function restoreWindow() {
  if (hadWindow) {
    // jsdom provides `window`; just put it back.
    globalThis.window = globalThis as unknown as Window & typeof globalThis;
  } else {
    Reflect.deleteProperty(globalThis, "window");
  }
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Default jsdom window origin.
  setWindowOrigin("http://localhost:3000");
});

afterEach(() => {
  // Clear all env vars between tests.
  for (const key of Object.keys(envMock)) {
    delete envMock[key];
  }
  restoreWindow();
  vi.restoreAllMocks();
});

// ===========================================================================
// getBackendBaseURL
// ===========================================================================

describe("getBackendBaseURL", () => {
  test("returns empty string when NEXT_PUBLIC_BACKEND_BASE_URL is undefined", async () => {
    await importConfig();
    expect(getBackendBaseURL()).toBe("");
  });

  test("returns empty string when NEXT_PUBLIC_BACKEND_BASE_URL is empty", async () => {
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "";
    await importConfig();
    // emptyStringAsUndefined means the runtime treats "" as undefined,
    // but our mock returns whatever we set. The function checks truthiness,
    // so empty string is falsy and yields "".
    expect(getBackendBaseURL()).toBe("");
  });

  test("returns absolute URL when NEXT_PUBLIC_BACKEND_BASE_URL is an absolute URL", async () => {
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "https://api.example.com";
    await importConfig();
    expect(getBackendBaseURL()).toBe("https://api.example.com");
  });

  test("strips single trailing slash from absolute URL", async () => {
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "https://api.example.com/";
    await importConfig();
    expect(getBackendBaseURL()).toBe("https://api.example.com");
  });

  test("strips multiple trailing slashes", async () => {
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "https://api.example.com///";
    await importConfig();
    expect(getBackendBaseURL()).toBe("https://api.example.com");
  });

  test("resolves relative path against window origin", async () => {
    setWindowOrigin("http://localhost:3000");
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "/backend";
    await importConfig();
    expect(getBackendBaseURL()).toBe("http://localhost:3000/backend");
  });

  test("uses window.location.origin as base for relative paths", async () => {
    setWindowOrigin("https://my-app.example.com");
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "/api/v2";
    await importConfig();
    expect(getBackendBaseURL()).toBe("https://my-app.example.com/api/v2");
  });

  test("returns correct URL with port in env var", async () => {
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "http://localhost:8080";
    await importConfig();
    expect(getBackendBaseURL()).toBe("http://localhost:8080");
  });

  test("handles URL with path segments and trailing slashes", async () => {
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "https://api.example.com/v1//";
    await importConfig();
    expect(getBackendBaseURL()).toBe("https://api.example.com/v1");
  });

  test("uses the SSR origin fallback for a relative backend URL", async () => {
    removeWindow();
    envMock.NEXT_PUBLIC_BACKEND_BASE_URL = "/backend";
    await importConfig();

    expect(getBackendBaseURL()).toBe("http://localhost:2026/backend");
  });
});

// ===========================================================================
// getLangGraphBaseURL
// ===========================================================================

describe("getLangGraphBaseURL", () => {
  // ----- With NEXT_PUBLIC_LANGGRAPH_BASE_URL set -----

  describe("when NEXT_PUBLIC_LANGGRAPH_BASE_URL is set", () => {
    test("returns absolute URL (normalised by URL constructor)", async () => {
      envMock.NEXT_PUBLIC_LANGGRAPH_BASE_URL = "https://langgraph.example.com";
      await importConfig();
      // new URL normalises bare hostnames by appending a trailing slash.
      expect(getLangGraphBaseURL()).toBe("https://langgraph.example.com/");
    });

    test("preserves trailing slashes (no strip logic)", async () => {
      envMock.NEXT_PUBLIC_LANGGRAPH_BASE_URL = "https://langgraph.example.com/";
      await importConfig();
      expect(getLangGraphBaseURL()).toBe("https://langgraph.example.com/");
    });

    test("resolves relative path against window origin", async () => {
      setWindowOrigin("http://localhost:4000");
      envMock.NEXT_PUBLIC_LANGGRAPH_BASE_URL = "/lg";
      await importConfig();
      expect(getLangGraphBaseURL()).toBe("http://localhost:4000/lg");
    });

    test("ignores isMock flag when env var is set", async () => {
      envMock.NEXT_PUBLIC_LANGGRAPH_BASE_URL = "https://langgraph.example.com";
      await importConfig();
      expect(getLangGraphBaseURL(true)).toBe("https://langgraph.example.com/");
    });

    test("uses custom window origin as base for relative path", async () => {
      setWindowOrigin("https://custom-domain.com");
      envMock.NEXT_PUBLIC_LANGGRAPH_BASE_URL = "/graph";
      await importConfig();
      expect(getLangGraphBaseURL()).toBe("https://custom-domain.com/graph");
    });
  });

  // ----- When env var is NOT set -----

  describe("when NEXT_PUBLIC_LANGGRAPH_BASE_URL is not set", () => {
    // ----- isMock = true (browser) -----

    describe("isMock=true (browser)", () => {
      test("returns mock API path with window origin", async () => {
        setWindowOrigin("http://localhost:3000");
        await importConfig();
        expect(getLangGraphBaseURL(true)).toBe(
          "http://localhost:3000/mock/api",
        );
      });

      test("uses custom window origin for mock path", async () => {
        setWindowOrigin("https://staging.example.com");
        await importConfig();
        expect(getLangGraphBaseURL(true)).toBe(
          "https://staging.example.com/mock/api",
        );
      });
    });

    // ----- isMock = true (SSR) -----

    describe("isMock=true (SSR, no window)", () => {
      test("returns localhost fallback for mock path", async () => {
        removeWindow();
        await importConfig();
        expect(getLangGraphBaseURL(true)).toBe(
          "http://localhost:3000/mock/api",
        );
      });
    });

    // ----- isMock = false / undefined (browser) -----

    describe("isMock=false/undefined (browser)", () => {
      test("returns langgraph API path with window origin", async () => {
        setWindowOrigin("http://localhost:3000");
        await importConfig();
        expect(getLangGraphBaseURL()).toBe(
          "http://localhost:3000/api/langgraph",
        );
      });

      test("returns langgraph API path when isMock is explicitly false", async () => {
        setWindowOrigin("http://localhost:3000");
        await importConfig();
        expect(getLangGraphBaseURL(false)).toBe(
          "http://localhost:3000/api/langgraph",
        );
      });

      test("uses custom window origin for langgraph path", async () => {
        setWindowOrigin("https://prod.example.com");
        await importConfig();
        expect(getLangGraphBaseURL()).toBe(
          "https://prod.example.com/api/langgraph",
        );
      });
    });

    // ----- isMock = false / undefined (SSR) -----

    describe("isMock=false/undefined (SSR, no window)", () => {
      test("returns localhost:2026 fallback for langgraph path", async () => {
        removeWindow();
        await importConfig();
        expect(getLangGraphBaseURL()).toBe(
          "http://localhost:2026/api/langgraph",
        );
      });

      test("returns localhost:2026 fallback when isMock is explicitly false", async () => {
        removeWindow();
        await importConfig();
        expect(getLangGraphBaseURL(false)).toBe(
          "http://localhost:2026/api/langgraph",
        );
      });
    });
  });
});
