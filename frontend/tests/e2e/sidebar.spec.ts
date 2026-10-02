import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

// The workbench order: Chats → capability center (Agents tab) →
// Workflows → Library, followed by the standalone Scheduled tasks entry.
const WORKBENCH_NAV_HREFS = [
  "/workspace/chats",
  "/workspace/capabilities/agents",
  "/workspace/workflows",
  "/workspace/library",
  "/workspace/scheduled-tasks",
];

test.describe("Sidebar navigation", () => {
  test("sidebar keeps the pre-merge entries and appends Scheduled tasks", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    // Sidebar uses data-sidebar="menu-button" with asChild rendering on <Link>
    const sidebar = page.locator("[data-sidebar='sidebar']");
    for (const href of WORKBENCH_NAV_HREFS) {
      await expect(sidebar.locator(`a[href='${href}']`)).toBeVisible({
        timeout: 15_000,
      });
    }
    // ADR-0007: the capability-center link is the single agent entry; the
    // bare /workspace/agents URL is a redirect and never a sidebar link.
    await expect(sidebar.locator("a[href='/workspace/agents']")).toHaveCount(0);
  });

  test("Scheduled tasks follows Library and opens its existing page", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const libraryLink = sidebar.locator("a[href='/workspace/library']");
    const scheduledTasksLink = sidebar.locator(
      "a[href='/workspace/scheduled-tasks']",
    );
    await expect(libraryLink).toBeVisible({ timeout: 15_000 });
    await expect(scheduledTasksLink).toBeVisible();

    // DOM order: Scheduled tasks comes after the last original entry.
    const scheduledAfterLibrary = await sidebar.evaluate((root) => {
      const library = root.querySelector("a[href='/workspace/library']");
      const scheduled = root.querySelector(
        "a[href='/workspace/scheduled-tasks']",
      );
      return !!(
        library &&
        scheduled &&
        library.compareDocumentPosition(scheduled) & 4
      ); // 4 = FOLLOWING
    });
    expect(scheduledAfterLibrary).toBe(true);

    await scheduledTasksLink.click();
    // toHaveURL polls without requiring the load event; give it room for the
    // dev server's on-demand compilation of the destination route.
    await expect(page).toHaveURL(/\/workspace\/scheduled-tasks/, {
      timeout: 15_000,
    });
  });

  test("narrow screens expose the same entries through the sidebar drawer", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.setViewportSize({ width: 390, height: 664 });

    // The chats list renders a top-bar trigger below md width that opens the
    // same navigation as a drawer. Scope to the page header: the sidebar's
    // own (sheet-mounted) trigger would make the locator ambiguous. The dev
    // server keeps the load event pending past the test timeout, so settle
    // on domcontentloaded and let the assertions below wait for hydration.
    await page.goto("/workspace/chats", { waitUntil: "domcontentloaded" });

    const trigger = page.locator("header [data-sidebar='trigger']");
    await expect(trigger).toBeVisible({ timeout: 15_000 });

    // Below md the sidebar renders as a Sheet with data-mobile="true"; the
    // desktop container stays in the DOM but hidden, so scope to the mobile
    // instance for the drawer assertions.
    const sidebar = page.locator(
      "[data-sidebar='sidebar'][data-mobile='true']",
    );

    // The trigger needs React hydration before it responds; retry the click
    // until the drawer actually opens (a plain anchor click would navigate
    // without hydration, a button does not).
    await expect(async () => {
      await trigger.click();
      await expect(sidebar).toBeVisible();
    }).toPass({ timeout: 20_000 });

    for (const href of WORKBENCH_NAV_HREFS) {
      await expect(sidebar.locator(`a[href='${href}']`)).toBeVisible();
    }
    await expect(sidebar.locator("a[href='/workspace/agents']")).toHaveCount(0);
  });

  test("mobile welcome layout stays within viewport and desktop sidebar shows the entries", async ({
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
    for (const href of WORKBENCH_NAV_HREFS) {
      await expect(desktopSidebar.locator(`a[href='${href}']`)).toBeVisible();
    }
    await expect(
      desktopSidebar.locator("a[href='/workspace/agents']"),
    ).toHaveCount(0); // redirect target, never rendered as a sidebar link
  });
});
