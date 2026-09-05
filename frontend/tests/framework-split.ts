/**
 * Framework split for the unit-test tree.
 *
 * The merge left two test frameworks in place by decision (no framework
 * migration this round): files that import `@rstest/core` run under rstest,
 * everything else runs under vitest.  Both configs call `classifyUnitTests()`
 * at load time so the split stays self-maintaining — a new test file is
 * collected by exactly one runner based on its imports, never by a
 * hand-maintained list.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ROOT = process.cwd();
const UNIT_DIR = join(ROOT, "tests", "unit");

function walkTestFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...walkTestFiles(full));
    } else if (/\.test\.(ts|tsx)$/.test(entry.name)) {
      found.push(full);
    }
  }
  return found;
}

function classify(): { rstest: string[]; vitest: string[] } {
  const rstest: string[] = [];
  const vitest: string[] = [];
  for (const file of walkTestFiles(UNIT_DIR)) {
    const rel = relative(ROOT, file).split(sep).join("/");
    if (readFileSync(file, "utf8").includes("@rstest/core")) {
      rstest.push(rel);
    } else {
      vitest.push(rel);
    }
  }
  return { rstest: rstest.sort(), vitest: vitest.sort() };
}

const classified = classify();

/** Files collected by rstest (import `@rstest/core`). */
export const rstestUnitFiles: string[] = classified.rstest;
/** Files collected by vitest (everything else). */
export const vitestUnitFiles: string[] = classified.vitest;
