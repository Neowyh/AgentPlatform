import { describe, expect, it } from "vitest";

import { isLarkIntegrationUsable } from "@/core/integrations/lark/capability";
import type { LarkIntegrationStatus } from "@/core/integrations/lark/types";

function makeStatus(
  overrides: Partial<LarkIntegrationStatus>,
): LarkIntegrationStatus {
  return {
    installed: false,
    version: "v1.0.65",
    manifest_version: null,
    latest_available_version: null,
    runtime_version_mismatch: false,
    app_configured: false,
    app_id: null,
    app_brand: null,
    skills_expected: 27,
    skills_installed: 0,
    installed_skills: [],
    enabled_skills: [],
    install_path: "/tmp/integrations/skills/lark-cli",
    cli: { available: false, path: null, version: null, error: null },
    auth: {
      status: "not_configured",
      message: null,
      user: null,
      verified: false,
    },
    sandbox_runtime_mode: "none",
    sandbox_runtime_ready: false,
    sandbox_runtime_detail: null,
    ...overrides,
  };
}

describe("isLarkIntegrationUsable", () => {
  it("follows the Gateway lark-cli probe", () => {
    expect(
      isLarkIntegrationUsable(
        makeStatus({
          cli: {
            available: true,
            path: "/usr/bin/lark-cli",
            version: "v1.0.65",
            error: null,
          },
        }),
      ),
    ).toBe(true);
    expect(isLarkIntegrationUsable(makeStatus({}))).toBe(false);
  });

  it("does not require the pack to be installed or authorized yet", () => {
    expect(
      isLarkIntegrationUsable(
        makeStatus({
          installed: false,
          app_configured: false,
          cli: {
            available: true,
            path: "/usr/bin/lark-cli",
            version: "v1.0.65",
            error: null,
          },
        }),
      ),
    ).toBe(true);
  });

  it("is false without a status", () => {
    expect(isLarkIntegrationUsable(null)).toBe(false);
    expect(isLarkIntegrationUsable(undefined)).toBe(false);
  });
});
