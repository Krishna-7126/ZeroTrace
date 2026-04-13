from pathlib import Path

from ephemeral_workspace.preflight import run_preflight


def test_preflight_fails_on_negative_timeout(tmp_path: Path) -> None:
    result = run_preflight(
        session_type="browser",
        storage_root=tmp_path,
        app_path="",
        timeout_min=-1,
    )
    assert not result.ok
    assert any("Timeout minutes cannot be negative" in e for e in result.errors)


def test_preflight_fails_on_missing_app_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing_app.exe"
    result = run_preflight(
        session_type="app",
        storage_root=tmp_path,
        app_path=str(missing),
        timeout_min=0,
    )
    assert not result.ok
    assert any("App executable not found" in e for e in result.errors)
