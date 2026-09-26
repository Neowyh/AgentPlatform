import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ChannelsSettingsPage } from "@/components/workspace/settings/channels-settings-page";
import type { ChannelConnection, ChannelProvider } from "@/core/channels/types";

import { makeChannelProvider } from "../../../utils/channel-provider";

// Mock the channels API seam so the page exercises its real hooks against a
// controlled backend response.
const channelsApiState = vi.hoisted(() => ({
  providers: [] as ChannelProvider[],
  connections: [] as ChannelConnection[],
}));

vi.mock("@/core/channels/api", () => ({
  listChannelProviders: () =>
    Promise.resolve({
      enabled: true,
      providers: channelsApiState.providers,
    }),
  listChannelConnections: () => Promise.resolve(channelsApiState.connections),
  connectChannelProvider: vi.fn(() =>
    Promise.resolve({
      provider: "buzz",
      mode: "binding_code",
      url: null,
      code: "abc123",
      instruction: "Send /connect abc123 to the DeerFlow Buzz bot.",
      expires_in: 600,
    }),
  ),
  configureChannelProvider: vi.fn(),
  disconnectChannelConnection: vi.fn(),
  disconnectChannelProvider: vi.fn(),
}));

vi.mock(
  "@/components/workspace/channels/channel-runtime-config-dialog",
  () => ({
    // Render an observable marker so tests can assert the page opened the
    // runtime-config dialog without mounting the real form.
    ChannelRuntimeConfigDialog: ({ open }: { open: boolean }) =>
      open ? <div data-testid="runtime-config-dialog-open" /> : null,
  }),
);

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      common: { loading: "Loading…" },
      settings: {
        channels: {
          title: "Channels",
          description: "Connect messaging channels.",
          disabled: "Channels are not available in this deployment.",
        },
      },
      channels: {
        disabled: "Disabled",
        unconfigured: "Not configured",
        unavailableShort: "Unavailable",
        unavailable: "Channels are unavailable.",
        connected: "Connected",
        pending: "Pending",
        revoked: "Revoked",
        notConnected: "Not connected",
        connectedAs: (label: string) => `Connected as ${label}`,
        descriptions: {
          buzz: "Buzz channels and direct messages",
          telegram: "Telegram direct messages",
        },
        modify: "Modify",
        disconnect: "Disconnect",
        reconnect: "Reconnect",
        connect: "Connect",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  channelsApiState.providers = [];
  channelsApiState.connections = [];
});

afterEach(() => {
  cleanup();
});

function renderChannelsPage() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ChannelsSettingsPage />
    </QueryClientProvider>,
  );
}

describe("ChannelsSettingsPage capability display", () => {
  test("lists a configured, running provider", async () => {
    channelsApiState.providers = [
      makeChannelProvider({ connection_status: "connected" }),
    ];
    renderChannelsPage();

    await waitFor(() => {
      expect(screen.getByText("Buzz")).toBeInTheDocument();
    });
  });

  test("hides providers the deployment cannot use", async () => {
    channelsApiState.providers = [
      makeChannelProvider({ connection_status: "connected" }),
      makeChannelProvider({
        provider: "telegram",
        display_name: "Telegram",
        configured: false,
        connectable: false,
        connection_status: "not_connected",
        unavailable_reason:
          "Enter the required Telegram credentials to connect this channel.",
      }),
      makeChannelProvider({
        provider: "slack",
        display_name: "Slack",
        connection_status: "not_connected",
        unavailable_reason:
          "Slack channel is configured but is not running. Check the credentials and service logs.",
      }),
    ];
    renderChannelsPage();

    await waitFor(() => {
      expect(screen.getByText("Buzz")).toBeInTheDocument();
    });
    expect(screen.queryByText("Telegram")).not.toBeInTheDocument();
    expect(screen.queryByText("Slack")).not.toBeInTheDocument();
  });

  test("falls back to the disabled message when nothing is usable", async () => {
    channelsApiState.providers = [
      makeChannelProvider({
        provider: "telegram",
        display_name: "Telegram",
        configured: false,
        connectable: false,
        connection_status: "not_connected",
        unavailable_reason:
          "Enter the required Telegram credentials to connect this channel.",
      }),
    ];
    renderChannelsPage();

    await waitFor(() => {
      expect(
        screen.getByText("Channels are not available in this deployment."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Telegram")).not.toBeInTheDocument();
  });

  test("connects a usable, not-yet-connected provider directly", async () => {
    const user = userEvent.setup();
    const { connectChannelProvider } = await import("@/core/channels/api");
    channelsApiState.providers = [
      makeChannelProvider({ connection_status: "not_connected" }),
    ];
    renderChannelsPage();

    await waitFor(() => {
      expect(screen.getByText("Buzz")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(connectChannelProvider).toHaveBeenCalledWith("buzz");
    });
  });

  test("offers runtime-config editing for a usable provider with credentials", async () => {
    const user = userEvent.setup();
    channelsApiState.providers = [
      makeChannelProvider({
        credential_fields: [
          { name: "token", label: "Token", type: "password", required: true },
        ],
      }),
    ];
    renderChannelsPage();

    await waitFor(() => {
      expect(screen.getByText("Buzz")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Modify" }));

    expect(
      screen.getByTestId("runtime-config-dialog-open"),
    ).toBeInTheDocument();
  });
});
