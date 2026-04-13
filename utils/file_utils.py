from __future__ import annotations

import time
from pathlib import Path


def is_subpath(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def scan_recent_file_writes(base: Path, session_start_ts: float) -> list[Path]:
    recent: list[Path] = []
    now = time.time()

    if not base.exists() or not base.is_dir():
        return recent

    for path in base.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue

        if session_start_ts <= mtime <= now:
            recent.append(path)

    return recent
