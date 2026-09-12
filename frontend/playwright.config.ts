import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const skipWebServer = process.env.PLAYWRIGHT_SKIP_WEB_SERVER === "1";
// The mock lane's webServer always disables auth (SSR mocks assume an
// authenticated session). The auth-flow corpus needs an auth-enabled server
// and is opt-in: PLAYWRIGHT_AUTH_ENABLED=1 leaves the flag off for both the
// webServer and the runner, so the specs' skip guards see the same decision.
const authDisabled = process.env.PLAYWRIGHT_AUTH_ENABLED !== "1";
if (authDisabled) {
  process.env.DEER_FLOW_AUTH_DISABLED = "1";
}

export default defineConfig({
  testDir: "./tests/e2e",
  // The visual-regression specs belong to the frontend-visual lane
  // (screenshots depend on machine font rendering); keep them out of the
  // default functional collection unless that lane opts in.
  testIgnore: process.env.PLAYWRIGHT_VISUAL
    ? []
    : ["tests/e2e/visual/**/*.spec.ts"],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "html",
  timeout: 30_000,

  use: {
    baseURL,
    locale: "en-US",
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: skipWebServer
    ? undefined
    : {
        command:
          process.env.PLAYWRIGHT_DEV_SERVER === "1"
            ? "./node_modules/.bin/next dev"
            : "./node_modules/.bin/next build && ./node_modules/.bin/next start",
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        // Cold Next.js builds can exceed two minutes in constrained CI
        // worktrees; keep the smoke lane deterministic while retaining a
        // bounded startup wait.
        timeout: 300_000,
        env: {
          SKIP_ENV_VALIDATION: "1",
          ...(authDisabled ? { DEER_FLOW_AUTH_DISABLED: "1" } : {}),
        },
      },
});
