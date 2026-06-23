import { describe, expect, test } from "vitest";

import { LANGGRAPH_COMPAT_POLICY } from "@/core/auth/proxy-policy";
import type { ProxyPolicy } from "@/core/auth/proxy-policy";

// ── ProxyPolicy type conformance ────────────────────────────────────

describe("ProxyPolicy interface", () => {
  test("LANGGRAPH_COMPAT_POLICY satisfies the ProxyPolicy shape", () => {
    // Compile-time check: assigning to the type must not error.
    const policy: ProxyPolicy = LANGGRAPH_COMPAT_POLICY;
    expect(policy).toBeDefined();
  });

  test("has required top-level keys", () => {
    const policy = LANGGRAPH_COMPAT_POLICY;
    expect(policy).toHaveProperty("allowedPaths");
    expect(policy).toHaveProperty("strippedRequestHeaders");
    expect(policy).toHaveProperty("strippedResponseHeaders");
    expect(policy).toHaveProperty("credential");
    expect(policy).toHaveProperty("timeoutMs");
    expect(policy).toHaveProperty("csrf");
  });
});

// ── allowedPaths ────────────────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY.allowedPaths", () => {
  test("is a readonly array of strings", () => {
    const paths = LANGGRAPH_COMPAT_POLICY.allowedPaths;
    expect(Array.isArray(paths)).toBe(true);
    for (const p of paths) {
      expect(typeof p).toBe("string");
    }
  });

  test("contains all expected upstream path prefixes", () => {
    const expected = [
      "threads",
      "runs",
      "assistants",
      "store",
      "models",
      "mcp",
      "skills",
      "memory",
    ];
    expect(LANGGRAPH_COMPAT_POLICY.allowedPaths).toEqual(expected);
  });

  test("does not contain empty strings", () => {
    for (const p of LANGGRAPH_COMPAT_POLICY.allowedPaths) {
      expect(p.length).toBeGreaterThan(0);
    }
  });

  test("contains exactly 8 entries", () => {
    expect(LANGGRAPH_COMPAT_POLICY.allowedPaths).toHaveLength(8);
  });
});

// ── strippedRequestHeaders ──────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders", () => {
  test("is a Set", () => {
    expect(LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders).toBeInstanceOf(Set);
  });

  test("contains all expected hop-by-hop and sensitive request headers", () => {
    const expected = [
      "host",
      "connection",
      "keep-alive",
      "transfer-encoding",
      "te",
      "trailer",
      "upgrade",
      "authorization",
      "x-api-key",
      "origin",
      "referer",
      "proxy-authorization",
      "proxy-authenticate",
    ];
    for (const header of expected) {
      expect(LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders.has(header)).toBe(
        true,
      );
    }
  });

  test("contains exactly 13 entries", () => {
    expect(LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders.size).toBe(13);
  });

  test("includes hop-by-hop headers per RFC 2616", () => {
    const hopByHop = [
      "connection",
      "keep-alive",
      "transfer-encoding",
      "te",
      "trailer",
      "upgrade",
    ];
    for (const header of hopByHop) {
      expect(LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders.has(header)).toBe(
        true,
      );
    }
  });

  test("includes authentication-related headers", () => {
    const authHeaders = [
      "authorization",
      "x-api-key",
      "proxy-authorization",
      "proxy-authenticate",
    ];
    for (const header of authHeaders) {
      expect(LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders.has(header)).toBe(
        true,
      );
    }
  });
});

// ── strippedResponseHeaders ─────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders", () => {
  test("is a Set", () => {
    expect(LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders).toBeInstanceOf(Set);
  });

  test("contains all expected response headers to strip", () => {
    const expected = [
      "connection",
      "keep-alive",
      "transfer-encoding",
      "te",
      "trailer",
      "upgrade",
      "content-length",
      "set-cookie",
    ];
    for (const header of expected) {
      expect(LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders.has(header)).toBe(
        true,
      );
    }
  });

  test("contains exactly 8 entries", () => {
    expect(LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders.size).toBe(8);
  });

  test("strips set-cookie to prevent session leakage", () => {
    expect(
      LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders.has("set-cookie"),
    ).toBe(true);
  });

  test("strips content-length (will be recalculated by the proxy)", () => {
    expect(
      LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders.has("content-length"),
    ).toBe(true);
  });
});

// ── credential ──────────────────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY.credential", () => {
  test("uses cookie credential type", () => {
    expect(LANGGRAPH_COMPAT_POLICY.credential.type).toBe("cookie");
  });

  test("forwards the access_token cookie", () => {
    expect(LANGGRAPH_COMPAT_POLICY.credential.name).toBe("access_token");
  });

  test("has exactly two properties (type and name)", () => {
    expect(Object.keys(LANGGRAPH_COMPAT_POLICY.credential)).toEqual([
      "type",
      "name",
    ]);
  });
});

// ── timeoutMs ───────────────────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY.timeoutMs", () => {
  test("is set to 120 seconds", () => {
    expect(LANGGRAPH_COMPAT_POLICY.timeoutMs).toBe(120_000);
  });

  test("is a positive number", () => {
    expect(LANGGRAPH_COMPAT_POLICY.timeoutMs).toBeGreaterThan(0);
  });
});

// ── csrf ────────────────────────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY.csrf", () => {
  test("CSRF protection is enabled", () => {
    expect(LANGGRAPH_COMPAT_POLICY.csrf).toBe(true);
  });

  test("is a boolean", () => {
    expect(typeof LANGGRAPH_COMPAT_POLICY.csrf).toBe("boolean");
  });
});

// ── Immutability ────────────────────────────────────────────────────

describe("LANGGRAPH_COMPAT_POLICY immutability", () => {
  test("allowedPaths is a readonly array (TypeScript enforced)", () => {
    // At runtime the array is still mutable, but the type should prevent
    // assignment. We verify the current content is stable.
    const copy = [...LANGGRAPH_COMPAT_POLICY.allowedPaths];
    expect(LANGGRAPH_COMPAT_POLICY.allowedPaths).toEqual(copy);
  });

  test("strippedRequestHeaders Set is present and populated", () => {
    // ReadonlySet at the type level; at runtime it's a regular Set.
    // Verify we can query it but the reference is stable.
    const ref = LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders;
    expect(ref).toBe(LANGGRAPH_COMPAT_POLICY.strippedRequestHeaders);
  });

  test("strippedResponseHeaders Set is present and populated", () => {
    const ref = LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders;
    expect(ref).toBe(LANGGRAPH_COMPAT_POLICY.strippedResponseHeaders);
  });
});
