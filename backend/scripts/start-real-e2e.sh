#!/usr/bin/env bash
# Start one isolated backend for the real browser E2E lane.
set -euo pipefail

if [[ "${QA_ISOLATED:-}" != "1" ]]; then
  echo "QA_ISOLATED=1 is required for real E2E runs." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PORT="${PORT:-8001}"
RUN_ID="${E2E_RUN_ID:-real-e2e-$(date +%s)-$RANDOM}"

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "PORT must be an integer between 1 and 65535, got '$PORT'." >&2
  exit 2
fi
if ! [[ "$RUN_ID" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "E2E_RUN_ID may contain only letters, digits, and hyphens, got '$RUN_ID'." >&2
  exit 2
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use; refusing to attach an E2E run to it." >&2
  exit 1
fi

STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ideer-real-e2e-${RUN_ID}-XXXXXX")"
LOGS_DIR="$STATE_DIR/logs"
SQLITE_DIR="$STATE_DIR/sqlite"
CONFIG_PATH="$STATE_DIR/config.yaml"
MANIFEST_PATH="$STATE_DIR/manifest.json"
DATABASE_PATH="$SQLITE_DIR/ideer.db"
mkdir -p "$LOGS_DIR" "$SQLITE_DIR"

cleanup_failed_start() {
  local status=$?
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || :
    wait "$PID" 2>/dev/null || :
  fi
  rm -rf "$STATE_DIR"
  exit "$status"
}
trap cleanup_failed_start ERR

cat > "$CONFIG_PATH" <<YAML
log_level: info
models:
  - name: real-e2e-model
    display_name: Real E2E Model
    use: langchain_openai:ChatOpenAI
    model: gpt-4o-mini
    api_key: \$OPENAI_API_KEY
    base_url: \$OPENAI_API_BASE
sandbox:
  use: ideer.sandbox.local:LocalSandboxProvider
agents_api:
  enabled: true
database:
  backend: sqlite
  sqlite_dir: $SQLITE_DIR
YAML

(
  cd "$BACKEND_DIR"
  export IDEER_HOME="$STATE_DIR"
  export IDEER_CONFIG_PATH="$CONFIG_PATH"
  export AUTH_JWT_SECRET="real-e2e-only-secret"
  export OPENAI_API_KEY="real-e2e-placeholder-key"
  export OPENAI_API_BASE="https://example.invalid"
  export QA_ISOLATED=1
  exec uv run uvicorn app.gateway.app:app --host 127.0.0.1 --port "$PORT"
) >"$LOGS_DIR/backend.log" 2>&1 &
PID=$!

python3 - "$MANIFEST_PATH" "$STATE_DIR" "$PID" "$PORT" "$CONFIG_PATH" "$SQLITE_DIR" "$DATABASE_PATH" "$LOGS_DIR/backend.log" "$RUN_ID" <<'PY'
import json
import sys

manifest_path, state_dir, pid, port, config_path, sqlite_dir, database_path, log_path, run_id = sys.argv[1:]
with open(manifest_path, "w", encoding="utf-8") as output:
    json.dump(
        {
            "state_dir": state_dir,
            "pid": int(pid),
            "port": int(port),
            "base_url": f"http://127.0.0.1:{port}",
            "config_path": config_path,
            "sqlite_dir": sqlite_dir,
            "database_path": database_path,
            "ideer_home": state_dir,
            "log_path": log_path,
            "run_id": run_id,
        },
        output,
        sort_keys=True,
    )
    output.write("\n")
PY

for _ in $(seq 1 30); do
  if curl --silent --show-error --fail "http://127.0.0.1:$PORT/api/v1/auth/setup-status" >/dev/null 2>&1; then
    trap - ERR
    printf '%s\n' "$MANIFEST_PATH"
    exit 0
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "Backend exited before becoming ready; see $LOGS_DIR/backend.log" >&2
    exit 1
  fi
  sleep 1
done

echo "Backend did not become ready; see $LOGS_DIR/backend.log" >&2
exit 1
