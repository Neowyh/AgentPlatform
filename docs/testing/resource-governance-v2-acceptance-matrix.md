# Resource Governance V2 验收矩阵

> audience: developers, reviewers, QA, release engineering
> status: binding acceptance contract
> last-verified: 2026-08-14
> canonical-path: `docs/testing/resource-governance-v2-acceptance-matrix.md`

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

## 阶段门

每个阶段提交前必须执行：

1. `gitnexus_detect_changes`，确认仅影响预期符号和执行流；
2. 当前阶段的 RED→GREEN 目标测试；
3. 相关 backend/frontend lint 或 check；
4. `git diff --check`；
5. 检查未暂存文件，排除 GitNexus 生成的规则统计和 `dev-log`。

最终门还包括 backend unit/integration/contracts、blocking-I/O、frontend unit/check/E2E、Workflow Worker、Assistants compatibility、内网部署、私有 bundled 初始化、离线包 checksum/manifest 和断网新装。所有要求必须获得新鲜 exit 0 或等价的可核验运行证据。
