# Definition of Done — checklist（deer-flow v2.1.0 合并）

> 票 12 逐项闭环。`✅` = 有证据通过，`⚠️` = 如实记录的例外，`⏳` = 待办/挂起。
> 分节与 `deerflow-main-0f7d8709/DoD_CHECKLIST.md` 对齐，验收底线见
> 合并计划 §4.4（内网特性防线）。

## Git

- ✅ `git merge-base --is-ancestor v2.1.0 HEAD` → 上游 v2.1.0 全量并入 integration/deerflow-v2.1.0（merge commit `0f632ade4`，96 冲突逐 hunk 处置）。
- ✅ 合并前本地快照 tag `deerflow-v2.1.0`（= develop `44530091a`）留存回滚锚点；与上游锚点 tag `v2.1.0`（已推 origin）命名区分已写入治理文档。
- ✅ 冲突台账 `CONFLICT_LEDGER.md`：§1 六片处置冻结、§3 76 个暗冲突全登记、§4 回流文件清单、§5 冻结决议 D1–D5。
- ✅ 补丁台账 `UPSTREAM_PATCH_LEDGER.md` 唯一权威化：PATCH-001..032 全量 reassess（31 保 / 1 闭 / 1 吸收），`git diff v2.1.0 -- backend/packages/harness/deerflow` 与台账零未登记差。

## Runtime

- ✅ 后端全量（非 serial、排除 blocking_io/llm/live/external）：**29386 passed / 237 skipped / 0 failed**（2103s，候选 = 提交批次 `1f18d4170..c18d47b59` 之前的工作树同内容；提交后 focused 复跑 165+150+118 全绿）。
- ✅ 合并丢失语义修复后 focused 验证：sse_consumer 订阅循环恢复、`_ensure_thread_metadata` 去重、迁移真实链头探测、agent store 引导缝、MCP 任务快照清理、上传虚拟路径 skip 包络（`1f18d4170..76c049e6b`）。
- ✅ pr-standard lane **exit 0**（第五轮，候选 `2a7bcd9d4`）：local-runtime 8-11s ✅、backend-standard 1030s ✅（29385 passed / 1 failed→逐根因修复后全绿）、frontend-standard 458s ✅（1281/1282→修复后全绿）、frontend-smoke 63s ✅；`TEST_LANE_DURATION lane=pr-standard seconds=1563 status=0`。
- ✅ 收敛期暴露并修复的顺序/负载依赖问题（各有单测验证）：logging real-emit urllib3 级别隔离（`5d1aad7d3`）、uvloop 跨线程 spawn 竞态改标准库循环（`6776673a9`）、skill case-probe 收集期竞态（前置提交）、workbuddy smoke 模型选择器 role 与侧栏 thread-list testid（`4a054ef1b`/`30c70ccbf`）、browser 日志 URL 双层脱敏契约分层（前置提交）、staged-chip 生命周期对齐（`2a7bcd9d4`）。
- ⏳ core-full 交付级 lane 逐子 lane summary + TEST_LANE_DURATION（运行中）。

## AgentPlatform

- ✅ Gateway 授权并集：`_ALL_PERMISSIONS` = 本地 THREADS*/RUNS* + 上游 ASSISTANTS_READ/MODELS_READ/PROJECTS_*；viewer 集合并集；本地 RBAC 403 契约保留（`test_auth_me_permissions` 7✓，fallback 桩 `_platform_identity_for_user`）。
- ✅ 入口对齐四层检查 `check-frontend-entry-parity.sh 44530091a HEAD` 全层 PASSED（路由/导航/i18n/API 挂载）。
- ✅ 上游 SkillGallery 所需 `/api/skills/custom*` 已挂载并置于 AuthMiddleware 之后（app.py）。
- ✅ Resource Governance 边界未动：canonical `/api/resources`，前端零 `/api/agents` 调用（仅 features 注释）。
- ✅ D3：star-counter/github-stars 不吸收（外呼 bytedance 仓库，离线红线）；D4：`/workspace/agents` 入口移除后重定向语义由冻结处置锁定。

## Security

- ✅ 上传沙箱获取走 authz `try_acquire_sandbox_for_request` 授权门（sandbox:execute RBAC 门 + lease manager）；评审中拒绝了绕过授权门的同步回退包装器，测试 fakes 改为 `acquire_async` AsyncMock 对齐生产契约。
- ✅ DooD socket 仅非 local 沙箱模式挂载，upstream 变量优先（`DEER_FLOW_DOCKER_SOCKET`），SECURITY.md 警示保留。
- ✅ 本地机密零提交：config/intranet 值均走未跟踪文件（pre-commit block-untrackable-files 通过）。

## Data

- ✅ 迁移链 D2：`20261001_rejoin_upstream_line` no-op 合流修订（down = 20260918_knowledge_publish_eval_gate × 0025_repair_run_change_seq），单一 alembic head 验证。
- ✅ bootstrap 真实链头探测（`_get_head_revision`）替代元数据快照，低于真头的库仍尝试升级（`76c049e6b`）。
- ✅ 迁移相关套件全绿：TestUnifiedMigrationChain、0022/0023/0025、forward_revision_compat、unified_chain_adoption。

## Tests

- ✅ backend 全量 29386/237 skipped/0 failed（见 Runtime）。
- ✅ frontend vitest 1281/1282 + rstest 保留套件；唯一失败 `input-box-project-attachment.dom.test.tsx`（staged-count 重置）为合并前已存在、bisect 判依赖漂移 → 登记 develop 跟进，非合并回归。
- ✅ `pnpm check` exit 0（0 errors / 1324 warnings，warning 为存量基线）。
- ⏳ pr-standard：✅ 见 Runtime 节（exit 0，逐子 lane summary 在案）。
- ⏳ core-full：backend-full（含 serial）、frontend-core（coverage+check）、frontend-mock-e2e summary（运行中）。
- ✅ Playwright smoke workbuddy-cascade：3 例失败已逐根因修复并在 lane 内验证（模型选择器 role=button 对齐、侧栏 thread-list testid 恢复、task-first 断言随 testid 恢复通过）；frontend-smoke 子 lane 连续两轮 status=0。

## Offline

- ⏳ `scripts/package-intranet-offline.sh` bundle 重建（bundled-skills 白名单）+ 产物 manifest/SHA256SUMS。
- ⏳ bundle 内 `./check-intranet.sh` 8/8。
- ⏳ 容器栈冒烟（登录/resources/thread/frontend + 重启持久化）。
- ✅ 技能包边界：`test_skills_loader`（SKILL.md 目录=包边界）+ `test_skills_bundled`（frontmatter）在全量通过中覆盖；skill-creator 快速校验器回补（`27e571842`）保证导出回路可用。

## Merge

- ⏳ GitNexus `detect-changes --scope compare --base-ref product/offline-1.x` 干净（partial/truncated 不算过）。
- ⏳ `--no-ff` 合入 develop + 合并后 pr-standard 复验。
- ⏳ integration 分支与 worktree 删除、stash@{0}（取消代理 WIP）确认被取代后删除、`.scratch` 票据全关。
- ⏳ PR 材料定稿（PR_MATERIALS.md：用户可见变更/验证命令/high-risk lane Real E2E 选择注明）。
- ⏳ 用户执行 `git push origin develop`。
