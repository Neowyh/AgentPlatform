import { expect, test, type Page, type Route } from "@playwright/test";

import { mockLangGraphAPI, type MockThread } from "./utils/mock-api";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";
const THREAD_ID = "00000000-0000-0000-0000-000000000701";

// The finalized mock-api helper has no project/trash endpoints, so this spec
// seeds them itself: a small in-memory document store behind Playwright routes
// that mirrors the gateway contract (projects §6.5, trash §8).
type ShelfDocument = {
  id: string;
  project_id: string;
  name: string;
  size_bytes: number;
  sha256: string;
  content_missing: boolean;
  source_thread_id: string | null;
  source_kind: string | null;
  source_name: string | null;
  created_at: string;
  updated_at: string;
};

type TrashOrigin = { project_id: string; project_name: string };

type TrashRow = ShelfDocument & {
  trashed_at: string;
  trash_origin: TrashOrigin | null;
};

type SeedDocument = {
  id: string;
  project_id?: string;
  name: string;
  size_bytes: number;
};

type SeedTrashDocument = SeedDocument & {
  trashed_at: string;
  trash_origin: TrashOrigin | null;
};

type SeedProject = {
  id: string;
  name: string;
  instructions?: string;
};

type ProjectDocumentsSeed = {
  projects: SeedProject[];
  threads?: MockThread[];
  projectDocuments?: SeedDocument[];
  trashDocuments?: SeedTrashDocument[];
  projectsConfig?: { trash_retention_days: number };
};

const PROJECTS_CONFIG_DEFAULT = {
  instructions_max_bytes: 8192,
  trash_retention_days: 30,
};

function seedProject(): ProjectDocumentsSeed {
  return {
    projects: [{ id: PROJECT_ID, name: "Alpha" }],
    threads: [
      {
        thread_id: THREAD_ID,
        title: "Project chat",
        updated_at: "2026-09-10T10:00:00Z",
        metadata: { deerflow_project_id: PROJECT_ID },
      },
    ],
  };
}

function makeDocument(seed: SeedDocument, projectId: string): ShelfDocument {
  const now = new Date().toISOString();
  return {
    id: seed.id,
    project_id: seed.project_id ?? projectId,
    name: seed.name,
    size_bytes: seed.size_bytes,
    sha256: `sha256-${seed.id}`,
    content_missing: false,
    source_thread_id: null,
    source_kind: null,
    source_name: null,
    created_at: now,
    updated_at: now,
  };
}

function paginateDocuments(rows: ShelfDocument[], url: string) {
  const params = new URL(url).searchParams;
  const limit = Number(params.get("limit") ?? "100");
  const offset = Number(params.get("offset") ?? "0");
  return {
    documents: rows.slice(offset, offset + limit),
    total: rows.length,
    limit,
    offset,
  };
}

async function mockProjectDocumentsAPI(
  page: Page,
  seed: ProjectDocumentsSeed,
): Promise<void> {
  const firstProject = seed.projects[0];
  const projectId = firstProject?.id ?? PROJECT_ID;
  const shelf: ShelfDocument[] = (seed.projectDocuments ?? []).map((doc) =>
    makeDocument(doc, doc.project_id ?? projectId),
  );
  const trash: TrashRow[] = (seed.trashDocuments ?? []).map((row) => ({
    ...makeDocument(row, row.project_id ?? projectId),
    trashed_at: row.trashed_at,
    trash_origin: row.trash_origin ?? null,
  }));
  const config = { ...PROJECTS_CONFIG_DEFAULT, ...seed.projectsConfig };
  let nextDocumentId = 0;
  const projectNameOf = (id: string) =>
    seed.projects.find((project) => project.id === id)?.name ?? id;
  const notFound = (route: Route) =>
    route.fulfill({ status: 404, json: { detail: "not found" } });

  mockLangGraphAPI(page, { threads: seed.threads ?? [] });

  await page.route("**/api/projects", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: { projects: seed.projects } })
      : route.fallback(),
  );
  await page.route("**/api/projects/**", (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;
    const rest = path.slice(
      path.indexOf("/api/projects") + "/api/projects".length,
    );
    const segments = rest.split("/").filter(Boolean);

    if (segments.length === 1 && segments[0] === "config" && method === "GET") {
      return route.fulfill({ json: config });
    }
    if (segments.length === 1 && method === "GET") {
      const project = seed.projects.find((p) => p.id === segments[0]);
      if (!project) {
        return notFound(route);
      }
      return route.fulfill({
        json: {
          id: project.id,
          name: project.name,
          instructions: project.instructions ?? "",
          presentation: {},
          status: "active",
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-01T00:00:00Z",
        },
      });
    }
    if (
      segments.length === 2 &&
      segments[1] === "threads" &&
      method === "GET"
    ) {
      const threads = (seed.threads ?? [])
        .filter(
          (thread) => thread.metadata?.deerflow_project_id === segments[0],
        )
        .map((thread) => ({
          thread_id: thread.thread_id,
          display_name: thread.title ?? null,
          metadata: thread.metadata ?? null,
          updated_at: thread.updated_at ?? null,
        }));
      return route.fulfill({ json: threads });
    }
    if (
      segments.length === 2 &&
      segments[1] === "documents" &&
      method === "GET"
    ) {
      return route.fulfill({ json: paginateDocuments(shelf, request.url()) });
    }
    if (
      segments.length === 2 &&
      segments[1] === "documents" &&
      method === "POST"
    ) {
      const ownerProjectId = segments[0] ?? "";
      const filename =
        /filename="([^"]+)"/.exec(request.postData() ?? "")?.[1] ??
        "upload.bin";
      const now = new Date().toISOString();
      const document: ShelfDocument = {
        id: `doc-${++nextDocumentId}`,
        project_id: ownerProjectId,
        name: filename,
        size_bytes: request.postDataBuffer()?.byteLength ?? 0,
        sha256: `sha256-doc-${nextDocumentId}`,
        content_missing: false,
        source_thread_id: null,
        source_kind: "upload",
        source_name: null,
        created_at: now,
        updated_at: now,
      };
      shelf.push(document);
      return route.fulfill({
        status: 201,
        json: { document, deduplicated: false },
      });
    }
    if (
      segments.length === 3 &&
      segments[1] === "documents" &&
      method === "DELETE"
    ) {
      const ownerProjectId = segments[0] ?? "";
      const documentId = segments[2] ?? "";
      const index = shelf.findIndex(
        (doc) => doc.id === documentId && doc.project_id === ownerProjectId,
      );
      const document = shelf[index];
      if (index < 0 || !document) {
        return notFound(route);
      }
      shelf.splice(index, 1);
      trash.push({
        ...document,
        trashed_at: new Date().toISOString(),
        trash_origin: {
          project_id: ownerProjectId,
          project_name: projectNameOf(ownerProjectId),
        },
      });
      return route.fulfill({ status: 204 });
    }
    if (
      segments.length === 5 &&
      segments[1] === "documents" &&
      segments[3] === "attach-to-thread" &&
      method === "POST"
    ) {
      const document = shelf.find(
        (doc) => doc.id === segments[2] && doc.project_id === segments[0],
      );
      if (!document) {
        return notFound(route);
      }
      return route.fulfill({
        json: {
          filename: document.name,
          size_bytes: document.size_bytes,
          virtual_path: `/mnt/user_data/projects/${document.project_id}/${document.name}`,
          artifact_url: `/api/projects/${document.project_id}/documents/${document.id}/content`,
        },
      });
    }
    return route.fallback();
  });
  await page.route("**/api/trash/**", (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;
    const rest = path.slice(path.indexOf("/api/trash") + "/api/trash".length);
    const segments = rest.split("/").filter(Boolean);

    if (
      segments.length === 1 &&
      segments[0] === "documents" &&
      method === "GET"
    ) {
      return route.fulfill({ json: paginateDocuments(trash, request.url()) });
    }
    if (
      segments.length === 3 &&
      segments[0] === "documents" &&
      segments[2] === "restore" &&
      method === "POST"
    ) {
      const index = trash.findIndex((row) => row.id === segments[1]);
      const row = trash[index];
      if (index < 0 || !row) {
        return notFound(route);
      }
      trash.splice(index, 1);
      const document: ShelfDocument = {
        id: row.id,
        project_id: row.project_id,
        name: row.name,
        size_bytes: row.size_bytes,
        sha256: row.sha256,
        content_missing: row.content_missing,
        source_thread_id: row.source_thread_id,
        source_kind: row.source_kind,
        source_name: row.source_name,
        created_at: row.created_at,
        updated_at: new Date().toISOString(),
      };
      shelf.push(document);
      return route.fulfill({ json: { outcome: "restored", document } });
    }
    if (
      segments.length === 3 &&
      segments[0] === "documents" &&
      segments[2] === "purge" &&
      method === "POST"
    ) {
      const index = trash.findIndex((row) => row.id === segments[1]);
      if (index < 0) {
        return notFound(route);
      }
      trash.splice(index, 1);
      return route.fulfill({ status: 204 });
    }
    if (segments.length === 1 && segments[0] === "purge" && method === "POST") {
      const purged = trash.length;
      trash.length = 0;
      return route.fulfill({ json: { purged } });
    }
    return route.fallback();
  });
}

async function openDocumentsTab(page: Page) {
  await page.goto(`/workspace/projects/${PROJECT_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  await expect(page.getByTestId("project-documents-shelf")).toBeVisible();
}

test("project document lifecycle: upload → shelf → attach → trash → restore → purge", async ({
  page,
}) => {
  await mockProjectDocumentsAPI(page, seedProject());

  // Upload joins the shelf.
  await openDocumentsTab(page);
  await page.getByTestId("project-documents-upload-input").setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("hello shelf"),
  });
  await expect(page.getByText("notes.txt", { exact: true })).toBeVisible();

  // Attach hands the thread's composer a completed attachment.
  await page
    .getByRole("button", { name: "Attach to chat", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Project chat", exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`/workspace/chats/${THREAD_ID}`));
  await expect(page.getByTestId("project-attachment-chip")).toContainText(
    "notes.txt",
  );

  // Move to trash behind its retention-window confirmation.
  await openDocumentsTab(page);
  await page
    .getByRole("button", { name: "Move to trash", exact: true })
    .click();
  await expect(
    page.getByText(/will move to the trash and stay recoverable for 30 days/),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Move to trash", exact: true })
    .click();
  await expect(page.getByText("No documents yet")).toBeVisible();

  // Trash view: origin project + retention, then restore into the origin.
  await page.goto("/workspace/trash", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("notes.txt", { exact: true })).toBeVisible();
  await expect(page.getByText(/from Alpha/)).toBeVisible();
  await expect(page.getByText(/days left/)).toBeVisible();
  await page.getByRole("button", { name: "Restore", exact: true }).click();
  await expect(page.getByText("Trash is empty.")).toBeVisible();

  // Restored row is back on the shelf; trash it again, then purge for good.
  await openDocumentsTab(page);
  await expect(page.getByText("notes.txt", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Move to trash", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Move to trash", exact: true })
    .click();
  await page.goto("/workspace/trash", { waitUntil: "domcontentloaded" });
  await page
    .getByRole("button", { name: "Delete permanently", exact: true })
    .click();
  await expect(
    page.getByText(/will be permanently deleted. This cannot be undone./),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete permanently", exact: true })
    .click();
  await expect(page.getByText("Trash is empty.")).toBeVisible();
});

test("Empty trash permanently deletes every freshly trashed row", async ({
  page,
}) => {
  const trashedAt = new Date(Date.now() - 60_000).toISOString();
  await mockProjectDocumentsAPI(page, {
    ...seedProject(),
    trashDocuments: ["one.txt", "two.txt"].map((name, index) => ({
      id: `trash-${index}`,
      project_id: PROJECT_ID,
      name,
      size_bytes: 32,
      // Trashed a minute ago: far inside the 30-day retention window, so the
      // action cannot lean on the retention sweep to delete them.
      trashed_at: trashedAt,
      trash_origin: { project_id: PROJECT_ID, project_name: "Alpha" },
    })),
  });

  await page.goto("/workspace/trash", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("one.txt", { exact: true })).toBeVisible();
  await expect(page.getByText("two.txt", { exact: true })).toBeVisible();

  await page.getByTestId("trash-empty-button").click();
  await expect(
    page.getByText(
      "2 documents will be permanently deleted. This cannot be undone.",
    ),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Empty trash", exact: true })
    .click();

  // The confirmation promised both rows; both are gone.
  await expect(page.getByText("Trash is empty.")).toBeVisible();
  await expect(page.getByText("one.txt", { exact: true })).toHaveCount(0);
  await expect(page.getByText("two.txt", { exact: true })).toHaveCount(0);
});

test("the shelf paginates past the first page and the trash confirmation names the configured retention", async ({
  page,
}) => {
  await mockProjectDocumentsAPI(page, {
    ...seedProject(),
    projectsConfig: { trash_retention_days: 7 },
    projectDocuments: Array.from({ length: 120 }, (_, index) => ({
      id: `doc-${index}`,
      project_id: PROJECT_ID,
      name: `doc-${String(index).padStart(3, "0")}.txt`,
      size_bytes: 128,
    })),
  });

  await openDocumentsTab(page);
  // First page: 100 of 120 loaded, with a Load more affordance.
  await expect(page.getByText("Showing 100 of 120")).toBeVisible();
  await expect(page.getByText("doc-099.txt", { exact: true })).toBeVisible();
  await expect(page.getByText("doc-119.txt", { exact: true })).toHaveCount(0);
  await page.getByTestId("project-documents-load-more").click();
  await expect(page.getByText("Showing 120 of 120")).toBeVisible();
  await expect(page.getByText("doc-119.txt", { exact: true })).toBeVisible();
  await expect(page.getByTestId("project-documents-load-more")).toHaveCount(0);

  // The confirmation names the server-configured 7-day window, not the
  // 30-day default.
  await page
    .getByRole("button", { name: "Move to trash", exact: true })
    .first()
    .click();
  await expect(page.getByText(/stay recoverable for 7 days/)).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
});

test("the trash view paginates and counts down the configured retention window", async ({
  page,
}) => {
  await mockProjectDocumentsAPI(page, {
    ...seedProject(),
    projectsConfig: { trash_retention_days: 7 },
    trashDocuments: Array.from({ length: 120 }, (_, index) => ({
      id: `trash-${index}`,
      project_id: PROJECT_ID,
      name: `trash-${String(index).padStart(3, "0")}.txt`,
      size_bytes: 64,
      // Trashed 10 days ago: past the configured 7-day window.
      trashed_at: new Date(Date.now() - 10 * 86_400_000).toISOString(),
      trash_origin: { project_id: PROJECT_ID, project_name: "Alpha" },
    })),
  });

  await page.goto("/workspace/trash", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Showing 100 of 120")).toBeVisible();
  await page.getByTestId("trash-load-more").click();
  await expect(page.getByText("Showing 120 of 120")).toBeVisible();
  await expect(page.getByTestId("trash-load-more")).toHaveCount(0);
  await expect(page.getByText(/Less than a day left/).first()).toBeVisible();
});

test("a project member thread renders no injected <project> text in the message list", async ({
  page,
}) => {
  await mockProjectDocumentsAPI(page, {
    projects: [
      {
        id: PROJECT_ID,
        name: "Alpha",
        instructions: "Always answer in haiku.",
      },
    ],
    threads: [
      {
        thread_id: THREAD_ID,
        title: "Project chat",
        updated_at: "2026-09-10T10:00:00Z",
        metadata: { deerflow_project_id: PROJECT_ID },
        messages: [
          {
            type: "human",
            id: "msg-human-1",
            content: [{ type: "text", text: "status?" }],
          },
          { type: "ai", id: "msg-ai-1", content: "all green" },
        ],
      },
    ],
  });
  await page.goto(`/workspace/chats/${THREAD_ID}`, {
    waitUntil: "domcontentloaded",
  });
  const list = page.getByTestId("main-message-list");
  await expect(list.getByText("all green", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  // Project context is injected request-side only: no <project> block, and no
  // instructions text, ever reaches the rendered conversation.
  await expect(list.getByText(/<project>/)).toHaveCount(0);
  await expect(list.getByText(/Always answer in haiku/)).toHaveCount(0);
});
