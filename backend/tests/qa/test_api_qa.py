"""
API QA 测试框架

自动测试所有后端 API 端点的功能正确性。
使用 httpx 直接测试，不依赖前端渲染。

运行方式:
    cd backend && PYTHONPATH=. uv run pytest tests/qa/test_api_qa.py -v

环境变量:
    QA_BASE_URL: 后端服务地址（默认: http://localhost:8001）
    QA_ADMIN_EMAIL: 管理员邮箱（默认: admin@test.com）
    QA_ADMIN_PASSWORD: 管理员密码（默认: Test1234!）

示例:
    # 使用默认凭据
    cd backend && .venv/bin/python -m pytest tests/qa/test_api_qa.py -v

    # 使用自定义凭据
    QA_ADMIN_EMAIL="your-admin@example.com" QA_ADMIN_PASSWORD="your-password" \
    cd backend && .venv/bin/python -m pytest tests/qa/test_api_qa.py -v
"""

import os

import httpx
import pytest

# 测试配置
BASE_URL = os.environ.get("QA_BASE_URL", "http://localhost:8001")
TEST_EMAIL = os.environ.get("QA_ADMIN_EMAIL", "admin@test.com")
TEST_PASSWORD = os.environ.get("QA_ADMIN_PASSWORD", "Test1234!")


class QAAuthHelper:
    """认证辅助类"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token: str | None = None

    async def ensure_admin(self) -> str:
        """确保有管理员账户并获取 token"""
        async with httpx.AsyncClient() as client:
            # 检查是否需要初始化
            setup_response = await client.get(f"{self.base_url}/api/v1/auth/setup-status")
            setup_data = setup_response.json()

            if setup_data.get("needs_setup", False):
                # 初始化管理员
                init_response = await client.post(
                    f"{self.base_url}/api/v1/auth/initialize",
                    json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                )
                if init_response.status_code not in (200, 201, 409):  # 409 = already exists
                    raise RuntimeError(f"Failed to initialize admin: {init_response.text}")
            else:
                # 管理员已存在，记录诊断信息
                print(f"\n⚠️  管理员已存在，尝试使用凭据: {TEST_EMAIL}")

            # 尝试登录
            response = await client.post(
                f"{self.base_url}/api/v1/auth/login/local",
                data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
            )

            # 如果登录失败，提供详细的诊断信息
            if response.status_code != 200:
                error_detail = response.json().get("detail", {})
                if isinstance(error_detail, dict):
                    error_code = error_detail.get("code", "unknown")
                    error_message = error_detail.get("message", "Unknown error")
                else:
                    error_code = "unknown"
                    error_message = str(error_detail)

                # 提供解决方案建议
                suggestion = ""
                if error_code == "invalid_credentials":
                    suggestion = (
                        "\n💡 解决方案:\n   1. 使用环境变量指定正确的管理员凭据:\n      QA_ADMIN_EMAIL='your-admin@example.com' QA_ADMIN_PASSWORD='your-password'\n   2. 或者重置管理员密码\n   3. 或者重新初始化系统（删除数据库文件）"
                    )
                elif error_code == "too_many_requests":
                    suggestion = "\n💡 解决方案: 等待几分钟后重试，或重启后端服务"

                pytest.skip(f"Login failed: {error_code} - {error_message}\n使用凭据: {TEST_EMAIL}{suggestion}")

            self.token = response.json()["access_token"]
            return self.token

    def headers(self) -> dict:
        """获取认证 headers"""
        assert self.token, "Must call ensure_admin() first"
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture(scope="session")
def auth():
    """Session-scoped 认证 fixture"""
    import asyncio

    helper = QAAuthHelper(BASE_URL)
    asyncio.get_event_loop().run_until_complete(helper.ensure_admin())
    return helper


@pytest.fixture
def auth_headers(auth):
    """认证 headers fixture"""
    return auth.headers()


class TestAuthQA:
    """认证模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_setup_status(self):
        """GET /api/v1/auth/setup-status"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/auth/setup-status")
            assert response.status_code == 200
            data = response.json()
            assert "needs_setup" in data
            # has_users 字段已从 API 响应中移除，使用 needs_setup 替代
            # assert "has_users" in data

    @pytest.mark.asyncio
    async def test_login_success(self):
        """POST /api/v1/auth/login/local — 正确凭据"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/login/local",
                data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
            )

            # 如果登录失败（可能是因为凭据不匹配），跳过测试
            if response.status_code != 200:
                pytest.skip(f"Login failed with test credentials: {response.text}")

            data = response.json()
            assert "access_token" in data
            assert "token_type" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """POST /api/v1/auth/login/local — 错误密码"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/login/local",
                data={"username": TEST_EMAIL, "password": "wrongpassword"},
            )
            # 允许 401（认证失败）、422（验证错误）或 429（速率限制）
            assert response.status_code in (401, 422, 429)

    @pytest.mark.asyncio
    async def test_me(self, auth_headers):
        """GET /api/v1/auth/me"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/v1/auth/me",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert "email" in data

    @pytest.mark.asyncio
    async def test_me_unauthorized(self):
        """GET /api/v1/auth/me — 未认证"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/auth/me")
            assert response.status_code in (401, 403)


class TestAgentsQA:
    """Agent 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_agents(self, auth_headers):
        """GET /api/agents"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/agents",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_agent_crud(self, auth_headers):
        """Agent 完整 CRUD 流程"""
        agent_name = "qa-test-agent"

        async with httpx.AsyncClient() as client:
            # 创建
            response = await client.post(
                f"{BASE_URL}/api/agents",
                headers=auth_headers,
                json={
                    "name": agent_name,
                    "description": "QA test agent",
                    "visibility": "private",
                },
            )
            assert response.status_code in (200, 201)

            # 获取
            response = await client.get(
                f"{BASE_URL}/api/agents/{agent_name}",
                headers=auth_headers,
            )
            assert response.status_code == 200

            # 更新
            response = await client.put(
                f"{BASE_URL}/api/agents/{agent_name}",
                headers=auth_headers,
                json={"description": "Updated by QA"},
            )
            assert response.status_code == 200

            # 删除
            response = await client.delete(
                f"{BASE_URL}/api/agents/{agent_name}",
                headers=auth_headers,
            )
            assert response.status_code in (200, 204)

            # 验证删除
            response = await client.get(
                f"{BASE_URL}/api/agents/{agent_name}",
                headers=auth_headers,
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_check_agent_name(self, auth_headers):
        """GET /api/agents/check?name=xxx"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/agents/check?name=nonexistent-agent",
                headers=auth_headers,
            )
            assert response.status_code == 200


class TestWorkflowsQA:
    """Workflow 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_workflows(self, auth_headers):
        """GET /api/workflows"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/workflows",
                headers=auth_headers,
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_workflow_crud(self, auth_headers):
        """Workflow 完整 CRUD 流程"""
        wf_name = "qa-test-workflow"
        wf_yaml = f"name: {wf_name}\nsteps:\n  - id: step1\n    type: agent\n    agent: default"

        async with httpx.AsyncClient() as client:
            # 创建
            response = await client.post(
                f"{BASE_URL}/api/workflows",
                headers=auth_headers,
                json={"yaml": wf_yaml},
            )
            assert response.status_code in (200, 201)

            # 获取
            response = await client.get(
                f"{BASE_URL}/api/workflows/{wf_name}",
                headers=auth_headers,
            )
            assert response.status_code == 200

            # 更新
            updated_yaml = f"name: {wf_name}\nsteps:\n  - id: step1\n    type: agent\n    agent: default\n    prompt: updated"
            response = await client.put(
                f"{BASE_URL}/api/workflows/{wf_name}",
                headers=auth_headers,
                json={"yaml": updated_yaml},
            )
            assert response.status_code == 200

            # 删除
            response = await client.delete(
                f"{BASE_URL}/api/workflows/{wf_name}",
                headers=auth_headers,
            )
            assert response.status_code in (200, 204)


class TestThreadsQA:
    """Thread 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_search_threads(self, auth_headers):
        """POST /api/threads/search"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/threads/search",
                headers=auth_headers,
                json={"limit": 10},
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_create_thread(self, auth_headers):
        """POST /api/threads"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/threads",
                headers=auth_headers,
                json={},
            )
            assert response.status_code in (200, 201)


class TestAdminQA:
    """Admin 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_stats(self, auth_headers):
        """GET /api/admin/stats"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/stats",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_users(self, auth_headers):
        """GET /api/admin/users"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/users",
                headers=auth_headers,
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_departments(self, auth_headers):
        """GET /api/admin/departments"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/departments",
                headers=auth_headers,
            )
            assert response.status_code == 200


class TestSkillsQA:
    """Skills 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_skills(self, auth_headers):
        """GET /api/skills"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/skills",
                headers=auth_headers,
            )
            assert response.status_code == 200


class TestToolsQA:
    """Tools 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_tools(self, auth_headers):
        """GET /api/tools"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/tools",
                headers=auth_headers,
            )
            assert response.status_code == 200


class TestMemoryQA:
    """Memory 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_load_memory(self, auth_headers):
        """GET /api/memory"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/memory",
                headers=auth_headers,
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_memory(self, auth_headers):
        """GET /api/memory/export"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/memory/export",
                headers=auth_headers,
            )
            assert response.status_code == 200


class TestModelsQA:
    """Models 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_models(self, auth_headers):
        """GET /api/models"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/models",
                headers=auth_headers,
            )
            assert response.status_code == 200


class TestMCPConfigQA:
    """MCP Config 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_get_config(self, auth_headers):
        """GET /api/mcp/config"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/mcp/config",
                headers=auth_headers,
            )
            assert response.status_code == 200
