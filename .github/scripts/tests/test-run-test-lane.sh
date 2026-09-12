#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
RUNNER="$ROOT_DIR/scripts/run-test-lane.sh"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
# This harness substitutes the test executors; prerequisite probing is covered
# by the dedicated preflight tests and would reject the intentionally fake tools.
export TEST_LANE_SKIP_PREFLIGHT=1

mkdir -p "$TEMP_DIR/bin"
cat >"$TEMP_DIR/bin/uv" <<'EOF'
#!/usr/bin/env bash
if [[ ${TEST_LANE_TEST_DELAY:-0} == 1 ]]; then
  sleep 1
fi
printf 'uv %s\n' "$*"
if [[ ${TEST_LANE_FAIL_BACKEND:-0} == 1 && "$*" == *"pytest"* ]]; then
  exit 7
fi
EOF
cat >"$TEMP_DIR/bin/pnpm" <<'EOF'
#!/usr/bin/env bash
printf 'pnpm %s\n' "$*"
EOF
chmod +x "$TEMP_DIR/bin/uv" "$TEMP_DIR/bin/pnpm"

assert_contains() {
  local output=$1
  local expected=$2
  if [[ $output != *"$expected"* ]]; then
    echo "expected output to contain: $expected" >&2
    echo "$output" >&2
    exit 1
  fi
}

assert_not_contains() {
  local output=$1
  local unexpected=$2
  if [[ $output == *"$unexpected"* ]]; then
    echo "expected output not to contain: $unexpected" >&2
    echo "$output" >&2
    exit 1
  fi
}

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" backend-standard)
assert_contains "$output" 'uv run pytest -p no:rerunfailures'
assert_contains "$output" 'not serial and not requires_llm'
assert_contains "$output" '-n auto'
assert_contains "$output" 'TEST_LANE_DURATION lane=backend-standard'

if output=$(PATH="$TEMP_DIR/bin:$PATH" TEST_LANE_MAX_SECONDS=0 TEST_LANE_TEST_DELAY=1 bash "$RUNNER" backend-standard); then
  echo "over-budget lane unexpectedly succeeded" >&2
  exit 1
fi
assert_contains "$output" 'TEST_LANE_BUDGET_EXCEEDED lane=backend-standard limit=0s'
assert_contains "$output" 'status=124'

output=$(PATH="$TEMP_DIR/bin:$PATH" TEST_LANE_SHARDS=4 TEST_LANE_SHARD_INDEX=2 bash "$RUNNER" backend-standard)
assert_contains "$output" '--splits 4 --group 2 --splitting-algorithm least_duration -n auto'

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" backend-serial)
assert_contains "$output" 'serial and not requires_llm'
assert_not_contains "$output" '-n auto'

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" backend-llm)
assert_contains "$output" 'requires_llm'
assert_not_contains "$output" '-n auto'

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" frontend-core)
assert_contains "$output" 'pnpm vitest run --coverage'
assert_contains "$output" 'pnpm check'

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" frontend-visual)
assert_contains "$output" 'pnpm test:e2e:visual'

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" frontend-stagehand)
assert_contains "$output" 'status=unexecuted reason=missing_stagehand_credentials'

output=$(PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" pr-standard)
assert_contains "$output" 'TEST_LANE_DURATION lane=pr-standard'
assert_contains "$output" 'pnpm test:e2e:smoke'

if output=$(PATH="$TEMP_DIR/bin:$PATH" TEST_LANE_FAIL_BACKEND=1 bash "$RUNNER" core-full); then
  echo "composite lane unexpectedly succeeded after backend failure" >&2
  exit 1
fi
assert_contains "$output" 'pnpm vitest run --coverage'
assert_contains "$output" 'pnpm exec playwright test tests/e2e/'
assert_contains "$output" 'TEST_LANE_DURATION lane=core-full'
assert_contains "$output" 'status=7'

if PATH="$TEMP_DIR/bin:$PATH" bash "$RUNNER" unknown >/dev/null 2>&1; then
  echo "unknown lane unexpectedly succeeded" >&2
  exit 1
fi

echo "test lane runner cases passed"
