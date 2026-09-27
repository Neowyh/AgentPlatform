import { expect, test, type Page } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_KNOWLEDGE_BASES = {
  items: [
    {
      id: "kb-1",
      type: "knowledge_base",
      slug: "team-docs",
      display_name: "Team docs",
      visibility: "public",
      can_modify: true,
      knowledge_document_count: 2,
    },
    {
      id: "kb-2",
      type: "knowledge_base",
      slug: "chip-manuals",
      display_name: "Chip manuals",
      visibility: "private",
      can_modify: true,
      knowledge_document_count: 1,
    },
  ],
  total: 2,
};

function mockDocument(id: string, resourceId: string, name: string) {
  return {
    id,
    resource_id: resourceId,
    name,
    size: 1024,
    mime_type: "text/plain",
    content_hash: `hash-${id}`,
    source: "upload",
    status: "ready",
    can_modify: true,
    metadata: {},
    created_at: "2026-09-01T00:00:00Z",
    updated_at: null,
  };
}

const MOCK_DOCUMENTS: Record<string, { items: unknown[] }> = {
  "kb-1": {
    items: [
      mockDocument("doc-1", "kb-1", "Platform overview"),
      mockDocument("doc-2", "kb-1", "Onboarding guide"),
    ],
  },
  "kb-2": {
    items: [mockDocument("doc-3", "kb-2", "Datasheet handbook")],
  },
};

async function mockLibraryAPI(page: Page) {
  await page.route(/\/api\/resources\?type=knowledge_base/, (route) =>
    route.fulfill({ json: MOCK_KNOWLEDGE_BASES }),
  );
  await page.route(/\/api\/resources\/[^/?]+\/documents$/, (route) => {
    const resourceId = /\/api\/resources\/([^/?]+)\/documents/.exec(
      route.request().url(),
    )?.[1];
    return route.fulfill({
      json: MOCK_DOCUMENTS[resourceId ?? ""] ?? { items: [] },
    });
  });
  await page.route(/\/api\/resources\/[^/?]+\/knowledge-revisions/, (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route(/\/api\/resources\/[^/?]+\/eval-cases/, (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route(/\/api\/resources\/[^/?]+\/retrieval-tests/, (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route(/\/api\/resources\/[^/?]+\/evaluations(\?.*)?$/, (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route(/\/api\/resources\/[^/?]+\/evaluation-policy/, (route) =>
    route.fulfill({ json: { configured: false } }),
  );
}

test.describe("Library", () => {
  test("restored page keeps the baseline layout and documents tab", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await mockLibraryAPI(page);
    await page.goto("/workspace/library");

    await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
    await expect(page.getByPlaceholder("Search documents...")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Upload Document" }),
    ).toBeVisible();

    // Baseline two-tab bar; governance tabs live on their own page.
    await expect(page.getByRole("tab", { name: "Documents" })).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Knowledge Bases" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Revisions" })).toBeHidden();
    await expect(page.getByRole("tab", { name: "Evaluation" })).toBeHidden();

    // Documents of the first knowledge base are listed immediately.
    await expect(page.getByText("Platform overview")).toBeVisible();
    await expect(page.getByText("Onboarding guide")).toBeVisible();
  });

  test("knowledge base cards list document counts", async ({ page }) => {
    mockLangGraphAPI(page);
    await mockLibraryAPI(page);
    await page.goto("/workspace/library");

    await page.getByRole("tab", { name: "Knowledge Bases" }).click();

    await expect(page.getByText("Team docs")).toBeVisible();
    await expect(page.getByText("2 documents")).toBeVisible();
    await expect(page.getByText("Chip manuals")).toBeVisible();
    await expect(page.getByText("1 document", { exact: false })).toBeVisible();
  });

  test("selecting a knowledge base opens its documents", async ({ page }) => {
    mockLangGraphAPI(page);
    await mockLibraryAPI(page);
    await page.goto("/workspace/library");

    await page.getByRole("tab", { name: "Knowledge Bases" }).click();
    await page.getByRole("button", { name: /Chip manuals/ }).click();

    await expect(page.getByRole("tab", { name: "Documents" })).toHaveAttribute(
      "data-state",
      "active",
    );
    await expect(page.getByText("Datasheet handbook")).toBeVisible();
    await expect(page.getByText("Platform overview")).toBeHidden();
  });

  test("revisions and evaluation open from the library entry", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await mockLibraryAPI(page);
    await page.goto("/workspace/library");

    await page.getByRole("link", { name: "Revisions & evaluation" }).click();

    await expect(page).toHaveURL(/\/workspace\/library\/quality/);
    await expect(
      page.getByRole("heading", { name: "Revisions & evaluation" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Revisions" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Eval Cases" })).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Retrieval Test" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "Evaluation" })).toBeVisible();

    await page.getByRole("tab", { name: "Retrieval Test" }).click();
    await expect(page.getByText("Select a knowledge base")).toBeHidden();
  });
});
