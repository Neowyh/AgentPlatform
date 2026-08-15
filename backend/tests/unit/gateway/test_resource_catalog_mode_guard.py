from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.gateway.resource_catalog_mode import require_legacy_resource_facades


def test_legacy_facades_remain_available_in_legacy_and_dual_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for mode in ("legacy", "dual"):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", mode)
        assert require_legacy_resource_facades() is None


def test_canonical_mode_disables_every_name_addressed_facade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")

    with pytest.raises(HTTPException) as caught:
        require_legacy_resource_facades()

    assert caught.value.status_code == 410
    assert "resource UUID" in caught.value.detail
