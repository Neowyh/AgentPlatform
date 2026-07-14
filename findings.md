# Findings: 新 Phase 5 务实分层验收

## Confirmed design

- PR 只运行 hermetic backend `unit/integration/contracts`、frontend typecheck/lint 与 mock Chromium。
- isolated real E2E 是唯一真实浏览器认证、RBAC、持久化和可见性写操作证据。它要求临时 SQLite、专属后端、专属前端、seed 和 teardown。
- visual、a11y 和参考截图只在 nightly/manual 运行；它们分别使用专用 Next 服务，不复用未知的 3000 或 8001 服务。
- standalone auth 是本地诊断，不能替代 real E2E；mock、visual、a11y 也不能证明真实认证。
- Coverage 是诊断数据。删除测试的安全性来自 matrix/ledger 的唯一主责任与可复现 keeper 命令，而不是全局 statements 百分比。

## Existing implementation to verify

- `backend/tests/qa/` 及其两个 shared-8001 workflow 已删除；`test-migration-ledger.md` 需要把原 API、RBAC、SSE 行为逐项映射到明确 keeper。
- 默认 Playwright 配置只收集 mock `smoke/` 与 `workflows/`；real、a11y、login visual、reference capture 使用独立配置或端口。
- 十张视觉基线的目标构成为：landing 3、workspace 3、core workspace 3、login 1。
- 旧 coverage/QA/98% 结论仍分散在历史治理文档中，必须在交付前移除或改为明确的非阻断历史诊断。

## Verification record

| Command | Result | Exit code | Notes |
| --- | --- | --- | --- |
| Pending | Pending | Pending | This file records only commands executed in the current Phase 5 run. |
