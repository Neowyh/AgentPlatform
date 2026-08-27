import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useScenarioSelection } from "@/core/scenarios/hooks";

describe("useScenarioSelection", () => {
  it("initializes with null selections", () => {
    const { result } = renderHook(() => useScenarioSelection());
    expect(result.current.selectedScenario).toBeNull();
    expect(result.current.selectedPill).toBeNull();
    expect(result.current.selectedChip).toBeNull();
  });

  it("selectScenario sets scenario and clears pill/chip", () => {
    const { result } = renderHook(() => useScenarioSelection());
    act(() => result.current.selectScenario("daily"));
    expect(result.current.selectedScenario).toBe("daily");
    expect(result.current.selectedPill).toBeNull();
    expect(result.current.selectedChip).toBeNull();
  });

  it("togglePill sets pill and clears chip", () => {
    const { result } = renderHook(() => useScenarioSelection());
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    expect(result.current.selectedPill).toEqual({
      scenarioId: "daily",
      agentSlug: "office-docs",
    });
    expect(result.current.selectedChip).toBeNull();
  });

  it("togglePill deselects when clicking same pill", () => {
    const { result } = renderHook(() => useScenarioSelection());
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() => result.current.togglePill("daily", "office-docs"));
    expect(result.current.selectedPill).toBeNull();
  });

  it("toggleChip sets chip", () => {
    const { result } = renderHook(() => useScenarioSelection());
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() => result.current.toggleChip("daily", "office-docs", "word-editor"));
    expect(result.current.selectedChip).toEqual({
      scenarioId: "daily",
      agentSlug: "office-docs",
      taskId: "word-editor",
    });
  });

  it("toggleChip deselects when clicking same chip", () => {
    const { result } = renderHook(() => useScenarioSelection());
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() => result.current.toggleChip("daily", "office-docs", "word-editor"));
    act(() => result.current.toggleChip("daily", "office-docs", "word-editor"));
    expect(result.current.selectedChip).toBeNull();
  });

  it("resetSelection clears all", () => {
    const { result } = renderHook(() => useScenarioSelection());
    act(() => result.current.selectScenario("daily"));
    act(() => result.current.togglePill("daily", "office-docs"));
    act(() => result.current.resetSelection());
    expect(result.current.selectedScenario).toBeNull();
    expect(result.current.selectedPill).toBeNull();
    expect(result.current.selectedChip).toBeNull();
  });
});
