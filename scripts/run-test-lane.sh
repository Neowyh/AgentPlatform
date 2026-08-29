#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LANE=${1:-}
START_SECONDS=$SECONDS

usage() {
  cat <<'EOF'
Usage: scripts/run-test-lane.sh <lane>

Lanes:
  backend-standard    Parallel backend unit, integration, and contract tests.
  backend-serial      Backend tests marked serial, excluding real LLM tests.
  backend-full        backend-standard followed by backend-serial.
  backend-llm         Backend tests marked requires_llm.
  frontend-standard   Frontend Vitest tests without coverage.
  frontend-core       Frontend Vitest coverage and pnpm check.
  frontend-smoke      Mock browser smoke tests.
  frontend-mock-e2e   Full mock browser tests.
  backend-blocking-io Blocking-I/O regression tests.
  frontend-visual     Visual regression browser tests.
  frontend-a11y       Accessibility browser tests.
  pr-standard         Backend standard, frontend standard, and browser smoke.
  core-full           Backend full, frontend core, and full mock browser tests.
EOF
}

finish() {
  local status=$?
  local elapsed=$((SECONDS - START_SECONDS))
  if [[ $status -eq 0 && -n ${TEST_LANE_MAX_SECONDS:-} && $elapsed -gt $TEST_LANE_MAX_SECONDS ]]; then
    status=124
    echo "TEST_LANE_BUDGET_EXCEEDED lane=${LANE:-unknown} limit=${TEST_LANE_MAX_SECONDS}s actual=${elapsed}s"
  fi
  echo "TEST_LANE_DURATION lane=${LANE:-unknown} seconds=${elapsed} status=${status}"
  if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
    {
      echo "## Test lane: \`${LANE:-unknown}\`"
      echo
      echo "- Test execution: ${elapsed}s"
      echo "- Exit status: ${status}"
    } >>"$GITHUB_STEP_SUMMARY"
  fi
  exit "$status"
}

trap finish EXIT

backend_pytest() {
  local markers=$1
  local coverage=${TEST_LANE_COVERAGE:-0}
  local -a args=(
    -p no:rerunfailures
    tests/unit tests/integration tests/contracts
    -v
    -m "$markers"
  )

  if [[ ${TEST_LANE_SHARDS:-0} -gt 0 ]]; then
    args+=(
      --splits "$TEST_LANE_SHARDS"
      --group "${TEST_LANE_SHARD_INDEX:?TEST_LANE_SHARD_INDEX is required when sharding}"
      --splitting-algorithm least_duration
      -n auto
    )
  elif [[ $markers == "not serial and not requires_llm" ]]; then
    args+=(-n auto)
  fi

  if [[ $coverage == 1 ]]; then
    args+=(--cov=app --cov=packages --cov-report=term-missing)
  fi

  (
    cd "$ROOT_DIR/backend"
    PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest "${args[@]}"
  )
}

case "$LANE" in
  backend-standard)
    backend_pytest "not serial and not requires_llm"
    ;;
  backend-serial)
    backend_pytest "serial and not requires_llm"
    ;;
  backend-full)
    backend_pytest "not serial and not requires_llm"
    backend_pytest "serial and not requires_llm"
    ;;
  backend-llm)
    backend_pytest "requires_llm"
    ;;
  frontend-standard)
    (cd "$ROOT_DIR/frontend" && pnpm vitest run)
    ;;
  frontend-core)
    (cd "$ROOT_DIR/frontend" && pnpm vitest run --coverage && pnpm check)
    ;;
  frontend-smoke)
    (cd "$ROOT_DIR/frontend" && pnpm test:e2e:smoke)
    ;;
  frontend-mock-e2e)
    (cd "$ROOT_DIR/frontend" && pnpm test:e2e)
    ;;
  backend-blocking-io)
    (cd "$ROOT_DIR/backend" && make test-blocking-io)
    ;;
  frontend-visual)
    (cd "$ROOT_DIR/frontend" && pnpm test:e2e:visual)
    ;;
  frontend-a11y)
    (cd "$ROOT_DIR/frontend" && pnpm test:e2e:a11y)
    ;;
  pr-standard)
    "$ROOT_DIR/scripts/run-test-lane.sh" backend-standard
    "$ROOT_DIR/scripts/run-test-lane.sh" frontend-standard
    "$ROOT_DIR/scripts/run-test-lane.sh" frontend-smoke
    ;;
  core-full)
    "$ROOT_DIR/scripts/run-test-lane.sh" backend-full
    "$ROOT_DIR/scripts/run-test-lane.sh" frontend-core
    "$ROOT_DIR/scripts/run-test-lane.sh" frontend-mock-e2e
    ;;
  -h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
