#!/usr/bin/env bash
# Seed a specific isolated backend. The manifest is the run capability.
set -euo pipefail

if [[ "${QA_ISOLATED:-}" != "1" ]]; then
  echo "QA_ISOLATED=1 is required for real E2E seeding." >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/manifest.json" >&2
  exit 2
fi

MANIFEST_PATH="$1"
if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "Manifest not found: $MANIFEST_PATH" >&2
  exit 2
fi

mapfile -t manifest_values < <(python3 - "$MANIFEST_PATH" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1]).resolve()
data = json.loads(path.read_text(encoding="utf-8"))
required = ("state_dir", "pid", "port", "base_url", "config_path", "sqlite_dir", "database_path", "ideer_home", "log_path", "run_id")
missing = [key for key in required if not data.get(key)]
if missing:
    raise SystemExit(f"manifest missing required fields: {', '.join(missing)}")
if pathlib.Path(data["state_dir"]).resolve() != path.parent:
    raise SystemExit("manifest state_dir does not match its parent directory")
if pathlib.Path(data["ideer_home"]).resolve() != path.parent:
    raise SystemExit("manifest ideer_home does not match its parent directory")
for key in required:
    print(data[key])
PY
)
STATE_DIR="${manifest_values[0]}"
PID="${manifest_values[1]}"
PORT="${manifest_values[2]}"
BASE_URL="${manifest_values[3]}"
LOG_PATH="${manifest_values[8]}"
RUN_ID="${manifest_values[9]}"
LOGS_DIR="$(dirname "$LOG_PATH")"

if ! kill -0 "$PID" 2>/dev/null; then
  echo "Backend PID $PID from manifest is not running." >&2
  exit 1
fi
if [[ ! -d "$STATE_DIR" || ! -d "$LOGS_DIR" ]]; then
  echo "Manifest state directory is incomplete: $STATE_DIR" >&2
  exit 1
fi

COOKIE_DIR="$(mktemp -d "$STATE_DIR/cookies-XXXXXX")"
ADMIN_COOKIE="$COOKIE_DIR/admin.txt"
USER_COOKIE="$COOKIE_DIR/user.txt"
CROSS_DEPARTMENT_COOKIE="$COOKIE_DIR/cross-department-user.txt"
RESPONSE_FILE="$STATE_DIR/seed-response.json"
trap 'rm -rf "$COOKIE_DIR" "$RESPONSE_FILE"' EXIT

fail_response() {
  echo "Seed request failed: $1" >&2
  [[ -f "$RESPONSE_FILE" ]] && cat "$RESPONSE_FILE" >&2
  exit 1
}

request() {
  local expected="$1"
  shift
  local args=("$@")
  local cookie_jar=""
  local csrf_token=""
  local actual

  for ((index = 0; index < ${#args[@]} - 1; index++)); do
    if [[ "${args[$index]}" == "-b" ]]; then
      cookie_jar="${args[$((index + 1))]}"
      break
    fi
  done
  if [[ -n "$cookie_jar" ]]; then
    csrf_token="$(awk '$6 == "csrf_token" { print $7 }' "$cookie_jar")"
    [[ -n "$csrf_token" ]] || fail_response "csrf_token missing from $cookie_jar"
    args+=(-H "X-CSRF-Token: $csrf_token")
  fi

  actual="$(curl --silent --show-error --output "$RESPONSE_FILE" --write-out '%{http_code}' "${args[@]}")" || fail_response "curl transport error"
  [[ "$actual" == "$expected" ]] || fail_response "expected HTTP $expected, got $actual"
}

json_value() {
  local field="$1"
  python3 - "$field" "$RESPONSE_FILE" <<'PY'
import json
import sys

with open(sys.argv[2], encoding="utf-8") as response:
    value = json.load(response)
for part in sys.argv[1].split("."):
    value = value[part]
if value in (None, ""):
    raise SystemExit(1)
print(value)
PY
}

echo "Initializing isolated backend at $BASE_URL"
request 201 -X POST "$BASE_URL/api/v1/auth/initialize" -H 'Content-Type: application/json' \
  --data '{"email":"super_admin@test.com","password":"super_admin@test.com"}'

request 200 -c "$ADMIN_COOKIE" -X POST "$BASE_URL/api/v1/auth/login/local" \
  --data 'username=super_admin@test.com&password=super_admin@test.com'

create_department() {
  local name="$1"
  local description="$2"
  request 200 -b "$ADMIN_COOKIE" -X POST "$BASE_URL/api/admin/departments" -H 'Content-Type: application/json' \
    --data "{\"name\":\"$name\",\"description\":\"$description\"}"
  json_value id
}

DEPARTMENT_ID="$(create_department 'Real E2E Engineering' 'Isolated real E2E department')"
CROSS_DEPARTMENT_ID="$(create_department 'Real E2E Cross Department' 'Isolated real E2E cross-department fixture')"
if [[ "$DEPARTMENT_ID" == "$CROSS_DEPARTMENT_ID" ]]; then
  echo "Cross-department fixture must use a different department." >&2
  exit 1
fi

create_user() {
  local email="$1"
  local role="$2"
  local department_id="$3"
  request 201 -b "$ADMIN_COOKIE" -X POST "$BASE_URL/api/admin/users" -H 'Content-Type: application/json' \
    --data "{\"email\":\"$email\",\"password\":\"$email\",\"username\":\"$email\",\"role\":\"$role\",\"department_id\":\"$department_id\"}"
}

create_user 'department_admin@test.com' 'user' "$DEPARTMENT_ID"
DEPARTMENT_ADMIN_ID="$(json_value id)"
create_user 'user@test.com' 'user' "$DEPARTMENT_ID"
create_user 'viewer@test.com' 'viewer' "$DEPARTMENT_ID"
create_user 'cross-department-user@test.com' 'user' "$CROSS_DEPARTMENT_ID"

request 200 -b "$ADMIN_COOKIE" -X PUT "$BASE_URL/api/admin/users/$DEPARTMENT_ADMIN_ID/role" -H 'Content-Type: application/json' \
  --data '{"role":"department_admin"}'

request 200 -c "$USER_COOKIE" -X POST "$BASE_URL/api/v1/auth/login/local" \
  --data 'username=user@test.com&password=user@test.com'

request 200 -c "$CROSS_DEPARTMENT_COOKIE" -X POST "$BASE_URL/api/v1/auth/login/local" \
  --data 'username=cross-department-user@test.com&password=cross-department-user@test.com'

create_agent() {
  local name="$1"
  request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/agents" -H 'Content-Type: application/json' \
    --data "{\"name\":\"$name\",\"description\":\"Isolated real E2E resource $name\",\"skills\":[],\"soul\":\"Real E2E seed resource.\"}"
}

VIEWER_AGENT="e2e-${RUN_ID}-viewer-agent"
APPROVE_AGENT="e2e-${RUN_ID}-approve-agent"
REJECT_AGENT="e2e-${RUN_ID}-reject-agent"
create_agent "$VIEWER_AGENT"
create_agent "$APPROVE_AGENT"
create_agent "$REJECT_AGENT"

CROSS_DEPARTMENT_AGENT="e2e-${RUN_ID}-cross-department-agent"
request 201 -b "$CROSS_DEPARTMENT_COOKIE" -X POST "$BASE_URL/api/agents" -H 'Content-Type: application/json' \
  --data "{\"name\":\"$CROSS_DEPARTMENT_AGENT\",\"description\":\"Isolated real E2E cross-department resource $CROSS_DEPARTMENT_AGENT\",\"skills\":[],\"soul\":\"Real E2E cross-department seed resource.\"}"

request 201 -b "$CROSS_DEPARTMENT_COOKIE" -X POST "$BASE_URL/api/visibility-applications" -H 'Content-Type: application/json' \
  --data "{\"resource_type\":\"agent\",\"resource_id\":\"$CROSS_DEPARTMENT_AGENT\",\"target_visibility\":\"public\",\"reason\":\"e2e-${RUN_ID}-cross-department-pending\"}"

request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/visibility-applications" -H 'Content-Type: application/json' \
  --data "{\"resource_type\":\"agent\",\"resource_id\":\"$VIEWER_AGENT\",\"target_visibility\":\"public\",\"reason\":\"Seed public resource for viewer role checks\"}"
PUBLIC_APPLICATION_ID="$(json_value id)"
PUBLIC_APPLICATION_VERSION="$(json_value version)"

request 200 -b "$ADMIN_COOKIE" -X PUT "$BASE_URL/api/visibility-applications/$PUBLIC_APPLICATION_ID" -H 'Content-Type: application/json' \
  --data "{\"action\":\"approved\",\"comment\":\"Seed visibility\",\"version\":$PUBLIC_APPLICATION_VERSION}"

rm -f "$RESPONSE_FILE"
echo "Seed complete: $VIEWER_AGENT, $APPROVE_AGENT, and $REJECT_AGENT."
