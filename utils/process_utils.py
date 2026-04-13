from __future__ import annotations

from pathlib import Path

import psutil


def find_pids_by_cmdline_contains(needle: str) -> set[int]:
    needle_lc = needle.lower()
    pids: set[int] = set()
    for proc in psutil.process_iter(attrs=["pid", "cmdline"]):
        cmdline = " ".join(proc.info.get("cmdline") or [])
        if needle_lc in cmdline.lower():
            pids.add(proc.info["pid"])
    return pids


def kill_process_tree_for_profile(profile_dir: Path, baseline_pids: set[int] | None = None) -> int:
    pids = set(baseline_pids or set())
    pids.update(find_pids_by_cmdline_contains(str(profile_dir.resolve())))
    killed = 0

    for pid in sorted(pids):
        try:
            proc = psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        for child in proc.children(recursive=True):
            try:
                child.kill()
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        try:
            proc.kill()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return killed
