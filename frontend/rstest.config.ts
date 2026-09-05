import { resolve } from "path";

import { pluginReact } from "@rsbuild/plugin-react";
import { defineConfig } from "@rstest/core";

import { rstestUnitFiles } from "./tests/framework-split";

// Build wiring is identical across projects; only the environment and which
// files each one claims differ.
const shared = {
  plugins: [pluginReact()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  output: {
    // Streamdown imports KaTeX CSS as a side effect. Bundle these packages so
    // Rsbuild processes that CSS import instead of Node trying to load it.
    bundleDependencies: ["streamdown", "katex"],
  },
};

// Framework split (see tests/framework-split.ts): rstest only claims the
// files that import `@rstest/core`; vitest collects the rest, so no file
// runs twice.
const rstestNodeFiles = rstestUnitFiles.filter((file) => !file.includes(".dom.test."));
const rstestDomFiles = rstestUnitFiles.filter((file) => file.includes(".dom.test."));

export default defineConfig({
  projects: [
    {
      ...shared,
      name: "node",
      include: rstestNodeFiles,
      // A DOM environment costs roughly 3x the runtime of this suite, so the
      // pure-logic tests that make up nearly all of it stay on node and only
      // `*.dom.test.*` pays for a document.
      exclude: { patterns: ["**/*.dom.test.*"], override: false },
    },
    {
      ...shared,
      name: "dom",
      testEnvironment: "happy-dom",
      include: rstestDomFiles,
    },
  ],
});
