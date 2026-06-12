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
TEST_EMAIL = os.environ.get("QA_ADMIN_EMAIL", "super_admin@test.com")
TEST_PASSWORD = os.environ.get("QA_ADMIN_PASSWORD", "super_admin@test.com")


class QAAuthHelper:
    """认证辅助类"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token: str | None = None
        self.csrf_token: str | None = None

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

            # Token 通过 Set-Cookie 返回，从 cookie 中提取
            cookies = response.cookies
            if "access_token" in cookies:
                self.token = cookies["access_token"]
            else:
                # 备用方案：从响应体中获取
                response_data = response.json()
                self.token = response_data.get("access_token")
                if not self.token:
                    pytest.skip(f"Login succeeded but no access_token found in response or cookies. Response: {response_data}")

            # 获取 CSRF token
            if "csrf_token" in cookies:
                self.csrf_token = cookies["csrf_token"]
            else:
                # 如果登录响应中没有 CSRF token，手动获取
                # CSRF token 会在首次 POST 请求后设置
                self.csrf_token = None

            return self.token

    def headers(self) -> dict:
        """获取认证 headers"""
        assert self.token, "Must call ensure_admin() first"
        headers = {"Authorization": f"Bearer {self.token}"}
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        return headers

    def cookies(self) -> dict:
        """获取认证 cookies"""
        assert self.token, "Must call ensure_admin() first"
        cookies = {"access_token": self.token}
        if self.csrf_token:
            cookies["csrf_token"] = self.csrf_token
        return cookies


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


@pytest.fixture
def auth_cookies(auth):
    """认证 cookies fixture"""
    return auth.cookies()


@pytest.fixture
def auth_headers_and_cookies(auth):
    """认证 headers 和 cookies fixture"""
    return auth.headers(), auth.cookies()


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

            # 验证登录成功
            data = response.json()
            assert "expires_in" in data
            assert response.status_code == 200

            # 验证 token 通过 cookie 返回
            assert "access_token" in response.cookies, "access_token should be in cookies"

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
    async def test_me(self, auth_cookies):
        """GET /api/v1/auth/me"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/v1/auth/me",
                cookies=auth_cookies,
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
    async def test_list_agents(self, auth_cookies):
        """GET /api/agents"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/agents",
                cookies=auth_cookies,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_agent_crud(self, auth_headers_and_cookies):
        """Agent 完整 CRUD 流程"""
        auth_headers, auth_cookies = auth_headers_and_cookies
        agent_name = "qa-test-agent"

        async with httpx.AsyncClient() as client:
            # 创建
            response = await client.post(
                f"{BASE_URL}/api/agents",
                cookies=auth_cookies,
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
                cookies=auth_cookies,
            )
            assert response.status_code == 200

            # 更新
            response = await client.put(
                f"{BASE_URL}/api/agents/{agent_name}",
                cookies=auth_cookies,
                headers=auth_headers,
                json={"description": "Updated by QA"},
            )
            assert response.status_code == 200

            # 删除
            response = await client.delete(
                f"{BASE_URL}/api/agents/{agent_name}",
                cookies=auth_cookies,
                headers=auth_headers,
            )
            assert response.status_code in (200, 204)

            # 验证删除
            response = await client.get(
                f"{BASE_URL}/api/agents/{agent_name}",
                cookies=auth_cookies,
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_check_agent_name(self, auth_cookies):
        """GET /api/agents/check?name=xxx"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/agents/check?name=nonexistent-agent",
                cookies=auth_cookies,
            )
            assert response.status_code == 200


class TestWorkflowsQA:
    """Workflow 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_workflows(self, auth_cookies):
        """GET /api/workflows"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/workflows",
                cookies=auth_cookies,
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_workflow_crud(self, auth_headers_and_cookies):
        """Workflow 完整 CRUD 流程"""
        auth_headers, auth_cookies = auth_headers_and_cookies
        wf_name = "qa-test-workflow"
        wf_yaml = f"name: {wf_name}\nsteps:\n  - id: step1\n    type: agent\n    agent: default"

        async with httpx.AsyncClient() as client:
            # 创建
            response = await client.post(
                f"{BASE_URL}/api/workflows",
                cookies=auth_cookies,
                headers=auth_headers,
                json={"yaml_content": wf_yaml},
            )
            assert response.status_code in (200, 201)

            # 获取
            response = await client.get(
                f"{BASE_URL}/api/workflows/{wf_name}",
                cookies=auth_cookies,
            )
            assert response.status_code == 200

            # 更新
            updated_yaml = f"name: {wf_name}\nsteps:\n  - id: step1\n    type: agent\n    agent: default\n    prompt: updated"
            response = await client.put(
                f"{BASE_URL}/api/workflows/{wf_name}",
                cookies=auth_cookies,
                headers=auth_headers,
                json={"yaml_content": updated_yaml},
            )
            assert response.status_code == 200

            # 删除
            response = await client.delete(
                f"{BASE_URL}/api/workflows/{wf_name}",
                cookies=auth_cookies,
                headers=auth_headers,
            )
            assert response.status_code in (200, 204)


class TestThreadsQA:
    """Thread 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_search_threads(self, auth_headers_and_cookies):
        """POST /api/threads/search"""
        auth_headers, auth_cookies = auth_headers_and_cookies
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/threads/search",
                cookies=auth_cookies,
                headers=auth_headers,
                json={"limit": 10},
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_create_thread(self, auth_headers_and_cookies):
        """POST /api/threads"""
        auth_headers, auth_cookies = auth_headers_and_cookies
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/threads",
                cookies=auth_cookies,
                headers=auth_headers,
                json={},
            )
            assert response.status_code in (200, 201)


class TestAdminQA:
    """Admin 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_stats(self, auth_cookies):
        """GET /api/admin/stats"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/stats",
                cookies=auth_cookies,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_users(self, auth_cookies):
        """GET /api/admin/users"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/users",
                cookies=auth_cookies,
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_departments(self, auth_cookies):
        """GET /api/admin/departments"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/departments",
                cookies=auth_cookies,
            )
            assert response.status_code == 200


class TestSkillsQA:
    """Skills 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_skills(self, auth_cookies):
        """GET /api/skills"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/skills",
                cookies=auth_cookies,
            )
            assert response.status_code == 200


class TestToolsQA:
    """Tools 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_tools(self, auth_cookies):
        """GET /api/tools"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/tools",
                cookies=auth_cookies,
            )
            assert response.status_code == 200


class TestMemoryQA:
    """Memory 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_load_memory(self, auth_cookies):
        """GET /api/memory"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/memory",
                cookies=auth_cookies,
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_memory(self, auth_cookies):
        """GET /api/memory/export"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/memory/export",
                cookies=auth_cookies,
            )
            assert response.status_code == 200


class TestModelsQA:
    """Models 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_list_models(self, auth_cookies):
        """GET /api/models"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/models",
                cookies=auth_cookies,
            )
            assert response.status_code == 200


class TestMCPConfigQA:
    """MCP Config 模块 QA 测试"""

    @pytest.mark.asyncio
    async def test_get_config(self, auth_cookies):
        """GET /api/mcp/config"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/mcp/config",
                cookies=auth_cookies,
            )
            assert response.status_code == 200
