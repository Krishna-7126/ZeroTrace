from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from config import DEFAULT_AUDIT_DIR, DEFAULT_START_URL, DEFAULT_WIPE_PASSES
from ephemeral_workspace.audit_logger import AuditLogger
from ephemeral_workspace.browser_manager import BrowserManager
from ephemeral_workspace.file_guard import FileGuard
from ephemeral_workspace.workspace_manager import WorkspaceManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared-device ephemeral workspace launcher")
    parser.add_argument("--url", default=DEFAULT_START_URL, help="Initial URL to open")
    parser.add_argument("--wipe-passes", type=int, default=DEFAULT_WIPE_PASSES, help="Overwrite passes before delete")
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR), help="Path to write judge/audit logs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = WorkspaceManager(wipe_passes=args.wipe_passes)
    browser = BrowserManager()
    session_start_ts = time.time()

    paths = workspace.create()
    print(f"[+] Session created: {paths.root}")
    print(f"[+] Profile dir: {paths.profile}")
    print(f"[+] Downloads dir: {paths.downloads}")

    guard = FileGuard(paths.root)
    guard.assert_allowed(paths.profile)
    guard.assert_allowed(paths.downloads)
    guard.assert_allowed(paths.user_files)

    audit = AuditLogger(
        session_id=workspace.session_label(),
        output_dir=Path(args.audit_dir),
    )
    audit.log("session_created", root=str(paths.root), downloads=str(paths.downloads))
    is_shutdown = False

    def shutdown() -> None:
        nonlocal is_shutdown
        if is_shutdown:
            return
        is_shutdown = True

        print("[*] Closing browser session...")
        audit.log("shutdown_requested")
        browser.close()
        killed = browser.force_kill_related_processes()
        audit.log("process_kill_fallback", killed_processes=killed)

        host_findings = guard.scan_host_persistence_paths(session_start_ts)
        audit.log("host_persistence_scan", findings=len(host_findings))

        if host_findings:
            print("[!] Warning: possible host-persistent files touched during session:")
            for finding in host_findings[:15]:
                print(f"    - {finding}")
            if len(host_findings) > 15:
                print(f"    - ... and {len(host_findings) - 15} more")

        print("[*] Wiping temporary workspace...")
        stats = workspace.destroy()
        audit.log(
            "workspace_wiped",
            files_wiped=stats.files_wiped,
            bytes_overwritten=stats.bytes_overwritten,
        )

        print(f"[+] Wipe complete. Files wiped: {stats.files_wiped}, bytes overwritten: {stats.bytes_overwritten}")
        summary = audit.write_summary()
        print(f"[+] Audit summary written: {summary}")

    browser.install_ctrl_c_handler(on_interrupt=shutdown)

    try:
        audit.log("browser_launch_started", url=args.url)
        browser.launch(
            profile_dir=str(paths.profile),
            downloads_dir=str(paths.downloads),
            start_url=args.url,
        )
        audit.log("browser_launch_completed")
        print("[+] Browser launched. Close browser window or press Ctrl+C to end session.")
        browser.wait_until_closed()
        audit.log("browser_window_closed")
        shutdown()
    except Exception as exc:
        print(f"[!] Error: {exc}")
        audit.log("session_error", error=str(exc))
        shutdown()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
