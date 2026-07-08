"""TOCTOU race test for skill import.

import_skill() checks storage.custom_skill_exists → then writes.  Two
concurrent calls both see "not exists" and both proceed to write.  This
test proves the race exists by showing write_custom_skill is invoked
more than once.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateway.routers.skills import SkillImportRequest, import_skill
from ideer.persistence.models.user import UserModel, UserRole


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.skills.get_skills_path.return_value = "/tmp/skills"
    return cfg


@pytest.fixture
def mock_user():
    u = MagicMock(spec=UserModel)
    u.id = "user-1"
    u.role = UserRole.USER
    u.department_id = None
    return u


@pytest.mark.asyncio
async def test_concurrent_import_skill_toctou(mock_config, mock_user):
    """Two concurrent import calls — both pass the exists check, both write."""

    write_count = 0
    exists_count = 0

    def track_write(name, relative_path, content):
        nonlocal write_count
        write_count += 1

    def exists_side_effect(name):
        nonlocal exists_count
        exists_count += 1
        return exists_count > 2  # First 2 calls return False (both pass the check)

    mock_storage = MagicMock()
    mock_storage.custom_skill_exists.side_effect = exists_side_effect
    mock_storage.write_custom_skill.side_effect = track_write
    mock_storage.load_skills.return_value = []
    mock_storage.get_custom_skill_dir.return_value = MagicMock()
    mock_storage.validate_skill_markdown_content = MagicMock()

    request = SkillImportRequest(
        name="race-skill",
        content="# Race Skill\n\nTest skill.",
        visibility="private",
    )

    with (
        patch(
            "app.gateway.routers.skills.get_or_new_skill_storage",
            return_value=mock_storage,
        ),
        patch(
            "app.gateway.routers.skills.scan_skill_content",
            new_callable=AsyncMock,
        ) as mock_scan,
        patch("app.gateway.routers.skills._save_skill_meta", AsyncMock()),
        patch(
            "app.gateway.routers.skills.refresh_skills_system_prompt_cache_async",
            AsyncMock(),
        ),
    ):
        mock_scan.return_value = MagicMock(decision="allow", reason="ok")

        results = await asyncio.gather(
            import_skill(request, config=mock_config, current_user=mock_user),
            import_skill(request, config=mock_config, current_user=mock_user),
            return_exceptions=True,
        )

    for r in results:
        assert not isinstance(r, Exception), f"Unexpected exception: {r}"

    assert write_count > 1, f"write_custom_skill called {write_count} time(s) — expected > 1 (TOCTOU race not triggered)"
    assert exists_count >= 2, f"custom_skill_exists called {exists_count} time(s) — expected >= 2 (both calls must check existence)"
