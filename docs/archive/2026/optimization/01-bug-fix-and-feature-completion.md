# Bug 修复与功能完善方案

## 概述

本文档列出 `offline_feature` 分支中需要在 PR 合并前修复的所有 Bug 和功能缺陷。这些问题来源于代码审查、`docs/bug-list.md`（37 项遗留问题）以及本轮新发现的问题。

> 已有 Bug 追踪表：参见 `docs/bug-list.md`（103 项，其中 30 项已修复，37 项遗留）

---

## 一、后端 Bug 修复

### CRITICAL（必须在 PR 前修复）

<a id="bug-c01"></a>
#### C01: 工作流 goto 跳转实际不生效

- **文件**: `backend/packages/harness/ideer/workflows/executor.py`
- **问题**: goto 机制标记中间步骤为 skipped，但 `for` 循环的 `current_idx` 未改变，循环仍从 `current_idx + 1` 继续执行。对于向前跳转超过 1 步的情况，目标步骤永远不会被执行。
- **修复方案**: 改用 `while` 循环 + 手动索引控制，在 goto 时直接设置 `current_idx = target_idx`。
- **影响**: 所有使用 goto 的工作流条件分支。

```python
# 修复前（伪代码）
for idx, step in enumerate(steps):
    if goto:
        mark_skipped(intermediate_steps)
        # BUG: idx 仍然递增，不会跳到 target

# 修复后（伪代码）
idx = 0
while idx < len(steps):
    step = steps[idx]
    result = await execute(step)
    if result is goto:
        target_idx = find_step(result.target)
        mark_skipped(steps[idx+1:target_idx])
        idx = target_idx
        continue
    idx += 1
```

<a id="bug-c02"></a>
#### C02: Auth bypass 检查逻辑缺陷

- **文件**: `backend/app/gateway/authz.py`（`require_auth` 和 `require_permission`）
- **问题**: 当 `Request` 对象带有 `_ideer_test_bypass_auth=True` 时，代码记录 SECURITY 日志后仍然执行 bypass（因为后续的 `getattr` 检查返回 True）。如果攻击者能注入此属性，认证完全绕过。
- **修复方案**: 对真实 `Request` 对象，记录日志后应 `return None`（拒绝），而非 fall through。

```python
# 修复后
if isinstance(request, Request) and getattr(request, "_ideer_test_bypass_auth", False):
    logger.error("SECURITY: test bypass on real Request — ignoring")
    return None  # 拒绝，不 fall through
```

### HIGH（本迭代必须修复）

<a id="bug-h01"></a>
#### H01: RBAC 数据库故障时权限升级

- **文件**: `backend/app/gateway/authz.py`（`_authenticate` 函数）
- **问题**: RBAC 数据库查询失败时，`except Exception: pass` 静默授予 `_ALL_PERMISSIONS`。数据库宕机 = 所有用户获得完全权限。
- **修复方案**: 数据库故障时返回最小权限（仅 `threads:read`），并记录 ERROR 日志。

<a id="bug-h02"></a>
#### H02: MCP 缓存初始化竞态条件

- **文件**: `backend/packages/harness/ideer/mcp/cache.py`
- **问题**: `asyncio.Lock` 在不同事件循环间不共享。多线程调用时两个线程可能同时执行初始化。`asyncio.get_event_loop()` 在 Python 3.10+ 已弃用。
- **修复方案**: 使用 `threading.Lock` 保护初始化，或使用 `asyncio.Runner`（Python 3.11+）。

<a id="bug-h03"></a>
#### H03: 工作流表达式运算符子串匹配

- **文件**: `backend/packages/harness/ideer/workflows/executor.py`（`_evaluate_expression`）
- **问题**: `if op_str in rendered` 是子串匹配。`">="` 包含 `">"`，导致运算符误判。虽然代码按长度降序检查，但不覆盖所有边界情况。
- **修复方案**: 使用正则表达式做词边界匹配，或改用 tokenizer。

<a id="bug-h04"></a>
#### H04: get_current_rbac_user 角色修正未持久化

- **文件**: `backend/app/gateway/authz.py`
- **问题**: 检测到无效角色时设置 `rbac_user.role = UserRole.VIEWER` 但未 `session.commit()`，下次请求用户仍持有无效角色。
- **修复方案**: 添加 `await session.commit()` 持久化修正。

<a id="bug-h05"></a>
#### H05: MCP session pool 持锁执行 I/O

- **文件**: `backend/packages/harness/ideer/mcp/session_pool.py`
- **问题**: 竞态检查时在持有 `self._lock` 的情况下 `await cm.__aexit__()`，阻塞所有其他 session 操作。
- **修复方案**: 释放锁后再关闭多余 session。

<a id="bug-h06"></a>
#### H06: channels 路由缺少授权检查

- **文件**: `backend/app/gateway/routers/channels.py`
- **问题**: `get_channels_status` 和 `restart_channel` 无 `@require_permission` 装饰器，任何已认证用户可重启 channel。
- **修复方案**: 添加 `@require_role("department_admin")` 或更高权限。

<a id="bug-h07"></a>
#### H07: ModelConfig 字段定义矛盾

- **文件**: `backend/packages/harness/ideer/config/model_config.py`
- **问题**: `Field(..., default_factory=lambda: None)` 中 `...` 标记为必填，`default_factory` 提供默认值。Pydantic v2 中 `...` 优先，导致字段变为必填。
- **修复方案**: 移除 `...`，改为 `Field(default=None)`。

<a id="bug-h08"></a>
#### H08: 工作流创建竞态条件

- **文件**: `backend/app/gateway/routers/workflows.py`
- **问题**: `create_workflow` 先检查存在性再保存，无事务保护。并发请求可同时通过检查。
- **修复方案**: 使用数据库唯一约束 + `INSERT ... ON CONFLICT` 或 try/except IntegrityError。

### MEDIUM（建议修复）

| 编号 | 文件 | 问题 | 修复方案 |
|------|------|------|----------|
| M01 | `mcp/session_pool.py` | `reset_session_pool()` 未关闭已有 session | 关闭后再置 None |
| M02 | `mcp/cache.py` | `reset_mcp_tools_cache()` 导入顺序问题 | 统一模块级导入 |
| M03 | `workflows/executor.py` | 条件步骤 retry 禁用过于保守 | 仅含内联子步骤的分支禁用 |
| M04 | `runtime/events/store/jsonl.py` | `_ensure_seq_loaded` 全量扫描 | 改为读取最后一条记录 |
| M05 | `agents/memory/storage.py` | `load()` TOCTOU 窗口 | 在锁内完成 mtime 检查 |
| M06 | `routers/auth.py` | `_get_client_ip` 返回 "unknown" 共享限流桶 | 返回 `None`，跳过限流 |
| M07 | `routers/agents.py` | `_load_agent_meta` 吞掉所有异常 | 区分 JSON 错误和其他异常 |
| M08 | `routers/agents.py` | f-string 日志 | 改为 %-style |
| M09 | `config/extensions_config.py` | McpOAuthConfig.enabled 默认 True | 改为默认 False |

---

## 二、前端 Bug 修复

### CRITICAL / HIGH

<a id="bug-f01"></a>
#### F01: Admin 页面无角色校验

- **文件**: `frontend/src/app/workspace/admin/page.tsx` 及子页面
- **问题**: `/workspace/admin/*` 页面仅检查登录状态，不检查角色。任何已认证用户（含 viewer）可访问用户管理、部门管理。
- **修复方案**: 在 admin layout 中添加角色检查，非 admin 角色重定向到 `/workspace`。

<a id="bug-f02"></a>
#### F02: 多个 API 模块缺少 response.ok 检查

- **文件**:
  - `frontend/src/core/models/api.ts` — `loadModels()`
  - `frontend/src/core/skills/api.ts` — `loadSkills()`
  - `frontend/src/core/mcp/api.ts` — `updateMCPConfig()`
  - `frontend/src/core/threads/hooks.ts` — `useThreadHistory` 中的 `loadMessages`
- **问题**: 直接 `.json()` 不检查 HTTP 状态码，错误响应被当作正常数据解析。
- **修复方案**: 统一使用 `extractError()` 模式。

<a id="bug-f03"></a>
#### F03: Skill 保存功能未实现

- **文件**: `frontend/src/components/workspace/settings/skill-settings-page.tsx`
- **问题**: `handleSaveSkill` 仅 `console.log`，用户编辑 Skill 后点保存，内容丢失。
- **修复方案**: 实现 `PUT /api/skills/{name}` 调用，参考 `admin/api.ts` 中的 API 模式。

<a id="bug-f04"></a>
#### F04: Memory API 代理未转发认证

- **文件**: `frontend/src/app/api/memory/route.ts` 和 `frontend/src/app/api/memory/[...path]/route.ts`
- **问题**: Next.js API route 代理请求到后端时未转发 `access_token` cookie。
- **修复方案**: 从请求中提取 cookie 并附加到代理请求头。

### MEDIUM

| 编号 | 文件 | 问题 | 修复方案 |
|------|------|------|----------|
| F05 | `core/api/api-client.ts` | console.log 泄露 API URL | 移除或降级为 debug |
| F06 | `core/config/index.ts` | console.log 泄露环境变量 | 移除 |
| F07 | Admin 页面全部 | 硬编码中文，未使用 i18n | 改用 `useI18n()` |
| F08 | `settings/skill-editor.tsx` | `dangerouslySetInnerHTML` XSS 风险 | 使用 DOMPurify 或 markdown-it |
| F09 | `core/workflows/validate.ts` | YAML 验证仅检查字符串包含 | 使用 `yaml` 库解析验证 |
| F10 | `ai-elements/model-selector.tsx` | 硬编码外部 URL `models.dev` | 改为本地资源或可配置 |
| F11 | `package.json` | 包含 `nuxt-og-image`（Nuxt 依赖） | 移除 |
| F12 | `core/tasks/context.tsx` | `useUpdateSubtask` stale closure | 修复状态更新逻辑 |
| F13 | `core/threads/hooks.ts` | `useDeleteThread` 无回滚机制 | 添加事务性删除 |

### LOW

| 编号 | 文件 | 问题 |
|------|------|------|
| F14 | `components/workspace/todo-list.tsx` | 硬编码 "To-dos" 文本 |
| F15 | `hooks/use-global-shortcuts.ts` | useEffect 依赖可变数组 |
| F16 | `components/workspace/input-box.tsx` | useEffect 缺少依赖 |
| F17 | Admin 页面多个 | 缺少 `aria-label` |
| F18 | `(auth)/login/page.tsx` | UI 标签 "Email" 与 API 字段 "username" 不匹配 |

---

## 三、已有 Bug 清单中的遗留问题

以下问题来自 `docs/bug-list.md` 第四节"后续处理的问题"，按优先级筛选需要在本轮修复的：

### 建议本轮修复（HIGH，影响功能正确性）

| 原编号 | 问题 | 修复方案 |
|--------|------|----------|
| #25 | ToolRegistry.update_config 无实际效果 | 统一工具实例化路径 |
| #16 | 重试机制覆盖历史步骤结果 | 保存步骤原始结果，重试时覆盖 |
| #33 | submit_review TOCTOU | 使用数据库事务合并读写 |
| #73 | submit_review 不验证执行器存活性 | 添加心跳检查或超时机制 |
| #89 | 后台任务孤立运行 | 添加任务恢复机制 |

### 建议本轮修复（MEDIUM，影响数据一致性）

| 原编号 | 问题 | 修复方案 |
|--------|------|----------|
| #48 | save_run_state 无重试 | 添加指数退避重试 |
| #63 | save_workflow 并发竞态 | 使用 upsert |
| #67 | save_run_state 无事务隔离 | 使用乐观锁（version 字段） |
| #84 | save_run_state 未持久化 review_result | 在 human_review 步骤保存 |
| #91 | 运行记录不快照 YAML | 创建运行时保存 YAML 快照 |

---

## 四、修复顺序建议

### 第 1 周：CRITICAL Bug
1. C01: 工作流 goto 跳转
2. C02: Auth bypass 逻辑
3. H01: RBAC 权限升级
4. F01: Admin 页面角色校验

### 第 2 周：HIGH Bug
1. H02-H08: 后端 HIGH 级别 Bug
2. F02-F04: 前端 HIGH 级别 Bug

### 第 3 周：MEDIUM Bug + 遗留问题
1. M01-M09: 后端 MEDIUM Bug
2. F05-F13: 前端 MEDIUM Bug
3. 已有 Bug 清单中的 HIGH/MEDIUM 遗留问题

---

## 五、验收标准

- [ ] 所有 CRITICAL Bug 修复并通过测试
- [ ] 所有 HIGH Bug 修复并通过测试
- [ ] 前端 Admin 页面角色校验生效
- [ ] 前端 API 模块统一错误处理
- [ ] Skill 保存功能可用
- [ ] 已有 Bug 清单中 HIGH 遗留问题清零
- [ ] 所有修复有对应的回归测试
