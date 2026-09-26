import type { ChannelProvider } from "@/core/channels/types";

/**
 * Shared channel-provider fixture for unit tests. A usable default (enabled,
 * configured, no availability problem) so individual tests only spell out the
 * fields under test. Not connected by default, matching the Gateway's state
 * for a channel nobody has bound yet.
 */
export function makeChannelProvider(
  overrides: Partial<ChannelProvider>,
): ChannelProvider {
  return {
    provider: "buzz",
    display_name: "Buzz",
    enabled: true,
    configured: true,
    connectable: true,
    auth_mode: "binding_code",
    connection_status: "not_connected",
    credential_fields: [],
    ...overrides,
  };
}
