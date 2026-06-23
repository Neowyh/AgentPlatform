import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { defineConfig, devices } from "@playwright/test";
import { config } from "dotenv";

// Load root .env so test-runner process sees OPENAI_API_KEY, etc.
const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../.env") });

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
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
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "qa",
      testDir: "./tests/e2e/qa",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "visual",
      testDir: "./tests/e2e/visual",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "a11y",
      testDir: "./tests/e2e/a11y",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "pnpm exec next build --webpack && pnpm start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      SKIP_ENV_VALIDATION: "1",
      IDEER_AUTH_DISABLED: "1",
      NEXT_PUBLIC_BACKEND_BASE_URL: "http://localhost:3000",
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
      OPENAI_BASE_URL: process.env.OPENAI_BASE_URL ?? "",
    },
  },
});
