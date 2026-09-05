import { resolve } from "path";

import { defineConfig } from "vitest/config";

import { vitestUnitFiles } from "./tests/framework-split";

export default defineConfig({
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  css: {
    // Mock CSS imports so jsdom tests don't fail on .css files
    modules: {
      localsConvention: "camelCaseOnly",
    },
  },
  test: {
    // Only the files this framework owns (see tests/framework-split.ts);
    // rstest collects its own set so no file runs twice.
    include: vitestUnitFiles,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.d.ts",
        "src/**/*.stories.{ts,tsx}",
        "src/app/layout.tsx",
      ],
      reporter: ["text", "html", "lcov", "json"],
      reportsDirectory: "coverage",
    },
  },
});
