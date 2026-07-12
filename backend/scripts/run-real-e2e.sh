#!/usr/bin/env bash
# Run the complete isolated real-browser E2E lane and always clean its run.
set -euo pipefail

if [[ "${QA_ISOLATED:-}" != "1" ]]; then
  echo "QA_ISOLATED=1 is required for the real E2E lane." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST_PATH=""
ARTIFACTS_DIR="${REAL_E2E_ARTIFACTS_DIR:-}"

copy_artifacts() {
  [[ -n "$ARTIFACTS_DIR" && -n "$MANIFEST_PATH" && -d "${STATE_DIR:-}" ]] || return 0
  mkdir -p "$ARTIFACTS_DIR"
  mkdir -p "$ARTIFACTS_DIR/backend-logs"
  cp -R "$STATE_DIR/logs/." "$ARTIFACTS_DIR/backend-logs/"
}

cleanup() {
  local status=$?
  copy_artifacts || echo "Failed to copy real E2E artifacts to $ARTIFACTS_DIR" >&2
  if [[ -n "$MANIFEST_PATH" && -f "$MANIFEST_PATH" ]]; then
    QA_ISOLATED=1 "$SCRIPT_DIR/stop-real-e2e.sh" "$MANIFEST_PATH" >&2 || :
  fi
  exit "$status"
}
trap cleanup EXIT

MANIFEST_PATH="$(QA_ISOLATED=1 PORT="${PORT:-8001}" "$SCRIPT_DIR/start-real-e2e.sh")"
QA_ISOLATED=1 "$SCRIPT_DIR/seed-real-e2e.sh" "$MANIFEST_PATH"

mapfile -t manifest_values < <(python3 - "$MANIFEST_PATH" <<'PY'
import json
import pathlib
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
print(data["state_dir"])
print(data["base_url"])
print(str(pathlib.Path(data["log_path"]).parent))
print(data["run_id"])
PY
)
STATE_DIR="${manifest_values[0]}"
BACKEND_URL="${manifest_values[1]}"
LOGS_DIR="${manifest_values[2]}"
RUN_ID="${manifest_values[3]}"

cd "$REPO_DIR/frontend"
IDEER_INTERNAL_GATEWAY_BASE_URL="$BACKEND_URL" \
REAL_E2E_MANIFEST="$MANIFEST_PATH" \
E2E_STATE_DIR="$STATE_DIR" \
E2E_RUN_ID="$RUN_ID" \
REAL_E2E_ARTIFACTS_DIR="$ARTIFACTS_DIR" \
pnpm exec playwright test --config=playwright.real.config.ts 2>&1 | tee "$LOGS_DIR/playwright.log"
