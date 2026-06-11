# 安全加固方案

## 概述

本方案基于代码审查发现的真实安全漏洞，针对性地进行安全加固。当前已有 `auth_middleware.py` 和 `csrf_middleware.py`，本方案补充限流、输入验证和审计日志。

> 注意：部分安全问题已在 `01-bug-fix-and-feature-completion.md` 中列为 Bug（如 auth bypass、权限升级），本文档聚焦于新增安全措施。

---

## 1. API 限流

### 1.1 目标

- 防止 API 暴力破解（当前 `_login_attempts` 仅内存存储，多 worker 不共享）
- 保护系统稳定性

### 1.2 实现方式

在 `backend/app/gateway/` 下新建限流中间件，复用现有中间件注册模式（参考 `auth_middleware.py`）。

```python
"""backend/app/gateway/rate_limit_middleware.py"""

import time
import logging
from typing import Dict, Callable
from collections import defaultdict
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Rate limit configuration."""
    def __init__(self, requests: int = 100, window: int = 60):
        self.requests = requests
        self.window = window


# Rate limit by role
RATE_LIMITS: Dict[str, RateLimitConfig] = {
    "viewer": RateLimitConfig(requests=50, window=60),
    "user": RateLimitConfig(requests=200, window=60),
    "department_admin": RateLimitConfig(requests=500, window=60),
    "super_admin": RateLimitConfig(requests=1000, window=60),
}

# Endpoint-specific limits
ENDPOINT_LIMITS: Dict[str, RateLimitConfig] = {
    "/api/auth/login": RateLimitConfig(requests=10, window=60),
    "/api/auth/register": RateLimitConfig(requests=5, window=60),
}


class RateLimitStore:
    """In-memory rate limit store. For multi-worker, use Redis."""
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str, config: RateLimitConfig) -> tuple[bool, Dict[str, str]]:
        now = time.time()
        window_start = now - config.window

        # Clean old requests
        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        if len(self._requests[key]) >= config.requests:
            oldest = self._requests[key][0]
            retry_after = int(oldest + config.window - now) + 1
            return False, {
                "X-RateLimit-Limit": str(config.requests),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(retry_after),
            }

        self._requests[key].append(now)
        remaining = config.requests - len(self._requests[key])
        return True, {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Remaining": str(remaining),
        }


_rate_limit_store = RateLimitStore()


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key from request."""
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user.id}"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        return "ip:unknown"

    return f"ip:{client_ip}"


def get_rate_limit_config(request: Request) -> RateLimitConfig:
    """Get rate limit config for request."""
    path = request.url.path
    for pattern, config in ENDPOINT_LIMITS.items():
        if path == pattern:
            return config

    user = getattr(request.state, "user", None)
    if user:
        role = getattr(user, "role", "user")
        return RATE_LIMITS.get(role, RATE_LIMITS["user"])

    return RATE_LIMITS.get("viewer", RateLimitConfig(requests=50, window=60))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        config = get_rate_limit_config(request)
        key = get_rate_limit_key(request)
        is_allowed, headers = _rate_limit_store.is_allowed(key, config)

        if not is_allowed:
            logger.warning("Rate limit exceeded for %s", key)
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers=headers
            )

        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response
```

### 1.3 集成到应用

在 `backend/app/gateway/app.py` 的 `create_app()` 中添加：

```python
from app.gateway.rate_limit_middleware import RateLimitMiddleware

# 在现有中间件之后添加
app.add_middleware(RateLimitMiddleware)
```

### 1.4 限流策略

| 角色 | 请求限制 | 时间窗口 |
|------|----------|----------|
| viewer | 50 | 60s |
| user | 200 | 60s |
| department_admin | 500 | 60s |
| super_admin | 1000 | 60s |

| 端点 | 请求限制 | 说明 |
|------|----------|------|
| /api/auth/login | 10/60s | 防止暴力破解 |
| /api/auth/register | 5/60s | 防止恶意注册 |

---

## 2. 输入验证增强

### 2.1 目标

- 防止 XSS 攻击
- 防止路径遍历
- 加强密码强度
- 防止 YAML 反序列化攻击

### 2.2 实现文件

```
backend/app/gateway/validators.py
```

### 2.3 核心实现

```python
"""backend/app/gateway/validators.py"""

import re
import html
import os
from typing import Any
from pydantic import field_validator


class SafeString(str):
    """Safe string type with XSS protection."""

    @classmethod
    def validate(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError('string required')
        v = v.replace('\x00', '')
        v = html.escape(v)
        return cls(v)


class SafePath(str):
    """Safe file path type with traversal protection."""

    @classmethod
    def validate(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError('string required')

        # Check for path traversal
        if '..' in v:
            raise ValueError('Path traversal detected')

        # Normalize path
        v = os.path.normpath(v)

        # Double-check after normalization
        if '..' in v:
            raise ValueError('Path traversal detected')

        return cls(v)


class Username(str):
    """Username with validation."""

    @classmethod
    def validate(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError('string required')

        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be 3-50 characters')

        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, hyphens, and dots')

        return cls(v)


class Password(str):
    """Password with strength validation."""

    @classmethod
    def validate(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError('string required')

        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')

        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters')

        # At least 2 of: uppercase, lowercase, digit, special
        checks = [
            (r'[A-Z]', 'uppercase'),
            (r'[a-z]', 'lowercase'),
            (r'[0-9]', 'digit'),
            (r'[!@#$%^&*(),.?":{}|<>]', 'special'),
        ]
        missing = [name for pattern, name in checks if not re.search(pattern, v)]

        if len(missing) > 2:
            raise ValueError('Password must contain at least 2 of: uppercase, lowercase, digit, special character')

        common = ['password', '12345678', 'qwerty123', 'letmein', 'welcome']
        if v.lower() in common:
            raise ValueError('This password is too common')

        return cls(v)


class WorkflowYAML(str):
    """Workflow YAML with validation."""

    @classmethod
    def validate(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError('string required')

        if len(v) > 100000:  # 100KB
            raise ValueError('Workflow YAML too large')

        # Check for dangerous YAML constructs
        dangerous = [
            r'!!python/',
            r'!!binary',
            r'!!merge',
        ]
        for pattern in dangerous:
            if re.search(pattern, v):
                raise ValueError('Dangerous YAML construct detected')

        # Validate YAML syntax
        try:
            import yaml
            data = yaml.safe_load(v)
            if not isinstance(data, dict):
                raise ValueError('YAML must be a mapping')
            if 'name' not in data:
                raise ValueError('Missing required field: name')
            if 'steps' not in data:
                raise ValueError('Missing required field: steps')
        except Exception as e:
            if 'Missing required field' in str(e) or 'YAML must be' in str(e):
                raise
            raise ValueError(f'Invalid YAML syntax: {e}')

        return cls(v)
```

### 2.4 验证规则汇总

| 类型 | 检查项 |
|------|--------|
| SafeString | 空字节移除、HTML 转义 |
| SafePath | 路径遍历（`..`）、路径规范化 |
| Username | 长度 3-50、字符限制 |
| Password | 长度 8-128、复杂度要求、常见密码拒绝 |
| WorkflowYAML | 大小限制 100KB、危险构造、语法验证 |

### 2.5 测试用例

```python
"""backend/tests/test_validators.py"""

import pytest
from app.gateway.validators import SafeString, SafePath, Username, Password, WorkflowYAML


class TestSafeString:
    def test_normal_string(self):
        result = SafeString.validate("hello world")
        assert result == "hello world"

    def test_html_escaped(self):
        result = SafeString.validate("<script>alert('xss')</script>")
        assert "<script>" not in result

    def test_null_bytes_removed(self):
        result = SafeString.validate("hello\x00world")
        assert "\x00" not in result


class TestSafePath:
    def test_normal_path(self):
        result = SafePath.validate("documents/file.txt")
        assert result == "documents/file.txt"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="Path traversal"):
            SafePath.validate("../../../etc/passwd")


class TestUsername:
    def test_valid_username(self):
        result = Username.validate("john.doe")
        assert result == "john.doe"

    def test_too_short(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            Username.validate("ab")


class TestPassword:
    def test_valid_password(self):
        result = Password.validate("StrongPass123!")
        assert result == "StrongPass123!"

    def test_too_short(self):
        with pytest.raises(ValueError, match="at least 8"):
            Password.validate("Pass1!")


class TestWorkflowYAML:
    def test_valid_yaml(self):
        yaml = """
        name: test
        steps:
          - id: step1
            type: agent
            agent: test
            prompt: "test"
        """
        result = WorkflowYAML.validate(yaml)
        assert "name: test" in result

    def test_dangerous_construct(self):
        yaml = """
        name: test
        data: !!python/object:os.system
        """
        with pytest.raises(ValueError, match="Dangerous YAML construct"):
            WorkflowYAML.validate(yaml)
```

---

## 3. 审计日志

### 3.1 目标

- 记录所有 API 操作
- 支持合规审计
- 敏感数据自动脱敏

### 3.2 实现文件

```
backend/app/gateway/audit_middleware.py
```

### 3.3 核心实现

```python
"""backend/app/gateway/audit_middleware.py"""

import json
import time
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("audit")


# Action mappings
ACTION_MAPPINGS = {
    "GET": "read",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# Resource type mappings
RESOURCE_MAPPINGS = {
    "/api/admin/users": "user",
    "/api/admin/departments": "department",
    "/api/workflows": "workflow",
    "/api/agents": "agent",
    "/api/skills": "skill",
    "/api/tools": "tool",
}

# Sensitive fields to redact
SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "authorization"}


def get_resource_type(path: str) -> str:
    for prefix, resource_type in RESOURCE_MAPPINGS.items():
        if path.startswith(prefix):
            return resource_type
    return "unknown"


def sanitize_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive data in request body."""
    sanitized = {}
    for key, value in body.items():
        if key.lower() in SENSITIVE_FIELDS:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_body(value)
        else:
            sanitized[key] = value
    return sanitized


class AuditMiddleware(BaseHTTPMiddleware):
    """Audit logging middleware."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health checks
        if request.url.path in ["/health", "/favicon.ico"]:
            return await call_next(request)
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Get user info
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None)
        username = getattr(user, "username", None)

        action = ACTION_MAPPINGS.get(request.method, "unknown")
        resource_type = get_resource_type(request.url.path)

        details = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
        }

        # Sanitize request body for POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_json = json.loads(body)
                    details["body"] = sanitize_body(body_json)
            except Exception:
                pass

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id,
                "user_id": user_id,
                "username": username,
                "action": action,
                "resource_type": resource_type,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "ip": request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown"),
                "details": details,
            }

            logger.info("Audit: %s", json.dumps(log_data))
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Audit error: %s",
                json.dumps({
                    "request_id": request_id,
                    "user_id": user_id,
                    "action": action,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                })
            )
            raise
```

### 3.4 集成到应用

```python
"""backend/app/gateway/app.py"""

from app.gateway.audit_middleware import AuditMiddleware

# 在限流中间件之后添加
app.add_middleware(AuditMiddleware)
```

### 3.5 审计日志字段

| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | string | ISO 时间戳 |
| request_id | string | 请求 UUID |
| user_id | string | 用户 ID |
| username | string | 用户名 |
| action | string | 操作类型 (read/create/update/delete) |
| resource_type | string | 资源类型 |
| status_code | int | HTTP 状态码 |
| duration_ms | float | 请求耗时（毫秒） |
| ip | string | 客户端 IP |
| details | object | 请求详情（敏感字段已脱敏） |

---

## 4. 安全头配置

### 4.1 在 app.py 中添加安全头

```python
"""backend/app/gateway/app.py"""

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

### 4.2 CORS 配置

```python
from fastapi.middleware.cors import CORSMiddleware

# 从环境变量读取允许的域名
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 5. 中间件注册顺序

在 `backend/app/gateway/app.py` 的 `create_app()` 中，中间件注册顺序应为：

```python
def create_app() -> FastAPI:
    app = FastAPI(...)

    # 1. CORS（最外层）
    app.add_middleware(CORSMiddleware, ...)

    # 2. 安全头
    @app.middleware("http")
    async def add_security_headers(request, call_next): ...

    # 3. 审计日志
    app.add_middleware(AuditMiddleware)

    # 4. 限流
    app.add_middleware(RateLimitMiddleware)

    # 5. CSRF（现有）
    app.add_middleware(CSRFMiddleware)

    # 6. Auth（最内层，最先执行认证）
    app.add_middleware(AuthMiddleware)

    return app
```

**注意**：FastAPI 中间件按注册顺序**反向执行**（后注册的先执行）。所以 AuthMiddleware 最先执行认证，然后 CSRF、限流、审计、安全头、CORS。

---

## 6. 总结

### 6.1 安全加固清单

| 安全措施 | 预计工作量 | 预期收益 |
|----------|------------|----------|
| API 限流 | 1-2 天 | 防止暴力破解 |
| 输入验证增强 | 1-2 天 | 防止注入攻击 |
| 审计日志 | 1-2 天 | 合规审计 |
| 安全头配置 | 0.5 天 | 防止常见攻击 |
| **总计** | **4-6 天** | |

### 6.2 与现有安全措施的关系

| 现有措施 | 文件 | 本方案补充 |
|----------|------|-----------|
| AuthMiddleware | `auth_middleware.py` | 限流中间件 |
| CSRFMiddleware | `csrf_middleware.py` | 审计日志 |
| RBAC 权限 | `authz.py` | 输入验证 |
