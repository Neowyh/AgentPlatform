"""Tests for tray control surface actions (spec requirement)."""

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.audit import AuditKind
from core.settings import CapabilityRule, RuntimeSettings
from core.tray import TrayController


def test_open_settings_and_view_audit_are_exposed(tmp_path: Path) -> None:
    """The control surface must expose Open Settings and View Local Audit.

    Spec: "控制：Pause / Disconnect / Open Settings / View Local Audit".
    """
    settings = RuntimeSettings(
        server_url="ws://127.0.0.1:8001",
        device_id="device-1",
        session_token="token",
        audit_db_path=str(tmp_path / "audit.db"),
    )
    config_path = tmp_path / "runtime.json"
    settings.config_path = str(config_path)
    controller = TrayController(
        settings=settings,
        private_key=Ed25519PrivateKey.generate(),
        consent_store_path=tmp_path / "consent.db",
    )

    # open_settings() returns the live settings object the UI edits in place
    settings_view = controller.open_settings()
    assert settings_view is controller.settings
    assert settings_view.device_id == "device-1"

    # view_local_audit() returns a view object the UI can render
    controller.settings.set_rule("local.files.write", CapabilityRule.DENY)
    controller.save_settings()
    audit_view = controller.view_local_audit()
    assert hasattr(audit_view, "entries")
    assert hasattr(audit_view, "clear")
    assert hasattr(audit_view, "integrity")
    # Entries are newest-first
    assert audit_view.entries, "audit should have CONFIG entries after save"
    assert audit_view.entries[0].kind == AuditKind.CONFIG
    # clear is callable and records the clear itself
    clearance = audit_view.clear(actor_id="alice")
    assert "entries_removed" in clearance
