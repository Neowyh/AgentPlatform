import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import {
  DEFAULT_MOCK_MEMORY,
  mockLangGraphAPI,
  type MockAgent,
  type MockSkill,
  type MockWorkflow,
} from "../utils/mock-api";

const CONTRACT_AGENT: MockAgent = {
  name: "contract-agent",
  description: "Agent API shape consumed by the gallery and detail views",
  model: "gpt-4o-mini",
  tool_groups: ["web"],
  skills: ["contract-skill"],
  soul: "Contract test agent",
  read_only: false,
};

const CONTRACT_WORKFLOW: MockWorkflow = {
  name: "contract-workflow",
  description: "Workflow API shape consumed by gallery and detail views",
  version: "1.0",
  steps: [{ id: "step1", type: "agent", agent: "contract-agent" }],
  inputs: {
    topic: { type: "string", required: true, description: "Topic" },
  },
};

const CONTRACT_SKILL: MockSkill = {
  name: "contract-skill",
  description: "Skill API shape consumed by settings",
  category: "public",
  license: "requires_internet",
  enabled: true,
};

async function openSettings(page: Page) {
  const trigger = page
    .locator("button")
    .filter({ hasText: /settings and more|settings/i })
    .last();
  await trigger.click({ timeout: 10_000 });
  await page.getByRole("menuitem", { name: /settings/i }).click();
}

test("shared mock fixture preserves agent workflow memory and skill contracts", async ({
  page,
}) => {
  mockLangGraphAPI(page, {
    agents: [CONTRACT_AGENT],
    workflows: [CONTRACT_WORKFLOW],
    skills: [CONTRACT_SKILL],
    memory: {
      ...DEFAULT_MOCK_MEMORY,
      facts: [
        {
          id: "contract-fact",
          content: "Contract memory fact",
          category: "context",
          confidence: 0.99,
          createdAt: "2026-07-09T00:00:00Z",
          source: "manual",
        },
      ],
    },
  });

  await page.goto("/workspace/agents");
  await expect(page.getByText("contract-agent")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(CONTRACT_AGENT.description!)).toBeVisible();

  await page.goto("/workspace/workflows");
  await expect(page.getByText("contract-workflow")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(CONTRACT_WORKFLOW.description!)).toBeVisible();

  await page.goto("/workspace/chats/new");
  await openSettings(page);
  await page.getByTestId("settings-tab-memory").click();
  await expect(page.getByText("Contract memory fact")).toBeVisible({
    timeout: 15_000,
  });

  await page.getByTestId("settings-tab-skills").click();
  await expect(page.getByText("contract-skill")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(CONTRACT_SKILL.description!)).toBeVisible();
});
