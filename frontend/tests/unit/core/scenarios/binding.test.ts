import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useScenarioBinding } from "@/core/scenarios/hooks";

describe("useScenarioBinding", () => {
  it("starts on creative and derives Agent-only binding", () => {
    const { result } = renderHook(() => useScenarioBinding());

    expect(result.current.selectedScenario).toBe("creative");
    act(() => result.current.togglePill("daily", "office-docs"));

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
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() => result.current.toggleChip("daily", "office-docs", "word-editor"));

    expect(result.current.activeBinding).toMatchObject({
      skillName: "anthropic-docx",
      promptTemplate: "请帮我处理以下 Word 文档：[描述需求]",
    });
    expect(result.current.tags.at(-1)).toEqual({
      id: "task:word-editor",
      label: "anthropic-docx",
    });

    act(() => result.current.toggleChip("daily", "office-docs", "word-editor"));
    expect(result.current.activeBinding?.skillName).toBeNull();
    expect(result.current.activeBinding?.promptTemplate).toBeNull();
    expect(result.current.tags).toHaveLength(1);
  });

  it("does not cancel the active scenario and rejects an unknown chip", () => {
    const { result } = renderHook(() => useScenarioBinding("daily"));
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() => result.current.toggleChip("daily", "office-docs", "missing"));

    expect(result.current.selectedScenario).toBe("daily");
    expect(result.current.selectedChip).toBeNull();
  });

  it("rejects a chip that does not belong to the selected Agent Pill", () => {
    const { result } = renderHook(() => useScenarioBinding("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() =>
      result.current.toggleChip(
        "daily",
        "data-analysis",
        "excel-data-analysis",
      ),
    );

    expect(result.current.selectedChip).toBeNull();
  });
});
