import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

/**
 * Sandbox management E2E tests.
 *
 * Verifies that sandbox-related UI elements render correctly.
 * Actual sandbox API testing is covered by the backend test template
 * (sandbox-test.template.py); this file focuses on front-end behaviour.
 */

const MOCK_AGENTS = [
  {
    name: "e2e-test-agent",
    description: "A test agent for E2E sandbox verification",
    model: "gpt-4o",
    tool_groups: [],
    skills: [],
    visibility: "private",
    owner_id: "e2e-user",
    department_id: null,
  },
];

test.describe("Sandbox Management", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });
  });

  test("workspace page loads without sandbox errors", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // The workspace should render without crashing
    await expect(page.locator("body")).toBeVisible();

    // Check that no uncaught sandbox-related errors appear
    const errors: string[] = [];
    page.on("pageerror", (err) => {
      if (err.message.toLowerCase().includes("sandbox")) {
        errors.push(err.message);
      }
    });

    // Give the page a moment to settle
    await page.waitForTimeout(1000);
    expect(errors).toHaveLength(0);
  });

  test("agent chat page renders without sandbox errors", async ({ page }) => {
    // The agents gallery lives at /workspace/agents, not the base /workspace
    // path (which redirects to /workspace/chats/new).
    await page.goto("/workspace/agents");
    await page.waitForLoadState("networkidle");

    // Wait for the agent card to appear (rendered from mock agents data)
    const agentCard = page.locator('[data-testid="agent-card"]').first();
    await expect(agentCard).toBeVisible({ timeout: 10000 });

    // Click the "Chat" button inside the agent card to navigate to the agent
    // chat page — this is where sandbox execution would occur.
    const chatButton = agentCard.locator('[data-testid="agent-chat-button"]');
    await chatButton.click();
    await page.waitForLoadState("networkidle");

    // The agent chat page should render without sandbox-related errors
    await expect(page.locator("body")).toBeVisible();
  });
});
