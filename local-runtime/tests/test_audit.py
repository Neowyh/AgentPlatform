from core.audit import AuditKind, LocalAuditLog


def test_local_audit_lists_recent_events_newest_first(tmp_path) -> None:
    log = LocalAuditLog(db_path=tmp_path / "audit.db")

    log.record(AuditKind.TASK, "received", capability="local.files.write")
    log.record(AuditKind.EXECUTION, "completed", capability="local.files.write")

    recent = log.recent(limit=10)

    assert [(entry.kind, entry.action) for entry in recent] == [
        (AuditKind.EXECUTION, "completed"),
        (AuditKind.TASK, "received"),
    ]


def test_local_audit_survives_restart_and_stays_append_only(tmp_path) -> None:
    path = tmp_path / "audit.db"
    LocalAuditLog(db_path=path).record(
        AuditKind.CONSENT, "approved", capability="local.python", digest="abc"
    )

    reopened = LocalAuditLog(db_path=path)
    entry = reopened.recent(limit=5)[0]

    assert entry.action == "approved"
    assert entry.capability == "local.python"
    assert entry.digest == "abc"
    assert reopened.verify().ok is True


def test_a_cleared_log_still_verifies_and_keeps_its_seal(tmp_path) -> None:
    """Clearing hides history; it must not make the remaining chain look forged."""
    path = tmp_path / "audit.db"
    log = LocalAuditLog(db_path=path)
    for index in range(3):
        log.record(AuditKind.TASK, f"received-{index}", capability="local.files.read")
    before_clear = log.recent(limit=0)[0].entry_hash

    log.clear(actor_id="alice")
    reopened = LocalAuditLog(db_path=path)

    assert reopened.verify().ok is True
    assert reopened.verify().entries == 1
    assert [entry.action for entry in reopened.recent(limit=5)] == ["cleared"]
    assert reopened.clearances()[0]["last_entry_hash"] == before_clear
    # The chain resumes from the seal: a later entry verifies against it.
    reopened.record(AuditKind.TASK, "received-after")
    assert LocalAuditLog(db_path=path).verify().ok is True


def test_rewriting_a_row_after_a_clear_is_still_detected(tmp_path) -> None:
    path = tmp_path / "audit.db"
    log = LocalAuditLog(db_path=path)
    log.record(AuditKind.TASK, "received")
    log.clear(actor_id="alice")
    log.record(AuditKind.TASK, "after-clear")

    import sqlite3

    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE audit_entries SET action = 'tampered' WHERE kind = 'task'"
            " AND action = 'after-clear'"
        )
        db.commit()

    result = LocalAuditLog(db_path=path).verify()

    assert result.ok is False
    assert "chain broken" in (result.problem or "")
