import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const { mockGetServerSideUser, mockRedirect } = vi.hoisted(() => ({
  mockGetServerSideUser: vi.fn(),
  mockRedirect: vi.fn(),
}));

vi.mock("@/core/auth/server", () => ({
  getServerSideUser: mockGetServerSideUser,
}));

// The layout reads the request locale on the server; `next/headers` cookie
// access is unavailable under vitest, so stub the locale probe.
vi.mock("@/core/i18n/server", () => ({
  detectLocaleServer: async () => "en-US",
}));

vi.mock("@/core/i18n/context", () => ({
  I18nProvider: ({ children }: any) => (
    <div data-testid="i18n-provider">{children}</div>
  ),
}));

vi.mock("@/components/workspace/gateway-offline-banner", () => ({
  GatewayOfflineBanner: () => <div data-testid="gateway-offline-banner" />,
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

  test("renders the offline fallback with a banner instead of children when gateway unavailable", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "gateway_unavailable" });
    render(await AuthLayout({ children: <div>child</div> }));
    // Children are intentionally not rendered while the gateway is down; the
    // fallback shows the banner-driven recovery UI instead.
    expect(screen.getByTestId("gateway-offline-banner")).toBeInTheDocument();
    expect(screen.queryByText("child")).not.toBeInTheDocument();
  });

  test("wraps the gateway-unavailable fallback in an AuthProvider", async () => {
    mockGetServerSideUser.mockResolvedValue({ tag: "gateway_unavailable" });
    render(await AuthLayout({ children: <div>child</div> }));
    const provider = screen.getByTestId("auth-provider");
    expect(provider).toBeInTheDocument();
    expect(provider.getAttribute("data-initial-user")).toBe("null");
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
