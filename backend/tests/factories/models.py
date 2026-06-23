"""模型配置和工具信息 factories。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4


class AppConfigFactory:
    """构建模拟的 AppConfig 对象。

    Usage::

        from tests.factories import AppConfigFactory

        config = AppConfigFactory.build()
        config = AppConfigFactory.build(llm={"provider": "anthropic", "model": "claude-sonnet-4-20250514"})
    """

    @staticmethod
    def build(**kwargs) -> dict:
        defaults = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "test-key",
            },
            "sandbox": {"enabled": False},
            "persistence": {"checkpointer": {"type": "sqlite"}},
        }
        defaults.update(kwargs)
        return defaults


class ToolInfoFactory:
    """构建模拟的工具信息对象。

    Usage::

        from tests.factories import ToolInfoFactory

        tool = ToolInfoFactory.build()
        tool = ToolInfoFactory.build(name="web_search", group="search")
    """

    @staticmethod
    def build(**kwargs) -> SimpleNamespace:
        defaults = {
            "name": "test_tool",
            "description": "A test tool",
            "group": "test",
            "requires_network": False,
            "configurable": True,
            "config_schema": {},
            "param_schema": {},
            "config": {},
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    @staticmethod
    def build_batch(count: int, **kwargs) -> list[SimpleNamespace]:
        """构建多个工具信息对象。"""
        return [ToolInfoFactory.build(name=f"tool_{i}", **kwargs) for i in range(count)]


class UserFactory:
    """构建用户数据对象（SimpleNamespace）。

    Usage::

        from tests.factories import UserFactory

        user = UserFactory.build()
        user = UserFactory.build(role="admin", department_id="dept-1")
    """

    @staticmethod
    def build(**kwargs) -> SimpleNamespace:
        uid = str(uuid4())[:8]
        defaults = {
            "id": f"user-{uid}",
            "email": f"user-{uid}@test.com",
            "username": f"testuser-{uid}",
            "password_hash": "$2b$12$test_hash_value",
            "system_role": "user",
            "role": "user",
            "department_id": None,
            "oauth_provider": None,
            "oauth_id": None,
            "needs_setup": False,
            "token_version": 0,
            "disabled": False,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    @staticmethod
    def build_admin(**kwargs) -> SimpleNamespace:
        """构建管理员用户。"""
        return UserFactory.build(role="super_admin", system_role="admin", **kwargs)

    @staticmethod
    def build_batch(count: int, **kwargs) -> list[SimpleNamespace]:
        """构建多个用户。"""
        return [UserFactory.build(**kwargs) for _ in range(count)]
