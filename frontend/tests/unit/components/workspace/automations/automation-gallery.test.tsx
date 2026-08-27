import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspace/automations",
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      automations: {
        title: "Automations",
        description: "Manage your workflow automations",
        create: "Create Automation",
        templates: "Templates",
        myAutomations: "My Automations",
      },
    },
  }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({
    children,
    defaultValue,
  }: {
    children: React.ReactNode;
    defaultValue?: string;
  }) => (
    <div data-testid="tabs" data-default-value={defaultValue}>
      {children}
    </div>
  ),
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tabs-list">{children}</div>
  ),
  TabsTrigger: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => (
    <button data-testid="tabs-trigger" data-value={value}>
      {children}
    </button>
  ),
  TabsContent: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => (
    <div data-testid="tabs-content" data-value={value}>
      {children}
    </div>
  ),
}));

vi.mock(
  "@/components/workspace/automations/automation-template-gallery",
  () => ({
    AutomationTemplateGallery: () => (
      <div data-testid="automation-template-gallery">Template Gallery</div>
    ),
  }),
);

vi.mock("@/components/workspace/automations/automation-list", () => ({
  AutomationList: () => (
    <div data-testid="automation-list">Automation List</div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AutomationGallery: typeof import("@/components/workspace/automations/automation-gallery").AutomationGallery;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/automations/automation-gallery");
  AutomationGallery = mod.AutomationGallery;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AutomationGallery", () => {
  test("renders page title and description", () => {
    render(<AutomationGallery />);
    expect(screen.getByText("Automations")).toBeInTheDocument();
    expect(
      screen.getByText("Manage your workflow automations"),
    ).toBeInTheDocument();
  });

  test("renders create automation button", () => {
    render(<AutomationGallery />);
    expect(screen.getByText("Create Automation")).toBeInTheDocument();
  });

  test("renders tabs for templates and my automations", () => {
    render(<AutomationGallery />);
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
    expect(screen.getByTestId("tabs-list")).toBeInTheDocument();
    expect(screen.getByText("Templates")).toBeInTheDocument();
    expect(screen.getByText("My Automations")).toBeInTheDocument();
  });

  test("renders tab content sections", () => {
    render(<AutomationGallery />);
    expect(
      screen.getByTestId("automation-template-gallery"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("automation-list")).toBeInTheDocument();
  });

  test("has correct default tab value", () => {
    render(<AutomationGallery />);
    const tabs = screen.getByTestId("tabs");
    expect(tabs.getAttribute("data-default-value")).toBe("templates");
  });

  test("has correct tab trigger values", () => {
    render(<AutomationGallery />);
    const triggers = screen.getAllByTestId("tabs-trigger");
    expect(triggers[0]?.getAttribute("data-value")).toBe("templates");
    expect(triggers[1]?.getAttribute("data-value")).toBe("my-automations");
  });
});
