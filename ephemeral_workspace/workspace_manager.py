from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .secure_wiper import SecureWiper, WipeStats


@dataclass
class SessionPaths:
    root: Path
    profile: Path
    downloads: Path
    user_files: Path


class WorkspaceManager:
    """Creates and destroys an ephemeral workspace for one browser session."""

    def __init__(self, base_prefix: str = "ephemeral_ws_", wipe_passes: int = 2) -> None:
        self._base_prefix = base_prefix
        self._wiper = SecureWiper(passes=wipe_passes)
        self.session_paths: SessionPaths | None = None

    def create(self, storage_root: Path | None = None) -> SessionPaths:
        if storage_root is None:
            session_root = Path(tempfile.mkdtemp(prefix=self._base_prefix))
        else:
            storage_root.mkdir(parents=True, exist_ok=True)
            session_root = Path(tempfile.mkdtemp(prefix=self._base_prefix, dir=str(storage_root)))

        profile = session_root / "profile"
        downloads = session_root / "downloads"
        user_files = session_root / "files"

        profile.mkdir(parents=True, exist_ok=True)
        downloads.mkdir(parents=True, exist_ok=True)
        user_files.mkdir(parents=True, exist_ok=True)

        self.session_paths = SessionPaths(
            root=session_root,
            profile=profile,
            downloads=downloads,
            user_files=user_files,
        )
        return self.session_paths

    def destroy(self) -> WipeStats:
        if not self.session_paths:
            return WipeStats()

        root = self.session_paths.root
        stats = self._wiper.wipe_directory(root)

        # Best-effort fallback if secure wipe had partial failures.
        if root.exists():
            self._remove_with_retries(root)

        self.session_paths = None
        return stats

    def session_label(self) -> str:
        return f"session-{int(time.time())}"

    @staticmethod
    def _remove_with_retries(root: Path, retries: int = 6, delay_sec: float = 1.5) -> None:
        for _ in range(retries):
            if not root.exists():
                return
            try:
                shutil.rmtree(root)
                return
            except Exception:
                time.sleep(delay_sec)

        shutil.rmtree(root, ignore_errors=True)
