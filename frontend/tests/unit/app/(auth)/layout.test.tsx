import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const { mockGetServerSideUser, mockRedirect } = vi.hoisted(() => ({
  mockGetServerSideUser: vi.fn(),
  mockRedirect: vi.fn(),
}));

vi.mock("@/core/auth/server", () => ({
  getServerSideUser: mockGetServerSideUser,
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  AuthProvider: ({ children, initialUser }: any) => (
    <div
      data-testid="auth-provider"
      data-initial-user={JSON.stringify(initialUser)}
    >
      {children}
    </div>
  ),
}));

vi.mock("@/core/auth/types", () => ({
  assertNever: (value: never) => {
    throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
  },
}));

vi.mock("next/navigation", () => ({
  redirect: (...args: any[]) => mockRedirect(...args),
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

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

import AuthLayout from "@/app/(auth)/layout";

describe("AuthLayout", () => {
  test("redirects to /workspace when authenticated", async () => {
    mockGetServerSideUser.mockResolvedValue({
      tag: "authenticated",
      user: { id: "1" },
    });
    mockRedirect.mockImplementation(() => {
      throw new Error("REDIRECT");
    });

    await expect(AuthLayout({ children: <div>child</div> })).rejects.toThrow(
      "REDIRECT",
    );

    expect(mockRedirect).toHaveBeenCalledWith("/workspace");
  });

  test("renders gateway unavailable page", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "gateway_unavailable" });
    render(await AuthLayout({ children: <div>child</div> }));
    expect(
      screen.getByText("Service temporarily unavailable."),
    ).toBeInTheDocument();
  });

  test("renders retry link on gateway unavailable page", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "gateway_unavailable" });
    render(await AuthLayout({ children: <div>child</div> }));
    const link = screen.getByText("Retry");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/login");
  });

  test("renders unauthenticated state with children", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "unauthenticated" });
    render(await AuthLayout({ children: <div>login form</div> }));
    expect(screen.getByText("login form")).toBeInTheDocument();
    expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
  });

  test("passes null as initialUser for unauthenticated", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "unauthenticated" });
    render(await AuthLayout({ children: <div>child</div> }));
    const provider = screen.getByTestId("auth-provider");
    expect(provider.getAttribute("data-initial-user")).toBe("null");
  });

  test("renders needs_setup state with children", async () => {
    mockGetServerSideUser.mockResolvedValue({
      tag: "needs_setup",
      user: { id: "1" },
    });
    render(await AuthLayout({ children: <div>setup form</div> }));
    expect(screen.getByText("setup form")).toBeInTheDocument();
  });

  test("passes user as initialUser for needs_setup", async () => {
    const user = { id: "1", email: "admin@test.com" };
    mockGetServerSideUser.mockResolvedValue({ tag: "needs_setup", user });
    render(await AuthLayout({ children: <div>child</div> }));
    const provider = screen.getByTestId("auth-provider");
    expect(provider.getAttribute("data-initial-user")).toBe(
      JSON.stringify(user),
    );
  });

  test("renders system_setup_required state", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "system_setup_required" });
    render(await AuthLayout({ children: <div>child</div> }));
    expect(screen.getByText("child")).toBeInTheDocument();
    expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
  });

  test("passes null as initialUser for system_setup_required", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "system_setup_required" });
    render(await AuthLayout({ children: <div>child</div> }));
    const provider = screen.getByTestId("auth-provider");
    expect(provider.getAttribute("data-initial-user")).toBe("null");
  });

  test("throws on config_error", async () => {
    mockGetServerSideUser.mockResolvedValue({
      tag: "config_error",
      message: "Missing API key",
    });

    await expect(AuthLayout({ children: <div>child</div> })).rejects.toThrow(
      "Missing API key",
    );
  });
});
