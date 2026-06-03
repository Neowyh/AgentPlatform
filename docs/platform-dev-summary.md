# 企业内网智能体平台开发总结

## 概述

基于字节跳动开源项目 iDeer（原 deer-flow）智能体框架，通过品牌重命名、内网适配、权限管控、工作流引擎、工具扩展共 5 个阶段的系统性改造，构建了面向企业内网环境的智能体平台。平台具备离线部署能力、RBAC 权限管理、声明式工作流编排、以及文档处理/代码执行/数据分析等企业级工具集，可直接部署在无互联网的内网环境中运行。

---

## Phase 1: 品牌重命名 (deer-flow → iDeer)

**目标**: 将项目从社区版品牌重命名为企业版品牌 iDeer

**改动范围**:
- Python 包名：`deerflow` → `ideer`
- 环境变量：`DEER_FLOW_*` → `IDEER_*`
- Docker 容器/网络/镜像名称
- 前端品牌文本和外部链接
- 配置文件、脚本和文档

**关键数据**: 797 个文件变更，涵盖后端、前端、Docker、文档

---

## Phase 2: 内网适配 (离线化改造)

**目标**: 使平台可在无互联网的内网环境部署运行

**功能**:
- 网络模式自动检测（`network_mode.py`）
- 工具加载过滤：`requires_network` 字段跳过需要联网的工具
- Skill 加载过滤：`requires_internet` 字段跳过需要联网的技能
- 前端外部资源本地化（Google Fonts、CDN 图片等）
- Docker Compose 内网专用配置

**关键文件**:
- `backend/packages/harness/ideer/network_mode.py`
- `config.intranet.yaml`
- `docker/docker-compose.intranet.yaml`

---

## Phase 3: 软件工厂 (RBAC 权限 + 管理后台)

**目标**: 提供企业级的用户权限管理和资源管控能力

**功能**:
- RBAC 权限模型：4 级角色（`super_admin` > `department_admin` > `user` > `viewer`）
- 数据库模型：`departments`（部门）+ `users_ext`（用户扩展）表
- Admin API：用户/部门/Agent/Skill/Tool 的 CRUD 接口
- 前端管理后台：仪表盘、用户管理、部门管理、工具管理页面
- Agent 可见性控制：`public` / `private` / `restricted`
- Alembic 数据库迁移支持

**RBAC 权限模式示例**（来自 `admin.py`）:

```python
from app.gateway.authz import get_current_rbac_user, require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    department_id: str | None = None
```

**关键文件**:
- `backend/packages/harness/ideer/persistence/models/rbac.py`
- `backend/app/gateway/routers/admin.py`
- `backend/app/gateway/authz.py`（`get_current_rbac_user` 依赖）
- `frontend/src/app/admin/`（管理后台页面）

---

## Phase 4: 工作流引擎 (YAML/DSL 编排)

**目标**: 提供声明式的多步骤工作流编排能力

**功能**:
- YAML DSL 定义工作流，支持 6 种步骤类型：
  - `agent`：调用 Agent（通过 SubagentExecutor，完整工具/中间件能力）
  - `tool`：直接调用工具
  - `human_review`：人工审批（数据库轮询，多进程安全）
  - `condition`：条件分支
  - `parallel`：并行执行
  - `loop`：循环遍历
- 模板引擎：`{{inputs.xxx}}` 和 `{{steps.xxx.output}}` 变量引用，类型保留
- WorkflowStore：数据库持久化运行状态，支持断点恢复
- 8 个 API 端点 + React 前端（列表/详情/编辑/新建）
- 39 个单元测试

**工作流 Schema 定义**（来自 `schema.py`）:

```python
class StepType(StrEnum):
    AGENT = "agent"
    TOOL = "tool"
    HUMAN_REVIEW = "human_review"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"

class WorkflowDef(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    inputs: dict[str, InputParam] = Field(default_factory=dict)
    steps: list[StepDef] = Field(default_factory=list)
    triggers: list[dict[str, Any]] | None = None
```

**YAML DSL 示例**:

```yaml
name: research_pipeline
description: 调研-分析-审批流水线
version: "1.0"

inputs:
  topic:
    type: string
    required: true
    description: "调研主题"

steps:
  - id: research
    type: agent
    agent: researcher
    prompt: "请调研以下主题：{{inputs.topic}}"

  - id: analyze
    type: agent
    agent: analyzer
    prompt: "请分析以下调研结果：{{steps.research.output}}"

  - id: review
    type: human_review
    message: "请审批分析报告"
    approvers:
      - admin@example.com
```

**API 端点列表**:

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| `GET` | `/api/workflows` | 列出所有工作流 | 公开 |
| `GET` | `/api/workflows/{name}` | 获取工作流详情 | 公开 |
| `POST` | `/api/workflows` | 创建工作流 | 部门管理员 / 超级管理员 |
| `PUT` | `/api/workflows/{name}` | 更新工作流 YAML | 部门管理员 / 超级管理员 |
| `DELETE` | `/api/workflows/{name}` | 删除工作流 | 超级管理员 |
| `POST` | `/api/workflows/{name}/run` | 启动一次工作流执行 | 公开 |
| `GET` | `/api/workflows/{name}/runs` | 列出运行历史 | 公开 |
| `GET` | `/api/workflows/{name}/runs/{run_id}` | 查询运行状态详情 | 公开 |

**状态流转**:

```
pending → running → completed
              ↓ (human_review)
         waiting_human → running
              ↓ (异常)
           failed
```

**关键文件**:
- `backend/packages/harness/ideer/workflows/`（schema, parser, template, executor, store, steps/）
- `backend/app/gateway/routers/workflows.py`
- `frontend/src/app/workspace/workflows/`

---

## Phase 5: 工具扩展 (文档处理 + 代码执行)

**目标**: 扩展 Agent 的工具能力，覆盖企业常见场景

**新增工具**:

| 工具 | 功能 | 技术实现 |
|------|------|----------|
| `read_document` | PDF/Word/Excel/PPT → Markdown 文本提取 | pymupdf4llm + MarkItDown |
| `code_interpreter` | Python/JavaScript 代码安全执行 | subprocess + 沙箱隔离 |
| `data_analyzer` | CSV/Excel/JSON 数据统计分析 | pandas（summary/describe/correlation） |

**工具详细说明**:

### read_document（文档读取）

支持 `.pdf`、`.docx`、`.doc`、`.xlsx`、`.xls`、`.pptx`、`.ppt` 格式，将文档转换为 Markdown 文本。PDF 文件支持指定页面范围提取（如 `"1-5"` 或 `"3"`），通过 `pymupdf4llm` 实现精确页面提取，其他格式通过 `MarkItDown` 转换。输出自动截断至 50,000 字符，并附带文件元信息头部。

### code_interpreter（代码解释器）

支持 Python 和 JavaScript 代码的安全执行。代码写入临时文件后通过 `subprocess` 运行，执行完毕自动清理。支持超时控制（默认 60 秒，最大 300 秒），输出采用中间截断策略（保留首尾各 50%），返回结构化的 stdout/stderr/exit_code。

### data_analyzer（数据分析器）

支持 CSV、Excel（`.xlsx`/`.xls`）、JSON 文件的统计分析，提供三种分析模式：
- `summary`：数据概览（行列数、列类型、缺失值、前 5 行预览）
- `describe`：数值列统计摘要 + 分类列频次统计
- `correlation`：数值列相关性矩阵，自动标注强相关（|r| > 0.7）列对

**两种加载方式**:
- **Community Tool**：`config.yaml` 中配置 `use` 路径，适合单体部署
- **MCP Server**：`extensions_config.json` 中注册，适合独立部署

**关键文件**:
- `backend/packages/harness/ideer/community/doc_reader/`
- `backend/packages/harness/ideer/community/code_interpreter/`
- `backend/packages/harness/ideer/community/data_analyzer/`

---

## 技术架构总结

分层说明本次改造在 iDeer 原有架构上的叠加：

```
┌─────────────────────────────────────────────┐
│  前端层 (Next.js)                            │
│  管理后台 + 工作流 + Agent 对话               │
├─────────────────────────────────────────────┤
│  API 网关层 (FastAPI)                        │
│  RBAC 权限 + 8 Workflow API + Admin API      │
├─────────────────────────────────────────────┤
│  业务逻辑层                                   │
│  工作流引擎 + 工具扩展 + Agent 编排            │
├─────────────────────────────────────────────┤
│  基础设施层 (iDeer 原有)                      │
│  Sandbox + MCP + Skills + Memory + Persistence│
└─────────────────────────────────────────────┘
```

**各层说明**:

| 层级 | 技术栈 | 本次改造内容 |
|------|--------|-------------|
| 前端层 | Next.js + React | 管理后台页面、工作流编辑器、品牌重命名 |
| API 网关层 | FastAPI | RBAC 权限中间件、8 个 Workflow API、Admin CRUD API |
| 业务逻辑层 | Python | YAML DSL 解析引擎、模板引擎、3 个 Community Tool |
| 基础设施层 | iDeer 框架 | 沿用 Sandbox、MCP、Skills、Memory、Persistence |

---

## 测试覆盖

| 模块 | 测试文件 | 测试数量 |
|------|----------|----------|
| Schema + Parser | `test_schema_parser.py` | 21 |
| Template Engine | `test_template.py` | 18 |
| read_document | `test_doc_reader.py` | 11 |
| code_interpreter | `test_code_interpreter.py` | 5 |
| data_analyzer | `test_data_analyzer.py` | 6 |
| **合计** | | **61** |

---

## 提交记录

```
9f94aa5d feat(tools): add MCP Server wrappers for Phase 5 tools
a548b4db feat(tools): add read_document, code_interpreter, and data_analyzer
d57a02b9 docs(workflow): add README, examples, and unit tests
e3aa7b9f refactor(workflow): persist state to DB, use SubagentExecutor
98e205b7 docs(workflow): add example workflow and README
60fcf44b feat(workflow): implement YAML-based workflow engine
e27cc99b feat(rbac): wire up real auth dependencies
5d636c59 feat: add software factory with RBAC (Phase 3)
```
