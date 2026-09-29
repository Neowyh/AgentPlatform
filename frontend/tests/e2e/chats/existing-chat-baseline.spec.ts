import { expect, test, type Page, type Route } from "@playwright/test";

import { MOCK_THREAD_ID, mockLangGraphAPI } from "../utils/mock-api";

// Existing-conversation baseline (issue 08): entering a conversation or
// receiving a new message must never expand the right panel on its own, and
// the message list, composer, and its attachment/model/skill controls keep
// their pre-merge positions and paths.
const BROWSER_THREAD_ID = "00000000-0000-0000-0000-000000004001";
const RUN_ID = "00000000-0000-0000-0000-000000004009";
const BROWSER_SHOT_PATH = "/browser/live-frame.png";
// 1x1 transparent PNG so the inline frame preview renders a real image.
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

function sseBody(events: Array<{ event: string; data: unknown }>) {
  return events
    .map(
      (event) =>
        `event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`,
    )
    .join("");
}

// The chat panel's share of its resizable group: ~1 when the right panel is
// collapsed, ~0.6 at the default open size. Fractions keep the assertions
// independent of the left sidebar's width.
async function chatPanelFraction(page: Page) {
  return page.evaluate(() => {
    const chat = document.querySelector("#chat");
    const panel = chat?.closest("[data-panel]");
    const group = panel?.parentElement;
    if (!chat || !group) {
      return 0;
    }
    const groupWidth = group.getBoundingClientRect().width;
    return groupWidth > 0 ? chat.getBoundingClientRect().width / groupWidth : 0;
  });
}

async function expectPanelClosed(page: Page) {
  await expect(page.locator("aside#artifacts")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
  await expect.poll(() => chatPanelFraction(page)).toBeGreaterThan(0.95);
}

async function expectPanelOpen(page: Page) {
  await expect(page.locator("aside#artifacts")).toHaveAttribute(
    "aria-hidden",
    "false",
  );
  await expect.poll(() => chatPanelFraction(page)).toBeLessThan(0.75);
}

// A custom run stream bypasses the shared mock's thread upsert, so the SDK's
// end-of-run state refetch must be served the persisted turn explicitly (same
// contract as artifact-stream-state.spec.ts).
function servePersistedTurnAfterRun(
  page: Page,
  threadId: string,
  title: string,
  runMessages: unknown[],
) {
  let runStarted = false;
  const markRunStarted = () => {
    runStarted = true;
  };
  const runHistoryRoute = async (route: Route) => {
    if (!runStarted) {
      return route.fallback();
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          values: {
            title,
            goal: null,
            messages: runMessages,
            artifacts: [],
          },
          next: [],
          metadata: {},
          created_at: "2025-01-01T00:00:00Z",
          parent_config: null,
        },
      ]),
    });
  };
  const runMessagesRoute = async (route: Route) => {
    if (!runStarted) {
      return route.fallback();
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: runMessages.map((message, index) => ({
          run_id: RUN_ID,
          seq: index + 1,
          content: message,
          metadata: { caller: "lead_agent" },
          created_at: `2025-01-01T00:00:${String(index).padStart(2, "0")}Z`,
        })),
        has_more: false,
        next_before_seq: null,
      }),
    });
  };
  void page.route("**/api/langgraph/threads/*/history", runHistoryRoute);
  void page.route(/\/api\/threads\/[^/]+\/messages\/page/, runMessagesRoute);
  return { markRunStarted };
}

async function openExistingChat(page: Page, threadId: string) {
  await page.goto(`/workspace/chats/${threadId}`);
  await expect(page.getByTestId("chat-input")).toBeVisible({
    timeout: 15_000,
  });
  await expectPanelClosed(page);
}

test.describe("Existing conversation baseline", () => {
  test("revisiting a chat does not restore an expanded artifact panel", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Artifact history conversation",
          artifacts: ["/reports/summary.md"],
          messages: [
            {
              type: "human",
              id: "msg-human-artifact-history",
              content: [{ type: "text", text: "Write a summary" }],
            },
          ],
        },
      ],
    });

    await openExistingChat(page, MOCK_THREAD_ID);
    await page.getByTestId("artifact-trigger").click();
    await expectPanelOpen(page);

    await page.reload();
    await expect(page.getByTestId("main-message-list")).toBeVisible();
    await expectPanelClosed(page);
  });

  test("entering a conversation with browser history keeps the right panel closed", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: BROWSER_THREAD_ID,
          title: "Browser history conversation",
          messages: [
            {
              type: "human",
              id: "msg-human-browser",
              content: [{ type: "text", text: "Check example.com" }],
            },
            {
              type: "ai",
              id: "msg-ai-browser",
              content: "",
              tool_calls: [
                {
                  id: "call-browser-history",
                  name: "browser_navigate",
                  args: { url: "https://example.com" },
                },
              ],
            },
            {
              type: "tool",
              id: "msg-tool-browser",
              name: "browser_navigate",
              tool_call_id: "call-browser-history",
              content: "Navigated",
              additional_kwargs: {
                browser_view: {
                  screenshot: BROWSER_SHOT_PATH,
                  url: "https://example.com",
                  title: "Example page",
                },
              },
            },
          ],
        },
      ],
      features: { browserControlEnabled: true },
    });

    await page.goto(`/workspace/chats/${BROWSER_THREAD_ID}`);

    await expect(page.getByTestId("main-message-list")).toBeVisible({
      timeout: 15_000,
    });
    // The conversation has browser history, so the trigger is available —
    // but history replay must not open the panel by itself.
    await expect(
      page.getByRole("button", { name: "Open Agent browser panel" }),
    ).toBeVisible();
    await expectPanelClosed(page);
  });

  test("a new browser frame does not open the panel; clicking the inline frame does", async ({
    page,
  }) => {
    const runMessages = [
      {
        type: "human",
        id: "msg-human-live",
        content: [{ type: "text", text: "Open example.com" }],
      },
      {
        type: "ai",
        id: "msg-ai-live",
        content: "",
        tool_calls: [
          {
            id: "call-browser-live",
            name: "browser_navigate",
            args: { url: "https://example.com" },
          },
        ],
      },
      {
        type: "tool",
        id: "msg-tool-live",
        name: "browser_navigate",
        tool_call_id: "call-browser-live",
        content: "Navigated",
        additional_kwargs: {
          browser_view: {
            screenshot: BROWSER_SHOT_PATH,
            url: "https://example.com",
            title: "Example page",
          },
        },
      },
    ];
    mockLangGraphAPI(page, {
      threads: [{ thread_id: MOCK_THREAD_ID, title: "Live browser chat" }],
      features: { browserControlEnabled: true },
      runStreamHandler: (route: Route) =>
        route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: sseBody([
            {
              event: "metadata",
              data: { run_id: RUN_ID, thread_id: MOCK_THREAD_ID },
            },
            { event: "values", data: { messages: runMessages } },
            { event: "end", data: {} },
          ]),
        }),
    });
    const { markRunStarted } = servePersistedTurnAfterRun(
      page,
      MOCK_THREAD_ID,
      "Live browser chat",
      runMessages,
    );
    await page.route(/\/api\/threads\/[^/]+\/artifacts\//, (route) =>
      route.fulfill({
        status: 200,
        contentType: "image/png",
        body: PNG_BYTES,
      }),
    );

    await openExistingChat(page, MOCK_THREAD_ID);

    await page.getByTestId("chat-input").fill("Open example.com");
    await page.getByTestId("chat-input").press("Enter");
    markRunStarted();

    const framePreview = page.locator('button:has(img[alt="Example page"])');
    await expect(framePreview).toBeVisible({ timeout: 15_000 });
    // The frame arriving with the new message must not narrow the chat.
    await expectPanelClosed(page);

    await framePreview.click();
    await expectPanelOpen(page);
    await page.getByTestId("browser-trigger").click();
    await expectPanelClosed(page);
  });

  test("a streamed file write does not open the panel; the tool-call step does", async ({
    page,
  }) => {
    const WRITE_PATH = "/reports/quarterly-summary.md";
    const runMessages = [
      {
        type: "human",
        id: "msg-human-write",
        content: [{ type: "text", text: "Write the summary" }],
      },
      {
        type: "ai",
        id: "msg-ai-write",
        content: "",
        tool_calls: [
          {
            id: "call-write",
            name: "write_file",
            args: { path: WRITE_PATH, content: "# Summary" },
          },
        ],
      },
      {
        type: "tool",
        id: "msg-tool-write",
        name: "write_file",
        tool_call_id: "call-write",
        content: "OK",
      },
    ];
    mockLangGraphAPI(page, {
      threads: [{ thread_id: MOCK_THREAD_ID, title: "Write chat" }],
      runStreamHandler: (route: Route) =>
        route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: sseBody([
            {
              event: "metadata",
              data: { run_id: RUN_ID, thread_id: MOCK_THREAD_ID },
            },
            { event: "values", data: { messages: runMessages } },
            { event: "end", data: {} },
          ]),
        }),
    });
    const { markRunStarted } = servePersistedTurnAfterRun(
      page,
      MOCK_THREAD_ID,
      "Write chat",
      runMessages,
    );

    await openExistingChat(page, MOCK_THREAD_ID);

    await page.getByTestId("chat-input").fill("Write the summary");
    await page.getByTestId("chat-input").press("Enter");
    markRunStarted();

    await expect(page.getByText(WRITE_PATH)).toBeVisible({
      timeout: 15_000,
    });
    // Receiving the file-write turn must not expand the review panel.
    await expectPanelClosed(page);

    await page.getByText(WRITE_PATH).click();
    await expectPanelOpen(page);
    await page
      .locator("aside#artifacts")
      .getByRole("button", { name: "Close" })
      .click();
    await expectPanelClosed(page);
  });

  test("composer and header controls keep their baseline positions", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Controls baseline chat",
          messages: [
            {
              type: "human",
              id: "msg-human-controls",
              content: [{ type: "text", text: "Hello there" }],
            },
            {
              type: "ai",
              id: "msg-ai-controls",
              content: "Hi! How can I help?",
            },
          ],
        },
      ],
    });

    await page.goto(`/workspace/chats/${MOCK_THREAD_ID}`);
    await expect(page.getByTestId("main-message-list")).toBeVisible({
      timeout: 15_000,
    });

    const attachment = page.getByTestId("add-attachments-button");
    const mode = page.getByRole("button", { name: "Mode", exact: true });
    const model = page.getByTestId("model-selector-trigger");
    const skill = page.getByTestId("skill-selector-trigger");
    const submit = page.getByRole("button", { name: "Submit" });
    for (const control of [attachment, mode, model, skill, submit]) {
      await expect(control).toBeVisible();
    }

    // Attachment and mode sit left of the model, skill, and submit group.
    const [attachmentBox, modeBox, modelBox, skillBox, submitBox] =
      await Promise.all([
        attachment.boundingBox(),
        mode.boundingBox(),
        model.boundingBox(),
        skill.boundingBox(),
        submit.boundingBox(),
      ]);
    expect(attachmentBox!.x).toBeLessThan(modeBox!.x);
    expect(modeBox!.x).toBeLessThan(modelBox!.x);
    expect(modelBox!.x).toBeLessThan(skillBox!.x);
    expect(skillBox!.x).toBeLessThan(submitBox!.x);

    // The original header controls stay in place.
    await expect(page.getByTestId("export-trigger-button")).toBeVisible();
    await expect(page.getByTestId("artifact-trigger")).toHaveCount(0);
    await expectPanelClosed(page);

    const fileChooser = page.waitForEvent("filechooser");
    await attachment.click();
    await fileChooser;

    await model.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");

    await skill.click();
    await expect(page.getByTestId("slash-overlay")).toBeVisible();
  });
});
