from __future__ import annotations

from pathlib import Path

from utils.file_utils import is_subpath, scan_recent_file_writes


class FileGuard:
    """Enforces temp-root policy and checks common host folders for recent writes."""

    def __init__(self, allowed_root: Path) -> None:
        self.allowed_root = allowed_root.resolve()

    def is_allowed(self, candidate: Path) -> bool:
        return is_subpath(candidate, self.allowed_root)

    def assert_allowed(self, candidate: Path) -> None:
        if not self.is_allowed(candidate):
            raise PermissionError(f"Path is outside ephemeral workspace: {candidate}")

    def scan_host_persistence_paths(self, session_start_ts: float) -> list[Path]:
        home = Path.home()
        candidates = [home / "Desktop", home / "Documents", home / "Downloads"]
        findings: list[Path] = []

        for base in candidates:
            if not base.exists() or not base.is_dir():
                continue
            findings.extend(self._scan_recent(base, session_start_ts))

        return findings

    def _scan_recent(self, base: Path, session_start_ts: float) -> list[Path]:
        return scan_recent_file_writes(base, session_start_ts)
