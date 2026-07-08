import { describe, expect, it } from "vitest";

import type {
  InputParam,
  RetryPolicy,
  ReviewData,
  RunStatus,
  StepDef,
  StepStatus,
  WorkflowDetail,
  WorkflowRunResult,
  WorkflowSummary,
} from "@/core/workflows/types";

describe("WorkflowSummary", () => {
  it("can be constructed with required fields", () => {
    const summary: WorkflowSummary = {
      name: "test-workflow",
      description: "A test workflow",
      version: "1.0.0",
      steps_count: 3,
      inputs: {
        name: {
          type: "string",
          required: true,
          default: "",
          description: "User name",
        },
      },
      visibility: "public",
      owner_id: "u-1",
      department_id: null,
    };
    expect(summary.name).toBe("test-workflow");
    expect(summary.steps_count).toBe(3);
  });

  it("handles optional fields", () => {
    const summary: WorkflowSummary = {
      name: "wf-1",
      description: "",
      version: "1.0",
      steps_count: 0,
      inputs: {},
      visibility: "private",
      owner_id: null,
      department_id: null,
      is_favorited: true,
      error: "Invalid YAML",
    };
    expect(summary.is_favorited).toBe(true);
    expect(summary.error).toBe("Invalid YAML");
  });
});

describe("WorkflowDetail", () => {
  it("extends WorkflowSummary with yaml and steps", () => {
    const detail: WorkflowDetail = {
      name: "wf-1",
      description: "",
      version: "1.0",
      steps_count: 1,
      inputs: {},
      visibility: "public",
      owner_id: null,
      department_id: null,
      yaml_content: "name: wf-1\nsteps: []",
      steps: [],
    };
    expect(detail.yaml_content).toBe("name: wf-1\nsteps: []");
    expect(detail.steps).toEqual([]);
  });
});

describe("StepDef", () => {
  it("can be constructed for agent step type", () => {
    const step: StepDef = {
      id: "step-1",
      type: "agent",
      agent: "assistant",
      prompt: "Do something",
    };
    expect(step.type).toBe("agent");
    expect(step.agent).toBe("assistant");
  });

  it("can be constructed for tool step type", () => {
    const step: StepDef = {
      id: "step-2",
      type: "tool",
      tool: "search",
      params: { query: "hello" },
    };
    expect(step.type).toBe("tool");
    expect(step.tool).toBe("search");
  });

  it("can be constructed for condition step with branching", () => {
    const step: StepDef = {
      id: "step-3",
      type: "condition",
      expression: "x > 5",
      then: { id: "then-1", type: "tool", tool: "log" },
      else: "else-step",
    };
    expect(step.type).toBe("condition");
    expect(step.then).toBeDefined();
    expect(typeof step.else).toBe("string");
  });

  it("can be constructed for parallel step with nested steps", () => {
    const step: StepDef = {
      id: "step-4",
      type: "parallel",
      steps: [
        { id: "sub-1", type: "agent", agent: "a1", prompt: "Do X" },
        { id: "sub-2", type: "agent", agent: "a2", prompt: "Do Y" },
      ],
    };
    expect(step.steps).toHaveLength(2);
  });

  it("can be constructed with retry and timeout", () => {
    const step: StepDef = {
      id: "step-5",
      type: "tool",
      tool: "api",
      timeout: 30,
      retry: { max: 3, backoff: 1, on_errors: ["timeout"] },
      on_error: "error-handler",
    };
    expect(step.retry?.max).toBe(3);
    expect(step.timeout).toBe(30);
    expect(step.on_error).toBe("error-handler");
  });

  it("can be constructed for human_review step with all fields", () => {
    const step: StepDef = {
      id: "step-review",
      type: "human_review",
      message: "Please review this output",
      input_schema: { result: { type: "string" } },
      approvers: ["admin-1", "admin-2"],
    };
    expect(step.message).toBe("Please review this output");
    expect(step.approvers).toHaveLength(2);
  });

  it("can be constructed for parallel step with loop fields", () => {
    const step: StepDef = {
      id: "step-loop",
      type: "parallel",
      steps: [{ id: "sub-1", type: "tool", tool: "search" }],
      items: "$.results",
      max_iterations: 10,
    };
    expect(step.items).toBe("$.results");
    expect(step.max_iterations).toBe(10);
  });

  it("can be constructed for condition step with step ref string", () => {
    const step: StepDef = {
      id: "step-cond",
      type: "condition",
      condition: "${inputs.score} > 0.8",
      then: "approve-step",
      else: "reject-step",
    };
    expect(step.condition).toBe("${inputs.score} > 0.8");
  });
});

describe("InputParam", () => {
  it("can be constructed with all fields", () => {
    const param: InputParam = {
      type: "string",
      required: true,
      default: "default value",
      description: "A parameter",
    };
    expect(param.required).toBe(true);
    expect(param.default).toBe("default value");
  });
});

describe("RetryPolicy", () => {
  it("can be constructed with retry config", () => {
    const policy: RetryPolicy = {
      max: 3,
      backoff: 2,
      on_errors: ["timeout", "rate_limit"],
    };
    expect(policy.max).toBe(3);
    expect(policy.on_errors).toHaveLength(2);
  });
});

describe("WorkflowRunResult", () => {
  it("can be constructed with run metadata", () => {
    const result: WorkflowRunResult = {
      run_id: "run-1",
      status: "running",
      workflow: "wf-1",
    };
    expect(result.status).toBe("running");
  });
});

describe("StepStatus", () => {
  it("can be constructed with nullable fields", () => {
    const status: StepStatus = {
      status: "completed",
      output: { result: "success" },
      error: null,
      retries: 0,
      started_at: "2024-01-01T00:00:00Z",
      finished_at: "2024-01-01T00:01:00Z",
    };
    expect(status.status).toBe("completed");
    expect(status.output).toEqual({ result: "success" });
    expect(status.error).toBeNull();
  });

  it("handles error state", () => {
    const status: StepStatus = {
      status: "failed",
      output: null,
      error: "Something went wrong",
      retries: 2,
      started_at: "2024-01-01T00:00:00Z",
      finished_at: null,
    };
    expect(status.error).toBe("Something went wrong");
    expect(status.finished_at).toBeNull();
  });
});

describe("RunStatus", () => {
  it("handles null current_step", () => {
    const status: RunStatus = {
      run_id: "run-2",
      workflow: "wf-1",
      status: "pending",
      current_step: null,
      error: null,
      steps: {},
    };
    expect(status.current_step).toBeNull();
  });

  it("can be constructed with steps record", () => {
    const status: RunStatus = {
      run_id: "run-1",
      workflow: "wf-1",
      status: "running",
      current_step: "step-2",
      error: null,
      steps: {
        "step-1": {
          status: "completed",
          output: null,
          error: null,
          retries: 0,
          started_at: "2024-01-01T00:00:00Z",
          finished_at: "2024-01-01T00:01:00Z",
        },
      },
    };
    const step1 = status.steps["step-1"];
    expect(step1).toBeDefined();
    expect(step1!.status).toBe("completed");
  });
});

describe("ReviewData", () => {
  it("can be constructed with minimal fields", () => {
    const review: ReviewData = { approved: true };
    expect(review.approved).toBe(true);
    expect(review.comment).toBeUndefined();
  });

  it("can be constructed with optional comment", () => {
    const review: ReviewData = { approved: false, comment: "Needs changes" };
    expect(review.approved).toBe(false);
    expect(review.comment).toBe("Needs changes");
  });
});
