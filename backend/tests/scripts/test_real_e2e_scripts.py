"""Static contract tests for the real-E2E backend runner scripts.

These tests keep the shell entrypoints intentionally small while protecting the
isolation guarantees that prevent a browser test from touching a developer DB.
"""

from pathlib import Path

SCRIPTS = Path(__file__).parents[2] / "scripts"
REAL_PLAYWRIGHT_CONFIG = Path(__file__).parents[3] / "frontend" / "playwright.real.config.ts"


def _script(name: str) -> str:
    return (SCRIPTS / name).read_text()


def test_start_requires_isolation_and_writes_a_manifest() -> None:
    script = _script("start-real-e2e.sh")

    assert "QA_ISOLATED" in script
    assert "manifest.json" in script
    assert '"pid"' in script
    assert '"database_path"' in script
    assert '"ideer_home"' in script
    assert '"config_path"' in script
    assert '"log_path"' in script
    assert '"run_id"' in script
    assert 'FRONTEND_PORT="${E2E_FRONTEND_PORT:-3101}"' in script
    assert 'GATEWAY_CORS_ORIGINS="http://127.0.0.1:$FRONTEND_PORT,http://localhost:$FRONTEND_PORT"' in script


def test_stop_requires_an_explicit_manifest_and_never_discovers_tmp_runs() -> None:
    script = _script("stop-real-e2e.sh")

    assert "Usage:" in script
    assert "manifest.json" in script
    assert "ls -d /tmp/ideer-real-e2e-" not in script


def test_seed_uses_the_manifest_and_does_not_downgrade_setup_failures() -> None:
    script = _script("seed-real-e2e.sh")

    assert "manifest.json" in script
    assert "QA_ISOLATED" in script
    assert "non-fatal" not in script
    assert "|| true" not in script
    assert "X-CSRF-Token" in script
    assert "csrf_token" in script


def test_seed_does_not_create_unused_cross_department_fixtures() -> None:
    script = _script("seed-real-e2e.sh")

    assert "Real E2E Cross Department" not in script
    assert "cross-department-user@test.com" not in script
    assert "e2e-${RUN_ID}-cross-department-agent" not in script
    assert "e2e-${RUN_ID}-cross-department-pending" not in script


def test_runner_passes_manifest_and_isolated_backend_url_to_playwright() -> None:
    script = _script("run-real-e2e.sh")

    assert "QA_ISOLATED" in script
    assert "start-real-e2e.sh" in script
    assert "seed-real-e2e.sh" in script
    assert "stop-real-e2e.sh" in script
    assert "IDEER_INTERNAL_GATEWAY_BASE_URL" in script
    assert "REAL_E2E_MANIFEST" in script
    assert "E2E_STATE_DIR" in script
    assert "E2E_RUN_ID" in script
    assert "REAL_E2E_ARTIFACTS_DIR" in script
    assert 'RUN_ARTIFACTS_DIR="$ARTIFACTS_DIR/$RUN_ID"' in script
    assert 'REAL_E2E_ARTIFACTS_DIR="$RUN_ARTIFACTS_DIR"' in script
    assert 'rm -rf "$REPO_DIR/frontend/.next-e2e-$RUN_ID"' in script
    assert "setsid pnpm exec playwright test --config=playwright.real.config.ts" in script
    assert 'kill -- -"$PLAYWRIGHT_PID"' in script
    assert "backend-logs" in script


def test_real_playwright_uses_an_isolated_production_build() -> None:
    config = REAL_PLAYWRIGHT_CONFIG.read_text()

    assert "pnpm exec next build --webpack && pnpm start -p ${frontendPort}" in config
    assert "next dev" not in config
    assert "IDEER_NEXT_DIST_DIR: `.next-e2e-${runId}`" in config
    assert "timeout: 420_000" in config
