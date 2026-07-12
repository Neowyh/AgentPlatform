import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/styles/globals.css", () => ({}));
vi.mock("katex/dist/katex.min.css", () => ({}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ agent_name: "test-agent" }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: any) => (
    <a href={href} data-testid="next-link">
      {children}
    </a>
  ),
}));

const mockUseAgent = vi.fn(() => ({
  agent: {
    name: "test-agent",
    description: "A test agent",
    model: "gpt-4",
    read_only: false,
    tool_groups: ["file:read", "bash"],
    skills: ["coding"],
    soul: "You are helpful.",
  },
  isLoading: false,
  error: null,
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en",
    t: {
      common: { loading: "Loading..." },
      agents: { backToGallery: "Back to Gallery" },
    },
  }),
}));

vi.mock("@/core/agents", () => ({
  useAgent: (...args: any[]) => (mockUseAgent as any)(...args),
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, variant }: any) => (
    <span data-testid="badge" data-variant={variant}>
      {children}
    </span>
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, variant, onClick, asChild, ...props }: any) => (
    <button data-testid="button" data-variant={variant} onClick={onClick}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: any) => <div data-testid="card">{children}</div>,
  CardContent: ({ children }: any) => (
    <div data-testid="card-content">{children}</div>
  ),
  CardDescription: ({ children }: any) => (
    <div data-testid="card-description">{children}</div>
  ),
  CardHeader: ({ children }: any) => (
    <div data-testid="card-header">{children}</div>
  ),
  CardTitle: ({ children }: any) => (
    <div data-testid="card-title">{children}</div>
  ),
}));

vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="workspace-breadcrumb" />,
}));

import AgentDetailPage from "@/app/workspace/agents/[agent_name]/page";

afterEach(() => {
  vi.clearAllMocks();
  mockUseAgent.mockReturnValue({
    agent: {
      name: "test-agent",
      description: "A test agent",
      model: "gpt-4",
      read_only: false,
      tool_groups: ["file:read", "bash"],
      skills: ["coding"],
      soul: "You are helpful.",
    },
    isLoading: false,
    error: null,
  });
});

describe("AgentDetailPage", () => {
  test("renders agent name", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("test-agent")).toBeInTheDocument();
  });

  test("renders agent description", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("A test agent")).toBeInTheDocument();
  });

  test("renders workspace breadcrumb", () => {
    render(<AgentDetailPage />);
    expect(screen.getByTestId("workspace-breadcrumb")).toBeInTheDocument();
  });

  test("renders model badge", () => {
    render(<AgentDetailPage />);
    const badges = screen.getAllByTestId("badge");
    const modelBadge = badges.find(
      (b) =>
        b.textContent === "gpt-4" &&
        b.getAttribute("data-variant") === "secondary",
    );
    expect(modelBadge).toBeDefined();
    expect(modelBadge!.textContent).toBe("gpt-4");
    expect(modelBadge!.getAttribute("data-variant")).toBe("secondary");
  });

  test("renders stat cards", () => {
    render(<AgentDetailPage />);
    const cards = screen.getAllByTestId("card");
    expect(cards.length).toBeGreaterThanOrEqual(4);
  });

  test("renders edit agent link", () => {
    render(<AgentDetailPage />);
    const links = screen.getAllByTestId("next-link");
    const editLink = links.find((l) =>
      l.getAttribute("href")?.includes("/edit"),
    );
    expect(editLink).toBeDefined();
    expect(editLink!.getAttribute("href")).toMatch(/\/edit$/);
  });

  test("renders configuration section with tool groups", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("file:read")).toBeInTheDocument();
    expect(screen.getByText("bash")).toBeInTheDocument();
  });

  test("renders skills section", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("coding")).toBeInTheDocument();
  });

  test("renders soul section", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("You are helpful.")).toBeInTheDocument();
  });

  test("renders quick actions", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("Start Chat")).toBeInTheDocument();
    expect(screen.getByText("Edit Configuration")).toBeInTheDocument();
  });
});

describe("AgentDetailPage - Loading state", () => {
  test("shows loading indicator", () => {
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: true,
      error: null,
    } as any);
    render(<AgentDetailPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

describe("AgentDetailPage - Error state", () => {
  test("shows error message when agent not found", () => {
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: false,
      error: null,
    } as any);
    render(<AgentDetailPage />);
    expect(screen.getByText("Agent not found")).toBeInTheDocument();
  });

  test("shows error message when error occurs", () => {
    mockUseAgent.mockReturnValue({
      agent: null,
      isLoading: false,
      error: new Error("Network error"),
    } as any);
    render(<AgentDetailPage />);
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });
});
