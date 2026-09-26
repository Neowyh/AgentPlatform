import type { ChannelProvider } from "./types";

/**
 * A provider the deployment can actually use: enabled in config, holding the
 * required credentials, and reporting no availability problem (e.g. runtime
 * not running). The Gateway derives its `connectable` flag from exactly these
 * fields, and connected providers satisfy them too, so this never contradicts
 * the wire status. Unusable providers must not surface as actionable entries
 * in offline deployments.
 */
export function isUsableChannelProvider(provider: ChannelProvider): boolean {
  return (
    provider.enabled && provider.configured && !provider.unavailable_reason
  );
}

export function hasUsableChannelProvider(
  providers: ChannelProvider[],
): boolean {
  return providers.some(isUsableChannelProvider);
}

export function providerCanConnect(provider: ChannelProvider): boolean {
  return (
    (provider.connectable ?? (provider.enabled && provider.configured)) &&
    provider.connection_status !== "connected"
  );
}

export function providerNeedsRuntimeConfig(provider: ChannelProvider): boolean {
  return (
    provider.enabled &&
    !provider.configured &&
    (provider.credential_fields?.length ?? 0) > 0
  );
}

export function providerCanEditRuntimeConfig(
  provider: ChannelProvider,
): boolean {
  return provider.enabled && (provider.credential_fields?.length ?? 0) > 0;
}
