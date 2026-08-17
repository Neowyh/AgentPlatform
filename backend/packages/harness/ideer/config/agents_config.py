"""Configuration types for custom agents.

Custom agents are catalog resources in canonical mode; this module keeps
the name-validation rules and the ``AgentConfig`` model used by canonical
resource loading.
"""

import logging
import re

from pydantic import BaseModel

logger = logging.getLogger(__name__)

AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


def validate_agent_name(name: str | None) -> str | None:
    """Validate a custom agent name before using it in filesystem paths."""
    if name is None:
        return None
    if not isinstance(name, str):
        raise ValueError("Invalid agent name. Expected a string or None.")
    if not AGENT_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid agent name '{name}'. Must match pattern: {AGENT_NAME_PATTERN.pattern}")
    return name


class AgentConfig(BaseModel):
    """Configuration for a custom agent."""

    name: str
    description: str = ""
    model: str | None = None
    tool_groups: list[str] | None = None
    # skills controls which skills are loaded into the agent's prompt:
    # - None (or omitted): load all enabled skills (default fallback behavior)
    # - [] (explicit empty list): disable all skills
    # - ["skill1", "skill2"]: load only the specified skills
    skills: list[str] | None = None
    visibility: str = "private"  # private | department | public
    owner_id: str | None = None
    department_id: str | None = None
