import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  buildScenarioSubmissionBinding,
  useScenarioBinding,
} from "@/core/scenarios/binding";

describe("useScenarioBinding", () => {
  it("does not retain a paper-review Skill when the Expert switches to fault-zeroing", () => {
    const binding = buildScenarioSubmissionBinding({
      baseContext: {
        mode: "flash",
        agent_resource_id: "old-paper-agent",
        skill_resource_id: "paper-skill-id",
        skill_name: "academic-paper-review",
      },
      selectedPill: { scenarioId: "professional", agentSlug: "fault-zeroing" },
      selectedChip: null,
      agent: { resource_id: "fault-agent-id", slug: "fault-zeroing" },
      agentDetails: { skills: ["fault-skill-id"] },
      skills: [
        {
          resource_id: "paper-skill-id",
          slug: "academic-paper-review",
          name: "Academic paper review",
        },
        {
          resource_id: "fault-skill-id",
          slug: "fault-zeroing",
          name: "Fault zeroing",
        },
      ],
    });

    expect(binding).toMatchObject({
      valid: true,
      context: {
        agent_resource_id: "fault-agent-id",
        agent_name: "fault-zeroing",
      },
    });
    expect(binding.valid).toBe(true);
    if (!binding.valid) throw new Error("expected valid binding");
    expect(binding.context).not.toHaveProperty("skill_resource_id");
    expect(binding.context).not.toHaveProperty("skill_name");
  });

  it("rejects a selected Task Skill outside the loaded Expert closure", () => {
    const binding = buildScenarioSubmissionBinding({
      baseContext: { mode: "flash" },
      selectedPill: { scenarioId: "professional", agentSlug: "fault-zeroing" },
      selectedChip: {
        scenarioId: "professional",
        agentSlug: "fault-zeroing",
        taskId: "fault-zeroing",
      },
      agent: { resource_id: "fault-agent-id", slug: "fault-zeroing" },
      agentDetails: { skills: ["other-skill-id"] },
      skills: [
        {
          resource_id: "fault-skill-id",
          slug: "fault-zeroing",
          name: "Fault zeroing",
        },
      ],
    });

    expect(binding).toEqual({
      valid: false,
      reason: "请重新选择当前专家下的任务后再提交。",
    });
  });

  it("selects the scenario and Agent pill for a configured agent", () => {
    const { result } = renderHook(() => useScenarioBinding());

    act(() => result.current.selectAgent("fault-zeroing"));

    expect(result.current.selectedScenario).toBe("professional");
    expect(result.current.selectedPill).toEqual({
      scenarioId: "professional",
      agentSlug: "fault-zeroing",
    });
  });

  it("starts on creative and derives Agent-only binding", () => {
    const { result } = renderHook(() => useScenarioBinding());

    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("office-docs"));

    expect(result.current.selectedScenario).toBe("daily");
    expect(result.current.activeBinding).toMatchObject({
      agentSlug: "office-docs",
      agentName: "办公文档",
      skillName: null,
      promptTemplate: null,
    });
  });

  it("keeps skill and prompt together and clears them on re-click", () => {
    const { result } = renderHook(() => useScenarioBinding("daily"));
    act(() => result.current.togglePill("office-docs"));
    act(() => result.current.toggleChip("word-editor"));

    expect(result.current.activeBinding).toMatchObject({
      skillName: "anthropic-docx",
      promptTemplate:
        "请处理以下 Word 文档。目标：[要完成的事情]；材料：[上传文件或粘贴内容]；要求：[格式/语气/保留内容]。请先概括处理方案，再完成修改并列出变更点与待确认项。",
    });
    expect(result.current.activeBinding.tags.at(-1)).toEqual({
      id: "task:word-editor",
      text: "anthropic-docx",
      kind: "task",
    });

    act(() => result.current.toggleChip("word-editor"));
    expect(result.current.activeBinding?.skillName).toBeNull();
    expect(result.current.activeBinding?.promptTemplate).toBeNull();
    expect(result.current.activeBinding.tags).toHaveLength(1);
  });

  it("does not cancel the active scenario and rejects an unknown chip", () => {
    const { result } = renderHook(() => useScenarioBinding("daily"));
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("office-docs"));
    act(() => result.current.toggleChip("missing"));

    expect(result.current.selectedScenario).toBe("daily");
    expect(result.current.selectedChip).toBeNull();
  });

  it("rejects a chip that does not belong to the selected Agent Pill", () => {
    const { result } = renderHook(() => useScenarioBinding("daily"));
    act(() => result.current.togglePill("office-docs"));
    act(() => result.current.toggleChip("excel-data-analysis"));

    expect(result.current.selectedChip).toBeNull();
  });
});
