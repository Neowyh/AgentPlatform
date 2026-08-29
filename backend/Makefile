install:
	uv sync

dev:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --reload

gateway:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001

workflow-worker:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run python -m app.workflow_worker

DEFAULT_TEST_PATHS := tests/unit tests/integration tests/contracts
DEFAULT_TEST_MARKERS := not serial and not requires_llm
DEFAULT_TEST_OPTS := -p no:rerunfailures

test:
	bash ../scripts/run-test-lane.sh backend-standard

test-full:
	bash ../scripts/run-test-lane.sh backend-full

test-llm:
	bash ../scripts/run-test-lane.sh backend-llm

test-unit:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest $(DEFAULT_TEST_OPTS) tests/unit -v -m "$(DEFAULT_TEST_MARKERS)"

test-integration:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest $(DEFAULT_TEST_OPTS) tests/integration -v -m "$(DEFAULT_TEST_MARKERS)"

test-contracts:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest $(DEFAULT_TEST_OPTS) tests/contracts -v -m "$(DEFAULT_TEST_MARKERS)"

test-parallel:
	bash ../scripts/run-test-lane.sh backend-standard

test-coverage:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest $(DEFAULT_TEST_OPTS) $(DEFAULT_TEST_PATHS) -v -m "$(DEFAULT_TEST_MARKERS)" --cov=app --cov=packages --cov-report=term-missing --cov-report=html:htmlcov

test-blocking-io:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/blocking_io -q --tb=short

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check . --fix && uv run ruff format .

detect-blocking-io:
	@PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run python ../scripts/detect_blocking_io_static.py --output ../.ideer/blocking-io-findings.json
