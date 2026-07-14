import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "../docs/manual/scripts",
  testMatch: "generate-screenshots.ts",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "list",
  timeout: 60_000,

  use: {
    baseURL: "http://localhost:3005",
    trace: "off",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "pnpm exec next build --webpack && pnpm start -p 3005",
    url: "http://localhost:3005",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
