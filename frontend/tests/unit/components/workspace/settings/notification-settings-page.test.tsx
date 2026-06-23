import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockRequestPermission = vi.fn();
const mockShowNotification = vi.fn();

let mockPermission: "default" | "granted" | "denied" = "default";
let mockIsSupported = true;
let mockNotificationEnabled = false;

vi.mock("@/core/notification/hooks", () => ({
  useNotification: () => ({
    permission: mockPermission,
    isSupported: mockIsSupported,
    requestPermission: mockRequestPermission,
    showNotification: mockShowNotification,
  }),
}));

vi.mock("@/core/settings", () => ({
  useLocalSettings: () => [
    { notification: { enabled: mockNotificationEnabled } },
    vi.fn(),
  ],
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        notification: {
          title: "Notifications",
          description: "Manage notification settings",
          notSupported: "Notifications not supported",
          requestPermission: "Enable Notifications",
          deniedHint: "Notifications are blocked",
          testButton: "Send Test",
          testTitle: "Test",
          testBody: "Test notification body",
        },
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
    description?: React.ReactNode;
    children: React.ReactNode;
  }) => (
    <div data-testid="settings-section">
      <h3>{title}</h3>
      {description && <div>{description}</div>}
      {children}
    </div>
  ),
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    disabled,
    onCheckedChange,
  }: {
    checked?: boolean;
    disabled?: boolean;
    onCheckedChange?: (v: boolean) => void;
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

// ── Dynamic import ───────────────────────────────────────────────────────────

let NotificationSettingsPage: typeof import("@/components/workspace/settings/notification-settings-page").NotificationSettingsPage;

beforeEach(async () => {
  vi.clearAllMocks();
  mockPermission = "default";
  mockIsSupported = true;
  mockNotificationEnabled = false;
  const mod =
    await import("@/components/workspace/settings/notification-settings-page");
  NotificationSettingsPage = mod.NotificationSettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("NotificationSettingsPage", () => {
  test("renders not supported message when not supported", () => {
    mockIsSupported = false;
    render(<NotificationSettingsPage />);
    expect(screen.getByText("Notifications not supported")).toBeInTheDocument();
  });

  test("renders notification settings when supported", () => {
    render(<NotificationSettingsPage />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  test("shows enable button when permission is default", () => {
    mockPermission = "default";
    render(<NotificationSettingsPage />);
    expect(screen.getByText("Enable Notifications")).toBeInTheDocument();
  });

  test("calls requestPermission when enable button clicked", async () => {
    const user = userEvent.setup();
    mockPermission = "default";
    render(<NotificationSettingsPage />);
    await user.click(screen.getByText("Enable Notifications"));
    expect(mockRequestPermission).toHaveBeenCalledTimes(1);
  });

  test("shows denied hint when permission is denied", () => {
    mockPermission = "denied";
    render(<NotificationSettingsPage />);
    expect(screen.getByText("Notifications are blocked")).toBeInTheDocument();
  });

  test("shows test button when permission is granted and enabled", () => {
    mockPermission = "granted";
    mockNotificationEnabled = true;
    render(<NotificationSettingsPage />);
    expect(screen.getByText("Send Test")).toBeInTheDocument();
  });

  test("calls showNotification when test button clicked", async () => {
    const user = userEvent.setup();
    mockPermission = "granted";
    mockNotificationEnabled = true;
    render(<NotificationSettingsPage />);
    await user.click(screen.getByText("Send Test"));
    expect(mockShowNotification).toHaveBeenCalledWith("Test", {
      body: "Test notification body",
    });
  });

  test("hides enable button when permission is granted", () => {
    mockPermission = "granted";
    render(<NotificationSettingsPage />);
    expect(screen.queryByText("Enable Notifications")).not.toBeInTheDocument();
  });

  test("does not show test button when permission is not granted", () => {
    mockPermission = "default";
    render(<NotificationSettingsPage />);
    expect(screen.queryByText("Send Test")).not.toBeInTheDocument();
  });
});
