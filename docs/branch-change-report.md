# offline_feature 分支变更深度分析报告

> 统计范围：`main` → `offline_feature`（共 12 个提交）
> 统计日期：2026-06-10
> 总计：**890 个文件变更**，+19,677 行，-5,959 行
>
> **阅读指南**：
> - 🏢 **甲方/决策者**：阅读每章的「需求背景」和「业务价值」部分，了解相比 main 分支新增了哪些能力
> - 🔧 **运维工程师**：阅读「运维指南」和「关键配置项」部分，了解如何部署、配置和维护
> - 👤 **终端用户**：阅读「用户操作指南」部分，了解如何使用新功能
> - 🤖 **AI/测试**：阅读「测试验证指南」部分，了解如何验证功能正确性和发现潜在缺陷

---

## 目录

1. [Phase 1: 品牌重命名 (deer-flow → iDeer)](#phase-1-品牌重命名)
2. [Phase 2: 内网/离线部署适配](#phase-2-内网离线部署适配)
3. [Phase 3: RBAC 权限管理与管理后台](#phase-3-rbac-权限管理与管理后台)
4. [Phase 4: 工作流引擎](#phase-4-工作流引擎)
5. [Phase 5: 工具扩展](#phase-5-工具扩展)
6. [附录：文件变更清单](#附录文件变更清单)

---

## Phase 1: 品牌重命名

### 需求背景

项目基于字节跳动开源的 deer-flow 智能体框架进行企业化改造。第一阶段将所有品牌标识从社区版 `deer-flow` / `deerflow` / `DeerFlow` 统一变更为企业版 `iDeer` / `ideer`，为后续内网部署和商业化交付奠定基础。

### 业务价值

- 统一品牌形象，避免与开源社区版本混淆
- 环境变量、包名、Docker 镜像等全部使用企业品牌，便于内网资产管理
- 为后续版本独立演进提供命名空间隔离

### 实现思路

采用**全局搜索替换 + 目录重命名**策略，覆盖 5 个维度：

| 维度 | 变更内容 | 影响范围 |
|------|----------|----------|
| Python 包名 | `backend/packages/harness/deerflow/` → `ideer/` | 所有 Python import 路径 |
| 环境变量 | `DEER_FLOW_*` → `IDEER_*` | 配置文件、脚本、Docker Compose |
| Docker 资源 | 容器名/网络名/镜像名 | docker-compose*.yaml |
| 前端文本 | 品牌名称、链接、本地化 | 前端组件、i18n 文件 |
| 文档 | 所有 README、docs/、frontend/src/content/ | 约 80 个文档文件 |

### 关键文件

- `backend/packages/harness/ideer/` — 整个 Python 包目录（18 个子模块）
- `backend/packages/harness/pyproject.toml` — 包名和入口点
- `docker/docker-compose*.yaml` — Docker 资源命名
- `frontend/src/core/i18n/locales/` — 多语言品牌文本

### 测试验证指南

> 🤖 **AI 验证要点**：

1. **残留检查**：`grep -r "deerflow\|deer-flow\|DeerFlow" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.json" --include="*.md"` 应返回空结果（排除本报告和 git 历史）
2. **Import 验证**：`python -c "import ideer"` 应成功，`python -c "import deerflow"` 应失败
3. **环境变量**：确认 `.env.example` 中所有变量以 `IDEER_` 开头
4. **Docker**：`docker compose config` 应无错误，容器名不含 `deerflow`
5. **前端**：检查 `frontend/src/core/i18n/locales/en-US.ts` 和 `zh-CN.ts` 中无 `deer-flow` 字样
6. **潜在缺陷**：检查是否有硬编码的旧路径（如 `backend/packages/harness/deerflow/`）在运行时被引用

---

## Phase 2: 内网/离线部署适配

### 需求背景

企业客户的数据中心通常与互联网物理隔离（气隙环境/Air-Gapped）。main 分支的 iDeer 依赖外部 Docker Hub 拉取镜像、依赖云 API 进行模型推理、依赖互联网工具（web_search 等），无法在内网环境运行。本阶段的目标是让平台**完全不依赖互联网**即可部署和运行。

### 业务价值

- 🏢 **甲方**：可在涉密内网环境部署智能体平台，数据不出内网
- 🔧 **运维**：提供一键打包、一键部署、自动预检的完整工具链
- 👤 **用户**：内网环境下的体验与外网一致，只是去除了联网工具

### 实现思路：三层防御体系

本功能采用**三层防御**设计，确保在任何层面都不会意外访问互联网：

```
┌─────────────────────────────────────────────────┐
│  第一层：打包层（构建机）                          │
│  package-intranet-offline.sh                     │
│  · 构建 Docker 镜像并导出为 .tar                  │
│  · 打包源码和配置模板                              │
│  · 生成 SHA256 校验和                              │
├─────────────────────────────────────────────────┤
│  第二层：部署层（目标机）                          │
│  deploy-intranet.sh                              │
│  · docker-compose.intranet.yaml: pull_policy: never │
│  · 自动生成 IDEER_NETWORK_MODE=offline            │
│  · 内网专用配置模板                                │
├─────────────────────────────────────────────────┤
│  第三层：运行时层（Python 后端）                   │
│  network_mode.py → is_offline()                  │
│  · 工具加载时过滤 requires_network=true 的工具     │
│  · Skill 加载时过滤 requires_internet=true 的技能  │
│  · LLM 永远看不到被过滤的工具/技能                 │
└─────────────────────────────────────────────────┘
```

### 机制详解

#### 机制一：网络模式检测

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/config/network_mode.py` | 定义 `NetworkMode` 枚举和 `is_offline()` 函数 |

**工作原理**：读取环境变量 `IDEER_NETWORK_MODE`，值为 `offline`（不区分大小写）时返回 `True`。无自动检测——必须显式设置。

**被以下模块调用**：
- `tools/tools.py` — 工具过滤
- `skills/storage/skill_storage.py` — 技能过滤

#### 机制二：工具运行时过滤

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/config/tool_config.py` | `ToolConfig` 模型定义 `requires_network: bool` 字段 |
| `backend/packages/harness/ideer/tools/tools.py` | `get_available_tools()` 函数在离线模式下过滤联网工具 |

**工作原理**：
1. 每个工具在 `config.yaml` 中声明 `requires_network: true/false`
2. `get_available_tools()` 在构建 LLM 工具列表前检查 `is_offline()`
3. 离线模式下，所有 `requires_network: true` 的工具被静默移除并记录日志
4. LLM 的工具 schema 中完全不包含这些工具，因此无法尝试调用

**被过滤的工具**：`web_search`、`web_fetch`、`image_search` 等所有依赖互联网的工具

#### 机制三：技能运行时过滤

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/skills/types.py` | `Skill` 数据类定义 `requires_internet: bool` 字段 |
| `backend/packages/harness/ideer/skills/parser.py` | 从 SKILL.md 的 frontmatter 解析 `requires-internet` 元数据 |
| `backend/packages/harness/ideer/skills/storage/skill_storage.py` | `list_skills()` 在离线模式下过滤联网技能 |

**工作原理**：每个技能的 `SKILL.md` 文件可通过 frontmatter 声明 `requires-internet: true`。`list_skills()` 在离线模式下过滤掉这些技能。

**声明联网依赖的技能（7 个）**：`github-deep-research`、`vercel-deploy-claimable`、`video-generation`、`podcast-generation`、`image-generation`、`systematic-literature-review`、`chart-visualization`

#### 机制四：Docker 层离线保障

| 文件 | 作用 |
|------|------|
| `docker/docker-compose.intranet.yaml` | 内网专用 Compose 文件，所有服务设置 `pull_policy: never` |

**关键配置**：`pull_policy: never` 确保 Docker 永远不会尝试从 Registry 拉取镜像。如果镜像未预加载，容器直接启动失败而非尝试联网。

#### 机制五：离线打包与部署

| 文件 | 作用 |
|------|------|
| `scripts/package-intranet-offline.sh` | 在联网构建机上打包：构建镜像 → `docker save` → 打包源码 → 生成校验和 |
| `scripts/deploy-intranet.sh` | 在目标机上部署：预检 → 解压 → 加载镜像 → 生成密钥 → 启动服务 → 健康检查 |
| `scripts/check-intranet.sh` | 8 步预检：Docker 可用性、镜像存在性、端口占用、磁盘空间、LLM 端点可达性 |
| `config.intranet.yaml` | 内网专用配置模板，移除所有联网工具组、指向内网模型端点 |
| `scripts/README-intranet.md` | 内网部署完整文档（201 行） |

**部署流程**：
```
[联网构建机]                    [文件传输]           [内网目标机]
package-intranet-offline.sh  →  U盘/安全传输  →  deploy-intranet.sh up
  ├─ 构建 gateway 镜像                              ├─ check-intranet.sh (预检)
  ├─ 构建 frontend 镜像                             ├─ 解压源码包
  ├─ 拉取 nginx 镜像                                ├─ 加载 Docker 镜像
  ├─ docker save → .tar                             ├─ 生成密钥
  ├─ 打包源码                                       ├─ 设置 IDEER_NETWORK_MODE=offline
  └─ 生成 SHA256SUMS                                ├─ docker compose up
                                                    └─ 健康检查
```

### 关键配置项

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `IDEER_NETWORK_MODE` | 网络模式开关 | `online`（设为 `offline` 激活离线模式） |
| `IDEER_LLM_ENDPOINT` | LLM 端点地址（预检用） | 无（可选） |
| `IDEER_BUNDLE_ROOT` | 离线包目录 | 当前目录 |
| `IDEER_NO_LOAD` | 跳过镜像加载 | `0` |
| `BETTER_AUTH_SECRET` | 认证密钥（自动生成） | 自动生成并持久化到文件 |

### 运维指南

1. **打包**：在联网机器执行 `scripts/package-intranet-offline.sh`，可指定 `--version`、`--platform`、`--output-dir`
2. **传输**：将生成的 bundle 目录通过安全方式传输到内网目标机
3. **部署**：在目标机执行 `scripts/deploy-intranet.sh up`
4. **日常管理**：
   - `deploy-intranet.sh status` — 查看服务状态
   - `deploy-intranet.sh logs` — 查看日志
   - `deploy-intranet.sh restart` — 重启服务
   - `deploy-intranet.sh stop` — 停止服务
5. **配置 LLM**：编辑 `runtime/config.yaml` 中的 `models` 部分，指向内网 LLM 端点

### 用户操作指南

内网用户使用方式与外网基本一致，但以下功能不可用：
- ❌ 网络搜索工具（web_search、web_fetch、image_search）
- ❌ 需要联网的技能（如 GitHub 深度调研、视频生成等）
- ✅ 文件操作、代码执行、数据分析等本地工具完全可用
- ✅ 文档读取（read_document）完全可用

### 测试验证指南

> 🤖 **AI 验证要点**：

1. **网络模式检测**：
   - 设置 `IDEER_NETWORK_MODE=offline`，调用 `is_offline()` 应返回 `True`
   - 设置 `IDEER_NETWORK_MODE=ONLINE`（大写），应返回 `False`
   - 不设置该变量，应默认返回 `False`（在线模式）
   - 设置无效值（如 `IDEER_NETWORK_MODE=xxx`），应记录警告并默认在线

2. **工具过滤**：
   - 离线模式下调用 `get_available_tools()`，返回列表不应包含 `requires_network: true` 的工具
   - 在线模式下，所有工具应正常返回
   - 检查日志中是否有被过滤工具的记录

3. **技能过滤**：
   - 离线模式下调用 `list_skills()`，返回列表不应包含 `requires-internet: true` 的技能
   - 确认 7 个联网技能被正确过滤

4. **Docker 层**：
   - `docker compose -f docker-compose.intranet.yaml config` 确认所有服务 `pull_policy: never`
   - 在无网络环境下执行 `docker compose up`，确认不会尝试拉取镜像

5. **打包完整性**：
   - 执行 `sha256sum -c SHA256SUMS` 验证所有文件校验和
   - 确认 bundle 包含：镜像 tar、源码 tar.gz、部署脚本、配置模板、MANIFEST.txt

6. **潜在缺陷探测**：
   - 检查是否有工具/技能绕过 `is_offline()` 检查直接注册
   - 检查 MCP Server 模式的工具是否也受离线过滤（当前设计下 MCP Server 由 `extensions_config.json` 控制，不受 `requires_network` 过滤）
   - 检查 `config.intranet.yaml` 中是否遗漏了联网依赖

---

## Phase 3: RBAC 权限管理与管理后台

### 需求背景

main 分支的 iDeer 没有用户权限管理——所有登录用户拥有相同权限，无法区分管理员和普通用户，无法控制 Agent/Skill 的可见性。企业环境需要：
- 不同角色拥有不同操作权限
- 部门级资源隔离（部门 A 的 Agent 不应被部门 B 看到）
- 管理员可集中管理用户、部门和工具

### 业务价值

- 🏢 **甲方**：满足企业信息安全合规要求，实现最小权限原则
- 🔧 **运维**：通过管理后台可视化管理用户和资源，无需直接操作数据库
- 👤 **用户**：每个用户只能看到自己有权限的资源，界面更清晰

### 实现思路：双层认证 + 基于角色的访问控制

```
┌─────────────────────────────────────────────────┐
│  请求进入                                         │
│  ↓                                               │
│  第一层：JWT 认证（deps.py）                       │
│  · 从 Cookie 读取 access_token                    │
│  · 解码 JWT，验证 token_version                   │
│  · 产出：User 对象（ID、email）                    │
│  ↓                                               │
│  第二层：RBAC 鉴权（authz.py）                     │
│  · 查询 users_ext 表获取角色和部门                 │
│  · 首个用户自动提升为 super_admin                  │
│  · 被禁用用户返回 403                              │
│  · 产出：UserModel（role、department_id）          │
│  ↓                                               │
│  权限检查（装饰器/函数）                            │
│  · require_role() — 角色检查                      │
│  · check_resource_access() — 资源可见性检查        │
│  · check_resource_modify() — 资源修改权限检查      │
└─────────────────────────────────────────────────┘
```

### 机制详解

#### 机制一：RBAC 数据模型

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/persistence/models/user.py` | 定义 `UserRole` 枚举、`ResourceVisibility` 枚举、`DepartmentModel`、`UserModel` |
| `backend/packages/harness/ideer/persistence/migrations/versions/16147afec43b_*.py` | 创建 `departments` 和 `users_ext` 表 |
| `backend/packages/harness/ideer/persistence/migrations/versions/f3a2b1c4d5e6_*.py` | 添加 `disabled` 字段和索引 |

**角色层级**（权限从高到低）：
```
super_admin > department_admin > user > viewer
```

**资源可见性**：
```
private（仅自己） < department（同部门） < public（所有人）
```

**数据库表结构**：

`departments` 表：
| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(36) PK | 部门 ID |
| name | String(128) UNIQUE | 部门名称 |
| description | String(512) | 部门描述 |
| created_at | DateTime | 创建时间 |

`users_ext` 表：
| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(36) PK | 用户 ID（与 JWT 认证的用户 ID 对应） |
| username | String(128) UNIQUE | 用户名 |
| role | String(32) | 角色（user/department_admin/super_admin） |
| department_id | String(36) FK | 所属部门 |
| disabled | Boolean | 是否禁用 |
| created_at | DateTime | 创建时间 |
| last_login | DateTime | 最后登录时间 |

#### 机制二：权限中间件

| 文件 | 作用 |
|------|------|
| `backend/app/gateway/authz.py` | 核心 RBAC 中间件，包含 `get_current_rbac_user()`、`require_role()`、`check_resource_access()` 等 |
| `backend/app/gateway/deps.py` | JWT 认证依赖注入，`get_current_user_from_request()` |

**关键函数**：

- `get_current_rbac_user(request)` — FastAPI 依赖函数，每次请求解析当前用户的 RBAC 角色。首个注册用户自动提升为 `super_admin`（使用 `SELECT FOR UPDATE` 防止并发竞态）
- `require_role(*roles)` — 装饰器工厂，限制接口只允许特定角色访问
- `check_resource_access(user, owner_id, dept_id, visibility)` — 判断用户是否有权访问某个资源
- `check_resource_modify(user, owner_id, dept_id)` — 判断用户是否有权修改某个资源
- `filter_visible_resources(items, user)` — 批量过滤用户可见的资源列表

**角色权限矩阵**：

| 能力 | super_admin | department_admin | user | viewer |
|------|:-----------:|:----------------:|:----:|:------:|
| 查看自己的资源 | ✅ | ✅ | ✅ | ✅ 只读 |
| 查看部门资源 | ✅ | ✅ | ❌ | ❌ |
| 查看所有资源 | ✅ | ❌ | ❌ | ❌ |
| 修改自己的资源 | ✅ | ✅ | ✅ | ❌ |
| 修改部门资源 | ✅ | ✅ | ❌ | ❌ |
| 修改任意资源 | ✅ | ❌ | ❌ | ❌ |
| 用户管理 | ✅ | ❌ | ❌ | ❌ |
| 部门管理 | ✅ | ❌ | ❌ | ❌ |
| 设置 public 可见性 | ✅ | ❌ | ❌ | ❌ |
| 设置 department 可见性 | ✅ | ✅ | ❌ | ❌ |
| 测试工具 | ✅ | ✅ | ❌ | ❌ |
| 配置工具 | ✅ | ❌ | ❌ | ❌ |
| 安装技能 | ✅ | ✅ | ❌ | ❌ |

#### 机制三：资源可见性元数据

| 文件 | 作用 |
|------|------|
| `backend/app/gateway/routers/agents.py` | Agent 资源的 `.meta.json` 文件管理 |
| `backend/app/gateway/routers/skills.py` | Skill 资源的 `.meta.json` 文件管理 |

**工作原理**：Agent 和 Skill 的可见性信息存储在文件系统中的 `.meta.json` 文件中（非数据库），包含 `visibility`、`owner_id`、`department_id` 字段。每次 API 请求时读取并检查权限。

#### 机制四：管理后台 API

| 文件 | 作用 |
|------|------|
| `backend/app/gateway/routers/admin.py` | Admin API 路由（8 个端点） |
| `backend/app/gateway/routers/tools.py` | 工具管理 API（5 个端点） |

**API 端点清单**：

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/admin/stats` | super_admin | 系统统计（用户数、部门数） |
| GET | `/api/admin/users` | super_admin | 用户列表（支持分页、按部门/角色筛选） |
| PUT | `/api/admin/users/{id}/role` | super_admin | 修改用户角色（防止移除最后一个 super_admin） |
| DELETE | `/api/admin/users/{id}` | super_admin | 禁用用户（不能禁用自己、不能禁用最后一个 super_admin） |
| GET | `/api/admin/departments` | 任何认证用户 | 部门列表（member_count 仅对 admin 可见） |
| POST | `/api/admin/departments` | super_admin | 创建部门 |
| PUT | `/api/admin/departments/{id}` | super_admin | 更新部门 |
| DELETE | `/api/admin/departments/{id}` | super_admin | 删除部门（有活跃成员时拒绝） |
| GET | `/api/tools` | 任何认证用户 | 工具列表（支持 group、search 筛选） |
| GET | `/api/tools/groups` | 任何认证用户 | 工具分组列表 |
| GET | `/api/tools/{tool_name}` | 任何认证用户 | 工具详情（含 param_schema、config_schema） |
| POST | `/api/tools/{name}/test` | dept_admin+ | 测试执行工具 |
| PUT | `/api/tools/{name}/config` | super_admin | 修改工具配置 |

### 关键配置项

无需额外配置。RBAC 功能在首次用户登录时自动激活：
1. 第一个登录的用户自动成为 `super_admin`
2. 后续登录的用户默认为 `user` 角色
3. 管理员通过管理后台调整角色和部门

### 运维指南

1. **首次部署**：第一个登录系统的用户自动获得超级管理员权限
2. **用户管理**：通过管理后台（`/workspace/admin/users`）管理用户角色
3. **部门管理**：通过管理后台（`/workspace/admin/departments`）管理组织架构
4. **安全防护**：
   - 系统自动防止移除最后一个超级管理员
   - 管理员不能禁用自己的账号
   - 有活跃成员的部门不能被删除
   - 使用 `SELECT FOR UPDATE` 防止并发修改竞态

### 用户操作指南

1. **普通用户**：
   - 登录后可使用对话功能、查看自己创建的 Agent/Skill
   - 可将自己创建的资源设为 `private`（仅自己可见）
   - 可启动工作流运行

2. **部门管理员**：
   - 除普通用户权限外，还可：
   - 查看和管理本部门的所有资源
   - 将资源设为 `department` 可见性
   - 安装新技能、测试工具

3. **超级管理员**：
   - 拥有所有权限
   - 通过 `/workspace/admin` 管理用户、部门、工具
   - 可将资源设为 `public`（全员可见）
   - 可修改工具配置

### 测试验证指南

> 🤖 **AI 验证要点**：

1. **首个用户自动提升**：
   - 清空 `users_ext` 表，用新用户登录，确认角色为 `super_admin`
   - 并发创建两个用户，确认只有一个被提升为 `super_admin`（竞态测试）

2. **角色权限检查**：
   - `user` 角色调用 `GET /api/admin/users` 应返回 403
   - `viewer` 角色调用 `POST /api/workflows/{name}/run` 应返回 403
   - `department_admin` 调用 `DELETE /api/admin/users/{id}` 应返回 403

3. **资源可见性**：
   - 创建 `private` Agent，用其他用户请求应返回 404
   - 创建 `department` Agent，同部门用户可见，跨部门不可见
   - `super_admin` 可见所有资源

4. **安全防护**：
   - 尝试禁用自己 → 应返回 400
   - 尝试移除最后一个 super_admin 的角色 → 应返回 400
   - 尝试删除有活跃成员的部门 → 应返回 400

5. **潜在缺陷探测**：
   - 检查 `.meta.json` 文件损坏时的降级处理
   - 检查 `disabled` 用户的已有会话是否被正确终止
   - 检查 `viewer` 角色是否真的只能读取（不能创建对话、不能修改资源）
   - 检查部门删除后，原部门成员的 `department_id` 是否被正确清理

---

## Phase 4: 工作流引擎

### 需求背景

企业业务流程通常包含多个步骤，且需要人工审批环节。main 分支的 iDeer 只支持单轮对话，无法编排复杂的多步骤流程。本阶段实现了一个 YAML 声明式的工作流引擎，支持：
- 多步骤顺序/并行/循环执行
- 条件分支
- Agent 调用和工具调用
- 人工审批环节（支持多进程/多服务器部署）
- 运行状态持久化（支持断点恢复）

### 业务价值

- 🏢 **甲方**：将企业业务流程固化为可复用的工作流模板，降低对个人经验的依赖
- 🔧 **运维**：通过 YAML 文件管理和版本控制工作流，无需修改代码
- 👤 **用户**：通过 Web 界面创建、编辑、运行工作流，查看运行历史

### 实现思路：YAML DSL + 步骤分发器 + 数据库轮询

```
YAML 定义 → 解析器(Parser) → 工作流定义(WorkflowDef)
                                    ↓
                              执行器(Executor)
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              步骤分发器        模板引擎          状态管理
           (steps/__init__)  (template.py)    (state.py)
                    ↓
        ┌───┬───┬───┬───┬───┬───┐
        ↓   ↓   ↓   ↓   ↓   ↓   ↓
      agent tool human cond para loop retry
        ↓   ↓   ↓   ↓   ↓   ↓   ↓
        └───┴───┴───┴───┴───┴───┘
                    ↓
              数据库持久化(store.py)
              · 每步执行后保存状态
              · 人工审批通过 DB 轮询
              · 支持断点恢复
```

### 机制详解

#### 机制一：YAML Schema 定义

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/schema.py` | 定义 `StepType`、`StepDef`、`WorkflowDef`、`InputParam`、`RetryPolicy` |

**支持的 7 种步骤类型**：

| 类型 | 说明 | 必需字段 |
|------|------|----------|
| `agent` | 调用 Agent（完整工具/中间件能力） | `agent`（Agent 名称）、`prompt`（提示词模板） |
| `tool` | 直接调用工具 | `tool`（工具名称）、`params`（参数字典） |
| `human_review` | 人工审批（数据库轮询） | `message`（审批提示） |
| `condition` | 条件分支 | `expression`（条件表达式） |
| `parallel` | 并行执行多个子步骤 | `steps`（子步骤列表） |
| `loop` | 遍历列表执行子步骤 | `items`（列表表达式）、`steps`（子步骤列表） |
| `retry` | 重试执行 | `steps`（子步骤列表）、`max`（最大重试次数） |

**YAML DSL 示例**：

```yaml
name: research_pipeline
description: 调研-分析-审批流水线
version: "1.0"

inputs:
  topic:
    type: string
    required: true
    description: "调研主题"
  analysis_type:
    type: string
    default: "summary"

steps:
  - id: research
    type: agent
    agent: researcher
    prompt: "请调研以下主题：{{inputs.topic}}"

  - id: analyze
    type: agent
    agent: analyzer
    prompt: "请分析以下调研结果：{{steps.research.output}}"
    retry:
      max: 2
      backoff: 5.0

  - id: review
    type: human_review
    message: "请审批分析报告"
    approvers:
      - admin@example.com

  - id: generate
    type: agent
    condition: "{{steps.review.approved}}"
    agent: report-writer
    prompt: "生成报告：{{steps.analyze.output}}"
```

#### 机制二：YAML 解析与验证

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/parser.py` | YAML 解析器，执行 7 项验证 |

**验证规则**：
1. 必须包含 `name` 字段
2. 所有步骤 ID 递归收集后不能重复
3. `then`/`else` 字符串引用必须指向已存在的步骤 ID
4. 步骤类型必须是有效的 `StepType` 枚举值
5. 每种类型有必需字段（如 agent 步骤必须有 `agent` 字段）
6. `human_review` 不能嵌套在 `loop` 或 `parallel` 内部
7. 最大嵌套深度 20 层

#### 机制三：模板引擎

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/template.py` | 模板渲染引擎 |

**模板语法**：
- `{{inputs.xxx}}` — 引用工作流输入参数
- `{{steps.xxx.output}}` — 引用已完成步骤的输出
- `{{steps.xxx.status}}` — 引用步骤状态
- `{{_loop.index}}` — 循环索引（在 loop 步骤内）
- `{{_loop.item}}` — 循环当前项（在 loop 步骤内）

**类型保持**：完整字符串模板（如 `{{steps.a.output}}`）保持原始类型（dict/list/int），不会转为字符串。部分嵌入模板（如 `"结果：{{steps.a.output}}"`）转为字符串。

**安全措施**：屏蔽 `__class__`、`__globals__` 等 dunder 属性访问，最大表达式长度 1000 字符。

#### 机制四：执行引擎

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/executor.py` | 工作流执行器 |

**执行流程**：
1. 创建 `WorkflowState`（状态：RUNNING）
2. 持久化初始状态到数据库
3. 顺序遍历顶层步骤
4. 对每个步骤：评估 `condition` 守卫 → 带重试执行 → 检查 goto 指令 → 持久化状态
5. 全部成功 → 状态变为 COMPLETED
6. 任一失败 → 状态变为 FAILED（除非 `on_error: skip`）

**重试机制**：每个步骤可配置 `RetryPolicy`（max/backoff/on_errors），使用线性退避（`backoff × (attempt + 1)`）+ 随机抖动（`random.uniform(0, 1)`）防止雷群效应。

#### 机制五：人工审批（数据库轮询）

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/steps/human_step.py` | 人工审批步骤实现 |
| `backend/app/gateway/routers/workflows.py` | 审批提交 API |

**为什么用数据库轮询而非内存 Future**：设计文档明确说明这是为了支持多 Worker 部署和服务重启恢复。内存 Future 只在单进程环境下有效。

**工作流程**：
1. 步骤执行器将状态设为 `WAITING_HUMAN` 并写入数据库
2. 进入轮询循环：每 2 秒读取数据库状态（指数退避，最大 30 秒）
3. 外部客户端调用 `POST /api/workflows/{name}/runs/{id}/review`
4. API 端点原子更新数据库：`WHERE status='WAITING_HUMAN'` → 设为 `RUNNING`，写入 `review_result`
5. 轮询循环检测到状态变化，将审批结果写入步骤输出，继续执行
6. 超时（默认 1 小时）→ 状态变为 FAILED

#### 机制六：数据库持久化

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/store.py` | 工作流存储层（287 行） |
| `backend/packages/harness/ideer/persistence/models/workflow.py` | 数据库模型 |

**单表设计**：`workflow_runs` 表同时存储工作流定义和运行记录：
- 定义行：`run_id = "def:<name>"`，`status = "definition"`
- 运行行：`run_id = UUID`，`status = 运行状态`

**每步持久化**：执行器在每个步骤完成后调用 `save_run_state()`，将完整的 `WorkflowState` 序列化为 JSON 写入数据库。这意味着即使服务重启，也可以从最后一步的状态恢复执行。

#### 机制七：步骤执行器

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/workflows/steps/__init__.py` | 步骤分发器 |
| `backend/packages/harness/ideer/workflows/steps/agent_step.py` | Agent 步骤（通过 SubagentExecutor 执行，拥有完整工具/中间件能力） |
| `backend/packages/harness/ideer/workflows/steps/tool_step.py` | 工具步骤（直接调用工具，支持 async/sync） |
| `backend/packages/harness/ideer/workflows/steps/condition_step.py` | 条件步骤（支持 goto 和内联子步骤） |
| `backend/packages/harness/ideer/workflows/steps/parallel_step.py` | 并行步骤（asyncio.gather，支持超时和 fail_fast） |
| `backend/packages/harness/ideer/workflows/steps/loop_step.py` | 循环步骤（遍历列表，支持嵌套循环，每迭代结果命名空间隔离） |
| `backend/packages/harness/ideer/workflows/steps/retry_step.py` | 重试步骤（整组子步骤重试 + 线性退避） |

### 关键配置项

无需额外配置。工作流功能通过 API 自动可用。

**API 端点清单**：

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/workflows` | 任何认证用户 | 列出工作流 |
| GET | `/api/workflows/{name}` | 任何认证用户 | 获取工作流详情（原始 YAML 仅 admin 可见） |
| POST | `/api/workflows` | dept_admin+ | 创建工作流 |
| PUT | `/api/workflows/{name}` | dept_admin+ | 更新工作流 |
| DELETE | `/api/workflows/{name}` | super_admin | 删除工作流 |
| POST | `/api/workflows/{name}/run` | user+ | 启动运行 |
| GET | `/api/workflows/{name}/runs` | 任何认证用户 | 运行历史 |
| GET | `/api/workflows/{name}/runs/{id}` | 任何认证用户 | 运行状态详情 |
| POST | `/api/workflows/{name}/runs/{id}/review` | 任何认证用户 | 提交人工审批 |

### 运维指南

1. **工作流管理**：通过 API 或前端界面创建/编辑/删除工作流
2. **运行监控**：通过 `GET /api/workflows/{name}/runs` 查看运行历史和状态
3. **人工审批**：运行进入 `WAITING_HUMAN` 状态后，通过 `POST .../review` 提交审批
4. **数据库维护**：`workflow_runs` 表会持续增长，定期清理历史运行记录
5. **超时配置**：人工审批默认超时 1 小时，可在步骤级别通过 `timeout` 字段调整

### 用户操作指南

1. **创建工作流**：
   - 通过 `/workspace/workflows/new` 页面编写 YAML
   - 或通过 `POST /api/workflows` API 提交

2. **运行工作流**：
   - 通过 `/workspace/workflows/{name}` 页面点击「运行」
   - 填写必需的输入参数
   - 运行立即返回，后台异步执行

3. **查看运行状态**：
   - 通过 `/workspace/workflows/{name}` 页面查看运行历史
   - 每个步骤的状态、输出、错误信息均可查看

4. **审批**：
   - 当运行进入「等待审批」状态时，审批人会看到审批界面
   - 审批可附带数据（`data` 字段），后续步骤可通过 `{{steps.xxx.data}}` 引用
   - 审批通过后工作流继续执行

### 测试验证指南

> 🤖 **AI 验证要点**：

1. **YAML 解析验证**：
   - 重复步骤 ID → 应报错
   - `then` 引用不存在的步骤 → 应报错
   - `human_review` 嵌套在 `loop` 内 → 应报错
   - 缺少必需字段 → 应报错
   - 超过 20 层嵌套 → 应报错

2. **模板渲染**：
   - `{{steps.a.output}}` 为完整字符串时应保持原始类型
   - `{{steps.nonexistent.output}}` 应返回 None 而非报错
   - `{{__class__}}` 等 dunder 访问应被屏蔽
   - 表达式长度超过 1000 字符 → 应返回 _MISSING

3. **执行流程**：
   - 条件分支：`expression: "false"` 应跳过 then 分支
   - 并行步骤：部分子步骤失败时应继续（除非全部失败）
   - 循环步骤：`max_iterations` 超限时应截断
   - 重试：验证线性退避（`backoff*(attempt+1)`）和随机抖动（`random.uniform(0,1)`）

4. **人工审批**：
   - 运行进入 `WAITING_HUMAN` 后，数据库状态应正确
   - 提交审批后，轮询循环应在下一次轮询时检测到
   - 超时后状态应变为 FAILED
   - 并发提交审批（两人同时审批同一运行）→ 应只有一个成功（原子更新）

5. **状态持久化**：
   - 每步执行后数据库应有最新状态
   - 模拟服务重启后，从数据库加载状态应能恢复

6. **潜在缺陷探测**：
   - 循环步骤中嵌套循环时，`loop_vars` 的保存/恢复是否正确
   - 并行步骤中 `_ERROR_SENTINEL` 是否正确区分错误和正常输出
   - 条件步骤的 goto 指令是否正确跳过中间步骤
   - `on_error: skip` 时步骤失败后是否真的继续执行下一步

---

## Phase 5: 工具扩展

### 需求背景

main 分支的 iDeer 只有基础的文件操作和搜索工具，缺乏企业常见的文档处理、代码执行和数据分析能力。本阶段新增三个企业级工具，覆盖办公场景的核心需求。

### 业务价值

- 🏢 **甲方**：智能体可直接处理企业内部的 Word/Excel/PPT/PDF 文档，无需人工转换
- 👤 **用户**：上传数据文件即可获得统计分析，上传代码即可执行验证
- 🔧 **运维**：每个工具都有路径白名单和资源限制，安全性可控

### 实现思路：双模式架构

每个工具同时实现两种部署模式：

```
┌─────────────────────────────────────────────────┐
│  模式一：Community Tool（集成模式）               │
│  · 作为 LangChain @tool 运行在 Agent 进程内      │
│  · 通过 Runtime 对象访问沙箱基础设施              │
│  · 适合单体部署                                   │
│  · 配置：config.yaml 中 use 字段                  │
├─────────────────────────────────────────────────┤
│  模式二：MCP Server（独立模式）                   │
│  · 作为独立子进程运行，通过 stdio 通信             │
│  · 不依赖 iDeer 沙箱，自行实现安全隔离             │
│  · 适合独立部署/分布式部署                        │
│  · 配置：extensions_config.json                   │
└─────────────────────────────────────────────────┘
```

### 工具一：read_document（文档读取）

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/community/doc_reader/tools.py` | Community Tool 实现（212 行） |
| `backend/packages/harness/ideer/community/doc_reader/mcp_server.py` | MCP Server 实现（227 行） |
| `backend/packages/harness/ideer/community/doc_reader/README.md` | 使用文档 |

**支持格式**：`.pdf`、`.docx`、`.doc`、`.xlsx`、`.xls`、`.pptx`、`.ppt`

**核心能力**：
- 将办公文档转换为 Markdown 文本
- PDF 支持页面范围提取（如 `"1-5"`、`"3"`、`"1-3,7,10-12"`），使用 `pymupdf4llm` 库
- 其他格式使用 `MarkItDown` 库转换
- 输出包含元信息头部：`<!-- file: name | size: N bytes | pages: P -->`

**安全机制**：

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 路径白名单 | `/mnt/user-data`、`/tmp` | 只能读取白名单目录下的文件 |
| 文件大小上限 | 100 MB | 超过则拒绝处理 |
| 输出截断 | 50,000 字符 | 保留文档开头部分 |
| 页面上限 | 10,000 页 | 防止内存耗尽 |

**输入/输出**：
- 输入：`file_path: str`（必需）、`page_range: str | None`（可选，仅 PDF）
- 输出：Markdown 文本（成功）或 `{"error": "..."}` JSON（失败）

### 工具二：code_interpreter（代码解释器）

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/community/code_interpreter/tools.py` | Community Tool 实现（123 行） |
| `backend/packages/harness/ideer/community/code_interpreter/mcp_server.py` | MCP Server 实现（156 行） |
| `backend/packages/harness/ideer/community/code_interpreter/README.md` | 使用文档 |

**支持语言**：Python（`python3`）、JavaScript（`node`）

**核心能力**：
- 执行任意代码并返回 stdout/stderr 输出
- 适合数据处理、计算、图表生成等任务
- 沙箱中预装 pandas、matplotlib、numpy

**安全机制（两种模式不同）**：

Community Tool 模式（通过沙箱）：
- 代码在 iDeer 沙箱容器中执行
- 使用 `timeout` 命令限制执行时间
- 临时文件在 `finally` 块中清理

MCP Server 模式（独立子进程）：
- **环境净化**：仅传递 `PATH`、`LANG`、`LC_ALL`、`TZ`、`USER`、`TMPDIR` 六个环境变量
- **资源限制**（Unix）：内存 512MB（`RLIMIT_AS`）、文件大小 100MB（`RLIMIT_FSIZE`）、进程数 64（`RLIMIT_NPROC`）
- **超时**：`subprocess.run(timeout=...)`，范围 [1, 300] 秒
- **临时文件清理**：`tempfile.mkstemp` → 执行 → `finally` 删除

通用限制：
| 限制项 | 值 | 说明 |
|--------|-----|------|
| 代码大小 | 1 MB | 超过则拒绝 |
| 输出截断 | 20,000 字符 | 中间截断（保留首尾各 50%） |

**输入/输出**：
- 输入：`code: str`（必需）、`language: str = "python"`、`timeout: int = 60`
- 输出：`{"stdout": "...", "stderr": "...", "exit_code": N}`

### 工具三：data_analyzer（数据分析器）

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/community/data_analyzer/tools.py` | Community Tool 实现（202 行） |
| `backend/packages/harness/ideer/community/data_analyzer/mcp_server.py` | MCP Server 实现（226 行） |
| `backend/packages/harness/ideer/community/data_analyzer/README.md` | 使用文档 |

**支持格式**：`.csv`、`.xlsx`、`.xls`、`.json`（支持标准 JSON、NDL JSON、分块读取）

**三种分析模式**：

| 模式 | 说明 | 输出 |
|------|------|------|
| `summary` | 数据概览 | 行列数、列类型、缺失值、前 5 行预览 |
| `describe` | 统计摘要 | 数值列 describe()、分类列 top 5 频次 |
| `correlation` | 相关性分析 | Pearson 相关矩阵、强相关（\|r\| > 0.7）列对 |

**安全机制**：

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 路径白名单 | `/mnt/user-data`、`/tmp` | 只能读取白名单目录下的文件 |
| 文件大小上限 | 200 MB | 超过则拒绝 |
| 行数上限 | 500,000 行 | 防止 OOM |
| 内存上限 | 500 MB | 加载后检查 `df.memory_usage(deep=True)` |
| 输出截断 | 10,000 字符 | 二分搜索截断，保证 JSON 可解析 |
| 分类列分析上限 | 20 列 | value_counts 最多分析 20 个分类列 |

**输入/输出**：
- 输入：`file_path: str`（必需）、`analysis_type: str = "summary"`
- 输出：`{"file_path": "...", "analysis_type": "...", "result": {...}}` 或截断时 `{"result_summary": "...", "truncated": true}`

### 工具注册与配置

| 文件 | 作用 |
|------|------|
| `backend/packages/harness/ideer/tools/registry.py` | 工具注册表（内存中的元数据管理，111 行） |
| `backend/packages/harness/ideer/config/extensions_config.py` | MCP 扩展配置加载 |
| `extensions_config.example.json` | MCP 扩展配置示例 |

**MCP Server 配置示例**（`extensions_config.json`）：
```json
{
  "mcpServers": {
    "doc-reader": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["-m", "ideer.community.doc_reader.mcp_server"]
    },
    "code-interpreter": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["-m", "ideer.community.code_interpreter.mcp_server"]
    },
    "data-analyzer": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["-m", "ideer.community.data_analyzer.mcp_server"]
    }
  }
}
```

### 运维指南

1. **启用工具**：
   - Community Tool 模式：在 `config.yaml` 的 `tools` 部分添加对应工具配置
   - MCP Server 模式：在 `extensions_config.json` 中设置 `enabled: true`

2. **安全配置**：
   - 路径白名单硬编码为 `/mnt/user-data` 和 `/tmp`，如需修改需改代码
   - 文件大小、行数、内存等限制在各工具的 `_MAX_*` 常量中定义

3. **依赖管理**：
   - `read_document`：需要 `pymupdf4llm`、`markitdown` 包
   - `code_interpreter`：需要系统安装 `python3` 和 `node`
   - `data_analyzer`：需要 `pandas`、`openpyxl` 包

### 用户操作指南

1. **文档读取**：
   - 将文件上传到工作区（`/mnt/user-data` 目录）
   - 在对话中要求 Agent 读取文档，如「请读取 xxx.pdf 的第 1-5 页」
   - Agent 会自动调用 `read_document` 工具

2. **代码执行**：
   - 在对话中要求 Agent 执行代码，如「请用 Python 计算 1 到 100 的和」
   - Agent 会调用 `code_interpreter` 执行代码并返回结果
   - 支持 Python 和 JavaScript

3. **数据分析**：
   - 上传 CSV/Excel/JSON 文件到工作区
   - 在对话中要求分析，如「请分析 sales.csv 的数据概览」
   - 支持三种分析模式：summary、describe、correlation

### 测试验证指南

> 🤖 **AI 验证要点**：

1. **read_document**：
   - 读取 PDF 指定页面范围 → 应只返回指定页面内容
   - 读取超过 100MB 的文件 → 应返回错误
   - 读取白名单外路径 → 应返回 PermissionError
   - 输出超过 50,000 字符 → 应被截断
   - 各格式文件（docx/xlsx/pptx）→ 应正确转换为 Markdown

2. **code_interpreter**：
   - 执行 `print("hello")` → stdout 应为 "hello"
   - 执行死循环代码 → 应在 timeout 后终止
   - 执行超过 1MB 的代码 → 应返回错误
   - MCP 模式下尝试访问环境变量 → 应只有白名单变量可用
   - 输出超过 20,000 字符 → 应中间截断（保留首尾）

3. **data_analyzer**：
   - `summary` 模式 → 应返回行列数、列类型、缺失值
   - `describe` 模式 → 应返回数值列统计和分类列频次
   - `correlation` 模式 → 应返回相关矩阵和强相关列对
   - 超过 500,000 行的文件 → 应返回错误
   - JSON 文件三种格式（标准/NDL/分块）→ 应正确解析

4. **双模式一致性**：
   - Community Tool 和 MCP Server 对同一输入应产生相同结果（除沙箱差异外）
   - MCP Server 不可用时，Community Tool 应仍可工作（反之亦然）

5. **潜在缺陷探测**：
   - `data_analyzer` MCP Server 的 `_read_file` 缺少行数限制安全网（与 Community Tool 不一致）
   - `code_interpreter` MCP 模式的 `resource.setrlimit` 仅在 Unix 生效，Windows 无保护
   - 路径白名单使用 `os.path.realpath()`，检查符号链接是否可绕过
   - 并发调用同一工具时临时文件是否冲突

---

## 附录：文件变更清单

### Phase 1: 品牌重命名（约 800 个文件）

<details>
<summary>点击展开完整清单</summary>

**Python 包重命名**（`backend/packages/harness/deerflow/` → `ideer/`）：
- `agents/`（factory, features, lead_agent, memory, middlewares, thread_state）
- `client.py`
- `community/`（aio_sandbox, ddg_search, exa, firecrawl, image_search, infoquest, jina_ai, serper, tavily）
- `config/`（acp_config, agents_config, app_config, checkpointer_config, database_config, extensions_config, guardrails_config, loop_detection_config, memory_config, model_config, network_mode, paths, run_events_config, runtime_paths, safety_finish_reason_config, sandbox_config, skill_evolution_config, skills_config, stream_bridge_config, subagents_config, summarization_config, title_config, token_usage_config, tool_config, tool_search_config, tracing_config）
- `guardrails/`（builtin, middleware, provider）
- `mcp/`（cache, client, oauth, session_pool, tools）
- `models/`（claude_provider, credential_loader, factory, mindie_provider, openai_codex_provider, patched_deepseek, patched_minimax, patched_openai, vllm_provider）
- `persistence/`（base, engine, feedback, json_compat, migrations, models, run, thread_meta, user）
- `reflection/`（resolvers）
- `runtime/`（checkpointer, converters, events, journal, runs, serialization, store, stream_bridge, user_context）
- `sandbox/`（exceptions, file_operation_lock, local, middleware, sandbox, sandbox_provider, search, security, tools）
- `skills/`（installer, parser, security_scanner, storage, tool_policy, types, validation）
- `subagents/`（builtins, config, executor, registry, token_collector）
- `tools/`（builtins, registry, skill_manage_tool, sync, tools, types）
- `tracing/`（factory, metadata）
- `uploads/`（manager）
- `utils/`（file_conversion, network, readability, time）

**项目级文件**：README*.md, AGENTS.md, CLAUDE.md, CONTRIBUTING.md, SECURITY.md, Install.md, LICENSE, Makefile, .env.example, .gitignore, config.example.yaml

**Docker**：docker-compose*.yaml, dev-entrypoint.sh, provisioner/

**前端**：组件、i18n、文档内容（约 80 个 .mdx 文件）

**测试**：约 120 个测试文件的 import 路径更新

**文档**：backend/docs/ 下约 25 个文件

</details>

### Phase 2: 内网/离线部署（约 23 个文件）

**新增文件**：
- `backend/packages/harness/ideer/config/network_mode.py`
- `config.intranet.yaml`
- `docker/docker-compose.intranet.yaml`
- `scripts/README-intranet.md`
- `scripts/check-intranet.sh`
- `extensions_config.example.json`

**修改文件**：
- `backend/packages/harness/ideer/skills/types.py`
- `backend/packages/harness/ideer/config/skills_config.py`
- `backend/packages/harness/ideer/config/tool_config.py`
- `backend/packages/harness/ideer/tools/tools.py`
- `scripts/deploy-intranet.sh`
- `scripts/package-intranet-offline.sh`
- `frontend/next.config.js`

### Phase 3: RBAC 权限管理（约 35 个文件）

**新增文件**：
- `backend/app/gateway/routers/admin.py`
- `backend/app/gateway/routers/tools.py`
- `backend/packages/harness/ideer/persistence/models/user.py`（RBAC 模型）
- `backend/packages/harness/ideer/persistence/migrations/versions/16147afec43b_*.py`
- `backend/packages/harness/ideer/persistence/migrations/versions/f3a2b1c4d5e6_*.py`
- `frontend/src/app/workspace/admin/page.tsx`
- `frontend/src/app/workspace/admin/users/page.tsx`
- `frontend/src/app/workspace/admin/departments/page.tsx`
- `frontend/src/app/workspace/admin/tools/page.tsx`
- `frontend/src/core/admin/api.ts`
- `frontend/src/core/admin/types.ts`
- `frontend/src/core/tools/api.ts`
- `frontend/src/core/tools/types.ts`

**修改文件**：
- `backend/app/gateway/authz.py`
- `backend/app/gateway/deps.py`
- `backend/app/gateway/routers/__init__.py`
- `backend/app/gateway/routers/agents.py`
- `backend/app/gateway/routers/skills.py`
- `backend/app/gateway/app.py`
- `frontend/src/components/workspace/workspace-nav-menu.tsx`
- `frontend/src/components/workspace/agents/agent-card.tsx`
- `frontend/src/components/workspace/agents/agent-gallery.tsx`

### Phase 4: 工作流引擎（约 25 个文件）

**新增文件**：
- `backend/packages/harness/ideer/workflows/`（__init__, schema, parser, template, executor, state, store）
- `backend/packages/harness/ideer/workflows/steps/`（__init__, agent_step, tool_step, human_step, condition_step, parallel_step, loop_step, retry_step）
- `backend/packages/harness/ideer/workflows/README.md`
- `backend/packages/harness/ideer/workflows/examples/`（3 个 YAML 示例）
- `backend/packages/harness/ideer/persistence/migrations/versions/d7e0060b1ebc_*.py`
- `backend/packages/harness/ideer/persistence/models/workflow.py`
- `backend/app/gateway/routers/workflows.py`
- `frontend/src/app/workspace/workflows/`（page, [name]/page, [name]/edit/page, new/page）
- `frontend/src/components/workspace/workflows/`（workflow-card, workflow-gallery）
- `frontend/src/core/workflows/`（api, hooks, types, index）
- `workflows/README.md`
- `workflows/example-data-analysis.yaml`

### Phase 5: 工具扩展（约 16 个文件）

**新增文件**：
- `backend/packages/harness/ideer/community/doc_reader/`（__init__, tools, mcp_server, README）
- `backend/packages/harness/ideer/community/code_interpreter/`（__init__, tools, mcp_server, README）
- `backend/packages/harness/ideer/community/data_analyzer/`（__init__, tools, mcp_server, README）
- `backend/packages/harness/ideer/tools/registry.py`

### 测试新增（5 个文件）

- `backend/tests/test_schema_parser.py`（21 个用例）
- `backend/tests/test_template.py`（18 个用例）
- `backend/tests/test_doc_reader.py`（11 个用例）
- `backend/tests/test_code_interpreter.py`（5 个用例）
- `backend/tests/test_data_analyzer.py`（6 个用例）

### 提交记录

```
d1ac4ee4 refactor: rebrand deer-flow/DeerFlow to iDeer/ideer
5265449b feat: add intranet/offline deployment support (Phase 2)
a3e3d3bf revert: remove unnecessary intranet build overrides
5d636c59 feat: add software factory with RBAC (Phase 3)
e27cc99b feat(rbac): wire up real auth dependencies and complete pending items
60fcf44b feat(workflow): implement YAML-based workflow engine with frontend
98e205b7 docs(workflow): add example workflow and README
e3aa7b9f refactor(workflow): persist state to DB, use SubagentExecutor, database-backed human review
d57a02b9 docs(workflow): add README, examples, and unit tests
a548b4db feat(tools): add read_document, code_interpreter, and data_analyzer community tools
9f94aa5d feat(tools): add MCP Server wrappers for Phase 5 tools
5f2b6c5d docs: add platform development summary and update project docs
```
