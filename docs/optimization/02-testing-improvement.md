# 测试完善方案

## 概述

当前已有 211 个后端测试文件和 30 个前端测试文件。但 Phase 3-5 新增的功能模块（Admin API、工作流引擎、Community Tools）测试覆盖不足，需要补充。

> 已有测试清单：参见 `backend/tests/` 和 `frontend/tests/`

## 当前测试状态

| 模块 | 测试文件 | 测试数量 | 状态 |
|------|----------|----------|------|
| Schema + Parser | test_schema_parser.py | 21 | ✅ 通过 |
| Template Engine | test_template.py | 18 | ✅ 通过 |
| read_document | test_doc_reader.py | 11 | ✅ 通过 |
| code_interpreter | test_code_interpreter.py | 5 | ✅ 通过 |
| data_analyzer | test_data_analyzer.py | 6 | ✅ 通过 |
| Admin API | 无 | 0 | ❌ 缺失 |
| Workflow Executor | test_workflow_executor.py | ~15 | ⚠️ 不足 |
| 前端 E2E | 8 个 spec 文件 | ~40 | ⚠️ 不足 |
| **合计** | 211 后端 + 30 前端 | | |

## 目标

| 模块 | 当前 | 目标 | 覆盖率 |
|------|------|------|--------|
| Admin API | 0 | 30+ | 80% |
| Workflow Executor | ~15 | 30+ | 85% |
| 前端 E2E（Admin/Workflow） | 0 | 15+ | 主要流程 |

---

## 1. Admin API 测试

### 1.1 测试文件位置

```
backend/tests/test_admin_api.py
```

### 1.2 测试内容

#### RBAC 权限测试

```python
"""Admin API tests for RBAC management."""

import pytest
from httpx import AsyncClient


class TestAdminStats:
    """Admin dashboard statistics tests."""

    @pytest.mark.asyncio
    async def test_get_stats_as_super_admin(self, client: AsyncClient, super_admin_token: str):
        """Super admin can access dashboard stats."""
        response = await client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_departments" in data

    @pytest.mark.asyncio
    async def test_get_stats_as_normal_user_forbidden(self, client: AsyncClient, user_token: str):
        """Normal user cannot access dashboard stats."""
        response = await client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403
```

#### 用户管理测试

```python
class TestUserManagement:
    """User CRUD operations tests."""

    @pytest.mark.asyncio
    async def test_create_user(self, client: AsyncClient, super_admin_token: str):
        """Create a new user."""
        response = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "username": "testuser",
                "password": "TestPass123!",
                "role": "user",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["role"] == "user"

    @pytest.mark.asyncio
    async def test_create_duplicate_user_fails(self, client: AsyncClient, super_admin_token: str):
        """Cannot create user with existing username."""
        await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"username": "dup_user", "password": "Pass123!"}
        )
        response = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"username": "dup_user", "password": "Pass456!"}
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_user_role(self, client: AsyncClient, super_admin_token: str):
        """Update user role."""
        create_resp = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"username": "role_test", "password": "Pass123!", "role": "user"}
        )
        user_id = create_resp.json()["id"]

        response = await client.put(
            f"/api/admin/users/{user_id}/role",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"role": "department_admin"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "department_admin"

    @pytest.mark.asyncio
    async def test_delete_user(self, client: AsyncClient, super_admin_token: str):
        """Delete user."""
        create_resp = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"username": "delete_test", "password": "Pass123!"}
        )
        user_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
```

#### 部门管理测试

```python
class TestDepartmentManagement:
    """Department CRUD operations tests."""

    @pytest.mark.asyncio
    async def test_create_department(self, client: AsyncClient, super_admin_token: str):
        response = await client.post(
            "/api/admin/departments",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": "Engineering", "description": "Software Engineering"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Engineering"

    @pytest.mark.asyncio
    async def test_assign_user_to_department(self, client: AsyncClient, super_admin_token: str):
        dept_resp = await client.post(
            "/api/admin/departments",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": "Test Dept"}
        )
        dept_id = dept_resp.json()["id"]

        user_resp = await client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"username": "dept_user", "password": "Pass123!"}
        )
        user_id = user_resp.json()["id"]

        response = await client.put(
            f"/api/admin/users/{user_id}/department",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"department_id": dept_id}
        )
        assert response.status_code == 200
```

#### 资源可见性测试

```python
class TestResourceVisibility:
    """Agent/Skill visibility control tests."""

    @pytest.mark.asyncio
    async def test_public_agent_visible_to_all(self, client: AsyncClient, user_token: str):
        response = await client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_private_agent_only_visible_to_owner(
        self, client: AsyncClient, user_token: str, other_user_token: str
    ):
        create_resp = await client.post(
            "/api/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"name": "private_agent", "visibility": "private"}
        )
        agent_id = create_resp.json()["id"]

        owner_resp = await client.get(
            f"/api/agents/{agent_id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert owner_resp.status_code == 200

        other_resp = await client.get(
            f"/api/agents/{agent_id}",
            headers={"Authorization": f"Bearer {other_user_token}"}
        )
        assert other_resp.status_code == 404
```

### 1.3 测试 Fixtures

```python
"""Test fixtures for Admin API tests."""

import pytest
from httpx import AsyncClient
from app.gateway.app import create_app


@pytest.fixture
async def client():
    """Create async test client."""
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def super_admin_token(client: AsyncClient):
    """Get super admin authentication token."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPass123!"}
    )
    return response.json()["access_token"]


@pytest.fixture
async def user_token(client: AsyncClient):
    """Get regular user authentication token."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "user", "password": "UserPass123!"}
    )
    return response.json()["access_token"]


@pytest.fixture
async def other_user_token(client: AsyncClient):
    """Get other user authentication token."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "other_user", "password": "OtherPass123!"}
    )
    return response.json()["access_token"]
```

### 1.4 预期测试数量

| 测试类 | 测试数量 |
|--------|----------|
| TestAdminStats | 5 |
| TestUserManagement | 12 |
| TestDepartmentManagement | 8 |
| TestResourceVisibility | 8 |
| **总计** | **33+** |

---

## 2. 工作流执行器集成测试

### 2.1 测试文件位置

```
backend/tests/test_workflow_executor_integration.py
```

### 2.2 测试内容

#### 基础工作流测试

```python
"""Workflow executor integration tests."""

import pytest
from ideer.workflows.executor import WorkflowExecutor
from ideer.workflows.parser import parse_workflow_string


class TestWorkflowExecution:
    """End-to-end workflow execution tests."""

    @pytest.mark.asyncio
    async def test_simple_agent_workflow(self, mock_agent):
        yaml_content = """
        name: simple_test
        description: Simple agent test
        version: "1.0"
        steps:
          - id: research
            type: agent
            agent: researcher
            prompt: "Research AI trends"
        """
        wf = parse_workflow_string(yaml_content)
        executor = WorkflowExecutor(wf)
        state = await executor.run(inputs={})
        assert state.status == "completed"
        assert "research" in state.steps_state

    @pytest.mark.asyncio
    async def test_parallel_workflow(self, mock_agent):
        yaml_content = """
        name: parallel_test
        description: Parallel execution test
        version: "1.0"
        steps:
          - id: parallel_tasks
            type: parallel
            steps:
              - id: task1
                type: agent
                agent: worker
                prompt: "Task 1"
              - id: task2
                type: agent
                agent: worker
                prompt: "Task 2"
        """
        wf = parse_workflow_string(yaml_content)
        executor = WorkflowExecutor(wf)
        state = await executor.run(inputs={})
        assert state.status == "completed"

    @pytest.mark.asyncio
    async def test_condition_workflow(self, mock_agent):
        yaml_content = """
        name: condition_test
        description: Condition test
        version: "1.0"
        inputs:
          score:
            type: number
            default: 85
        steps:
          - id: check
            type: condition
            expression: "{{inputs.score}} > 80"
            then: pass_step
            else: fail_step
          - id: pass_step
            type: agent
            agent: processor
            prompt: "Score is high"
          - id: fail_step
            type: agent
            agent: processor
            prompt: "Score is low"
        """
        wf = parse_workflow_string(yaml_content)
        executor = WorkflowExecutor(wf)
        state = await executor.run(inputs={"score": 85})
        assert state.status == "completed"
        assert state.steps_state["pass_step"].status == "completed"
        assert state.steps_state.get("fail_step") is None

    @pytest.mark.asyncio
    async def test_loop_workflow(self, mock_agent):
        yaml_content = """
        name: loop_test
        description: Loop test
        version: "1.0"
        inputs:
          items:
            type: array
            default: ["item1", "item2", "item3"]
        steps:
          - id: process_items
            type: loop
            items: "{{inputs.items}}"
            steps:
              - id: process
                type: agent
                agent: processor
                prompt: "Process {{item}}"
        """
        wf = parse_workflow_string(yaml_content)
        executor = WorkflowExecutor(wf)
        state = await executor.run(inputs={"items": ["a", "b", "c"]})
        assert state.status == "completed"
```

#### 错误处理测试

```python
class TestErrorHandling:
    """Error handling tests."""

    @pytest.mark.asyncio
    async def test_invalid_yaml_raises_error(self):
        invalid_yaml = """
        name: invalid
        steps:
          - id: step1
            type: invalid_type
        """
        with pytest.raises(ValueError):
            parse_workflow_string(invalid_yaml)

    @pytest.mark.asyncio
    async def test_missing_required_input_raises_error(self):
        yaml_content = """
        name: input_test
        inputs:
          required_param:
            type: string
            required: true
        steps:
          - id: step1
            type: agent
            agent: worker
            prompt: "{{inputs.required_param}}"
        """
        wf = parse_workflow_string(yaml_content)
        executor = WorkflowExecutor(wf)
        with pytest.raises(ValueError, match="Missing required input"):
            await executor.run(inputs={})

    @pytest.mark.asyncio
    async def test_step_failure_stops_workflow(self):
        yaml_content = """
        name: failure_test
        steps:
          - id: step1
            type: agent
            agent: failing_agent
            prompt: "This will fail"
          - id: step2
            type: agent
            agent: worker
            prompt: "This should not run"
        """
        wf = parse_workflow_string(yaml_content)
        executor = WorkflowExecutor(wf)
        state = await executor.run(inputs={})
        assert state.status == "failed"
```

### 2.3 测试 Fixtures

```python
"""Test fixtures for Workflow Executor tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    agent.arun.return_value = MagicMock(
        output="Test output",
        metadata={"model": "test"}
    )
    return agent


@pytest.fixture
def mock_agent_with_errors():
    agent = AsyncMock()
    agent.arun.side_effect = [
        Exception("Temporary failure"),
        Exception("Temporary failure"),
        MagicMock(output="Success", metadata={"model": "test"})
    ]
    return agent


@pytest.fixture
def slow_agent():
    import asyncio
    async def slow_run(*args, **kwargs):
        await asyncio.sleep(10)
        return MagicMock(output="Slow output")
    agent = AsyncMock()
    agent.arun.side_effect = slow_run
    return agent
```

### 2.4 预期测试数量

| 测试类 | 测试数量 |
|--------|----------|
| TestWorkflowExecution | 12 |
| TestTemplateRendering | 6 |
| TestErrorHandling | 6 |
| **总计** | **24+** |

---

## 3. 前端 E2E 测试扩展

### 3.1 现有测试

当前 `frontend/tests/e2e/` 已有 8 个 spec 文件，覆盖：sidebar、artifacts、thread history、chat、landing page。

### 3.2 需要补充的测试

#### Admin 页面测试

```typescript
/* frontend/tests/e2e/admin.spec.ts */

import { test, expect } from '@playwright/test';

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'AdminPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/workspace');
  });

  test('displays dashboard statistics', async ({ page }) => {
    await page.goto('/workspace/admin');
    await expect(page.locator('text=Total Users')).toBeVisible();
    await expect(page.locator('text=Total Departments')).toBeVisible();
  });

  test('navigates to user management', async ({ page }) => {
    await page.goto('/workspace/admin');
    await page.click('text=User Management');
    await expect(page).toHaveURL('/workspace/admin/users');
  });

  test('creates new user', async ({ page }) => {
    await page.goto('/workspace/admin/users');
    await page.click('button:has-text("Add User")');
    await page.fill('[name="username"]', 'newuser');
    await page.fill('[name="password"]', 'NewPass123!');
    await page.selectOption('[name="role"]', 'user');
    await page.click('button:has-text("Create")');
    await expect(page.locator('text=newuser')).toBeVisible();
  });
});
```

#### Workflow 页面测试

```typescript
/* frontend/tests/e2e/workflows.spec.ts */

import { test, expect } from '@playwright/test';

test.describe('Workflow Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'AdminPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/workspace');
  });

  test('lists all workflows', async ({ page }) => {
    await page.goto('/workspace/workflows');
    await expect(page.locator('h1')).toContainText('Workflows');
  });

  test('creates new workflow', async ({ page }) => {
    await page.goto('/workspace/workflows/new');
    await page.fill('[name="name"]', 'test_workflow');
    const yamlContent = `
name: test_workflow
description: Test workflow
version: "1.0"
steps:
  - id: research
    type: agent
    agent: researcher
    prompt: "Research AI trends"
`;
    await page.fill('[name="yaml"]', yamlContent);
    await page.click('button:has-text("Create")');
    await expect(page.locator('text=Workflow created')).toBeVisible();
  });
});
```

### 3.3 预期测试数量

| 测试文件 | 测试数量 |
|----------|----------|
| admin.spec.ts | 8 |
| workflows.spec.ts | 6 |
| settings.spec.ts | 4 |
| **总计** | **18+** |

---

## 4. 持续集成配置

### 4.1 GitHub Actions 配置

```yaml
# .github/workflows/test.yml

name: Tests

on:
  push:
    branches: [main, offline_feature]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: |
          cd backend
          uv sync

      - name: Run tests
        run: |
          cd backend
          uv run pytest --cov=app --cov=ideer --cov-report=xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd frontend
          pnpm install

      - name: Run unit tests
        run: |
          cd frontend
          pnpm test

      - name: Run E2E tests
        run: |
          cd frontend
          pnpm exec playwright install --with-deps
          pnpm exec playwright test

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: frontend/playwright-report/
```

---

## 5. 总结

### 5.1 预期测试数量

| 测试类型 | 当前数量 | 目标新增 | 总计 |
|----------|----------|----------|------|
| 后端单元/集成 | 211 文件 | +57 测试 | 211+ 文件 |
| 前端 E2E | 8 spec | +18 测试 | 26 spec |
| 前端单元 | 22 文件 | 不变 | 22 文件 |

### 5.2 工作量估算

| 任务 | 预计工作量 |
|------|------------|
| Admin API 测试 | 2-3 天 |
| 工作流集成测试 | 2-3 天 |
| 前端 E2E 测试 | 2-3 天 |
| CI/CD 配置 | 0.5 天 |
| **总计** | **7-10 天** |
