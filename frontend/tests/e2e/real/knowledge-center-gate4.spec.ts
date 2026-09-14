import { expect, test, type Page } from "@playwright/test";

import {
  hasRealE2EEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
  runScopedName,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };
const datasetId = process.env.E2E_KNOWLEDGE_DATASET_ID;

function hasRealKnowledgeEnvironment() {
  return hasRealE2EEnvironment() && Boolean(datasetId);
}

test.skip(
  !hasRealKnowledgeEnvironment(),
  "requires Real E2E harness plus E2E_KNOWLEDGE_DATASET_ID for a real RAGFlow dataset",
);

async function createBoundKnowledgeBase(page: Page, slug: string) {
  const cookies = await page.context().cookies();
  const cookie = cookies
    .map(({ name, value }) => `${name}=${value}`)
    .join("; ");
  const csrfToken = cookies.find((item) => item.name === "csrf_token")?.value;
  const baseUrl = process.env.IDEER_INTERNAL_GATEWAY_BASE_URL;
  const headers = {
    Cookie: cookie,
    "Content-Type": "application/json",
    ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
  };
  const create = await fetch(`${baseUrl}/api/resources`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      type: "knowledge_base",
      slug,
      display_name: slug,
      storage_kind: "database",
    }),
  });
  if (!create.ok)
    throw new Error(`create knowledge base failed: ${create.status}`);
  const resource = (await create.json()) as { id: string };

  const bind = await fetch(
    `${baseUrl}/api/resources/${encodeURIComponent(resource.id)}/knowledge`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        provider_dataset_id: datasetId,
        provider_type: "ragflow",
      }),
    },
  );
  if (!bind.ok)
    throw new Error(`bind knowledge dataset failed: ${bind.status}`);
  return resource.id;
}

test.describe.serial("real Knowledge Center Gate4", () => {
  test.use({ storageState: emptyStorageState });

  test.beforeAll(requireRealE2EEnvironment);

  test("owner creates, uploads, indexes, deletes, and observes no document", async ({
    page,
  }) => {
    const slug = runScopedName("knowledge-gate4");
    await loginAsRealUser(page, "user@test.com");
    const resourceId = await createBoundKnowledgeBase(page, slug);

    try {
      await page.goto("/workspace/library");
      await expect(
        page.getByRole("heading", { name: /library|知识库/i }),
      ).toBeVisible();
      await page.getByRole("tab", { name: /Knowledge Bases|知识库/i }).click();
      await page.getByRole("button", { name: slug }).click();
      await page.getByRole("tab", { name: /Documents|文档/i }).click();

      const uploadBody = new FormData();
      uploadBody.append(
        "file",
        new Blob([`Gate4 provider acceptance ${slug}`], { type: "text/plain" }),
        `${slug}.txt`,
      );
      const uploadCookies = await page.context().cookies();
      const uploadCookie = uploadCookies
        .map(({ name, value }) => `${name}=${value}`)
        .join("; ");
      const uploadCsrf = uploadCookies.find(
        (item) => item.name === "csrf_token",
      )?.value;
      const uploadResponse = await fetch(
        `${process.env.IDEER_INTERNAL_GATEWAY_BASE_URL}/api/resources/${encodeURIComponent(resourceId)}/documents`,
        {
          method: "POST",
          headers: {
            Cookie: uploadCookie,
            ...(uploadCsrf ? { "X-CSRF-Token": uploadCsrf } : {}),
          },
          body: uploadBody,
        },
      );
      if (!uploadResponse.ok)
        throw new Error(`upload document failed: ${uploadResponse.status}`);
      await page.reload();

      await expect(page.getByText(`${slug}.txt`, { exact: true })).toBeVisible({
        timeout: 60_000,
      });
      await expect(page.getByText("ready", { exact: true })).toBeVisible({
        timeout: 180_000,
      });

      await page.getByRole("button", { name: "Delete" }).click();
      await expect(
        page.getByText(`${slug}.txt`, { exact: true }),
      ).not.toBeVisible({ timeout: 60_000 });

      const cookie = (await page.context().cookies())
        .map(({ name, value }) => `${name}=${value}`)
        .join("; ");
      const baseUrl = process.env.IDEER_INTERNAL_GATEWAY_BASE_URL;
      await expect
        .poll(
          async () => {
            const response = await fetch(
              `${baseUrl}/api/resources/${encodeURIComponent(resourceId)}/documents`,
              { headers: { Cookie: cookie } },
            );
            if (!response.ok)
              throw new Error(`list documents failed: ${response.status}`);
            return response.json() as Promise<{ items: unknown[] }>;
          },
          { timeout: 60_000 },
        )
        .toMatchObject({ items: [] });
    } finally {
      const cookie = (await page.context().cookies())
        .map(({ name, value }) => `${name}=${value}`)
        .join("; ");
      const csrfToken = (await page.context().cookies()).find(
        (item) => item.name === "csrf_token",
      )?.value;
      await fetch(
        `${process.env.IDEER_INTERNAL_GATEWAY_BASE_URL}/api/resources/${encodeURIComponent(resourceId)}/archive`,
        {
          method: "POST",
          headers: {
            Cookie: cookie,
            ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
          },
        },
      );
    }
  });
});
