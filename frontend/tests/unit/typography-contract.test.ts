import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

describe("production typography contract", () => {
  test("defines the production typography roles and responsive scale", async () => {
    const css = await readFile(
      join(process.cwd(), "src/styles/globals.css"),
      "utf8",
    );

    expect(css).toContain("--text-display: 2.5rem;");
    expect(css).toContain("--text-page-title: 1.5rem;");
    expect(css).toContain("--text-section-title: 1.125rem;");
    expect(css).toContain("--text-body: 1rem;");
    expect(css).toContain("--text-supporting: 0.875rem;");
    expect(css).toContain("--text-compact: 0.75rem;");
    expect(css).toContain(".type-display");
    expect(css).toContain(".type-page-title");
    expect(css).toContain(".type-section-title");
    expect(css).toContain(".type-body");
    expect(css).toContain(".type-supporting");
    expect(css).toContain(".type-compact");
    expect(css).toContain("line-height: 1.5;");
    expect(css).not.toMatch(/h[123]\s*\{[^}]*font-size:[^}]*!important/s);
  });

  test("does not retain unclassified small or utility text sizes", async () => {
    const { execFile } = await import("node:child_process");
    const { promisify } = await import("node:util");
    const run = promisify(execFile);
    const classArgs = [
      "-n",
      "--glob",
      "!src/app/prototype/**",
      "--glob",
      "!**/*.test.*",
      "--glob",
      "*.{ts,tsx}",
      "-e",
      "text-(xs|sm|lg|xl|2xl|3xl|4xl|5xl|6xl)|text-\\[(8px|10px|11px)\\]",
      "src",
    ];
    const cssArgs = [
      "-n",
      "--glob",
      "!src/app/prototype/**",
      "--glob",
      "*.css",
      "-e",
      "font-size\\s*:\\s*(8|9|10|11|12|13|14|15)px",
      "src",
    ];

    const { stdout: classOutput } = await run("rg", classArgs, {
      cwd: process.cwd(),
    }).catch((error) => {
      if (error.code === 1) return { stdout: "" };
      throw error;
    });
    const { stdout: cssOutput } = await run("rg", cssArgs, {
      cwd: process.cwd(),
    }).catch((error) => {
      if (error.code === 1) return { stdout: "" };
      throw error;
    });

    expect(classOutput).toBe("");
    expect(cssOutput).toBe("");
  });
});
