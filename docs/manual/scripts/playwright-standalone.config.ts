import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "list",
  timeout: 60_000,

  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    trace: "off",
    screenshot: "off",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // 不启动 web server，使用已运行的服务
  webServer: undefined,
});
