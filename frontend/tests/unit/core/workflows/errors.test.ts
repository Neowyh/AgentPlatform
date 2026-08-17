import { describe, expect, test } from "vitest";

import {
  formatWorkflowRunError,
  workflowErrorCodeLabel,
} from "@/core/workflows/errors";

describe("workflowErrorCodeLabel", () => {
  test("maps known codes to Chinese labels", () => {
    expect(workflowErrorCodeLabel("invalid_file_roots")).toBe(
      "文件访问路径未注册",
    );
    expect(workflowErrorCodeLabel("schema_violation")).toBe(
      "输出未通过 Schema 校验",
    );
    expect(workflowErrorCodeLabel("max_attempts")).toBe("重试次数达到上限");
  });

  test("passes unknown codes through verbatim", () => {
    expect(workflowErrorCodeLabel("mystery_code")).toBe("mystery_code");
  });

  test("returns empty for missing code", () => {
    expect(workflowErrorCodeLabel(null)).toBe("");
    expect(workflowErrorCodeLabel(undefined)).toBe("");
  });
});

describe("formatWorkflowRunError", () => {
  test("prefixes the summary with the code label", () => {
    expect(
      formatWorkflowRunError(
        "无法启动工作流：2 个路径未注册",
        "invalid_file_roots",
      ),
    ).toBe("文件访问路径未注册：无法启动工作流：2 个路径未注册");
  });

  test("does not duplicate the label when already prefixed", () => {
    expect(
      formatWorkflowRunError(
        "输出未通过 Schema 校验：第 1 项违规",
        "schema_violation",
      ),
    ).toBe("输出未通过 Schema 校验：第 1 项违规");
  });

  test("returns the message unchanged without a code", () => {
    expect(formatWorkflowRunError("工作流失败", null)).toBe("工作流失败");
    expect(formatWorkflowRunError("工作流失败", "unknown")).toBe("工作流失败");
  });

  test("falls back to a default for empty messages", () => {
    expect(formatWorkflowRunError(null, "agent_failed")).toBe("工作流执行失败");
    expect(formatWorkflowRunError("", undefined)).toBe("工作流执行失败");
  });
});
