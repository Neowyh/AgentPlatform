import { expect, test } from "@playwright/test";

const APP =
  process.env.E2E_APP_URL ??
  `http://localhost:${process.env.E2E_FRONTEND_PORT ?? "3000"}`;

test.describe("auth-disabled contract (real backend)", () => {
  test("gateway /auth/me keeps anonymous identity at the user role without a cookie", async ({
    context,
  }) => {
    const resp = await context.request.get(`${APP}/api/v1/auth/me`);

    expect(resp.status(), await resp.text()).toBe(200);
    await expect(resp.json()).resolves.toMatchObject({
      id: "default",
      email: "default@test.local",
      system_role: "user",
      needs_setup: false,
      oauth_provider: null,
    });
  });
});
