import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { defineConfig, devices } from "@playwright/test";
import { config } from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, "../.env") });
const baseURL = "http://localhost:3002";

export default defineConfig({
  testDir: "./tests/e2e/a11y",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  timeout: 30_000,
  use: { baseURL, trace: "on-first-retry", ...devices["Desktop Chrome"] },
  webServer: {
    command: "pnpm exec next build --webpack && pnpm start -p 3002",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      SKIP_ENV_VALIDATION: "1",
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
      OPENAI_BASE_URL: process.env.OPENAI_BASE_URL ?? "",
    },
  },
});
