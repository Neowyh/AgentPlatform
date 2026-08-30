import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

describe("production typography contract", () => {
  test("defines the three shared sizes and body line height", async () => {
    const css = await readFile(
      join(process.cwd(), "src/styles/globals.css"),
      "utf8",
    );

    expect(css).toContain("--text-body: 1rem;");
    expect(css).toContain("--text-subtitle: 2.25rem;");
    expect(css).toContain("--text-title: 2.75rem;");
    expect(css).toContain("font-size: var(--text-body);");
    expect(css).toContain("line-height: 1.5;");
    expect(css).toContain("font-size: 2.25rem !important;");
    expect(css).toContain("font-size: 1.75rem !important;");
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
      "text-(xs|sm|lg|xl|2xl|3xl|4xl|5xl|6xl)",
      "src",
    ];
    const cssArgs = [
      "-n",
      "--glob",
      "!src/app/prototype/**",
      "--glob",
      "*.css",
      "-e",
      "font-size\\s*:\\s*(10|11|12|13|14|15)px",
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
