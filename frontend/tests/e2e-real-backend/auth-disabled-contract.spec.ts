import { expect, test } from "@playwright/test";

const APP =
  process.env.E2E_APP_URL ??
  `http://localhost:${process.env.E2E_FRONTEND_PORT ?? "3000"}`;

// /me also returns the caller's effective route permissions (RFC #4063
// Phase 4). Auth-disabled mode grants the full registered set, in the order
// of backend _ALL_PERMISSIONS (backend/app/gateway/authz.py) — after the
// v2.1.0 merge that set is the upstream projects/trash scopes unioned with
// the local assistants:read / models:read scopes (11 items).
const AUTH_DISABLED_PERMISSIONS = [
  "threads:read",
  "threads:write",
  "threads:delete",
  "runs:create",
  "runs:read",
  "runs:cancel",
  "assistants:read",
  "models:read",
  "projects:read",
  "projects:write",
  "projects:delete",
];

test.describe("auth-disabled contract (real backend)", () => {
  test("gateway /auth/me keeps anonymous identity at the user role without a cookie", async ({
    context,
  }) => {
    const resp = await context.request.get(`${APP}/api/v1/auth/me`);

    expect(resp.status(), await resp.text()).toBe(200);
    await expect(resp.json()).resolves.toMatchObject({
      id: "default",
      email: "default@test.local",
      // Merged backend auth.py pins the auth-disabled synthetic identity to
      // the platform "user" role (upstream's synthetic super_admin is not
      // what the merged /me returns).
      system_role: "user",
      needs_setup: false,
      oauth_provider: null,
      permissions: AUTH_DISABLED_PERMISSIONS,
    });
  });
});
