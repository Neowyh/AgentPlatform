import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useScenarioBinding } from "@/core/scenarios/binding";

describe("useScenarioBinding", () => {
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
