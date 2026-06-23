import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockUser = { email: "test@example.com", system_role: "admin" };
const mockLogout = vi.fn();

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser, logout: mockLogout }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        account: {
          profileTitle: "Profile",
          email: "Email",
          role: "Role",
          changePasswordTitle: "Change Password",
          changePasswordDescription: "Update your password",
          currentPassword: "Current password",
          newPassword: "New password",
          confirmNewPassword: "Confirm new password",
          updatePassword: "Update Password",
          updating: "Updating...",
          passwordChangedSuccess: "Password changed successfully",
          passwordMismatch: "Passwords do not match",
          passwordTooShort: "Password too short",
          networkError: "Network error",
          signOut: "Sign Out",
        },
      },
      common: {
        cancel: "Cancel",
      },
    },
  }),
}));

const mockFetch = vi.fn();
vi.mock("@/core/api/fetcher", () => ({
  fetch: (...args: unknown[]) => mockFetch(...args),
  getCsrfHeaders: () => ({ "x-csrf-token": "mock" }),
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
      {title && <h3>{title}</h3>}
      {description && <p>{description}</p>}
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AccountSettingsPage: typeof import("@/components/workspace/settings/account-settings-page").AccountSettingsPage;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/settings/account-settings-page");
  AccountSettingsPage = mod.AccountSettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AccountSettingsPage", () => {
  test("renders profile section with user email", () => {
    render(<AccountSettingsPage />);
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  test("renders profile section with user role", () => {
    render(<AccountSettingsPage />);
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  test("renders change password form", () => {
    render(<AccountSettingsPage />);
    expect(screen.getByPlaceholderText("Current password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("New password")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Confirm new password"),
    ).toBeInTheDocument();
  });

  test("renders sign out button", () => {
    render(<AccountSettingsPage />);
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
  });

  test("calls logout when sign out clicked", async () => {
    const user = userEvent.setup();
    render(<AccountSettingsPage />);
    await user.click(screen.getByText("Sign Out"));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  test("shows error when passwords do not match", async () => {
    const user = userEvent.setup();
    render(<AccountSettingsPage />);

    await user.type(
      screen.getByPlaceholderText("Current password"),
      "oldpass123",
    );
    await user.type(screen.getByPlaceholderText("New password"), "newpass123");
    await user.type(
      screen.getByPlaceholderText("Confirm new password"),
      "different123",
    );

    await user.click(screen.getByRole("button", { name: /Update Password/i }));

    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
  });

  test("shows error when password is too short", async () => {
    const user = userEvent.setup();
    render(<AccountSettingsPage />);

    await user.type(
      screen.getByPlaceholderText("Current password"),
      "oldpass123",
    );
    await user.type(screen.getByPlaceholderText("New password"), "short");
    await user.type(
      screen.getByPlaceholderText("Confirm new password"),
      "short",
    );

    await user.click(screen.getByRole("button", { name: /Update Password/i }));

    expect(screen.getByText("Password too short")).toBeInTheDocument();
  });

  test("shows success message on successful password change", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    render(<AccountSettingsPage />);

    await user.type(
      screen.getByPlaceholderText("Current password"),
      "oldpass123",
    );
    await user.type(
      screen.getByPlaceholderText("New password"),
      "newpass12345",
    );
    await user.type(
      screen.getByPlaceholderText("Confirm new password"),
      "newpass12345",
    );

    await user.click(screen.getByRole("button", { name: /Update Password/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Password changed successfully"),
      ).toBeInTheDocument();
    });
  });

  test("shows error on API error response", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Invalid credentials" }),
    });
    render(<AccountSettingsPage />);

    await user.type(
      screen.getByPlaceholderText("Current password"),
      "wrongpass",
    );
    await user.type(
      screen.getByPlaceholderText("New password"),
      "newpass12345",
    );
    await user.type(
      screen.getByPlaceholderText("Confirm new password"),
      "newpass12345",
    );

    await user.click(screen.getByRole("button", { name: /Update Password/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  test("shows network error on fetch exception", async () => {
    const user = userEvent.setup();
    mockFetch.mockRejectedValue(new Error("Network failure"));
    render(<AccountSettingsPage />);

    await user.type(
      screen.getByPlaceholderText("Current password"),
      "oldpass123",
    );
    await user.type(
      screen.getByPlaceholderText("New password"),
      "newpass12345",
    );
    await user.type(
      screen.getByPlaceholderText("Confirm new password"),
      "newpass12345",
    );

    await user.click(screen.getByRole("button", { name: /Update Password/i }));

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
