import {
  render,
  screen,
  cleanup,
  waitFor,
  fireEvent,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { mockPush, mockUseAuth, mockFetch } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockUseAuth: vi.fn().mockReturnValue({ isAuthenticated: false, user: null }),
  mockFetch: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "dark", resolvedTheme: "dark" }),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/core/auth/types", () => ({
  parseAuthError: (data: any) => ({ message: data?.detail || "Error" }),
}));

vi.mock("@/core/api/fetcher", () => ({
  getCsrfHeaders: () => ({ "x-csrf-token": "test-token" }),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/components/ui/flickering-grid", () => ({
  FlickeringGrid: (props: any) => <div data-testid="flickering-grid" />,
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input {...props} />,
}));

import SetupPage from "@/app/(auth)/setup/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SetupPage", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, user: null });
    mockPush.mockReset();
    globalThis.fetch = mockFetch;
  });

  test("shows loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<SetupPage />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  test("enters change_password mode when authenticated with needs_setup", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true, email: "admin@test.com" },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Complete admin account setup"),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Complete Setup")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Current password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("New password")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Confirm new password"),
    ).toBeInTheDocument();
  });

  test("redirects to /workspace when authenticated without needs_setup", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: false },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace");
    });
  });

  test("shows iDeer branding in change_password mode", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    render(<SetupPage />);

    await waitFor(() => {
      const headings = screen.getAllByText("iDeer");
      expect(headings.length).toBeGreaterThanOrEqual(1);
    });
  });

  test("renders flickering grid in change_password mode", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByTestId("flickering-grid")).toBeInTheDocument();
    });
  });

  test("change_password mode shows password mismatch error", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "old" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "different" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });
  });

  test("change_password mode shows short password error", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "short" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "short" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(
        screen.getByText("Password must be at least 8 characters"),
      ).toBeInTheDocument();
    });
  });

  test("change_password mode has correct form fields", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Your email")).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText("Your email")).toHaveAttribute(
      "type",
      "email",
    );
    expect(screen.getByPlaceholderText("Current password")).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByPlaceholderText("New password")).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByPlaceholderText("Confirm new password")).toHaveAttribute(
      "type",
      "password",
    );
  });

  test("change_password mode shows setup instructions", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Set your real email and a new password."),
      ).toBeInTheDocument();
    });
  });

  // --- init_admin mode via setup-status fetch ---

  test("enters init_admin mode when setup-status returns needs_setup=true", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: true }),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByText("Create admin account")).toBeInTheDocument();
    });

    expect(screen.getByText("Create Admin Account")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password")).toBeInTheDocument();
  });

  test("redirects to /login when setup-status returns needs_setup=false", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: false }),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  test("redirects to /login when setup-status fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    render(<SetupPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  // --- init_admin form rendering ---

  test("init_admin mode shows iDeer branding and instructions", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: true }),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByText("Create admin account")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Set up the administrator account to get started."),
    ).toBeInTheDocument();
    const headings = screen.getAllByText("iDeer");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  test("init_admin mode renders flickering grid", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: true }),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByTestId("flickering-grid")).toBeInTheDocument();
    });
  });

  // --- init_admin form submission ---

  test("init_admin shows password mismatch error", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: true }),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "different123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });
  });

  test("init_admin successful submission redirects to /workspace", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: true }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace");
    });
  });

  test("init_admin shows error on API failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: true }),
        });
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: "Admin already exists" }),
      });
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Admin already exists")).toBeInTheDocument();
    });
  });

  test("init_admin shows network error on fetch failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: true }),
        });
      }
      return Promise.reject(new Error("Network error"));
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please try again."),
      ).toBeInTheDocument();
    });
  });

  test("init_admin shows loading state during submission", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: true }),
        });
      }
      return new Promise(() => {}); // never resolves
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Creating account…")).toBeInTheDocument();
    });
  });

  test("init_admin sends correct API request body", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: true }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/initialize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: "admin@test.com",
          password: "password123",
        }),
      });
    });
  });

  // --- change_password API call paths ---

  test("change_password successful submission redirects to /workspace", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "newpassword123" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace");
    });
  });

  test("change_password shows error on API failure", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Invalid current password" }),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "wrongpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "newpassword123" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Invalid current password")).toBeInTheDocument();
    });
  });

  test("change_password shows network error on fetch failure", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    mockFetch.mockRejectedValue(new Error("Network error"));

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "newpassword123" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(
        screen.getByText("Network error. Please try again."),
      ).toBeInTheDocument();
    });
  });

  test("change_password shows loading state during submission", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "newpassword123" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Setting up…")).toBeInTheDocument();
    });
  });

  test("change_password sends correct API request with CSRF headers", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Your email"), {
      target: { value: "admin@test.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "newpassword123" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/change-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": "test-token",
        },
        credentials: "include",
        body: JSON.stringify({
          current_password: "oldpass",
          new_password: "newpassword123",
          new_email: "admin@test.com",
        }),
      });
    });
  });

  test("change_password sends undefined new_email when email is empty", async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { needs_setup: true },
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    render(<SetupPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Current password"),
      ).toBeInTheDocument();
    });

    // Leave email empty
    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "newpassword123" },
    });

    const form = screen.getByPlaceholderText("Your email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/change-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": "test-token",
        },
        credentials: "include",
        body: JSON.stringify({
          current_password: "oldpass",
          new_password: "newpassword123",
          new_email: undefined,
        }),
      });
    });
  });
});
