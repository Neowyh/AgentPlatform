"""Enterprise SkillStorage variants.

The upstream :class:`LocalSkillStorage` / :class:`UserScopedSkillStorage`
handle discovery and per-user isolation. The enterprise variants add the
intranet (offline) network-mode policy: skills declaring
``requires-internet: true`` in their SKILL.md frontmatter are hidden from
discovery when ``IDEER_NETWORK_MODE=offline`` (see
:mod:`app.agentplatform.config.network_mode`).

This preserves the pre-convergence ``ideer`` runtime behaviour documented in
``docs/platform-dev-summary.md`` ("Skill 加载过滤：requires_internet 字段跳过
需要联网的技能").
"""

from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from app.agentplatform.config.network_mode import is_offline
from deerflow.skills.storage.local_skill_storage import LocalSkillStorage
from deerflow.skills.storage.user_scoped_skill_storage import UserScopedSkillStorage
from deerflow.skills.types import Skill

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _frontmatter_requires_internet(skill_file: Path) -> bool:
    """Return the ``requires-internet`` flag from a SKILL.md frontmatter."""
    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError:
        return False
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return False
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return False
    if not isinstance(metadata, dict):
        return False
    return bool(metadata.get("requires-internet", False))


def _declares_internet(skill: Skill) -> bool:
    """Whether *skill* needs internet access.

    The enterprise :class:`app.agentplatform.resources.skill_types.Skill`
    carries ``requires_internet``; the upstream frozen dataclass does not,
    so fall back to reading the frontmatter.
    """
    declared = getattr(skill, "requires_internet", None)
    if declared is not None:
        return bool(declared)
    return _frontmatter_requires_internet(skill.skill_file)


def apply_offline_skill_policy(skills: Iterable[Skill]) -> list[Skill]:
    """Drop internet-dependent skills when running in offline (intranet) mode."""
    skills = list(skills)
    if not is_offline():
        return skills
    kept: list[Skill] = []
    skipped: list[str] = []
    for skill in skills:
        if _declares_internet(skill):
            skipped.append(skill.name)
            continue
        kept.append(skill)
    if skipped:
        logger.warning(
            "Offline mode: skipping %d internet-dependent skill(s): %s",
            len(skipped),
            ", ".join(sorted(skipped)),
        )
    return kept


class EnterpriseSkillStorage(LocalSkillStorage):
    """``LocalSkillStorage`` plus the enterprise offline-mode skill policy."""

    def load_skills(self, *, enabled_only: bool = False) -> list[Skill]:
        return apply_offline_skill_policy(super().load_skills(enabled_only=enabled_only))


class EnterpriseUserScopedSkillStorage(UserScopedSkillStorage):
    """``UserScopedSkillStorage`` plus the enterprise offline-mode skill policy."""

    def load_skills(self, *, enabled_only: bool = False) -> list[Skill]:
        return apply_offline_skill_policy(super().load_skills(enabled_only=enabled_only))


_user_scoped_storages: OrderedDict[str, tuple[Any, EnterpriseUserScopedSkillStorage]] = OrderedDict()
_user_scoped_lock = threading.Lock()
_MAX_USER_SCOPED_STORAGES = 64


def get_or_new_enterprise_user_skill_storage(user_id: str, **kwargs) -> EnterpriseUserScopedSkillStorage:
    """Return a per-user enterprise storage (LRU-cached, mirrors the upstream factory)."""
    from deerflow.config import get_app_config
    from deerflow.config.paths import make_safe_user_id

    safe_id = make_safe_user_id(user_id)
    app_config = kwargs.get("app_config")
    if app_config is None:
        app_config = get_app_config()
    kwargs["app_config"] = app_config

    with _user_scoped_lock:
        cached = _user_scoped_storages.get(safe_id)
        if cached is not None and cached[0] is app_config:
            _user_scoped_storages.move_to_end(safe_id)
            return cached[1]

        storage = EnterpriseUserScopedSkillStorage(safe_id, **kwargs)
        _user_scoped_storages[safe_id] = (app_config, storage)
        while len(_user_scoped_storages) > _MAX_USER_SCOPED_STORAGES:
            _user_scoped_storages.popitem(last=False)
        return storage
