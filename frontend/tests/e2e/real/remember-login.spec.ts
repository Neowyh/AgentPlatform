import { expect, test } from "@playwright/test";

test("login choice controls session cookie persistence", async ({ page }) => {
  const login = async (rememberMe: boolean) => {
    await page.goto("/login");

    const checkbox = page.getByRole("checkbox", {
      name: /keep me signed in/i,
    });
    if (rememberMe) {
      await checkbox.check();
    } else {
      await expect(checkbox).not.toBeChecked();
    }

    await page.locator("#email").fill("super_admin@test.com");
    await page.locator("#password").fill("super_admin@test.com");

    const loginResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/v1/auth/login/local"),
    );
    await page.getByRole("button", { name: /sign in/i }).click();
    expect((await loginResponse).ok()).toBe(true);
    await expect(page).toHaveURL(/\/workspace/);

    return page.context().cookies();
  };

  const sessionCookies = await login(false);
  expect(
    sessionCookies.find((cookie) => cookie.name === "access_token"),
  ).toMatchObject({ expires: -1, httpOnly: true });
  expect(
    sessionCookies.find(
      (cookie) => cookie.name === "deerflow_session_persistent",
    ),
  ).toMatchObject({ expires: -1, httpOnly: true });

  await page.context().clearCookies();

  const persistentCookies = await login(true);
  const persistentAccessCookie = persistentCookies.find(
    (cookie) => cookie.name === "access_token",
  );
  expect(persistentAccessCookie?.httpOnly).toBe(true);
  expect(persistentAccessCookie?.expires).toBeGreaterThan(
    Math.floor(Date.now() / 1000),
  );
});
