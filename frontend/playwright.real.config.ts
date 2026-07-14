import { resolve } from "path";

import { defineConfig, devices } from "@playwright/test";

const stateDir = process.env.E2E_STATE_DIR;
const runId = process.env.E2E_RUN_ID;
const gatewayUrl = process.env.IDEER_INTERNAL_GATEWAY_BASE_URL;
const frontendPort = process.env.E2E_FRONTEND_PORT ?? "3101";

if (!stateDir || !runId || !gatewayUrl) {
  throw new Error(
    "Real E2E requires E2E_STATE_DIR, E2E_RUN_ID, and IDEER_INTERNAL_GATEWAY_BASE_URL. Run `pnpm test:e2e:real` rather than Playwright directly.",
  );
}

const artifactsDir = resolve(
  process.env.REAL_E2E_ARTIFACTS_DIR ||
    resolve(stateDir, "playwright-artifacts"),
);
const baseURL = `http://localhost:${frontendPort}`;

export default defineConfig({
  testDir: "./tests/e2e/real",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: resolve(artifactsDir, "report"), open: "never" }],
  ],
  outputDir: resolve(artifactsDir, "test-results"),
  timeout: 120_000,

  expect: { timeout: 20_000 },
  use: {
    baseURL,
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "real", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `pnpm exec next build --webpack && pnpm start -p ${frontendPort}`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 420_000,
    env: {
      SKIP_ENV_VALIDATION: "1",
      IDEER_INTERNAL_GATEWAY_BASE_URL: gatewayUrl,
      IDEER_TRUSTED_ORIGINS: baseURL,
      IDEER_NEXT_DIST_DIR: `.next-e2e-${runId}`,
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
      OPENAI_BASE_URL: process.env.OPENAI_BASE_URL ?? "",
    },
  },
});
