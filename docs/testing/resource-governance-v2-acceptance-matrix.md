# Resource Governance V2 验收矩阵

> audience: developers, reviewers, QA, release engineering
> status: binding acceptance contract
> last-verified: 2026-08-16
> canonical-path: `docs/testing/resource-governance-v2-acceptance-matrix.md`

## 切换验收执行记录（2026-08-15，本地工作树 `resource-governance-v2`）

以下为切换 canonical 前本地执行的 fresh 证据，全部真实 exit 0：

- Alembic 单 head `20260814_resource_catalog_v2`，DB 已 `upgrade head`（`alembic_version` 一致）；
- `audit` exit 0 / errors 0；`migrate` 首次 created 10、二次 unchanged 10（幂等）；`verify` exit 0；
- `seed_bundled_resources` created 24 / unchanged 3（含 bundled 身份冲突修复后重建）；目录 34 资源、bundled 27、dependencies 3；
- `compare`（dual）exit 0：total 10 / ok 10，diverged/errors 为空，extras = 24 个 bundled 稳定 UUID（预期信号：bundled 资源不落 legacy 目录）；
- backend：`make lint` exit 0；`make test` 12594 passed；`make test-blocking-io` 5 passed；runtime 修复后全量重跑 `make test` 12596 passed（= 12594 + 新增 2 测试，无回归）；
- frontend：`pnpm check` exit 0（1270 warnings）；`pnpm test` 332 files / 7896 passed；`pnpm test:e2e` 148 passed，1 项 flaky（`i18n-language-switching.spec.ts:337`）单独复跑通过且文件本分支未改动；
- canonical 冒烟（`IDEER_RESOURCE_CATALOG_MODE=canonical`，Gateway 8001）：`/api/resources` 返回 34 项 canonical；`/api/agents|skills|workflows/{name}` 全部 410；老名字 `fault-zeroing` run 经 alias 解析为 UUID 56e2423d… 成功创建；`run_resource_snapshots` 落库 agent+skill 各 1 行（version/hash 正确）；前端 admin 资源页经同源代理渲染 canonical 数据（66 项全局清单，fault-zeroing/srs-writing/bundled skills 可见）。
- canonical Workflow Worker 冒烟（`IDEER_RESOURCE_CATALOG_MODE=canonical`）：`POST /api/resources/{id}/workflow-runs` 201 入队；worker 消费后状态 queued→running→failed（failed 为冒烟占位 `upload_dir` 不存在导致的业务失败，非加载错误）；`run_resource_snapshots` 为该 run 落 3 行完整闭包（workflow fault-zeroing + agent fault-zeroing + skill fault-zeroing，version/hash 正确）。

冒烟发现并修复一处契约断裂：bundled `_prepare_agent` 将 `config.skills` 改写为稳定 UUID，而 `runtime.load_agent_skill_definitions` 只按 slug 匹配导致 bundled Agent run 409。修复为按 UUID 优先、slug 次之匹配，缺失引用 fail-closed；新增 2 个单元测试（UUID 引用解析、缺失引用拒绝），`tests/unit/resources/` 93 passed。

Assistants compatibility 已由 `tests/integration/api/test_assistants_compat_comprehensive.py`（含 `IDEER_RESOURCE_CATALOG_MODE=canonical` 场景）与 `test_assistants_compat_router.py` 覆盖，随 backend 全量 12596 通过。离线部署项已按下方"部署/离线"行执行记录完成验证（含一处缺陷修复）。

本矩阵是完成判定依据。单元测试通过不能替代同一行要求的集成、运行时或部署证据；挂起、扩大 skip、降低断言或旧产物不计为通过。

| 领域 | 必须证明的行为 | 权威证据 |
|---|---|---|
| 身份权限 | owner/non-owner、同/跨部门、viewer/user/department-admin/super-admin 的列表、详情、导出、运行和修改矩阵均 fail-closed | backend unit+contracts；API integration；frontend role E2E |
| 同名资源 | 同 type/slug 不同 owner 可独立创建、浏览、编辑、运行、Fork、归档；转移冲突要求明确 rename | service concurrency tests；API 409 contract；migration audit fixture |
| public 认证 | public 对所有已登录且有 action permission 的用户可用，匿名仍为 401 | API contracts 和 Assistants compatibility tests |
| 草稿/发布 | 非 owner 看不到 draft；draft revision 冲突；发布校验、不可变版本、hash 和 latest 单调推进 | model/store/service tests；故障注入 integration |
| 依赖闭包 | Agent→Skill、Workflow→Agent/Skill 按 UUID 解析；环、缺失、不可见、archived/suspended 均拒绝 | resolver unit/property tests；run-creation integration |
| Run 冻结 | 发布 v2 后新 Run 使用 v2，旧 Run 继续使用快照版本；Worker 重启不重解析名称/latest | Gateway→queue→Worker integration；snapshot DB assertions |
| 工具隔离 | 实际工具为资源声明、调用者权限、平台/沙箱/网络策略交集 | tool policy unit+integration；viewer/user role runtime tests |
| 凭据/记忆 | 共享 Agent 不读 owner 明文凭据、配置回退或个人记忆；记忆按 runner+resource 隔离 | runtime integration with sentinel owner secrets/memory |
| 可见性缩小 | 阻止不再满足闭包的新 Run，撤销 pending application，通知上层 owner；已启动 Run 可完成 | service transaction tests；active-run integration |
| 紧急下架 | suspend 阻止新 Run，并取消闭包含该资源的 queued/running/paused Run | concurrency integration；Worker cancellation/restart tests |
| Archive/purge | owner delete 只 archive；历史版本、快照和审计仍可读取；物理清理只回收安全文件 | lifecycle contracts；retention/GC integration |
| 用户删除 | transfer/archive/purge 经 ResourceService；UUID/历史保持；slug 冲突预检；用户状态清理不删资源快照 | user deletion integration and audit assertions |
| 部门删除 | scope 转移或降 private 同事务执行，审批撤销且部门过滤正确 | admin API integration and rollback tests |
| Fork | 最新发布内容复制为当前用户 private v1；来源可审计；依赖浅复制并重校验 | service/API tests and file/DB hash assertions |
| 文件安全 | 拒绝 symlink、穿越、超限归档/文件数/体积和未经扫描的可执行内容 | adversarial storage tests |
| 跨介质一致性 | 文件失败不写 DB；DB 失败留下可审计未引用对象；reconcile/GC 幂等清理；并发发布唯一 | fault injection and concurrency integration |
| 缓存 | key 含 UUID、version、authz revision；权限正确不依赖手工进程内失效 | multi-process Gateway/Worker tests |
| 名称兼容 | 当前 owner 优先、唯一共享次之、多匹配 409；不任取第一条 | facade/API/frontend redirect tests |
| API/SDK | unified API、typed facade、Assistants `assistant_id` UUID、`lead_agent` 保留、客户端 SDK 一致 | contracts + SDK integration |
| 前端 | UUID 动态路由，展示 slug/display name；Admin、审批、审计、收藏、统计、导入导出正确 | Vitest、TypeScript/ESLint、Playwright replay artifacts |
| 数据迁移 | 单一 head；空库、旧库、重复升级、downgrade 边界；audit/migrate/verify/rollback 幂等 | Alembic schema suite；realistic legacy fixture；backup restore |
| 部署/离线 | bundled UUID 稳定；初始化任一失败整体失败；内网、无沙箱包、断网新装均可验证 | script tests；bundle hash/manifest checks；offline installation log |

### 部署/离线行执行记录（2026-08-16）

- **离线包 checksum/manifest**：`dist/intranet/ideer-20260815-5abd849c6-1x-nosandbox/`（本分支产物）`sha256sum -c SHA256SUMS` 6/6 OK（images tar、source tar、作业指导书、deploy/check 脚本、MANIFEST）；MANIFEST 含版本、git commit、镜像 digest、文件清单。
- **无沙箱包**：该包为 `--no-sandbox` 构建（`ideer-sandbox` digest: not bundled），断网新装验证同时覆盖"无沙箱包"场景——部署 exit 0，sandbox 镜像缺失为 check 脚本 WARNING 级（非错误），runtime config 保留 `AioSandboxProvider` + 缺省镜像，符合文档化预期。
- **断网新装（隔离模拟）**：在 `/tmp/opencode/intranet-sim/` 完整复制 bundle 后 `deploy-intranet.sh up`（`PORT=2027` 规避本机系统 nginx 占用 2026）——docker load 本地镜像 tar → compose up → 健康检查 → super admin 自动创建 → bundled 27 资源全量 created（24 skill + 2 agent + 1 workflow，owner 为 super admin）→ fault-zeroing workflow seeded（Version 1）。冒烟：`/api/resources` 返回 27 项全 bundled（含 UUID id、storage_kind=bundled）；legacy 名称 alias（agent/skill/workflow fault-zeroing）dual 模式下均 200；nginx 前端 200。
- **初始化任一失败整体失败（fail-fast 语义实测）**：首轮部署因 bundled agent/workflow 源在容器内缺失而 seed 失败，脚本整体 exit 1、提示 `canonical bundled resource seeding failed` / `private resource initialization failed`，容器不进入"部署完成"状态；修复后全流程 exit 0。失败语义符合"任一失败整体失败"要求。
- **发现并修复打包链缺陷**：gateway 镜像仅 COPY `backend`，而 `bundled-resources.json` 的 bundled agent 源位于 `docs/*-agent/agent`、workflow 源位于 `workflows/`，compose 未挂载导致容器内 seed 缺源。修复：`docker/docker-compose.intranet.yaml` 为 gateway 与 workflow-worker 服务增加 `../docs:/app/docs:ro` 与 `../workflows:/app/workflows:ro` 挂载（见 fix 提交）。修复后隔离模拟部署 exit 0、27 created。当前 dist 包为修复前产物，下次打包自动携带修复。

## 阶段门

每个阶段提交前必须执行：

1. `gitnexus_detect_changes`，确认仅影响预期符号和执行流；
2. 当前阶段的 RED→GREEN 目标测试；
3. 相关 backend/frontend lint 或 check；
4. `git diff --check`；
5. 检查未暂存文件，排除 GitNexus 生成的规则统计和 `dev-log`。

最终门还包括 backend unit/integration/contracts、blocking-I/O、frontend unit/check/E2E、Workflow Worker、Assistants compatibility、内网部署、私有 bundled 初始化、离线包 checksum/manifest 和断网新装。所有要求必须获得新鲜 exit 0 或等价的可核验运行证据。
