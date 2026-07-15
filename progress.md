# Progress: ✅ Phase 5 务实分层验收与交付（已完成）

## 2026-07-14（最终验收）

### 审查结果

| 审查项 | 结果 |
|--------|------|
| 根测试 (`backend/tests/test_*.py`) | 0 残留 ✅ |
| 坏命名 (`coverage`/`boost`/`gaps`/`full`/`extra`/`cov*`/`fix`) | 0 残留 ✅ |
| Playwright 重复收集 | 0 重复（chromium 仅收集 `smoke/` + `workflows/`）✅ |
| `git diff --check` | 无冲突标记残留 ✅ |
| GitNexus `detect_changes` | 0 受影响 execution flow ✅ |

### 分层 lane 验证

| Lane | Configuration | Collection | 验证结果 |
|------|---------------|-----------|---------|
| PR: 后端 hermetic unit/integration/contracts | `backend-unit-tests.yml` | 4 shards, `-m "not serial and not requires_llm"` | ✅ `make lint` ruff pass |
| PR: 前端 unit/typecheck/lint | `lint-check.yml`, `frontend-unit-tests.yml` | ESLint + `tsc --noEmit` + dep-cruiser + build | ✅ `pnpm typecheck` 0 errors |
| PR: mock Chromium | `playwright.config.ts` chromium project | `smoke/` + `workflows/` | ✅ `--list` 无重复收集 |
| **合并**: isolated real E2E | `real-e2e-tests.yml` / `run-real-e2e.sh` | `real/` (5 tests, 3 files) | ✅ `--list` 可复现 |
| Nightly: visual | `playwright.config.ts` visual + `login-visual.config.ts` | 10 baselines | ✅ 9 + 1 = 10 tests listed |
| Nightly: a11y | `playwright.a11y.config.ts` | 3 public pages | ✅ 3 tests (Landing/Login/Setup) |

### 制品清理

- 旧格式 `*-chromium-linux.png` 基线 → 已删除，仅保留 `*-visual-linux.png` ✅
- `backend/test-results/`, `test-results/`, `task_plan.md`, `session-ses_*`, `config.yaml.bak-*` 等 → 已清理 ✅
- `frontend/playwright-artifacts/` → 保留为空目录（visual-screenshot 输出目标）✅

### 收口标准达成

1. ✅ 每项核心能力有且仅有一个主责任测试（coverage-matrix.md 记录）
2. ✅ PR/合并/nightly lane 均有可复现的 `--list` 退出码
3. ✅ coverage-matrix.md 标明主测试层级与真实闭环位置
4. ✅ test-migration-ledger.md 对所有删除提供保留测试和验证命令
5. ✅ 10 张新视觉基线已审查；无效 login→workspace 基线已清理
6. ✅ 测试失败可归因到产品契约/前端行为/环境隔离/基础设施之一

## 2026-07-15 文档治理续作

- 文档治理进度记录见 `task_plan.md` 和 `docs/archive/2026/README.md`。
- 本轮验证：192 个文档、174 个可验证相对链接、0 个断链；current canonical 无重复；归档 canonical 均存在。
- 已迁移测试/验证历史材料至 `docs/archive/2026/testing/`，离线和权限历史材料至对应归档目录。
- 已迁移 `docs/optimization/` 至 `docs/archive/2026/optimization/`，建立归档索引并新增 `docs/backlog.md`。
- 已迁移后端历史计划至 `backend/docs/archive/2026/`，保留 `engineering-backlog.md`、`AUTO_TITLE_GENERATION.md` 和 `MEMORY_SETTINGS_REVIEW.md` 为当前入口。
- 最终公开文档 smoke：Playwright Chromium 3/3 通过，覆盖 `/zh/docs`、`/zh/docs/application/quick-start`、`/en/docs/application/deployment-guide` 和未知路径 404。
