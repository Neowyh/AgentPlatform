import type { LarkIntegrationStatus } from "./types";

/**
 * Whether the deployment has the approved Feishu/Lark access capability.
 *
 * The Gate is the Gateway's lark-cli probe: an offline deployment never ships
 * or downloads lark-cli, so `cli.available` is false there and the Settings
 * Integrations entry must stay hidden. Gating on `installed` or the auth
 * state instead would hide first-time install/authorization flows, which run
 * from this very entry on capable deployments.
 */
export function isLarkIntegrationUsable(
  status: LarkIntegrationStatus | null | undefined,
): boolean {
  return status?.cli?.available ?? false;
}
