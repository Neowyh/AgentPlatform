#!/usr/bin/env bash
set -euo pipefail

# The convergence is complete: control-plane code must use the DeerFlow
# runtime. Reject any reintroduction of direct legacy runtime imports.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mapfile -t imports < <(rg -l '^[[:space:]]*(from ideer|import ideer)' "$repo_root/backend/app" -g '*.py' | sort)

printf 'backend/app direct ideer import files: %s\n' "${#imports[@]}"
printf '%s\n' "${imports[@]}"

baseline="${RUNTIME_BOUNDARY_MAX_IMPORT_FILES:-0}"
if (( ${#imports[@]} > baseline )); then
  printf 'ERROR: runtime boundary grew from %s to %s files\n' "$baseline" "${#imports[@]}" >&2
  exit 1
fi
printf 'OK: boundary is not larger than baseline (%s)\n' "$baseline"
