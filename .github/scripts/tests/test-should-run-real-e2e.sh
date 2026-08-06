#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
SELECTOR="$ROOT_DIR/.github/scripts/should-run-real-e2e.sh"

assert_selection() {
  local expected=$1
  shift

  local actual
  actual=$(printf '%s\n' "$@" | bash "$SELECTOR")
  if [[ "$actual" != "$expected" ]]; then
    echo "expected $expected, got $actual for: $*" >&2
    exit 1
  fi
}

assert_selection false "frontend/src/components/common/button.tsx"
assert_selection true "backend/app/gateway/auth/jwt.py"
assert_selection true "backend/app/gateway/routers/admin_skill_applications.py"
assert_selection true "backend/packages/harness/ideer/persistence/models/user.py"
assert_selection true "frontend/src/app/api/memory/route.ts"
assert_selection true "frontend/tests/e2e/real/memory-persistence.spec.ts"
assert_selection true \
  "frontend/src/components/common/button.tsx" \
  "backend/app/gateway/routers/auth.py"

echo "real E2E selector cases passed"
