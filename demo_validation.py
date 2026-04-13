from __future__ import annotations

import tempfile
from pathlib import Path

from ephemeral_workspace.workspace_manager import WorkspaceManager


def main() -> int:
    manager = WorkspaceManager()
    paths = manager.create()

    # Simulate session artifacts.
    cookie_file = paths.profile / "Cookies"
    download_file = paths.downloads / "demo.txt"
    note_file = paths.user_files / "note.txt"

    cookie_file.write_text("session_cookie=abc123", encoding="utf-8")
    download_file.write_text("downloaded data", encoding="utf-8")
    note_file.write_text("user temp notes", encoding="utf-8")

    root = paths.root
    print(f"[+] Test data created in {root}")

    stats = manager.destroy()
    print(f"[+] Wipe stats: files={stats.files_wiped}, bytes={stats.bytes_overwritten}")

    if root.exists():
        print("[!] Validation failed: session root still exists")
        return 1

    # Spot-check temp directory for leftover path reference.
    tmp_dir = Path(tempfile.gettempdir())
    leftovers = [p for p in tmp_dir.glob("ephemeral_ws_*") if p.exists()]
    if leftovers:
        print(f"[!] Warning: found {len(leftovers)} other ephemeral directories: {leftovers}")
    else:
        print("[+] Validation passed: no ephemeral directories found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
