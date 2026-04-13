from __future__ import annotations

import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WipeStats:
    files_wiped: int = 0
    bytes_overwritten: int = 0


class SecureWiper:
    """Best-effort secure delete for files inside a session directory."""

    def __init__(self, passes: int = 2, chunk_size: int = 1024 * 1024) -> None:
        self.passes = max(1, passes)
        self.chunk_size = max(4096, chunk_size)

    def wipe_directory(self, directory: Path) -> WipeStats:
        stats = WipeStats()

        if not directory.exists():
            return stats

        for file_path in self._iter_files_bottom_up(directory):
            try:
                stats.bytes_overwritten += self._overwrite_file(file_path)
                stats.files_wiped += 1
            except Exception:
                # Continue wiping even if one file fails.
                pass

        shutil.rmtree(directory, ignore_errors=True)
        return stats

    def _iter_files_bottom_up(self, root: Path):
        for base, _, files in os.walk(root, topdown=False):
            for file_name in files:
                yield Path(base) / file_name

    def _overwrite_file(self, file_path: Path) -> int:
        size = file_path.stat().st_size
        if size == 0:
            file_path.unlink(missing_ok=True)
            return 0

        with file_path.open("r+b", buffering=0) as f:
            for _ in range(self.passes):
                f.seek(0)
                self._write_random_bytes(f, size)
                f.flush()
                os.fsync(f.fileno())

        file_path.unlink(missing_ok=True)
        return size * self.passes

    def _write_random_bytes(self, file_obj, total_size: int) -> None:
        remaining = total_size
        while remaining > 0:
            chunk_len = min(self.chunk_size, remaining)
            file_obj.write(secrets.token_bytes(chunk_len))
            remaining -= chunk_len
