import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

/**
 * Accessibility (a11y) tests using axe-core.
 *
 * Scans core pages against WCAG 2.1 AA + best-practice rules.
 * Critical / serious violations are blocking; moderate / minor are reported
 * as warnings but do not fail the suite.
 */

const PAGES = [
  { name: "Landing", path: "/" },
  { name: "Login", path: "/login" },
  { name: "Setup", path: "/setup" },
];

test.describe("Accessibility — WCAG 2.1 AA", () => {
  for (const pageInfo of PAGES) {
    test(`${pageInfo.name} page has no critical a11y violations`, async ({
      page,
    }) => {
      // Mock backend so pages render without a real server
      mockLangGraphAPI(page);

      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");
      await expect(page.locator("body")).toBeVisible();

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "best-practice"])
        .analyze();

      const criticalViolations = results.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious",
      );

      if (criticalViolations.length > 0) {
        // Log details for debugging
        for (const v of criticalViolations) {
          console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
          for (const node of v.nodes.slice(0, 3)) {
            console.log(`    → ${node.html}`);
          }
          if (v.nodes.length > 3) {
            console.log(`    … and ${v.nodes.length - 3} more`);
          }
        }
      }

      // Block on critical / serious violations
      expect(
        criticalViolations.length,
        `Found ${criticalViolations.length} critical/serious a11y violations on ${pageInfo.name}`,
      ).toBe(0);
    });
  }
});
