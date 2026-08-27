import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockAutomations = [
  {
    id: "automation-1",
    name: "My Daily Report",
    template_id: "daily-report",
    status: "active",
  },
  {
    id: "automation-2",
    name: "Team Weekly",
    template_id: "weekly-report",
    status: "inactive",
  },
];

vi.mock("@/core/automations", () => ({
  useAutomations: () => ({
    automations: mockAutomations,
    isLoading: false,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AutomationList: typeof import("@/components/workspace/automations/automation-list").AutomationList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/automations/automation-list");
  AutomationList = mod.AutomationList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AutomationList", () => {
  test("displays list of automations", () => {
    render(<AutomationList />);
    expect(screen.getByText("My Daily Report")).toBeInTheDocument();
    expect(screen.getByText("Team Weekly")).toBeInTheDocument();
  });

  test("displays automation status", () => {
    render(<AutomationList />);
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  test("displays automation IDs", () => {
    render(<AutomationList />);
    expect(screen.getByText("automation-1")).toBeInTheDocument();
    expect(screen.getByText("automation-2")).toBeInTheDocument();
  });
});
