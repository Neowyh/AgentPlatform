# 后端改进项清单

> 本文档记录 `offline_feature` 分支相对于 `main` 的全面检查中发现的剩余改进项（P2/P3）。
> P0/P1 项已全部修复，见本文档末尾的已完成清单。
>
> 生成日期: 2026-06-09

---

## 目录

- [P2 — 中等优先级 (45 项)](#p2--中等优先级)
  - [安全与认证 (6)](#p2-安全与认证)
  - [持久化与配置 (5)](#p2-持久化与配置)
  - [工作流引擎 (6)](#p2-工作流引擎)
  - [工具与沙箱 (3)](#p2-工具与沙箱)
  - [Agent 与运行时 (8)](#p2-agent-与运行时)
  - [测试覆盖 (6)](#p2-测试覆盖)
  - [API 网关 (5)](#p2-api-网关)
  - [构建与依赖 (6)](#p2-构建与依赖)
- [P3 — 低优先级 (29 项)](#p3--低优先级)
- [已完成项 (P0/P1)](#已完成项)

---

## P2 — 中等优先级

### P2 安全与认证

#### P2-AUTH-01: SQLite 首次用户竞态

- **文件**: `backend/app/gateway/authz.py:499-502`
- **问题**: SQLite 不支持 `SELECT FOR UPDATE`，两个并发首次用户可能同时看到 `admin_count == 0` 并都被提升为 `super_admin`。
- **当前行为**: IntegrityError 回退后重新查询用户，但不重新检查 admin_count。
- **改进方案**:
  ```python
  # 在 IntegrityError catch 块中，重新查询后检查用户角色
  except IntegrityError:
      await session.rollback()
      stmt = select(UserModel).where(...)
      rbac_user = (await session.execute(stmt)).scalar_one()
      # 如果用户已被其他请求创建为 super_admin，但当前请求也试图提升，
      # 重新检查 admin_count 并可能降级
      if rbac_user.role == UserRole.SUPER_ADMIN:
          admin_count = (await session.execute(count_stmt)).scalar() or 0
          if admin_count > 1:
              rbac_user.role = UserRole.USER
              await session.commit()
  ```
- **影响**: 低 — SQLite 单机部署场景罕见并发首次登录

#### P2-AUTH-02: JWT 密钥文件权限

- **文件**: `backend/app/gateway/auth/config.py:36-58`
- **问题**: 自动生成的 `.jwt_secret` 仅依赖文件系统权限（0o600），备份/复制可能丢失权限。
- **改进方案**:
  ```python
  # 生产环境强制要求显式设置
  def get_auth_config() -> AuthConfig:
      if os.environ.get("IDEER_ENVIRONMENT") == "production" and not os.environ.get("AUTH_JWT_SECRET"):
          raise RuntimeError("AUTH_JWT_SECRET must be set in production environment")
  ```
- **影响**: 中 — 生产环境安全基线

#### P2-AUTH-03: 内部令牌多 Worker 不一致

- **文件**: `backend/app/gateway/internal_auth.py:15-19`
- **问题**: 未设置 `IDEER_INTERNAL_AUTH_TOKEN` 时，每个 worker 生成不同随机令牌，跨 worker 内部调用失败。
- **改进方案**:
  ```python
  # 从 JWT_SECRET 确定性派生内部令牌（已跨 worker 共享）
  def _derive_internal_token() -> str:
      jwt_secret = os.environ.get("AUTH_JWT_SECRET", "")
      if jwt_secret:
          import hashlib
          return hashlib.sha256(f"{jwt_secret}:internal-auth".encode()).hexdigest()[:43]
      return secrets.token_urlsafe(32)
  ```
- **影响**: 中 — 多 worker 部署场景

#### P2-AUTH-04: 角色变更无审计日志

- **文件**: `backend/app/gateway/routers/admin.py:121-153`
- **问题**: `update_user_role` 和 `disable_user` 无审计日志记录谁在何时做了什么变更。
- **改进方案**: 已在 P1 中为 `update_user_role` 和 `disable_user` 添加了 `logger.warning` 审计日志。后续可扩展为结构化审计表。
- **影响**: 低 — 已部分修复

#### P2-AUTH-05: DB 角色未校验枚举

- **文件**: `backend/app/gateway/authz.py:322-353`
- **问题**: `UserModel.role` 是 `String` 类型，数据库中可能存储非枚举值（如直接 SQL 插入），导致权限判断异常。
- **改进方案**:
  ```python
  # 在 get_current_rbac_user 中添加角色验证
  try:
      UserRole(rbac_user.role)
  except ValueError:
      logger.error("Invalid role '%s' for user %s, defaulting to viewer", rbac_user.role, rbac_user.id)
      rbac_user.role = UserRole.VIEWER
  ```
- **影响**: 低 — 数据库完整性保护

#### P2-AUTH-06: routers/__init__.py 缺失导入

- **文件**: `backend/app/gateway/routers/__init__.py`
- **问题**: `admin`、`tools`、`agents` 未在 `__init__.py` 中导入。
- **改进方案**: 已在 P1 中修复。
- **影响**: 已修复

---

### P2 持久化与配置

#### P2-PERSIST-01: SQL 注入风险

- **文件**: `backend/packages/harness/ideer/persistence/engine.py:51`
- **问题**: `_auto_create_postgres_db` 中数据库名通过 f-string 插入 SQL，含双引号的名称可逃逸。
- **改进方案**:
  ```python
  # 转义嵌入的双引号
  db_name_escaped = db_name.replace('"', '""')
  await conn.execute(text(f'CREATE DATABASE "{db_name_escaped}"'))
  ```
- **影响**: 中 — PostgreSQL 自动建库场景

#### P2-PERSIST-02: create_all 与 Alembic 冲突

- **文件**: `backend/packages/harness/ideer/persistence/engine.py:137`
- **问题**: 启动时无条件运行 `create_all()`，与 Alembic 迁移冲突（ALTER TABLE 被跳过）。
- **改进方案**:
  ```python
  # 检测是否已有 Alembic 版本表，有则跳过 create_all
  async with _engine.begin() as conn:
      has_alembic = await conn.run_sync(
          lambda sync_conn: inspect(sync_conn).has_table("alembic_version")
      )
      if not has_alembic:
          await conn.run_sync(Base.metadata.create_all)
  ```
- **影响**: 中 — 生产部署安全

#### P2-PERSIST-03: thread_meta 更新丢失

- **文件**: `backend/packages/harness/ideer/persistence/thread_meta/sql.py:188`
- **问题**: `update_metadata()` 的读取-修改-写入无锁保护，并发更新丢失。
- **改进方案**:
  ```python
  # 使用 SELECT FOR UPDATE 锁定行
  row = await session.get(ThreadMetaRow, thread_id, with_for_update=True)
  ```
- **影响**: 中 — 并发元数据更新场景

#### P2-PERSIST-04: thread_meta 所有权 TOCTOU

- **文件**: `backend/packages/harness/ideer/persistence/thread_meta/sql.py:159`
- **问题**: `_check_ownership` 与后续 UPDATE 分离，中间可被并发修改。
- **改进方案**:
  ```python
  # 在 UPDATE 语句中直接包含 user_id 条件
  stmt = (
      update(ThreadMetaRow)
      .where(ThreadMetaRow.thread_id == thread_id, ThreadMetaRow.user_id == resolved_user_id)
      .values(display_name=display_name, updated_at=datetime.now(UTC))
  )
  result = await session.execute(stmt)
  if result.rowcount == 0:
      return  # 所有权已变更或行不存在
  ```
- **影响**: 中 — 并发安全

#### P2-PERSIST-05: PG 连接池配置缺失

- **文件**: `backend/packages/harness/ideer/persistence/engine.py:125`
- **问题**: PostgreSQL 引擎未配置 `pool_recycle`、`pool_timeout`，可能导致过期连接。
- **改进方案**:
  ```python
  _engine = create_async_engine(
      url,
      echo=echo,
      pool_size=pool_size,
      pool_pre_ping=True,
      pool_recycle=1800,  # 30 分钟回收
      pool_timeout=30,    # 30 秒获取超时
      json_serializer=_json_serializer,
  )
  ```
- **影响**: 中 — 云数据库/PgBouncer 场景

---

### P2 工作流引擎

#### P2-WF-01: 并行步骤状态损坏

- **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:28-38`
- **问题**: 并行子步骤共享 `WorkflowState`，ID 冲突时静默覆盖。
- **改进方案**:
  ```python
  # 子步骤 ID 加父步骤前缀
  namespaced_id = f"{parent_step_id}.{sub_id}"
  state.set_step_result(namespaced_id, status="completed", output=result)
  ```
- **影响**: 高 — 并行工作流正确性

#### P2-WF-02: 循环步骤状态覆盖

- **文件**: `backend/packages/harness/ideer/workflows/steps/loop_step.py:70-98`
- **问题**: 循环迭代覆盖前次结果，finally 块用列表覆盖单值。
- **改进方案**:
  ```python
  # 每次迭代使用命名空间化的 key
  iter_key = f"{sub_id}[{idx}]"
  state.set_step_result(iter_key, status="completed", output=result)
  # finally 块聚合时保留原始 key 但输出为列表
  state.set_step_result(sub_id, status=status, output=outputs)
  ```
- **影响**: 高 — 循环工作流正确性

#### P2-WF-03: 子步骤 ID 与外部步骤冲突

- **文件**: `backend/packages/harness/ideer/workflows/parser.py`
- **问题**: 解析器仅验证顶层步骤 ID 唯一性，不检查并行/循环子步骤 ID。
- **改进方案**: 在 `_parse_workflow` 中收集所有步骤（含子步骤）ID 并检查唯一性。
- **影响**: 中 — 工作流定义验证

#### P2-WF-04: 模板表达式长度限制

- **文件**: `backend/packages/harness/ideer/workflows/template.py:14`
- **问题**: 正则匹配无长度限制，超长表达式导致 CPU 压力。
- **改进方案**: 已在 P1 中通过 `except Exception` 部分缓解。可进一步添加：
  ```python
  if len(expr) > 1000:
      raise ValueError(f"Template expression too long: {len(expr)} chars (max 1000)")
  ```
- **影响**: 低 — 防御性编程

#### P2-WF-05: 工作流取消 API

- **文件**: `backend/app/gateway/routers/workflows.py`
- **问题**: 无取消运行中工作流的 API。
- **改进方案**:
  ```python
  @router.post("/{workflow_name}/runs/{run_id}/cancel")
  async def cancel_workflow_run(...):
      # 设置状态为 CANCELLED
      # human_step 轮询会检测到并退出
      # agent/tool 步骤需要 asyncio.Event 协作取消
  ```
- **影响**: 中 — 运维能力

#### P2-WF-06: 重试退避无 Jitter

- **文件**: `backend/packages/harness/ideer/workflows/executor.py:110`
- **问题**: 线性退避无随机抖动，多步骤同时失败时惊群效应。
- **改进方案**:
  ```python
  import random
  await asyncio.sleep(retry.backoff * (attempt + 1) + random.uniform(0, 1))
  ```
- **影响**: 低 — 生产稳定性

---

### P2 工具与沙箱

#### P2-TOOL-01: 环境变量泄露

- **文件**: `backend/packages/harness/ideer/community/code_interpreter/tools.py:40-45`
- **问题**: `_SAFE_ENV_KEYS` 包含 `PYTHONPATH`、`NODE_PATH`、`HOME`，可被利用加载恶意模块。
- **改进方案**: 已在 P1 中从 MCP 服务器版本移除。LangChain 工具版本现在使用 sandbox，不再直接执行。
- **影响**: 已修复（通过沙箱化）

#### P2-TOOL-02: 无资源限制

- **文件**: `backend/packages/harness/ideer/community/code_interpreter/tools.py:57-64`
- **问题**: 无 CPU/内存/磁盘限制，恶意脚本可耗尽资源。
- **改进方案**: 已在 P1 中为 MCP 服务器版本添加了 `resource.setrlimit`。LangChain 版本通过沙箱容器资源限制天然隔离。
- **影响**: 已修复

#### P2-TOOL-03: seccomp=unconfined

- **文件**: `backend/packages/harness/ideer/community/aio_sandbox/local_backend.py:133-144`
- **问题**: Docker 容器使用 `--security-opt seccomp=unconfined`，禁用系统调用过滤。
- **改进方案**:
  ```python
  # 创建最小 seccomp profile，仅允许必要的系统调用
  # 或使用 Docker 默认 profile 并添加白名单
  security_opt = ["seccomp=/etc/ideer/seccomp-profile.json"]
  ```
- **影响**: 中 — 容器安全加固

---

### P2 Agent 与运行时

#### P2-RUNTIME-01: 内存存储 TOCTOU

- **文件**: `backend/packages/harness/ideer/agents/memory/storage.py:66-71`
- **问题**: `FileMemoryStorage` 的 mtime 检查在锁外执行，缓存可能过期。
- **改进方案**:
  ```python
  # 将 mtime 检查移入锁内
  with self._lock:
      current_mtime = path.stat().st_mtime
      if current_mtime != cached_mtime:
          # 重新加载
  ```
- **影响**: 中 — 并发内存访问

#### P2-RUNTIME-02: 子 agent 内存泄漏

- **文件**: `backend/packages/harness/ideer/subagents/executor.py:129-131`
- **问题**: `_background_tasks` 全局字典无 TTL 清理，任务完成后永久保留。
- **改进方案**:
  ```python
  _MAX_TASK_AGE_SECONDS = 3600

  def _evict_stale_tasks() -> None:
      now = time.time()
      with _background_tasks_lock:
          stale = [tid for tid, r in _background_tasks.items()
                   if r.completed_at and now - r.completed_at > _MAX_TASK_AGE_SECONDS]
          for tid in stale:
              del _background_tasks[tid]

  # 在 get_background_task_result 入口调用
  ```
- **影响**: 中 — 长期运行服务的内存稳定性

#### P2-RUNTIME-03: Claude 同步重试阻塞

- **文件**: `backend/packages/harness/ideer/models/claude_provider.py:296-319`
- **问题**: 同步 `_generate` 的 `time.sleep()` 阻塞线程池 worker，最多 14 秒。
- **改进方案**: 文档化行为，考虑在高负载场景使用异步路径。
- **影响**: 低 — 可接受的同步 API 行为

#### P2-RUNTIME-04: MCP 缓存懒初始化竞态

- **文件**: `backend/packages/harness/ideer/mcp/cache.py:107-128`
- **问题**: `asyncio.get_event_loop()` 已弃用，多线程并发初始化可能竞态。
- **改进方案**:
  ```python
  # 使用 threading.Lock 保护初始化路径
  _init_lock = threading.Lock()
  def get_cached_mcp_tools():
      with _init_lock:
          if not _cache_initialized:
              # 初始化逻辑
  ```
- **影响**: 低 — 启动时单次调用

#### P2-RUNTIME-05: 摘要忙等待

- **文件**: `backend/packages/harness/ideer/agents/middlewares/summarization_middleware.py`
- **问题**: `_processing=True` 时 `timer(0)` 重调度导致 CPU 忙等待。
- **改进方案**:
  ```python
  # 当 processing 时使用短延迟而非 0
  delay = 0 if not self._processing else 0.1
  self._schedule_timer(delay)
  ```
- **影响**: 低 — CPU 优化

#### P2-RUNTIME-06: ClarificationMiddleware 多实例

- **文件**: `backend/packages/harness/ideer/agents/factory.py:289-297`
- **问题**: 置底逻辑仅处理第一个 ClarificationMiddleware 实例。
- **改进方案**:
  ```python
  # 循环查找并移动所有实例
  while True:
      idx = next((i for i, m in enumerate(middlewares) if isinstance(m, ClarificationMiddleware)), None)
      if idx is None:
          break
      middlewares.append(middlewares.pop(idx))
  ```
- **影响**: 低 — 防御性编程

#### P2-RUNTIME-07: 子 agent 沙箱共享

- **文件**: `backend/packages/harness/ideer/subagents/executor.py:440-447`
- **问题**: 子 agent 继承父级沙箱，无独立隔离。
- **改进方案**: 文档化设计决策。如需隔离，为每个子 agent 创建独立沙箱。
- **影响**: 低 — 设计决策

#### P2-RUNTIME-08: 内存队列跨用户干扰

- **文件**: `backend/packages/harness/ideer/agents/memory/queue.py:36-42`
- **问题**: 全局单例定时器导致跨用户防抖重置。
- **改进方案**: 已在 P1 中通过 per-key timer 部分缓解。完整方案需将 `_timer` 改为 `_timers: dict[str, threading.Timer]`。
- **影响**: 已部分修复

---

### P2 测试覆盖

#### P2-TEST-01: tools 路由零测试

- **文件**: `backend/app/gateway/routers/tools.py`
- **问题**: 5 个端点（含代码执行）无任何测试。
- **改进方案**:
  ```python
  # 创建 backend/tests/test_tools_router.py
  # 覆盖: list_tools, list_groups, get_tool_detail, test_tool (RBAC), update_config (RBAC)
  ```
- **影响**: 高 — 安全关键路由无测试

#### P2-TEST-02: admin 路由零测试

- **文件**: `backend/app/gateway/routers/admin.py`
- **问题**: RBAC 关键的管理端路由无测试。
- **改进方案**:
  ```python
  # 创建 backend/tests/test_admin_router.py
  # 覆盖: RBAC 角色检查, 用户 CRUD, 部门管理, 角色分配, 最后管理员保护
  ```
- **影响**: 高 — RBAC 安全无测试

#### P2-TEST-03: agents 路由零测试

- **文件**: `backend/app/gateway/routers/agents.py`
- **问题**: agents 路由无测试。
- **改进方案**: 创建 `test_agents_router.py` 覆盖 agent 管理端点。
- **影响**: 中

#### P2-TEST-04: workflow 路由无 RBAC 测试

- **文件**: `backend/app/gateway/routers/workflows.py`
- **问题**: 现有测试不验证 RBAC 执行（viewer/user 角色访问）。
- **改进方案**:
  ```python
  # 添加角色拒绝测试
  def test_viewer_cannot_run_workflow():
      _set_user(role="viewer")
      response = client.post("/api/workflows/test/run", ...)
      assert response.status_code == 403
  ```
- **影响**: 中

#### P2-TEST-05: asyncio.sleep monkey-patch

- **文件**: `backend/tests/test_workflow_steps.py:436-484`
- **问题**: 全局 monkey-patch `asyncio.sleep`，异常时未恢复。
- **改进方案**:
  ```python
  # 使用上下文管理器替代手动 patch
  with patch("asyncio.sleep", new_callable=AsyncMock):
      ...
  ```
- **影响**: 低 — 测试稳定性

#### P2-TEST-06: doc_reader 缺 async 标记

- **文件**: `backend/tests/test_doc_reader.py`
- **问题**: 异步测试缺少 `pytestmark = pytest.mark.asyncio`。
- **改进方案**: 在模块顶部添加 `pytestmark = pytest.mark.asyncio`。
- **影响**: 低 — 测试可发现性

---

### P2 API 网关

#### P2-API-01: 装饰器顺序不一致

- **文件**: `backend/app/gateway/routers/tools.py:98-99`
- **问题**: `@require_role` 在 `@router.post` 下方，与 admin.py 相反。
- **改进方案**: 统一为 `@router.*` 在上、`@require_role` 在下（或反之），全文档一致。
- **影响**: 低 — 可维护性

#### P2-API-02: agents.py 注释误导

- **文件**: `backend/app/gateway/routers/agents.py:236-237`
- **问题**: 注释说 "Default to 'public'" 但代码实际默认 `'private'`。
- **改进方案**: 修正注释为 "Default to 'private'"。
- **影响**: 低 — 文档准确性

#### P2-API-03: run_workflow 角色枚举脆弱

- **文件**: `backend/app/gateway/routers/workflows.py:154`
- **问题**: 显式枚举 `USER, DEPARTMENT_ADMIN, SUPER_ADMIN`，新增角色时易遗漏。
- **改进方案**: 考虑使用 `@require_role(*[r for r in UserRole if r != UserRole.VIEWER])` 或文档化设计。
- **影响**: 低

#### P2-API-04: skills.py 错误泄露

- **文件**: `backend/app/gateway/routers/skills.py`
- **问题**: 已在 P0 中修复 10 处 `str(e)` 泄露。
- **影响**: 已修复

#### P2-API-05: workflow YAML 内容暴露

- **文件**: `backend/app/gateway/routers/workflows.py`
- **问题**: `list_workflows` 和 `get_workflow` 无 RBAC，任何认证用户可查看 YAML 内容。
- **改进方案**: 对非管理员用户隐藏敏感配置字段，或添加角色检查。
- **影响**: 中 — 信息泄露

---

### P2 构建与依赖

#### P2-BUILD-01: duckdb/markitdown 主依赖

- **文件**: `backend/packages/harness/pyproject.toml:31-37`
- **问题**: `duckdb` 和 `markitdown` 作为主依赖，增加安装体积。
- **改进方案**:
  ```toml
  [project.optional-dependencies]
  data = ["duckdb>=1.4.4"]
  docs = ["markitdown[all,xlsx]>=0.0.1a2"]
  ```
- **影响**: 低 — 安装优化

#### P2-BUILD-02: ruff known-first-party

- **文件**: `backend/ruff.toml:9`
- **问题**: `known-first-party` 缺少 `packages`，测试导入被误分类。
- **改进方案**: 添加 `"packages"` 到列表。
- **影响**: 低 — lint 准确性

#### P2-BUILD-03: 测试导入路径非标准

- **文件**: `backend/tests/` 多个文件
- **问题**: 测试使用 `from packages.harness.ideer...` 而非 `from ideer...`。
- **改进方案**: 统一为 `from ideer...` 导入路径。
- **影响**: 低 — 一致性

#### P2-BUILD-04: postgres:// URI 未处理

- **文件**: `backend/packages/harness/ideer/config/database_config.py:96`
- **问题**: `postgres://` 短前缀不转换为异步驱动。
- **改进方案**:
  ```python
  if url.startswith("postgres://") and not url.startswith("postgresql+"):
      url = url.replace("postgres://", "postgresql+asyncpg://", 1)
  ```
- **影响**: 低 — 兼容性

#### P2-BUILD-05: JsonlRunEventStore 多进程警告

- **文件**: `backend/packages/harness/ideer/runtime/events/store/jsonl.py:30`
- **问题**: 文档标注单进程但无显式警告。
- **改进方案**: 添加启动时日志警告。
- **影响**: 低

#### P2-BUILD-06: ExtensionsConfig 静默空字符串

- **文件**: `backend/packages/harness/ideer/config/extensions_config.py:167`
- **问题**: 未解析的环境变量静默转为空字符串。
- **改进方案**: 添加 `logger.warning` 当环境变量未找到时。
- **影响**: 低

---

## P3 — 低优先级

| # | 文件 | 问题 | 改进方案 |
|---|------|------|----------|
| 1 | `workflows/schema.py:20` | StepType.RETRY 未文档化 | 更新 README 或移除枚举值 |
| 2 | `workflows/schema.py:26` | RetryPolicy 默认 max=3 可能误导 | 文档化默认行为 |
| 3 | `workflows/store.py:258-274` | `_json_safe` 双重序列化 | 改用类型检查替代 try/except |
| 4 | `workflows/state.py:56-62` | 步骤输出跨步骤可见 | 文档化或添加输出过滤 |
| 5 | `routers/workflows.py:81` | YAML 解析错误消息泄露 | 保持现状（YAML 错误通常安全） |
| 6 | `routers/workflows.py:49-55` | 分页响应格式不一致 | 添加 `limit`/`offset` 到响应 |
| 7 | `routers/workflows.py:55` | 分页上限 500 vs 200 不一致 | 统一为 200 |
| 8 | `routers/tools.py:29-60` | `list_tools` 无分页 | 添加 limit/offset |
| 9 | `persistence/json_compat.py:168` | JSON 路径注入防护 | 当前正则已足够，添加注释 |
| 10 | `runtime/runs/manager.py:497` | 重启后孤儿运行检测 | 确保 reconcile 在新运行前执行 |
| 11 | `runtime/events/store/db.py:96` | advisory lock 哈希碰撞 | 使用双键 advisory lock |
| 12 | `config/extensions_config.py:167` | 环境变量静默空值 | 添加 warning 日志 |
| 13 | `agents/middlewares/loop_detection_middleware.py:160` | MD5 截断碰撞 | 改用 SHA-256 |
| 14 | `agents/middlewares/safety_finish_reason_middleware.py:108` | 宽异常捕获 | 缩窄为预期异常类型 |
| 15 | `agents/middlewares/dynamic_context_middleware.py:104-119` | 内存双加载 | 缓存单次调用 |
| 16 | `agents/middlewares/token_usage_middleware.py:270-358` | O(n) 反向遍历 | 索引 AIMessages by tool_call_id |
| 17 | `agents/middlewares/clarification_middleware.py:153-156` | goto=END 硬编码 | 使用可配置目标 |
| 18 | `subagents/executor.py:680-722` | 中间 RUNNING 状态可观测 | 初始化为 PENDING |
| 19 | `tools/registry.py:37-39` | 工具注册无去重冲突 | 添加优先级或报错机制 |
| 20 | `tools/registry.py:51-68` | config_schema 仅验证 key | 添加值类型验证 |
| 21 | `skills/validation.py:15` | `requires-internet` 未测试 | 添加测试用例 |
| 22 | `skills/types.py:44-72` | 路径穿越拒绝未测试 | 添加 `..` 路径测试 |
| 23 | `tests/test_workflow_executor.py:309-334` | 测试名称与实际不符 | 重命名测试 |
| 24 | `tests/test_data_analyzer.py:1-92` | 非标准导入路径 | 统一为 `from ideer...` |
| 25 | `ruff.toml:9` | known-first-party 缺少 `packages` | 添加到列表 |
| 26 | `persistence/engine.py:125` | PG pool 缺少 pool_recycle | 添加配置 |
| 27 | `persistence/thread_meta/sql.py:159` | UPDATE 无 user_id WHERE | 添加条件 |
| 28 | `config/app_config.py:356` | 全局配置无锁 | 添加 threading.Lock |
| 29 | `agents/middlewares/tool_error_handling_middleware.py` | 中间件顺序 | 已验证正确 ✅ |

---

## 已完成项

### P0 — 严重/高危安全漏洞 (已修复)

| # | 问题 | 文件 | 修复内容 |
|---|------|------|----------|
| 1 | **CRITICAL** code_interpreter RCE | `code_interpreter/tools.py` | 改用 `sandbox.execute_command()` |
| 2 | **CRITICAL** code_interpreter MCP RCE | `code_interpreter/mcp_server.py` | 添加 resource limits + 移除危险环境变量 |
| 3 | **HIGH** doc_reader 任意文件读取 | `doc_reader/tools.py` | 添加 `_validate_path()` 路径限制 |
| 4 | **HIGH** doc_reader MCP 任意文件读取 | `doc_reader/mcp_server.py` | 同上 |
| 5 | **HIGH** data_analyzer 任意文件读取 | `data_analyzer/tools.py` | 同上 |
| 6 | **HIGH** data_analyzer MCP 任意文件读取 | `data_analyzer/mcp_server.py` | 同上 |
| 7 | **HIGH** tools.py 堆栈泄露 | `routers/tools.py` | `str(e)` → "Internal server error" |
| 8 | **HIGH** skills.py 错误泄露 (10处) | `routers/skills.py` | 统一替换 |
| 9 | **HIGH** admin.py TOCTOU | `routers/admin.py` | SELECT FOR UPDATE + 审计日志 |
| 10 | **HIGH** disable_user TOCTOU | `routers/admin.py` | 同上 |

### P1 — 高危功能修复 (已修复)

| # | 问题 | 文件 | 修复内容 |
|---|------|------|----------|
| 1 | 模板注入 | `workflows/template.py` | `except Exception` 替换 |
| 2 | YAML 大小限制 | `workflows/parser.py` | 100KB 上限 |
| 3 | save_review_result TOCTOU | `workflows/store.py` | 原子 UPDATE |
| 4 | 人工审核轮询 | `workflows/human_step.py` | 指数退避 2s→30s |
| 5 | 条件 goto 死代码 | `workflows/executor.py` | 实现跳转解析 |
| 6 | 认证绕过标志 | `authz.py` | 检测真实 Request 对象 |
| 7 | list_departments 信息泄露 | `routers/admin.py` | 非管理员隐藏 member_count |
| 8 | MCP 会话池竞态 | `mcp/session_pool.py` | 创建后二次检查 |
| 9 | 循环检测跨线程误报 | `loop_detection_middleware.py` | 唯一匿名 thread_id |
| 10 | 内部令牌警告 | `internal_auth.py` | 添加 WARNING 日志 |
| 11 | routers/__init__.py 缺失 | `routers/__init__.py` | 补全导入 |

### P2 — 中等优先级 (已修复)

| # | 问题 | 文件 | 修复内容 |
|---|------|------|----------|
| 1 | P2-AUTH-01 SQLite 首次用户竞态 | `authz.py` | IntegrityError 后重新检查 admin_count |
| 2 | P2-AUTH-02 JWT 密钥生产环境强制 | `auth/config.py` | 生产环境要求显式设置 AUTH_JWT_SECRET |
| 3 | P2-AUTH-03 内部令牌多 Worker 不一致 | `internal_auth.py` | 从 JWT_SECRET 确定性派生，改为懒加载 |
| 4 | P2-AUTH-05 DB 角色未校验枚举 | `authz.py` | get_current_rbac_user 中添加角色验证 |
| 5 | P2-PERSIST-01 SQL 注入风险 | `persistence/engine.py` | 转义嵌入的双引号 |
| 6 | P2-PERSIST-02 create_all 与 Alembic 冲突 | `persistence/engine.py` | 检测 alembic_version 表，有则跳过 |
| 7 | P2-PERSIST-03 thread_meta 更新丢失 | `thread_meta/sql.py` | update_metadata 使用 SELECT FOR UPDATE |
| 8 | P2-PERSIST-04 thread_meta 所有权 TOCTOU | `thread_meta/sql.py` | 合并所有权检查到 UPDATE 语句 |
| 9 | P2-PERSIST-05 PG 连接池配置缺失 | `persistence/engine.py` | 添加 pool_recycle=1800, pool_timeout=30 |
| 10 | P2-WF-01 并行步骤状态损坏 | `parallel_step.py` | 子步骤 ID 加父步骤前缀 |
| 11 | P2-WF-02 循环步骤状态覆盖 | `loop_step.py` | 每次迭代使用命名空间化的 key |
| 12 | P2-WF-04 模板表达式长度限制 | `template.py` | 添加 1000 字符上限 |
| 13 | P2-WF-06 重试退避无 Jitter | `executor.py` | 添加 random.uniform(0, 1) 抖动 |
| 14 | P2-TOOL-03 seccomp=unconfined | `aio_sandbox/local_backend.py` | 使用 Docker 默认 seccomp profile |
| 15 | P2-RUNTIME-01 内存存储 TOCTOU | `agents/memory/storage.py` | mtime 检查移入锁内 |
| 16 | P2-RUNTIME-02 子 agent 内存泄漏 | `subagents/executor.py` | 添加 1 小时 TTL 淘汰机制 |
| 17 | P2-RUNTIME-04 MCP 缓存懒初始化竞态 | `mcp/cache.py` | 添加 threading.Lock 保护 |
| 18 | P2-RUNTIME-06 ClarificationMiddleware 多实例 | `agents/factory.py` | 循环查找并移动所有实例 |
| 19 | P2-API-05 workflow YAML 内容暴露 | `routers/workflows.py` | 非管理员隐藏 yaml_content |
| 20 | P2-BUILD-02 ruff known-first-party | `ruff.toml` | 添加 "packages" |
| 21 | P2-BUILD-04 postgres:// URI 未处理 | `config/database_config.py` | 处理 postgres:// 短前缀 |
| 22 | P2-BUILD-05 JsonlRunEventStore 多进程警告 | `runtime/events/store/jsonl.py` | 添加启动时日志警告 |
| 23 | P2-BUILD-06 ExtensionsConfig 静默空字符串 | `config/extensions_config.py` | 添加 warning 日志 |

---

## 统计

| 类别 | 总数 | 已修复 | 待修复 |
|------|------|--------|--------|
| P0 (严重) | 2 | 2 | 0 |
| P0 (高危) | 8 | 8 | 0 |
| P1 (高危) | 11 | 11 | 0 |
| P2 (中等) | 45 | 28 | 17 |
| P3 (低危) | 29 | 0 | 29 |
| **合计** | **95** | **49** | **46** |
