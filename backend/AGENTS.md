# Backend guidance

The backend has two layers with a one-way dependency: `backend/app/` contains the Gateway and channel integrations; `backend/packages/harness/deerflow/` contains the reusable agent framework. App code may import the harness. Harness code must remain independent of `app.*`; `backend/tests/test_harness_boundary.py` enforces this boundary.

For current backend architecture, configuration, Gateway contracts, and runtime behavior, start at [backend/docs/README.md](docs/README.md). Read the nearest `AGENTS.md` before changing a governed subsystem. `packages/harness/deerflow/AGENTS.md` and its nested files describe the harness; `app/gateway/AGENTS.md` and `app/channels/AGENTS.md` describe application code.

Use the repository test policy in the root `AGENTS.md`. Backend live tests use `make test-live` and require the explicit `DEER_FLOW_RUN_LIVE_TESTS` opt-in because they call external APIs. The focused test comes first; run the applicable backend lane at implementation completion and `pr-standard` for the high-risk or cross-stack changes listed in the root guidance.

Before changing configuration, runtime, tools, channels, memory, uploads, or retrieval evidence, read the [backend development reference](docs/development-reference.md). It preserves the detailed runtime and architecture contracts migrated from the former backend guidance.

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
