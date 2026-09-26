import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ChannelsSettingsPage } from "@/components/workspace/settings/channels-settings-page";

// Mock the channels API seam so the page exercises its real hooks against a
// controlled backend response.
const channelsApiState = vi.hoisted(() => ({
  providers: [] as Array<Record<string, unknown>>,
  connections: [] as Array<Record<string, unknown>>,
}));

vi.mock("@/core/channels/api", () => ({
  listChannelProviders: () =>
    Promise.resolve({
      enabled: true,
      providers: channelsApiState.providers,
    }),
  listChannelConnections: () => Promise.resolve(channelsApiState.connections),
  connectChannelProvider: vi.fn(),
  configureChannelProvider: vi.fn(),
  disconnectChannelConnection: vi.fn(),
  disconnectChannelProvider: vi.fn(),
}));

vi.mock(
  "@/components/workspace/channels/channel-runtime-config-dialog",
  () => ({
    ChannelRuntimeConfigDialog: () => null,
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

function makeProvider(overrides: Record<string, unknown>) {
  return {
    provider: "buzz",
    display_name: "Buzz",
    enabled: true,
    configured: true,
    connectable: true,
    auth_mode: "binding_code",
    connection_status: "connected",
    credential_fields: [],
    ...overrides,
  };
}

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
    channelsApiState.providers = [makeProvider({})];
    renderChannelsPage();

    await waitFor(() => {
      expect(screen.getByText("Buzz")).toBeInTheDocument();
    });
  });

  test("hides providers the deployment cannot use", async () => {
    channelsApiState.providers = [
      makeProvider({}),
      makeProvider({
        provider: "telegram",
        display_name: "Telegram",
        configured: false,
        connectable: false,
        connection_status: "not_connected",
        unavailable_reason:
          "Enter the required Telegram credentials to connect this channel.",
      }),
      makeProvider({
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
      makeProvider({
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
});
