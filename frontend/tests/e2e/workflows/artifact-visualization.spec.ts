import { expect, test } from "@playwright/test";

import { MOCK_THREAD_ID, mockLangGraphAPI } from "../utils/mock-api";

const FAULT_TREE_PATH = "/mnt/user-data/outputs/fault_tree.json";
const SVG_PATH = "/mnt/user-data/outputs/fault_tree.svg";

const faultTreeJson = JSON.stringify(
  {
    top_event: "HF-07 heat flux exceeds limit",
    intermediate_events: [{ id: "IE-01", name: "Measurement chain anomaly" }],
    bottom_events: [
      {
        id: "BE-01",
        name: "CH-07 zero drift",
        probability: "medium",
        confidence: "high",
        status: "likely",
      },
      {
        id: "BE-02",
        name: "Local flow anomaly",
        probability: null,
        confidence: "low",
        status: "to_verify",
      },
    ],
    logic: [{ parent: "IE-01", children: ["BE-01", "BE-02"], type: "OR" }],
  },
  null,
  2,
);

test.describe("Artifact visualization", () => {
  let faultTreeJsonRequests: number;
  let svgRequests: number;

  test.beforeEach(async ({ page }) => {
    faultTreeJsonRequests = 0;
    svgRequests = 0;

    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Fault tree artifacts",
          artifacts: [FAULT_TREE_PATH, SVG_PATH],
        },
      ],
      artifacts: {
        [FAULT_TREE_PATH]: {
          body: faultTreeJson,
          headers: { "X-Test-Artifact": "fault-tree-json" },
        },
        [SVG_PATH]: {
          body: '<svg xmlns="http://www.w3.org/2000/svg"><text>Fault Tree SVG</text></svg>',
          headers: { "X-Test-Artifact": "fault-tree-svg" },
        },
      },
    });

    page.on("response", (response) => {
      const url = response.url();
      if (!url.includes(`/mock/api/threads/${MOCK_THREAD_ID}/artifacts/`)) {
        return;
      }
      if (url.includes("fault_tree.json")) {
        faultTreeJsonRequests += 1;
      }
      if (url.includes("fault_tree.svg")) {
        svgRequests += 1;
      }
    });
  });

  test("renders fault_tree.json as a graph preview with code fallback", async ({
    page,
  }) => {
    await page.goto(`/workspace/chats/${MOCK_THREAD_ID}?mock=true`);

    await page.getByTestId("artifact-trigger-button").click();
    await page.getByText("fault_tree.json").click();

    await expect(page.getByText("HF-07 heat flux exceeds limit")).toBeVisible();
    await expect(page.getByText("CH-07 zero drift")).toBeVisible();
    await expect(page.getByText("Bottom events")).toBeVisible();
    await expect(page.getByText("To verify")).toBeVisible();
    expect(faultTreeJsonRequests).toBeGreaterThan(0);

    await page.getByRole("radio", { name: /code/i }).click();
    await expect(page.getByText('"top_event"')).toBeVisible();
  });

  test("previews svg artifacts as images instead of iframes", async ({
    page,
  }) => {
    await page.goto(`/workspace/chats/${MOCK_THREAD_ID}?mock=true`);

    await page.getByTestId("artifact-trigger-button").click();
    await page.getByText("fault_tree.svg").click();

    await expect(page.locator('img[alt="fault_tree.svg"]')).toBeVisible();
    await expect(page.locator("iframe")).toHaveCount(0);
    expect(svgRequests).toBeGreaterThan(0);
  });
});
