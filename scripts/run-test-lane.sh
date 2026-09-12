#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LANE=${1:-}
START_SECONDS=$SECONDS
PYTHON_BIN=${PYTHON:-python3}
PNPM_CMD=("$PYTHON_BIN" "$ROOT_DIR/scripts/pnpm_command.py")

# Resolve the lane before doing any environment work.  This keeps --help and
# malformed invocations useful on machines without the test dependencies.
VALID_LANES=(backend-standard backend-serial backend-full backend-llm backend-external backend-blocking-io frontend-standard frontend-core frontend-smoke frontend-mock-e2e frontend-auth frontend-real frontend-stagehand frontend-visual frontend-a11y pr-standard core-full test-inventory test-contracts)
is_valid_lane() {
  local candidate=$1 lane
  for lane in "${VALID_LANES[@]}"; do [[ $lane == "$candidate" ]] && return 0; done
  return 1
}

usage() {
  cat <<'EOF'
Usage: scripts/run-test-lane.sh <lane>

Lanes:
  backend-standard    Parallel backend unit, integration, and contract tests.
  backend-serial      Backend tests marked serial, excluding real LLM tests.
  backend-full        backend-standard followed by backend-serial.
  backend-llm         Backend tests marked requires_llm.
  backend-external    Backend tests requiring network or external build tools.
  frontend-standard   Frontend Vitest tests without coverage.
  frontend-core       Frontend Vitest coverage and pnpm check.
  frontend-smoke      Mock browser smoke tests.
  frontend-mock-e2e   Full mock browser tests.
  frontend-auth       Auth-enabled browser tests.
  frontend-real       Real-backend browser tests.
  frontend-stagehand  AI-powered Stagehand browser tests (requires explicit credentials).
  backend-blocking-io Blocking-I/O regression tests.
  frontend-visual     Visual regression browser tests.
  frontend-a11y       Accessibility browser tests.
  pr-standard         Backend standard, frontend standard, and browser smoke.
  core-full           Backend full, frontend core, and full mock browser tests.
  test-inventory      Print discovered tests and lane ownership.
  test-contracts      Validate lane ownership and entry contracts.
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
  if [[ -n ${ARTIFACT_DIR:-} ]]; then
    printf 'finished=%s\nstatus=%s\nseconds=%s\n' "$(date -u +%FT%TZ)" "$status" "$elapsed" >>"$ARTIFACT_DIR/run.meta" || true
  fi
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

run_composite() {
  local overall=0 child rc
  for child in "$@"; do
    set +e
    "$ROOT_DIR/scripts/run-test-lane.sh" "$child"
    rc=$?
    set -e
    if [[ $rc -ne 0 && $overall -eq 0 ]]; then
      overall=$rc
    fi
  done
  return "$overall"
}

trap finish EXIT
# Preserve interruption/timeout status instead of allowing the EXIT trap to
# observe the successful status of the last completed shell command.
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$LANE" == "-h" || "$LANE" == "--help" ]]; then
  usage
  exit 0
fi
if [[ -z "$LANE" ]] || ! is_valid_lane "$LANE"; then
  usage >&2
  exit 2
fi

ARTIFACT_DIR=${TEST_LANE_ARTIFACT_DIR:-$ROOT_DIR/logs/test-lanes}/"${LANE}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
if ! mkdir -p "$ARTIFACT_DIR"; then
  echo "unable to create test lane artifact directory: $ARTIFACT_DIR" >&2
  exit 1
fi
printf 'lane=%s\ncommand=%q\nstarted=%s\n' "$LANE" "$0 $*" "$(date -u +%FT%TZ)" >"$ARTIFACT_DIR/run.meta"

if [[ ${TEST_LANE_SKIP_PREFLIGHT:-0} != 1 && "$LANE" != "test-inventory" && "$LANE" != "test-contracts" ]]; then
  "$PYTHON_BIN" "$ROOT_DIR/scripts/test_preflight.py" "$LANE"
fi

backend_pytest() {
  local markers=$1
  local coverage=${TEST_LANE_COVERAGE:-0}
  local -a args=(
    -p no:rerunfailures
    tests/
    --ignore=tests/blocking_io
    -v
    -m "$markers"
  )

  if [[ ${TEST_LANE_SHARDS:-0} -gt 0 ]]; then
    args+=(
      --splits "$TEST_LANE_SHARDS"
      --group "${TEST_LANE_SHARD_INDEX:?TEST_LANE_SHARD_INDEX is required when sharding}"
      --splitting-algorithm least_duration
      -n auto
      --dist loadfile
    )
  elif [[ $markers == not\ serial* ]]; then
    args+=(-n auto --dist loadfile)
  fi

  if [[ $coverage == 1 ]]; then
    args+=(--cov=app --cov=packages --cov-report=term-missing)
  fi

  (
    cd "$ROOT_DIR/backend"
    # A number of compatibility tests intentionally use the shared helpers as
    # top-level modules (for example ``_router_auth_helpers``).  Keep the
    # lane's collection roots on PYTHONPATH so those modules resolve exactly
    # as they do under the backend Make targets.
    PYTHONPATH=.:tests PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest "${args[@]}"
  )
}

case "$LANE" in
  backend-standard)
    backend_pytest "not serial and not requires_llm and not live and not external"
    ;;
  backend-serial)
    backend_pytest "serial and not requires_llm and not live"
    ;;
  backend-full)
    backend_pytest "not serial and not requires_llm and not live and not external"
    backend_pytest "serial and not requires_llm and not live"
    ;;
  backend-llm)
    backend_pytest "requires_llm"
    ;;
  backend-external)
    backend_pytest "external"
    ;;
  frontend-standard)
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" rstest run && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" vitest run)
    ;;
  frontend-core)
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" rstest run && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" vitest run --coverage && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" check)
    ;;
  frontend-smoke)
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" test:e2e:smoke)
    ;;
  frontend-auth)
    (cd "$ROOT_DIR/frontend" && PLAYWRIGHT_AUTH_ENABLED=1 XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" playwright test tests/e2e/auth tests/e2e-auth)
    ;;
  frontend-real)
    (cd "$ROOT_DIR/frontend" && PLAYWRIGHT_SKIP_WEB_SERVER=1 XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" playwright test tests/e2e/real tests/e2e-real-backend)
    ;;
  frontend-stagehand)
    if [[ -z ${OPENAI_API_KEY:-} && -z ${OPENAI_BASE_URL:-} ]]; then
      echo "TEST_LANE_STATUS lane=frontend-stagehand status=unexecuted reason=missing_stagehand_credentials"
      exit 0
    fi
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" test:e2e:stagehand)
    ;;
  frontend-mock-e2e)
    # Mock E2E owns root functional specs plus the shared smoke/workflow
    # suites. Auth, real-backend, visual, a11y, and Stagehand directories have
    # dedicated lanes and must not silently run here.
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" exec playwright test tests/e2e/*.spec.ts tests/e2e/smoke tests/e2e/workflows)
    ;;
  backend-blocking-io)
    (cd "$ROOT_DIR/backend" && make test-blocking-io)
    ;;
  frontend-visual)
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" test:e2e:visual)
    ;;
  frontend-a11y)
    (cd "$ROOT_DIR/frontend" && XDG_DATA_HOME="${TEST_PNPM_XDG:-/tmp/deer-flow-xdg}" PNPM_HOME="${TEST_PNPM_HOME:-/tmp/deer-flow-pnpm-home}" "${PNPM_CMD[@]}" test:e2e:a11y)
    ;;
  test-inventory)
    "$PYTHON_BIN" "$ROOT_DIR/scripts/test_inventory.py"
    ;;
  test-contracts)
    PYTHONPATH="$ROOT_DIR/scripts" "$PYTHON_BIN" "$ROOT_DIR/scripts/check_test_contracts.py"
    ;;
  pr-standard)
    bash "$ROOT_DIR/scripts/check-runtime-boundary.sh"
    run_composite backend-standard frontend-standard frontend-smoke
    ;;
  core-full)
    bash "$ROOT_DIR/scripts/check-runtime-boundary.sh"
    run_composite backend-full frontend-core frontend-mock-e2e
    ;;
  -h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
