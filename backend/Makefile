install:
	uv sync

dev:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --reload

gateway:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001

test:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/ -v

test-parallel:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
		uv run pytest tests/ -v -n auto \
		--ignore=tests/qa \
		--ignore=tests/blocking_io \
		-m "not serial and not requires_llm"

test-coverage:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/ -v --cov=app --cov=packages --cov-report=term-missing --cov-report=html:htmlcov

test-blocking-io:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/blocking_io -q --tb=short

lint:
	uvx ruff check .
	uvx ruff format --check .

format:
	uvx ruff check . --fix && uvx ruff format .

detect-blocking-io:
	@PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run python ../scripts/detect_blocking_io_static.py --output ../.ideer/blocking-io-findings.json
