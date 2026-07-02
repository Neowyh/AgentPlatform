import { describe, expect, test } from "vitest";

import { aboutMarkdown } from "@/components/workspace/settings/about-content";

describe("aboutMarkdown", () => {
  test("is a non-empty string", () => {
    expect(typeof aboutMarkdown).toBe("string");
    expect(aboutMarkdown.length).toBeGreaterThan(0);
  });

  test("contains the iDeer heading", () => {
    expect(aboutMarkdown).toContain("# 关于 iDeer 2.0");
  });

  test("mentions the open source philosophy", () => {
    expect(aboutMarkdown).toContain("源于开源，回馈开源");
  });

  test("lists core features", () => {
    expect(aboutMarkdown).toContain("技能与工具");
    expect(aboutMarkdown).toContain("子智能体编排");
    expect(aboutMarkdown).toContain("沙箱与文件系统");
    expect(aboutMarkdown).toContain("长期记忆");
  });

  test("mentions MIT License", () => {
    expect(aboutMarkdown).toContain("MIT 许可证");
  });

  test("contains acknowledgments section", () => {
    expect(aboutMarkdown).toContain("致谢");
    expect(aboutMarkdown).toContain("LangChain");
    expect(aboutMarkdown).toContain("LangGraph");
    expect(aboutMarkdown).toContain("Next.js");
  });
});
