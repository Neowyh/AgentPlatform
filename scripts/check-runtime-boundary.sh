#!/usr/bin/env bash
set -euo pipefail

# Transitional guard for the dual-runtime phase. This does not claim that the
# ideer package is removable yet; it makes the remaining control-plane imports
# explicit and prevents accidental growth while each seam is migrated.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mapfile -t imports < <(rg -l '^[[:space:]]*(from ideer|import ideer)' "$repo_root/backend/app" -g '*.py' | sort)

printf 'backend/app direct ideer import files: %s\n' "${#imports[@]}"
printf '%s\n' "${imports[@]}"

baseline="${RUNTIME_BOUNDARY_MAX_IMPORT_FILES:-26}"
if (( ${#imports[@]} > baseline )); then
  printf 'ERROR: runtime boundary grew from %s to %s files\n' "$baseline" "${#imports[@]}" >&2
  exit 1
fi
printf 'OK: boundary is not larger than baseline (%s)\n' "$baseline"
