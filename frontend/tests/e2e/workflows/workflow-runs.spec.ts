import { expect, test } from "@playwright/test";

import { mockLangGraphAPI, type MockWorkflowRun } from "../utils/mock-api";

const MOCK_WORKFLOW = {
  name: "test-workflow",
  description: "A test workflow",
  version: "2.0",
  nodes: [
    {
      id: "fork_start",
      type: "fork",
      branches: ["evidence_collection", "deductive_tree"],
      join: "join_review",
    },
    {
      id: "evidence_collection",
      type: "action",
      action: { kind: "agent", name: "test-agent" },
    },
    { id: "join_review", type: "join", fork: "fork_start" },
  ],
  edges: [
    { from: "fork_start", to: "evidence_collection" },
    { from: "evidence_collection", to: "join_review" },
  ],
};

const COMPLETED_RUN: MockWorkflowRun = {
  run_id: "run-1",
  workflow: "test-workflow",
  status: "completed",
  definition_version: 2,
  error: null,
  steps: {
    fork_start: { status: "completed", retries: 0 },
    evidence_collection: {
      status: "completed",
      output: "evidence gathered",
      retries: 0,
    },
    join_review: { status: "completed", retries: 0 },
  },
  events: [
    { seq: 1, type: "node_started", payload: { node_id: "fork_start" } },
    {
      seq: 2,
      type: "edge_selected",
      payload: { from: "fork_start", to: "evidence_collection" },
    },
    { seq: 3, type: "node_completed", payload: { node_id: "fork_start" } },
    {
      seq: 4,
      type: "node_completed",
      payload: { node_id: "evidence_collection" },
    },
    { seq: 5, type: "run_completed", payload: {} },
  ],
  artifacts: [
    { path: "/mnt/user-data/outputs/fault_tree.json", size: 1234 },
    { path: "/mnt/user-data/outputs/analysis.md", size: 512 },
  ],
  artifactContents: {
    "/mnt/user-data/outputs/fault_tree.json": '{"a": 1}',
    "/mnt/user-data/outputs/analysis.md": "# analysis",
  },
  record: {
    md: "# Run record\n\nrun-1 completed",
    jsonl:
      '{"seq":1,"type":"node_started","payload":{"node_id":"fork_start"}}\n{"seq":2,"type":"run_completed","payload":{}}\n',
  },
};

const PAUSED_RUN: MockWorkflowRun = {
  ...COMPLETED_RUN,
  run_id: "run-2",
  status: "paused",
  steps: {
    fork_start: { status: "completed", retries: 0 },
    evidence_collection: { status: "running", retries: 0 },
  },
  events: [
    { seq: 1, type: "node_started", payload: { node_id: "fork_start" } },
    { seq: 2, type: "interrupted", payload: {} },
  ],
  artifacts: [],
};

test.describe("Workflow run detail", () => {
  test("shows run status, event timeline and artifacts for a completed run", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      workflows: [MOCK_WORKFLOW],
      workflowRuns: { "run-1": COMPLETED_RUN },
    });
    await page.goto("/workspace/workflows/test-workflow/runs/run-1");

    await expect(page.getByText("run-1").first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("completed").first()).toBeVisible();

    // Event timeline (Collapsible is open by default? click the trigger)
    await page.getByText("Event timeline").click();
    await expect(page.getByText("#1")).toBeVisible();
    await expect(page.getByText("node_started")).toBeVisible();
    await expect(
      page.getByText("fork_start → evidence_collection"),
    ).toBeVisible();

    // Artifacts list with sizes
    await expect(page.getByText("fault_tree.json")).toBeVisible();
    await expect(page.getByText("analysis.md")).toBeVisible();
  });

  test("paused run offers resume and cancel buttons", async ({ page }) => {
    mockLangGraphAPI(page, {
      workflows: [MOCK_WORKFLOW],
      workflowRuns: { "run-2": PAUSED_RUN },
    });
    await page.goto("/workspace/workflows/test-workflow/runs/run-2");

    await expect(
      page.getByRole("button", { name: "Resume execution" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: "Cancel run" }),
    ).toBeVisible();
  });

  test("resume submits a command to the runs commands endpoint", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      workflows: [MOCK_WORKFLOW],
      workflowRuns: { "run-2": PAUSED_RUN },
    });
    await page.goto("/workspace/workflows/test-workflow/runs/run-2");

    const commandResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/workflow-runs/run-2/commands") &&
        res.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Resume execution" }).click();
    await commandResponse;
  });

  test("MD download requests the record endpoint with format=md", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      workflows: [MOCK_WORKFLOW],
      workflowRuns: { "run-1": COMPLETED_RUN },
    });
    await page.goto("/workspace/workflows/test-workflow/runs/run-1");

    const recordResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/workflow-runs/run-1/record?format=md") &&
        res.status() === 200,
    );
    await page.getByRole("button", { name: "MD" }).click();
    await recordResponse;
  });

  test("JSONL download requests the record endpoint with format=jsonl", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      workflows: [MOCK_WORKFLOW],
      workflowRuns: { "run-1": COMPLETED_RUN },
    });
    await page.goto("/workspace/workflows/test-workflow/runs/run-1");

    const recordResponse = page.waitForResponse(
      (res) =>
        res.url().includes("/workflow-runs/run-1/record?format=jsonl") &&
        res.status() === 200,
    );
    await page.getByRole("button", { name: "JSONL" }).click();
    await recordResponse;
  });

  test("previews artifact content as pretty JSON", async ({ page }) => {
    mockLangGraphAPI(page, {
      workflows: [MOCK_WORKFLOW],
      workflowRuns: { "run-1": COMPLETED_RUN },
    });
    await page.goto("/workspace/workflows/test-workflow/runs/run-1");

    const artifactRow = page
      .getByText("fault_tree.json")
      .locator("xpath=ancestor::li");
    await artifactRow.getByRole("button", { name: "Preview" }).click();

    await expect(page.locator("pre")).toContainText('"a"');
    await expect(page.locator("pre")).toContainText("1");
  });
});
