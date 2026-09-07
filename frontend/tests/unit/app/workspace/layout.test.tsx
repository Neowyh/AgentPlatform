import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- declared before component imports
// ---------------------------------------------------------------------------

const mockGetServerSideUser = vi.fn();
const mockRedirect = vi.fn().mockImplementation(() => {
  // Next.js redirect() throws to abort rendering — simulate that behavior
  throw new Error("NEXT_REDIRECT");
});

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

vi.mock("@/core/auth/server", () => ({
  getServerSideUser: (...args: unknown[]) => mockGetServerSideUser(...args),
}));

// The layout reads the request locale on the server; `next/headers` cookie
// access is unavailable under vitest, so stub the locale probe.
vi.mock("@/core/i18n/server", () => ({
  detectLocaleServer: async () => "en-US",
}));

vi.mock("@/core/i18n/context", () => ({
  I18nProvider: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div data-testid="i18n-provider">{children}</div>,
}));

vi.mock("@/core/auth/types", () => ({
  assertNever: (x: never) => {
    throw new Error(`Unexpected auth result: ${JSON.stringify(x)}`);
  },
}));

vi.mock("@/app/workspace/workspace-content", () => ({
  WorkspaceContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="workspace-content">{children}</div>
  ),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  AuthProvider: ({
    children,
    initialUser,
  }: {
    children: React.ReactNode;
    initialUser: unknown;
  }) => (
    <div data-testid="auth-provider" data-user={JSON.stringify(initialUser)}>
      {children}
    </div>
  ),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import WorkspaceLayout from "@/app/workspace/layout";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockUser = {
  id: "u1",
  email: "test@example.com",
  system_role: "user" as const,
  needs_setup: false,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WorkspaceLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  // ── Authenticated ─────────────────────────────────────────────────────

  describe("when authenticated", () => {
    beforeEach(() => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "authenticated",
        user: mockUser,
      });
    });

    test("renders AuthProvider with user data", async () => {
      render(await WorkspaceLayout({ children: <div>child content</div> }));

      expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
      expect(screen.getByTestId("auth-provider")).toHaveAttribute(
        "data-user",
        JSON.stringify(mockUser),
      );
    });

    test("renders WorkspaceContent wrapping children", async () => {
      render(await WorkspaceLayout({ children: <div>child content</div> }));

      expect(screen.getByTestId("workspace-content")).toBeInTheDocument();
      expect(screen.getByText("child content")).toBeInTheDocument();
    });

    test("renders children inside WorkspaceContent", async () => {
      render(await WorkspaceLayout({ children: <p>hello world</p> }));

      expect(screen.getByText("hello world")).toBeInTheDocument();
    });

    test("does not redirect", async () => {
      render(await WorkspaceLayout({ children: <div>content</div> }));

      expect(mockRedirect).not.toHaveBeenCalled();
    });
  });

  // ── needs_setup ───────────────────────────────────────────────────────

  describe("when needs_setup", () => {
    beforeEach(() => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "needs_setup",
        user: mockUser,
      });
    });

    test("redirects to /setup", async () => {
      await expect(
        WorkspaceLayout({ children: <div>content</div> }),
      ).rejects.toThrow("NEXT_REDIRECT");
      expect(mockRedirect).toHaveBeenCalledWith("/setup");
    });

    test("calls redirect exactly once", async () => {
      await expect(
        WorkspaceLayout({ children: <div>content</div> }),
      ).rejects.toThrow("NEXT_REDIRECT");
      expect(mockRedirect).toHaveBeenCalledTimes(1);
    });
  });

  // ── system_setup_required ─────────────────────────────────────────────

  describe("when system_setup_required", () => {
    beforeEach(() => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "system_setup_required",
      });
    });

    test("redirects to /setup", async () => {
      await expect(
        WorkspaceLayout({ children: <div>content</div> }),
      ).rejects.toThrow("NEXT_REDIRECT");
      expect(mockRedirect).toHaveBeenCalledWith("/setup");
    });
  });

  // ── unauthenticated ───────────────────────────────────────────────────

  describe("when unauthenticated", () => {
    beforeEach(() => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "unauthenticated",
      });
    });

    test("redirects to /login", async () => {
      await expect(
        WorkspaceLayout({ children: <div>content</div> }),
      ).rejects.toThrow("NEXT_REDIRECT");
      expect(mockRedirect).toHaveBeenCalledWith("/login");
    });
  });

  // ── gateway_unavailable ───────────────────────────────────────────────

  describe("when gateway_unavailable", () => {
    beforeEach(() => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "gateway_unavailable",
      });
    });

    test("keeps rendering the workspace content with the children", async () => {
      render(await WorkspaceLayout({ children: <div>content</div> }));

      // The merged layout no longer serves a bare static page: the workspace
      // shell stays mounted (with the offline banner inside WorkspaceContent)
      // so the UI keeps its usual recovery affordances.
      expect(screen.getByText("content")).toBeInTheDocument();
      expect(
        screen.getByTestId("workspace-content"),
      ).toBeInTheDocument();
    });

    test("wraps the shell in an AuthProvider so the offline banner can recover", async () => {
      render(await WorkspaceLayout({ children: <div>content</div> }));

      const authProvider = screen.getByTestId("auth-provider");
      expect(authProvider).toBeInTheDocument();
      expect(authProvider).toHaveAttribute("data-user", "null");
    });

    test("does not redirect", async () => {
      render(await WorkspaceLayout({ children: <div>content</div> }));

      expect(mockRedirect).not.toHaveBeenCalled();
    });
  });

  // ── config_error ──────────────────────────────────────────────────────

  describe("when config_error", () => {
    beforeEach(() => {
      mockGetServerSideUser.mockResolvedValue({
        tag: "config_error",
        message: "Missing GITHUB_OAUTH_TOKEN",
      });
    });

    test("throws an error with the config error message", async () => {
      await expect(
        WorkspaceLayout({ children: <div>content</div> }),
      ).rejects.toThrow("Missing GITHUB_OAUTH_TOKEN");
    });
  });

  // ── Dynamic export ────────────────────────────────────────────────────

  test("exports force-dynamic", async () => {
    const mod = await import("@/app/workspace/layout");
    expect(mod.dynamic).toBe("force-dynamic");
  });
});
