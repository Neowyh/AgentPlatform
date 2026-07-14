/**
 * Playwright config for Auth E2E tests.
 *
 * Runs the frontend WITHOUT IDEER_AUTH_DISABLED, connecting to the real
 * backend at localhost:8001 for authentication. Requires the backend to
 * be running with auth enabled.
 */
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { defineConfig, devices } from "@playwright/test";
import { config } from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../.env") });
const frontendPort = process.env.E2E_FRONTEND_PORT ?? "3003";
const baseURL = `http://localhost:${frontendPort}`;

export default defineConfig({
  testDir: "./tests/e2e/auth",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "list",
  timeout: 30_000,

  expect: {
    timeout: 15_000,
  },

  use: {
    baseURL,
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "auth",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: `pnpm exec next build --webpack && pnpm start -p ${frontendPort}`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      SKIP_ENV_VALIDATION: "1",
      // Auth is ENABLED — no IDEER_AUTH_DISABLED
      // Do NOT set NEXT_PUBLIC_BACKEND_BASE_URL — the Next.js rewrite rules
      // in next.config.js proxy /api/* to the gateway when this is unset.
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
      OPENAI_BASE_URL: process.env.OPENAI_BASE_URL ?? "",
    },
  },
});
