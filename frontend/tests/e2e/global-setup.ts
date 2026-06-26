/**
 * Playwright Global Setup — authenticate once and save storage state.
 *
 * This runs BEFORE the webServer starts, so it talks directly to the
 * backend at http://localhost:8001.  The saved cookies are loaded by
 * every test project that sets `storageState` in playwright.config.ts.
 *
 * Auth-specific tests (smoke-login, auth-flow) override storageState
 * with an empty object so they start unauthenticated.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import type { FullConfig } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const TEST_EMAIL = "super_admin@test.com";
const TEST_PASSWORD = "super_admin@test.com";
const BACKEND_URL = "http://localhost:8001";

interface PlaywrightCookie {
  name: string;
  value: string;
  domain: string;
  path: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: "Strict" | "Lax" | "None";
}

function parseSetCookie(header: string): PlaywrightCookie {
  const segments = header.split(";").map((s) => s.trim());
  const nameValue = segments[0] ?? "";
  const eqIdx = nameValue.indexOf("=");
  const name = nameValue.slice(0, eqIdx);
  const value = nameValue.slice(eqIdx + 1);

  const cookie: PlaywrightCookie = {
    name,
    value,
    domain: "localhost",
    path: "/",
    httpOnly: false,
    secure: false,
    sameSite: "Lax",
  };

  for (const attr of segments.slice(1)) {
    const lower = attr.toLowerCase();
    if (lower === "httponly") cookie.httpOnly = true;
    if (lower === "secure") cookie.secure = true;
    if (lower.startsWith("samesite=")) {
      const raw = attr.split("=")[1]?.trim() ?? "Lax";
      cookie.sameSite = (raw.charAt(0).toUpperCase() +
        raw.slice(1).toLowerCase()) as "Strict" | "Lax" | "None";
    }
    if (lower.startsWith("path=")) {
      cookie.path = attr.split("=")[1]?.trim() ?? "/";
    }
  }

  return cookie;
}

async function globalSetup(_config: FullConfig): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/v1/auth/login/local`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `username=${encodeURIComponent(TEST_EMAIL)}&password=${encodeURIComponent(TEST_PASSWORD)}`,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `[global-setup] Login failed: ${res.status} ${res.statusText} — ${body}`,
    );
  }

  const setCookieHeaders = res.headers.getSetCookie();
  if (!setCookieHeaders || setCookieHeaders.length === 0) {
    throw new Error(
      "[global-setup] Login succeeded but no Set-Cookie headers returned.",
    );
  }

  const cookies = setCookieHeaders.map(parseSetCookie);

  const storageState = { cookies, origins: [] };
  const statePath = path.resolve(__dirname, ".auth/storage-state.json");
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  fs.writeFileSync(statePath, JSON.stringify(storageState, null, 2));

  // Expose the path so config can reference it
  process.env.STORAGE_STATE = statePath;
}

export default globalSetup;
