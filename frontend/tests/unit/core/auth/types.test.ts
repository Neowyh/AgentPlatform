import { describe, expect, test } from "vitest";

import {
  assertNever,
  buildLoginUrl,
  parseAuthError,
  userSchema,
} from "@/core/auth/types";
import type { AuthErrorCode, AuthErrorResponse, User } from "@/core/auth/types";

// ── userSchema ──────────────────────────────────────────────────────

describe("userSchema", () => {
  test("accepts a valid user with all fields", () => {
    const input = {
      id: "u-1",
      email: "alice@example.com",
      system_role: "super_admin",
      needs_setup: true,
    };
    const result = userSchema.safeParse(input);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual(input);
    }
  });

  test("defaults needs_setup to false when omitted", () => {
    const input = {
      id: "u-2",
      email: "bob@example.com",
      system_role: "user",
    };
    const result = userSchema.safeParse(input);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.needs_setup).toBe(false);
    }
  });

  test("accepts all valid system_role values", () => {
    const roles = [
      "viewer",
      "user",
      "department_admin",
      "super_admin",
    ] as const;
    for (const role of roles) {
      const result = userSchema.safeParse({
        id: "u-1",
        email: "test@example.com",
        system_role: role,
      });
      expect(result.success).toBe(true);
    }
  });

  test("rejects an invalid system_role", () => {
    const result = userSchema.safeParse({
      id: "u-1",
      email: "test@example.com",
      system_role: "admin",
    });
    expect(result.success).toBe(false);
  });

  test("rejects a missing id", () => {
    const result = userSchema.safeParse({
      email: "test@example.com",
      system_role: "user",
    });
    expect(result.success).toBe(false);
  });

  test("rejects a missing email", () => {
    const result = userSchema.safeParse({
      id: "u-1",
      system_role: "user",
    });
    expect(result.success).toBe(false);
  });

  test("rejects an invalid email format", () => {
    const result = userSchema.safeParse({
      id: "u-1",
      email: "not-an-email",
      system_role: "user",
    });
    expect(result.success).toBe(false);
  });

  test("rejects a missing system_role", () => {
    const result = userSchema.safeParse({
      id: "u-1",
      email: "test@example.com",
    });
    expect(result.success).toBe(false);
  });

  test("rejects non-object input", () => {
    expect(userSchema.safeParse("string").success).toBe(false);
    expect(userSchema.safeParse(42).success).toBe(false);
    expect(userSchema.safeParse(null).success).toBe(false);
    expect(userSchema.safeParse(undefined).success).toBe(false);
  });
});

// ── assertNever ─────────────────────────────────────────────────────

describe("assertNever", () => {
  test("throws with the JSON representation of the value", () => {
    expect(() => assertNever("unexpected" as never)).toThrow(
      'Unexpected auth result: "unexpected"',
    );
  });

  test("throws for an object value", () => {
    expect(() => assertNever({ foo: 1 } as never)).toThrow(
      "Unexpected auth result:",
    );
  });
});

// ── buildLoginUrl ───────────────────────────────────────────────────

describe("buildLoginUrl", () => {
  test("builds a login URL with a simple path", () => {
    expect(buildLoginUrl("/dashboard")).toBe("/login?next=%2Fdashboard");
  });

  test("encodes special characters in the return path", () => {
    expect(buildLoginUrl("/path?q=hello&lang=en")).toBe(
      `/login?next=${encodeURIComponent("/path?q=hello&lang=en")}`,
    );
  });

  test("encodes unicode characters", () => {
    expect(buildLoginUrl("/page/日本語")).toBe(
      `/login?next=${encodeURIComponent("/page/日本語")}`,
    );
  });

  test("handles root path", () => {
    expect(buildLoginUrl("/")).toBe("/login?next=%2F");
  });

  test("handles empty string", () => {
    expect(buildLoginUrl("")).toBe("/login?next=");
  });
});

// ── parseAuthError ──────────────────────────────────────────────────

describe("parseAuthError", () => {
  // Top-level {code, message}
  test("parses a top-level {code, message} object", () => {
    const data = { code: "token_expired", message: "Token has expired" };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "token_expired",
      message: "Token has expired",
    });
  });

  test("accepts all valid auth error codes at top level", () => {
    const codes: AuthErrorCode[] = [
      "invalid_credentials",
      "token_expired",
      "token_invalid",
      "user_not_found",
      "email_already_exists",
      "provider_not_found",
      "not_authenticated",
      "system_already_initialized",
    ];
    for (const code of codes) {
      const result = parseAuthError({ code, message: "test" });
      expect(result.code).toBe(code);
    }
  });

  test("rejects an invalid error code at top level and falls back", () => {
    const data = { code: "unknown_code", message: "Something" };
    const result = parseAuthError(data);
    // Falls through to default because {code, message} parse fails
    // and there's no "detail" key
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  // {detail: {code, message}} envelope
  test("unwraps FastAPI {detail: {code, message}} envelope", () => {
    const data = {
      detail: { code: "user_not_found", message: "No user with that email" },
    };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "user_not_found",
      message: "No user with that email",
    });
  });

  test("rejects invalid code inside detail envelope and falls back", () => {
    const data = {
      detail: { code: "bad_code", message: "Something" },
    };
    const result = parseAuthError(data);
    // detail parse fails, detail is an object but not ErrorDetailSchema shape
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  // Legacy string detail
  test("handles legacy {detail: string} responses", () => {
    const data = { detail: "Invalid email or password" };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "Invalid email or password",
    });
  });

  // Pydantic validation error detail list
  test("handles Pydantic validation {detail: [{msg, type, loc}]}", () => {
    const data = {
      detail: [
        { msg: "field required", type: "value_error", loc: ["body", "email"] },
      ],
    };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "field required",
    });
  });

  test("handles Pydantic detail list with multiple entries (uses first)", () => {
    const data = {
      detail: [
        { msg: "first error", type: "value_error", loc: ["body", "email"] },
        { msg: "second error", type: "value_error", loc: ["body", "password"] },
      ],
    };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "first error",
    });
  });

  test("falls back for Pydantic detail list with invalid first entry", () => {
    const data = {
      detail: [{ unknown: "field" }],
    };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("falls back for Pydantic detail list with non-object first entry", () => {
    const data = {
      detail: ["raw string error"],
    };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  // Single detail object (not {code, message} but {msg, type, loc})
  test("handles single {detail: {msg, type, loc}} object", () => {
    const data = {
      detail: {
        msg: "value is not a valid email",
        type: "value_error",
        loc: ["body", "email"],
      },
    };
    const result = parseAuthError(data);
    expect(result).toEqual({
      code: "invalid_credentials",
      message: "value is not a valid email",
    });
  });

  // Fallback for completely unknown data
  test("returns default error for null input", () => {
    expect(parseAuthError(null)).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("returns default error for undefined input", () => {
    expect(parseAuthError(undefined)).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("returns default error for a plain string", () => {
    expect(parseAuthError("something went wrong")).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("returns default error for a number", () => {
    expect(parseAuthError(42)).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("returns default error for an empty object", () => {
    expect(parseAuthError({})).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("returns default error for an object with unrelated keys", () => {
    expect(parseAuthError({ error: "bad request", status: 400 })).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("handles {detail: null} gracefully", () => {
    expect(parseAuthError({ detail: null })).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });

  test("handles {detail: 123} (non-string, non-object, non-array)", () => {
    expect(parseAuthError({ detail: 123 })).toEqual({
      code: "invalid_credentials",
      message: "Authentication failed",
    });
  });
});
