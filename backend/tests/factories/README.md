# 测试数据工厂使用规范

## 原则

1. 新测试**必须**使用 Factory，不再手写 `_make_*` builder
2. Factory 定义放在 `tests/factories/` 对应模块中
3. 通过 import 使用：`from tests.factories import UserFactory`
4. 需要特殊数据时用 `UserFactory.build(field=value)` 覆盖默认值

## 可用 Factories

| Factory | 模块 | 用途 |
|---------|------|------|
| `UserDictFactory` | auth.py | 构建用户数据（SimpleNamespace） |
| `UserFactory` | models.py | 构建带 role/department 的用户 |
| `ToolInfoFactory` | models.py | 构建工具信息对象 |
| `AppConfigFactory` | models.py | 构建应用配置 dict |
| `LLMResponseFactory` | llm.py | 构建 LLM 响应对象 |
| `ToolCallModelFactory` | llm.py | 构建模拟 ToolCallingModel |
| `WorkflowStateFactory` | workflow.py | 构建工作流状态 |
| `WorkflowStoreFactory` | workflow.py | 构建模拟 WorkflowStore |

## 使用示例

### 基本用法

```python
from tests.factories import UserFactory, LLMResponseFactory

def test_user_role():
    admin = UserFactory.build(role="admin")
    viewer = UserFactory.build(role="viewer")
    assert admin.role == "admin"
    assert viewer.role == "viewer"

def test_llm_response():
    resp = LLMResponseFactory.build(content="custom answer")
    assert resp.content == "custom answer"
```

### 批量构建

```python
from tests.factories import UserFactory

def test_batch_users():
    users = UserFactory.build_batch(5, role="user")
    assert len(users) == 5
```

### 带预设的方法

```python
from tests.factories import LLMResponseFactory, WorkflowStateFactory

# 带 tool calls 的响应
resp = LLMResponseFactory.build_with_tool_calls()

# 运行中的工作流
state = WorkflowStateFactory.build_running(current_step="step-2")
```

## 添加新 Factory

1. 在对应模块中定义 Factory 类（使用 `@staticmethod` 的 `build` 方法）
2. 在 `__init__.py` 中导出
3. 编写至少一个使用该 Factory 的测试
4. 更新本文档的可用 Factories 表

## 禁止

- 禁止在测试文件中定义 Factory（必须放 `factories/` 模块）
- 禁止 Factory 依赖其他 Factory 的运行时状态（用参数传入而非直接调用）
- 新测试禁止手写 `_make_*` builder（使用 Factory 替代）

## 渐进迁移策略

- 旧测试中的 `_make_*` builder 保持不动，不删除
- 新测试必须使用 Factory
- 重构旧测试时，逐步替换为 Factory
