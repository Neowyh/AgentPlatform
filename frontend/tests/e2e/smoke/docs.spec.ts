import { expect, test } from "@playwright/test";

test.describe("Public documentation", () => {
  test("renders the Chinese documentation home and application quick start", async ({
    page,
  }) => {
    const home = await page.goto("/zh/docs");
    expect(home?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: "iDeer 文档" }),
    ).toBeVisible();

    await page.goto("/zh/docs/application/quick-start");
    await expect(page).toHaveTitle(/快速上手|iDeer/);
  });

  test("renders the English application deployment guide", async ({ page }) => {
    const response = await page.goto("/en/docs/application/deployment-guide");
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { name: /deployment guide/i }),
    ).toBeVisible();
  });

  test("returns not found for an unknown documentation page", async ({
    page,
  }) => {
    const response = await page.goto("/en/docs/does-not-exist");
    expect(response?.status()).toBe(404);
  });
});
