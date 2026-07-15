#!/usr/bin/env bash
set -euo pipefail

RISK_PATTERN='^(backend/app/gateway/(auth/|auth\.py$|auth_middleware\.py$|authz\.py$|rbac_users\.py$|routers/(auth|admin[^/]*|visibility_applications|memory|agents|skills|workflows)\.py$)|backend/packages/harness/ideer/persistence/|backend/scripts/.*real-e2e.*\.sh$|frontend/src/(app/\(auth\)/|app/api/memory/|app/workspace/admin/|core/(auth|admin|memory|visibility-applications)/)|frontend/(playwright\.real\.config\.ts$|tests/e2e/real/)|\.github/(scripts/should-run-real-e2e\.sh$|workflows/real-e2e-tests\.yml$))'

if grep -Eq "$RISK_PATTERN"; then
  echo true
else
  echo false
fi
