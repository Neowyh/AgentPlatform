import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspace/resources",
  useRouter: () => ({ push: vi.fn() }),
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
      resources: {
        title: "Resources",
        description: "Manage your experts, skills, and connectors",
        experts: "Experts",
        skills: "Skills",
        connectors: "Connectors",
      },
      // 工作树为能力中心接入搜索框，占位符复用 capabilities 键。
      capabilities: {
        searchSkills: "Search skills by name or purpose",
        searchPlugins: "Search plugins by name or purpose",
      },
    },
  }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({
    children,
    defaultValue,
    value,
  }: {
    children: React.ReactNode;
    defaultValue?: string;
    value?: string;
  }) => (
    <div
      data-testid="tabs"
      data-default-value={defaultValue}
      data-value={value}
    >
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

vi.mock("@/components/workspace/resources/agent-list", () => ({
  AgentList: () => <div data-testid="agent-list">Agent List</div>,
}));

vi.mock("@/components/workspace/resources/skill-list", () => ({
  SkillList: () => <div data-testid="skill-list">Skill List</div>,
}));

vi.mock("@/components/workspace/resources/connector-list", () => ({
  ConnectorList: () => <div data-testid="connector-list">Connector List</div>,
}));

// 合并后 skills/connectors tab 真实挂载上游 PluginGallery/SkillGallery
//（台账裁决：上游组件必须挂进本地 [tab] 页）；二者内部走 react-query，
// 本测试只覆盖本页结构与本地列表，mock 之。
vi.mock("@/components/workspace/capabilities/skill-gallery", () => ({
  SkillGallery: () => <div data-testid="skill-gallery">Skill Gallery</div>,
}));

vi.mock("@/components/workspace/capabilities/plugin-gallery", () => ({
  PluginGallery: () => <div data-testid="plugin-gallery">Plugin Gallery</div>,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ResourceGallery: typeof import("@/components/workspace/resources/resource-gallery").ResourceGallery;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/resources/resource-gallery");
  ResourceGallery = mod.ResourceGallery;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ResourceGallery", () => {
  test("renders page title and description", () => {
    render(<ResourceGallery />);
    expect(screen.getByText("Resources")).toBeInTheDocument();
    expect(
      screen.getByText("Manage your experts, skills, and connectors"),
    ).toBeInTheDocument();
  });

  test("renders tabs for experts, skills, connectors", () => {
    render(<ResourceGallery />);
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
    expect(screen.getByTestId("tabs-list")).toBeInTheDocument();
    expect(screen.getByText("Experts")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("Connectors")).toBeInTheDocument();
  });

  test("renders tab content sections", () => {
    render(<ResourceGallery />);
    expect(screen.getByTestId("agent-list")).toBeInTheDocument();
    expect(screen.getByTestId("skill-list")).toBeInTheDocument();
    expect(screen.getByTestId("connector-list")).toBeInTheDocument();
  });

  test("uses the tab encoded by the route", () => {
    render(<ResourceGallery />);
    const tabs = screen.getByTestId("tabs");
    expect(tabs.getAttribute("data-value")).toBe("agents");
  });

  test("has correct tab trigger values", () => {
    render(<ResourceGallery />);
    const triggers = screen.getAllByTestId("tabs-trigger");
    expect(triggers[0]?.getAttribute("data-value")).toBe("agents");
    expect(triggers[1]?.getAttribute("data-value")).toBe("skills");
    expect(triggers[2]?.getAttribute("data-value")).toBe("connectors");
  });
});
