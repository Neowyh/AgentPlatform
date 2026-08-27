"""Automation routes — list, create, delete workflow automations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.gateway.authz import get_current_rbac_user
from ideer.persistence.models.user import UserModel

router = APIRouter(prefix="/api/automations", tags=["automations"])


class AutomationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_id: str = Field(min_length=1, max_length=128)


AUTOMATION_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "daily-report",
        "name": "Daily Report",
        "description": "Generate daily work reports",
        "category": "reporting",
    },
    {
        "id": "weekly-report",
        "name": "Weekly Report",
        "description": "Generate weekly work reports",
        "category": "reporting",
    },
    {
        "id": "meeting-minutes",
        "name": "Meeting Minutes",
        "description": "Summarize meeting discussions",
        "category": "meetings",
    },
    {
        "id": "data-report",
        "name": "Data Report",
        "description": "Generate data analysis reports",
        "category": "reporting",
    },
    {
        "id": "anomaly-monitor",
        "name": "Anomaly Monitor",
        "description": "Monitor and alert on anomalies",
        "category": "monitoring",
    },
    {
        "id": "task-reminder",
        "name": "Task Reminder",
        "description": "Send task deadline reminders",
        "category": "reminders",
    },
    {
        "id": "meeting-reminder",
        "name": "Meeting Reminder",
        "description": "Send meeting schedule reminders",
        "category": "reminders",
    },
    {
        "id": "doc-change-notify",
        "name": "Document Change Notification",
        "description": "Notify on document changes",
        "category": "notifications",
    },
]


@router.get("/templates")
async def list_automation_templates() -> list[dict[str, Any]]:
    """List all automation templates."""
    return AUTOMATION_TEMPLATES


@router.get("")
async def list_automations(
    current_user: UserModel = Depends(get_current_rbac_user),
) -> list[dict[str, Any]]:
    """List user's automations."""
    return []


@router.post("", status_code=201)
async def create_automation(
    body: AutomationCreateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    """Create a new automation."""
    template_ids = [t["id"] for t in AUTOMATION_TEMPLATES]
    if body.template_id not in template_ids:
        raise HTTPException(400, f"Template {body.template_id!r} not found")
    return {
        "id": "automation-new",
        "name": body.name,
        "template_id": body.template_id,
        "status": "active",
    }


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(
    automation_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> None:
    """Delete an automation."""
    pass
