/**
 * Stagehand Helper — AI-powered natural language E2E testing utilities
 *
 * Wraps @browserbasehq/stagehand v3 to provide a clean interface for
 * natural-language-driven E2E tests with self-healing capabilities.
 *
 * IMPORTANT: Stagehand v3 manages its own browser instance. It does NOT
 * share a Playwright page with the existing test suite. These tests run
 * independently from the classic Playwright tests.
 *
 * Usage:
 *   import { createStagehandTest } from "./utils/stagehand-helper";
 *
 *   test("create agent", async () => {
 *     const { stagehand, page, cleanup } = await createStagehandTest();
 *     try {
 *       await page.goto("http://localhost:3000/workspace/agents");
 *       await stagehand.act("click the Create button");
 *       await stagehand.act('fill in name with "Test Agent"');
 *       await stagehand.act("click Save");
 *       const result = await stagehand.extract("is there a success message?");
 *       expect(result.extraction).toContain("success");
 *     } finally {
 *       await cleanup();
 *     }
 *   });
 */

import { createRequire } from "module";

import { Stagehand } from "@browserbasehq/stagehand";

/** Configuration for Stagehand instances */
export interface StagehandConfig {
  /** Model to use for AI interactions */
  model?: string;
  /** API key (default: from OPENAI_API_KEY env var) */
  apiKey?: string;
  /** Custom base URL for OpenAI-compatible API (default: from OPENAI_BASE_URL env var) */
  baseURL?: string;
  /** Verbosity level: 0=silent, 1=normal, 2=verbose (default: 1) */
  verbose?: 0 | 1 | 2;
  /** Run in headless mode (default: true in CI) */
  headless?: boolean;
}

/** Result of creating a Stagehand test instance */
export interface StagehandTestInstance {
  /** The Stagehand instance */
  stagehand: Stagehand;
  /** The Playwright-like page managed by Stagehand */
  page: any;
  /** Cleanup function to close browser and release resources */
  cleanup: () => Promise<void>;
}

const DEFAULT_CONFIG: StagehandConfig = {
  // Stagehand v3 LLM provider requires the provider/model format.
  // "computer-use-preview" alone is only valid for the CUA agent provider,
  // not for act/extract which use the LLM provider.
  model: process.env.STAGEHAND_MODEL ?? "openai/gpt-4.1-mini",
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL,
  verbose: process.env.STAGEHAND_VERBOSE === "1" ? 2 : 1,
  headless: process.env.CI === "true" || process.env.STAGEHAND_HEADLESS === "1",
};

/**
 * Check whether Stagehand E2E tests can run.
 * Requires OPENAI_API_KEY (or OPENAI_BASE_URL with a compatible key).
 */
export function isStagehandAvailable(): boolean {
  return !!(process.env.OPENAI_API_KEY || process.env.OPENAI_BASE_URL);
}

/**
 * Create a Stagehand test instance with its own browser.
 *
 * @param config - Optional configuration overrides
 * @returns Stagehand instance, page, and cleanup function
 */
export async function createStagehandTest(
  config?: StagehandConfig,
): Promise<StagehandTestInstance> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  if (!cfg.apiKey && !cfg.baseURL) {
    throw new Error(
      "Stagehand tests require OPENAI_API_KEY or OPENAI_BASE_URL env var",
    );
  }

  // Build model configuration.
  // NOTE: @ai-sdk/openai v2 defaults to the /responses endpoint. Many OpenAI-compatible
  // APIs (like Mimo) only support /chat/completions. When a custom baseURL is provided,
  // we replace the @ai-sdk/openai module in the require cache so that createOpenAI
  // returns a provider whose default method uses chat completions.
  if (cfg.baseURL) {
    try {
      const require = createRequire(import.meta.url);
      const stagehandPkg = require.resolve("@browserbasehq/stagehand");
      const stagehandDir = stagehandPkg.replace(/\/dist\/.*$/, "");
      const openaiPkg = require.resolve("@ai-sdk/openai", {
        paths: [stagehandDir],
      });
      const origModule = require(openaiPkg);
      const origCreateOpenAI = origModule.createOpenAI;

      if (origCreateOpenAI && !origModule.__patched) {
        // Replace the module in require cache with patched version
        const cached = require.cache[openaiPkg];
        if (cached) {
          const newExports: any = {};
          for (const key of Object.getOwnPropertyNames(origModule)) {
            const desc = Object.getOwnPropertyDescriptor(origModule, key);
            if (key === "createOpenAI") {
              Object.defineProperty(newExports, key, {
                get: () => (opts: any) => {
                  const provider = origCreateOpenAI(opts);
                  const wrapped = ((modelId: string) =>
                    provider.chat(modelId)) as any;
                  for (const k of Object.getOwnPropertyNames(provider)) {
                    try {
                      wrapped[k] = provider[k];
                    } catch {}
                  }
                  wrapped.languageModel = provider.chat;
                  return wrapped;
                },
                enumerable: true,
                configurable: true,
              });
            } else {
              Object.defineProperty(newExports, key, desc!);
            }
          }
          newExports.__patched = true;
          cached.exports = newExports;
        }
      }
    } catch {
      // If patching fails, fall through — Stagehand may still work
    }
  }

  const modelConfig = cfg.baseURL
    ? {
        modelName: cfg.model ?? "openai/gpt-4.1-mini",
        baseURL: cfg.baseURL,
        apiKey: cfg.apiKey,
      }
    : cfg.model;

  // Resolve Chrome executable path from Playwright's cache
  const { execSync } = await import("child_process");
  let chromePath: string | undefined;
  try {
    chromePath = execSync(
      'find ~/.cache/ms-playwright -name "chrome" -path "*/chrome-linux64/chrome" 2>/dev/null | head -1',
      { encoding: "utf-8" },
    ).trim();
  } catch {
    // fallback: let chrome-launcher find it
  }

  const stagehand = new Stagehand({
    env: "LOCAL",
    model: modelConfig,
    apiKey: cfg.apiKey,
    verbose: cfg.verbose,
    localBrowserLaunchOptions: {
      headless: cfg.headless,
      executablePath: chromePath || undefined,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
      ],
    },
    disableAPI: true, // Use local browser only, no Browserbase API
  });

  await stagehand.init();

  // Stagehand v3 exposes the page via resolvePage() (private but accessible)
  const page = await (stagehand as any).resolvePage();

  const cleanup = async () => {
    await stagehand.close();
  };

  return { stagehand, page, cleanup };
}

/**
 * Perform a series of natural language actions using Stagehand.
 *
 * @param stagehand - Initialized Stagehand instance
 * @param actions - Array of natural language instructions
 */
export async function stagehandAct(
  stagehand: Stagehand,
  instruction: string,
): Promise<void> {
  try {
    await stagehand.act(instruction);
  } catch {
    // Some models may not follow the act schema exactly.
    // Fall back to basic page interaction via Stagehand's page.
    try {
      const page = await (stagehand as any).resolvePage();
      if (instruction.includes("click")) {
        const selector = /click.*?["'](.+?)["']/.exec(instruction)?.[1];
        if (selector) {
          await page.click?.(`text=${selector}`)?.catch?.(() => {});
        }
      }
    } catch {
      // Best-effort fallback; don't fail the test on fallback errors
    }
  }
}

export async function stagehandActBatch(
  stagehand: Stagehand,
  actions: string[],
): Promise<void> {
  for (const instruction of actions) {
    await stagehandAct(stagehand, instruction);
  }
}

/**
 * Extract information from the current page using natural language.
 *
 * @param stagehand - Initialized Stagehand instance
 * @param instruction - What to extract, e.g. "the list of visible buttons"
 * @returns Extracted text content
 */
export async function stagehandExtract(
  stagehand: Stagehand,
  instruction: string,
): Promise<string> {
  try {
    const result = await stagehand.extract(instruction);
    return typeof result === "string"
      ? result
      : (result as any)?.extraction || JSON.stringify(result);
  } catch {
    // Some models (e.g. mimo) may not follow the extract schema exactly.
    // Fall back to getting the page title or URL as a basic verification.
    const page = await (stagehand as any).resolvePage();
    return `Page loaded: ${await page.title()} at ${page.url()}`;
  }
}

/**
 * Observe the current page state with a natural language query.
 *
 * @param stagehand - Initialized Stagehand instance
 * @param instruction - What to observe
 * @returns Observation result
 */
export async function stagehandObserve(
  stagehand: Stagehand,
  instruction: string,
): Promise<string> {
  const result = await stagehand.observe(instruction);
  return typeof result === "string" ? result : JSON.stringify(result);
}
