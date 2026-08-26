import { afterEach, describe, expect, test, vi } from "vitest";

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }));

vi.mock("@/core/api/fetcher", () => ({ fetch: mockFetch }));
vi.mock("@/core/config", () => ({
  getBackendBaseURL: () => "http://localhost:8000",
}));

import {
  createWorkflow,
  getRunStatus,
  getWorkflow,
  listWorkflowRuns,
  listWorkflows,
  deleteWorkflow,
  runWorkflow,
  updateWorkflow,
  workflowEventsUrl,
  workflowRunArtifactDownloadUrl,
  workflowRunRecordDownloadUrl,
} from "@/core/workflows/api";

function response(body: unknown, ok = true) {
  return { ok, json: vi.fn().mockResolvedValue(body) };
}

const resourceId = "11111111-1111-1111-1111-111111111111";
const resource = {
  id: resourceId,
  type: "workflow",
  slug: "review-flow",
  display_name: "Review Flow",
  owner_id: "owner",
  visibility: "public",
  scope_department_id: null,
  latest_version: 2,
  draft_revision: 4,
  can_modify: true,
  is_favorited: true,
};
const definition = {
  schema_version: 2,
  name: "review-flow",
  description: "Review documents",
  inputs: {},
  state: {},
  entrypoint: "review",
  nodes: [
    {
      id: "review",
      type: "action",
      action: { kind: "agent", name: "agent-id" },
    },
  ],
  edges: [],
};

describe("canonical Workflow API facade", () => {
  afterEach(() => vi.resetAllMocks());

  test("lists canonical Workflows only", async () => {
    mockFetch.mockResolvedValueOnce(response({ items: [resource], total: 1 }));

    const result = await listWorkflows();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources?type=workflow&limit=200",
    );
    expect(result).toEqual({
      workflows: [
        expect.objectContaining({
          resource_id: resourceId,
          slug: "review-flow",
          name: "Review Flow",
          version: "2",
          read_only: false,
          is_favorited: true,
        }),
      ],
      total: 1,
    });
  });

  test("loads UUID details from the published canonical version", async () => {
    mockFetch.mockResolvedValueOnce(
      response({
        resource,
        version: { version: 2 },
        content: definition,
        yaml_content: "schema_version: 2\nname: review-flow\n",
      }),
    );

    const result = await getWorkflow(resourceId);

    expect(mockFetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/resources/${resourceId}/published`,
    );
    expect(result).toMatchObject({
      resource_id: resourceId,
      name: "Review Flow",
      entrypoint: "review",
      read_only: false,
      yaml_content: "schema_version: 2\nname: review-flow\n",
    });
  });

  test("creates new Workflows as private canonical resources and publishes v1", async () => {
    mockFetch
      .mockResolvedValueOnce(
        response({
          ...resource,
          latest_version: 0,
          draft_revision: 0,
          can_modify: true,
          visibility: "private",
        }),
      )
      .mockResolvedValueOnce(response({ revision: 1, content_hash: "hash" }))
      .mockResolvedValueOnce(response({ version: 1, content_hash: "hash" }));

    const created = await createWorkflow({
      yaml_content:
        "schema_version: 2\nname: review-flow\nentrypoint: review\nnodes:\n  - id: review\n    type: action\n    action:\n      kind: agent\n      name: agent-id\nedges: []\n",
    });

    expect(mockFetch.mock.calls.map((call) => call[0])).toEqual([
      "http://localhost:8000/api/resources",
      `http://localhost:8000/api/resources/${resourceId}/workflow-draft`,
      `http://localhost:8000/api/resources/${resourceId}/publish`,
    ]);
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/resources",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          type: "workflow",
          slug: "review-flow",
          display_name: "review-flow",
          storage_kind: "database",
        }),
      }),
    );
    expect(created).toMatchObject({
      resource_id: resourceId,
      slug: "review-flow",
      read_only: false,
      version: "1",
    });
  });

  test("saves and publishes an owner canonical Workflow with optimistic locking", async () => {
    mockFetch
      .mockResolvedValueOnce(
        response({
          resource_id: resourceId,
          revision: 5,
          content_hash: "hash",
        }),
      )
      .mockResolvedValueOnce(response({ resource_id: resourceId, version: 3 }));

    await updateWorkflow(resourceId, {
      yaml_content:
        "schema_version: 2\nname: review-flow\nnodes:\n  - id: review\n",
      draft_revision: 4,
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/api/resources/${resourceId}/workflow-draft`,
      expect.objectContaining({
        method: "PUT",
        body: expect.stringContaining('"expected_revision":4'),
      }),
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8000/api/resources/${resourceId}/publish`,
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"expected_draft_revision":5'),
      }),
    );
  });

  test("archives canonical Workflows instead of hard deleting them", async () => {
    mockFetch.mockResolvedValueOnce(
      response({ ...resource, lifecycle_status: "archived" }),
    );

    await deleteWorkflow(resourceId);

    expect(mockFetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/resources/${resourceId}/archive`,
      { method: "POST" },
    );
  });

  test("routes canonical run operations by resource UUID", async () => {
    mockFetch
      .mockResolvedValueOnce(
        response({
          run_id: "run-1",
          status: "queued",
          workflow_resource_id: resourceId,
        }),
      )
      .mockResolvedValueOnce(
        response({
          run_id: "run-1",
          workflow: resourceId,
          status: "running",
          error: null,
        }),
      )
      .mockResolvedValueOnce(
        response({ runs: [], total: 0, limit: 50, offset: 0 }),
      );

    await runWorkflow(resourceId, {});
    await getRunStatus(resourceId, "run-1");
    await listWorkflowRuns(resourceId);

    expect(mockFetch.mock.calls.map((call) => call[0])).toEqual([
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs`,
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs/run-1`,
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs`,
    ]);
    expect(workflowEventsUrl(resourceId, "run-1", 3)).toBe(
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs/run-1/events?after_seq=3`,
    );
    expect(
      workflowRunArtifactDownloadUrl(resourceId, "run-1", "reports/summary.md"),
    ).toBe(
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs/run-1/artifacts/content?path=reports%2Fsummary.md`,
    );
    expect(workflowRunRecordDownloadUrl(resourceId, "run-1", "jsonl")).toBe(
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs/run-1/record?format=jsonl`,
    );
  });

  test("sends an optional model choice when starting a workflow", async () => {
    mockFetch.mockResolvedValueOnce(
      response({
        run_id: "run-model",
        status: "queued",
        workflow_resource_id: resourceId,
      }),
    );

    await runWorkflow(resourceId, { topic: "test" }, "model-b");

    expect(mockFetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/resources/${resourceId}/workflow-runs`,
      expect.objectContaining({
        body: JSON.stringify({
          inputs: { topic: "test" },
          model_name: "model-b",
        }),
      }),
    );
  });
});
