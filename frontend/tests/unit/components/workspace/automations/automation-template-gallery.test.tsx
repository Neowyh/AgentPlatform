import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockTemplates = [
  {
    id: "daily-report",
    name: "Daily Report",
    description: "Generate daily work reports",
    category: "reporting",
  },
  {
    id: "weekly-report",
    name: "Weekly Report",
    description: "Generate weekly work reports",
    category: "reporting",
  },
  {
    id: "meeting-minutes",
    name: "Meeting Minutes",
    description: "Summarize meeting discussions",
    category: "meetings",
  },
];

vi.mock("@/core/automations", () => ({
  useAutomationTemplates: () => ({
    templates: mockTemplates,
    isLoading: false,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AutomationTemplateGallery: typeof import("@/components/workspace/automations/automation-template-gallery").AutomationTemplateGallery;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/automations/automation-template-gallery");
  AutomationTemplateGallery = mod.AutomationTemplateGallery;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AutomationTemplateGallery", () => {
  test("displays list of automation templates", () => {
    render(<AutomationTemplateGallery />);
    expect(screen.getByText("Daily Report")).toBeInTheDocument();
    expect(screen.getByText("Weekly Report")).toBeInTheDocument();
    expect(screen.getByText("Meeting Minutes")).toBeInTheDocument();
  });

  test("displays template descriptions", () => {
    render(<AutomationTemplateGallery />);
    expect(screen.getByText("Generate daily work reports")).toBeInTheDocument();
    expect(
      screen.getByText("Generate weekly work reports"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Summarize meeting discussions"),
    ).toBeInTheDocument();
  });

  test("displays template categories", () => {
    render(<AutomationTemplateGallery />);
    expect(screen.getAllByText("reporting")).toHaveLength(2);
    expect(screen.getByText("meetings")).toBeInTheDocument();
  });
});
