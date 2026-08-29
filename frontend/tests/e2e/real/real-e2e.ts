import { execFileSync } from "child_process";
import { existsSync, readFileSync } from "fs";
import { join, resolve } from "path";

import { expect, type Page } from "@playwright/test";

type Manifest = { database_path: string; ideer_home: string };

function requiredEnv(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`Real E2E runner did not provide ${name}`);
  return value;
}

export function requireRealE2EEnvironment() {
  const stateDir = requiredEnv("E2E_STATE_DIR");
  requiredEnv("E2E_RUN_ID");
  requiredEnv("IDEER_INTERNAL_GATEWAY_BASE_URL");
  if (!existsSync(join(stateDir, "manifest.json"))) {
    throw new Error(`Real E2E manifest is missing from ${stateDir}`);
  }
}

export function runScopedName(suffix: string) {
  return `e2e-${requiredEnv("E2E_RUN_ID")}-${suffix}`;
}

export function seedAgentName(suffix: string) {
  return runScopedName(suffix);
}

export async function loginAsRealUser(page: Page, email: string) {
  await page.goto("/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(email);
  await page.getByRole("button", { name: /sign in|登录/i }).click();

  await expect
    .poll(
      async () =>
        (await page.context().cookies()).some(
          (cookie) => cookie.name === "access_token",
        ),
      { timeout: 60_000 },
    )
    .toBe(true);
  await expect(page).toHaveURL(/\/workspace/, { timeout: 60_000 });
}

function manifest(): Manifest {
  const manifestPath = join(requiredEnv("E2E_STATE_DIR"), "manifest.json");
  const value = JSON.parse(readFileSync(manifestPath, "utf8")) as Manifest;
  if (
    !value.database_path ||
    !value.ideer_home ||
    !existsSync(value.database_path) ||
    !existsSync(value.ideer_home)
  ) {
    throw new Error(`Manifest paths are unavailable: ${manifestPath}`);
  }
  return value;
}

export function queryDatabase(sql: string, params: string[]) {
  const program = [
    "import json, sqlite3, sys",
    "connection = sqlite3.connect(sys.argv[1])",
    "row = connection.execute(sys.argv[2], json.loads(sys.argv[3])).fetchone()",
    "print(json.dumps(list(row) if row else None))",
  ].join("; ");
  const output = execFileSync(
    "python3",
    ["-c", program, manifest().database_path, sql, JSON.stringify(params)],
    { encoding: "utf8" },
  );
  return JSON.parse(output) as unknown[] | null;
}

function requiredDatabaseValue(
  sql: string,
  params: string[],
  description: string,
) {
  const row = queryDatabase(sql, params);
  if (!row?.[0] || typeof row[0] !== "string") {
    throw new Error(`Missing ${description}: ${JSON.stringify(row)}`);
  }
  return row[0];
}

export function assertRbacSeed() {
  const expectedRoles = {
    "super_admin@test.com": "super_admin",
    "user@test.com": "user",
  } as const;
  for (const [email, role] of Object.entries(expectedRoles)) {
    const row = queryDatabase(
      "SELECT users_ext.role FROM users JOIN users_ext ON users.id = users_ext.id WHERE users.email = ?",
      [email],
    );
    if (row?.[0] !== role) {
      throw new Error(
        `Expected ${email} to have ${role}, got ${JSON.stringify(row)}`,
      );
    }
  }

  for (const agentSuffix of ["approve-agent", "reject-agent"] as const) {
    requiredDatabaseValue(
      "SELECT resource_metadata.owner_id FROM resource_metadata JOIN users ON resource_metadata.owner_id = users.id WHERE resource_metadata.resource_type = 'agent' AND resource_metadata.resource_id = ? AND users.email = ?",
      [seedAgentName(agentSuffix), "user@test.com"],
      `${agentSuffix} ownership by user@test.com`,
    );
  }
}

export function expectVisibilityState({
  agentName,
  reason,
  status,
  visibility,
}: {
  agentName: string;
  reason: string;
  status: "approved" | "rejected";
  visibility: "department" | "private";
}) {
  const application = queryDatabase(
    "SELECT status FROM visibility_applications WHERE resource_type = 'agent' AND resource_id = ? AND reason = ?",
    [agentName, reason],
  );
  if (application?.[0] !== status) {
    throw new Error(
      `Expected ${agentName} application to be ${status}, got ${JSON.stringify(application)}`,
    );
  }
  const metadata = queryDatabase(
    "SELECT visibility FROM resource_metadata WHERE resource_type = 'agent' AND resource_id = ?",
    [agentName],
  );
  if (metadata?.[0] !== visibility) {
    throw new Error(
      `Expected ${agentName} visibility ${visibility}, got ${JSON.stringify(metadata)}`,
    );
  }
}

export async function expectMemoryStorageToContain(
  content: string,
  expected = true,
) {
  const userId = requiredDatabaseValue(
    "SELECT id FROM users WHERE email = 'super_admin@test.com'",
    [],
    "super admin user id",
  );
  const memoryPath = resolve(
    manifest().ideer_home,
    "users",
    userId,
    "memory.json",
  );

  await expect
    .poll(
      async () => {
        if (!existsSync(memoryPath)) return { exists: false, found: false };
        const raw = readFileSync(memoryPath, "utf8");
        return { exists: true, found: raw.includes(content) };
      },
      {
        timeout: 15_000,
        message: `memory.json ${expected ? "contains" : "excludes"} "${content}"`,
      },
    )
    .toEqual({ exists: true, found: expected });
}
