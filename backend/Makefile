install:
	uv sync

dev:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --reload

gateway:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001

DEFAULT_TEST_PATHS := tests/unit tests/integration tests/contracts
DEFAULT_TEST_MARKERS := not serial and not requires_llm

test:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest $(DEFAULT_TEST_PATHS) -v -m "$(DEFAULT_TEST_MARKERS)"

test-unit:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit -v -m "$(DEFAULT_TEST_MARKERS)"

test-integration:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration -v -m "$(DEFAULT_TEST_MARKERS)"

test-contracts:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/contracts -v -m "$(DEFAULT_TEST_MARKERS)"

test-qa:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/qa -v

test-parallel:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
		uv run pytest $(DEFAULT_TEST_PATHS) -v -n auto \
		-m "$(DEFAULT_TEST_MARKERS)"

test-coverage:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest $(DEFAULT_TEST_PATHS) -v -m "$(DEFAULT_TEST_MARKERS)" --cov=app --cov=packages --cov-report=term-missing --cov-report=html:htmlcov

test-blocking-io:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/blocking_io -q --tb=short

lint:
	uvx ruff check .
	uvx ruff format --check .

format:
	uvx ruff check . --fix && uvx ruff format .

detect-blocking-io:
	@PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run python ../scripts/detect_blocking_io_static.py --output ../.ideer/blocking-io-findings.json
