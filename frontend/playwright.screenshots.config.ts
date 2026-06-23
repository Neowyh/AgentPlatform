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
    baseURL: "http://localhost:3000",
    trace: "off",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "echo 'Using existing server'",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 5_000,
  },
});
