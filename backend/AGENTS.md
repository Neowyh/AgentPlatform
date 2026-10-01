For the backend architecture and design patterns:
@./CLAUDE.md

Backend live-test commands use `make test-live` with the `DEER_FLOW_RUN_LIVE_TESTS` opt-in for real external APIs.

### Backend Benchmarks

Benchmarks in `scripts/benchmark/` must be standalone and reproducible. Import
the production function a benchmark measures; never duplicate it or introduce an
alternative runtime implementation.

- Pin every external dataset by immutable revision and SHA-256. Callers provide
  the local dataset path; evaluation commands must not silently download data.
- Never commit upstream dataset text, credentials, complete provider requests,
  or response headers. Read provider credentials and endpoints from named
  environment variables.
- Use fixed clocks and deterministic ordering for offline selection. Results
  must record the config, manifest, prompt, dataset, and git revisions used.
