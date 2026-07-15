# Test Gate Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不削弱认证、RBAC、用户隔离和持久化保障的前提下，减少普通 PR 的重复测试和浏览器测试等待时间。

**Architecture:** 保留现有测试目录与职责，只调整 CI 触发方式。PR 默认运行基础测试和浏览器 smoke；完整 mock E2E 在 main/nightly 运行；real E2E 由可测试的风险路径脚本自动决定，并由固定汇总门禁兜底。

**Tech Stack:** GitHub Actions、Bash、Vitest、Playwright、pytest

---

## 范围和收口目标

本轮只做三项改动：删除前端覆盖率重复运行、将 PR 浏览器门禁缩为 smoke、让 real E2E 只在高风险 PR 自动运行。暂不移动测试文件、不引入智能测试选择器、不继续清理断言。

完成后必须满足：

- 前端覆盖率测试在一次 CI 中只运行一次。
- 普通前端 PR 只跑 mock smoke；main、nightly、手动运行完整 mock E2E。
- 认证、RBAC、管理权限、Memory、Visibility、持久化和 real-E2E 基础设施改动自动运行 real E2E。
- real E2E 未被选中时有明确的成功门禁，而不是依赖人工判断。
- 现有后端默认测试和关键 contract 范围不变。

### Task 1: 删除前端覆盖率重复执行

**Files:**
- Modify: `.github/workflows/frontend-unit-tests.yml:41-71`

- [ ] **Step 1: 修改覆盖率摘要步骤**

保留 `make test-coverage` 和现有 `coverage/coverage-final.json` 解析。删除第二次执行 Vitest 的 `Coverage Summary` 步骤，并在 `Publish frontend coverage summary` 末尾直接写入摘要：

```yaml
          echo "Frontend statement coverage: ${STATEMENTS}%"
          echo "Frontend coverage is diagnostic only."
          {
            echo "## Frontend Coverage Report"
            echo "Frontend statement coverage: ${STATEMENTS}%"
            echo "Coverage is diagnostic only."
          } >> "$GITHUB_STEP_SUMMARY"
```

- [ ] **Step 2: 验证 workflow 格式和重复命令已消失**

Run:

```bash
cd frontend
pnpm exec prettier --check ../.github/workflows/frontend-unit-tests.yml
cd ..
if rg -n 'pnpm vitest run --coverage' .github/workflows/frontend-unit-tests.yml; then exit 1; fi
```

Expected: Prettier 通过，workflow 中不存在第二次 `vitest run --coverage`。

- [ ] **Step 3: 提交独立改动**

```bash
git add .github/workflows/frontend-unit-tests.yml
git commit -m "ci(frontend): avoid duplicate coverage run"
```

### Task 2: PR 只跑 mock smoke，完整 mock E2E 转到 main/nightly

**Files:**
- Modify: `.github/workflows/e2e-tests.yml:54-58`
- Modify: `docs/testing/coverage-matrix.md:32-34`

- [ ] **Step 1: 按事件选择 mock E2E 范围**

将 `Run E2E tests` 替换为两个互斥步骤：

```yaml
      - name: Run PR browser smoke
        if: ${{ github.event_name == 'pull_request' }}
        working-directory: frontend
        run: pnpm test:e2e:smoke
        env:
          SKIP_ENV_VALIDATION: '1'

      - name: Run full mock E2E
        if: ${{ github.event_name != 'pull_request' }}
        working-directory: frontend
        run: pnpm test:e2e
        env:
          SKIP_ENV_VALIDATION: '1'
```

保留当前 `frontend/**` 路径触发、Chromium 安装、报告上传、visual 和 a11y nightly 作业。

- [ ] **Step 2: 更新覆盖矩阵中的门禁说明**

将“Mock Chromium is the PR browser gate”改为以下明确规则：

```markdown
- PR mock Chromium collects `e2e/smoke/**/*.spec.ts`; full mock
  `smoke/` + `workflows/` runs on `main`, nightly, and manual dispatch.
- Isolated real E2E remains the browser-to-persistence proof and is selected
  for high-risk PR paths; visual and public-page a11y run nightly.
```

- [ ] **Step 3: 验证两种收集边界**

Run:

```bash
cd frontend
pnpm exec playwright test --project=chromium tests/e2e/smoke --list
pnpm exec playwright test --project=chromium --list
pnpm exec prettier --check ../.github/workflows/e2e-tests.yml
```

Expected: 第一个命令只列出 `smoke/`；第二个列出 `smoke/` 和 `workflows/`；workflow 格式通过。

- [ ] **Step 4: 提交独立改动**

```bash
git add .github/workflows/e2e-tests.yml docs/testing/coverage-matrix.md
git commit -m "ci(e2e): use smoke tests as pull request gate"
```

### Task 3: real E2E 按高风险路径自动选择

**Files:**
- Create: `.github/scripts/should-run-real-e2e.sh`
- Create: `.github/scripts/tests/test-should-run-real-e2e.sh`
- Modify: `.github/workflows/real-e2e-tests.yml`
- Modify: `docs/testing/coverage-matrix.md:37-39`

- [ ] **Step 1: 创建可本地验证的风险选择脚本**

创建 `.github/scripts/should-run-real-e2e.sh`，从标准输入读取改动文件列表，只输出 `true` 或 `false`：

```bash
#!/usr/bin/env bash
set -euo pipefail

RISK_PATTERN='^(backend/app/gateway/(auth/|auth\.py$|auth_middleware\.py$|authz\.py$|rbac_users\.py$|routers/(auth|admin[^/]*|visibility_applications|memory|agents|skills|workflows)\.py$)|backend/packages/harness/ideer/persistence/|backend/scripts/.*real-e2e.*\.sh$|frontend/src/(app/\(auth\)/|app/api/memory/|app/workspace/admin/|core/(auth|admin|memory|visibility-applications)/)|frontend/(playwright\.real\.config\.ts$|tests/e2e/real/)|\.github/(scripts/should-run-real-e2e\.sh$|workflows/real-e2e-tests\.yml$))'

if grep -Eq "$RISK_PATTERN"; then
  echo true
else
  echo false
fi
```

- [ ] **Step 2: 先验证选择规则**

Run:

```bash
printf '%s\n' 'frontend/src/components/common/button.tsx' | bash .github/scripts/should-run-real-e2e.sh
printf '%s\n' 'backend/app/gateway/auth/jwt.py' | bash .github/scripts/should-run-real-e2e.sh
printf '%s\n' 'backend/packages/harness/ideer/persistence/models/user.py' | bash .github/scripts/should-run-real-e2e.sh
```

Expected: 依次输出 `false`、`true`、`true`。

- [ ] **Step 3: 在 real-E2E workflow 中增加选择和汇总门禁**

移除 `pull_request.paths`，使风险判断在每个非 draft PR 上执行；保留 `push main` 的现有全量触发。增加 `select_real_e2e` job：

```yaml
  select_real_e2e:
    if: ${{ github.event_name != 'pull_request' || github.event.pull_request.draft == false }}
    runs-on: ubuntu-latest
    outputs:
      run_real: ${{ steps.select.outputs.run_real }}
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - id: select
        env:
          EVENT_NAME: ${{ github.event_name }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          if [[ "$EVENT_NAME" != "pull_request" ]]; then
            echo "run_real=true" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          git diff --name-only "$BASE_SHA" "$HEAD_SHA" > /tmp/changed-files.txt
          RUN_REAL=$(bash .github/scripts/should-run-real-e2e.sh < /tmp/changed-files.txt)
          echo "run_real=$RUN_REAL" >> "$GITHUB_OUTPUT"
```

让现有 `real_e2e_tests` job 增加依赖和条件：

```yaml
    needs: select_real_e2e
    if: ${{ needs.select_real_e2e.outputs.run_real == 'true' }}
```

最后增加固定汇总 job：

```yaml
  real_e2e_gate:
    name: Real E2E Gate
    if: ${{ always() && (github.event_name != 'pull_request' || github.event.pull_request.draft == false) }}
    runs-on: ubuntu-latest
    needs: [select_real_e2e, real_e2e_tests]
    steps:
      - env:
          SELECT_RESULT: ${{ needs.select_real_e2e.result }}
          RUN_REAL: ${{ needs.select_real_e2e.outputs.run_real }}
          REAL_RESULT: ${{ needs.real_e2e_tests.result }}
        run: |
          test "$SELECT_RESULT" = "success"
          if [[ "$RUN_REAL" = "true" ]]; then
            test "$REAL_RESULT" = "success"
          fi
```

分支保护只要求 `Real E2E Gate`，不要要求条件执行的 `real_e2e_tests` job。

- [ ] **Step 4: 更新文档并验证格式**

在覆盖矩阵中记录：普通 PR 的 real E2E 可跳过；高风险路径、main 和手动运行必须执行；固定 `Real E2E Gate` 负责汇总结果。

Run:

```bash
cd frontend
pnpm exec prettier --check ../.github/workflows/real-e2e-tests.yml
cd ..
bash -n .github/scripts/should-run-real-e2e.sh
bash .github/scripts/tests/test-should-run-real-e2e.sh
git diff --check
```

Expected: YAML、Bash 和 diff 检查全部通过。

- [ ] **Step 5: 最终收口验证**

Run:

```bash
cd backend
PYTHONPATH=. uv run pytest tests/scripts/test_real_e2e_scripts.py -q
cd ../frontend
pnpm exec playwright test --project=chromium tests/e2e/smoke --list
E2E_STATE_DIR=/tmp E2E_RUN_ID=collect-only IDEER_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:8001 pnpm exec playwright test --config=playwright.real.config.ts --list
cd ..
git diff --check
```

Expected: runner 脚本测试通过；smoke 和 real 测试均能正确收集；diff 无格式错误。此计划不要求本地完整运行 real E2E，首次真实执行由 CI 高风险 PR 或手动 dispatch 验证。

- [ ] **Step 6: 提交独立改动**

```bash
git add .github/scripts/should-run-real-e2e.sh .github/scripts/tests/test-should-run-real-e2e.sh .github/workflows/real-e2e-tests.yml docs/testing/coverage-matrix.md docs/superpowers/plans/2026-07-15-test-gate-simplification.md
git commit -m "ci(e2e): select real browser gate by risk"
```

## 实施停止条件

- 如果路径选择脚本无法明确判断某类改动，先将该路径加入高风险集合，不允许默认降挡。
- 如果 `Real E2E Gate` 在未选择 real E2E 时无法稳定返回成功，停止调整分支保护，先修正汇总逻辑。
- 如果 PR smoke 未覆盖首页、工作区入口和核心导航，不删除原完整 PR 门禁，先补齐 smoke 的最小职责。
- 不通过增加 skip、放宽断言或降低关键 contract 范围换取通过。
