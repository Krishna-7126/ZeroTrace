from __future__ import annotations

import time
from pathlib import Path

from config import DEFAULT_AUDIT_DIR, DEFAULT_START_URL
from ephemeral_workspace.audit_logger import AuditLogger
from ephemeral_workspace.browser_manager import BrowserManager
from ephemeral_workspace.file_guard import FileGuard
from ephemeral_workspace.workspace_manager import WorkspaceManager


def main() -> int:
    workspace = WorkspaceManager()
    browser = BrowserManager()
    paths = workspace.create()
    session_start_ts = time.time()

    guard = FileGuard(paths.root)
    guard.assert_allowed(paths.profile)
    guard.assert_allowed(paths.downloads)
    guard.assert_allowed(paths.user_files)

    audit = AuditLogger(session_id=workspace.session_label(), output_dir=Path(DEFAULT_AUDIT_DIR))
    audit.log("session_created", root=str(paths.root), mode="automated_e2e")

    try:
        audit.log("browser_launch_started", url=DEFAULT_START_URL)
        session = browser.launch(
            profile_dir=str(paths.profile),
            downloads_dir=str(paths.downloads),
            start_url=DEFAULT_START_URL,
        )
        audit.log("browser_launch_completed")

        # Keep session alive briefly to prove the full lifecycle can execute.
        session.page.wait_for_timeout(3000)
        audit.log("browser_runtime_elapsed", ms=3000)
    except Exception as exc:
        audit.log("session_error", error=str(exc))
        print(f"[!] E2E launch failed: {exc}")
        browser.close()
        workspace.destroy()
        return 1

    browser.close()
    killed = browser.force_kill_related_processes()
    audit.log("process_kill_fallback", killed_processes=killed)

    findings = guard.scan_host_persistence_paths(session_start_ts)
    audit.log("host_persistence_scan", findings=len(findings))

    stats = workspace.destroy()
    audit.log("workspace_wiped", files_wiped=stats.files_wiped, bytes_overwritten=stats.bytes_overwritten)

    summary_path = audit.write_summary()
    if not summary_path.exists() or not audit.events_path.exists():
        print("[!] E2E failed: audit artifacts missing")
        return 1

    print("[+] E2E success")
    print(f"[+] Audit events: {audit.events_path}")
    print(f"[+] Audit summary: {summary_path}")
    print(f"[+] Wipe stats: files={stats.files_wiped}, bytes={stats.bytes_overwritten}")
    print(f"[+] Host findings count: {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
