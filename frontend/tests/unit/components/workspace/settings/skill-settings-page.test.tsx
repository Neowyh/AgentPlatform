import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockSkillsData: unknown[] = [];
let mockIsLoading = false;
let mockError: Error | null = null;

vi.mock("@/core/skills/hooks", () => ({
  useSkills: () => ({
    skills: mockSkillsData,
    isLoading: mockIsLoading,
    error: mockError,
  }),
}));

vi.mock("@/components/workspace/settings/settings-section", () => ({
  SettingsSection: ({
    title,
    description,
    children,
  }: {
    title: string;
    description?: string;
    children: React.ReactNode;
  }) => (
    <div data-testid="settings-section">
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </div>
  ),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({
    children,
    onValueChange,
  }: {
    children: React.ReactNode;
    defaultValue?: string;
    onValueChange?: (v: string) => void;
  }) => (
    <div data-testid="tabs">
      <button onClick={() => onValueChange?.("public")}>Public Tab</button>
      <button onClick={() => onValueChange?.("custom")}>Custom Tab</button>
      {children}
    </div>
  ),
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsTrigger: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => <button data-value={value}>{children}</button>,
}));

vi.mock("@/components/ui/empty", () => ({
  Empty: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="empty">{children}</div>
  ),
  EmptyHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  EmptyMedia: ({
    children,
  }: {
    children: React.ReactNode;
    variant?: string;
  }) => <div>{children}</div>,
  EmptyTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  EmptyDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/ui/item", () => ({
  Item: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
    variant?: string;
  }) => (
    <div data-testid="item" className={className}>
      {children}
    </div>
  ),
  ItemContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  ItemTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  ItemDescription: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    variant,
    className,
  }: {
    children: React.ReactNode;
    variant?: string;
    className?: string;
  }) => (
    <span data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        skills: {
          title: "Skills",
          description: "Manage your skills",
          emptyTitle: "No skills yet",
          emptyDescription: "No skills available",
        },
      },
      common: {
        loading: "Loading...",
        public: "Public",
        custom: "Custom",
      },
    },
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let SkillSettingsPage: typeof import("@/components/workspace/settings/skill-settings-page").SkillSettingsPage;

beforeEach(async () => {
  vi.clearAllMocks();
  mockSkillsData = [
    {
      name: "Code Review",
      description: "Reviews code for quality",
      category: "public",
      enabled: true,
      license: "mit",
    },
    {
      name: "Custom Skill",
      description: "A custom skill",
      category: "custom",
      enabled: false,
      license: "mit",
      owner_id: "test-user",
    },
    {
      name: "Web Skill",
      description: "Needs internet connection",
      category: "public",
      enabled: true,
      license: "requires_internet",
    },
  ];
  mockIsLoading = false;
  mockError = null;
  const mod =
    await import("@/components/workspace/settings/skill-settings-page");
  SkillSettingsPage = mod.SkillSettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SkillSettingsPage", () => {
  test("renders the settings section with title", () => {
    render(<SkillSettingsPage />);
    expect(screen.getByText("Skills")).toBeInTheDocument();
  });

  test("renders description", () => {
    render(<SkillSettingsPage />);
    expect(screen.getByText("Manage your skills")).toBeInTheDocument();
  });

  test("renders skill cards when skills are loaded", () => {
    render(<SkillSettingsPage />);
    // Default tab is public, so only public skills are shown
    expect(screen.getByText("Code Review")).toBeInTheDocument();
    expect(screen.getByText("Web Skill")).toBeInTheDocument();
  });

  test("renders tabs for public and custom", () => {
    render(<SkillSettingsPage />);
    expect(screen.getByText("Public Tab")).toBeInTheDocument();
    expect(screen.getByText("Custom Tab")).toBeInTheDocument();
  });

  test("shows loading state", () => {
    mockIsLoading = true;
    mockSkillsData = [];
    render(<SkillSettingsPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("shows error state", () => {
    mockError = new Error("Failed to load");
    mockSkillsData = [];
    render(<SkillSettingsPage />);
    expect(screen.getByText("Error: Failed to load")).toBeInTheDocument();
  });

  test("filters skills by custom category when custom tab clicked", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);

    // Initially shows only public skills
    expect(screen.getByText("Code Review")).toBeInTheDocument();
    expect(screen.getByText("Web Skill")).toBeInTheDocument();
    expect(screen.queryByText("Custom Skill")).not.toBeInTheDocument();

    // Switch to custom tab
    await user.click(screen.getByText("Custom Tab"));

    // Now shows only custom skills
    expect(screen.queryByText("Code Review")).not.toBeInTheDocument();
    expect(screen.queryByText("Web Skill")).not.toBeInTheDocument();
    expect(screen.getByText("Custom Skill")).toBeInTheDocument();
  });

  test("shows EmptySkill when no skills match filter", async () => {
    const user = userEvent.setup();
    // Only provide public skills
    mockSkillsData = [
      {
        name: "Code Review",
        category: "public",
        enabled: true,
        license: "mit",
        description: "Reviews code",
      },
    ];
    render(<SkillSettingsPage />);

    // Initially shows public skills
    expect(screen.getByText("Code Review")).toBeInTheDocument();

    // Switch to custom tab - no custom skills
    await user.click(screen.getByText("Custom Tab"));

    // EmptySkill should be shown
    expect(screen.getByText("No skills yet")).toBeInTheDocument();
    expect(screen.getByText("No skills available")).toBeInTheDocument();
  });

  test("skill cards display name and description", () => {
    render(<SkillSettingsPage />);
    // Default tab is public, so only public skills are shown
    expect(screen.getByText("Code Review")).toBeInTheDocument();
    expect(screen.getByText("Reviews code for quality")).toBeInTheDocument();
    expect(screen.getByText("Web Skill")).toBeInTheDocument();
    expect(screen.getByText("Needs internet connection")).toBeInTheDocument();
  });

  test("skill cards display category badge", () => {
    render(<SkillSettingsPage />);
    const badges = screen.getAllByText("public");
    expect(badges.length).toBeGreaterThan(0);
  });
});
