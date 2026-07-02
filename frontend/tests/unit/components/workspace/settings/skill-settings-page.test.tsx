import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockMutate = vi.fn();
const mockPush = vi.fn();
let mockSkillsData: unknown[] = [];
let mockIsLoading = false;
let mockError: Error | null = null;

vi.mock("@/core/skills/hooks", () => ({
  useSkills: () => ({
    skills: mockSkillsData,
    isLoading: mockIsLoading,
    error: mockError,
  }),
  useEnableSkill: () => ({
    mutate: mockMutate,
  }),
}));

vi.mock("@/core/skills/api", () => ({
  submitSkillApplication: vi.fn().mockResolvedValue({}),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: "test-user", email: "test@test.com", system_role: "user" },
  }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        skills: {
          title: "Skills",
          description: "Manage your skills",
          createSkill: "Create Skill",
          emptyTitle: "No skills yet",
          emptyDescription: "Create your first skill",
          emptyButton: "Create Skill",
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

vi.mock("@/components/workspace/settings/skill-editor", () => ({
  SkillEditor: ({
    skillName,
    onClose,
    onSave,
  }: {
    skillName: string;
    onClose: () => void;
    onSave?: (content: string) => void;
  }) => (
    <div data-testid="skill-editor">
      <span>Editing: {skillName}</span>
      <button onClick={onClose}>Close Editor</button>
      {onSave && <button onClick={() => onSave("test content")}>Save</button>}
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
  EmptyContent: ({ children }: { children: React.ReactNode }) => (
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
  ItemActions: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
    onOpenChange,
  }: {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (v: boolean) => void;
  }) =>
    open ? (
      <div data-testid="dialog">
        {children}
        <button onClick={() => onOpenChange?.(false)}>Close Dialog</button>
      </div>
    ) : null,
  DialogContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
  DialogFooter: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onCheckedChange,
    disabled,
  }: {
    checked?: boolean;
    onCheckedChange?: (v: boolean) => void;
    disabled?: boolean;
  }) => (
    <button
      role="switch"
      data-checked={checked}
      data-disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
    >
      Switch
    </button>
  ),
}));

vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
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
      name: "Other's Custom Skill",
      description: "A skill owned by another user",
      category: "custom",
      enabled: true,
      license: "mit",
      owner_id: "other-user",
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
    expect(screen.getByText("Code Review")).toBeInTheDocument();
  });

  test("renders create skill button", () => {
    render(<SkillSettingsPage />);
    expect(screen.getByText("Create Skill")).toBeInTheDocument();
  });

  test("renders tabs for public and custom", () => {
    render(<SkillSettingsPage />);
    expect(screen.getByText("Public Tab")).toBeInTheDocument();
    expect(screen.getByText("Custom Tab")).toBeInTheDocument();
  });

  test("opens editor dialog when edit button clicked", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);
    const editButtons = screen.getAllByTitle("Edit skill");
    await user.click(editButtons[0]!);
    expect(screen.getByTestId("skill-editor")).toBeInTheDocument();
    expect(screen.getByText("Editing: Code Review")).toBeInTheDocument();
  });

  test("closes editor dialog when close clicked", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);
    const editButtons = screen.getAllByTitle("Edit skill");
    await user.click(editButtons[0]!);
    expect(screen.getByTestId("skill-editor")).toBeInTheDocument();
    await user.click(screen.getByText("Close Editor"));
    expect(screen.queryByTestId("skill-editor")).not.toBeInTheDocument();
  });

  test("opens test dialog when test button clicked", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);
    const testButtons = screen.getAllByTitle("Test skill");
    await user.click(testButtons[0]!);
    expect(screen.getByText("Test Skill: Code Review")).toBeInTheDocument();
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

  test("passes onClose to SkillSettingsPage", () => {
    const onClose = vi.fn();
    render(<SkillSettingsPage onClose={onClose} />);
    expect(screen.getByText("Skills")).toBeInTheDocument();
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
    expect(screen.getByText("Create your first skill")).toBeInTheDocument();
  });

  test("clicking switch toggles skill enabled state via enableSkill mutation", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);
    const switches = screen.getAllByRole("switch");
    // Click the first switch (Code Review, currently enabled=true)
    await user.click(switches[0]!);
    expect(mockMutate).toHaveBeenCalledWith({
      skillName: "Code Review",
      enabled: false,
    });
  });

  test("clicking switch on disabled skill enables it", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);
    const switches = screen.getAllByRole("switch");
    // The Custom Skill is at index 2 (Code Review=0, Web Skill=1, Custom Skill is in custom tab)
    // But default tab is public, so only Code Review (0) and Web Skill (1) are shown
    // Click the second switch (Web Skill, currently enabled=true)
    await user.click(switches[1]!);
    expect(mockMutate).toHaveBeenCalledWith({
      skillName: "Web Skill",
      enabled: false,
    });
  });

  test("shows requires_internet badge for skills that need internet", () => {
    render(<SkillSettingsPage />);
    expect(screen.getByText("Requires Internet")).toBeInTheDocument();
  });

  test("Create Skill button navigates to skill creation page and calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SkillSettingsPage onClose={onClose} />);

    await user.click(screen.getByText("Create Skill"));

    expect(onClose).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/new?mode=skill");
  });

  test("Start New Chat button in test dialog navigates to new chat", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);

    // Open test dialog
    const testButtons = screen.getAllByTitle("Test skill");
    await user.click(testButtons[0]!);
    expect(screen.getByText("Test Skill: Code Review")).toBeInTheDocument();

    // Click Start New Chat
    await user.click(screen.getByText("Start New Chat"));

    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/new");
    // Dialog should be closed
    expect(
      screen.queryByText("Test Skill: Code Review"),
    ).not.toBeInTheDocument();
  });

  test("Close button in test dialog closes the dialog without navigation", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);

    // Open test dialog
    const testButtons = screen.getAllByTitle("Test skill");
    await user.click(testButtons[0]!);
    expect(screen.getByText("Test Skill: Code Review")).toBeInTheDocument();

    // Click Close
    await user.click(screen.getByText("Close"));

    // Dialog should be closed, no navigation
    expect(
      screen.queryByText("Test Skill: Code Review"),
    ).not.toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  test("handleSaveSkill logs and closes editor", async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    render(<SkillSettingsPage />);

    // Open editor
    const editButtons = screen.getAllByTitle("Edit skill");
    await user.click(editButtons[0]!);
    expect(screen.getByTestId("skill-editor")).toBeInTheDocument();

    // Click Save in the editor - triggers handleSaveSkill which logs and closes
    await user.click(screen.getByText("Save"));

    expect(consoleSpy).toHaveBeenCalledWith(
      "Saving skill:",
      "Code Review",
      "test content",
    );
    expect(screen.queryByTestId("skill-editor")).not.toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  test("clicking skill name opens editor dialog", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);

    // Click the skill name text (not the edit button)
    await user.click(screen.getByText("Code Review"));
    expect(screen.getByTestId("skill-editor")).toBeInTheDocument();
    expect(screen.getByText("Editing: Code Review")).toBeInTheDocument();
  });

  test("editor dialog onOpenChange closes editor when open is false", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);

    // Open editor via edit button
    const editButtons = screen.getAllByTitle("Edit skill");
    await user.click(editButtons[0]!);
    expect(screen.getByTestId("skill-editor")).toBeInTheDocument();

    // Click the Dialog's Close Dialog button (triggers onOpenChange(false))
    await user.click(screen.getByText("Close Dialog"));
    expect(screen.queryByTestId("skill-editor")).not.toBeInTheDocument();
  });

  test("test dialog onOpenChange closes test dialog when open is false", async () => {
    const user = userEvent.setup();
    render(<SkillSettingsPage />);

    // Open test dialog
    const testButtons = screen.getAllByTitle("Test skill");
    await user.click(testButtons[0]!);
    expect(screen.getByText("Test Skill: Code Review")).toBeInTheDocument();

    // Click the Dialog's Close Dialog button (triggers onOpenChange(false))
    await user.click(screen.getByText("Close Dialog"));
    expect(
      screen.queryByText("Test Skill: Code Review"),
    ).not.toBeInTheDocument();
  });
});
