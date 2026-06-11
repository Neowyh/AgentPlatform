"""
QA 测试配置

提供 QA 测试的 fixtures 和辅助函数。
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("QA_BASE_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
def base_url():
    """测试基础 URL"""
    return BASE_URL


@pytest.fixture(scope="session")
async def admin_token(base_url):
    """获取管理员 token（session 级别）"""
    async with httpx.AsyncClient() as client:
        # 初始化管理员
        await client.post(
            f"{base_url}/api/v1/auth/initialize",
            json={"email": "admin@test.com", "password": "Test1234!"},
        )

        # 登录
        response = await client.post(
            f"{base_url}/api/v1/auth/login/local",
            data={"username": "admin@test.com", "password": "Test1234!"},
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None


@pytest.fixture
def auth_headers(admin_token):
    """认证 headers"""
    if admin_token:
        return {"Authorization": f"Bearer {admin_token}"}
    return {}
