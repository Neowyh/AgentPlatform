# 验证流程缺口分析报告

> **日期**: 2026-06-12
> **触发原因**: Workflow 管理页面出现两个未被 validation-orchestrator 捕获的问题
> **分析范围**: 全项目一致性扫描，覆盖 ORM/DB、前后端类型、RBAC、配置、路由、错误处理

---

## 目录

1. [背景：两个漏网问题](#1-背景两个漏网问题)
2. [缺口全景图](#2-缺口全景图)
3. [类别 1：ORM 模型 vs 数据库 Schema](#3-类别-1orm-模型-vs-数据库-schema)
4. [类别 2：前端类型 vs 后端 API 响应](#4-类别-2前端类型-vs-后端-api-响应)
5. [类别 3：RBAC 角色定义 vs 实际权限执行](#5-类别-3rbac-角色定义-vs-实际权限执行)
6. [类别 4：配置文件 vs 代码实际使用](#6-类别-4配置文件-vs-代码实际使用)
7. [类别 5：公开路径白名单 vs 实际端点](#7-类别-5公开路径白名单-vs-实际端点)
8. [类别 6：错误处理模式不一致](#8-类别-6错误处理模式不一致)
9. [根因分析](#9-根因分析)
10. [修复优先级与建议](#10-修复优先级与建议)

---

## 1. 背景：两个漏网问题

### 问题 A：数据库 Schema 不匹配

- **现象**: Workflow 管理页面一直显示 Loading
- **根因**: `workflow_runs` 表缺少 `loop_vars` 列，ORM 查询报 `OperationalError: no such column`
- **为什么没被捕获**:
  - backend-validator Phase 0 检查迁移文件语法，但不连接实际数据库比对 schema
  - qa-tester 的 DB 迁移验证在临时 SQLite 上执行，不验证生产数据库
  - `alembic_version` 表不存在，迁移从未被执行

### 问题 B：i18n 硬编码英文

- **现象**: Workflow 页面显示英文，与其他页面中文不一致
- **根因**: ~55 个硬编码英文字符串未接入项目的 `useI18n()` 翻译系统
- **为什么没被捕获**:
  - frontend-validator 的 i18n 检查只做 key parity（en-US vs zh-CN key 是否一致）
  - 硬编码中文检测只查中文字符串 `[一-鿿]`，不查硬编码英文
  - 验证只覆盖变更文件，workflow 组件从未被修改过

---

## 2. 缺口全景图

共发现 **6 类 23 个缺口**，按风险等级分布：

| 风险等级 | 数量 | 说明 |
|----------|------|------|
| 🔴 严重 (CRITICAL) | 2 | 功能完全不可用 |
| 🔴 高 (HIGH) | 4 | 安全漏洞或数据完整性问题 |
| 🟡 中 (MEDIUM) | 11 | 功能异常或用户体验问题 |
| 🟢 低 (LOW) | 6 | 边缘场景或维护风险 |

---

## 3. 类别 1：ORM 模型 vs 数据库 Schema

> 与 loop_vars 同类的"定义存在但运行时不存在"问题

### 缺口 1.1 🔴 高：UserModel.role 无 server_default 导致 fail-open

- **位置**: `backend/packages/harness/ideer/persistence/models/user.py:47` / 迁移 `16147afec43b:41` / `backend/app/gateway/authz.py:180`
- **问题**: 迁移中 `role` 列定义为 `nullable=True` 且无 `server_default`。ORM 的 Python-side `default=UserRole.USER` 仅在通过 ORM 创建实例时生效。若通过原始 SQL 插入或绕过 ORM，数据库中 `role` 为 NULL
- **影响**: `authz.py:180` 的 `rbac_user.role == UserRole.VIEWER` 判断在 role 为 NULL 时返回 False → 用户获得全部权限（fail-open）
- **验证流程缺口**: backend-validator 不检查迁移的 `server_default` 是否与 ORM default 一致

### 缺口 1.2 🟡 中：alembic_version 表不存在

- **位置**: `.ideer/data/ideer.db`
- **问题**: 数据库中没有 `alembic_version` 表，说明所有 Alembic 迁移从未被执行。迁移文件只是"存在"但未被标记为已应用
- **影响**: 下次 ORM 字段变更时会再次出现 loop_vars 同类问题。当前 4 个迁移文件（`16147afec43b`, `d7e0060b1ebc`, `f3a2b1c4d5e6`, `a1b2c3d4e5f6`）均未被跟踪
- **验证流程缺口**: qa-tester 在临时 SQLite 上验证迁移脚本能否执行，不验证实际数据库的迁移状态

---

## 4. 类别 2：前端类型 vs 后端 API 响应

> 与 i18n 同类的"定义不一致"模式 — 前端 TypeScript 类型与后端 Pydantic 响应模型字段不匹配

### 缺口 2.1 🔴 严重：Agent export HTTP 方法不匹配

- **前端**: `frontend/src/core/agents/api.ts:117` — 使用 `fetch()`（默认 GET）
- **后端**: `backend/app/gateway/routers/agents.py:754` — 定义为 `@router.post("/agents/{name}/export")`
- **影响**: 前端 GET 请求收到 405 Method Not Allowed，Agent 导出功能**完全不可用**
- **验证流程缺口**: frontend-validator 不验证 HTTP 方法与后端路由定义的一致性

### 缺口 2.2 🔴 严重：Agent import 请求体格式不匹配

- **前端**: `frontend/src/core/agents/api.ts:125-140` — 发送 `FormData`（文件上传）
- **后端**: `backend/app/gateway/routers/agents.py:823-913` — 期望 `AgentImportRequest` JSON `{name, config, soul, visibility}`
- **影响**: 后端拒绝 FormData 请求，Agent 导入功能**完全不可用**
- **验证流程缺口**: 同上

### 缺口 2.3 🔴 高：MCP 配置类型严重不足

- **前端**: `frontend/src/core/mcp/types.ts` — `MCPServerConfig` 仅定义 `{enabled, description}` 共 2 个字段
- **后端**: `backend/app/gateway/routers/mcp.py:34-46` — `McpServerConfigResponse` 返回 `{enabled, type, command, args, env, url, headers, oauth, description}` 共 9+ 个字段
- **影响**: 前端 MCP 编辑器无法显示 `command`, `args`, `env`, `url`, `headers`, `oauth` 等配置项，类型定义是"谎言"
- **验证流程缺口**: TypeScript 编译通过不代表类型与实际 API 匹配；无自动化类型-响应比对

### 缺口 2.4 🟡 中：Workflow create/update 响应缺少字段

- **前端**: `frontend/src/core/workflows/types.ts:48-55` — `WorkflowSummary` 期望 `{name, description, version, steps_count, inputs}`
- **后端**: `backend/app/gateway/routers/workflows.py:106,136` — create/update 仅返回 `{name, description, version}`
- **影响**: 新建或更新 workflow 后，前端拿到的对象缺少 `steps_count` 和 `inputs`，卡片渲染异常
- **验证流程缺口**: 同上

### 缺口 2.5 🟡 中：Agent 类型缺少 RBAC 字段

- **前端**: `frontend/src/core/agents/types.ts` — `Agent` 定义 `{name, description, model, tool_groups, skills, soul, read_only}`
- **后端**: `backend/app/gateway/routers/agents.py:65-78` — 额外返回 `visibility`, `owner_id`, `department_id`
- **影响**: 前端无法展示 RBAC 元数据，权限相关的 UI 功能缺失
- **验证流程缺口**: 同上

### 缺口 2.6 🟡 中：Tool 类型缺少 config 字段

- **前端**: `frontend/src/core/tools/types.ts` — `Tool` 定义不含 `config`
- **后端**: `backend/app/gateway/routers/tools.py:46-59` — 额外返回 `config`（当前配置字典）
- **影响**: 工具配置 UI 无法读取当前配置值，只能看到 `configurable` 布尔标记
- **验证流程缺口**: 同上

### 缺口 2.7 🟢 低：Upload 响应缺少 skipped_files

- **前端**: `frontend/src/core/uploads/api.ts` — `UploadResponse` 定义 `{success, files, message}`
- **后端**: `backend/app/gateway/routers/uploads.py:42-48` — 额外返回 `skipped_files: list[str]`
- **影响**: 用户不知道哪些不安全文件被跳过
- **验证流程缺口**: 同上

### 缺口 2.8 🟢 低：Memory Fact 缺少 sourceError

- **前端**: `frontend/src/core/memory/types.ts` — `MemoryFact` 无 `sourceError` 字段
- **后端**: `backend/app/gateway/routers/memory.py:44-53` — `Fact` 有 `sourceError: str | None`
- **影响**: 纠正上下文信息丢失
- **验证流程缺口**: 同上

### 缺口 2.9 🟢 低：Admin User 的 department_name 从不返回

- **前端**: `frontend/src/core/admin/types.ts` — `User` 有 `department_name?: string`
- **后端**: `backend/app/gateway/routers/admin.py:102-118` — 响应中无此字段
- **影响**: `department_name` 永远为 `undefined`，管理界面无法显示部门名称
- **验证流程缺口**: 同上

---

## 5. 类别 3：RBAC 角色定义 vs 实际权限执行

### 缺口 3.1 🔴 高：RBAC 装饰器覆盖率不足

- **位置**: `backend/app/gateway/auth_middleware.py:121` / 各 router 文件
- **问题**: `AuthMiddleware` 对所有已认证用户赋予 `_ALL_PERMISSIONS`，RBAC 检查仅在有 `@require_role` 装饰器的路由上生效
- **统计**: 18 个 router 中**只有 4 个**使用了 `@require_role`（admin, workflows, skills, tools）
- **未保护的 router**:
  - `channels.py` — 无任何权限装饰器
  - `mcp.py` — 无任何权限装饰器
  - `memory.py` — 无任何权限装饰器
  - `models.py` — 无任何权限装饰器（只读，风险较低）
  - `assistants_compat.py` — 无任何权限装饰器
- **影响**: VIEWER 用户可以修改 MCP 配置、清空记忆、管理 channel、修改 agent 配置
- **验证流程缺口**: qa-tester 的 multi-role 权限测试只在 `full` 级别运行，且主要测试 admin/user 边界，不测试 VIEWER 在未加装饰器 router 上的权限越界

### 缺口 3.2 🟡 中：两套角色系统映射不完整

- **Auth 层**: `frontend/src/core/auth/types.ts` — `system_role: "admin" | "user"`（仅 2 个值）
- **RBAC 层**: `backend/packages/harness/ideer/persistence/models/user.py:13-17` — `UserRole` 枚举有 4 个值：`VIEWER`, `USER`, `DEPARTMENT_ADMIN`, `SUPER_ADMIN`
- **影响**: 前端只知道 admin/user 两种角色，无法区分 DEPARTMENT_ADMIN 和 SUPER_ADMIN，也无法识别 VIEWER
- **验证流程缺口**: 无自动化检查验证两套角色系统的映射完整性

---

## 6. 类别 4：配置文件 vs 代码实际使用

### 缺口 4.1 🟡 中：config.yaml 中的 uploads 配置是死配置

- **位置**: `config.yaml:79-84` / `backend/packages/harness/ideer/config/app_config.py`
- **问题**: `config.yaml` 包含 `uploads` 配置块（`max_files`, `max_file_size`, `max_total_size`, `auto_convert_documents`, `pdf_converter`），但 `AppConfig` 类无 `uploads` 字段。Pydantic `extra="allow"` 静默接受但值从未被消费
- **影响**: 运维人员修改 uploads 配置不会产生任何效果，容易产生误解
- **验证流程缺口**: backend-validator 的 config 语义验证只做单向检查（代码引用的 key 是否存在于 config 中），不检查 config 中的 key 是否被代码消费

### 缺口 4.2 🟡 中：routers/__init__.py 的 __all__ 不完整

- **位置**: `backend/app/gateway/routers/__init__.py:1-3`
- **问题**: `__all__` 导出 12 个模块，但 `app.py` 实际导入了 18 个 router。缺少：`auth`, `channels`, `feedback`, `memory`, `runs`
- **影响**: 维护者查看 `__all__` 会得到不完整的 router 列表，可能遗漏某些 router
- **验证流程缺口**: 无自动化检查验证 `__all__` 与实际导入的一致性

### 缺口 4.3 🟢 低：config_version 无自动校验

- **位置**: `config.yaml` / `config.example.yaml`
- **问题**: `config_version: 10` 在两个文件中目前一致，但无自动化机制防止版本漂移
- **影响**: 版本不一致时只会产生启动警告，不会阻断
- **验证流程缺口**: qa-tester 的 config 验证不检查 config_version 一致性

---

## 7. 类别 5：公开路径白名单 vs 实际端点

### 缺口 5.1 🟡 中：OAuth 回调端点未在白名单中

- **位置**: `backend/app/gateway/auth_middleware.py:34-42` / `backend/app/gateway/routers/auth.py`
- **问题**: `/api/v1/auth/oauth/{provider}` 和 `/api/v1/auth/callback/{provider}` 不在 `_PUBLIC_EXACT_PATHS` 中。当前返回 501（未实现）
- **影响**: 启用 OAuth 时，AuthMiddleware 会以 401 拦截回调请求，OAuth 流程无法完成。这是一个**潜伏的未来破坏点**
- **验证流程缺口**: 无自动化检查验证"所有需要公开访问的端点是否都在白名单中"

---

## 8. 类别 6：错误处理模式不一致

### 缺口 6.1 🟡 中：前端错误解析策略不统一

- **位置**: 各 `api.ts` 文件
- **问题**: 前端存在 5 种不同的错误解析策略：
  1. `extractError()`（workflows, admin）— 解析 `detail` 为 string 或 `Array<{msg?, loc?}>`
  2. 内联 `as {detail?: string}`（agents, workflows create/update）— 假设 detail 总是 string
  3. `readMemoryResponse()`（memory）— 完整处理 string/array/object/primitive
  4. `readErrorDetail()`（uploads）— 假设 `error.detail` 是 string
  5. 无错误处理（skills `loadSkills`）— 不检查 `response.ok` 直接解析 JSON
- **影响**: 同一后端错误格式在不同页面表现不同，可能导致崩溃或显示乱码
- **验证流程缺口**: frontend-validator 不检查错误处理模式的一致性

### 缺口 6.2 🟡 中：AuthProvider.refreshUser 不使用自定义 fetch

- **位置**: `frontend/src/core/auth/AuthProvider.tsx:64`
- **问题**: 使用原生 `fetch("/api/v1/auth/me", { credentials: "include" })` 而非自定义 `fetcher`。自定义 fetcher 在 401 时自动跳转登录页
- **影响**: 会话过期时 `refreshUser()` 将 `user` 设为 `null` 而非跳转登录页，用户可能停留在无权限状态
- **验证流程缺口**: qa-tester 不测试会话过期后的前端行为

### 缺口 6.3 🟢 低：Agent API 禁用检测依赖硬编码字符串

- **位置**: `frontend/src/core/agents/api.ts:25-27`
- **问题**: `isAgentsApiDisabledDetail()` 检查后端错误消息是否包含子串 `"agents_api.enabled"`
- **影响**: 后端措辞变化会静默破坏前端检测，用户看到通用错误而非"API 已禁用"提示
- **验证流程缺口**: 无自动化检查验证前后端错误消息的耦合关系

---

## 9. 根因分析

| 根因 | 影响的缺口 | 说明 |
|------|-----------|------|
| **验证只看"变更文件"，不看"项目整体一致性"** | 1.x, 2.x, 3.x | 验证基于 git diff，未变更的文件不在检查范围内。workflow 组件从未被修改，所以 i18n 缺口从未被扫描 |
| **静态分析通过 ≠ 运行时正确** | 1.1, 2.1-2.3 | TypeScript 编译通过不代表类型与实际 API 匹配；Python lint 通过不代表迁移已执行 |
| **验证在隔离环境中运行** | 1.2 | qa-tester 在临时 DB 上验证迁移，不验证实际数据库的状态 |
| **RBAC 检查是 opt-in 而非 opt-out** | 3.1-3.2 | `@require_role` 是装饰器而非默认行为，遗漏 = 全开。应考虑改为 deny-by-default |
| **配置验证是单向的** | 4.1 | 只查"代码用了 config 中的 key"，不查"config 中的 key 是否被代码用到" |
| **前端类型是手写的** | 2.x | 手写 TypeScript 类型必然与后端 Pydantic 模型漂移，应考虑从 OpenAPI schema 自动生成 |
| **错误处理无统一规范** | 6.1 | 每个 API 模块自行决定如何解析错误，无强制的统一策略 |

---

## 10. 修复优先级与建议

### P0 — 立即修复

| 缺口 | 修复方案 | 负责模块 |
|------|---------|---------|
| 1.1 | 为 `UserModel.role` 添加迁移设置 `server_default='user'`，并修复 NULL role 的 fail-open 行为 | backend |
| 1.2 | 启动脚本（`make dev` / `make start`）集成 `alembic upgrade head` | DevOps |
| 2.1 | 修复 Agent export：前端 `fetch` 方法从 GET 改为 POST | frontend |
| 2.2 | 修复 Agent import：前端改为发送 JSON 而非 FormData，或后端改为接收文件 | frontend + backend |

### P1 — 短期修复

| 缺口 | 修复方案 | 负责模块 |
|------|---------|---------|
| 2.3 | 补全 MCP 类型定义，或从后端 OpenAPI schema 自动生成前端类型 | frontend |
| 2.4 | 补全 Workflow create/update 响应中的 `steps_count` 和 `inputs` | backend |
| 3.1 | 审计所有 router，为需要权限控制的端点添加 `@require_role`，或改为 deny-by-default 模式 | backend |
| 3.2 | 统一角色系统，前端 `system_role` 扩展为与后端 `UserRole` 一致 | frontend + backend |
| 验证增强 | qa-tester Phase 0 添加 `PRAGMA table_info` vs `Base.metadata` 比对 | validation skills |
| 验证增强 | frontend-validator 添加硬编码英文字符串扫描 | validation skills |

### P2 — 中期改进

| 缺口 | 修复方案 | 负责模块 |
|------|---------|---------|
| 2.5-2.9 | 补全所有前端类型定义与后端响应的字段对齐 | frontend |
| 4.1 | 清理 config.yaml 中的死配置，或在 AppConfig 中添加 `uploads` 字段 | backend |
| 4.2 | 同步 `routers/__init__.py` 的 `__all__` 与 `app.py` 的实际导入 | backend |
| 5.1 | 实现 OAuth 时同步更新 `_PUBLIC_EXACT_PATHS` 白名单 | backend |
| 6.1 | 统一前端错误解析策略，强制使用 `extractError()` 或其增强版 | frontend |
| 6.2 | `AuthProvider.refreshUser()` 改用自定义 fetcher | frontend |
| 验证增强 | 添加 RBAC 装饰器覆盖率检查脚本 | validation skills |
| 验证增强 | 添加前端类型 vs 后端响应模型自动比对 | validation skills |

### P3 — 长期架构改进

| 改进项 | 说明 |
|--------|------|
| 从 OpenAPI schema 自动生成前端类型 | 消除手写类型漂移的根因。后端 FastAPI 已有 OpenAPI schema，可使用 `openapi-typescript` 自动生成 |
| RBAC 改为 deny-by-default | 将权限检查从 opt-in 装饰器改为 middleware 级别的默认拒绝，需要显式声明公开权限 |
| 配置双向验证 | 配置验证工具同时检查"代码引用的 key 是否在 config 中"和"config 中的 key 是否被代码引用" |
| 定期全项目一致性扫描 | 在 CI 中添加定期（非仅变更触发）的全项目一致性检查，覆盖 ORM/DB、类型、i18n、RBAC |
