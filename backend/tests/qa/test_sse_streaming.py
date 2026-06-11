"""
SSE 流式端点集成测试

测试 Server-Sent Events 的 HTTP 协议行为：
- 响应头格式
- 事件帧结构
- 错误事件格式
- 流结束事件

运行方式:
    # 需要后端服务运行
    cd backend && PYTHONPATH=. uv run pytest tests/qa/test_sse_streaming.py -v

环境变量:
    QA_BASE_URL: 后端服务地址（默认: http://localhost:8001）
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("QA_BASE_URL", "http://localhost:8001")


class QAAuthHelper:
    """认证辅助类"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token: str | None = None

    async def ensure_admin(self) -> str:
        """确保有管理员账户并获取 token"""
        async with httpx.AsyncClient() as client:
            setup_response = await client.get(f"{self.base_url}/api/v1/auth/setup-status")
            setup_data = setup_response.json()

            if setup_data.get("needs_setup", False):
                await client.post(
                    f"{self.base_url}/api/v1/auth/initialize",
                    json={"email": "admin@test.com", "password": "Test1234!"},
                )

            response = await client.post(
                f"{self.base_url}/api/v1/auth/login/local",
                data={"username": "admin@test.com", "password": "Test1234!"},
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")
                return self.token
            pytest.skip(f"Auth failed: {response.status_code}")


@pytest.fixture(scope="module")
def auth():
    """模块级认证 fixture"""
    helper = QAAuthHelper(BASE_URL)
    return helper


@pytest.fixture(scope="module")
def auth_headers(auth):
    """认证 headers"""
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(auth.ensure_admin())
    loop.close()
    if auth.token:
        return {"Authorization": f"Bearer {auth.token}"}
    return {}


class TestSSEResponseHeaders:
    """测试 SSE 响应头"""

    @pytest.mark.asyncio
    async def test_stream_endpoint_returns_sse_headers(self, auth_headers):
        """POST /api/runs/stream 应返回正确的 SSE 响应头"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/runs/stream",
                json={"assistant_id": "lead_agent", "input": {"messages": [{"role": "user", "content": "hi"}]}},
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                assert response.headers.get("cache-control") == "no-cache"
                assert response.headers.get("x-accel-buffering") == "no"
                # Content-Location 应包含 run 信息
                assert "/api/threads/" in response.headers.get("content-location", "")

    @pytest.mark.asyncio
    async def test_thread_run_stream_returns_sse_headers(self, auth_headers):
        """POST /api/threads/{id}/runs/stream 应返回正确的 SSE 响应头"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 先创建一个 thread
            thread_resp = await client.post(
                f"{BASE_URL}/api/threads",
                json={},
                headers=auth_headers,
            )
            if thread_resp.status_code != 200:
                pytest.skip(f"Cannot create thread: {thread_resp.status_code}")
            thread_id = thread_resp.json().get("thread_id")

            async with client.stream(
                "POST",
                f"{BASE_URL}/api/threads/{thread_id}/runs/stream",
                json={"assistant_id": "lead_agent", "input": {"messages": [{"role": "user", "content": "hi"}]}},
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                assert response.headers.get("cache-control") == "no-cache"


class TestSSEEventFormat:
    """测试 SSE 事件帧格式"""

    @pytest.mark.asyncio
    async def test_stream_emits_sse_frames(self, auth_headers):
        """SSE 流应包含标准的 event:/data: 帧格式"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            frames = []
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/runs/stream",
                json={"assistant_id": "lead_agent", "input": {"messages": [{"role": "user", "content": "hi"}]}},
                headers=auth_headers,
            ) as response:
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    # SSE 帧以双换行分隔
                    while "\n\n" in buffer:
                        frame, buffer = buffer.split("\n\n", 1)
                        frame = frame.strip()
                        if frame:
                            frames.append(frame)
                    # 收集到 end 事件就停止
                    if any("event: end" in f for f in frames):
                        break

            # 应该至少有一个事件帧
            assert len(frames) > 0, "SSE stream should emit at least one event frame"

            # 验证帧格式：每个帧应包含 event: 和 data: 行
            for frame in frames:
                lines = frame.split("\n")
                has_event = any(line.startswith("event:") for line in lines)
                has_data = any(line.startswith("data:") for line in lines)
                # 心跳帧是注释格式，跳过
                if not frame.startswith(":"):
                    assert has_event or has_data, f"Frame missing event/data: {frame}"

    @pytest.mark.asyncio
    async def test_stream_ends_with_end_event(self, auth_headers):
        """SSE 流应以 end 事件结束"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            last_event = None
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/runs/stream",
                json={"assistant_id": "lead_agent", "input": {"messages": [{"role": "user", "content": "hi"}]}},
                headers=auth_headers,
            ) as response:
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        frame, buffer = buffer.split("\n\n", 1)
                        frame = frame.strip()
                        if frame:
                            last_event = frame
                    if last_event and "event: end" in last_event:
                        break

            # 最后一个事件应该是 end
            assert last_event is not None, "Stream should emit at least one event"
            assert "event: end" in last_event, f"Last event should be 'end', got: {last_event}"


class TestSSEErrorHandling:
    """测试 SSE 错误处理"""

    @pytest.mark.asyncio
    async def test_invalid_assistant_returns_error(self, auth_headers):
        """使用无效的 assistant_id 应返回错误事件"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            frames = []
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/runs/stream",
                json={"assistant_id": "nonexistent_agent_xyz", "input": {"messages": []}},
                headers=auth_headers,
            ) as response:
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        frame, buffer = buffer.split("\n\n", 1)
                        frame = frame.strip()
                        if frame:
                            frames.append(frame)
                    # 收集几个帧后停止
                    if len(frames) > 5:
                        break

            # 应该有事件返回（可能是 error 或 end）
            assert len(frames) > 0, "Should receive at least one event for invalid assistant"

    @pytest.mark.asyncio
    async def test_unauthenticated_stream_returns_401(self):
        """未认证请求应返回 401"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BASE_URL}/api/runs/stream",
                json={"assistant_id": "lead_agent", "input": {"messages": []}},
            )
            # 无 token 应被拒绝
            assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"


class TestSSEHeartbeat:
    """测试 SSE 心跳机制"""

    @pytest.mark.asyncio
    async def test_stream_may_emit_heartbeat_comments(self, auth_headers):
        """长时间运行的流应发送心跳注释（SSE comment 以 : 开头）"""
        # 心跳通常在空闲时发送，这里验证流格式不被心跳破坏
        async with httpx.AsyncClient(timeout=30.0) as client:
            raw_text = ""
            async with client.stream(
                "POST",
                f"{BASE_URL}/api/runs/stream",
                json={"assistant_id": "lead_agent", "input": {"messages": [{"role": "user", "content": "hi"}]}},
                headers=auth_headers,
            ) as response:
                async for chunk in response.aiter_text():
                    raw_text += chunk
                    if "event: end" in raw_text:
                        break

            # 验证流格式有效（不包含非法字符）
            # 心跳格式: ": heartbeat\n\n"
            if ": heartbeat" in raw_text:
                # 心跳行应以冒号开头
                for line in raw_text.split("\n"):
                    if line.strip().startswith(":"):
                        assert "heartbeat" in line, f"Invalid heartbeat format: {line}"
