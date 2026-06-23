import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockSetTheme = vi.fn();
const mockChangeLocale = vi.fn();
let mockSystemTheme = "light";
let mockTheme: string | null = "light";

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
    systemTheme: mockSystemTheme,
  }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        appearance: {
          themeTitle: "Theme",
          themeDescription: "Select your theme",
          system: "System",
          systemDescription: "Follow system preference",
          light: "Light",
          lightDescription: "Light theme",
          dark: "Dark",
          darkDescription: "Dark theme",
          languageTitle: "Language",
          languageDescription: "Select your language",
        },
      },
    },
    locale: "en-US",
    changeLocale: mockChangeLocale,
  }),
}));

vi.mock("@/core/i18n", () => ({
  enUS: { locale: { localName: "English" } },
  zhCN: { locale: { localName: "Chinese" } },
  isLocale: (v: string) => ["en-US", "zh-CN"].includes(v),
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

vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    value,
    onValueChange,
  }: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (v: string) => void;
  }) => (
    <div data-testid="select" data-value={value}>
      <button onClick={() => onValueChange?.("zh-CN")}>Change</button>
      <button onClick={() => onValueChange?.("invalid-locale")}>Invalid</button>
      {children}
    </div>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectValue: () => <span>Select Value</span>,
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectItem: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => <option value={value}>{children}</option>,
}));

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr data-testid="separator" />,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AppearanceSettingsPage: typeof import("@/components/workspace/settings/appearance-settings-page").AppearanceSettingsPage;

beforeEach(async () => {
  vi.clearAllMocks();
  mockSystemTheme = "light";
  mockTheme = "light";
  const mod =
    await import("@/components/workspace/settings/appearance-settings-page");
  AppearanceSettingsPage = mod.AppearanceSettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AppearanceSettingsPage", () => {
  test("renders theme section", () => {
    render(<AppearanceSettingsPage />);
    expect(screen.getByText("Theme")).toBeInTheDocument();
  });

  test("renders language section", () => {
    render(<AppearanceSettingsPage />);
    expect(screen.getByText("Language")).toBeInTheDocument();
  });

  test("renders three theme options", () => {
    render(<AppearanceSettingsPage />);
    expect(screen.getByText("System")).toBeInTheDocument();
    expect(screen.getByText("Light")).toBeInTheDocument();
    expect(screen.getByText("Dark")).toBeInTheDocument();
  });

  test("calls setTheme when theme card clicked", async () => {
    const user = userEvent.setup();
    render(<AppearanceSettingsPage />);

    const darkButton = screen.getByText("Dark").closest("button")!;
    await user.click(darkButton);
    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  test("calls setTheme with system when system card clicked", async () => {
    const user = userEvent.setup();
    render(<AppearanceSettingsPage />);

    const systemButton = screen.getByText("System").closest("button")!;
    await user.click(systemButton);
    expect(mockSetTheme).toHaveBeenCalledWith("system");
  });

  test("renders theme descriptions", () => {
    render(<AppearanceSettingsPage />);
    expect(screen.getByText("Follow system preference")).toBeInTheDocument();
    expect(screen.getByText("Light theme")).toBeInTheDocument();
    expect(screen.getByText("Dark theme")).toBeInTheDocument();
  });

  test("renders separator between sections", () => {
    render(<AppearanceSettingsPage />);
    expect(screen.getByTestId("separator")).toBeInTheDocument();
  });

  test("renders language selector", () => {
    render(<AppearanceSettingsPage />);
    expect(screen.getByTestId("select")).toBeInTheDocument();
  });

  test("calls changeLocale when valid locale selected via Change button", async () => {
    const user = userEvent.setup();
    render(<AppearanceSettingsPage />);

    // Click the Change button in the Select mock, which triggers onValueChange("zh-CN")
    await user.click(screen.getByText("Change"));

    expect(mockChangeLocale).toHaveBeenCalledWith("zh-CN");
  });

  test("system theme preview uses dark preview when systemTheme is dark", () => {
    mockSystemTheme = "dark";
    render(<AppearanceSettingsPage />);

    // The System card should render with dark preview styles
    const systemCard = screen.getByText("System").closest("button");
    expect(systemCard).toBeInTheDocument();

    // The preview div inside the System card should have dark-specific classes
    const previewDiv = systemCard!.querySelector("[class*='bg-neutral-900']");
    expect(previewDiv).toBeInTheDocument();
  });

  test("system theme preview uses light preview when systemTheme is light", () => {
    mockSystemTheme = "light";
    render(<AppearanceSettingsPage />);

    const systemCard = screen.getByText("System").closest("button");
    expect(systemCard).toBeInTheDocument();

    // The preview div should have light-specific classes
    const previewDiv = systemCard!.querySelector("[class*='bg-white']");
    expect(previewDiv).toBeInTheDocument();
  });

  test("light theme card always uses light preview regardless of systemTheme", () => {
    mockSystemTheme = "dark";
    render(<AppearanceSettingsPage />);

    const lightCard = screen.getByText("Light").closest("button");
    expect(lightCard).toBeInTheDocument();

    const previewDiv = lightCard!.querySelector("[class*='bg-white']");
    expect(previewDiv).toBeInTheDocument();
  });

  test("dark theme card always uses dark preview regardless of systemTheme", () => {
    mockSystemTheme = "light";
    render(<AppearanceSettingsPage />);

    const darkCard = screen.getByText("Dark").closest("button");
    expect(darkCard).toBeInTheDocument();

    const previewDiv = darkCard!.querySelector("[class*='bg-neutral-900']");
    expect(previewDiv).toBeInTheDocument();
  });

  test("calls setTheme when light card clicked", async () => {
    const user = userEvent.setup();
    render(<AppearanceSettingsPage />);

    const lightButton = screen.getByText("Light").closest("button")!;
    await user.click(lightButton);
    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });

  test("defaults to system theme when theme is null", () => {
    mockTheme = null;
    render(<AppearanceSettingsPage />);

    // The System card should be active (currentTheme defaults to "system")
    const systemButton = screen.getByText("System").closest("button")!;
    expect(systemButton.className).toContain("border-primary");
  });

  test("does not call changeLocale for invalid locale", async () => {
    const user = userEvent.setup();
    render(<AppearanceSettingsPage />);

    // Click the Invalid button which triggers onValueChange with invalid locale
    await user.click(screen.getByText("Invalid"));

    // changeLocale should NOT be called for invalid locale
    expect(mockChangeLocale).not.toHaveBeenCalled();
  });
});
