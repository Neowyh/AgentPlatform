import { execFileSync } from "child_process";
import { existsSync, readdirSync, readFileSync } from "fs";
import { join, resolve } from "path";

import { expect, type Page } from "@playwright/test";

type Manifest = {
  config_path: string;
  database_path: string;
  ideer_home: string;
};

function requiredEnv(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`Real E2E runner did not provide ${name}`);
  return value;
}

/** True when the Real E2E harness (GitHub Actions Real E2E lane) is present. */
export function hasRealE2EEnvironment() {
  if (!process.env.E2E_STATE_DIR || !process.env.E2E_RUN_ID) {
    return false;
  }
  return existsSync(join(process.env.E2E_STATE_DIR, "manifest.json"));
}

export function hasRealModelEnvironment() {
  return (
    hasRealE2EEnvironment() &&
    process.env.REAL_E2E_REAL_MODEL === "1" &&
    Boolean(process.env.REAL_E2E_MODEL_NAME) &&
    Boolean(process.env.REAL_E2E_EXPECTED_MARKER)
  );
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

export function seedAgentResourceId(suffix: string) {
  return requiredDatabaseValue(
    "SELECT id FROM resources WHERE type = 'agent' AND slug = ?",
    [seedAgentName(suffix)],
    `${suffix} resource id`,
  );
}

export function seedWorkflowResourceId() {
  return requiredDatabaseValue(
    "SELECT id FROM resources WHERE type = 'workflow' AND slug = ?",
    [runScopedName("knowledge-workflow")],
    "knowledge workflow resource id",
  );
}

export function seedWorkflowRunId(workflowResourceId: string) {
  return requiredDatabaseValue(
    "SELECT run_id FROM workflow_v2_runs WHERE workflow_resource_id = ? ORDER BY created_at DESC LIMIT 1",
    [workflowResourceId],
    "knowledge workflow run id",
  );
}

export function seedRealModelWorkflowResourceId() {
  return requiredDatabaseValue(
    "SELECT id FROM resources WHERE type = 'workflow' AND slug = ?",
    [runScopedName("real-model-workflow")],
    "real model workflow resource id",
  );
}

export function seedRealModelManifestHash() {
  return requiredDatabaseValue(
    "SELECT r.manifest_hash FROM knowledge_base_revisions r JOIN knowledge_bases k ON k.active_revision_id = r.id JOIN resources x ON x.id = k.resource_id WHERE x.slug = ?",
    [runScopedName("real-model-kb")],
    "real model manifest hash",
  );
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
    !value.config_path ||
    !existsSync(value.database_path) ||
    !existsSync(value.ideer_home) ||
    !existsSync(value.config_path)
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
      "SELECT resources.owner_id FROM resources JOIN users ON resources.owner_id = users.id WHERE resources.type = 'agent' AND resources.slug = ? AND users.email = ?",
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
    "SELECT status FROM visibility_applications WHERE resource_type = 'agent' AND canonical_resource_id = ? AND reason = ?",
    [agentName, reason],
  );
  if (application?.[0] !== status) {
    throw new Error(
      `Expected ${agentName} application to be ${status}, got ${JSON.stringify(application)}`,
    );
  }
  const resource = queryDatabase(
    "SELECT visibility FROM resources WHERE type = 'agent' AND id = ?",
    [agentName],
  );
  if (resource?.[0] !== visibility) {
    throw new Error(
      `Expected ${agentName} visibility ${visibility}, got ${JSON.stringify(resource)}`,
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
  const configuredStoragePath = execFileSync(
    "python3",
    [
      "-c",
      "import sys, yaml; config = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}; memory = config.get('memory') or {}; backend = memory.get('backend_config') or {}; print(backend.get('storage_path') or '')",
      manifest().config_path,
    ],
    { encoding: "utf8" },
  ).trim();
  const memoryStorageRoot = configuredStoragePath
    ? resolve(manifest().ideer_home, configuredStoragePath)
    : manifest().ideer_home;
  const memoryRoot = resolve(memoryStorageRoot, "users", userId);
  const memoryPath = resolve(memoryRoot, "memory.json");

  function storageContainsFact(): boolean {
    if (
      existsSync(memoryPath) &&
      readFileSync(memoryPath, "utf8").includes(content)
    ) {
      return true;
    }
    const factsRoot = resolve(memoryRoot, "agents", "__default__", "facts");
    if (!existsSync(factsRoot)) return false;
    const pending = [factsRoot];
    while (pending.length > 0) {
      const directory = pending.pop()!;
      for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const path = resolve(directory, entry.name);
        if (entry.isDirectory()) pending.push(path);
        else if (
          entry.isFile() &&
          readFileSync(path, "utf8").includes(content)
        ) {
          return true;
        }
      }
    }
    return false;
  }

  await expect
    .poll(
      async () => {
        const exists = existsSync(memoryPath);
        return { exists, found: storageContainsFact() };
      },
      {
        timeout: 15_000,
        message: `memory.json ${expected ? "contains" : "excludes"} "${content}"`,
      },
    )
    .toEqual({ exists: true, found: expected });
}
