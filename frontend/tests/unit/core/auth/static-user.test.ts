import { describe, expect, test } from "vitest";

import { STATIC_WEBSITE_USER } from "@/core/auth/static-user";

describe("STATIC_WEBSITE_USER", () => {
  test("has expected id", () => {
    expect(STATIC_WEBSITE_USER.id).toBe("static-website-user");
  });

  test("has expected email", () => {
    expect(STATIC_WEBSITE_USER.email).toBe("static@example.local");
  });

  test("has super_admin role", () => {
    expect(STATIC_WEBSITE_USER.system_role).toBe("super_admin");
  });

  test("does not need setup", () => {
    expect(STATIC_WEBSITE_USER.needs_setup).toBe(false);
  });
});
