from pathlib import Path

from ephemeral_workspace.secure_wiper import SecureWiper


def test_wipe_directory_removes_root(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()
    (target / "a.txt").write_text("secret", encoding="utf-8")
    (target / "b.bin").write_bytes(b"abc123")

    wiper = SecureWiper(passes=1)
    stats = wiper.wipe_directory(target)

    assert stats.files_wiped >= 2
    assert stats.bytes_overwritten > 0
    assert not target.exists()
