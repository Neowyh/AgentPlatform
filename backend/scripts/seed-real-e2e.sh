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
DATABASE_PATH="${manifest_values[6]}"
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
  if [[ "$actual" != "$expected" ]]; then
    {
      echo "---"
      echo "expected HTTP $expected, got $actual"
      echo "--- response body (first 500 chars) ---"
      head -c 500 "$RESPONSE_FILE" 2>/dev/null || echo "(no response body)"
      echo ""
      echo "---"
    } >&2
    fail_response "expected HTTP $expected, got $actual"
  fi
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

create_user() {
  local email="$1"
  local role="$2"
  local department_id="$3"
  request 201 -b "$ADMIN_COOKIE" -X POST "$BASE_URL/api/admin/users" -H 'Content-Type: application/json' \
    --data "{\"email\":\"$email\",\"password\":\"$email\",\"username\":\"$email\",\"role\":\"$role\",\"department_id\":\"$department_id\"}"
}

create_user 'user@test.com' 'user' "$DEPARTMENT_ID"

request 200 -c "$USER_COOKIE" -X POST "$BASE_URL/api/v1/auth/login/local" \
  --data 'username=user@test.com&password=user@test.com'

create_agent() {
  local name="$1"
  request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources" -H 'Content-Type: application/json' \
    --data "{\"type\":\"agent\",\"slug\":\"$name\",\"display_name\":\"$name\",\"storage_kind\":\"filesystem\"}"
  local resource_id
  resource_id="$(json_value id)"
  request 200 -b "$USER_COOKIE" -X PUT "$BASE_URL/api/resources/$resource_id/agent-draft" -H 'Content-Type: application/json' \
    --data "{\"config\":{\"name\":\"$name\",\"description\":\"Isolated real E2E resource $name\",\"skills\":[]},\"soul\":\"Real E2E seed resource.\",\"expected_revision\":0}"
  request 200 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources/$resource_id/publish" -H 'Content-Type: application/json' \
    --data '{"expected_draft_revision":1}'
}

APPROVE_AGENT="e2e-${RUN_ID}-approve-agent"
REJECT_AGENT="e2e-${RUN_ID}-reject-agent"
create_agent "$APPROVE_AGENT"
create_agent "$REJECT_AGENT"

REAL_MODEL_WORKFLOW=""
if [[ "${REAL_E2E_REAL_MODEL:-0}" == "1" ]]; then
  REAL_MODEL_DATASET_ID="${REAL_E2E_RAGFLOW_DATASET_ID:-}"
  [[ -n "$REAL_MODEL_DATASET_ID" ]] || {
    echo "REAL_E2E_RAGFLOW_DATASET_ID is required when REAL_E2E_REAL_MODEL=1." >&2
    exit 2
  }

  REAL_MODEL_KB="e2e-${RUN_ID}-real-model-kb"
  request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources" -H 'Content-Type: application/json' \
    --data "{\"type\":\"knowledge_base\",\"slug\":\"$REAL_MODEL_KB\",\"display_name\":\"$REAL_MODEL_KB\",\"storage_kind\":\"database\"}"
  REAL_MODEL_KB_ID="$(json_value id)"
  request 200 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources/$REAL_MODEL_KB_ID/knowledge" -H 'Content-Type: application/json' \
    --data "{\"provider_dataset_id\":\"$REAL_MODEL_DATASET_ID\",\"provider_type\":\"ragflow\"}"

  # The provider dataset and its marker are created by the real RAGFlow gate.
  # Seed a published immutable revision that points at that dataset so the
  # browser-triggered run exercises the same production closure resolver.
  REAL_MODEL_REVISION_ID="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
  python3 - "$DATABASE_PATH" "$REAL_MODEL_KB_ID" "$REAL_MODEL_REVISION_ID" "$REAL_MODEL_DATASET_ID" <<'PY'
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

database_path, kb_id, revision_id, dataset_id = sys.argv[1:]
now = datetime.now(timezone.utc).isoformat()
with sqlite3.connect(database_path) as connection:
    user_id = connection.execute(
        "SELECT id FROM users_ext WHERE id IN (SELECT id FROM users WHERE email = 'user@test.com')"
    ).fetchone()[0]
    manifest = []
    manifest_hash = hashlib.sha256(b"[]").hexdigest()
    connection.execute(
        "UPDATE knowledge_bases SET provider_dataset_id = ?, sync_status = 'ok', initialization_status = 'ready', initialization_step = 'ready' WHERE resource_id = ?",
        (dataset_id, kb_id),
    )
    connection.execute(
        "UPDATE resources SET latest_version = 1, draft_revision = 1 WHERE id = ?",
        (kb_id,),
    )
    connection.execute(
        "INSERT INTO resource_versions (id, resource_id, version, content_hash, storage_key, scan_result, content, created_by, published_at) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            kb_id,
            hashlib.sha256(b"{}").hexdigest(),
            f"knowledge_bases/{kb_id}",
            json.dumps({}),
            json.dumps({}),
            user_id,
            now,
        ),
    )
    connection.execute(
        "INSERT INTO knowledge_base_revisions "
        "(id, knowledge_base_id, revision_no, status, manifest_hash, manifest_json, provider_doc_map_json, document_count, provider_dataset_id, publish_attempt, integrity_status, created_by, created_at, published_at) "
        "VALUES (?, ?, 1, 'published', ?, ?, ?, 0, ?, 1, 'healthy', ?, ?, ?)",
        (revision_id, kb_id, manifest_hash, json.dumps(manifest), json.dumps({}), dataset_id, user_id, now, now),
    )
    connection.execute("UPDATE knowledge_bases SET active_revision_id = ? WHERE resource_id = ?", (revision_id, kb_id))
    connection.commit()
PY

  REAL_MODEL_AGENT="e2e-${RUN_ID}-real-model-agent"
  request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources" -H 'Content-Type: application/json' \
    --data "{\"type\":\"agent\",\"slug\":\"$REAL_MODEL_AGENT\",\"display_name\":\"$REAL_MODEL_AGENT\",\"storage_kind\":\"filesystem\"}"
  REAL_MODEL_AGENT_ID="$(json_value id)"
  request 200 -b "$USER_COOKIE" -X PUT "$BASE_URL/api/resources/$REAL_MODEL_AGENT_ID/agent-draft" -H 'Content-Type: application/json' \
    --data "{\"config\":{\"name\":\"$REAL_MODEL_AGENT\",\"description\":\"Browser real model acceptance agent\",\"skills\":[],\"tool_groups\":[\"knowledge\"]},\"soul\":\"Use knowledge_search with gate-kb and answer the marker only.\",\"knowledge_dependencies\":[{\"resource_id\":\"$REAL_MODEL_KB_ID\",\"dependency_mode\":\"pinned\",\"revision_id\":\"$REAL_MODEL_REVISION_ID\",\"required\":true,\"purpose\":\"M4 browser real model proof\"}],\"expected_revision\":0}"
  request 200 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources/$REAL_MODEL_AGENT_ID/publish" -H 'Content-Type: application/json' \
    --data '{"expected_draft_revision":1}'

  REAL_MODEL_WORKFLOW="e2e-${RUN_ID}-real-model-workflow"
  request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources" -H 'Content-Type: application/json' \
    --data "{\"type\":\"workflow\",\"slug\":\"$REAL_MODEL_WORKFLOW\",\"display_name\":\"$REAL_MODEL_WORKFLOW\",\"storage_kind\":\"database\"}"
  REAL_MODEL_WORKFLOW_ID="$(json_value id)"
  request 200 -b "$USER_COOKIE" -X PUT "$BASE_URL/api/resources/$REAL_MODEL_WORKFLOW_ID/workflow-draft" -H 'Content-Type: application/json' \
    --data "{\"content\":{\"schema_version\":2,\"name\":\"$REAL_MODEL_WORKFLOW\",\"inputs\":{},\"state\":{},\"entrypoint\":\"run\",\"nodes\":[{\"id\":\"run\",\"type\":\"action\",\"action\":{\"kind\":\"agent\",\"name\":\"$REAL_MODEL_AGENT\"}}],\"edges\":[]},\"dependencies\":[{\"resource_id\":\"$REAL_MODEL_AGENT_ID\",\"dependency_mode\":\"live\",\"required\":true,\"purpose\":\"M4 browser real model proof\"}],\"expected_revision\":0}"
  request 200 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources/$REAL_MODEL_WORKFLOW_ID/publish" -H 'Content-Type: application/json' \
    --data '{"expected_draft_revision":1}'
fi

# Create one canonical Workflow Run so the real browser lane can inspect the
# production run-detail API and its immutable knowledge snapshot. The run is
# marked completed after creation; no model call is needed for this UI proof.
WORKFLOW_NAME="e2e-${RUN_ID}-knowledge-workflow"
request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources" -H 'Content-Type: application/json' \
  --data "{\"type\":\"workflow\",\"slug\":\"$WORKFLOW_NAME\",\"display_name\":\"$WORKFLOW_NAME\",\"storage_kind\":\"database\"}"
WORKFLOW_RESOURCE_ID="$(json_value id)"
request 200 -b "$USER_COOKIE" -X PUT "$BASE_URL/api/resources/$WORKFLOW_RESOURCE_ID/workflow-draft" -H 'Content-Type: application/json' \
  --data "{\"content\":{\"schema_version\":2,\"name\":\"$WORKFLOW_NAME\",\"inputs\":{},\"state\":{},\"entrypoint\":\"run\",\"nodes\":[{\"id\":\"run\",\"type\":\"action\",\"action\":{\"kind\":\"agent\",\"name\":\"$APPROVE_AGENT\"}}],\"edges\":[]},\"dependencies\":[],\"expected_revision\":0}"
request 200 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources/$WORKFLOW_RESOURCE_ID/publish" -H 'Content-Type: application/json' \
  --data '{"expected_draft_revision":1}'
request 201 -b "$USER_COOKIE" -X POST "$BASE_URL/api/resources/$WORKFLOW_RESOURCE_ID/workflow-runs" -H 'Content-Type: application/json' \
  --data '{}'
WORKFLOW_RUN_ID="$(json_value run_id)"
python3 - "$DATABASE_PATH" "$WORKFLOW_RUN_ID" <<'PY'
import json
import sqlite3
import sys

database_path, run_id = sys.argv[1:]
snapshot = {
    "run_evidence": {
        "knowledge_scope": {
            "logical_selectors": ["gate-kb"],
            "revisions": {
                "gate-kb": {
                    "revision_id": "real-e2e-revision-2",
                    "revision_no": 2,
                    "manifest_hash": "abcdef1234567890",
                }
            },
        }
    }
}
connection = sqlite3.connect(database_path)
connection.execute(
    "UPDATE workflow_v2_runs SET status = 'completed', snapshot = ? WHERE run_id = ?",
    (json.dumps(snapshot), run_id),
)
connection.execute("UPDATE workflow_tasks SET status = 'completed' WHERE run_id = ?", (run_id,))
connection.commit()
connection.close()
PY

rm -f "$RESPONSE_FILE"
echo "Seed complete: $APPROVE_AGENT and $REJECT_AGENT."
if [[ -n "$REAL_MODEL_WORKFLOW" ]]; then
  echo "Real model workflow seeded: $REAL_MODEL_WORKFLOW"
fi
