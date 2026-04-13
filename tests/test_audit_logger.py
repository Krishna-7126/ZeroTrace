from pathlib import Path

from ephemeral_workspace.audit_logger import AuditLogger


def test_audit_summary_and_integrity_files_created(tmp_path: Path) -> None:
    logger = AuditLogger(session_id="test-session", output_dir=tmp_path)
    logger.log("session_created", mode="test")
    logger.log("workspace_wiped", files_wiped=3, bytes_overwritten=33)
    summary_path = logger.write_summary()

    integrity_path = tmp_path / "test-session_integrity.txt"
    events_path = tmp_path / "test-session.jsonl"

    assert events_path.exists()
    assert summary_path.exists()
    assert integrity_path.exists()

    content = integrity_path.read_text(encoding="utf-8")
    assert "events_sha256=" in content
    assert "summary_sha256=" in content
