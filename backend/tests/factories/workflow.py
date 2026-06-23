"""工作流相关 factories。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


class WorkflowStateFactory:
    """构建模拟的工作流状态对象。

    Usage::

        from tests.factories import WorkflowStateFactory

        state = WorkflowStateFactory.build()
        state = WorkflowStateFactory.build(current_step="step-2", status="running")
    """

    @staticmethod
    def build(**kwargs) -> SimpleNamespace:
        uid = str(uuid4())[:8]
        defaults = {
            "workflow_name": f"test-workflow-{uid}",
            "run_id": f"run-{uid}",
            "status": "pending",
            "current_step": None,
            "steps_completed": [],
            "steps_failed": [],
            "context": {},
            "error": None,
            "started_at": None,
            "finished_at": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    @staticmethod
    def build_running(**kwargs) -> SimpleNamespace:
        """构建运行中的工作流状态。"""
        return WorkflowStateFactory.build(status="running", **kwargs)

    @staticmethod
    def build_completed(**kwargs) -> SimpleNamespace:
        """构建已完成的工作流状态。"""
        return WorkflowStateFactory.build(status="completed", **kwargs)


class WorkflowStoreFactory:
    """构建模拟的 WorkflowStore。

    Usage::

        from tests.factories import WorkflowStoreFactory

        store = WorkflowStoreFactory.build()
        store = WorkflowStoreFactory.build(list_result=([workflow], 1))
    """

    @staticmethod
    def build(**kwargs) -> MagicMock:
        store = MagicMock()
        store.list_workflows = AsyncMock(return_value=kwargs.get("list_result", ([], 0)))
        store.load_workflow = AsyncMock(return_value=kwargs.get("load_result"))
        store.save_workflow = AsyncMock(return_value=kwargs.get("save_result", None))
        store.delete_workflow = AsyncMock(return_value=kwargs.get("delete_result", True))
        store.load_run_state = AsyncMock(return_value=kwargs.get("load_run_result"))
        store.list_runs = AsyncMock(return_value=kwargs.get("list_runs_result", ([], 0)))
        store.save_review_result = AsyncMock(return_value=kwargs.get("save_review_result", None))
        return store
