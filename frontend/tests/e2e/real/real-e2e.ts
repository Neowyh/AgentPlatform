import { execFileSync } from "child_process";
import { existsSync, readFileSync } from "fs";
import { join, resolve } from "path";

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
    "department_admin@test.com": "department_admin",
    "user@test.com": "user",
    "viewer@test.com": "viewer",
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

  for (const [agentSuffix, ownerEmail] of [
    ["viewer-agent", "viewer@test.com"],
    ["approve-agent", "user@test.com"],
    ["reject-agent", "user@test.com"],
  ]) {
    requiredDatabaseValue(
      "SELECT resource_metadata.owner_id FROM resource_metadata JOIN users ON resource_metadata.owner_id = users.id WHERE resource_metadata.resource_type = 'agent' AND resource_metadata.resource_id = ? AND users.email = ?",
      [seedAgentName(agentSuffix), ownerEmail],
      `${agentSuffix} ownership by ${ownerEmail}`,
    );
  }

  const departmentBoundary = queryDatabase(
    "SELECT applications.department_id, department_admin.department_id FROM visibility_applications AS applications JOIN users AS admins ON admins.email = 'department_admin@test.com' JOIN users_ext AS department_admin ON department_admin.id = admins.id WHERE applications.resource_type = 'agent' AND applications.resource_id = ? AND applications.reason = ?",
    [
      seedAgentName("cross-department-agent"),
      runScopedName("cross-department-pending"),
    ],
  );
  if (
    !departmentBoundary?.[0] ||
    departmentBoundary[0] === departmentBoundary[1]
  ) {
    throw new Error(
      `Cross-department seed does not cross a boundary: ${JSON.stringify(departmentBoundary)}`,
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

export function expectMemoryStorageToContain(content: string, expected = true) {
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
  if (!existsSync(memoryPath)) {
    throw new Error(`Expected super admin memory file at ${memoryPath}`);
  }
  const found = readFileSync(memoryPath, "utf8").includes(content);
  if (found !== expected) {
    throw new Error(
      `Expected isolated memory storage to ${expected ? "contain" : "exclude"} ${content}`,
    );
  }
}
