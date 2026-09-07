import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("Sidebar navigation", () => {
  test("sidebar contains Chats and Agents nav links", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    // Sidebar uses data-sidebar="menu-button" with asChild rendering on <Link>
    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.locator("a[href='/workspace/chats']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(sidebar.locator("a[href='/workspace/agents']")).toBeVisible();
  });

  test("Agents link navigates to agents page", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const agentsLink = sidebar.locator("a[href='/workspace/agents']");
    await expect(agentsLink).toBeVisible({ timeout: 15_000 });
    await agentsLink.click();

    await page.waitForURL("**/workspace/agents");
    await expect(page).toHaveURL(/\/workspace\/agents/);
  });

  test("Agents button is disabled with a hover tooltip when agents_api is off", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.route("**/api/features", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ agents_api: { enabled: false } }),
      }),
    );

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    // Chats remains a real link; Agents is no longer a navigable link.
    await expect(sidebar.locator("a[href='/workspace/chats']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(sidebar.locator("a[href='/workspace/agents']")).toHaveCount(0);

    // The disabled Agents button is rendered and announces its disabled state.
    const agentsButton = sidebar.getByRole("button", { name: "Experts" });
    await expect(agentsButton).toHaveAttribute("aria-disabled", "true");

    // The button itself has pointer-events suppressed; force the hover so the
    // event reaches the wrapping tooltip-trigger span that surfaces the tooltip.
    await agentsButton.hover({ force: true });
    await expect(page.getByText("Feature not enabled").first()).toBeVisible({
      timeout: 5_000,
    });

    // Keyboard/screen-reader users get the reason too: the disabled entry
    // stays in the tab order (focusable) and is wired to a visually-hidden
    // description rather than relying on the hover-only tooltip.
    const describedById = await agentsButton.getAttribute("aria-describedby");
    expect(describedById).toBeTruthy();
    await expect(page.locator(`#${describedById}`)).toHaveText(
      "Feature not enabled",
    );
    await agentsButton.focus();
    await expect(agentsButton).toBeFocused();
  });

  test("mobile welcome layout stays within viewport and opens sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 664 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");
    await page.evaluate(() => {
      document.cookie = "locale=zh-CN; path=/; SameSite=Lax";
    });
    await page.reload();

    const viewportWidth = page.viewportSize()?.width ?? 390;
    const expectInsideViewport = async (
      locator: ReturnType<typeof page.locator>,
    ) => {
      await expect(locator).toBeVisible({ timeout: 15_000 });
      const box = await locator.evaluate((element) => {
        let current: HTMLElement | null = element as HTMLElement;
        for (let depth = 0; current && depth < 4; depth += 1) {
          const rect = current.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            return { x: rect.x, width: rect.width };
          }
          current = current.parentElement;
        }
        return null;
      });
      expect(box).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(-1);
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewportWidth + 1);
    };

    await expectInsideViewport(page.getByRole("textbox").first());
    await expectInsideViewport(page.locator("[data-slot='suggestions-list']"));

    // The iDeer workbench welcome page is a mobile-first full-bleed layout:
    // it intentionally has no mobile sidebar drawer. Verify the layout holds
    // (no horizontal overflow) at phone width, then confirm the workspace
    // sidebar with its navigation links is reachable at desktop width.
    const overflowsHorizontally = await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth + 1,
    );
    expect(overflowsHorizontally).toBe(false);

    await page.setViewportSize({ width: 1280, height: 800 });
    const desktopSidebar = page.locator("[data-sidebar='sidebar']");
    await expect(desktopSidebar).toBeVisible({ timeout: 15_000 });
    await expect(
      desktopSidebar.locator("a[href='/workspace/chats']"),
    ).toBeVisible();
    await expect(
      desktopSidebar.locator("a[href='/workspace/agents']"),
    ).toBeVisible();
  });
});
