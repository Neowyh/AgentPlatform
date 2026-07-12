import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { mockPush, mockGetParam, mockUseAuth, mockFetch } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockGetParam: vi.fn().mockReturnValue(null),
  mockUseAuth: vi.fn().mockReturnValue({ isAuthenticated: false }),
  mockFetch: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: mockGetParam }),
}));

vi.mock("next/link", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: React.forwardRef(({ children, href, ...props }: any, ref: any) =>
      React.createElement("a", { ...props, ref, href }, children),
    ),
  };
});

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "dark", resolvedTheme: "dark" }),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/core/auth/types", () => ({
  parseAuthError: (data: any) => ({ message: data?.detail || "Error" }),
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

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn((msg: string) => {
      const el = document.createElement("div");
      el.setAttribute("data-testid", "toast-error");
      el.textContent = msg;
      document.body.appendChild(el);
    }),
  },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      auth: {
        signInTitle: "Sign in to your account",
        createAccountTitle: "Create a new account",
        email: "Email",
        password: "Password",
        signIn: "Sign In",
        createAccount: "Create Account",
        noAccount: "Don't have an account? Sign up",
        hasAccount: "Already have an account? Sign in",
        backToHome: "Back to home",
        pleaseWait: "Please wait...",
        errorInvalidCredentials: "Invalid credentials",
        errorAccountDisabled: "Account disabled",
        errorTooManyAttempts: "Too many attempts",
        errorNetwork: "Network error. Please try again.",
      },
    },
  }),
}));

vi.mock("globalThis", () => ({}));

import LoginPage from "@/app/(auth)/login/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  document
    .querySelectorAll('[data-testid="toast-error"]')
    .forEach((el) => el.remove());
});

describe("LoginPage", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    mockGetParam.mockReturnValue(null);
    mockPush.mockReset();
    mockFetch.mockReset();
    globalThis.fetch = mockFetch;
    // Default: setup-status returns no setup needed
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: false }),
    });
  });

  test("renders iDeer brand", () => {
    render(<LoginPage />);
    expect(screen.getByText("iDeer")).toBeInTheDocument();
  });

  test("renders sign in form", () => {
    render(<LoginPage />);
    expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  test("renders email and password inputs", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  test("renders sign up toggle", () => {
    render(<LoginPage />);
    expect(
      screen.getByText("Don't have an account? Sign up"),
    ).toBeInTheDocument();
  });

  test("renders back to home link", () => {
    render(<LoginPage />);
    expect(screen.getByText(/Back to home/)).toBeInTheDocument();
  });

  test("renders flickering grid background", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("flickering-grid")).toBeInTheDocument();
  });

  test("toggles to register mode", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    expect(screen.getByText("Create a new account")).toBeInTheDocument();
    expect(screen.getByText("Create Account")).toBeInTheDocument();
    expect(
      screen.getByText("Already have an account? Sign in"),
    ).toBeInTheDocument();
  });

  test("toggles back to login mode", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));
    fireEvent.click(screen.getByText("Already have an account? Sign in"));

    expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  test("clears error when toggling mode", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));
    fireEvent.click(screen.getByText("Already have an account? Sign in"));

    expect(
      screen.queryByText("Network error. Please try again."),
    ).not.toBeInTheDocument();
  });

  test("redirects if already authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("redirects to validated next param when authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockGetParam.mockReturnValue("/dashboard");

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/dashboard");
  });

  test("does not redirect to invalid next param (https)", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockGetParam.mockReturnValue("https://evil.com");

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("does not redirect to protocol-relative URL", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockGetParam.mockReturnValue("//evil.com/path");

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("does not redirect to javascript: URL", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockGetParam.mockReturnValue("javascript:alert(1)");

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("password input has minLength 8 in register mode", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    const passwordInput = screen.getByLabelText("Password");
    expect(passwordInput).toHaveAttribute("minlength", "8");
  });

  test("password input has minLength 6 in login mode", () => {
    render(<LoginPage />);

    const passwordInput = screen.getByLabelText("Password");
    expect(passwordInput).toHaveAttribute("minlength", "6");
  });

  test("email input type is email", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
  });

  test("password input type is password", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
  });

  test("renders form with submit handler", () => {
    render(<LoginPage />);
    const form = screen.getByLabelText("Email").closest("form");
    expect(form).toBeInTheDocument();
  });

  test("register mode shows email placeholder", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
  });

  test("login mode shows password placeholder", () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText("•••••••")).toBeInTheDocument();
  });

  // --- validateNextParam edge cases ---

  test("validateNextParam returns null for null input", () => {
    mockGetParam.mockReturnValue(null);
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("validateNextParam returns null for non-slash start", () => {
    mockGetParam.mockReturnValue("dashboard");
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("validateNextParam returns null for http:// URL", () => {
    mockGetParam.mockReturnValue("http://evil.com");
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/workspace");
  });

  test("validateNextParam accepts valid path with colon", () => {
    mockGetParam.mockReturnValue("/path:data");
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(<LoginPage />);

    expect(mockPush).toHaveBeenCalledWith("/path:data");
  });

  // --- setup-status fetch ---

  test("redirects to /setup when setup-status returns needs_setup=true", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: true }),
    });

    render(<LoginPage />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/setup");
    });
  });

  test("stays on login when setup-status returns needs_setup=false", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ needs_setup: false }),
    });

    render(<LoginPage />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/setup-status");
    });

    // Should not redirect to /setup
    expect(mockPush).not.toHaveBeenCalledWith("/setup");
  });

  test("stays on login when setup-status fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    render(<LoginPage />);

    // Should not redirect to /setup
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/setup-status");
    });
    expect(mockPush).not.toHaveBeenCalledWith("/setup");
  });

  // --- handleSubmit: login ---

  test("successful login redirects to /workspace", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace");
    });
  });

  test("login sends form-encoded request body", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/login/local", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "username=user%40test.com&password=password123",
        credentials: "include",
      });
    });
  });

  test("login shows error on API failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: "Invalid credentials" }),
      });
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrongpass" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  test("login shows network error on fetch failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.reject(new Error("Network error"));
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
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

  test("login shows loading state during submission", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return new Promise(() => {}); // never resolves
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Please wait...")).toBeInTheDocument();
    });
  });

  // --- handleSubmit: register ---

  test("successful register redirects to /workspace", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<LoginPage />);

    // Switch to register mode
    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace");
    });
  });

  test("register sends JSON request body", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "new@test.com",
          password: "password123",
        }),
        credentials: "include",
      });
    });
  });

  test("register shows error on API failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: "Email already registered" }),
      });
    });

    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "existing@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  test("register shows network error on fetch failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.reject(new Error("Network error"));
    });

    render(<LoginPage />);

    fireEvent.click(screen.getByText("Don't have an account? Sign up"));

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
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

  // --- redirectPath with next param ---

  test("login success redirects to validated next param", async () => {
    mockGetParam.mockReturnValue("/settings");
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/settings");
    });
  });

  test("invalid next param falls back to /workspace on login success", async () => {
    mockGetParam.mockReturnValue("https://evil.com");
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/v1/auth/setup-status") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ needs_setup: false }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });

    const form = screen.getByLabelText("Email").closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/workspace");
    });
  });
});
