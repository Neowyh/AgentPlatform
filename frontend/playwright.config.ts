import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { defineConfig, devices } from "@playwright/test";
import { config } from "dotenv";

// Load root .env so test-runner process sees OPENAI_API_KEY, etc.
const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../.env") });
const frontendPort = process.env.E2E_FRONTEND_PORT ?? "3000";
const baseURL = `http://localhost:${frontendPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  testIgnore: [
    "**/stagehand/**",
    "**/test-results/**",
    "**/playwright-artifacts/**",
    "**/playwright-report/**",
  ],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "html",
  timeout: 30_000,

  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      animations: "disabled",
    },
    toMatchSnapshot: {
      maxDiffPixelRatio: 0.01,
    },
    timeout: 15_000,
  },

  use: {
    baseURL,
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      testMatch: [/smoke\/.*\.spec\.ts/, /workflows\/.*\.spec\.ts/],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "visual",
      testMatch: [
        "visual/landing.visual.spec.ts",
        "visual/workspace-layout.visual.spec.ts",
        "visual/core.visual.spec.ts",
      ],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "visual-reference",
      testMatch: "visual/visual-screenshot.spec.ts",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    // IMPORTANT: IDEER_AUTH_DISABLED must reach BOTH build and runtime.
    // Next.js SSR (getServerSideUser) bypasses page.route mocks, so without
    // this flag it will fetch the real gateway at 127.0.0.1:8001 and redirect
    // to /login, which surfaces as a flaky "SSR auth redirect loop".
    // See frontend/src/core/auth/server.ts.
    command: `pnpm exec next build --webpack && pnpm start -p ${frontendPort}`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 300_000,
    env: {
      SKIP_ENV_VALIDATION: "1",
      // Auth is DISABLED for E2E — SSR getServerSideUser() returns the
      // hardcoded super_admin user so page.route mocks work consistently
      // (SSR fetches bypass browser-level interceptors).  Auth-specific
      // tests (smoke-login, auth-flow) are skipped when this is set.
      // This env is injected into BOTH next build and next start processes.
      IDEER_AUTH_DISABLED: "1",
      // Do not set NEXT_PUBLIC_BACKEND_BASE_URL — the Next.js rewrite rules
      // in next.config.js proxy /api/* to the gateway when this is unset.
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
      OPENAI_BASE_URL: process.env.OPENAI_BASE_URL ?? "",
    },
  },
});
