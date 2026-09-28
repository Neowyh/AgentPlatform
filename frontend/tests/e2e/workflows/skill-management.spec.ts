import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_SKILLS = [
  {
    name: "deep-research",
    description: "Multi-angle web research methodology",
    category: "public" as const,
    license: "requires_internet",
    enabled: true,
  },
  {
    name: "my-custom-skill",
    description: "A custom skill created by the user",
    category: "custom" as const,
    license: null,
    enabled: false,
  },
];

async function openSettings(page: Page) {
  await page.getByTestId("nav-menu-trigger").click();
  await page.getByTestId("settings-menu-item").click();
}

async function mockPublishedSkills(page: Page) {
  await page.route(/\/api\/resources\/[^/?]+\/published/, (route) => {
    const id = route
      .request()
      .url()
      .split("/api/resources/")[1]!
      .split("/")[0]!;
    const custom = id.endsWith("custom-skill");
    const name = custom ? "my-custom-skill" : "deep-research";
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        resource: {
          id,
          slug: name,
          display_name: name,
          owner_id: "e2e-user",
          visibility: custom ? "private" : "public",
          scope_department_id: null,
          system_owned: false,
          can_modify: custom,
        },
        content: { name, description: `${name} description` },
        skill_md: `# ${name}`,
        version: { version: 1 },
      }),
    });
  });
}

test.describe("Skill management", () => {
  test("legacy Skills entry opens the capability library with its common actions", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { skills: MOCK_SKILLS });
    await page.goto("/workspace/chats/new");
    await openSettings(page);
    await page.getByTestId("settings-tab-skills").click();

    await expect(page).toHaveURL(/\/workspace\/capabilities\/skills$/, {
      timeout: 30_000,
    });
    await expect(
      page.getByRole("link", { name: "deep-research" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "my-custom-skill" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /import/i })).toBeVisible();
    await expect(
      page.getByRole("link", { name: /create skill/i }),
    ).toBeVisible();
  });

  test("empty skill library still offers import and creation", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { skills: [] });
    await page.goto("/workspace/capabilities/skills");

    await expect(page.getByText("No skills found")).toBeVisible();
    await expect(page.getByRole("button", { name: /import/i })).toBeVisible();
    await expect(
      page.getByRole("link", { name: /create skill/i }),
    ).toHaveAttribute("href", /\/workspace\/chats\/new\?prompt=/);
  });

  test("public skills link to details without an archive action", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { skills: [MOCK_SKILLS[0]!] });
    await page.goto("/workspace/capabilities/skills");
    const detailLink = page.getByRole("link", { name: "deep-research" });
    await expect(detailLink).toHaveAttribute(
      "href",
      /\/workspace\/capabilities\/skills\//,
    );
    await expect(
      page.getByRole("button", { name: /skill archived/i }),
    ).toHaveCount(0);
  });

  test("custom skills link to details and offer an archive action", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { skills: [MOCK_SKILLS[1]!] });
    await page.goto("/workspace/capabilities/skills");
    const detailLink = page.getByRole("link", { name: "my-custom-skill" });
    await expect(detailLink).toHaveAttribute(
      "href",
      /\/workspace\/capabilities\/skills\//,
    );
    await expect(
      page.getByRole("button", { name: /skill archived/i }),
    ).toBeVisible();
  });

  test("public and custom skill details keep visibility actions scoped", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    mockLangGraphAPI(page, { skills: MOCK_SKILLS });
    await mockPublishedSkills(page);

    await page.goto(
      "/workspace/capabilities/skills/00000000-0000-0000-0000-eep-research",
      { waitUntil: "domcontentloaded", timeout: 60_000 },
    );
    await expect(
      page.getByRole("heading", { name: "deep-research" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /apply visibility/i }),
    ).toHaveCount(0);

    await page.goto(
      "/workspace/capabilities/skills/00000000-0000-0000-0000-custom-skill",
      { waitUntil: "domcontentloaded", timeout: 60_000 },
    );
    await expect(
      page.getByRole("heading", { name: "my-custom-skill" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /apply visibility/i }),
    ).toBeVisible();
  });
});
