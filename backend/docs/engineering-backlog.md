# Engineering Backlog

> 从 `TODO.md` 迁移（2026-07-14）。原有的已完成项已清除，此处仅保留尚待实施的工程改进。

## Backend Infrastructure

- [ ] Pooling the sandbox resources to reduce the number of sandbox containers
- [ ] Support for more document formats in upload
- [ ] Skill marketplace / remote skill installation

## Async & Performance

- [ ] Optimize async concurrency in agent hot path (IM channels multi-task scenario)
- [ ] Replace `subprocess.run()` with `asyncio.create_subprocess_shell()` in `packages/harness/ideer/sandbox/local/local_sandbox.py`
  - Replace sync `requests` with `httpx.AsyncClient` in community tools (tavily, jina_ai, firecrawl, infoquest, image_search)
  - Consider `asyncio.to_thread()` wrapper for remaining blocking file I/O
  - For production: use `langgraph up` (multi-worker) instead of `langgraph dev` (single-worker)
