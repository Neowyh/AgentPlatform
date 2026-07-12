#!/usr/bin/env bash
# Stop and remove exactly the isolated run named by a manifest or state dir.
set -euo pipefail

if [[ "${QA_ISOLATED:-}" != "1" ]]; then
  echo "QA_ISOLATED=1 is required for real E2E cleanup." >&2
  exit 2
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/manifest.json|/absolute/path/to/state-dir" >&2
  exit 2
fi

TARGET="$1"
if [[ -d "$TARGET" ]]; then
  MANIFEST_PATH="$TARGET/manifest.json"
else
  MANIFEST_PATH="$TARGET"
fi
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
state_dir = pathlib.Path(data["state_dir"]).resolve()
if path.parent != state_dir:
    raise SystemExit("manifest state_dir does not match its parent directory")
if state_dir.parent != pathlib.Path("/tmp") and state_dir.parent != pathlib.Path("/var/tmp"):
    raise SystemExit("refusing to clean a state directory outside /tmp or /var/tmp")
print(state_dir)
print(data["pid"])
PY
)
STATE_DIR="${manifest_values[0]}"
PID="${manifest_values[1]}"

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID"
  fi
fi

rm -rf "$STATE_DIR"
echo "Stopped and cleaned $STATE_DIR"
