# 文档建设方案

## 概述

当前文档主要集中在 `docs/` 目录下的开发文档，缺少面向用户和运维的文档。本方案补充 API 文档、用户手册和部署文档。

## 文档体系结构

```
docs/
├── api-reference/           # API 参考文档（待创建）
│   ├── README.md           # API 概述
│   ├── admin-api.md        # Admin API
│   ├── workflow-api.md     # Workflow API
│   └── agent-api.md        # Agent API
├── user-manual/             # 用户使用手册（待创建）
│   ├── README.md           # 快速入门
│   ├── workflows.md        # 工作流使用
│   ├── tools.md            # 工具使用
│   └── admin.md            # 管理后台
├── deployment/              # 部署文档（已有，待补充）
│   └── ...
└── optimization/            # 优化方案（本文档所在目录）
```

---

## 1. API 文档（Swagger/OpenAPI）

### 1.1 目标

- 自动生成 API 文档
- 提供交互式 API 测试界面

### 1.2 实现方式

FastAPI 自动生成 Swagger UI，通过代码注释和 Pydantic 模型生成文档。

### 1.3 配置

在 `backend/app/gateway/app.py` 的 `create_app()` 中配置：

```python
"""backend/app/gateway/app.py"""

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi


def create_app() -> FastAPI:
    app = FastAPI(
        title="iDeer Enterprise Platform API",
        description="""
# iDeer Enterprise Intranet Agent Platform API

## Authentication

All API endpoints require authentication via Bearer token:

```
Authorization: Bearer <your_token>
```

## Roles & Permissions

| Role | Description |
|------|-------------|
| `super_admin` | Full access to all resources |
| `department_admin` | Manage department users and resources |
| `user` | Use assigned agents and tools |
| `viewer` | Read-only access |

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
        """,
        version="1.0.0",
        docs_url=None,  # Disable default docs
        redoc_url=None,  # Disable default redoc
    )

    # ... existing middleware setup ...

    # Custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        )

    return app
```

### 1.4 API 路由文档增强

在路由函数中添加详细的 docstring 和 response_model：

```python
"""backend/app/gateway/routers/admin.py"""

from pydantic import BaseModel, Field
from typing import Optional, List


class UserResponse(BaseModel):
    """User response model."""
    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="User login name")
    role: str = Field(..., description="User role")
    department_id: Optional[str] = Field(None, description="Department ID")
    disabled: bool = Field(False, description="Whether user is disabled")


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List all users",
    description="Retrieve a paginated list of users. Requires super_admin role.",
    responses={
        200: {"description": "Users retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    }
)
async def list_users(
    department_id: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[str] = Query(None, description="Filter by role"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Skip N results"),
):
    """
    List all users with optional filters.

    - **department_id**: Filter users by department
    - **role**: Filter users by role
    - **limit**: Maximum number of users (1-200)
    - **offset**: Pagination offset
    """
    pass
```

### 1.5 访问文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## 2. 用户使用手册

### 2.1 快速入门

```markdown
# iDeer 快速入门

## 1. 访问平台

打开浏览器，访问系统管理员提供的 URL。

## 2. 登录系统

使用管理员提供的账号密码登录。

## 3. 创建第一个工作流

### 3.1 进入工作流页面

点击左侧菜单的 "Workflows" 进入工作流管理页面。

### 3.2 创建新工作流

点击 "New Workflow" 按钮，输入以下 YAML 内容：

```yaml
name: hello_world
description: Hello World workflow
version: "1.0"

steps:
  - id: greet
    type: agent
    agent: assistant
    prompt: "Say hello to the world"
```

### 3.3 运行工作流

点击 "Run" 按钮，等待执行完成。

### 3.4 查看结果

在运行历史中点击最新的运行，查看输出结果。
```

### 2.2 工作流 YAML 语法

```markdown
# YAML 工作流语法

## 基本结构

```yaml
name: workflow_name
description: 工作流描述
version: "1.0"

inputs:
  param1:
    type: string
    required: true

steps:
  - id: step1
    type: agent
    agent: agent_name
    prompt: "提示词"
```

## 步骤类型

| 类型 | 说明 | 必填字段 |
|------|------|----------|
| `agent` | 调用 AI Agent | `agent`, `prompt` |
| `tool` | 调用工具 | `tool` |
| `human_review` | 人工审批 | `message` |
| `condition` | 条件分支 | `expression`, `then` |
| `parallel` | 并行执行 | `steps` |
| `loop` | 循环遍历 | `items`, `steps` |

## 模板变量

| 语法 | 说明 |
|------|------|
| `{{inputs.xxx}}` | 引用输入参数 |
| `{{steps.xxx.output}}` | 引用步骤输出 |
| `{{_loop.item}}` | 循环当前项 |
| `{{_loop.index}}` | 循环当前索引 |
```

### 2.3 工具使用

```markdown
# 文档读取工具 (read_document)

支持 PDF、Word、Excel、PPT 文件，转换为 Markdown 文本。

## 使用方法

```yaml
- id: read_doc
  type: tool
  tool: read_document
  params:
    file_path: "/mnt/user-data/report.pdf"
    pages: "1-5"  # PDF 可选，指定页面范围
```

# 代码解释器 (code_interpreter)

支持 Python 和 JavaScript 代码安全执行。

```yaml
- id: run_code
  type: tool
  tool: code_interpreter
  params:
    code: "print('Hello, World!')"
    language: "python"
    timeout: 60
```

# 数据分析器 (data_analyzer)

支持 CSV、Excel、JSON 文件的统计分析。

```yaml
- id: analyze
  type: tool
  tool: data_analyzer
  params:
    file_path: "/mnt/user-data/data.csv"
    mode: "summary"  # summary / describe / correlation
```
```

---

## 3. 部署运维文档

### 3.1 内网部署指南

```markdown
# 内网环境部署指南

## 前置条件

### 硬件要求

| 资源 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8 核+ |
| 内存 | 8 GB | 16 GB+ |
| 磁盘 | 50 GB | 100 GB+ |

### 软件要求

- **操作系统**: CentOS 7+ / Ubuntu 20.04+ / RHEL 8+
- **Python**: 3.12+
- **Node.js**: 18+
- **数据库**: SQLite 3.35+（默认）/ PostgreSQL 14+（可选）

## 部署步骤

### 1. 环境准备

```bash
# 配置 pip 内网镜像
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << EOF
[global]
index-url = https://your-mirror.example.com/pypi/simple/
trusted-host = your-mirror.example.com
EOF

# 配置 npm 内网镜像
npm config set registry https://your-mirror.example.com/npm/
```

### 2. 获取代码

```bash
git clone https://your-git.example.com/ideer/ideer-platform.git
cd ideer-platform
```

### 3. 配置应用

```bash
cp config.intranet.yaml config.yaml
# 编辑 config.yaml，配置内网模型地址
```

### 4. 安装依赖

```bash
# 后端
uv sync

# 前端
cd frontend && pnpm install && cd ..
```

### 5. 启动服务

```bash
# 使用启动脚本（推荐）
./scripts/start-local.sh

# 或手动启动
make start
```

### 6. 验证部署

```bash
curl http://localhost:2026/health
# 预期输出: {"status": "ok"}
```
```

### 3.2 故障排除

```markdown
# 故障排除指南

## 服务无法启动

1. 检查端口占用: `lsof -i :8000`
2. 检查日志: `tail -f logs/*.log`
3. 检查配置: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`

## 数据库连接失败

1. 检查数据库文件: `ls -la data/ideer.db`（SQLite）
2. 检查配置: `grep "database" config.yaml`

## 模型服务连接失败

1. 检查模型地址: `curl http://your-vllm:8000/health`
2. 检查 API Key: `echo $VLLM_API_KEY`
```

---

## 4. 文档维护

### 4.1 更新流程

1. 代码变更时同步更新文档
2. 定期审查文档准确性
3. 收集用户反馈持续改进

### 4.2 文档规范

- 使用 Markdown 格式
- 代码示例使用语法高亮
- 提供完整可运行的示例

---

## 5. 总结

### 5.1 文档清单

| 文档类型 | 数量 | 状态 |
|----------|------|------|
| API 文档 | Swagger 自动生成 | 待配置 |
| 用户手册 | 5+ | 待编写 |
| 部署文档 | 3+ | 待补充 |

### 5.2 工作量估算

| 任务 | 预计工作量 |
|------|------------|
| Swagger 配置 | 0.5 天 |
| 用户手册 | 4-5 天 |
| 部署文档 | 2-3 天 |
| **总计** | **7-9 天** |
