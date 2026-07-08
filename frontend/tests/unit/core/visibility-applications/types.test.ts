import { describe, expect, it } from "vitest";

import type {
  ApplicationsResponse,
  VisibilityApplication,
} from "@/core/visibility-applications/types";

describe("VisibilityApplication", () => {
  it("can be constructed with all fields", () => {
    const app: VisibilityApplication = {
      id: "app-1",
      resource_type: "agent",
      resource_id: "agent-1",
      applicant_id: "u-1",
      current_visibility: "private",
      target_visibility: "public",
      department_id: "d-1",
      reason: "Need broader access",
      status: "pending",
      submitted_at: "2024-01-01T00:00:00Z",
      reviewed_by: null,
      reviewed_at: null,
      review_comment: null,
      version: 1,
    };
    expect(app.id).toBe("app-1");
    expect(app.status).toBe("pending");
    expect(app.version).toBe(1);
  });

  it("handles nullable fields", () => {
    const app: VisibilityApplication = {
      id: "app-2",
      resource_type: "workflow",
      resource_id: "wf-1",
      applicant_id: "u-2",
      current_visibility: "department",
      target_visibility: "public",
      department_id: null,
      reason: "For collaboration",
      status: "approved",
      submitted_at: "2024-01-01T00:00:00Z",
      reviewed_by: "admin",
      reviewed_at: "2024-01-02T00:00:00Z",
      review_comment: "Approved",
      version: 2,
    };
    expect(app.department_id).toBeNull();
    expect(app.reviewed_by).toBe("admin");
    expect(app.review_comment).toBe("Approved");
  });

  it("handles null submitted_at before submission", () => {
    const app: VisibilityApplication = {
      id: "app-3",
      resource_type: "agent",
      resource_id: "agent-3",
      applicant_id: "u-3",
      current_visibility: "private",
      target_visibility: "department",
      department_id: null,
      reason: "Need access",
      status: "draft",
      submitted_at: null,
      reviewed_by: null,
      reviewed_at: null,
      review_comment: null,
      version: 0,
    };
    expect(app.submitted_at).toBeNull();
    expect(app.version).toBe(0);
  });
});

describe("ApplicationsResponse", () => {
  it("can be constructed with paginated results", () => {
    const response: ApplicationsResponse = {
      applications: [],
      total: 0,
      page: 1,
      page_size: 20,
    };
    expect(response.applications).toEqual([]);
    expect(response.total).toBe(0);
  });
});
