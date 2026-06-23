import { resolve } from "path";

import { defineConfig } from "vitest/config";

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
    include: ["tests/unit/**/*.test.{ts,tsx}"],
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
