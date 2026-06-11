# 已知问题与待办事项

本文档记录代码审查中发现的、需要架构决策才能修复的问题。每个问题包含现象、根因、影响范围和建议方案。

---

## 1. 工作流条件表达式永远为真

**严重程度**: HIGH | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:117`

### 现象

工作流 YAML 中的 `condition` 步骤写比较表达式时，无论实际值是多少，`then` 分支永远执行：

```yaml
- id: check_score
  type: condition
  expression: "{{steps.analysis.output.score}} > 80"
  then: high_score_branch
  else: low_score_branch
```

当 `steps.analysis.output.score` 为 `42` 时，预期走 `low_score_branch`，实际走 `high_score_branch`。

### 根因

`_execute_condition` 方法使用 `render_value()` 替换模板变量后直接 `bool()` 转换：

```python
# executor.py:117
result = bool(render_value(step.expression or "true", context))
```

`render_value` 只做字符串替换，不解析运算符。表达式 `42 > 80` 被替换为字符串 `"42 > 80"`，Python 中 `bool("42 > 80")` 永远为 `True`（非空字符串）。

### 影响

- 所有使用比较表达式的 `condition` 步骤逻辑错误
- 无法实现基于数值/字符串的条件分支
- `then` 分支无条件执行，`else` 分支永远不会执行（除非表达式为空字符串）

### 建议方案

**方案 A — 使用 `asteval` 库**（推荐）

```python
from aeval import aeval

def evaluate_condition(expression: str, context: dict) -> bool:
    """安全求值条件表达式。"""
    # 将模板变量替换为实际值
    rendered = render_value(expression, context)
    # aeval 不支持 import、exec 等危险操作
    try:
        result = aeval(rendered)
        return bool(result)
    except Exception:
        logger.warning("Condition expression failed: %s", rendered)
        return False
```

优点：安全（无 `eval`）、支持比较运算符、纯 Python 实现
缺点：额外依赖

**方案 B — 简单比较解析器**

自己实现一个只支持 `>, <, >=, <=, ==, !=, in, not in, and, or, not` 的解析器：

```python
import re
import operator

OPS = {
    ">=": operator.ge, "<=": operator.le,
    "!=": operator.ne, "==": operator.eq,
    ">": operator.gt, "<": operator.lt,
}

def evaluate_condition(expression: str, context: dict) -> bool:
    rendered = render_value(expression, context)
    for op_str, op_func in OPS.items():
        if op_str in rendered:
            left, right = rendered.split(op_str, 1)
            left, right = left.strip(), right.strip()
            # 尝试类型转换
            try:
                left = float(left)
                right = float(right)
            except ValueError:
                pass
            return op_func(left, right)
    return bool(rendered)
```

优点：无外部依赖、可完全控制行为
缺点：不支持复合表达式（`a > 1 and b < 5`）

**方案 C — 引入 Jinja2 表达式**

模板引擎已使用 `{{...}}` 语法，可直接使用 Jinja2 的 `{% if %}` 语法：

```yaml
- id: check_score
  type: condition
  expression: "{{steps.analysis.output.score > 80}}"
```

Jinja2 会在模板内部完成比较，输出 `"True"` 或 `"False"`。

优点：与现有模板语法一致
缺点：需要改 `render_value` 支持 Jinja2 表达式模式

### 待办

- [ ] 选择表达式引擎方案
- [ ] 实现 `evaluate_condition` 函数
- [ ] 更新 `_execute_condition` 使用新函数
- [ ] **同步修复 `_should_run` 方法**（`executor.py:70`）：同样的 `bool(render_value(...))` 问题也影响步骤级 `condition` 字段。`condition: "false"` 或 `condition: "{{some_var}}"` 永远为 True
- [ ] 添加条件表达式的单元测试（比较、逻辑运算、边界值）
- [ ] 更新文档说明支持的表达式语法

---

## 2. code_interpreter 无沙箱隔离

**严重程度**: CRITICAL | **模块**: Community Tools | **文件**: `backend/packages/harness/ideer/community/code_interpreter/tools.py:86`

### 现象

`code_interpreter` 工具执行用户/Agent 提供的任意 Python/JavaScript 代码时，以父进程相同的权限运行。恶意代码可以：

1. 读取系统敏感文件（`/etc/shadow`、`/proc/self/environ`）
2. 通过 `os.environ` 获取所有环境变量（API Key、数据库密码）
3. 消耗全部内存/CPU 导致宿主机 OOM
4. 建立反向 shell 获取持久化访问
5. 写入文件系统安装后门

### 根因

```python
# tools.py:86
result = subprocess.run(
    [interpreter, temp_file],
    capture_output=True,
    text=True,
    timeout=timeout,
    env=os.environ,  # ← 完整继承父进程环境变量
)
```

问题清单：

| 问题 | 描述 |
|------|------|
| 无沙箱 | 子进程拥有与父进程相同的文件系统、网络、进程权限 |
| 无内存限制 | 只有 `timeout`（墙钟时间），无 `ulimit` 或 cgroup 限制 |
| 环境变量泄露 | `os.environ` 包含所有 API Key、数据库凭据 |
| 无文件系统隔离 | 可读写任意路径 |
| 无网络隔离 | 可建立出站连接 |

### 影响

- 生产环境中的 API Key、数据库密码可被恶意代码窃取
- 恶意代码可消耗全部服务器资源
- 内网环境中可扫描/攻击其他内部服务

### 建议方案

**方案 A — Docker 容器隔离**（推荐）

```python
import docker

def run_code_sandboxed(code: str, language: str, timeout: int) -> dict:
    client = docker.from_env()
    container = client.containers.run(
        "ideer-code-sandbox:latest",
        command=f"echo '{code}' | {'python3' if language == 'python' else 'node'}",
        detach=True,
        mem_limit="256m",           # 内存限制
        cpu_period=100000,
        cpu_quota=50000,            # 50% CPU
        network_disabled=True,      # 禁用网络
        read_only=True,             # 只读文件系统
        tmpfs={"/tmp": "size=64m"}, # 限制临时文件
        environment={},             # 空环境变量
    )
    try:
        result = container.wait(timeout=timeout)
        stdout = container.logs(stdout=True, stderr=False).decode()
        stderr = container.logs(stdout=False, stderr=True).decode()
        return {"stdout": stdout, "stderr": stderr, "exit_code": result["StatusCode"]}
    finally:
        container.remove(force=True)
```

优点：完全隔离、成熟方案、可精确控制资源
缺点：需要 Docker daemon、镜像构建、启动延迟（~1-2s）

**方案 B — Firecracker/gVisor 微虚拟机**

比 Docker 更强的隔离（内核级别），适合多租户场景。

优点：内核级隔离
缺点：部署复杂、需要 KVM 支持

**方案 C — 资源限制 + 环境变量白名单**（临时方案）

```python
import resource
import os

def _build_safe_env() -> dict:
    """只传递必要的环境变量。"""
    safe_keys = {"PATH", "HOME", "LANG", "LC_ALL", "TZ"}
    return {k: v for k, v in os.environ.items() if k in safe_keys}

def _set_limits(timeout: int):
    """设置进程资源限制。"""
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))  # 256MB
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))  # 10MB

result = subprocess.run(
    [interpreter, temp_file],
    capture_output=True,
    text=True,
    timeout=timeout,
    env=_build_safe_env(),  # 白名单环境变量
    preexec_fn=lambda: _set_limits(timeout),  # 资源限制
)
```

优点：无外部依赖、改动小
缺点：`preexec_fn` 不支持 asyncio、`resource` 仅限 Unix、无法阻止网络访问

### 待办

- [ ] 选择沙箱方案（推荐 Docker 容器）
- [ ] 构建 `ideer-code-sandbox` 镜像（预装 Python + Node.js + 常用库）
- [ ] 实现 `run_code_sandboxed` 函数
- [ ] 替换现有 `subprocess.run` 调用
- [ ] 配置资源限制参数（可通过 config.yaml 调整）
- [ ] 添加沙箱逃逸测试
- [ ] **临时措施**：立即实现方案 C 的环境变量白名单

---

## 3. doc_reader / data_analyzer 无路径遍历防护

**严重程度**: HIGH | **模块**: Community Tools | **文件**:
- `backend/packages/harness/ideer/community/doc_reader/tools.py:120`
- `backend/packages/harness/ideer/community/data_analyzer/tools.py:35`

### 现象

`read_document` 和 `data_analyzer` 工具接受 `file_path` 参数直接用于文件操作，无任何路径校验：

```python
# doc_reader/tools.py:120
def read_document(file_path: str, ...) -> str:
    path = Path(file_path)  # 直接使用用户输入
    if not path.exists():
        return f"Error: File not found: {file_path}"
    content = convert_to_markdown(path)
```

攻击者可以：

1. **路径遍历**：`file_path="/etc/passwd"` 读取系统文件
2. **符号链接攻击**：在上传目录创建指向 `/etc/shadow` 的符号链接
3. **OOM 攻击**：`file_path="/data/huge.xlsx"`（5GB 文件导致内存耗尽）
4. **密钥泄露**：`file_path="/proc/self/environ"` 读取环境变量

### 根因

1. 无路径白名单/沙箱目录限制
2. 无 `Path.resolve()` + `is_relative_to()` 校验
3. 无文件大小预检查
4. 两种部署模式（Community Tool / MCP Server）各维护一份代码，修复需要同步改两处

### 影响

- 服务器上任意文件可被读取（以 Python 进程的权限）
- 环境变量中的 API Key、数据库密码可被泄露
- 大文件可导致服务 OOM

### 建议方案

**方案 A — 上传目录白名单**（推荐）

```python
from pathlib import Path

# 配置化的允许目录
ALLOWED_DIRS = [
    Path("/data/uploads"),
    Path("/data/workspace"),
]

def validate_file_path(file_path: str) -> Path:
    """校验文件路径，防止路径遍历。"""
    path = Path(file_path).resolve()

    # 检查是否在允许的目录下
    if not any(path.is_relative_to(d) for d in ALLOWED_DIRS):
        raise ValueError(f"Access denied: {file_path} is outside allowed directories")

    # 检查文件大小
    if path.exists() and path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {path.stat().st_size} bytes (max {MAX_FILE_SIZE})")

    return path
```

优点：简单明确、可配置
缺点：需要明确"允许的目录"是哪些

**方案 B — 文件类型 + 大小双重限制**

```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",  # doc_reader
    ".csv", ".json", ".xlsx", ".xls",                             # data_analyzer
}

def validate_file_path(file_path: str) -> Path:
    path = Path(file_path).resolve()

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    if path.exists() and path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {path.stat().st_size} bytes")

    return path
```

优点：防止读取非文档文件
缺点：不限制目录，仍可遍历到系统上的 `.json` 文件

**方案 C — 临时文件目录 + 自动清理**

前端上传文件后存储到专用临时目录，工具只能访问该目录：

```python
UPLOAD_DIR = Path("/tmp/ideer-uploads")

def validate_file_path(file_path: str) -> Path:
    path = Path(file_path).resolve()

    if not path.is_relative_to(UPLOAD_DIR.resolve()):
        raise ValueError(f"Access denied: file must be in {UPLOAD_DIR}")

    return path
```

优点：最强隔离
缺点：需要改前端上传逻辑，确保文件存到正确位置

### 待办

- [ ] 确定允许的文件目录（与前端上传路径对齐）
- [ ] 实现 `validate_file_path` 函数到共享模块
- [ ] doc_reader 的 `tools.py` 和 `mcp_server.py` 同步修改
- [ ] data_analyzer 的 `tools.py` 和 `mcp_server.py` 同步修改
- [ ] 添加文件大小限制（可通过 config.yaml 配置）
- [ ] 添加路径遍历的单元测试（`../`、符号链接、绝对路径）
- [ ] **临时措施**：立即添加 `Path.resolve()` + `is_relative_to()` 校验

---

## 4. Community Tools 代码重复 (tools.py / mcp_server.py)

**严重程度**: MEDIUM | **模块**: Community Tools | **文件**:
- `backend/packages/harness/ideer/community/doc_reader/tools.py` + `mcp_server.py`
- `backend/packages/harness/ideer/community/code_interpreter/tools.py` + `mcp_server.py`
- `backend/packages/harness/ideer/community/data_analyzer/tools.py` + `mcp_server.py`

### 现象

每个 Community Tool 的核心业务逻辑在 `tools.py`（LangChain 工具模式）和 `mcp_server.py`（MCP Server 模式）之间几乎完全复制。三个工具共约 500+ 行重复代码。

以 `doc_reader` 为例，`_truncate_output`、`_get_page_count`、`_parse_page_range`、`_extract_pdf_pages` 和 `read_document` 的完整处理流程在两个文件中完全相同。

### 根因

两种部署模式（Community Tool / MCP Server）在设计时各自独立实现，没有抽取共享的核心逻辑模块。

### 影响

- Bug 修复需要同步改两处，遗漏其一将导致两种部署模式行为不一致
- 安全补丁（如沙箱限制、输出清理）可能只应用到一个版本
- 新增功能（如 OCR 支持）需要在两个文件中重复实现

### 建议方案

将核心逻辑抽取到 `core.py` 模块，`tools.py` 和 `mcp_server.py` 各自只做薄包装：

```python
# doc_reader/core.py
async def read_document(file_path: str, page_range: str | None = None) -> str:
    """Core logic, used by both LangChain tool and MCP server."""
    ...

# doc_reader/tools.py
@tool("read_document")
async def read_document_tool(file_path: str, page_range: str | None = None) -> str:
    return await read_document(file_path, page_range)

# doc_reader/mcp_server.py
@server.call_tool()
async def handle_read_document(params):
    return await read_document(params["file_path"], params.get("page_range"))
```

### 待办

- [ ] 为每个工具创建 `core.py` 模块
- [ ] 将 `tools.py` 和 `mcp_server.py` 改为薄包装
- [ ] 确保两种模式的行为完全一致

---

## 5. 工作流条件步骤 goto 分支为死代码

**严重程度**: HIGH | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:126`

### 现象

`_execute_condition` 方法在条件表达式求值后，如果 `then`/`else` 是字符串（步骤 ID 引用），返回 `f"goto:{step_id}"` 格式的字符串。但主执行循环 `run()` 从未处理这种 `goto:` 标记——它只是将字符串存储为步骤输出，然后继续执行下一个顺序步骤。

```yaml
- id: check_score
  type: condition
  expression: "{{inputs.score}} > 80"
  then: high_score_branch    # 字符串步骤 ID
  else: low_score_branch     # 字符串步骤 ID
```

当 `inputs.score` 为 `42` 时，`_execute_condition` 返回 `"goto:low_score_branch"`，但执行器忽略这个值，继续执行列表中的下一个步骤。

### 根因

`run()` 方法的主循环是纯线性的——遍历 `self.workflow.steps` 列表，没有跳转机制：

```python
for step in self.workflow.steps:
    if not self._should_run(step, state):
        state.set_step_result(step.id, status="skipped")
        continue
    # ... 执行步骤 ...
```

`goto:` 标记被存储为步骤输出但从未被消费。

### 影响

- 使用字符串 `then`/`else` 目标的条件分支完全不工作
- 仅当 `then`/`else` 是内联 `StepDef` 对象时分支才有效（通过递归调用 `_execute_step`）
- 用户按照文档编写的条件分支工作流静默地忽略分支逻辑
- **嵌套上下文同样受影响**：当 condition 步骤嵌套在 loop/parallel 中时，`condition_step.py` 返回 `{"goto": branch, "result": result}` 字典，但 `loop_step.py` 和 `parallel_step.py` 不检查此返回值，直接存储为输出，目标分支永远不会执行

### 建议方案

**方案 A — 步骤 ID 索引 + 跳转**（推荐）

将步骤列表转换为 `dict[id, StepDef]` 索引，实现 goto 语义：

```python
steps_by_id = {s.id: s for s in self.workflow.steps}
current_id = self.workflow.steps[0].id

while current_id is not None:
    step = steps_by_id[current_id]
    result = await self._execute_step(step, state)
    if isinstance(result, str) and result.startswith("goto:"):
        current_id = result[5:]  # 跳转到目标步骤
    else:
        # 找到下一个步骤
        idx = next(i for i, s in enumerate(self.workflow.steps) if s.id == current_id)
        current_id = self.workflow.steps[idx + 1].id if idx + 1 < len(self.workflow.steps) else None
```

**方案 B — 禁用字符串目标**

在 parser 层面拒绝字符串 `then`/`else`，只允许内联 StepDef。

### 待办

- [ ] 选择方案（推荐方案 A）
- [ ] 实现步骤索引和跳转逻辑
- [ ] 添加条件分支的集成测试
- [ ] 更新文档说明支持的分支语法

---

## 6. 并行步骤共享可变状态存在竞争条件

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:42`

### 现象

`execute_parallel_step` 使用 `asyncio.gather` 并发执行多个子步骤，但所有子步骤共享同一个 `WorkflowState` 对象。当子步骤修改 `state.inputs`、`state.steps` 或 `state.loop_vars` 时，其他正在运行的子步骤可以看到这些中间修改。

### 根因

```python
async def _run_sub(sub_def):
    result = await execute_step(sub_type, sub_def, state)  # 共享 state
    state.set_step_result(sub_id, status="completed", output=result)  # 无锁写入

pairs = await asyncio.gather(*[_run_sub(s) for s in sub_steps])
```

`asyncio.gather` 在同一个事件循环中并发运行，`set_step_result` 和 `get_context` 之间没有同步机制。

### 影响

- 包含 loop 子步骤的并行步骤会相互覆盖 `state.loop_vars`
- 并行子步骤读取 `state.get_context()` 可能看到不一致的中间状态
- 由于 asyncio 是单线程的，实际数据损坏的概率较低（只在 await 点切换），但逻辑正确性无法保证

### 建议方案

为每个并行子步骤创建独立的 state 快照：

```python
import copy

async def _run_sub(sub_def):
    local_state = copy.deepcopy(state)  # 独立副本
    result = await execute_step(sub_type, sub_def, local_state)
    state.set_step_result(sub_id, status="completed", output=result)  # 只写结果
    return sub_id, result
```

### 待办

- [ ] 实现 state 快照机制
- [ ] 确保快照不影响结果收集
- [ ] 添加并发安全的单元测试

---

## 7. 工作流存储 DB 未初始化处理不一致

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:28`

### 现象

`WorkflowStore` 的不同方法对"数据库未初始化"（`get_session_factory()` 返回 `None`）的处理不一致：

| 方法 | 行为 |
|------|------|
| `save_workflow` | 抛出 `RuntimeError` |
| `save_run_state` | 抛出 `RuntimeError` |
| `load_workflow` | 静默返回 `None` |
| `list_workflows` | 静默返回 `[]` |
| `list_runs` | 静默返回 `([], 0)` |
| `delete_workflow` | 静默返回 `False` |
| `update_run_status` | 静默返回 `None` |
| `save_review_result` | 静默返回 `False` |

### 根因

各方法独立实现，没有统一的错误处理策略。

### 影响

- 调用方无法区分"数据不存在"和"数据库故障"
- `load_workflow` 返回 `None` 会被解释为"工作流不存在"，掩盖真实的基础设施问题
- 运维人员可能在数据库宕机时看到空列表而非错误信息

### 建议方案

统一所有方法的错误处理：当 `sf is None` 时抛出 `RuntimeError("Database not initialized")`。

### 待办

- [ ] 统一所有方法的 `sf is None` 处理为 `raise RuntimeError`
- [ ] 更新调用方处理 `RuntimeError`

---

## 8. update_user_role 缺少行锁导致并发降级风险

**严重程度**: LOW | **模块**: Admin API | **文件**: `backend/app/gateway/routers/admin.py:133`

### 现象

`update_user_role` 在降级 super_admin 前检查剩余数量，但使用普通 `SELECT COUNT(*)` 而非 `SELECT ... FOR UPDATE`。两个并发请求可能同时读到 `count=2`，都通过检查，然后都执行降级，导致系统中 zero 个 super_admin。

### 根因

```python
count_stmt = select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.SUPER_ADMIN)
super_admin_count = (await session.execute(count_stmt)).scalar() or 0
if super_admin_count <= 1:
    raise HTTPException(status_code=400, detail="Cannot remove the last super_admin")
# ... 无 FOR UPDATE 锁 ...
user.role = body.role
await session.commit()
```

### 影响

- 极端并发场景下可能降级所有 super_admin
- 恢复需要直接数据库操作

### 建议方案

使用 `SELECT ... FOR UPDATE` 行锁：

```python
count_stmt = (
    select(func.count())
    .select_from(UserModel)
    .where(UserModel.role == UserRole.SUPER_ADMIN)
    .with_for_update()
)
```

### 待办

- [ ] 添加 `with_for_update()` 到计数查询
- [ ] 测试并发降级场景

---

## 9. 前端 Admin API 缺少分页参数

**严重程度**: LOW | **模块**: 前端 Admin API | **文件**: `frontend/src/core/admin/api.ts`

### 现象

后端 Admin API 的 `listUsers` 和 `listDepartments` 端点支持 `limit` 和 `offset` 分页参数，但前端 API 函数没有传递这些参数。

```typescript
// 当前实现
export async function listUsers(params?: {
  department_id?: string;
  role?: string;
}): Promise<{ users: User[]; total: number }> {
  // 缺少 limit 和 offset 参数
}

export async function listDepartments(): Promise<{
  departments: Department[];
  total: number;
}> {
  // 缺少 limit 和 offset 参数
}
```

### 根因

前端 API 函数在实现时没有完全对齐后端 API 的参数定义。

### 影响

- 无法实现分页加载，当用户/部门数量较多时可能导致性能问题
- 前端无法控制每次请求的数据量
- 与后端 API 文档不一致

### 建议方案

更新前端 API 函数，添加分页参数：

```typescript
export async function listUsers(params?: {
  department_id?: string;
  role?: string;
  limit?: number;
  offset?: number;
}): Promise<{ users: User[]; total: number; limit: number; offset: number }> {
  const url = new URL(`${getBackendBaseURL()}/api/admin/users`);
  if (params?.department_id) url.searchParams.set("department_id", params.department_id);
  if (params?.role) url.searchParams.set("role", params.role);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.offset) url.searchParams.set("offset", String(params.offset));
  // ...
}

export async function listDepartments(params?: {
  limit?: number;
  offset?: number;
}): Promise<{ departments: Department[]; total: number; limit: number; offset: number }> {
  const url = new URL(`${getBackendBaseURL()}/api/admin/departments`);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.offset) url.searchParams.set("offset", String(params.offset));
  // ...
}
```

### 待办

- [x] 更新 `listUsers` 函数添加 `limit` 和 `offset` 参数（已修复）
- [x] 更新 `listDepartments` 函数添加 `limit` 和 `offset` 参数（已修复）
- [ ] 更新前端页面支持分页加载

---

## 10. 前端 Admin API updateUserRole 返回类型不匹配

**严重程度**: MEDIUM | **模块**: 前端 Admin API | **文件**: `frontend/src/core/admin/api.ts`

### 现象

`updateUserRole` 函数声明返回 `Promise<User>`，但后端 API 实际返回 `{ success: boolean; user_id: string; new_role: string }`。

```typescript
// 修复前
export async function updateUserRole(
  userId: string,
  role: string,
): Promise<User> {  // 类型错误
  // ...
}
```

### 根因

前端 API 函数的返回类型定义与后端 API 的实际响应不匹配。

### 影响

- TypeScript 类型检查无法捕获潜在的类型错误
- 如果调用方尝试访问 User 对象的属性（如 `username`），将得到 `undefined`
- 代码可维护性降低

### 建议方案

更新函数返回类型以匹配后端 API：

```typescript
export async function updateUserRole(
  userId: string,
  role: string,
): Promise<{ success: boolean; user_id: string; new_role: string }> {
  // ...
}
```

### 待办

- [x] 更新 `updateUserRole` 函数返回类型（已修复）
- [ ] 确保所有调用方正确处理返回值

---

## 11. 前端工作流编辑器 YAML 验证过于简单

**严重程度**: LOW | **模块**: 前端工作流编辑器 | **文件**: `frontend/src/app/workspace/workflows/[workflow_name]/edit/page.tsx`

### 现象

工作流编辑器的 `validateYaml` 函数只检查 YAML 内容是否包含 `"name:"` 和 `"steps:"` 字符串，没有进行真正的 YAML 解析验证。

```typescript
function validateYaml(content: string): string[] {
  const errors: string[] = [];
  const trimmed = content.trim();

  if (!trimmed) {
    errors.push("YAML content cannot be empty");
    return errors;
  }

  // Basic structural checks
  if (!trimmed.includes("name:")) {
    errors.push('Missing required field: "name"');
  }
  if (!trimmed.includes("steps:")) {
    errors.push('Missing required field: "steps"');
  }

  return errors;
}
```

### 根因

前端验证函数在实现时只进行了简单的字符串匹配，没有使用 YAML 解析器进行真正的语法验证。

### 影响

- 用户可能保存语法错误的 YAML，导致后端解析失败
- 无法检测字段类型错误（如 `name` 应该是字符串但用户输入了数字）
- 无法检测缺少必需字段的步骤定义
- 用户体验差，错误信息不明确

### 建议方案

使用 YAML 解析器进行真正的语法验证：

```typescript
import yaml from "js-yaml";

function validateYaml(content: string): string[] {
  const errors: string[] = [];
  const trimmed = content.trim();

  if (!trimmed) {
    errors.push("YAML content cannot be empty");
    return errors;
  }

  try {
    const parsed = yaml.load(trimmed) as Record<string, unknown>;

    if (!parsed || typeof parsed !== "object") {
      errors.push("YAML must be a mapping");
      return errors;
    }

    if (!parsed.name || typeof parsed.name !== "string") {
      errors.push('Missing or invalid required field: "name" (must be a string)');
    }

    if (!Array.isArray(parsed.steps)) {
      errors.push('Missing or invalid required field: "steps" (must be a list)');
    } else {
      // Validate each step
      parsed.steps.forEach((step: unknown, index: number) => {
        if (!step || typeof step !== "object") {
          errors.push(`Step ${index + 1}: must be a mapping`);
          return;
        }
        const stepObj = step as Record<string, unknown>;
        if (!stepObj.id || typeof stepObj.id !== "string") {
          errors.push(`Step ${index + 1}: missing or invalid "id" field`);
        }
        if (!stepObj.type || typeof stepObj.type !== "string") {
          errors.push(`Step ${index + 1}: missing or invalid "type" field`);
        }
      });
    }
  } catch (e) {
    errors.push(`Invalid YAML syntax: ${e instanceof Error ? e.message : String(e)}`);
  }

  return errors;
}
```

### 待办

- [ ] 添加 YAML 解析库依赖（如 `js-yaml`）
- [ ] 实现真正的 YAML 语法验证
- [ ] 添加步骤级别的字段验证
- [ ] 提供更友好的错误信息

---

## 12. 前端工作流 StepDef 接口缺少字段

**严重程度**: LOW | **模块**: 前端工作流类型定义 | **文件**: `frontend/src/core/workflows/types.ts`

### 现象

前端 `StepDef` 接口只定义了部分字段，缺少后端 `StepDef` 模型中的多个字段。

```typescript
// 当前定义
export interface StepDef {
  id: string;
  type: string;
  agent?: string;
  tool?: string;
  prompt?: string;
  params?: Record<string, unknown>;
  depends_on?: string[];
  retries?: number;
  timeout?: number;
}
```

缺少的字段：
- `condition` - 步骤执行条件
- `then` / `else` - 条件分支
- `expression` - 条件表达式
- `message` - 人工审批消息
- `input_schema` - 人工审批输入模式
- `approvers` - 审批人列表
- `steps` - 子步骤列表
- `items` - 循环遍历项
- `on_error` - 错误处理策略

### 根因

前端类型定义在实现时没有完全对齐后端 Pydantic 模型。

### 影响

- 前端无法正确显示工作流步骤的完整信息
- 条件分支、并行执行、循环遍历等步骤类型无法正确渲染
- TypeScript 类型检查无法捕获潜在的字段访问错误
- 代码可维护性降低

### 建议方案

更新前端 `StepDef` 接口以匹配后端模型：

```typescript
export interface StepDef {
  id: string;
  type: string;

  // agent step
  agent?: string;
  prompt?: string;

  // tool step
  tool?: string;
  params?: Record<string, unknown>;

  // human_review step
  message?: string;
  input_schema?: Record<string, unknown>;
  approvers?: string[];

  // condition step
  expression?: string;
  then?: string | StepDef;
  else?: string | StepDef;

  // parallel / loop
  steps?: StepDef[];
  items?: string;

  // common
  condition?: string;
  timeout?: number;
  retry?: RetryPolicy;
  on_error?: string;
}

export interface RetryPolicy {
  max: number;
  backoff: number;
  on_errors: string[];
}
```

### 待办

- [x] 更新 `StepDef` 接口添加缺失字段（已修复：添加了 condition/then/else/expression/message/input_schema/approvers/steps/items/max_iterations/on_error 等字段）
- [x] 添加 `RetryPolicy` 接口（已修复）
- [ ] 更新前端组件以正确显示所有步骤类型
- [ ] 确保类型定义与后端模型保持同步

---

## 13. submit_review 缺少授权检查

**严重程度**: HIGH | **模块**: 工作流 API | **文件**: `backend/app/gateway/routers/workflows.py:247`

### 现象

`POST /{workflow_name}/runs/{run_id}/review` 端点只验证用户身份（`get_current_rbac_user`），不验证用户是否有权审批该工作流。任何已认证用户都可以对任何运行提交审批意见，包括批准或拒绝。

### 根因

只强制了认证，没有强制授权。工作流 YAML 中 `human_review` 步骤的 `approvers` 字段从未被检查。

### 影响

- 未授权用户可以批准敏感工作流
- 审批数据 `body.data` 未经 `input_schema` 验证直接存入数据库

### 建议方案

1. 解析工作流 YAML 提取 `human_review` 步骤的 `approvers` 列表
2. 验证 `current_user.id` 或 `current_user.username` 在 approvers 列表中，或角色为 `super_admin`
3. 使用 Pydantic 或 JSON Schema 验证 `body.data`

### 待办

- [ ] 实现 approver 权限验证
- [ ] 添加 `input_schema` 验证
- [ ] 添加审批权限的单元测试

---

## 14. 用户禁用接口的竞态条件

**严重程度**: MEDIUM | **模块**: Admin API | **文件**: `backend/app/gateway/routers/admin.py:184`

### 现象

`disable_user` 端点在禁用前检查活跃 super_admin 数量，但使用普通 `SELECT COUNT(*)` 而非 `SELECT ... FOR UPDATE`。与已知问题 #8（`update_user_role`）相同的竞态模式。

### 根因

计数查询缺少行级锁，并发请求可能同时通过检查，导致所有 super_admin 被禁用。

### 建议方案

使用 `SELECT ... FOR UPDATE` 行锁，或使用数据库级 advisory lock 序列化操作。

### 待办

- [ ] 添加 `with_for_update()` 到计数查询
- [ ] 测试并发禁用场景

---

## 15. list_users 不支持过滤已禁用用户

**严重程度**: LOW | **模块**: Admin API | **文件**: `backend/app/gateway/routers/admin.py:86`

### 现象

`list_users` 端点返回所有用户（包括已禁用的），没有 `disabled` 查询参数来过滤。`total` 计数也包含已禁用用户。

### 根因

`disabled` 字段添加到模型后，列表端点未更新支持过滤。

### 建议方案

添加 `disabled` 可选参数，在响应中包含 `disabled` 字段。

### 待办

- [ ] 添加 `disabled` 过滤参数
- [ ] 在响应中包含 `disabled` 字段

---

## 16. 重试机制覆盖历史步骤结果

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:83`

### 现象

重试循环中，每次尝试都调用 `state.set_step_result(step.id, status="running", ...)` 覆盖前一次尝试的结果。如果步骤有 `retry.max=3`，尝试 0、1、2 的结果全部丢失，只有最后一次尝试的数据保留。

### 根因

重试循环每次迭代覆盖同一个 `StepResult` 条目，而不是累积每次尝试的记录。

### 影响

- 排除故障时无法看到前几次尝试的错误信息
- 瞬时故障的诊断变得困难

### 建议方案

在重试耗尽时保留所有尝试的错误信息：

```python
errors = []
for attempt in range(retry.max + 1):
    ...
    except Exception as e:
        errors.append(f"attempt {attempt+1}: {e}")
state.set_step_result(step.id, status="failed", error="; ".join(errors))
```

### 待办

- [ ] 实现错误累积机制
- [ ] 添加重试诊断的单元测试

---

## 17. _authenticate 向所有用户授予全部权限

**严重程度**: MEDIUM | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:157`

### 现象

`_authenticate()` 向每个已认证用户无条件分配 `_ALL_PERMISSIONS`（threads:read, threads:write, threads:delete, runs:create, runs:read, runs:cancel）。viewer 角色的用户也获得写入/删除权限。

### 根因

占位实现，从未替换为基于角色的权限映射。

### 建议方案

映射 `UserRole` 到权限集。例如 `UserRole.VIEWER` 不应获得 `THREADS_WRITE`、`THREADS_DELETE`、`RUNS_CREATE`。

### 待办

- [ ] 实现 UserRole → 权限集映射
- [ ] 更新 `_authenticate` 使用角色权限
- [ ] 添加权限映射的单元测试

---

## 18. 工作流读取端点完全无认证

**严重程度**: MEDIUM | **模块**: 工作流 API | **文件**: `backend/app/gateway/routers/workflows.py:47,57,198,230`

### 现象

`list_workflows`、`get_workflow`、`list_runs`、`get_run_status` 四个端点使用 `get_optional_rbac_user`，未认证用户可以访问。工作流定义可能包含业务逻辑、API 引用或敏感提示词。

### 根因

设计时使用了"可选认证"，未考虑企业部署中工作流数据的敏感性。

### 建议方案

将 `get_optional_rbac_user` 改为 `get_current_rbac_user`，或实现工作流级别的可见性规则（public/private/department）。

### 待办

- [x] 决定认证策略（已修复：改为强制认证 get_current_rbac_user）
- [x] 更新端点依赖（已修复：list_workflows, get_workflow, list_runs, get_run_status 均改为强制认证）
- [ ] 添加工作流可见性的单元测试

---

## 19. _read_file 缺少 pandas 内部防御检查

**严重程度**: LOW | **模块**: data_analyzer | **文件**: `backend/packages/harness/ideer/community/data_analyzer/tools.py:30`

### 现象

`_read_file` 函数内部直接调用 `pd.read_csv()` 等方法，没有检查 `pd is None`。虽然调用方（`data_analyzer_tool`）有 `_check_pandas()` 前置检查，但 `_read_file` 自身的契约不完整。

### 根因

防御性检查放在调用方而非函数内部。

### 建议方案

在 `_read_file` 开头添加 `if pd is None` 检查。**（已在本轮修复中实现）**

### 待办

- [x] 添加内部 pandas 检查（已修复）

---

## 20. 前端角色变更缺少确认对话框

**严重程度**: LOW | **模块**: 前端 Admin | **文件**: `frontend/src/app/workspace/admin/users/page.tsx:77`

### 现象

`handleRoleChange` 直接调用 API 更新角色，没有任何确认步骤。误操作可能意外将普通用户提升为 super_admin，或将 department_admin 降级。对比 `handleDisable` 正确使用了 `confirm()`。

### 根因

敏感操作缺少确认步骤。

### 建议方案

为涉及 `super_admin` 的角色变更添加 `confirm()` 对话框。

### 待办

- [x] 添加角色变更确认对话框（已修复：涉及 super_admin 的变更需要确认）
- [x] 在确认中显示当前角色和新角色（已修复）

---

## 21. on_error 字段仅支持 "skip" 值

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:98`

### 现象

`on_error` 字段是自由格式字符串，但只有 `"skip"` 有实际效果。其他值（如 `"continue"`、`"retry"`、`"abort"`）行为与默认相同（标记工作流为 FAILED），没有验证或警告。

### 根因

只实现了 `on_error == "skip"` 的逻辑，其他值未定义行为。

### 建议方案

定义支持的 `on_error` 值（`skip`、`fail`、`retry`），在 parser 层验证，对不支持的值发出警告。

### 待办

- [ ] 定义支持的 on_error 值
- [ ] 添加 parser 层验证
- [ ] 更新文档

---

## 22. submitReview 返回类型不匹配

**严重程度**: MEDIUM | **模块**: 前端工作流 API | **文件**: `frontend/src/core/workflows/api.ts:114`

### 现象

`submitReview` 函数声明返回 `Promise<RunStatus>`，但后端实际返回 `{ success: boolean; run_id: string }`。

### 根因

前端 API 函数返回类型与后端响应不匹配。**（已在本轮修复中修正）**

### 待办

- [x] 更新返回类型（已修复）

---

## 23. extractError 辅助函数代码重复

**严重程度**: LOW | **模块**: 前端 API | **文件**: `frontend/src/core/admin/api.ts` + `frontend/src/core/workflows/api.ts`

### 现象

`extractError` 辅助函数在 `admin/api.ts` 和 `workflows/api.ts` 中完全相同，违反 DRY 原则。

### 根因

本轮修复中为两个文件独立添加了相同的错误提取逻辑。

### 建议方案

提取到共享模块 `frontend/src/core/api/errors.ts`。

### 待办

- [ ] 提取 `extractError` 到共享模块
- [ ] 更新两个文件的 import

---

## 24. tool_step 超时无法终止挂起的工具线程

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/tool_step.py:56`

### 现象

当工具不实现 `ainvoke` 时，执行器使用 `asyncio.wait_for(asyncio.to_thread(tool.invoke, p), timeout=timeout)`。超时触发时，`asyncio.wait_for` 取消的是 asyncio Task，但底层 OS 线程不会被中断。如果工具内部运行子进程（如 `code_interpreter` 的 `subprocess.run`），子进程在超时后继续运行，反复超时会累积僵尸子进程。

### 根因

`asyncio.to_thread` 不支持可靠的线程终止。Python 的线程模型没有提供安全的中途终止机制。

### 建议方案

- 对于运行子进程的工具，使用 `asyncio.create_subprocess_exec` 实现原生异步管理，超时时调用 `process.terminate()`
- 或使用 `threading.Timer` + `os.killpg` 发送 SIGTERM 到进程组

### 待办

- [ ] 评估影响范围（哪些工具使用同步 invoke）
- [ ] 实现子进程感知的超时机制
- [ ] 添加僵尸进程清理测试

---

## 25. ToolRegistry.update_config 对工具执行无实际效果

**严重程度**: HIGH | **模块**: 工具注册表 | **文件**: `backend/packages/harness/ideer/tools/registry.py:51`

### 现象

`ToolRegistry.update_config()` 更新内存中的 `ToolInfo.config`，但工具执行时通过 `get_available_tools()` 创建新实例，完全绕过注册表。API 调用 `update_config` 后配置变更对实际工具执行无任何影响。

### 根因

`get_available_tools()` 从 `config.tools`（AppConfig）读取配置并直接实例化工具类，从未查询注册表的 `ToolInfo.config`。

### 影响

- 管理员通过 API 修改工具配置后，工具行为不变
- `test_tool` 端点也使用 `get_available_tools()`，测试结果与配置变更无关

### 建议方案

将工具实例化逻辑改为从注册表读取配置，或在 `get_available_tools()` 中合并注册表的 config 覆盖。

### 待办

- [ ] 统一工具实例化路径，使注册表配置生效
- [ ] 更新 `test_tool` 使用注册表配置

---

## 26. render_value 返回 None 而非抛异常

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/template.py:31`

### 现象

`render_value()` 对无法解析的全字符串模板（如 `{{steps.missing.output}}`）返回 `None` 而非抛出 `KeyError`。这改变了条件步骤的语义：原来会快速失败，现在静默地将条件评估为 falsy。

### 根因

模板引擎重构时有意为之，文档说明了行为变更。

### 影响

- 引用不存在的步骤输出的条件表达式不会报错，而是走 else 分支
- 工作流表面成功但实际控制流错误

### 建议方案

在 `_resolve_safe` 中对无法解析的路径记录警告日志，或在模板引擎中添加严格模式选项。

### 待办

- [ ] 添加严格模式选项，无法解析时抛异常
- [ ] 在条件步骤中对 None 结果记录警告

---

## 27. loop_vars 未持久化到数据库

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:112`

### 现象

`save_run_state` 序列化工作流状态时从不写入 `state.loop_vars`。当循环中包含 `human_review` 步骤时，状态保存到数据库后重新加载，循环上下文（index、item）丢失。

### 根因

`save_run_state` 写入 `status`、`inputs`、`steps_state`、`current_step`、`error`，但不包含 `loop_vars`。`_state_to_dict` 虽然包含 `loop_vars`，但 `save_run_state` 未使用该字段。

### 影响

- 循环中的人工审批步骤在进程重启后丢失循环上下文
- 模板引用 `{{_loop.index}}` 解析为 `_MISSING`

### 建议方案

在 `workflow_runs` 表中添加 `loop_vars` JSON 列，在 `save_run_state` 和 `load_run_state` 中序列化/反序列化。

### 待办

- [ ] 添加 `loop_vars` 列到 `workflow_runs` 表（需要 Alembic 迁移）
- [ ] 更新 `save_run_state` 写入 `loop_vars`
- [ ] 更新 `load_run_state` 读取 `loop_vars`

---

## 28. 并行子步骤失败返回 dict 而非 None

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:38`

### 现象

并行子步骤执行失败时返回 `{"error": str(e), "status": "failed"}` 字典而非 `None`。下游代码通过检查 `result is None` 判断失败的逻辑被破坏。

### 根因

重构时将失败返回从 `None` 改为错误字典，但未更新所有消费方。

### 影响

- 下游步骤将失败结果视为成功数据
- 条件表达式对失败结果评估为 truthy

### 建议方案

统一失败返回约定：要么始终返回 None，要么在下游代码中检查 `result.get("status") == "failed"`。

### 待办

- [ ] 统一失败返回约定
- [ ] 更新所有消费方的失败检测逻辑

---

## 29. 条件步骤嵌套分支不支持列表类型

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/condition_step.py:33`

### 现象

`execute_condition_step` 的嵌套分支处理器（用于 loop/parallel 内部的条件步骤）只检查 `dict` 和 `str` 类型。当 `then`/`else` 是 YAML 列表（多个子步骤）时，分支被静默跳过。

### 根因

```python
if isinstance(branch, dict):
    result = await execute_step(...)
elif isinstance(branch, str):
    return {"goto": branch, "result": result}
# list 类型没有处理
```

### 影响

- 多步骤条件分支在 loop/parallel 内部不执行
- 条件评估后直接返回布尔值，忽略分支步骤

### 建议方案

添加 `elif isinstance(branch, list)` 处理，依次执行列表中的每个子步骤。

### 待办

- [ ] 实现列表类型分支处理
- [ ] 添加多步骤条件分支的单元测试

---

## 30. _is_visible_to_user 缺少 department_admin 部门访问规则

**严重程度**: LOW | **模块**: Skills API | **文件**: `backend/app/gateway/routers/skills.py:51`

### 现象

`_is_visible_to_user` 函数检查 skill 可见性时，缺少 `department_admin` 对同部门资源的访问规则。`authz.py` 中的 `check_resource_access` 允许 `department_admin` 访问同部门的 `department` 可见性资源，但 skills 路由的可见性检查不包含此规则。

### 根因

两个独立实现的可见性检查逻辑不一致。

### 影响

- `department_admin` 看不到同部门的 department-visibility skills
- 与 RBAC 模型定义的行为不一致

### 建议方案

在 `_is_visible_to_user` 中添加 `department_admin` 的部门匹配逻辑，或抽取共享的可见性检查函数。

### 待办

- [x] 添加 department_admin 部门匹配逻辑（已修复：agents.py 和 skills.py 均已添加）
- [ ] 抽取共享可见性检查函数

---

## 31. code_interpreter 安全环境变量过滤过于严格

**严重程度**: LOW | **模块**: Community Tools | **文件**: `backend/packages/harness/ideer/community/code_interpreter/mcp_server.py:35`

### 现象

`_build_safe_env()` 使用白名单只保留 6 个环境变量（PATH, HOME, LANG, LC_ALL, TZ, VIRTUAL_ENV），过滤掉了 PYTHONPATH、NODE_PATH、USER、TMPDIR 等运行时关键变量。

### 根因

安全环境变量设计过于保守，使用白名单而非黑名单。

### 影响

- 用户代码中依赖 PYTHONPATH 的 import 会失败
- Node.js 代码中依赖 NODE_PATH 的 require 会失败
- 临时文件目录可能不正确（TMPDIR 被过滤）

### 建议方案

改用黑名单模式：过滤掉包含 KEY、SECRET、PASSWORD、TOKEN、DATABASE_URL 等敏感模式的变量，保留其他所有变量。

### 待办

- [x] 添加 PYTHONPATH、NODE_PATH、USER、TMPDIR 到白名单（已修复）
- [ ] 改为黑名单模式过滤环境变量
- [ ] 添加过滤规则的单元测试

---

## 32. loop_step 静默处理 None 迭代项

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/loop_step.py:28`

### 现象

当循环步骤的 `items` 模板无法解析时（如 `{{steps.step_a.output.results}}` 引用不存在的路径），`render_value` 返回 `None`。loop_step 将 `None` 包装为 `[None]` 并执行一次迭代，产生垃圾输出而非报错。

### 根因

loop_step 没有检查 items 解析结果是否为 None 或有效列表。

### 影响

- 模板拼写错误不会报错，而是静默执行一次无效迭代
- 产生垃圾输出，难以定位根因

### 建议方案

在 loop_step 中检查 items 解析结果，None 时抛出明确错误。

### 待办

- [x] 添加 items 为 None 时的错误处理（已修复：返回空列表并记录警告）
- [ ] 添加相关单元测试

---

## 33. submit_review 存在 TOCTOU 竞态条件

**严重程度**: MEDIUM | **模块**: 工作流 API | **文件**: `backend/app/gateway/routers/workflows.py:257`

### 现象

`submit_review` 先加载运行状态验证 workflow_name，再调用 `save_review_result`。两次数据库操作之间，运行可能被删除或状态变更，导致 `save_review_result` 操作过期数据。

### 根因

加载和保存不是原子操作，存在时间窗口。

### 影响

- 并发删除运行时，审批可能保存到已删除的运行
- 两个并发审批可能都通过验证，最后一个写入者胜出

### 建议方案

在 `save_review_result` 内部合并 workflow_name 验证，使用单个数据库事务。

### 待办

- [ ] 合并验证和保存到单个事务
- [ ] 添加并发审批的测试

---

## 34. Agent 写端点缺少可见性/所有权检查

**严重程度**: MEDIUM | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py`

### 现象

读端点（`get_agent`、`export_agent`、`get_agent_stats`）已添加可见性检查，但写端点（`update_agent`、`delete_agent`）没有所有权或可见性验证。知道 agent 名称的用户可以更新或删除任何 agent。

### 根因

可见性检查只添加到了读端点，写端点遗漏。

### 影响

- 任何认证用户可以修改/删除不属于自己的 agent
- 与 skills.py 的 `_check_resource_modify` 模式不一致

### 建议方案

在 `update_agent` 和 `delete_agent` 中添加所有权检查。

### 待办

- [ ] 添加 agent 写端点的所有权检查
- [ ] 添加权限验证的单元测试

---

## 35. 取消的运行状态被覆盖为 FAILED

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:62`

### 现象

`human_step.py` 检测到外部取消后设置 `state.status = RunStatus.CANCELLED`，然后抛出 `RuntimeError`。executor 的 `run()` 方法捕获所有异常并无条件设置 `state.status = RunStatus.FAILED`，覆盖了 CANCELLED 状态。

### 根因

executor 的异常处理不区分取消和其他失败。

### 影响

- 取消信号丢失，运行显示为失败而非取消
- 用户无法区分主动取消和实际失败

### 建议方案

在 executor 中检查 `state.status` 是否已设置为 CANCELLED，如果是则不再覆盖为 FAILED。

### 待办

- [x] 在异常处理中保留 CANCELLED 状态（已修复：检查 `state.status != RunStatus.CANCELLED` 后才设置 FAILED）
- [ ] 添加取消状态的单元测试

---

## 36. list_tools 向所有认证用户暴露工具配置

**严重程度**: MEDIUM | **模块**: Tools API | **文件**: `backend/app/gateway/routers/tools.py:55`

### 现象

`list_tools` 端点返回每个工具的 `config` 字段，包含运行时配置值。任何认证用户（包括 viewer）都可以通过 `GET /api/tools` 读取这些配置，而 `get_tool_detail` 端点故意不返回 config。

### 根因

list_tools 响应包含了 config 字段，与 get_tool_detail 不一致。

### 影响

- 如果 config 包含敏感值（API Key、端点），会被非管理员读取
- 列表端点暴露的数据比详情端点更多

### 建议方案

从 list_tools 响应中移除 config 字段，或只对 super_admin 返回。

### 待办

- [ ] 从 list_tools 响应中移除 config 字段
- [ ] 确保 get_tool_detail 和 list_tools 的数据暴露一致

---

## 37. Agent 写端点使用可选认证，未认证用户可创建/修改/删除 Agent

**严重程度**: HIGH | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:389,486,654,801`

### 现象

Agent 的写端点（`create_agent`、`update_agent`、`delete_agent`、`import_agent`）使用 `get_optional_rbac_user` 依赖，未认证用户可以执行所有写操作。对比 admin.py 和 workflows.py 的写端点使用 `get_current_rbac_user`（强制认证）。

```python
# agents.py:389
async def create_agent_endpoint(
    request: AgentCreateRequest,
    current_user: UserModel | None = Depends(get_optional_rbac_user),  # ← 可选认证
):
```

### 根因

Agent 端点在添加 RBAC 支持时，读写端点统一使用了 `get_optional_rbac_user`，未区分读写操作的安全要求。

### 影响

- 未认证用户可以创建任意 Agent
- 未认证用户可以修改或删除其他用户的 Agent
- 未认证用户可以导入恶意 Agent 配置
- 与 admin.py 和 workflows.py 的安全模型不一致

### 建议方案

将写端点的依赖改为 `get_current_rbac_user`，或在函数内部检查 `current_user is not None`。

### 待办

- [ ] 将 create_agent、update_agent、delete_agent、import_agent 改为强制认证
- [ ] 保持 get_agent、list_agents、export_agent 为可选认证（读操作）
- [ ] 添加未认证写操作的测试

---

## 38. 首次用户竞态条件在 SQLite 下无法用行锁防护

**严重程度**: MEDIUM | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:495`

### 现象

`get_current_rbac_user` 在创建首个用户时使用 `SELECT ... FOR UPDATE` 防止两个并发请求同时将用户提升为 `super_admin`。但 SQLite 不支持 `FOR UPDATE` 语法，代码回退到普通 `SELECT COUNT(*)`，竞态窗口仍然存在。

### 根因

```python
try:
    count_stmt = select(func.count())...with_for_update(nowait=False)
    admin_count = (await session.execute(count_stmt)).scalar() or 0
except Exception:
    # SQLite fallback — no locking
    count_stmt = select(func.count())...
    admin_count = (await session.execute(count_stmt)).scalar() or 0
```

### 影响

- 在 SQLite 部署中，两个并发首次用户可能同时成为 `super_admin`
- 生产环境通常使用 PostgreSQL，影响有限

### 建议方案

使用应用级锁（`asyncio.Lock`）或 advisory lock 序列化首次用户创建。或接受 SQLite 的限制，在文档中说明。

### 待办

- [ ] 评估 SQLite 部署场景的并发风险
- [ ] 考虑使用 asyncio.Lock 作为跨数据库的锁方案
- [ ] 在部署文档中说明 SQLite 的并发限制

---

## 39. 工作流执行时每步重建工具注册表

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/tool_step.py:31`

### 现象

每个 tool_step 执行时调用 `get_app_config()` 和 `get_available_tools()`，从头重建完整的工具注册表。在一个 N 步工作流中，工具注册表被重建 N 次。

### 根因

`execute_tool_step` 函数在每次调用时独立获取工具列表，没有跨步骤的缓存机制。

### 影响

- 10 步工作流重建 10 次工具注册表
- 增加不必要的 I/O 和 CPU 开销
- 在高并发场景下可能成为性能瓶颈

### 建议方案

在 `WorkflowExecutor.run()` 初始化时构建一次工具注册表，通过参数传递给各步骤执行器。

### 待办

- [ ] 在 WorkflowExecutor 中缓存工具注册表
- [ ] 将缓存的注册表传递给 step executors
- [ ] 测量优化前后的性能差异

---

## 40. get_current_rbac_user 不检查用户禁用状态

**严重程度**: HIGH | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:487`

### 现象

`get_current_rbac_user` 在解析用户后检查 `rbac_user.disabled`，但如果用户的 JWT 在禁用前已签发，禁用后该 JWT 仍然有效。`require_role` 装饰器只检查角色，不检查禁用状态。

### 根因

JWT 无状态设计导致无法即时撤销。禁用用户后，已签发的 JWT 在过期前仍然有效。

### 影响

- 被禁用的用户在 JWT 过期前仍可访问所有端点
- 管理员无法立即终止被禁用用户的访问

### 建议方案

1. 使用短 JWT 过期时间（如 15 分钟）+ 刷新令牌
2. 在 `get_current_rbac_user` 中增加数据库级禁用状态检查（已部分实现）
3. 维护 JWT 黑名单或使用 Redis 存储已撤销的令牌

### 待办

- [ ] 确认 `get_current_rbac_user` 中的禁用检查是否在每次请求时执行
- [ ] 评估 JWT 过期时间是否足够短
- [ ] 考虑添加令牌撤销机制

---

## 41. 条件步骤重试导致内联子步骤重复执行

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:93`

### 现象

条件步骤的重试策略包裹整个 `_execute_condition` 调用。当内联 `StepDef` 子步骤失败时，重试会从头重新执行整个条件（包括子步骤），导致子步骤的重试次数与条件步骤的重试次数相乘。

### 根因

```python
# executor.py:83-93
for attempt in range(retry.max + 1):
    result = await self._dispatch(step, state)  # 包含 _execute_condition
    # 如果 _execute_condition 中的内联子步骤有自己的重试...
```

### 影响

- 条件步骤 `retry.max=3` + 子步骤 `retry.max=2` = 最多 4×3=12 次执行
- 有副作用的子步骤（如发送通知）会被重复执行

### 建议方案

条件步骤的内联子步骤应独立管理重试，不应被外层条件步骤的重试策略包裹。

### 待办

- [ ] 将条件步骤的重试逻辑改为只重试条件求值，不重试子步骤
- [ ] 或在条件步骤层面禁用重试，只允许子步骤级别的重试

---

## 42. 条件步骤内联子步骤绕过 _should_run 检查

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:124`

### 现象

条件步骤的 `then`/`else` 分支中的内联 `StepDef` 子步骤通过 `self._execute_step(step.then, state)` 直接执行，绕过了主循环中的 `_should_run` 检查。子步骤的 `condition` 字段被静默忽略。

### 根因

`_should_run` 只在主循环中调用，递归的 `_execute_step` 调用不经过 `_should_run`。

### 影响

- 内联子步骤的 `condition` 字段无效
- 工作流作者可能误以为条件守卫在子步骤级别生效

### 建议方案

在 `_execute_step` 开头调用 `_should_run`，或在 `_execute_condition` 中显式检查。

### 待办

- [ ] 在 `_execute_step` 中添加 `_should_run` 检查
- [ ] 添加条件守卫的单元测试

---

## 43. 前端 useSubmitReview 不刷新运行状态

**严重程度**: LOW | **模块**: 前端工作流 | **文件**: `frontend/src/core/workflows/hooks.ts:91`

### 现象

`useSubmitReview` mutation 成功后不 invalidate 或 refetch 运行状态查询。同时 `useRunStatus` 在 `waiting_human` 状态时停止轮询。用户提交审批后，UI 仍然显示旧的 `waiting_human` 状态。

### 根因

mutation 的 `onSuccess` 回调没有调用 `queryClient.invalidateQueries`。

### 影响

- 用户提交审批后需要手动刷新页面才能看到工作流恢复执行
- 用户体验差

### 建议方案

在 `useSubmitReview` 的 `onSuccess` 中添加 `queryClient.invalidateQueries(["runStatus", ...])`。

### 待办

- [x] 在 mutation 成功后 invalidate 相关查询（已修复：useSubmitReview 的 onSuccess 中 invalidateQueries）

---

## 44. 工作流 API 返回类型与前端接口不匹配

**严重程度**: LOW | **模块**: 前端工作流 API | **文件**: `frontend/src/core/workflows/api.ts:38,55,30`

### 现象

`createWorkflow`、`updateWorkflow`、`getWorkflow` 的返回类型与后端实际响应不匹配：

| 函数 | 前端期望 | 后端实际返回 | 缺少字段 |
|------|----------|-------------|----------|
| `createWorkflow` | `WorkflowSummary` | `{name, description, version}` | `steps_count`, `inputs` |
| `updateWorkflow` | `WorkflowSummary` | `{name, description, version}` | `steps_count`, `inputs` |
| `getWorkflow` | `WorkflowDetail` | `{name, description, version, inputs, steps, yaml_content}` | `steps_count` |

### 根因

后端端点在实现时没有完全对齐前端 `WorkflowSummary` 接口定义。

### 影响

- TypeScript 类型检查无法捕获字段缺失
- 前端代码访问 `result.steps_count` 会得到 `undefined`

### 建议方案

更新后端端点返回 `steps_count`，或更新前端接口移除不需要的字段。

### 待办

- [ ] 更新后端 `create_workflow` 和 `update_workflow` 返回 `steps_count` 和 `inputs`
- [ ] 或更新前端 `WorkflowSummary` 接口移除 `steps_count`
- [ ] 确保所有调用方正确处理返回值

---

## 45. 并行子步骤无超时强制执行

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:28-41`

### 现象

`_run_sub` 调用 `execute_step(sub_type, sub_def, state)` 时没有超时限制。如果子步骤类型没有内置超时（如 agent 步骤），它将无限期运行。父级 `StepDef.timeout` 字段被忽略。

### 根因

`execute_parallel_step` 不读取或应用 `step_def.get("timeout")` 到子步骤调用。`asyncio.gather` 调用没有超时包装。

### 影响

- 一个卡住的子步骤会导致整个并行步骤永远不返回
- 资源泄漏（线程、数据库连接等）

### 建议方案

从 `step_def` 读取超时并用 `asyncio.wait_for` 或 `asyncio.timeout`（Python 3.11+）包装 gather 调用。

### 待办

- [ ] 实现并行子步骤超时机制
- [ ] 添加超时后的子步骤取消逻辑

---

## 46. loop 步骤静默吞掉子步骤失败

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/loop_step.py:69-74`

### 现象

当循环内部的子步骤引发异常时，错误被捕获、记录为警告，循环继续下一次迭代。子步骤失败被记录为聚合输出中的 `None`，但整体循环步骤报告成功。没有 `fail_fast` 机制。

### 根因

内部 `try/except` 吞掉所有异常。没有 `on_error` 或 `fail_fast` 机制。

### 影响

- 工作流作者无法实现"首次错误即停止"的行为
- 部分失败的循环产生混合成功/None 的输出，难以诊断

### 建议方案

添加 `fail_fast` 选项（默认 false），启用时重新引发异常并中断循环。

### 待办

- [ ] 实现 `fail_fast` 选项
- [ ] 在 finally 块中保留循环上下文恢复
- [ ] 添加相关单元测试

---

## 47. 并行子步骤失败返回 dict 而非一致的错误格式

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:38`

### 现象

并行子步骤执行失败时返回 `{"error": str(e), "status": "failed"}` 字典而非 `None`。下游代码通过检查 `result is None` 判断失败的逻辑被破坏。条件表达式对失败结果评估为 truthy。

### 根因

重构时将失败返回从 `None` 改为错误字典，但未更新所有消费方。

### 建议方案

统一失败返回约定：要么始终返回 None，要么在下游代码中检查 `result.get("status") == "failed"`。

### 待办

- [ ] 统一失败返回约定
- [ ] 更新所有消费方的失败检测逻辑

---

## 48. Store save_run_state 无瞬态数据库错误重试

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:112-143`

### 现象

每次调用 `save_run_state` 都创建新的数据库会话、执行 SELECT、然后 INSERT 或 UPDATE、然后 commit。没有针对瞬态数据库错误（连接重置、死锁）的重试逻辑。在执行器的逐步持久化循环中，单次失败的 commit 会传播为未处理异常并将整个工作流标记为 FAILED。

### 根因

存储层没有针对瞬态数据库故障的弹性层。执行器的外层 `try/except` 捕获异常但即使步骤本身成功也会将工作流标记为 FAILED。

### 建议方案

在 `save_run_state` 的 session commit 周围添加小的重试包装（如 2-3 次重试，短退避）。

### 待办

- [ ] 实现重试机制
- [ ] 测试瞬态故障恢复

---

## 49. 条件步骤返回类型不一致

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/condition_step.py:46-50`

### 现象

当条件分支是内联 dict（步骤 42-47）时，执行器直接返回分支的输出。当分支是字符串步骤 ID（行 50）时，返回 `{"goto": branch, "result": result}` — 形状不同的字典。调用方必须知道使用了哪种分支类型才能正确解释返回值。

### 根因

两个分支路径返回不同类型（原始输出 vs 元数据字典），没有统一的信封。

### 建议方案

始终返回一致的类型，例如 `{"status": "goto", "target": branch, "result": result}` 用于字符串分支。

### 待办

- [ ] 统一条件步骤返回格式

---

## 50. Agent 步骤调用私有方法 _aexecute

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/agent_step.py:68`

### 现象

`executor._aexecute(prompt)` 调用 `SubagentExecutor` 的私有（下划线前缀）方法。公共 API 只暴露 `execute()`（同步）和 `execute_async()`（返回线程 ID 用于轮询）。私有方法不是公共契约的一部分，可能在没有通知的情况下更改。

### 根因

Agent 步骤需要异步接口，但 `SubagentExecutor` 只暴露同步 `execute()` 和 fire-and-forget `execute_async()`。

### 建议方案

在 `SubagentExecutor` 中添加公共 `async def aexecute()` 方法，或使用 `execute_async()` + 轮询获取结果。

### 待办

- [ ] 评估 SubagentExecutor API 设计
- [ ] 添加公共异步接口或改用轮询模式

---

## 51. 多个 _check_resource_modify 实现不一致

**严重程度**: HIGH | **模块**: 认证 | **文件**:
- `backend/app/gateway/authz.py:400-429`
- `backend/app/gateway/routers/agents.py:33-58`
- `backend/app/gateway/routers/skills.py:31-48`

### 现象

存在三个独立的资源修改授权实现：

1. `authz.py` (`check_resource_modify`)：纯布尔函数，user 为 None 时返回 False
2. `agents.py` (`_check_resource_modify`)：**user 为 None 时允许所有修改**（已修复为 401）
3. `skills.py` (`_check_resource_modify`)：user 为 None 时引发 401

三个实现的授权规则（谁可以修改什么）也存在细微差异。

### 根因

RBAC 函数在每个路由器文件中独立实现，而不是使用 `authz.py` 中的集中式 `check_resource_modify`。

### 建议方案

删除 `agents.py` 和 `skills.py` 中的本地 `_check_resource_modify` 实现。让它们调用 `authz.check_resource_modify`（或包装器将布尔转换为 HTTPException）。

### 待办

- [ ] 统一到 authz.py 的集中实现
- [ ] 更新所有路由器使用统一函数
- [ ] 添加授权规则的单元测试

---

## 52. _ideer_test_bypass_auth 属性可绕过所有授权

**严重程度**: HIGH | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:141,195,264`

### 现象

`require_auth`（行 195）和 `require_permission`（行 264）都检查 `getattr(request, "_ideer_test_bypass_auth", False)`，为 true 时跳过所有认证和授权。虽然生产环境中 FastAPI 注入的是真正的 Request（不会有此属性），但此模式很脆弱：任何构造 request-like 对象的代码路径都可能意外设置此属性并完全绕过认证。

### 根因

测试绕过通过 request 对象的属性检查实现，而不是由编译时或部署模式标志保护。

### 建议方案

将绕过逻辑置于环境变量检查之后（如 `os.environ.get("IDEER_TEST_BYPASS")`），使其在生产环境中永远不激活。

### 待办

- [ ] 改为环境变量控制的绕过机制
- [ ] 确保生产部署中不设置该环境变量

---

## 53. require_permission owner_check 与路由处理器之间的 TOCTOU 间隙

**严重程度**: MEDIUM | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:297-303`

### 现象

`require_permission` 装饰器的 owner_check 调用 `thread_store.check_access()`，它打开自己的数据库会话。路由处理器然后执行自己的操作（如 `thread_store.delete()`）。在访问检查和路由处理器操作之间，线程可能被另一个并发请求删除或转移给不同用户。

### 根因

授权检查和业务逻辑操作在不同的事务中，没有锁定。

### 建议方案

对于破坏性操作（DELETE, PATCH），考虑在路由处理器中使用带有 `SELECT ... FOR UPDATE` 的单一会话，将所有权检查移入同一事务。

### 待办

- [ ] 评估 TOCTOU 间隙的安全影响
- [ ] 考虑合并检查和操作到单一事务

---

## 54. Skill.visibility 字段使用未类型化的字符串

**严重程度**: LOW | **模块**: Skills | **文件**: `backend/packages/harness/ideer/skills/types.py:33`

### 现象

`visibility` 声明为 `str = "private"`，但 `ResourceVisibility` 枚举存在于 `user.py` 中，具有完全相同的允许值。使用原始字符串意味着任何值（如 `"publi"` 或 `"INTERNAL"`）都被接受，没有验证。

### 根因

`Skill` dataclass 没有导入或使用 `ResourceVisibility` 枚举。

### 建议方案

将字段更改为使用枚举：`visibility: ResourceVisibility = ResourceVisibility.PRIVATE`

### 待办

- [x] 更新 visibility 字段类型为 ResourceVisibility 枚举（已修复：ResourceVisibility 是 StrEnum，与 str 兼容）

---

## 55. 前端 listUsers 的 getBackendBaseURL 回退不一致

**严重程度**: LOW | **模块**: 前端 Admin API | **文件**: `frontend/src/core/admin/api.ts:23`

### 现象

`listUsers` 有独特的回退 `getBackendBaseURL() || (typeof window !== "undefined" ? window.location.origin : "")`，其他所有 admin API 函数都使用裸的 `getBackendBaseURL()`。

### 根因

可能是 `NEXT_PUBLIC_BACKEND_BASE_URL` 未设置时的一次性解决方案，但从未统一应用。

### 建议方案

统一所有 admin API 函数的 URL 获取方式。

### 待办

- [x] 统一 getBackendBaseURL 使用方式（已修复：listUsers 移除了独特的回退模式）

---

## 56. executor._dispatch 对 condition 步骤和其他步骤传递不同类型

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:107`

### 现象

`_dispatch` 方法对 `condition` 类型步骤传递原始 `StepDef` 对象，而对其他所有步骤类型传递 `step.model_dump(by_alias=True)` 转换后的字典：

```python
async def _dispatch(self, step: StepDef, state: WorkflowState) -> Any:
    step_dict = step.model_dump(by_alias=True)  # 转为 dict

    if step.type == StepType.CONDITION:
        return await self._execute_condition(step, state)  # ← 传 StepDef
    if step.type == StepType.HUMAN_REVIEW:
        return await execute_human_review_step(step_dict, state, self.store)  # ← 传 dict
    return await execute_step(step.type, step_dict, state)  # ← 传 dict
```

`_execute_condition` 使用 `step.then`（`StepDef` 对象）和 `isinstance(step.then, StepDef)` 检查。如果未来重构改为使用 `step_dict`，`model_dump` 会将嵌套的 `StepDef` 转为普通字典，`isinstance` 检查将失败。

### 根因

设计时 `_execute_condition` 需要访问 `StepDef` 的嵌套对象（`then`/`else_` 可以是 `StepDef`），而其他步骤执行器设计为接收字典。

### 影响

- 当前无功能影响，但代码维护风险较高
- 如果开发者将 `_execute_condition` 改为接收 dict，条件分支的内联步骤将无法正确执行

### 建议方案

统一 `_dispatch` 的传递类型：要么所有步骤都传 `StepDef`，要么在 `_execute_condition` 内部自行处理 `StepDef` 到 dict 的转换。推荐前者，因为 `StepDef` 提供类型安全。

### 待办

- [ ] 统一 `_dispatch` 的参数类型
- [ ] 确保所有步骤执行器的接口契约一致

---

## 57. submit_review dict 解包可覆盖 approved 字段

**严重程度**: HIGH | **模块**: 工作流 API | **文件**: `backend/app/gateway/routers/workflows.py:262`

### 现象

`submit_review` 端点使用 `{"approved": body.approved, **body.data}` 构建审批结果。如果 `body.data` 包含 `"approved"` 键，它会覆盖顶层的 `approved` 值：

```json
{"approved": true, "data": {"approved": false, "comment": "ok"}}
```

结果为 `{"approved": false, "comment": "ok"}`，用户意图的 `approved=true` 被静默覆盖。

### 根因

Python dict 解包语法 `{"approved": ..., **body.data}` 中，后出现的键覆盖先出现的键。

### 影响

- 用户提交的审批结果可能与 UI 显示的不一致
- 工作流可能基于错误的审批结果继续执行

### 建议方案

将 `body.data` 嵌套在独立键下：`{"approved": body.approved, "data": body.data}`，或在 API 层禁止 `body.data` 包含 `"approved"` 键。

**（已修复：改为 `{"approved": body.approved, **safe_data}`，其中 `safe_data` 过滤掉 `body.data` 中的 `"approved"` 键，保持平铺结构便于下游模板引用）**

### 待办

- [x] 修复 dict 解包覆盖问题（已修复：过滤 body.data 中的 approved 键）
- [x] 下游模板引用兼容性（已修复：保持平铺结构，无需更新前端）

---

## 58. read_document_tool sync→async 改造可能破坏同步调用方

**严重程度**: HIGH | **模块**: Community Tools | **文件**: `backend/packages/harness/ideer/community/doc_reader/tools.py:110`

### 现象

`read_document_tool` 从同步函数改为 `async def`，但仍使用 LangChain 的 `@tool` 装饰器。`@tool` 装饰器会将协程包装为 `StructuredTool`，其 `invoke()` 方法在同步上下文中返回协程对象而非实际结果。

### 根因

LangChain 的 `@tool` 装饰器对 async 函数的处理：
- `tool.ainvoke(params)` → 正确 await 协程
- `tool.invoke(params)` → 返回协程对象（未 await）

工作流的 `tool_step.py` 有 `hasattr(tool, "ainvoke")` 检查，会优先使用 `ainvoke`。但其他调用方（如直接使用 `tool.invoke()` 的代码）会得到协程对象。

### 影响

- 通过 `tool.invoke()` 同步调用 `read_document_tool` 的代码返回协程对象而非文档内容
- 工作流中 `tool_step` 的 `ainvoke` 路径不受影响

### 建议方案

1. 确保所有调用方使用 `ainvoke` 或 `await`
2. 或保持同步实现，内部使用 `asyncio.run()` 桥接
3. 在工具文档中明确标注为 async-only

### 待办

- [ ] 审查所有 `read_document_tool` 的调用方
- [ ] 确认是否需要保持同步兼容

---

## 59. ProgrammingError 捕获过宽可能掩盖真实 SQL 错误

**严重程度**: MEDIUM | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:504`

### 现象

`get_current_rbac_user` 中的 `SELECT FOR UPDATE` 回退同时捕获 `OperationalError` 和 `ProgrammingError`。在 PostgreSQL 上，`ProgrammingError` 表示语法错误、列不存在、权限不足等问题，而非仅限于 "FOR UPDATE 不支持"。

### 根因

```python
except (OperationalError, ProgrammingError):
    # If FOR UPDATE is not supported (e.g., SQLite), fall back to plain count
```

捕获范围过宽，可能掩盖真实的 SQL 错误。

### 影响

- 未来迁移重命名列时，`ProgrammingError` 被静默捕获，回退查询使用旧列名
- 回退查询也可能失败，导致 `admin_count=0`，每个并发首用户都被提升为 `super_admin`
- 生产环境的 SQL 错误被静默吞掉，难以调试

### 建议方案

1. 使用数据库方言检测（`session.bind.dialect.name == "sqlite"`）替代异常捕获
2. 或检查异常消息中是否包含 "FOR UPDATE" 相关关键词
3. 或只捕获 `OperationalError`（SQLite 通常抛出此异常）

### 待办

- [ ] 改用数据库方言检测或缩小异常捕获范围
- [ ] 测试 PostgreSQL 和 SQLite 下的行为

---

## 60. get_optional_rbac_user 重抛非 401 异常改变可选认证端点行为

**严重程度**: MEDIUM | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:548`

### 现象

`get_optional_rbac_user` 现在只吞掉 401（未认证）异常，重抛 403（禁用用户）和其他异常。这意味着被禁用的用户访问可选认证端点时会收到 403 错误，而非被视为匿名用户。

### 根因

```python
except HTTPException as e:
    if e.status_code != status.HTTP_401_UNAUTHORIZED:
        raise
    return None
```

### 影响

- 被禁用的用户访问 `GET /api/agents`（使用 `get_optional_rbac_user`）会收到 403 而非看到公开资源
- 与之前"可选认证"的设计语义不一致：可选认证应意味着"没有用户就当匿名处理"
- 数据库故障（500）也会被重抛，导致可选认证端点在数据库不可用时返回 500

### 建议方案

1. 在 `get_optional_rbac_user` 中也吞掉 403，让禁用用户被视为匿名
2. 或明确文档说明可选认证端点的行为变更
3. 或只重抛 403 但不重抛 500

### 待办

- [ ] 决定禁用用户在可选认证端点的行为
- [ ] 更新文档说明行为变更

---

## 61. list_workflows total 包含无法解析的工作流行

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:77`

### 现象

`list_workflows` 的 `total` 计数包含所有以 `def:` 开头的行，但结果列表排除了 YAML 解析失败的行。当存在损坏的工作流 YAML 时，`total` 大于实际返回的结果数量。

### 根因

```python
# Count includes ALL def: rows
count_stmt = select(func.count())...where(WorkflowRunRow.run_id.startswith("def:"))
total = (await session.execute(count_stmt)).scalar() or 0

# Results exclude parse failures
for row in rows:
    try:
        wf = parse_workflow_string(row.workflow_yaml)
        results.append(...)
    except Exception:
        results.append({"name": row.workflow_name, "error": str(e)})
```

实际上错误行也会被添加到结果中（带有 `error` 字段），所以这不是严重问题。但前端可能不理解 `error` 字段。

### 影响

- 前端分页可能显示不一致（total=5 但只有 4 个有效工作流卡片）
- 带 `error` 字段的工作流在前端可能显示异常

### 建议方案

在前端正确处理带 `error` 字段的工作流行，或在后端过滤掉损坏的行并调整 total。

### 待办

- [ ] 决定如何处理损坏的工作流 YAML
- [ ] 更新前端处理 error 字段

---

## 62. loop_vars 浅拷贝导致嵌套循环数据泄漏

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/loop_step.py:59`

### 现象

嵌套循环中，外层循环的 `loop_vars` 通过 `dict(state.loop_vars)` 保存。这是浅拷贝——如果外层循环的 `item` 是可变对象（如 dict 或 list），内层循环修改 `state.loop_vars["item"]` 时，外层的 `prev_loop` 中的 `item` 引用也会被修改。

### 根因

```python
prev_loop = dict(state.loop_vars)  # 浅拷贝 — item 引用共享
for idx, item in enumerate(items):
    state.loop_vars["item"] = item  # 覆盖 item 引用
```

`dict()` 只复制键值对，不复制值对象。当 `item` 是 dict 时，内外层共享同一个 dict 对象。

### 影响

- 嵌套循环中，外层循环恢复 `loop_vars` 时，`item` 可能指向内层循环最后一次迭代的值
- 仅在循环项为可变对象（dict/list）时触发，标量值不受影响

### 建议方案

使用 `copy.deepcopy(state.loop_vars)` 替代 `dict(state.loop_vars)`，或在恢复时重新从 `items` 列表获取当前项。

### 待办

- [ ] 使用 `copy.deepcopy` 替代浅拷贝
- [ ] 添加嵌套循环的单元测试

---

## 63. save_workflow 并发创建存在竞态条件

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:38`

### 现象

`save_workflow` 先 SELECT 检查行是否存在，再 INSERT 或 UPDATE。两个并发请求使用相同工作流名称时，都可能看到 `row is None` 并同时尝试 INSERT，导致主键 (`run_id = f"def:{name}"`) 的 `IntegrityError`。API 路由层 (`workflows.py:98-100`) 虽然也做了检查，但 check-then-act 本身也是 TOCTOU 竞态。

### 根因

没有数据库级冲突处理（如 `INSERT ... ON CONFLICT DO UPDATE` 或 `IntegrityError` 捕获重试）。

### 建议方案

在 INSERT 外包裹 `try/except IntegrityError`，捕获后回退到 UPDATE：

```python
try:
    session.add(row)
    await session.commit()
except IntegrityError:
    await session.rollback()
    # Re-select and update
```

### 待办

- [ ] 实现 upsert 模式或 IntegrityError 捕获重试
- [ ] 测试并发创建工作流场景

---

## 64. render_params 不递归处理嵌套列表

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/template.py:57`

### 现象

`render_params` 在顶层处理 `str`、`dict` 和 `list` 值。对于列表项，它渲染字符串并递归到 dict，但嵌套列表（如 `[["{{a}}", "{{b}}"], "{{c}}"]`）会直接传递而不渲染。内层列表的模板字符串会被作为字面 `{{a}}` 文本发送给工具。

### 根因

列表推导式处理了 `str` 和 `dict` 项，但对非字符串、非 dict 项（包括嵌套列表）直接透传。

### 建议方案

为嵌套列表添加递归：

```python
elif isinstance(v, list):
    result[k] = [
        render_value(i, context) if isinstance(i, str)
        else render_params(i, context) if isinstance(i, dict)
        else [render_value(j, context) if isinstance(j, str) else j for j in i] if isinstance(i, list)
        else i
        for i in v
    ]
```

### 待办

- [ ] 实现嵌套列表递归渲染
- [ ] 添加嵌套列表模板的单元测试

---

## 65. 并行子步骤成功结果可能被误判为失败

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:45`

### 现象

全失败检查使用 `isinstance(v, dict) and v.get("status") == "failed"`。如果一个成功的子步骤返回的 dict 恰好包含 `"status": "failed"` 键值对（如返回状态信息的工具），它会被误判为失败。如果所有子步骤都返回这样的 dict，即使全部成功，parallel 步骤也会抛出 `RuntimeError`。

### 根因

成功/失败的判别使用了相同的 dict 形状，与合法工具输出可能冲突。

### 建议方案

使用哨兵包装器（sentinel wrapper）来区分错误结果：

```python
_ERROR_SENTINEL = "__parallel_sub_step_error__"

# In _run_sub's except:
return sub_id, {_ERROR_SENTINEL: True, "error": str(e), "sub_step_id": sub_id}

# In the check:
if results and all(
    isinstance(v, dict) and v.get(_ERROR_SENTINEL)
    for v in results.values()
):
```

### 待办

- [ ] 实现哨兵包装器
- [ ] 更新所有消费方的失败检测逻辑

---

## 66. 条件步骤与执行器的分支实现不一致

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:117` + `condition_step.py:14`

### 现象

条件步骤的分支逻辑存在两个独立实现：
- `executor._execute_condition` 处理顶层条件步骤，使用 `StepDef` 对象和 `_execute_step`（带重试逻辑）
- `condition_step.execute_condition_step` 处理嵌套条件（loop/parallel 内部），使用原始 dict 和 `execute_step`（无重试逻辑）

两者对字符串分支返回不同类型（executor 返回 `f"goto:{...}"` 字符串；condition_step 返回 `{"goto": ..., "result": ...}` 字典），且 condition_step 版本绕过重试机制。

### 根因

为处理顶层 vs 嵌套执行上下文创建了两条代码路径，但随时间推移产生了分歧。

### 建议方案

合并为单一实现，通过标志或回调处理重试行为，或让执行器始终处理条件逻辑并将执行上下文传递给嵌套步骤。

### 待办

- [ ] 统一条件分支实现
- [ ] 确保两种路径的行为一致

---

## 67. save_run_state 无事务隔离

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:136`

### 现象

`save_run_state` 按 `run_id` 选择行，然后插入或更新。在多 worker 部署中，两个 worker 处理同一运行（如服务器重启后旧 worker 的任务仍在运行）时，都可能选择到 `None` 并同时尝试 INSERT，导致 IntegrityError。即使是单 worker 模式，人工审批 API 端点也写入同一行（通过 `save_review_result`），产生丢失更新的窗口。

### 根因

没有乐观锁、`SELECT ... FOR UPDATE`、`INSERT ... ON CONFLICT` 处理。

### 建议方案

使用 upsert 模式或添加带版本列的乐观锁。

### 待办

- [ ] 实现 upsert 或乐观锁
- [ ] 测试多 worker 并发场景

---

## 68. update_config 只验证键不验证值

**严重程度**: HIGH | **模块**: 工具注册表 | **文件**: `backend/packages/harness/ideer/tools/registry.py:51`

### 现象

`ToolRegistry.update_config()` 验证提交的键存在于 `config_schema.properties` 中，但不进行任何值验证。管理员可以将 `config["api_key"]` 设为空字符串、`config["port"]` 设为 `"not_a_number"`、或 `config["base_url"]` 设为恶意 URL。端点盲目调用 `tool.config.update(config)`，将原始 dict 合并到内存中的工具配置。

### 根因

`update_config` 只检查键成员资格，不根据 schema 检查值的类型/约束。

### 建议方案

使用 JSON Schema 验证器（如 `jsonschema.validate()`）验证值。拒绝不符合声明的类型、模式或枚举约束的更新。

### 待办

- [ ] 实现值级别的 schema 验证
- [ ] 添加验证失败的错误处理

---

## 69. test_tool 向客户端返回完整错误堆栈

**严重程度**: MEDIUM | **模块**: 工具 API | **文件**: `backend/app/gateway/routers/tools.py:147`

### 现象

`test_tool` 执行失败时，直接返回 `str(e)` 给客户端。错误消息可能包含文件路径、连接字符串、堆栈跟踪或内部状态。虽然端点需要管理员角色，但 department_admin 调用 `test_tool` 会获得完整的错误详情，可能暴露基础设施信息。

### 根因

工具测试响应中没有错误消息清理。

### 建议方案

返回通用错误消息给客户端，完整异常记录到服务器日志。

### 待办

- [ ] 清理返回给客户端的错误消息
- [ ] 确保完整异常记录到服务器日志

---

## 70. check_agent_name 端点无认证

**严重程度**: LOW | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:297`

### 现象

`/api/agents/check` 端点没有任何认证依赖（无 `current_user`）。未认证用户可以探测任何 agent 名称是否存在，包括私有 agent 的名称。

### 根因

缺少 `get_current_rbac_user` 或 `get_optional_rbac_user` 依赖。

### 建议方案

添加认证依赖，或至少添加 `get_optional_rbac_user` 以启用日志记录。

### 待办

- [ ] 添加认证依赖
- [ ] 测试未认证访问场景

---

## 71. Agent 元数据从错误用户目录加载

**严重程度**: MEDIUM | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:260`

### 现象

`list_agents` 中 `_load_agent_meta(a.name, user_id)` 从当前用户目录加载元数据。但 `list_custom_agents(user_id=user_id)` 返回来自用户目录和共享模板目录的 agent。对于共享 agent，元数据文件 (`.meta.json`) 位于共享目录而非用户目录。`_load_agent_meta` 对缺失文件返回 `{}`，导致 agent 默认为 `"public"` 可见性。

### 根因

`_load_agent_meta` 只检查一个用户目录，共享 agent 的元数据在不同路径中，从未被读取。

### 建议方案

当 `_load_agent_meta` 对共享 agent 返回空时，也检查共享目录的 `.meta.json`。或将 RBAC 元数据存储在中央位置（如数据库表）。

### 待办

- [ ] 修复共享 agent 的元数据加载路径
- [ ] 考虑将元数据迁移到数据库

---

## 72. 无管理员路径管理共享模板元数据

**严重程度**: LOW | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:676`

### 现象

`delete_agent` 在 agent 仅存在于共享模板目录时返回 409。没有机制让管理员（super_admin）删除共享 agent 的元数据，因为元数据按用户存储，`shutil.rmtree(agent_dir)` 只删除用户的副本。共享模板及其元数据成为孤立数据。

### 根因

没有管理员级别的端点或逻辑来管理共享模板元数据。

### 建议方案

添加 super_admin 专用路径来删除共享模板 agent 及其元数据，或将元数据集中存储。

### 待办

- [ ] 添加管理员级别的共享模板管理功能

---

## 73. submit_review 不验证执行器存活性

**严重程度**: MEDIUM | **模块**: 工作流 API | **文件**: `backend/packages/harness/ideer/workflows/store.py:217`

### 现象

`save_review_result` 查询 `status == WAITING_HUMAN` 的运行，然后设置 `row.status = RUNNING`。但不验证运行的执行器是否仍在等待中（如执行器可能已超时或被取消）。当执行器已死亡时设置状态为 RUNNING 会导致运行进入悬空状态。

### 根因

接受审批前没有执行器存活性检查。

### 建议方案

保存审批结果前验证执行器是否仍存活（如检查心跳或后台任务状态）。

### 待办

- [ ] 实现执行器存活性检查
- [ ] 添加执行器死亡时的错误处理

---

## 74. _can_set_visibility 允许无部门用户设置 department 可见性

**严重程度**: LOW | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:61`

### 现象

`_can_set_visibility("department", current_user)` 对任何 department_admin 或 super_admin 返回 `True`，即使 `current_user.department_id` 为 `None`。没有部门分配的 department_admin 可以创建 "department" 可见性的 agent，但 `_is_visible_to_user` 永远不会授予访问权限（因为 `department_id` 比较需要非 None 值），使 agent 对所有人不可见（除所有者和 super_admin）。

### 根因

`_can_set_visibility` 中缺少 `current_user.department_id is not None` 检查。

### 建议方案

在 `_can_set_visibility` 中，当 `visibility == "department"` 时，检查 `current_user.department_id is not None`。

### 待办

- [ ] 添加部门存在性检查
- [ ] 返回明确的错误消息

---

## 75. Agent 统计信息泄露给未认证用户

**严重程度**: LOW | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:932`

### 现象

`/api/agents/{name}/stats` 端点使用 `get_optional_rbac_user`，未认证用户可以访问公开 agent 的统计信息。响应包含 `total_runs` 和 `total_messages`，暴露了平台使用情况的运营元数据。

### 根因

没有根据认证状态过滤敏感统计字段。

### 建议方案

仅在用户已认证且有读取权限时返回 `total_runs` 和 `total_messages`。

### 待办

- [ ] 根据认证状态过滤统计字段

---

## 76. list_tools 和 get_tool_detail 的 config 字段不一致

**严重程度**: LOW | **模块**: 工具 API | **文件**: `backend/app/gateway/routers/tools.py:46 vs 87`

### 现象

`list_tools` 端点在响应中返回 `"config": t.config`，暴露工具的当前配置。但 `get_tool_detail` 完全省略 `config` 字段。详情端点提供的信息比列表端点少，这是不一致的。

### 根因

两个端点之间的复制粘贴不一致。

### 建议方案

在 `get_tool_detail` 的响应中添加 `"config": tool.config`，或从 `list_tools` 中移除（参见问题 #36）。

### 待办

- [ ] 统一两个端点的数据暴露

---

## 77. data_analyzer _MAX_ROWS 定义但从未执行

**严重程度**: LOW | **模块**: data_analyzer | **文件**: `backend/packages/harness/ideer/community/data_analyzer/tools.py:23`

### 现象

`_MAX_ROWS = 500_000` 定义但从未引用。`_read_file` 函数不检查行数，超大文件可能导致内存问题。

### 根因

常量添加时计划实现行数限制，但检查逻辑未完成。

### 建议方案

在 `_read_file()` 中加载后检查 `df.shape[0]` 是否超过 `_MAX_ROWS`，或移除常量。

### 待办

- [ ] 实现行数限制或移除常量

---

## 78. list_departments 缺少角色限制，任何认证用户可访问

**严重程度**: LOW | **模块**: Admin API | **文件**: `backend/app/gateway/routers/admin.py:204`

### 现象

`list_departments` 端点使用 `get_current_rbac_user`（强制认证）但没有 `@require_role` 装饰器。任何已认证用户（包括 viewer）都可以查看部门列表。对比 `list_users` 需要 `super_admin` 角色。

### 根因

端点设计时可能有意允许所有用户查看部门列表（如用于用户注册时选择部门），但与其他 admin 端点的安全模型不一致。

### 影响

- 普通用户可以查看组织部门结构
- 与 `list_users`（需要 super_admin）的安全级别不一致
- 部门名称和描述可能包含敏感的组织架构信息

### 建议方案

根据业务需求选择：
1. 添加 `@require_role(UserRole.SUPER_ADMIN)` 与其他 admin 端点一致
2. 或保持现状但在文档中说明这是有意设计

### 待办

- [ ] 决定 list_departments 的访问策略
- [ ] 如需要，添加角色限制

---

## 79. tools 管理页面直接使用 fetch 而非 admin API 模块

**严重程度**: LOW | **模块**: 前端 Admin | **文件**: `frontend/src/app/workspace/admin/tools/page.tsx:35`

### 现象

`tools/page.tsx` 直接使用 `fetch` 从 `@/core/api/fetcher` 和 `getBackendBaseURL` 发起请求，定义了本地 `backendURL` 辅助函数和 `Tool` 接口。其他 admin 页面（users、departments）使用 `@/core/admin/api.ts` 模块。

### 根因

tools 页面在 admin API 模块建立之前实现，未重构为统一模式。

### 影响

- 代码风格不一致
- `backendURL` 辅助函数与 `admin/api.ts` 中的 URL 构建逻辑重复
- `Tool` 接口本地定义，可能与后端响应不一致

### 建议方案

将 tools 页面的 API 调用迁移到 `@/core/admin/api.ts` 模块，共享 `Tool` 类型定义。

### 待办

- [x] 将 tools API 调用迁移到 admin/api.ts（已修复：添加了 listTools 和 testTool 函数）
- [x] 共享 Tool 类型定义（已修复：使用 @/core/tools/types 中的 Tool 类型）

---

## 80. 条件步骤 goto 机制为死代码

**严重程度**: HIGH | **模块**: 工作流引擎 | **文件**:
- `backend/packages/harness/ideer/workflows/steps/condition_step.py:54`
- `backend/packages/harness/ideer/workflows/executor.py:148`

### 现象

条件步骤的字符串 `then`/`else` 分支引用（步骤 ID）在两个执行路径中都会产生 goto 标记，但没有任何代码消费这些标记来改变控制流：

1. **嵌套路径**（`condition_step.py`）：`execute_condition_step` 对字符串分支返回 `{"goto": branch, "result": result}` 字典
2. **顶层路径**（`executor.py`）：`_execute_condition` 对字符串分支返回 `f"goto:{step.then}"` 字符串

两种格式均未被任何调用方处理：
- `loop_step.py` 直接存储结果为步骤输出，不检查 goto
- `parallel_step.py` 同样直接存储
- `executor.py` 的主循环 `run()` 线性遍历步骤列表，不检查步骤输出中的 goto 标记

```yaml
- id: check_score
  type: condition
  expression: "{{inputs.score}} > 80"
  then: high_score_branch    # 字符串步骤 ID
  else: low_score_branch     # 字符串步骤 ID
```

当 `inputs.score` 为 `42` 时，`_execute_condition` 返回 `"goto:low_score_branch"`，但执行器忽略这个值，继续执行列表中的下一个步骤。

### 根因

两条代码路径独立实现，都没有配套的跳转执行逻辑。`run()` 方法的主循环是纯线性的——遍历 `self.workflow.steps` 列表，没有跳转机制。

### 影响

- 使用字符串 `then`/`else` 目标的条件分支完全不工作
- 仅当 `then`/`else` 是内联 `StepDef` 对象时分支才有效（通过递归调用 `_execute_step`）
- 用户按照文档编写的条件分支工作流静默地忽略分支逻辑

### 待办

- [ ] 实现步骤 ID 索引和跳转逻辑（将步骤列表转换为 `dict[id, StepDef]` 索引）
- [ ] 统一两条代码路径的返回格式
- [ ] 添加条件分支的集成测试
- [ ] 更新文档说明支持的分支语法

---

## 81. 并行子步骤失败检测存在误报风险

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:45`

### 现象

并行步骤的"全部失败"检测使用 `isinstance(v, dict) and v.get("status") == "failed"` 判断。但成功的子步骤返回的是原始工具输出（无包装），如果一个工具合法地返回包含 `"status": "failed"` 的字典（如状态检查工具报告业务逻辑失败），会被误判为步骤执行失败。

```python
if results and all(
    isinstance(v, dict) and v.get("status") == "failed"
    for v in results.values()
):
    raise RuntimeError(f"All parallel sub-steps failed: ...")
```

### 根因

成功结果和失败结果使用相同的 dict 形状，没有哨兵包装器区分。失败分支返回 `{"error": str(e), "status": "failed"}`，但成功分支返回原始工具输出，两者可能冲突。

### 影响

- 工具返回 `{"status": "failed", "reason": "..."}` 作为正常输出时，被误判为步骤失败
- 如果所有并行子步骤都返回此类 dict，即使全部成功，parallel 步骤也会抛出 `RuntimeError`

### 待办

- [ ] 实现哨兵包装器区分错误结果和正常结果
- [ ] 或通过 `state.set_step_result` 的 status 字段判断失败，而非检查返回值

---

## 82. require_role 装饰器硬编码参数名 "current_user"

**严重程度**: LOW | **模块**: 认证 | **文件**: `backend/app/gateway/authz.py:337`

### 现象

`require_role` 装饰器通过 `kwargs.get("current_user")` 提取当前用户对象。如果处理器的参数名不是 `current_user`（如使用 `user` 或 `rbac_user`），装饰器会返回 `None` 并抛出 401 "Authentication required"，错误信息具有误导性。

```python
async def wrapper(*args: Any, **kwargs: Any) -> Any:
    current_user = kwargs.get("current_user")
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
```

### 根因

装饰器硬编码参数名，未使用 `inspect.signature` 动态查找用户参数。

### 影响

- 当前代码库中所有 15 个使用 `@require_role` 的处理器都正确使用 `current_user` 参数名，无活跃 bug
- 但未来开发者如果使用不同参数名，会得到误导性的 401 错误

### 待办

- [ ] 使用 `inspect.signature` 动态查找 `UserModel` 类型的参数
- [ ] 或添加开发文档说明 `@require_role` 要求参数名为 `current_user`

---

## 83. test_tool 端点无执行超时

**严重程度**: MEDIUM | **模块**: 工具 API | **文件**: `backend/app/gateway/routers/tools.py:132`

### 现象

`test_tool` 端点使用 `asyncio.to_thread(tool.invoke, ...)` 执行同步工具，但未使用 `asyncio.wait_for(timeout=...)` 包装。对比工作流引擎的 `tool_step.py` 对相同操作应用了可配置超时（默认 300 秒）。

### 根因

管理员测试端点在实现时遗漏了超时保护。

### 影响

- 挂起或缓慢的工具会无限期阻塞线程，管理员无法取消
- 反复调用可能耗尽线程池

### 待办

- [ ] 使用 `asyncio.wait_for(asyncio.to_thread(...), timeout=300)` 包装
- [ ] 或允许管理员通过请求参数指定超时

---

## 84. save_run_state 未持久化 review_result 列

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:128`

### 现象

`save_run_state` 方法在新建行和更新行时均未写入 `review_result` 列。`_state_to_dict` 序列化器包含 `review_result`，`_row_to_state` 通过 `getattr` 读取它，表明这是预期的往返字段。目前 `review_result` 仅通过专用的 `save_review_result` 方法写入。

### 根因

`save_run_state` 在实现时遗漏了 `review_result` 列的持久化。

### 影响

- 如果未来代码路径设置 `state.review_result` 后调用 `save_run_state`，数据会静默丢失
- 当前不会触发，因为 `review_result` 只通过 `save_review_result` 写入

### 待办

- [ ] 在 `save_run_state` 的 INSERT 和 UPDATE 路径中添加 `review_result` 列
- [ ] 添加往返持久化的单元测试

---

## 85. update_agent 未验证可见性变更权限

**严重程度**: LOW | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:487`

### 现象

`update_agent` 调用 `_check_resource_modify` 验证用户可以修改资源，但未调用 `_can_set_visibility` 验证用户可以设置新的可见性级别。对比 `create_agent` 和 `import_agent` 端点正确调用了 `_can_set_visibility`。

### 根因

可见性权限检查在 update 端点遗漏。

### 影响

- 当前 `AgentUpdateRequest` 不包含 visibility 字段，无实际影响
- 如果未来添加 visibility 字段到更新请求，普通用户可能将 agent 提升为 public 可见性

### 待办

- [ ] 在 `update_agent` 中添加 `_can_set_visibility` 检查
- [ ] 或在添加 visibility 更新功能时同步实现

---

## 86. WorkflowDef.name max_length=60 受 DB 列限制约束

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/schema.py:80`

### 现象

`WorkflowDef.name` 的 `max_length=60` 限制看似过于严格，但实际上是由数据库列约束决定的。`workflow_runs` 表的 `run_id` 列是 `String(64)`，工作流定义使用 `run_id=f"def:{name}"` 格式存储，因此名称最多 60 字符（64 - 4 字节的 "def:" 前缀）。

### 根因

存储设计将工作流定义和运行记录放在同一张表，通过 `run_id` 前缀区分。这限制了名称长度。

### 影响

- 用户无法使用超过 60 字符的工作流名称
- 长描述性名称（如 "Automated Quarterly Financial Report Generation and Distribution Workflow"）会被拒绝

### 建议方案

1. **短期**：在错误消息中说明限制原因
2. **长期**：将工作流定义分离到独立表，或使用自增 ID 替代名称作为主键

### 待办

- [ ] 在 Pydantic 验证错误消息中说明 DB 限制原因
- [ ] 考虑将工作流定义存储与运行记录分离

---

## 87. human_review 步骤嵌套在 loop/parallel 中时崩溃

**严重程度**: CRITICAL | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/__init__.py:15-42`

### 现象

`execute_step` 分发函数处理 `AGENT`、`TOOL`、`CONDITION`、`PARALLEL` 和 `LOOP` 步骤类型，但没有 `HUMAN_REVIEW` 的处理分支。当 `human_review` 步骤嵌套在 `loop` 或 `parallel` 步骤内部时，`execute_step` 抛出 `ValueError("Unknown step type: human_review")`。

### 根因

`HUMAN_REVIEW` 仅在 `executor.py:_dispatch`（行 127-130）中处理，该函数传递 store 对象。但 `loop_step.py` 和 `parallel_step.py` 中的嵌套步骤直接调用 `execute_step`（绕过 `_dispatch`），因此 `human_review` 子步骤会崩溃。

### 影响

- 任何将 `human_review` 步骤嵌套在 `loop` 或 `parallel` 块中的工作流 YAML 在运行时会崩溃
- 解析器接受此 YAML 不报错，因此 bug 仅在执行时发现
- 企业审批流程中常见的"对每个项目进行人工审批"模式无法实现

### 建议方案

**方案 A — 在 execute_step 中添加 HUMAN_REVIEW 处理**

需要将 store 对象传递给嵌套步骤执行器，这需要架构变更。

**方案 B — 在解析器中验证**

在解析器中验证 `human_review` 步骤不能作为 `loop`/`parallel` 步骤的子步骤出现。

### 待办

- [ ] 选择方案（推荐方案 B 作为短期修复）
- [ ] 实现验证或架构变更
- [ ] 添加相关单元测试

---

## 88. update_skill 对 extensions_config.json 的并发修改存在竞态条件

**严重程度**: MEDIUM | **模块**: Skills API | **文件**: `backend/app/gateway/routers/skills.py:497-514`

### 现象

`update_skill` 读取内存中的 `extensions_config`，修改它，序列化到磁盘，然后重新加载。两个并发请求（例如管理员 A 禁用技能 X，管理员 B 禁用技能 Y）都会读取相同的初始状态，都写入各自的版本到磁盘，第二个写入者覆盖第一个写入者的更改。

### 根因

共享 `extensions_config.json` 文件的读-改-写周期没有锁定或原子操作。

### 影响

- 并发的技能启用/禁用操作可能静默丢失更新
- 管理员 A 禁用技能 X，但管理员 B 的并发写入（不包含技能 X 的更改）覆盖文件，因此技能 X 保持启用状态

### 建议方案

使用文件锁（如 `fcntl.flock`）或原子重命名模式：

```python
import tempfile, os
lock = threading.Lock()
with lock:
    extensions_config = get_extensions_config()
    extensions_config.skills[skill_name] = SkillStateConfig(enabled=request.enabled)
    # Write to temp file then atomic rename
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config_data, f, indent=2)
        os.replace(tmp_path, config_path)
    except:
        os.unlink(tmp_path)
        raise
    reload_extensions_config()
```

### 待办

- [ ] 实现文件锁或原子写入
- [ ] 测试并发技能配置更新场景

---

## 89. 工作流后台任务在服务器重启后留下孤立运行

**严重程度**: MEDIUM | **模块**: 工作流 API | **文件**: `backend/app/gateway/routers/workflows.py:183-198`

### 现象

`run_workflow` 将工作流执行作为 fire-and-forget 的 `asyncio.Task` 启动，没有机制检测或恢复孤立运行。如果服务器在工作流运行时重启，这些运行将永久保持 `RUNNING`（或 `WAITING_HUMAN`）状态，无法恢复、取消或垃圾回收。

### 根因

`asyncio.create_task` 后台任务模式没有持久性。`_background_tasks` 集合仅在当前进程生命周期内防止 GC。没有"回收器"或启动恢复逻辑来检测过期的运行中工作流。

### 影响

- 服务器重启后，`list_runs` 显示永久卡在 `RUNNING` 状态的运行
- 用户无法取消或重启这些运行
- 随着时间推移，过期运行在数据库中累积

### 建议方案

添加启动恢复函数，扫描处于 `RUNNING` 或 `WAITING_HUMAN` 状态且最后更新时间超过 N 分钟的运行，将其标记为 `FAILED` 并附带适当的错误消息。或实现定期清理任务。

### 待办

- [ ] 实现启动恢复逻辑
- [ ] 或实现定期清理任务
- [ ] 添加过期运行检测的单元测试

---

## 90. _should_run 将所有 falsy 值视为"跳过"

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/executor.py:73-85`

### 现象

`_should_run` 使用 `bool(result)` 评估步骤条件。这意味着所有 falsy Python 值（`0`、`""`、`False`、`[]`、`{}`）都会导致步骤被跳过，即使用户可能将它们视为有效输出。例如，`condition: "{{steps.step1.output}}"` 其中 `step1.output` 为 `0` 会跳过步骤。

### 根因

已知问题 #1 和 #26 涵盖了表达式求值问题和 None 情况。然而，所有 falsy 值（不仅仅是 None）导致步骤跳过的更广泛问题未被记录。条件字段将"无输出"与"falsy 输出"混为一谈。

### 影响

- 产生合法 falsy 输出（数值零、空字符串、空列表）的步骤在用作条件时会被静默跳过
- 对于返回 `0` 或 `false` 作为有意义值的工具输出尤其令人困惑

### 建议方案

考虑添加严格模式，其中只有 `None` 和显式 `false`/`"false"` 跳过步骤，或将 falsy-评估为跳过的行为 prominently 记录在文档中。

### 待办

- [ ] 评估是否需要严格模式
- [ ] 更新文档说明条件评估行为

---

## 91. 运行记录不快照工作流 YAML 用于调试/审计

**严重程度**: MEDIUM | **模块**: 工作流 API | **文件**: `backend/app/gateway/routers/workflows.py:183-184`

### 现象

`run_workflow` 不将工作流 YAML 内容与运行记录一起持久化。`save_run_state` 方法创建 `workflow_yaml=""`（空字符串）的 `WorkflowRunRow`。如果工作流定义在运行创建后更新，无法重建执行时工作流的样子用于调试或审计。

### 根因

运行行中的 `workflow_yaml` 字段用于定义存储（`def:` 前缀行），不用于运行快照。执行器和存储没有在运行创建时快照 YAML 的机制。

### 影响

- 调试失败运行时，运维人员无法确定使用了哪个版本的工作流 YAML
- 如果工作流在运行和调查之间更新，当前 YAML 可能有不同的步骤、表达式或工具配置

### 建议方案

在 `run_workflow` 中，将 `yaml_content` 传递给执行器或与运行状态一起存储：

```python
state.workflow_yaml = yaml_content  # snapshot for debugging
```

或添加 `workflow_version` 字段来跟踪使用了哪个版本。

### 待办

- [ ] 实现 YAML 快照机制
- [ ] 添加版本跟踪字段

---

## 92. LocalSettings 类型定义过于宽松

**严重程度**: LOW | **模块**: 前端设置 | **文件**: `frontend/src/core/settings/local.ts:48`

### 现象

`LocalSettings.context` 的 `mode` 属性类型为 `"flash" | "thinking" | "pro" | "ultra" | undefined`，但不包括显式联合中的 `undefined`。`Omit` + 交集模式创建了一个混乱的类型，其中 `LocalSettings.context` 继承了 `AgentThreadContext` 的所有属性（通过 `Record<string, unknown>` 索引签名）和重新定义的字段。

### 根因

`Omit<AgentThreadContext, ...>` 模式结合 `Record<string, unknown>` 基类型意味着结果类型同时具有显式重新定义的字段和来自基类型的索引签名，允许使用 `unknown` 类型访问任意键。

### 影响

- 低。访问 `settings.context.thread_id` 的代码编译时无错误（类型来自索引签名的 `unknown`），但值从未被 `DEFAULT_LOCAL_SETTINGS` 设置
- 如果代码读取这些继承但未定义的字段，可能导致微妙的 bug

### 建议方案

使用更严格的类型定义，明确列出仅存在于 `LocalSettings.context` 中的字段，或添加运行时验证。

### 待办

- [ ] 评估类型定义的严格性需求
- [ ] 考虑添加运行时验证

---

## 93. 并行子步骤嵌套 ID 相同导致状态覆盖

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/parallel_step.py:32-33`

### 现象

当并行步骤包含嵌套子步骤（如每个分支是循环或另一个并行），且两个分支恰好定义了相同 ID 的子步骤时，`state.set_step_result(sub_id, ...)` 来自并发的 `_run_sub` 协程会相互覆盖共享 `state.steps` 字典中的结果。

### 根因

`_run_sub` 在共享的 `state` 对象上调用 `state.set_step_result(sub_id, status="completed", output=result)`。如果两个并行分支都有名为 "process_data" 的子步骤，它们会并发写入 `state.steps["process_data"]`。

### 影响

- 一个分支的结果静默替换另一个分支的结果
- 引用 `{{steps.process_data.output}}` 的下游步骤获得错误分支的输出
- 竞态条件取决于时序；难以重现

### 建议方案

在存储结果时为子步骤 ID 添加父并行步骤 ID 前缀：

```python
qualified_id = f"{step_def['id']}.{sub_id}"
state.set_step_result(qualified_id, status="completed", output=result)
```

或在解析时验证并行分支不共享任何嵌套步骤 ID。

### 待办

- [ ] 实现 ID 限定或解析时验证
- [ ] 添加相关单元测试

---

## 94. save_run_state 不处理非 JSON 可序列化的步骤输出

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/store.py:134-159`

### 现象

`save_run_state` 通过 `_state_to_dict` 序列化步骤结果，该函数包含 `sr.output`。此值存储在 `JSON` 列中。如果工具步骤返回非 JSON 可序列化对象（如自定义类实例、`bytes` 对象、`datetime`），`session.commit()` 将在 JSON 序列化期间抛出 `TypeError`。这会崩溃持久化调用，传播到执行器的外层 `try/except`，将整个工作流标记为 FAILED，即使步骤本身成功了。

### 根因

`WorkflowRunRow.steps_state` 是 `JSON` 列。SQLAlchemy 的 JSON 序列化器无法处理任意 Python 对象。`_state_to_dict` 函数直接传递 `sr.output` 而不进行序列化安全处理。

### 影响

- 成功但返回非可序列化输出的工具步骤导致整个工作流失败
- 错误消息具有误导性，因为步骤本身工作正常

### 建议方案

在 `_state_to_dict` 中添加 JSON 安全序列化器：

```python
def _json_safe(obj: Any) -> Any:
    """Ensure value is JSON-serializable."""
    import json
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
```

**（已在本轮修复中实现）**

### 待办

- [x] 添加 JSON 安全序列化器（已修复：递归清理 dict/list 结构，保留类型信息）
- [ ] 添加非可序列化输出的单元测试

---

## 95. 条件步骤缺少 expression 字段时默认为 always-true

**严重程度**: LOW | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/parser.py:92-93`

### 现象

解析器接受没有 `expression` 字段的 `condition` 步骤。验证只要求 `expression`、`then`、`else` 中至少有一个。只有 `then`（没有 `expression`）的条件步骤通过验证但在语义上无意义——执行器默认为 `bool(render_value("true", context))`，始终为 `True`，因此 `then` 分支总是无条件执行。

### 根因

验证逻辑使用 OR 逻辑。只有 `then` 的 YAML 满足条件并通过验证。执行器的回退 `step.expression or "true"` 在 `executor.py:137` 静默地将缺失的表达式转换为始终为真。

### 影响

- 工作流作者可以编写看起来有分支逻辑但总是走一条路径的条件步骤
- 这令人困惑，因为 YAML 看起来应该分支但实际上从不分支

### 建议方案

加强解析器验证，要求条件步骤必须有 `expression` 字段：

```python
if step_type == "condition" and "expression" not in raw:
    raise ValueError("Invalid step definition: 'condition' step requires 'expression' field ...")
```

**（已在本轮修复中实现）**

### 待办

- [x] 加强条件步骤验证（已修复：要求 expression 字段）
- [ ] 更新文档说明条件步骤必须有 expression

---

## 96. 循环变量模板路径变更为破坏性更改

**严重程度**: MEDIUM | **模块**: 工作流引擎 | **文件**: `backend/packages/harness/ideer/workflows/steps/loop_step.py:69`

### 现象

循环步骤的变量注入路径从 `state.inputs['_loop_index']` / `state.inputs['_loop_item']` 变更为 `state.loop_vars['index']` / `state.loop_vars['item']`，模板引用从 `{{inputs._loop_index}}` / `{{inputs._loop_item}}` 变更为 `{{_loop.index}}` / `{{_loop.item}}`。

### 根因

重构将循环变量从用户输入上下文中分离出来，使用独立的 `_loop` 命名空间，避免污染下游模板上下文。

### 影响

- 使用旧语法 `{{inputs._loop_index}}` 或 `{{inputs._loop_item}}` 的现有工作流 YAML 将静默地将模板保留为字面文本
- Agent 收到的提示词中包含 `{{inputs._loop_item}}` 而非实际循环项值
- 无错误提示，工作流表面成功但实际控制流错误

### 待办

- [x] 新语法已实现（`{{_loop.index}}` / `{{_loop.item}}`）
- [ ] 提供从旧语法到新语法的迁移脚本
- [ ] 更新工作流文档说明新的循环变量引用方式

---

## 97. update_skill 移除了 extensions_config.json 自动创建回退

**严重程度**: LOW | **模块**: Skills API | **文件**: `backend/app/gateway/routers/skills.py:516`

### 现象

`update_skill` 端点在 `ExtensionsConfig.resolve_config_path()` 返回 `None` 时，旧代码会自动在 `Path.cwd().parent / "extensions_config.json"` 创建配置文件。新代码直接返回 HTTP 500 错误。

### 根因

设计变更：从"静默创建"改为"快速失败"，避免在意外位置创建配置文件。

### 影响

- 全新部署或删除 `extensions_config.json` 后，无法通过 API 启用/禁用技能
- 需要先手动创建配置文件才能使用技能管理功能

### 待办

- [ ] 在部署文档中说明 `extensions_config.json` 的初始化步骤
- [ ] 或恢复自动创建逻辑但记录警告日志

---

## 98. 共享 Agent 在 list_agents 中对非 super_admin 不可见

**严重程度**: HIGH | **模块**: Agent API | **文件**: `backend/app/gateway/routers/agents.py:258-271`

### 现象

`list_agents` 端点的可见性过滤对共享模板 Agent 不正确。`_load_agent_meta(a.name, user_id)` 从**用户**目录查找 `.meta.json`，但共享 Agent 的元数据在**全局**目录。找不到元数据时返回 `{}`，导致 `visibility` 默认为 `"private"`、`owner_id` 为 `None`。`_is_visible_to_user("private", None, None, current_user)` 对除 `super_admin` 外的所有用户返回 `False`。

`_is_shared_only` 标志已计算（行 278）但从未用于豁免共享 Agent 的可见性过滤。

### 根因

RBAC 可见性过滤未区分共享模板 Agent 和用户私有 Agent。共享 Agent 应始终视为 public 可见性。

### 影响

- 非 super_admin 用户看不到任何共享模板 Agent
- 这是 pre-RBAC 行为的回归（之前所有 Agent 对所有人可见）
- `get_agent` 单个端点不受影响（有其他检查路径）

### 建议方案

在可见性过滤前检查 Agent 是否为共享模板，如果是则视为 public：

```python
for a in agents:
    is_shared = _is_shared_only(a.name, user_id)
    if is_shared:
        visibility = "public"
        owner_id = None
        dept_id = None
    else:
        meta = _load_agent_meta(a.name, user_id)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")
```

### 待办

- [ ] 在 list_agents 中为共享 Agent 设置 public 可见性
- [ ] 添加共享 Agent 可见性的单元测试

---

## 99. Admin 页面未使用 React Query 缓存

**严重程度**: LOW | **模块**: 前端 Admin | **文件**: `frontend/src/app/workspace/admin/users/page.tsx` 等

### 现象

三个 Admin 页面（users、departments、tools）使用手动 `useState` + `useEffect` + `useCallback` 进行数据获取，而 workflow 页面使用 React Query hooks。这导致 admin 页面缺少自动缓存、后台刷新、请求去重和 stale-while-revalidate 行为。

### 根因

admin 页面在 React Query hooks 模式建立之前实现，未重构为统一模式。

### 影响

- 用户切换筛选条件时触发全量重新获取，无缓存
- 页面切换后返回需要重新加载数据
- 与 workflow 页面的用户体验不一致

### 建议方案

创建 React Query hooks（如 `useUsers`、`useDepartments`、`useAdminTools`），遵循 `frontend/src/core/workflows/hooks.ts` 的模式。

### 待办

- [ ] 创建 admin 数据的 React Query hooks
- [ ] 迁移三个 admin 页面使用新 hooks
- [ ] 确保缓存失效策略正确

---

## 100. extensions_config 环境变量未设置时静默替换为空字符串

**严重程度**: MEDIUM | **模块**: ExtensionsConfig | **文件**: `backend/packages/harness/ideer/config/extensions_config.py:165-168`

### 现象

`resolve_env_variables` 对未设置的环境变量静默替换为 `""`，而 `app_config.py` 中的同名方法抛出 `ValueError`。例如 `MCP_OAUTH_CLIENT_SECRET` 未设置时，OAuth client_secret 变为空字符串，导致静默认证失败。

### 根因

两个配置模块的环境变量解析行为不一致。

### 影响

- MCP 服务器 OAuth 认证静默失败，无错误提示
- 配置错误难以排查（连接错误而非"环境变量未设置"）

### 建议方案

统一行为：当环境变量未设置时抛出 `ValueError`，与 `app_config.py` 一致。

### 待办

- [ ] 将 `resolve_env_variables` 改为未设置时抛异常
- [ ] 确保现有部署设置了所有必需的环境变量

---

## 101. 前端工作流 API 缺少分页参数

**严重程度**: LOW | **模块**: 前端工作流 API | **文件**: `frontend/src/core/workflows/api.ts`

### 现象

后端 `listWorkflows` 和 `listRuns` 端点支持 `limit` 和 `offset` 分页参数，但前端 API 函数没有传递这些参数。

### 影响

- 用户无法分页浏览大量工作流或运行记录
- 与 admin API 分页问题（#9）类似

### 待办

- [ ] 更新 `listWorkflows` 函数添加分页参数
- [ ] 添加 `listRuns` 前端函数

---

## 102. 前端 createWorkflow/updateWorkflow 使用非类型化请求体

**严重程度**: LOW | **模块**: 前端工作流 API | **文件**: `frontend/src/core/workflows/api.ts`

### 现象

`createWorkflow` 和 `updateWorkflow` 函数接受 `Record<string, unknown>` 而非具体的请求类型。后端期望 `{ yaml_content: string; name?: string }`，但 TypeScript 无法在编译时捕获缺失的必需字段。

### 影响

- 调用方可能忘记包含 `yaml_content`，错误仅在运行时被后端 Pydantic 验证捕获

### 待办

- [ ] 定义 `WorkflowCreateRequest` 和 `WorkflowUpdateRequest` 接口
- [ ] 更新函数签名使用具体类型

---

## 103. _check_resource_modify 允许 department_admin 修改私有资源

**严重程度**: LOW | **模块**: 认证 | **文件**:
- `backend/app/gateway/authz.py:403-432`
- `backend/app/gateway/routers/agents.py:33-58`
- `backend/app/gateway/routers/skills.py:41-58`

### 现象

`_check_resource_modify` 函数允许 `department_admin` 修改同部门的所有资源，包括 `private` 可见性的资源。这与 `_is_visible_to_user` 的文档不一致（文档说 "private: only owner and super_admin"）。

### 影响

- `department_admin` 可以修改或删除同部门其他用户的私有资源
- 三个实现（authz.py、agents.py、skills.py）行为一致，可能是设计意图

### 待办

- [ ] 确认这是设计意图还是需要修复
- [ ] 如需修复，在 `_check_resource_modify` 中添加可见性检查
