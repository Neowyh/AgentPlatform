# DeerFlow v2.1.0 conflict ledger

- Integration branch: `integration/deerflow-v2.1.0`（worktree `AgentPlatform-df-v210`）
- Locked target: tag `v2.1.0`（`345f08be00c8a9495079b732a39b46aa9af1584e`）；base `0f7d8709d3bbf0be26460b6277fbad9329302243`；pre-merge snapshot tag `deerflow-v2.1.0`
- Frozen: 2026-10-01（票 02）。三个并行分类报告（backend 42 / frontend 40 / 非冲突清点）汇成下表。
- 冲突 96 = 91 UU + 1 AA + 2 UD + 2 DU；自动合并 M 522（其中双侧都改的"暗冲突候选" 76，见 §3）；新增 A 401（上游测试/文档为主）；删除 D 2（上游正常拆分，无本地语义损失）。

## §1 冲突文件处置表（96）

处置枚举：收上游 / 保本地 / 语义合并 / 机械合并。Owner：DF=DeerFlow / AP=AgentPlatform / 语义=语义合并区。

### 片 A（harness，6 文件；另有 16 个自动合并补丁文件见 §3）

| 文件 | 处置 | 合并形状 | Owner | PATCH |
| --- | --- | --- | --- | --- |
| harness/agents/lead_agent/agent.py | 语义合并 | 保留 frozen 分支（PATCH-010 全部），memory_enabled/allowed_subagents/conversation-reader/新工具注入同时叠加到 frozen 与非 frozen 两条装配路径 | 语义 | 010 |
| harness/agents/lead_agent/prompt.py | 语义合并 | apply_prompt_template 签名取并集，正交段落叠加 | 语义 | 010 |
| harness/persistence/bootstrap.py | 语义合并（TBD 已裁决，见 §5 D1） | 采纳上游"版本行强校验"作为终态不变量，但已知版本集必须经统一链 version_locations 覆盖两棵树；at-head 短路保留 | 语义 | 006/015/031 |
| harness/persistence/models/__init__.py | 语义合并 | 上游 Project/RunChangeClock/UserPreference 导出 ∪ 本地 legacy Core 表导出 | 语义 | 031 |
| harness/runtime/journal.py | 语义合并 | 以上游事件管线重构为基底重新落 PATCH-026（TTFT+ensure_trace_id），丢弃本地格式重排噪音 | 语义 | 026 |
| harness/skills/storage/user_scoped_skill_storage.py | 收上游 | 上游 write_custom_skill 锁内实现是本地 PATCH-030 的超集；台账勾销该文件条款 | DF | 030 |

### 片 B（gateway，9 文件）

| 文件 | 处置 | 合并形状 | Owner |
| --- | --- | --- | --- |
| gateway/app.py | 语义合并 | 企业路由/种子保留；lifespan 按上游顺序（调度器 fail-closed→trash 清扫→channel）重排缝合 | 语义 |
| gateway/auth/pat.py | 语义合并 | scope 并集（上游 projects/trash + 本地 assistants:read/models:read），上游路由白名单全收 | 语义 |
| gateway/authz.py | 语义合并 | PROJECTS_* 并入全集与 viewer 只读集（viewer 仅 projects:read），保留本地 RBAC 结构与 resolve_model_authorization，收上游 resolve_route_permissions_for_request | 语义 |
| gateway/routers/auth.py | 语义合并 | /me 同时返回本地平台身份（department 等）与上游 effective permissions（经本地 authz 解析） | 语义 |
| gateway/routers/features.py | 语义合并 | conversation_references 与 knowledge 两个 feature 字段并存 | 语义 |
| gateway/routers/runs.py | 语义合并 | 本地 evidence 端点/模型导入保留；访问器/序列化符号切换上游新名（abuild_checkpoint_state_accessor 等） | 语义 |
| gateway/routers/thread_runs.py | 语义合并 | 本地端点/模型保留；消息读取改经上游 conversation_reader 模块（保留本地权限/中间件行过滤语义）；吸收 Idempotency-Key 与异步访问器 | 语义 |
| gateway/routers/uploads.py | 语义合并 | 逐端点缝合：本地 evidence/staging 语义与上游 upload_ingestion 服务化/no-overwrite 并存 | 语义 |
| gateway/services.py | 语义合并 | ⚠ 最大缝合面（23 hunk）：canonical-run/RBAC/证据语义叠加在上游访问器图缓存/项目上下文/UNTRUSTED/KeyedLockTable 之上 | 语义 |

### 片 C（backend/tests 12 文件 + extension-api 1）

| 文件 | 处置 | 合并形状 |
| --- | --- | --- |
| test_migration_0004/0007/0015_*.py（3 件） | 收上游 | 动态 `_get_head_revision()` 断言天然适配统一链头，删除本地钉值 |
| test_persistence_bootstrap.py | 语义合并 | 上游动态断言 + 0019 断言叠加在本地统一链夹具上；期望随 §5 D1 联动 |
| test_persistence_bootstrap_concurrency.py | 语义合并 | at-head 短路期望（upgrade_calls == []）随 D1 联动 |
| test_persistence_bootstrap_regression.py | 语义合并 | 并集 |
| test_authorization_route_permissions.py | 语义合并 | 断言并集：PROJECTS_* + ASSISTANTS/MODELS_READ；viewer 集随 authz 决议 |
| test_extension_api_contracts.py | 语义合并 | 上游 RunEvidenceReader/RunPage 契约 ∪ 本地 RunEvidenceEnvelope 契约；API_VERSION 取上游 0.2.1 |
| extension-api/__init__.py | 语义合并 | __all__ 并集；版本 0.2.1 |
| test_run_journal.py | 语义合并 | 上游并发/串行化新测试为基底，重放本地 TTFT 用例 |
| test_subagent_executor.py | 语义合并 | 上游新测试为主，本地 fixtures 的 runtime_evidence_hooks=None 字段保留 |
| test_threads_router.py | 语义合并 | 上游 +839 行为主，保留本地 monkeypatch 加固 |

### 片 D（config 三件）

| 文件 | 处置 | 合并形状 |
| --- | --- | --- |
| config.example.yaml | 语义合并 | 键块并集；config_version 取 45（knowledge/企业段保留；recursion/elide/projects/task_continuity 新段吸收） |
| extensions_config.example.json | 语义合并 | 本地最小企业形态 + 追加 parallel-search 可选条目 |
| .env.example | 语义合并 | 本地为主（iDeer 品牌化），上游新键（SOFYA/IMAGE_GENERATION）注释态追加 |

### 片 E（frontend 40 文件）—— 裁决要点

特殊形态 5 件：
1. `capabilities/page.tsx` [AA] → **保本地 redirect**；上游 CapabilityCenter/skill-gallery/plugin-gallery/skill-export-dialog 组件必须真实挂载进本地 `[tab]` 页（experts/skills/connectors），否则上游功能"路由在入口不可见"（P1 最大风险点）
2. `ai-elements/model-selector.tsx` [UD] → **维持上游删除**；新 model-picker-content 无 CDN logo 依赖，本地回退代码作废；type-* 排版类贴到新文件
3. `settings/skill-settings-page.tsx` [UD] → **维持删除 + 登记**；本地 RBAC/可见性能力先确认在能力中心技能 tab 存在
4. `workspace/agent-welcome.tsx` [DU] → **维持删除**；display_name 三元判断移植到专家聊天页；staged agent-display-name.dom.test.tsx 同步改写（现状必编译失败）
5. `agents/agent-settings-dialog.tsx` [DU] → **维持删除 + 白名单**；display_name 编辑/视口修复移植到 experts/[agent_name]/edit；staged agent-settings-layout.spec.ts 改写或撤销

入口/组件/core 要点：本地导航六项为准 ∪ 上游 capabilities 语义（`t.capabilities.title` 键必须在 i18n 合并后存在）；`agents/[...]chats/page.tsx` 保本地 redirect + 上游 5 项页级特性移植清单（归档状态/RUNS_CANCEL/agentSkillNames/resolveThreadContext/display_name → 本地 experts 聊天页）；input-box 以上游为基逐块回贴本地特性（ModelSelector 引用全改 ModelPicker）；recent-chat-list 上游为基移植"删除后落位邻居"；settings-dialog 本地结构 + 旧技能/工具分区改跳能力中心；chats/scheduled-tasks/sidecar/artifact-viewer 等收上游+复贴本地排版类；threads/hooks 上游消息序重构为基并入本地回调/上传扩展；i18n 三件套与 pnpm-lock 机械合并（lock 以合并版 package.json 重新生成，勿手拼）。

**staged 孤儿裁决（D3）**：`star-counter.tsx` + `github-stars/route.ts`（外呼 api.github.com/repos/bytedance/deer-flow）→ **drop**（离线/品牌冲突）；本地 header 保无星标形态。

### 片 F（CI/部署/文档 12 文件）

Makefile 目标并集；AGENTS.md 家族保本地重写+回填上游事实句（nginx 入口/loopback 默认）；backend/docs 四件本地结构+按最终路由追加上游端点节；nginx.conf 本地配置+上游 timeout 块；provisioner 本地基底+上游 max_shell_sessions 容量特性；deploy.sh 本地为主叠上游 socket/Windows 修复；pnpm.py 本地 TEST_PNPM_BIN 优先+上游循环解析。CI push trigger 的 `main` 分支名保持现状（PR trigger 生效，不扩权）。

## §2 交叉依赖锁定（收敛顺序约束）

1. bootstrap.py（D1）向下锁定 3 个 persistence 测试期望与 at-head 短路。
2. authz.py viewer/projects:read 锁定 test_authorization_route_permissions。
3. PAT scopes 与 runs/thread_runs 的访问器符号名（abuild_checkpoint_state_accessor）须同批落地。
4. capabilities AA 裁决锁定 E 片 tab 页挂载与 settings-dialog 旧分区去向。
5. 前端 auth-disabled 契约的 permissions 清单依赖后端 /me 合并结果，联调后定稿。

## §3 暗冲突候选（76，自动合并但双侧都改——票 03/04/08 必核）

**harness 16 个（并入票 03/04 重放范围）**：task_tool(+54/-2, P005)、tool_error_handling_middleware(+48/-2, P020)、openai_codex_provider(+40/-2, P025)、local_sandbox(+24/-14, P016)、runs/manager(+17/-17, P013/027)、aio_sandbox_provider(+25/-5, P021)、runs/worker(+8/-8, P027)、executor(+17/-17, P028)、input_sanitization_middleware、client.py、extensions/gateway.py（均 P030）、skills/projection.py（P030）、config/app_config.py(+8/-10, P004/023)、config/AGENTS.md（P003）、sandbox/tools.py（P017）、utils/readability.py（P032）。

**gateway 5**：assistants_compat.py(+69/-37 ⚠最大)、threads.py(+45/-33)、deps.py(+30/-7)、routers/skills.py、auth/models.py。
**channels 3**：manager.py、service.py、telegram.py。
**extension-api contracts.py**(+79/-1)：上游新增 run_evidence 公共契约（run_evidence.py 新文件 + harness extensions/run_evidence.py host adapter）与本地 PATCH-024/027/028 证据机制域重叠——**PATCH 退役评估的关键输入**。
**backend/tests 17**（test_config_version、extension_task_lifecycle、artifact_archive、aio_sandbox_provider、gateway_lifespan_shutdown、codex_provider、pat_auth、channels、sandbox_authorization、multi_worker_run_ownership、extension_manager、dev_entrypoint、app_config_reload、local_sandbox_provider_mounts、tool_error_handling_middleware、blocking_io/persistence_bootstrap、blocking_io/skills_update_router）。
**backend 其他 6**：pyproject.toml、uv.lock(+216/-3)、README.md、docs/ARCHITECTURE.md、docs/summarization.md、packages/harness/pyproject.toml（双侧都改且不在台账——包元数据，非 deerflow/ 源码登记范围）。
**frontend**：core 9（settings/local.ts +48/-35 ⚠回流、api-client.ts、agents/types.ts、features/hooks.ts、artifacts/preview.ts、auth/types.ts、threads/api.ts、threads/utils.ts、utils/files.tsx）+ components 7（use-thread-chat.ts +48/-3、memory-settings-page.tsx 等 5 个 ≤10 行）+ tests 4 + package.json(+17/-2) + src/AGENTS.md。
**scripts 3**（doctor.py +68/-19 等）、**skills 2**（image/video-generation SKILL.md）、**docker 1**（nginx.local.conf ⚠回流 12/45）。

## §4 回流文件（12/75 本地已删行被上游带回——修复清单）

确证回流：test_artifact_archive.py（4/4 全回流，ARCHIVE_URL POST 断言块）、docker/nginx/nginx.local.conf（12/45，websocket/超时块）、frontend settings/local.ts（6/29，isBrowser 等）、aio_sandbox_provider.py（2/5, P021）；疑似（泛型行干扰）：scheduled-tasks.spec、memory-settings-page、docs-localized-links.spec、threads.py、api-client.ts、runs/manager.py、local_sandbox.py、test_local_sandbox_provider_mounts.py。修复原则：本地删除意图优先，逐文件核对后恢复删除。

## §5 冻结决议

- **D1（bootstrap TBD 裁决）**：采纳上游强校验终态；已知版本集经统一链双 version_locations 解析；保留 at-head 短路与 PATCH-014 inspector 守卫。
- **D2（迁移链双 head）**：上游在 0018 后线性延伸至 0025_repair_run_change_seq，与本地 20260908_unify_migration_chains 形成 0018 双子节点/双 head。**修复：新增前向合并修订 20261001_rejoin（down_revision=(20260908_unify, 0025_repair_run_change_seq)）恢复单 head**；不改写已部署的 20260908 修订（forward-only 纪律）；台账 PATCH-015 族补记；前后 alembic heads 断言钉住。
- **D3（staged 孤儿）**：github-stars route + star-counter 组件 drop（外呼上游仓库，与离线/品牌冲突）。
- **D4（有意排除登记）**：/workspace/agents 管理入口移除、settings 技能/工具三分区改跳能力中心——收尾登入 BASELINE_NAV_REMOVALS/采用矩阵。

## §6 状态

| 片 | 票 | 状态 |
| --- | --- | --- |
| A（6 冲突 + 16 暗冲突） | 03/04 | open |
| B（9 + §3 gateway/channels 暗冲突） | 05 | open |
| C（13，含 D2 修复） | 06 | open |
| D（3） | 07 | open |
| E（40，含 D3/D4 与 §3 frontend 暗冲突） | 08 | open |
| F（12） | 09 | open |
| 回流修复（§4） | 并入对应片 | open |

## Closure record

所有行保持 open，直至每行指名 focused test 或报告后关闭（沿用 0f7d8709 轮纪律）。
